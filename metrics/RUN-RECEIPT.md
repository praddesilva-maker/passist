# Run Receipt Schema

Every skill in the `passist` framework emits a **Run Receipt** at the end of each execution. This receipt is ingested into a ledger and used to compute ROI metrics.

## Schema Fields

A run receipt must contain the following fields:

- `run_id`: (string, unique) - A globally unique identifier for this run (used as de-dupe key)
- `skill`: (string) - The name of the skill that was executed
- `category`: (string) - One of: `skill | sa | dev | admin` 
- `model`: (string) - The exact model used for this run (e.g., "gpt-4-turbo", "claude-3-opus")
- `timestamp`: (string) - ISO 8601 formatted timestamp of when the run completed
- `primary_volume`: (number/string) - The skill's unit of work delivered:
  - Pages created
  - Issues written  
  - Artefacts reviewed
  - Tasks processed
  - etc.
- `tokens_in`: (integer) - Input tokens consumed by this run
- `tokens_out`: (integer) - Output tokens consumed by this run
- `human_minutes_saved`: (integer) - How long the work would have taken manually (captured from prompt during live runs)
- `mode`: (string) - Either "interactive" or "single-command"
- `dry_run`: (boolean) - Whether this was a dry-run execution
- `notes`: (string, optional) - Additional context about the run

## Time-Saved Capture Prompt

During any live run that delivered actual work to the user, before emitting the receipt, the skill **must** ask the user one line with this question:
> "~how long would this have taken by hand?"

This prompt is used during live runs; in dry-run mode it's skipped.

## Location of Receipt Emission

Skills must emit run receipts to `metrics/inbox/` directory as a JSONL file named after the run_id (e.g., `metrics/inbox/<run_id>.json`).