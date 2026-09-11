# Change Request — CR-001: Academic-correctness artefact review

- Author: <me>   Date: <today>   Approver: <me>
- Priority: med   Target: —   Status: Approved

## 1. Goal
Authors/reviewers need to check an artefact (paper, report, thesis chapter) for academic
correctness before submission, and get a clear, ranked list of problems with fixes.

## 2. Requested capabilities
### Item 1
- Type: tool  (reuse if a local-file reader already exists, else create — mark which)
- Proposed name: readLocalFile
- Behaviour: read a local .md/.txt/.docx/.pdf and return extracted text + basic metadata.
- Inputs: path — required
- Output: { text, meta }
- Grounding sources: local filesystem
- External writes: no
- Modes: single-run + interactive
- Acceptance: returns text for a sample file; errors clearly on a missing/unsupported file
- Dependencies: none

### Item 2
- Type: skill
- Proposed name: academic-artefact-review
- Behaviour: given an artefact (path read via Item 1, or pasted text), assess academic
  correctness against a rubric — (a) claims supported by evidence/citations, (b) citations
  present, consistent, and actually referenced, (c) methodology soundness, (d) internal
  logical consistency, (e) data/statistical integrity, (f) structure & clarity.
- Inputs: artefact path (or pasted text) — required; rubric emphasis — optional
- Output: a findings TABLE (Finding | Severity | Location | Why it's a problem |
  Suggested fix), worst-first, + a one-paragraph verdict (Sound / Sound with revisions /
  Not ready) + a coverage/confidence note.
- Grounding sources: the artefact text ONLY (via Item 1). Never infer beyond the text;
  an absent section is reported "To be confirmed", not assumed.
- External writes: no  (READ-ONLY review)
- Modes: single-run + interactive
- Acceptance: runs on a sample artefact; produces a ranked table + verdict; invents
  nothing; emits a Run Receipt (category skill; primary volume = artefacts reviewed)
- Dependencies: Item 1

## 3. Constraints & non-goals
No external writes. Not a plagiarism detector and not a grammar-only pass (out of scope).

## 4. Risks / open questions
Very large artefacts may need chunking — to be confirmed at build time.

## 5. Notes
This CR exists to be built later with: `run capability-intake — CR:
docs/change-requests/CR-001-academic-artefact-review.md; Action: apply`.