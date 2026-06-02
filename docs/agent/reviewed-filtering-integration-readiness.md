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

## Phase 3C Internal Filtered DOCX Comparison

Phase 3C validates that the Phase 3B private filtered parse integration can
flow through existing DOCX generation in controlled internal tests. The tests
generate synthetic PDFs and temporary baseline/filtered DOCX files at runtime;
no generated DOCX files are committed.

Validated by committed synthetic tests:

- Baseline DOCX generation works for synthetic repeated header/footer/page
  number content.
- Filtered DOCX generation works only through the private internal config path.
- Approved repeated header/footer/page-number residuals are removed from DOCX
  body output in the repeated-header fixture.
- Body-region text signatures are preserved after filtered DOCX generation.
- Body table-like text near a footer remains preserved.
- No-header/no-footer negative-control content is preserved.
- Raw `would_exclude` without manual approval removes nothing.
- Rejected or unsure decisions remain blocked by fail-closed behavior.
- Generated DOCX files are created only in temporary test directories.

Safety interpretation:

- Body text signature preservation is the primary safety criterion.
- Body TextBlock count changes are warnings, not automatic failures, when the
  body text signature is preserved.
- Body text loss remains fail-closed.
- Table text loss remains fail-closed.
- True residual header/footer pollution remains fail-closed.
- Table count deltas must be reported and interpreted with text-preservation
  evidence.

Still intentionally not implemented:

- No Word section header/footer parts are generated.
- No content is migrated into DOCX headers or footers.
- No cross-page paragraph merge is added.
- No public CLI flag or public API option is exposed.
- Default `Converter.convert()` behavior remains unchanged.

Phase 3D should remain internal. The next useful work is to add the remaining
synthetic scenarios that are still thin: callout/text-box content, list/heading
boundaries, and synthetic table-geometry deltas under filtered parsing.

## Phase 3D Local Corpus DOCX Smoke Validation

Phase 3D runs the Phase 3B/3C private filtered parse and DOCX comparison path
against approved ignored local corpus samples. This remains local-only evidence:
the sample PDFs, review packs, generated DOCX files, and reports are not
committed.

Validated locally:

- `input.pdf` completed baseline vs filtered DOCX smoke validation.
- `input3.pdf` completed baseline vs filtered DOCX smoke validation.
- `input6_large.pdf` was validated only through a bounded subset of 15 pages.
- Generated baseline, filtered, and post-experiment default DOCX files stayed
  under ignored `local_reports/phase3d/` paths.
- The large sample full-document parse and DOCX generation stayed skipped.

Safety interpretation:

- Default conversion remains unchanged.
- Public CLI/API exposure remains closed.
- The internal config path still requires explicit review approvals.
- Raw `would_exclude` labels alone remain insufficient.
- Rejected, unsure, body-region, and layout-placeholder candidates remain
  blocked.
- Body text signature preservation remains the primary safety criterion.
- Body TextBlock count deltas and DOCX table count deltas are diagnostics, not
  automatic failures, when body and table text signatures remain preserved.
- Body text loss, table text loss, or true residual header/footer pollution
  remain fail-closed conditions.

Phase 3E should remain internal and should focus on broadening committed
synthetic regressions for callout/text-box, list/heading, and table-geometry
delta cases before any public opt-in design is considered.

## Phase 3E Synthetic Regression Broadening

Phase 3E broadens committed synthetic coverage for the remaining weak scenarios
identified before any Phase 4 header/footer DOCX generation work. The coverage
still uses generated PDFs and temporary DOCX outputs at test runtime; no
generated PDF or DOCX binaries are committed.

New committed synthetic coverage:

- Callout/text-box-like body panels near page edges.
- Table-like callout text that must remain body content.
- Heading, bullet-list, and numbered-list body boundaries.
- Synthetic table-geometry stress near footer/page-number candidates.
- First-page/odd-even header variation with body headings that resemble header
  text.
