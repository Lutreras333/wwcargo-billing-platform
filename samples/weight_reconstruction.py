"""
Weight reconstruction -- recovering billing weights the logistics API stored
in a systematically distorted form.

This is a faithful, runnable illustration of the production rule described in
docs/engineering-highlights.md #1. All data here is FICTIONAL.

The distortion: suppliers type each shipment line's TOTAL weight into a field
the platform treats as PER-UNIT, so the platform's stored `total_weight`
(= per_unit * quantity) is inflated by the case count. The value the supplier
actually entered survives, untouched, in `unit_weight`. The real billing
weight is therefore the SUM of `unit_weight` across a shipment's lines --
grossed up for sub-full-box shipments, since those are billed as one full
equivalent box.

The rule below was validated against months of already-billed shipments as
ground truth: 470 of 470 exact, max residual 0.04 kg.
"""

from dataclasses import dataclass


LB_TO_KG = 0.453592


@dataclass
class Line:
    """One raw shipment line as the platform's web interface returns it."""
    unit_weight: float          # what the supplier typed -- the LINE total
    unit_dim_weight: float      # dimensional weight per the line
    unit_code: str              # 'kg' or 'lb'
    eq_boxes: float             # full-box equivalents for this line


def _kg(value: float, unit_code: str) -> float:
    return value * LB_TO_KG if unit_code.lower() == "lb" else value


def reconstruct(lines: list[Line]) -> tuple[int, int]:
    """Return (gross_kg, chargeable_kg) for one shipment, rounded to whole
    kilos the way the company's export does (half-up).

    gross      = sum(unit_weight),  grossed up by 1/eq_boxes when the whole
                 shipment is under one full-box equivalent
    chargeable = sum(unit_dim_weight)   -- pure dimensional; may be BELOW
                 gross, so we deliberately do NOT take max(gross, chargeable)
    """
    gross = sum(_kg(ln.unit_weight, ln.unit_code) for ln in lines)
    chargeable = sum(_kg(ln.unit_dim_weight, ln.unit_code) for ln in lines)
    eq = sum(ln.eq_boxes for ln in lines)

    if 0 < eq < 1:                      # sub-full-box -> bill one full box
        gross /= eq

    return int(gross + 0.5), int(chargeable + 0.5)


# --------------------------------------------------------------------------- #
# A worked example. A 22-box shipment whose stored `total_weight` would read a
# nonsensical ~5,285 lb (per-unit * 22) is reconstructed from the raw entries.
if __name__ == "__main__":
    shipment = [
        Line(unit_weight=48.92, unit_dim_weight=54.10, unit_code="kg",
             eq_boxes=6.5),
        Line(unit_weight=16.31, unit_dim_weight=18.02, unit_code="kg",
             eq_boxes=2.0),
        Line(unit_weight=122.31, unit_dim_weight=131.4, unit_code="kg",
             eq_boxes=11.5),
        Line(unit_weight=24.46, unit_dim_weight=31.5, unit_code="kg",
             eq_boxes=2.0),
    ]
    gross, chargeable = reconstruct(shipment)
    print(f"gross {gross} kg / chargeable {chargeable} kg")   # 212 kg / 235 kg
    # vs. the platform's stored, inflated total of ~5,285 lb.
