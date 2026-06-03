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
- `odd_even`: classified but fail-closed.
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
- Odd/even Word header/footer writing is not implemented.
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
