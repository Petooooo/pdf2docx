# Reviewed Filtering Quality Evaluation

## MVP Scope

This document evaluates the current internal reviewed header/footer migration
MVP. It is a quality review pack, not a production integration plan.

The MVP currently covers:

- Detecting repeated header, footer, and page-number candidates.
- Requiring explicit human `approve_exclude` review decisions before removal.
- Removing approved boundary artifacts from the internal filtered body path.
- Writing approved simple text headers/footers to DOCX header/footer XML in
  internal tests.
- Supporting a default-policy-only writer path.
- Supporting explicit internal page-number behavior modes.
- Using normalized token/ngram body signature evidence as the primary local
  body preservation gate.

The MVP remains internal-only, disabled by default, and unavailable through
public CLI/API options.

## Validated Behavior

Synthetic coverage validates the main safety and migration surfaces:

- Repeated header/footer/page-number detection.
- Approval-gated reviewed filtering.
- Raw `would_exclude` blocked without explicit approval.
- Rejected and unsure candidates blocked.
- Body-region and layout-placeholder candidates protected.
- Filtered body plus DOCX header/footer XML output for default policy.
- Default-policy migration smoke.
- Explicit internal `word_field` PAGE field smoke.
- Placeholder and static page-number modes do not create PAGE fields.
- Callout/text-box content preserved.
- List and heading boundaries preserved.
- Table text preserved in stress scenarios.
- Non-default policies fail closed before writer application.

Local ignored evidence from Phase 4G records:

- `input.pdf`: passed normalized local migration gate.
- `input3.pdf`: passed normalized local migration gate.
- `input6_large.pdf`: bounded subset only; skipped because policy remained
  `unsupported` under incomplete coverage.
- True body text loss count: 0.
- Table text loss count: 0.
- Callout text loss count: 0.
- List text loss count: 0.
- Residual header/footer pollution count: 0.
- Strict exact-fragment mismatch remains diagnostic for the two passing local
  samples.

Local evidence is ignored/non-committed and must not be treated as production
fixture coverage.

## Phase 5B Local Corpus Review

Phase 5B expands the quality evaluation over the available ignored local
corpus reports without rerunning heavy full-document conversions and without
promoting local PDFs into committed fixtures.

Local corpus classifications:

| Sample | Local classification | Evidence summary |
| --- | --- | --- |
| `input.pdf` | `passed_internal_migration_smoke` | Default policy local migration smoke passed the normalized body signature gate. |
| `input2.pdf` | `negative_control_no_candidates` | Corpus analysis found repeated review-only/page-number signals but no eligible reviewed migration candidates. |
| `input3.pdf` | `passed_internal_migration_smoke` | Default policy local migration smoke passed the normalized body signature gate. |
| `input4.pdf` | `negative_control_no_candidates` | Corpus analysis found layout-placeholder style repetition only; no eligible reviewed migration candidates. |
| `input5.pdf` | `negative_control_no_candidates` | Corpus analysis found layout-placeholder/review-only repetition only; no eligible reviewed migration candidates. |
| `input6_large.pdf` | `bounded_subset_only` | Only a bounded subset was analyzed; policy remained `unsupported` under incomplete coverage, so full migration remains skipped. |

Phase 5B safety summary:

- Local samples summarized: 6.
- Passed internal migration smoke samples: 2 (`input.pdf`, `input3.pdf`).
- Negative/control samples: 3 (`input2.pdf`, `input4.pdf`, `input5.pdf`).
- Bounded/skipped samples: 1 (`input6_large.pdf`).
- Unsupported policy evidence: `input6_large.pdf` only, and it remains
  bounded/skipped rather than pass-classified.
- Body text loss count: 0.
- Table text loss count: 0.
- Callout text loss count: 0.
- List text loss count: 0.
- Residual header/footer pollution count: 0.

Remaining local evidence gaps:

- Local corpus evidence is ignored and non-committed.
- `input6_large.pdf` remains bounded-only; full-document behavior is not
  claimed.
- Negative/control samples help show fail-closed behavior but do not expand the
  positive migration evidence set.
- Non-default policy writing is still not supported.

Public/default readiness remains blocked because Phase 5B is evaluation-only:
normal conversion is unchanged, the public CLI/API remains closed, migration is
still internal-only and disabled by default, and only default-policy simple text
header/footer writing has internal smoke evidence.

## Phase 5F Public-Safe Synthetic Fixture Expansion

Phase 5F expands committed public-safe synthetic coverage without using ignored
local PDFs or local extracted text. The new tests generate small deterministic
PDFs at runtime with artificial `Synthetic public safe ...` content and keep
all generated PDF/DOCX artifacts in temporary directories.

New committed synthetic coverage:

- First-page-different header/footer fixture coverage verifies the future
  `first_page` policy shape remains fail-closed for the simple writer.
- Odd/even header/footer fixture coverage verifies `odd_even` remains
  fail-closed.
- Section-like contiguous ranges verify `section_scoped` remains fail-closed
  and still requires future section mapping.
- Header/footer text that partially resembles a body heading does not remove
  the body heading; the body signature remains preserved.