- Table-count delta diagnostics when table text signature is preserved.
- Fail-closed table text loss diagnostics.

Safety interpretation:

- Default conversion remains unchanged.
- Public CLI/API exposure remains closed.
- Reviewed filtering still runs only through the private internal config path.
- Explicit review approval remains mandatory.
- Raw `would_exclude` labels alone remain insufficient.
- Body-region and layout-placeholder protection remain hard requirements.
- Body text signature preservation remains the primary safety criterion.
- Body TextBlock, table count, or table boundary shifts remain diagnostics when
  body/table text signatures are preserved.
- Body text loss, table text loss, and true residual header/footer pollution
  remain fail-closed conditions.

Remaining gaps before Phase 4:

- No Word section header/footer parts are generated yet.
- No content is migrated into DOCX headers or footers yet.
- No cross-page paragraph merge is implemented.
- No public opt-in design has been exposed.
- More real-world local corpus validation may still be useful, but committed
  synthetic coverage is no longer limited to the original repeated-header and
  body-table fixtures.

Phase 4A can start only as another internal/private design step for DOCX
header/footer part generation. Default conversion and public CLI/API behavior
should remain closed until that work has its own regression evidence.

## Phase 4A Internal DOCX Header/Footer Foundation

Phase 4A adds the first internal foundation for representing reviewed
header/footer candidates as future Word header/footer content. This is still
not wired into normal conversion.

Design added:

- A JSON-serializable DOCX header/footer generation plan helper.
- The plan accepts only explicit `approve_exclude` header/footer/page-number
  candidates.
- Rejected, unsure, review-only, layout-placeholder, and body-region candidates
  are excluded or fail closed.
- Semantic repeated header/footer text is represented as simple planned text.
- Page numbers are represented only as a diagnostic `<PAGE_NUMBER>`
  placeholder.
- Section scope is recorded as document-level only.
- First-page and odd/even behavior are explicitly deferred.
- Images, logos, complex layout, and paragraph continuation are explicitly out
  of scope.

Internal DOCX proof:

- A small internal `python-docx` helper can apply the simple text plan to a
  provided `Document` object when explicitly enabled.
- Tests verify that a temporary DOCX contains `word/header*.xml` and
  `word/footer*.xml` parts with the planned simple text.
- This helper is not called by `Converter.convert()` or the public CLI.

Safety interpretation:

- Default conversion remains unchanged.
- Public CLI/API exposure remains closed.
- DOCX header/footer generation remains disabled by default.
- No content is migrated into Word header/footer parts during normal
  conversion.
- Page-number field generation is deferred until it can be represented with a
  real Word field safely.
- Section-specific, first-page, and odd/even mapping remain future work.

Phase 4B should stay internal and should decide how a private, opt-in DOCX
generation experiment can consume this plan without changing default
conversion behavior.

## Phase 4B Internal Filtered Body + DOCX Header/Footer Experiment

Phase 4B connects the Phase 3 internal filtered parse path and the Phase 4A
DOCX header/footer text writer only inside committed synthetic tests. It is
still not wired into normal conversion.

Validated internal experiment:

- A synthetic repeated header/footer/page-number PDF is converted through the
  private filtered parse path.
- Approved repeated header/footer/page-number candidates are removed from the
  DOCX body.
- A simple DOCX header/footer plan is built from the same explicit approvals.
- The plan is explicitly applied to the temporary DOCX with
  `apply_header_footer_text_plan()`.
- `word/header*.xml` contains the approved header text.
- `word/footer*.xml` contains the approved footer text and diagnostic
  `<PAGE_NUMBER>` placeholder.
- `word/document.xml` no longer contains the approved repeated header/footer
  body residuals.
- Body text signatures remain preserved.

Additional synthetic body-protection coverage verifies that callout/table-like
body text remains in the DOCX body and is not written to Word header/footer
parts.

Safety interpretation:

