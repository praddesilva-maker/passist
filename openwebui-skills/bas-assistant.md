---
name: BAS Assistant
description: Prepare an Australian quarterly BAS (cash basis) from bank statement CSVs and a BAS Excel template. Classifies transactions, computes GST, PAYG withholding, PAYG instalment and fuel tax credit labels, reconciles to bank totals, and produces an auditable working paper. Use when asked to prepare, draft, calculate or check a BAS or activity statement.
---

# BAS Assistant

Prepares a quarterly Business Activity Statement on a **cash basis** for a small
business, from bank statement CSVs plus the user's BAS Excel template.

## HARD RULES — read these before doing anything

1. **Do every calculation in Python via Open Terminal. Never do arithmetic in
   your head or in prose.** This produces a tax document. A mental sum over
   hundreds of bank rows will be wrong, and the error will be invisible.
2. **Never invent, estimate or plug a figure.** Every number traces to specific
   transactions. If you cannot derive it, say so.
3. **Never browse the web.** ATO rules come only from the attached Knowledge
   collection. If a rule you need is not there, say which rule is missing and
   stop — do not fall back on your own recollection of tax rates.
4. **Do not lodge anything** and do not connect to ATO systems.
5. **When uncertain, ask. Never guess to avoid asking.**
6. **Write results to files as you go.** Do not hold the classified register or
   the totals only in the conversation — if the conversation is compacted you
   will lose them. The files are your memory.

## Tooling and paths — non-negotiable

This instance has TWO file tools with completely separate, non-overlapping
roots. Using the wrong one is the single most common way this skill fails.

**Use ONLY Open Terminal.** Its tools are `run_command`, `list_files`,
`read_file`, `write_file`. Everything you need is reachable from it.

**NEVER use the filesystem MCP tools.** They are named `tool_list_directory`,
`tool_read_file`, `tool_write_file`, `tool_create_directory`,
`tool_list_allowed_directories` — anything shaped `tool_*_post`. They are rooted
at `/workspace`, an unrelated directory that contains NONE of the user's files.
If you call one you will get `Access denied - path outside allowed directories`,
or worse, you will silently create files somewhere the user will never find them.

Fixed paths — use these literally, never a relative path:

| What | Where |
|---|---|
| The user's uploaded files | `/home/user/` (they arrive automatically) |
| Your intermediate working files | `/home/user/out/<run>/working/` |
| Final deliverables | `/home/user/out/<run>/` |

`<run>` is a timestamped folder you create once, e.g. `20260917-1530`.
`/home/user/out/` is a real directory on the user's NAS, so anything you write
there they can actually collect. Nothing else is durable — write results there,
not to `/home/user` and never to `/workspace`.

If a path you expect is missing, run `ls -la /home/user` with `run_command` and
report exactly what you see. Do not go hunting with the other tool.

## Phase 0 — Check what you have

Before anything else, confirm and report:

- The ATO rules Knowledge collection is attached and readable. Name the rules
  you found. If it is absent, STOP and tell the user to attach it.
- Which files the user has uploaded. Run `ls -la /home/user` via `run_command`
  and list what you find: bank statement CSVs, BAS Excel template. Uploaded
  files are placed there by Open WebUI automatically — you do not fetch them.
- If either is missing, ask for it. Do not proceed on assumptions.

Then ask the user to confirm:
- The BAS period start and end dates
- That the basis is cash and the cycle is quarterly
- Their PAYG instalment rate (T2) or ATO-notified amount (T7) for this quarter

**Do not continue until the user answers.**

## Phase 1 — Load and inspect the statements

Using Python in Open Terminal:

1. Read each CSV. Detect the column layout from the header row — CBA, NAB and
   ANZ differ. Do not assume a layout. If a layout is unrecognised, show the
   header row and ask the user to map the columns.
2. Normalise to: date, description, amount, direction (in/out), account.
3. Filter to the BAS period. Report how many rows fell inside and outside.
4. Print the total money in and total money out. **Record these — they are what
   the reconciliation must match later.**
