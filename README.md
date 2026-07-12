# WWCARGO — Billing Automation Platform

[![samples](https://github.com/Lutreras333/wwcargo-billing-platform/actions/workflows/samples.yml/badge.svg)](https://github.com/Lutreras333/wwcargo-billing-platform/actions/workflows/samples.yml)
![python](https://img.shields.io/badge/python-3.13-blue)
![status](https://img.shields.io/badge/status-in%20production-success)

> A production system that automates the end-to-end billing cycle of a
> fresh-flower air-cargo business (South America → Miami): flight detection,
> shipment-manifest ingestion, spreadsheet bookkeeping, and customer/vendor
> invoicing — with machine-verification gates in front of every dollar.

**This is a public showcase.** The production repository is private (it embeds
real client and pricing data). The code samples here use fictional data and
exist to demonstrate the architecture and engineering decisions. Happy to walk
through the real system in an interview.

---

## The problem

A logistics company billed every flight by hand: reading shipment
manifests and vendor invoices out of email, transcribing them into a sprawling
Google Sheet with live formulas, and keying customer invoices and vendor bills
into QuickBooks one at a time. Hours per day, and a single fat-fingered weight
or a missed markup quietly costs real money.

The goal: make it run itself — detect each flight automatically, do the
bookkeeping and billing exactly the way the humans did (down to the sheet's
colors, borders, and stamps), and only involve a person when something doesn't
reconcile.

## What it does

```
 Logistics API + web session ─┐        ┌─► Google Sheets  (the company's books)
 (flight detection, manifests,│        │
  reconstructed weights)      ├─runner ┤
 Email (vendor invoice PDFs,  │(Python │
  duties reports)            ─┘ tools) └─► QuickBooks Online  (customer
                                ▲            invoices + vendor bills)
                                │ authenticated HTTP
                          n8n schedules ──► Telegram alerts
```

| Stage | What happens |
|-------|-------------|
| **Detect** | A scheduled job polls the logistics API; a new flight appears minutes after takeoff, before any email arrives. |
| **Ingest** | Manifests and vendor invoice PDFs are pulled and parsed. A weights figure the API doesn't expose is *reconstructed* from raw shipment rows (see below). |
| **Book** | Six spreadsheet ledgers are written with live formulas and exact formatting — the sheet stays human-readable and hand-editable. |
| **Verify** | Every write is re-checked against its source files before any money moves. |
| **Bill** | Customer invoices and vendor bills are created and sent in QuickBooks — machine-gated: anything that doesn't reconcile is *held* and flagged, never sent. |

## Results

- Processes **six figures of billing volume per month**, unattended.
- Replaced a multi-hour daily manual process end to end.
- **67 automated tests**, run in CI on every commit.
- Deployable to any always-on machine with one script (Linux or Windows).

## By the numbers

| | |
|---|---|
| Money lanes automated | 6 ledgers × 2 country pipelines |
| Weight reconstruction accuracy | 470 / 470 shipments, exact to the kg |
| Integrations | Google Sheets · Gmail · QuickBooks Online · logistics API + web · Telegram |
| Automated tests | 67, green in CI |
| Human steps to run a flight | 0 (machine-gated) |
| Time to migrate to a new machine | one script |

See the full [capabilities catalog](docs/capabilities.md) for everything the
platform does.

---

## Engineering highlights

Three problems worth reading about — full writeups in
[`docs/engineering-highlights.md`](docs/engineering-highlights.md):

**1. Reconstructing weights the API wouldn't give up.**
The billing weights weren't exposed by the logistics API, and its stored totals
were corrupted by a data-entry quirk (suppliers typed line *totals* into a
*per-unit* field, so the system multiplied them by the case count). By treating
months of already-billed invoices as ground truth and fitting candidate rules
across every field, I recovered the exact per-line weights —
[**verified to the kilogram on 470 of 470 shipments across three flights**](samples/weight_reconstruction.py).

**2. Parsers that prove instead of guess.**
Financial parsers never write an unproven number. A vendor invoice is only
booked if its memo *reconciles with its own totals* — fee lines must sum to the
invoice total, piece counts must agree, the printed total must match the charge
line. [Anything off is skipped loudly, never silently guessed.](samples/proving_parser.py)

**3. Machine gates in place of human approval.**
Full automation without a human in the loop demanded a hard safety layer:
[re-verify every write against source, hold on any resolver problem or audit
failure, and require a customer email on file before sending.](samples/verification_gate.py)
Anything questionable is held and pinged, not sent.

---

## Stack

**Language** Python 3.13 ·
**Integrations** Google Sheets & Gmail APIs, QuickBooks Online API, a logistics
platform (REST API + authenticated web interface) ·
**Automation** n8n (scheduling), Docker, systemd/Task-Scheduler services ·
**Quality** pytest (67 tests), GitHub Actions CI ·
**Notifications** Telegram

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design — the
schedule/worker split, the trust model, idempotency, and how the whole stack
migrates between machines by re-running one script.

---

## How it was built

Designed and built by **Lucas Utreras Acevedo** (Computer Engineering) for an
air-cargo logistics company. I used an AI assistant as a pair-programmer to accelerate
implementation; the architecture, the trade-offs, and every design decision are
mine, and I can defend each one. I believe in being transparent about how modern
software gets built.
