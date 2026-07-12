"""
Verification gate -- the machine conditions that replace human approval in a
fully-automated billing pipeline. Nothing is sent unless ALL gates pass;
anything short of that is HELD and reported.

Faithful, runnable illustration of docs/engineering-highlights.md #3. All data
is FICTIONAL. This mirrors the endpoint the scheduler calls per flight: it
re-verifies the boxes against source, checks resolution/audit/email, and only
then invoices -- otherwise it returns a HOLD with a human-readable reason.
"""

from dataclasses import dataclass, field


@dataclass
class FlightState:
    awb: str
    verify_findings: list[str] = field(default_factory=list)  # empty == clean
    unresolved_entities: list[str] = field(default_factory=list)
    audit_ok: bool = True
    customer_email: str | None = None


@dataclass
class GateResult:
    sent: bool
    held: bool
    reason: str


def invoice_flight(flight: FlightState, *, send) -> GateResult:
    """Create + send the flight's invoices, but only through four hard gates.
    `send` is the side-effecting call; it is reached only if every gate passes.
    """
    # Gate 1 -- the boxes must still match their source files. A stale or
    # hand-edited row that no longer reconciles stops everything.
    if flight.verify_findings:
        return _hold(flight, "verification failed: "
                     + "; ".join(flight.verify_findings))

    # Gate 2 -- every client/product resolved. An unknown entity means we
    # might bill the wrong account; never guess an identity.
    if flight.unresolved_entities:
        return _hold(flight, "unresolved: "
                     + ", ".join(flight.unresolved_entities))

    # Gate 3 -- the pre-send audit (totals reconcile end to end).
    if not flight.audit_ok:
        return _hold(flight, "pre-send audit did not reconcile")

    # Gate 4 -- a customer email on file. No destination, no send.
    if not flight.customer_email:
        return _hold(flight, "no customer email on file")

    send(flight)
    return GateResult(sent=True, held=False,
                      reason=f"{flight.awb}: invoiced + sent")


def _hold(flight: FlightState, why: str) -> GateResult:
    # In production this also fires a Telegram alert; the next scheduled
    # cycle retries, so a flight that gets its missing piece flows through
    # automatically with no further action.
    return GateResult(sent=False, held=True, reason=f"HELD {flight.awb}: {why}")


if __name__ == "__main__":
    calls = []
    clean = FlightState(awb="000-0000-0001",
                        customer_email="ap@northstar.example")
    print(invoice_flight(clean, send=calls.append).reason)      # sent

    missing = FlightState(awb="000-0000-0002")                  # no email
    print(invoice_flight(missing, send=calls.append).reason)    # HELD

    stale = FlightState(awb="000-0000-0003",
                        verify_findings=["row 12: boxes 5 vs source 6"],
                        customer_email="ap@evergreen.example")
    print(invoice_flight(stale, send=calls.append).reason)      # HELD

    print("actually sent:", [f.awb for f in calls])             # only #0001
