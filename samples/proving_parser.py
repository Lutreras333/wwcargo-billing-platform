"""
Proving parser -- a financial parser that emits a record only if it can prove
the record reconciles with its own totals. Otherwise it skips LOUDLY, with a
stated reason, and never guesses.

Faithful, runnable illustration of the pattern in docs/engineering-highlights.md
#2. All data is FICTIONAL. Returns (record | None, reason | None): exactly one
is non-None, so a caller can log every skip.
"""

import re

TOLERANCE = 0.02        # cents of float noise


def _money(text: str) -> float | None:
    try:
        return float(text.replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def parse_service_invoice(text: str):
    """A single flat-fee service invoice (e.g. a fumigation or handling fee).

    PROVEN or SKIPPED. Every guard below is a real failure mode seen in
    production PDFs whose layout drifts.
    """
    lines = [ln.strip() for ln in text.splitlines()]

    def after(label: str) -> str:
        for i, ln in enumerate(lines):
            if ln == label and i + 1 < len(lines):
                return lines[i + 1]
        return ""

    invoice = after("Invoice #")
    if not invoice:
        return None, "no invoice number"

    # The charge table prints as bare values under the column headers:
    #   <description> <pieces> <full boxes> <rate> <amount>
    try:
        start = lines.index("Amount")
    except ValueError:
        return None, "no charge table"

    nums, i = [], start + 1
    while i < len(lines) and not lines[i].startswith("CLIENT"):
        if re.fullmatch(r"[\d,]+(\.\d+)?", lines[i]):
            nums.append(_money(lines[i]))
        i += 1

    # EXACTLY four values. A populated optional column or a second charge line
    # shifts the positions and would otherwise write a wrong number silently.
    if len(nums) != 4:
        return None, f"charge table has {len(nums)} values, expected 4: {nums}"

    pieces, _boxes, rate, amount = nums
    if rate != amount:
        return None, (f"rate {rate} != amount {amount} -- not the single "
                      "flat-fee layout this parser knows")
    if pieces != int(pieces):
        return None, f"piece count {pieces} is not whole"

    # The memo must PROVE the header: itemized fees must sum to the total.
    fees = []
    for ln in lines[i:]:
        m = re.match(r"^(.+?)\s+\$([\d,]+\.?\d*)$", ln)
        if m:
            fees.append((m.group(1).strip(), _money(m.group(2))))
    fee_sum = sum(f for _name, f in fees)
    if abs(fee_sum - amount) > TOLERANCE:
        return None, f"fee lines sum {fee_sum:.2f} != total {amount:.2f}"

    # ...and the invoice's own printed Total must agree with the charge line
    # (catches a second charge line the collection window would have flattened).
    printed = [_money(ln) for ln in lines
               if re.fullmatch(r"\$[\d,]+\.\d{2}", ln)]
    if not printed or abs(printed[0] - amount) > TOLERANCE:
        got = f"{printed[0]:.2f}" if printed else "none"
        return None, f"printed total ({got}) != charge line {amount:.2f}"

    return {"invoice": invoice, "pieces": int(pieces), "total": amount,
            "fees": fees}, None


if __name__ == "__main__":
    good = (
        "Invoice #\nF-1001\nDescription\nPieces\nKilo\nFull Boxes\nRate\n"
        "Amount\nFumigation Fee\n1\n0.25\n120.00\n120.00\n"
        "CLIENT NORTHSTAR FLORAL\nFUMIGATION $80.00\nHANDLING $40.00\n"
        "$120.00\n$120.00\n$0.00\n"
    )
    print(parse_service_invoice(good))            # (record, None)

    tampered = good.replace("HANDLING $40.00", "HANDLING $45.00")
    print(parse_service_invoice(tampered))        # (None, 'fee lines sum ...')