- Default conversion remains unchanged.
- Public CLI/API exposure remains closed.
- Simple text header/footer generation remains internal-only and explicitly
  invoked by tests.
- The internal DOCX writer now fail-closes when a plan contains safety
  warnings or is not recommended for the internal experiment.
- Rejected, unsure, layout-placeholder, and body-region candidates do not
  appear in DOCX header/footer parts.
- Page-number behavior remains placeholder-only; real Word field insertion is
  still deferred.
- Section-specific, first-page, odd/even, image/logo, complex layout, and
  paragraph-continuation behavior remain future work.

Phase 4C should remain internal. The next safe direction is to decide whether
to broaden simple text header/footer output across more synthetic scenarios or
to design the next private section/page-number experiment without exposing a
public option.

## Phase 4C Internal Header/Footer Policy Layer

Phase 4C adds an internal policy classification layer on top of the
JSON-serializable DOCX header/footer plan. The policy remains diagnostic and is
not wired into normal conversion.

Policy types represented:

- `default`: the same approved header/footer/page-number pattern applies across
  the document section.
- `first_page`: the first page differs and the remaining pages share a stable
  default pattern.
- `odd_even`: odd and even pages have stable alternating patterns.
- `section_scoped`: stable contiguous page ranges suggest future
  section-specific header/footer mapping.
- `unsupported`: the approved candidate pattern is ambiguous, incomplete, or
  otherwise not safe to write.

Safety interpretation:

- Default conversion remains unchanged.
- Public CLI/API exposure remains closed.
- Only the `default` policy is considered safe for the current simple internal
  writer.
- `first_page`, `odd_even`, and `section_scoped` policies are classified for
  diagnostics but fail closed before DOCX writing.
- Unsupported or ambiguous policies fail closed.
- Rejected, unsure, raw `would_exclude`, review-only, body-region, and
  layout-placeholder candidates do not enter semantic header/footer policies.
- Page-number behavior remains placeholder-only; robust Word field insertion is
  still deferred.
- Actual first-page/odd-even DOCX writing was deferred.
- Production section mapping remains future work.
- Images/logos, complex layout, and paragraph continuation remain out of scope.

Phase 4D should remain internal and should either prototype safe first-page or
odd/even DOCX writing in temporary synthetic tests, or continue improving
policy diagnostics before any production integration is considered.

## Phase 4D Default-Policy Migration Smoke

Phase 4D adds an internal single-section default-policy migration smoke test.
It exercises the closest current approximation of the future reviewed
header/footer feature while keeping all behavior private and non-default.

Validated internal smoke path:

- A synthetic repeated header/footer/page-number PDF is converted through the
  private filtered parse path.
- Explicitly approved default header/footer/page-number candidates are removed
  from the DOCX body.
- The generated plan is required to classify as `default`.
- The default plan is applied to temporary DOCX header/footer parts with the
  internal writer.
- DOCX body XML no longer contains approved header/footer residuals.
- DOCX header XML contains the approved header text.
- DOCX footer XML contains the approved footer text.
- DOCX footer XML contains the diagnostic `<PAGE_NUMBER>` placeholder.
- Body text signatures remain preserved.
- Callout/table-like body text remains in the body and is not moved to
  header/footer parts.

Safety interpretation:

- Default conversion remains unchanged.
- Public CLI/API exposure remains closed.
- Only `default` policy is allowed for the internal writer.
- `first_page`, `odd_even`, `section_scoped`, and `unsupported` policies remain
  fail-closed before DOCX writing.
- Page-number behavior remains placeholder-only; robust Word field insertion is
  still deferred.
- Body text signature preservation remains mandatory.
- Body text loss, table text loss, and true residual header/footer pollution
  remain fail-closed conditions.
- This is still not production/default integration.

Phase 4E should remain internal. The next safe direction is to prototype
first-page or odd/even DOCX writing only in temporary synthetic tests, or to
keep improving policy diagnostics before production integration is considered.
