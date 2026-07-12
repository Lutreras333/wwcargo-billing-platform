"""
Idempotent writer -- why the scheduled pipeline can re-run every hour, and
survive a crash mid-batch, without ever double-billing.

Faithful illustration of the idempotency patterns in ARCHITECTURE.md. All data
is FICTIONAL. The three defenses shown:

  1. dedupe on identity        -- never write a record that already exists
  2. adopt-on-duplicate        -- a create that timed out but LANDED server-side
                                  is found and adopted, not recreated
  3. per-record writeback      -- the id is recorded the instant a record is
                                  created, so a timeout can't orphan the work
"""

from dataclasses import dataclass, field


@dataclass
class Ledger:
    """Stand-in for the accounting system (QuickBooks in production)."""
    by_doc: dict = field(default_factory=dict)          # doc_number -> record

    def find(self, doc_number: str):
        return self.by_doc.get(doc_number)

    def create(self, record: dict):
        doc = record["doc_number"]
        if doc in self.by_doc:                          # server rejects dupes
            raise DuplicateDocument(doc)
        self.by_doc[doc] = record
        return record


class DuplicateDocument(Exception):
    def __init__(self, doc):
        super().__init__(doc)
        self.doc = doc


def bill_once(ledger: Ledger, plan: dict, *, already_written: set) -> str:
    """Create the bill for `plan`, exactly once, no matter how many times this
    runs or where a prior run died. Returns a short status.
    """
    doc = plan["doc_number"]

    # (1) dedupe on identity -- our own record of what we've written.
    if doc in already_written:
        return f"{doc}: already done (skipped)"

    try:
        record = ledger.create(plan)
        # (3) per-record writeback -- record the id NOW, before doing anything
        # else, so a crash on the next line can't lose this fact.
        already_written.add(doc)
        return f"{doc}: created (${record['total']:.2f})"

    except DuplicateDocument:
        # (2) adopt-on-duplicate -- a previous run's create timed out on our
        # side but actually landed. Find it, verify it matches, and adopt it
        # instead of creating a second bill.
        existing = ledger.find(doc)
        if existing and abs(existing["total"] - plan["total"]) < 0.02:
            already_written.add(doc)
            return f"{doc}: adopted existing (matches)"
        # It exists but does NOT match -> a real conflict a human must see.
        return f"{doc}: CONFLICT -- exists as ${existing['total']:.2f}, " \
               f"plan is ${plan['total']:.2f} (held)"


if __name__ == "__main__":
    ledger, seen = Ledger(), set()
    plan = {"doc_number": "B-2001", "total": 512.25}

    print(bill_once(ledger, plan, already_written=seen))   # created
    print(bill_once(ledger, plan, already_written=seen))   # already done

    # Simulate a prior run that landed the bill but crashed before writeback:
    seen2 = set()
    print(bill_once(ledger, plan, already_written=seen2))  # adopted existing