- Page-number `word_field` behavior remains explicit: placeholder mode does
  not emit a Word `PAGE` field, while explicit `word_field` does.
- Strict exact-fragment mismatch remains diagnostic-only when the normalized
  token/ngram body signature gate passes.
- Warning model mapping remains stable for missing review decisions,
  unsupported policy, unsafe page-number behavior, body/table text loss, and
  residual header/footer pollution.
- A negative/control fixture with no repeated header/footer candidates remains
  ineligible for migration and removes nothing.

Public-safe fixture policy:

- No ignored local PDF text is used.
- No generated PDF or DOCX binaries are committed.
- Synthetic PDFs and DOCX outputs are generated only in temporary directories.
- The public CLI/API remains closed and default conversion remains unchanged.

Remaining fixture gaps:

- The committed fixture suite is still synthetic and intentionally small.
- First-page, odd/even, and section-scoped DOCX writing are not implemented.
- Image/logo header/footer migration is not covered.
- Cross-page paragraph merge is not implemented.
- Broader public-safe fixture diversity and performance/stress evidence are
  still required before public/default readiness.

Local corpus evidence remains ignored/non-committed. Phase 5F improves public
regression coverage, but it does not promote local samples into fixtures and
does not unblock public/default integration by itself.

## Header/Footer Role Mapping Follow-Up

A later local quality review reported a possible header/footer role swap in
generated DOCX output. OpenXML inspection showed that the default batch DOCX did
not contain Word header/footer parts, while the Phase 4G internal migration
DOCX for `input.pdf` kept top header text in header XML and bottom footer text
in footer XML.

The investigation still exposed an internal safety gap: plan generation and
writer application trusted `proposed_role` without a final role-vs-region
consistency check. Regression coverage now validates header/footer/page-number
OpenXML parts separately, and role/region mismatches fail closed before writing.

## Header/Footer Fidelity Follow-Up

Manual inspection after the role-mapping fix showed that reviewed migration
output was structurally correct but visually weak: header/footer text was placed
in the correct Word parts, but basic style, alignment, and dynamic page-number
fidelity were poor.

The internal plan now carries lightweight style/layout hints for approved
header/footer/page-number entries, and the internal DOCX writer applies simple
paragraph alignment plus run font size, bold, italic, color, and font-family
hints when they are available. `word_field` remains explicit and internal-only;
`placeholder_only` remains the default diagnostic mode. Exact PDF absolute
positioning, images/logos, and non-default header/footer policies remain out of
scope and fail closed.

## Header/Footer Fidelity Follow-Up

Further local inspection found three remaining fidelity questions: whether
header/footer text was actually gray, whether `Page 123`-style page-number
templates could be preserved, and whether generated header text was vulnerable
to clipping.

OpenXML inspection showed that the latest reviewed smoke output wrote black
`w:color` values, so the gray appearance is consistent with Word's normal
header/footer dimming while the body is active. The internal page-number plan
now preserves simple consecutive templates such as `Page 123`, writes the
prefix around a Word PAGE field, and sets a safe section start number when the
sequence is consecutive. Generated header/footer paragraphs now normalize
before/after spacing and avoid exact line-height settings. Public/default
conversion remains unchanged and closed.

## Header/Footer Pagination Follow-Up

Further inspection showed that same-baseline footer text and page-number items
were being written as separate Word paragraphs. This made the page number appear
one line lower and added avoidable footer height. The internal plan now groups
same-line header/footer items by target part and vertical center, and the writer
can emit one paragraph with center/right tab stops for left, center, and right
items. This keeps same-line footer text and `Page { PAGE }` together when the
bbox evidence is clear.

Dynamic Word PAGE fields still follow Word pagination, not original PDF page
boundaries. If DOCX body reflow creates extra Word pages, page labels can still
drift even when the prefix and start number are preserved. Exact source PDF page
label preservation remains future work and likely requires stronger page-boundary
fidelity, a source-static label mode, or per-page section mapping.

## Header Alignment Follow-Up

After same-line footer grouping improved the reviewed output, local manual
inspection found that a single top-right header was being serialized through the
same tab-stop layout used for multi-item footer lines. The internal writer now
uses direct paragraph alignment for single-item or single-zone line groups and
keeps tab-stop layout for multi-zone lines. Footer same-line grouping remains
valid, and dynamic PAGE fields still depend on Word pagination.

## Automatic Classification MVP

Manual review remains useful as a safety and diagnostics fallback, but it is
not the desired end-user workflow. The internal MVP now includes an automatic
candidate decision layer that classifies repeated boundary artifacts as
`auto_exclude`, `auto_keep`, or `auto_diagnostic`.

`auto_exclude` is reserved for high-confidence repeated top/bottom artifacts
with stable bbox bands, consistent role-region evidence, enough page coverage,
and no body/layout-placeholder/table/callout/list protection signals. Only
`auto_exclude` candidates are translated into the existing internal reviewed
filtering gates and DOCX header/footer plan. `auto_keep` and `auto_diagnostic`
candidates remain in the body and are reported without blocking ordinary
conversion.

