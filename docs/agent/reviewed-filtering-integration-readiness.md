# Reviewed Filtering Integration Readiness

## Purpose

Phase 2X adds an internal readiness gate for reviewed header/footer filtering.
The gate does not enable production filtering. It aggregates the local-only
evidence gathered through Phase 2W and decides whether the next experiment can
remain internal, opt-in, and guarded.

## Validated So Far

- Header/footer/page-number candidates are based on explicit human
  `approve_exclude` decisions, not raw `would_exclude` labels.
- The approved removal count is stable at 48 local raw-page objects.
- Raw-object mapping was one-to-one for all approved removals.
- Body-region removal stayed at 0.
- Rejected, unsure, review-only, and layout-placeholder removals stayed at 0.
- Filtered parse experiments preserved body TextBlock, image, and section
  counts.
- The known table-count delta was manually reviewed through the table geometry
  visual approval gate.
- Local baseline and filtered DOCX outputs were non-empty.
- DOCX residual inspection found no true residual header/footer pollution and no
  body/table text loss warnings.
- Existing conversion tests still passed with default behavior.

## Still Local-Only

- The sample PDF remains ignored under `local_samples/`.
- Layout reports, review packs, visual review images, and generated DOCX files
  remain ignored under `local_reports/`.
- The readiness report itself is generated at
  `local_reports/reviewed-filtering-feature-readiness-report.md` and is not
  committed.
- The current evidence is useful for internal gating, but it is not sufficient
  as reusable regression coverage because it depends on private/local artifacts.

## Why Default Integration Is Still Blocked

- There is no committed synthetic PDF fixture suite yet.
- There is no committed end-to-end regression fixture for reviewed filtering.
- No public API or CLI behavior has been designed for user-facing enablement.
- DOCX header/footer generation is not implemented.
- Paragraph merging is still report-only and must not be coupled to filtering in
  the same step.
- The safe path remains an explicitly opt-in internal experiment, not default
  production behavior.

## Required Synthetic Fixture Plan

Future committed fixtures should be generated from safe synthetic content and
should avoid private or copyrighted source material.

- `repeated_header_footer_page_numbers`: repeated header/footer text plus page
  numbers across all pages.
- `first_page_different_header`: a title-page or first-page header exception.
- `odd_even_headers`: alternating odd/even header text.
- `footer_close_to_body_text`: footer text close to the body region.
- `body_table_near_footer`: a real body table near a repeated footer.
- `callout_textbox_table_like_content`: text-box or callout content that may
  look table-like.
- `paragraph_crossing_page_boundary`: one paragraph visually split across pages.
- `hyphenated_cross_page_continuation`: a hyphenated word split across a page
  break.
- `list_items_and_headings`: list and heading boundaries that should not be
  over-merged.
- `no_header_no_footer_negative_control`: a document with no header/footer
  artifacts to remove.

## Next Safe Experiment

Phase 2Y should remain internal and non-default. The safest direction is to add
committable synthetic fixture generation or fixture definitions first, then run
the readiness gate against those fixtures before any production integration
attempt.

Guardrails for Phase 2Y:

- Keep reviewed filtering disabled by default.
- Do not expose a public CLI flag yet.
- Do not mutate production conversion output by default.
- Require explicit review approvals for any destructive filtering experiment.
- Require table visual approval evidence when table geometry changes.
- Keep generated reports and DOCX outputs local-only unless they contain no
  extracted or private text.