5. Save the normalised transactions to `/home/user/out/<run>/working/transactions.csv`.

Report the row counts and totals to the user before continuing.

## Phase 2 — Classify every transaction

Assign each transaction exactly one category:

| Category | Notes |
|---|---|
| taxable sale | GST applies |
| GST-free sale | per the rules collection |
| input-taxed sale | per the rules collection |
| taxable purchase | GST claimable |
| GST-free purchase | no GST to claim |
| capital purchase | may need separating — check the rules |
| wages | **no GST** |
| PAYG withholding | tax withheld from wages |
| ATO payment | **no GST** |
| private / non-deductible | excluded from BAS |
| transfer | between own accounts — excluded, not income or expense |
| **UNKNOWN** | anything you are not confident about |

Watch these traps specifically — **no GST** on: wages, bank interest and fees,
ATO payments, most government charges, private expenses, and purchases from
suppliers who are not GST-registered.

Save to `/home/user/out/<run>/working/classified.csv` with a `category` and `rule_reference` column.
Cite which rule from the Knowledge collection drove each non-obvious call.

Then **STOP and show the user**:
- A count and dollar total per category
- **Every UNKNOWN transaction, listed individually**, and ask them to categorise
- Any transaction that looks mixed business/private (vehicle, phone, home
  office, internet) — ask for the business-use percentage. Do not assume one.

Apply their answers, re-save the file, and confirm UNKNOWN is now empty or
explicitly accepted.

## Phase 3 — Compute the labels

In Python, using only the rules from the Knowledge collection. For each label,
produce the figure **and the list of transaction rows behind it**.

- **G1** total sales, **1A** GST on sales, **1B** GST on purchases
- **W1** gross wages, **W2** amounts withheld, **label 4**
- **T1** instalment income, **T2** rate or **T7** ATO amount, **5A**
- **7D** fuel tax credits
- **8A**, **8B**, **9** net amount owing or refundable

Apply the GST fraction and rounding exactly as the rules collection states. If
the collection does not state the rounding rule, say so and ask — do not pick one.

Save to `/home/user/out/<run>/working/labels.json`.

## Phase 4 — Reconcile (do not skip)

In Python, verify that classified totals equal the Phase 1 bank totals.

- If they balance, report the figures side by side.
- **If they do not balance, say so loudly, show the discrepancy itemised, and
  stop.** Do not adjust a figure to force a balance. An unbalanced
  reconciliation means the classification is incomplete, not that the total
  needs fixing.

Save to `/home/user/out/<run>/working/reconciliation.txt`.

## Phase 5 — Confirm the template mapping

Open the user's BAS Excel template and show which cell you intend to write each
label into. **Ask the user to confirm the mapping before writing anything.**
Templates differ and a misplaced figure is a wrong return.

**Write no figures until they confirm.**

## Phase 6 — Produce the outputs

Write to `/home/user/out/<run>/`, **never overwriting the user's uploads**
in `/home/user/`:

1. **Populated BAS template** — a copy, with the confirmed cells filled
2. **Working paper** — per label: the figure, the transactions behind it, and
   the arithmetic, so any number can be traced back to a bank line
3. **Classified transaction register**
4. **Reconciliation statement**

Then report:
- Each label and its value
- How many transactions were auto-classified vs needed user input
- The dollar value that was in UNKNOWN
- Anything you could not determine and why

## Closing statement — always include

> This is BAS preparation support, not registered tax agent advice. Figures are
> derived from the supplied bank statements only and will not capture anything
> that did not pass through those accounts — cash sales, purchases on other
> cards, or journal adjustments. Have a registered tax agent review before
> lodging.

## Stop and ask, do not push through, if

- The ATO rules collection is missing, or the rule you need is not in it
- A CSV layout is unrecognised
- The reconciliation does not balance
- UNKNOWN transactions remain uncategorised
- The user has not confirmed the period, or the template cell mapping
- You are about to state a GST rate, threshold or fuel tax credit rate that you
  cannot point to in the Knowledge collection
