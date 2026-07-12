# Architecture

A design walkthrough of the WWCARGO billing platform. Code samples referenced
here use fictional data; the production repository is private.

## The core split: schedule vs. work

The single most important decision was keeping the *scheduler* and the *worker*
completely separate.

- **n8n** (a self-hosted workflow engine) does nothing but fire on a schedule
  and send notifications. It holds no business logic. Its workflows are plain
  JSON that version-controls and moves between machines.
- **The runner** is a small Python HTTP service that exposes the pipeline over
  authenticated endpoints (`/check-flights`, `/process-flight`, `/invoice`,
  …). All the real logic — parsing, bookkeeping, verification, billing — lives
  here and is identical whether triggered by the scheduler or run by hand.

```
n8n (clock + dashboard)  ──HTTP──►  runner (Python)  ──►  Sheets + QuickBooks
        every 30 min                 all business logic
```

Why it matters: the intelligence is testable in isolation (67 unit tests hit
the Python directly, no scheduler needed), the scheduler is swappable (cron or
Task Scheduler could replace n8n without touching a line of logic), and a human
running a command gets byte-identical behavior to the 3 a.m. automated run.

## Data sources, and why there are several

No single system holds everything, so the platform fuses three feeds:

| Source | Provides | Notes |
|--------|----------|-------|
| Logistics **partner API** | Flight detection, manifest structure | Fast; sees a flight before its paperwork exists |
| Logistics **web interface** | Per-line weights & marcaciones | The billing weights are *reconstructed* from the raw shipment rows (see engineering highlights) |
| **Email** (vendor invoices, duties reports) | Vendor charges, declared values | Parsed from PDF; some data lives only here |

Detection is API-driven; billing figures are cross-checked between sources. When
a flight is detected before its email arrives, the pipeline records it and
quietly retries next cycle rather than failing.

## The trust model

This system moves real money with no human clicking "send," so trust is
enforced structurally, not assumed:

1. **Write, then verify.** After any spreadsheet write, an independent pass
   re-reads the sheet and diffs it against the source files. A mismatch stops
   the flight and alerts a human.
2. **Prove before booking.** Parsers reject any record whose numbers don't
   reconcile internally (fee lines summing to totals, piece counts agreeing).
   A loud skip always beats a silent wrong number.
3. **Gate before sending.** Invoicing requires: verification passed, zero
   unresolved entities, a clean audit, and a customer email on file. Anything
   short of all four → held and flagged.

## Idempotency

Every writer is safe to run repeatedly. Each dedupes against the live state
before writing, so the hourly schedule can re-run freely and a crash mid-batch
loses nothing:

- **Dedupe on identity** — a flight/client already present is never rewritten.
- **Adopt-on-duplicate** — if a create times out but actually landed
  server-side, the next run finds it by document number, verifies it matches,
  and adopts it instead of creating a double.
- **Per-record writeback** — identifiers are written back the instant each
  record is created, not batched at the end, so a timeout can't orphan work.
- **Persistent queues** — cross-stage handoffs use a small on-disk queue that
  only releases an item once its downstream rows verifiably exist.

## The spreadsheet as the human interface

The company's book of record is a Google Sheet, and people read and edit it
daily. So formatting is treated as part of the data contract: colors,
borders, merged cells, and approval stamps are reproduced exactly, because a
row that looks wrong reads as wrong to the humans who rely on it. Getting this
right — matching a hand-drawn stamp's font, weight, border style, and
alignment — was as much of the work as the numbers.

## Deployment & portability

Because the whole stack is containers + a Python service, moving it to a new
machine is a copy, not a rebuild:

1. `git clone` the (private) repo.
2. Copy the git-ignored secrets and state files.
3. Run one bootstrap script — `setup.sh` (Linux) or `setup.ps1` (Windows) —
   which installs dependencies, registers the runner as a boot service, brings
   up the scheduler, imports the workflows, and wires notifications.

The same workflow JSON runs identically on a laptop, a cloud VPS, or a company
VM. Migration is: stand up the new machine, deactivate the old scheduler.

## Security posture

- No credential, API key, or token ever enters version control (enforced by
  `.gitignore`, verified against full history). Secrets live only on the
  machines that run the pipeline.
- The runner is protected by a shared secret on every request.
- Untrusted input (emails, PDFs, API responses) is treated as *data, never
  instructions* — it can propose a row but can never trigger a send on its own.