The automatic path remains internal/local-only. Public CLI/API exposure is
still closed, default `Converter.convert()` behavior is unchanged, and
non-default policies still fail closed for migration.

## Automatic Classification v2

The automatic mode now recognizes a broader set of page-number templates,
including labeled, decorated, Korean-labeled, and total-page forms such as
`Page 123`, `p. 123`, `- 123 -`, `123 / 456`, and `페이지 123`. Sequence
metadata now distinguishes `consecutive`, `mostly_consecutive`,
`single_candidate`, and `not_sequence`, so high-confidence page-number
candidates can be migrated while unstable or body-region numbers remain
diagnostic or kept.

The classifier also detects strong odd/even header or footer patterns as
internal diagnostics. In v2 these stayed diagnostic-only because the writer was
still default-policy-only.

## Automatic Classification v3

Automatic classification now evaluates candidate coverage against the pages on
which the candidate is expected to appear. A strong odd-page header is measured
against odd source pages instead of being rejected for a global support ratio
near 0.5. The coverage model records `all_pages`,
`all_pages_except_first`, `odd_pages`, `even_pages`, `odd_even_pair`,
`contiguous_range`, and `sparse_or_unstable`.

Page-number sequence inference now recognizes parity-alternating dynamic page
numbers. For example, odd pages can carry right-aligned `Page 123`, `Page 125`,
`Page 127` while even pages carry left-aligned `Page 124`, `Page 126`,
`Page 128`; the combined family is treated as `parity_consecutive` when the
full source-page sequence is safe.

The internal DOCX writer now supports strong odd/even text policies using
Word odd/even header/footer parts. Odd/even output remains internal-only and is
not exposed through public CLI/API or default conversion. First-page-excluded
default repetition can also be represented internally by leaving the first-page
header/footer empty and writing the repeated default content for later pages.

Local v3 smoke on `input.pdf` through `input5.pdf` generated automatic reviewed
outputs for `input.pdf` and `input3.pdf`. `input3.pdf` still migrated only the
all-page footer: its top numeric candidate was not a consecutive page-number
sequence, and the odd-side header y-band was unstable, so the odd/even header
family remained diagnostic rather than being removed.

Manual review remains a fallback/debug workflow only. Public/default conversion
is still unchanged.

## Safety Gates

The current MVP remains fail-closed around these gates:

- Explicit review approval is required.
- Raw `would_exclude` is blocked.
- Rejected candidates are blocked.
- Unsure candidates are blocked.
- Body-region candidates are protected.
- Layout-placeholder candidates are protected.
- Normalized token/ngram body signature is the primary body preservation gate.
- Strict exact-fragment mismatch is diagnostic-only.
- True body text loss fails closed.
- Table text loss fails closed.
- Callout text loss fails closed.
- List text loss fails closed.
- Residual header/footer pollution fails closed.
- Unsafe policy fails closed.
- Unsafe page-number behavior fails closed.
- Missing review decisions fail closed.

## Policy Support

Current writer support is intentionally narrow:

- `default`: supported for the simple internal writer.
- `first_page`: classified but fail-closed.
- `first_page_excluded_default`: supported internally when the first page has
  no migrated header/footer content and later pages are stable.
- `odd_even`: supported internally for strong text/page-number families using
  Word odd/even parts.
- `section_scoped`: classified but fail-closed.
- `unsupported`: fail-closed.

Ambiguous policy must not silently become `default`.

## Page-Number Behavior

Supported internal modes:

- `placeholder_only`: default diagnostic behavior.
- `word_field`: explicit internal-only Word `PAGE` field behavior.
- `static_text`: diagnostic/static literal behavior only.
- `unsupported`: fail-closed.

`word_field` is not default and is not public. It must remain explicitly
selected by internal tests or diagnostics.

## Readiness Status

Internal MVP readiness:

- `ready_for_internal_quality_review` when synthetic coverage is present,
  local safety counts are clean, and public/default exposure remains closed.

Public/default readiness:

- `not_public_ready`.

The current evidence supports continued internal quality review only. It does
not support default conversion changes, public CLI/API exposure, or production
header/footer migration.

## Known Gaps

- Public CLI/API option is not exposed.
- Production/default migration is not enabled.
- First-page Word header/footer writing is not implemented.
- Odd/even Word header/footer writing remains internal-only.
- Full section-specific production mapping is not implemented.
- Image/logo header/footer migration is not implemented.
- Cross-page paragraph continuation merge is not implemented.
- Production table parsing behavior is unchanged.
- Large document evidence remains bounded for `input6_large`.
- Local corpus evidence is ignored and non-committed.

## Recommended Next Phases

Recommended Phase 5C direction:

- Keep the migration profile internal and disabled by default.
- Use the Phase 5A/5B quality pack as the evidence checklist for any next
  bounded smoke.
- If local work continues, prefer a profile-driven default-policy smoke that
  reuses the normalized gate.
- Do not broaden into public/default integration, non-default policy writing,
  image/logo migration, paragraph merge, or table parser changes without a
  separate explicit phase.
