# Reviewed Filtering Public Readiness Checklist

## Status

This checklist defines what must be true before reviewed header/footer
migration can be considered for public opt-in or default-on behavior.

Phase 5D is checklist-only. It does not expose a public API or CLI option, does
not change default conversion, and does not wire migration into production.

Current readiness:

- Internal MVP ready: yes.
- Public opt-in ready: no.
- Default-on ready: no.

## Current Internal Readiness

The internal MVP has the core private building blocks:

- Internal migration profile exists.
- Internal request/config surface exists.
- Default-policy migration smoke exists.
- DOCX header/footer XML output is validated.
- Explicit internal `word_field` PAGE field behavior is validated.
- Normalized token/ngram body signature local gate exists.
- Quality evaluation pack exists.

This evidence supports internal review and private bounded experiments only.
It does not justify public API, public CLI, or default conversion changes.

## Public API Readiness Blockers

Public opt-in remains blocked because:

- No public API or CLI option exists.
- The API shape is internal-only.
- The review decisions format is not user-facing.
- The local output/report policy is not user-facing.
- The error/warning model is not public-facing.
- End-user documentation does not exist.
- There is no backward compatibility policy for public option names.

## Default-On Readiness Blockers

Default-on behavior remains blocked because:

- Only `default` policy writing is supported.
- `first_page`, `odd_even`, `section_scoped`, and `unsupported` policies still
  fail closed.
- Image/logo header/footer migration is not implemented.
- Paragraph continuation merge is not implemented.
- Large document evidence remains bounded for `input6_large`.
- Local corpus evidence is ignored and non-committed.
- Public regression fixture coverage is still limited.
- Performance characteristics are not fully evaluated.
- Manual review approval is still required.

## Required Technical Gates Before Public Opt-In

Before public opt-in can be considered, the project needs:

- Public option naming proposal.
- Public warning/error model.
- Public review decision schema or automatic safe mode.
- Robust committed fixture suite.
- Quality gate summary exposed to the caller.
- Fail-closed behavior verified through public-facing workflows.
- Backward compatibility plan for public option names and behavior.
- End-user documentation.
- Security/privacy guidance for local reports and review artifacts.

## Required Technical Gates Before Default-On

Before default-on behavior can be considered, the project needs:

- Much broader corpus validation.
- Non-default policy support or safe user-facing skip behavior.
- First-page, odd/even, and section handling strategy.
- Paragraph continuation strategy.
- Performance and stress testing.
- User-facing fallback behavior.
- Stronger end-to-end DOCX structural tests.
- Clear success/failure metrics.

## Validation Evidence Required

Public/default readiness requires evidence beyond the current internal MVP:

- Committed public-safe fixtures covering headers, footers, page numbers,
  tables, callouts, lists, headings, and body text preservation.
- Negative/control fixtures that prove body-region and layout-placeholder
  content remains protected.
- Non-default policy fixtures or explicit public skip behavior.
- Large-document and stress evidence.
- DOCX OpenXML structure checks for header/footer parts.
- Residual header/footer pollution checks.
- Body/table/callout/list text loss checks.
- Public warning/error behavior checks.
- Backward compatibility checks for default conversion.

## Remaining Risks

Key risks before public/default exposure:

- Body text loss.
- Table text loss.
- Callout text loss.
- List text loss.
- Residual header/footer pollution.
- Unsupported policy behavior.
- Unsafe page-number behavior.
- Local report privacy.
- Large document performance.

## Recommended Next Phases

- Phase 5E: public option naming and warning model draft.
- Phase 5F: committed public-safe fixture expansion.
- Phase 5G: performance/stress evaluation.
- Phase 6A: paragraph continuation merge design.
- Phase 6B: first-page, odd/even, and section writing design.

Any public or default integration phase should remain blocked until its
readiness gates are explicitly satisfied and verified.
