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

## Synthetic Fixture Regression Coverage

Phase 2Z added committed synthetic regression coverage using generated PDFs
created at test runtime with PyMuPDF. The generated PDFs are written to
temporary directories only, use artificial test text, and are not committed.

Covered by committed tests:

- Repeated top header, repeated bottom footer, and repeated page numbers.
- Reviewed approval removes only explicitly approved header/footer/page-number
  candidates in internal report/guarded diagnostic paths.
- Body-region removal remains 0 for approved synthetic filtering.
- Body table-like content near a footer remains protected.
- A no-header/no-footer negative control produces no removable candidates.
- Raw `would_exclude` candidates are not treated as approved without explicit
  review decisions.
- First-page and odd/even header variation remains review-gated instead of
  being treated as one all-page header.
- A hyphenated paragraph crossing a page boundary remains available as body
  text after approved header/footer filtering.
- Body text signatures are checked independently of body TextBlock count so a
  grouping-count delta can be reported as a warning instead of becoming an
  automatic text-loss conclusion when text is preserved.

Still not fully covered by committed synthetic tests:

- Callout/text-box content that visually resembles a table.
- List item and heading boundary interactions with reviewed filtering.
- Full synthetic DOCX residual comparison with generated baseline/filtered
  DOCX files.
- Table parser geometry deltas under filtered parsing with a synthetic true
  table fixture.

Production default integration remains blocked. The new synthetic coverage
reduces reliance on ignored local PDFs, but future phases should add the
remaining synthetic scenarios before any public or default filtering behavior is
considered.

## Internal Opt-In Config Surface

Phase 3A added a minimal internal configuration scaffold for reviewed
header/footer filtering experiments. The scaffold lives in the internal layout
analysis helpers and is not exposed through the public CLI or public
`Converter.convert()` defaults.

Default state:

- `enabled`: `False`
- `mode`: `dry_run`
- `require_explicit_approval`: `True`
- `allow_raw_would_exclude`: `False`
- `allow_unsure`: `False`
- `allow_rejected`: `False`
- `protect_body_region`: `True`
- `protect_layout_placeholders`: `True`
- `collect_diagnostics`: `True`
- `write_local_reports`: `False`
- `fail_closed_on_warning`: `True`

Supported internal modes:

- `dry_run`
- `simulation`
- `guarded_apply_restore`
- `filtered_parse_experiment`
- `future_apply`

`future_apply` is intentionally blocked by the scaffold because permanent
production filtering has not been implemented or approved.

Safety rules:

- No config means reviewed filtering is disabled.
- `enabled=False` means reviewed filtering is disabled.
- Enabled config without explicit review decisions is blocked.
- Raw `would_exclude` labels are never sufficient approval.
- `reject_exclude` and `unsure` candidates remain blocked.
- Body-region candidates remain protected.
- Layout-placeholder candidates remain protected.
- Warnings fail closed by default.

The scaffold can summarize itself as JSON-serializable diagnostics and can map a
ready internal config into the existing private `Pages` diagnostic settings, but
it does not apply production filtering and does not change default conversion
behavior.

Public CLI/API exposure remains intentionally blocked. Any future public-facing
option needs a separate design review after the internal experiments and
synthetic regressions are stronger.

## Phase 3B Internal Filtered Parse Integration

Phase 3B connects the Phase 3A internal config scaffold to the private
`Pages.parse()` document-parse diagnostic path. This is still an internal
experiment path only.

Behavior:

- Default conversion remains unchanged when no private config is supplied.
- `enabled=False` keeps reviewed filtering disabled.
- `filtered_parse_experiment` is the only config mode that can apply reviewed
  filtering to the current internal parse input.
- The filtering insertion point remains `document_parse`, after raw pages are
  restored/cleaned and before margin and section parsing.
- Existing dry-run, raw-object mapping, copied-apply, guarded-restore, and
  filtered-parse diagnostics run first when the config is ready.
- The integration applies only explicit `approve_exclude` candidates.
- Raw `would_exclude` labels alone are not eligible.
- Rejected, unsure, review-only, layout-placeholder, and body-region candidates
  remain protected.
- Fail-closed config and mapping warnings block the internal apply path.
- Body TextBlock count deltas are recorded as diagnostics; preserved body text
  signature is required before such deltas can be treated as non-blocking.

Public exposure remains blocked:

- No public CLI flag was added.
- No public `Converter.convert()` default changed.
- No public documented API option was added.
- DOCX header/footer generation remains future work.
- Cross-page paragraph merging remains future work.
- Table parsing behavior remains unchanged.

Phase 3C should stay internal and should focus on broadening synthetic
coverage, especially callout/text-box and table geometry cases, before any
public opt-in design is considered.
