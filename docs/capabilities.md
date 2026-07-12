# Capabilities

The full scope of what the WWCARGO platform does. Each item below is
implemented, tested, and running in production. Identifiers and figures are
generalized; the production repository is private.

## Ingestion — getting the data in

- **Automated flight detection** via a logistics partner API — a new flight is
  picked up within minutes of takeoff, before its paperwork lands.
- **Manifest reconstruction** from the logistics platform's web interface,
  including a per-line **weight reconstruction** that recovers the exact billing
  weights from the raw shipment rows (verified to the kilogram on every shipment
  of three test flights).
- **Email ingestion** — pulls the right attachments (shipment relations, duties
  reports, vendor invoice PDFs, phytosanitary certs) out of the inbox by
  flight, into a working folder.
- **PDF parsing** for every vendor-invoice variety, with strict validation
  (see "proving parsers").
- **AI-assisted document reading** — an air-waybill image is read by a vision
  model to extract chargeable weight and rate, then cross-checked against the
  manifest before anything is trusted.

## Bookkeeping — the six ledgers

Each is written with live spreadsheet formulas and exact formatting so the
sheet stays human-readable and hand-editable:

| Ledger | What it holds |
|--------|---------------|
| Flight summary | Per-flight totals, cost/margin, the summary row every other tab references |
| Customer freight | One billable row per client (and marcación), the numbers customers are charged on |
| Duties | Per-farm declared value and duty (variety-aware rates), grouped by client with live total blocks |
| Vendor billing | Per-flight cost blocks that become the vendor bills, with approval stamps |
| Pallets | One row per pallet charge, deduped against what's already billed |
| Miscellaneous | The odd charges (destruction, fumigation) parsed from vendor PDFs |

Two country pipelines feed these — an origin-A flow and an origin-B flow with
different tariffs, client-resolution rules, and layout conventions — unified
into the same ledgers.

## Billing — money out

- **Customer invoices** created and sent in QuickBooks Online (freight, duties,
  pallets), each behind the verification gates.
- **Vendor bills** created for the freight company's own costs, with
  approval stamps reproduced pixel-for-pixel from the hand-drawn originals so a
  human can pay down the list.
- **Timeout-safe sending** — a create that times out but landed server-side is
  detected and adopted, never duplicated; send status is re-queried before any
  retry so an invoice is never sent twice.
- **Rate corrections** — a bulk tool that re-rates a range of already-issued
  bills when a tariff changes, marks them corrected, and refuses to touch any
  bill that's already been paid.

## Analysis

- **Six-figure tariff-refund workbook** — reconstructs a customs-refund claim
  from months of duties history, classifying each line by the rate actually
  charged and computing the refundable portion per client.

## Automation & operations

- **Scheduler** (n8n) — polls for flights every 30 minutes and sweeps vendor
  invoices hourly; all logic lives in a separate Python service it calls.
- **Runner service** — exposes the whole pipeline over authenticated HTTP so
  the scheduler, or a human, drives identical behavior.
- **Machine-gated invoicing** — full automation with no human approval, made
  safe by hard gates (verify, resolve, audit, email-on-file) that hold and
  alert instead of sending when anything is off.
- **Telegram notifications** — the human is pinged only when something needs
  them; silence means it's handled.
- **One-command deployment** to any always-on machine (`setup.sh` for Linux,
  `setup.ps1` for Windows), including boot-time service registration and
  workflow import. The same stack moves between a laptop, a cloud VPS, and a
  company VM unchanged.

## Quality & safety

- **67 automated tests**, run in CI on every commit.
- **Idempotent by design** — every writer dedupes against live state; the
  schedule can re-run freely and a crash mid-batch loses nothing.
- **Verify-before-money** — every write is diffed against its source before any
  billing action.
- **Secrets never in version control** — enforced and audited against full
  history; credentials live only on the running machines.
