# Header/Footer Exclusion Review Workflow

Date: 2026-05-31

## Why Phase 1G Exists

Phase 1G creates a human review checkpoint before any future body filtering.
Phase 1F can already mark dry-run candidates as `would_exclude`, `review`, or
`keep`, but those labels are still heuristic. A reviewer should approve or reject
candidate exclusions before Phase 2A changes any page body content.

This phase remains non-destructive:

- It does not remove PDF blocks.
- It does not merge paragraphs.
- It does not generate DOCX headers or footers.
- It does not change normal conversion output.
- It does not expose a public CLI option.

## Local Review File

The generated local-only review pack is:

```text
local_reports/header-footer-exclusion-review.md
```

That path is ignored by Git through `local_reports/`. The file may contain short
PDF text previews for local review, so it must not be staged or committed.

The review file is generated from:

```text
local_reports/input-layout-analysis-report.json
```

Both the raw report and the review pack are local validation artifacts.

## Review Fields

Each dry-run candidate is listed with:

- `candidate_id`
- `fingerprint`
- `proposed_role`
- `action`
- `region` and `regions`
- `support_count`
- `affected_pages`
- `confidence_label`
- `semantic_confidence`
- `positive_signals`
- `negative_signals`
- `reason`
- short preview, local-only
- `review_recommendation`
- manual decision fields: `approve_exclude`, `reject_exclude`, `unsure`
- reviewer notes

## How To Use Before Phase 2A

1. Open `local_reports/header-footer-exclusion-review.md`.
2. Review every candidate against the source PDF visually.
3. Mark exactly one manual decision for each candidate.
4. Treat `safe_candidate` as a hint, not approval.
5. Use `approve_exclude` only when the candidate is clearly a repeated
   header/footer/page-number artifact across the listed pages.
6. Use `reject_exclude` when the candidate may be body content, section content,
   figure/table content, or any text that should remain editable in the body.
7. Use `unsure` when more samples or visual inspection are needed.

## Guardrails For Phase 2A

- Phase 2A must start from explicit review decisions, not raw dry-run labels.
- `would_exclude` should not automatically remove content.
- `layout_placeholder` entries should not be treated as semantic text until image
  identity and placement are modeled.
- Low-support or adjacent-only repeated clusters should remain review-only unless
  explicitly approved.
- Body-region candidates must not be removed by a header/footer filter.
- Any filtering implementation should be opt-in and covered by tests that prove
  normal conversion behavior remains unchanged by default.
- Generated reports or review packs containing extracted text must remain ignored
  local artifacts.
