# Engineering highlights

Three problems from the WWCARGO build that were interesting to solve. Data and
identifiers below are fictional.

---

## 1. Reconstructing weights the API wouldn't give up

**The problem.** Freight is billed by weight, but the logistics API's read
endpoints didn't return one. Worse, the weights that *were* stored were
physically impossible — a house shipment of 22 flower boxes showing 5,285 lb.

**The investigation.** I pulled every field the platform's web interface
exposed (~300 per shipment line) and compared them against months of invoices
the company had already billed by hand — real ground truth. Fitting candidate formulas across
all fields, conditioned on discriminators (unit codes, single- vs. multi-item
shipments, sub-full-box quantities), the pattern emerged:

> Suppliers type each line's **total** weight into a field the system treats as
> **per-unit**. The system then multiplies by the case count. So the stored
> `totalWeight` is inflated by quantity — but the raw per-line value the
> supplier entered still sits, untouched, in a different field.

**The rule.** Sum the raw per-line entries; gross up sub-full-box shipments by
their box fraction; use dimensional weight (not the inflated field) for
chargeable weight; round to whole kilos the way the export does.

**The result.** Three independent rule-fitting passes converged on the same
formula, and an adversarial re-check confirmed it:

```
Flight A:  166 / 166 shipments exact  (gross + chargeable)
Flight B:  102 / 102 shipments exact
Flight C:  202 / 202 shipments exact
—————————————————————————————————————
Total:     470 / 470   (max residual 0.04 kg)
```

The lesson I keep from this: *a first-pass mismatch is a starting point, not a
verdict.* The value the business bills on existed in the data all along — it
just had to be recovered from a systematic distortion, not read off a field.

See [`samples/weight_reconstruction.py`](../samples/weight_reconstruction.py).

---

## 2. Parsers that prove instead of guess

**The problem.** Vendor invoices arrive as PDFs whose layout drifts — a memo
block wraps differently, a column is populated on some invoices and blank on
others, occasionally two charge lines appear where the parser expected one. A
parser that "does its best" on financial data will eventually write a wrong
number that nobody notices until reconciliation.

**The principle.** A parser may only emit a record it can *prove*. For a vendor
invoice that means every one of these must hold, or the record is skipped with
a stated reason:

- the charge table has exactly the expected number of values (a stray column
  or a second charge line changes the count → skip),
- the flat-fee line's rate equals its amount,
- the memo's itemized fees **sum to** the invoice total,
- the piece counts on the memo agree with the charge line,
- the invoice's own printed total agrees with the charge line.

**Why loud-skip beats best-effort.** A skipped invoice surfaces as a visible
"needs a human" item and gets handled in minutes. A silently mis-parsed invoice
becomes a wrong bill that ships to a customer or a vendor and surfaces — if ever
— as an angry email weeks later. In financial software the asymmetry is total,
so the parser is deliberately strict.

See [`samples/proving_parser.py`](../samples/proving_parser.py).

---

## 3. Machine gates in place of human approval

**The problem.** The mandate was full automation — no human approving invoices.
But "no human in the loop" cannot mean "no check in the loop." The judgment a
person used to apply had to be replaced with explicit, conservative machine
conditions.

**The gates.** Before any invoice is created and sent, all of these must pass:

1. the flight's spreadsheet rows **re-verify** against the source manifests,
2. every client and product **resolved** cleanly (zero unknowns),
3. the pre-send **audit** is clean (totals reconcile),
4. the customer has an **email on file**.

If any gate fails, the flight is **held** — nothing is sent — and a Telegram
alert explains exactly why. The next scheduled cycle retries; a held flight
that gets its missing piece flows through automatically.

**The stance.** The system is built to *stop* rather than improvise. It would
rather hold a correct invoice for an hour than send a wrong one instantly. That
bias — fail safe, alert, retry — is what makes hands-off operation on real money
defensible.

See [`samples/verification_gate.py`](../samples/verification_gate.py).
