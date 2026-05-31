# Sample Analysis Review

Date: 2026-05-31

This document summarizes local-only observations from `local_samples/input.pdf`.
It intentionally avoids large extracted PDF text. The sample PDF and generated
layout report remain ignored by Git.

## Phase 1D Baseline

- Pages analyzed: 12.
- Text blocks / placeholders summarized: 790.
- Repeated text candidate clusters: 9.
- Repeated candidate regions: 4 top-region clusters and 5 bottom-region clusters.
- Paragraph continuation entries: 11.
- Continuation labels: 9 `unlikely`, 2 `weak`, 0 `candidate`.
- The strongest repeated top/bottom candidates looked useful as header/footer
  evidence.
- Some two-page repeated clusters looked risky because they may have been body
  content close to page boundaries.
- The weak continuation candidates looked risky because they involved very short
  text or placeholder-like blocks.

## Phase 1E Heuristic Changes

- Added text-quality signals so the report can distinguish normal text from very
  short text, page-number placeholders, image placeholders, and generic
  placeholder-like text.
- Kept repeated candidates reportable, but added `semantic_confidence` and
  `confidence_label` so low-support or placeholder-only evidence is easier to
  review cautiously.
- Preserved raw support-based repeated `confidence` for compatibility with the
  existing report shape.
- Down-scored placeholder-like and very short continuation endpoints.
- Avoided selecting likely repeated top/bottom boundary text as paragraph
  continuation endpoints.
- Added clearer reason strings when a continuation candidate is limited by short
  text, placeholder text, or repeated boundary text.

## Phase 1E Sample Recheck

After regenerating the ignored local report:

- Repeated text candidate clusters remained 9.
- Repeated labels became 4 `strong`, 2 `placeholder`, and 3 `cautious`.
- Placeholder repeated clusters were still visible in the report but no longer
  looked like strong semantic header/footer evidence by themselves.
- Paragraph continuation entries remained 11.
- Continuation labels became 11 `unlikely`, 0 `weak`, and 0 `candidate`.
- The previous weak continuation entries were successfully made more cautious.

## Phase 1F Dry-run Review

Phase 1F added a non-destructive header/footer exclusion dry-run to the opt-in
layout report. The dry-run records what a future body-filtering phase might do,
but it does not alter page blocks or conversion output.

After regenerating the ignored local report:

- Dry-run candidates: 9.
- Actions: 4 `would_exclude`, 5 `review`, 0 `keep`.
- Proposed roles: 1 `header`, 2 `footer`, 1 `page_number`, 2
  `layout_placeholder`, and 3 `review_only`.
- The all-page/high-support repeated top and bottom text is now separated from
  low-support boundary text.
- Page-number-like repetition is separated from semantic body text.
- Image placeholders remain review-only layout signals.
- Low-support repeated boundary clusters remain visible but are not proposed for
  automatic exclusion.

## Interpretation

- The all-page top and bottom repeated text remains the strongest report-only
  evidence for future header/footer modeling.
- Page-number placeholders are useful repeated footer evidence, but should not be
  considered normal body text for paragraph continuation.
- Image placeholders are layout signals only until the analyzer can compare image
  identity and placement more precisely.
- Low-support two-page repeated clusters should stay visible for review, but they
  should not drive destructive body changes.
- Phase 1F `would_exclude` entries are future candidates only; they are not
  permission to mutate body content yet.

## Remaining Risks

- No body content is removed yet, and this review does not validate safe
  destructive filtering.
- More fixture diversity is needed before Phase 2, especially documents with
  first-page exceptions, section headers, odd/even headers, list-heavy pages,
  image-only headers, and tables near page boundaries.
- Actual paragraph merging should remain blocked until continuation candidates
  are validated against more samples and richer layout signals.
