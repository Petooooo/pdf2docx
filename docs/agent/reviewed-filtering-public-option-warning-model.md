# Reviewed Filtering Public Option and Warning Model Draft

## Status

This document drafts future public option names and a warning/error response
model for reviewed header/footer migration. The options described here are not
implemented, not exposed through CLI/API, and not connected to default
conversion.

Current exposure remains:

- Public CLI option: none.
- Public API option: none.
- Default conversion behavior: unchanged.
- Reviewed filtering: internal-only and disabled by default.

## Recommended Future Option Name

Recommended top-level API key:

- `reviewed_header_footer_migration`

Recommended future CLI flag:

- `--reviewed-header-footer-migration`

Rationale:

- The name keeps the human-reviewed safety contract visible.
- It avoids implying automatic/default migration.
- It distinguishes this feature from ordinary PDF header/footer layout
  detection.

Alternatives considered:

- `semantic_header_footer_migration`: too broad; implies more semantic
  understanding than the current MVP supports.
- `header_footer_migration`: concise but hides the review requirement.

## Future Option Shape

Possible future public shape:

```python
{
    "reviewed_header_footer_migration": {
        "mode": "disabled",
        "review_decisions_path": None,
        "review_decisions": None,
        "policy": "default_only",
        "page_number_behavior": "placeholder_only",
        "diagnostic_report_path": None,
    }
}
```

This shape is design-only.

## Modes

Proposed future modes:

- `disabled`: default; no migration behavior.
- `diagnose`: produce diagnostics only.
- `reviewed_migration`: require explicit review decisions and fail closed.
- future `auto_safe`: not supported; would require much broader evidence.

## Review Decisions

Public opt-in would need either:

- `review_decisions_path`
- `review_decisions`

Validation requirements:

- Explicit approval required for removal.
- Raw `would_exclude` is not enough.
- Rejected candidates remain blocked.
- Unsure candidates remain blocked.
- Body-region candidates remain protected.
- Layout placeholders remain protected.

The review decision format is not yet user-facing.

## Header/Footer Policy

Current public-safe policy proposal:

- `default_only`

Future policy concepts:

- `first_page`
- `odd_even`
- `section_scoped`

Unsupported or non-default policies must fail closed until explicitly designed,
implemented, and validated.

## Page Numbers

Proposed future values:

- `placeholder_only`: default diagnostic behavior.
- `word_field`: explicit Word `PAGE` field behavior.
- `static_text`: diagnostic/static literal behavior.
- `fail_closed`: response for unsupported or unsafe behavior.

`word_field` must not be selected by default.

## Quality Gate

The public response model should expose a concise quality summary:

- normalized token/ngram body signature gate is primary.
- strict exact-fragment mismatch is diagnostic-only.
- true body text loss fails closed.
- table text loss fails closed.
- callout text loss fails closed.
- list text loss fails closed.
- residual header/footer pollution fails closed.

## Report Output

Possible future report option:

- `diagnostic_report_path`

Rules:

- Local report output must be explicit.
- Reports may include local document metadata.
- Security/privacy guidance is required before public exposure.
- Generated reports must not be committed by default.

## Warning/Error Response Model

Each future warning/error entry should include:

- `severity`: one of `info`, `warning`, `blocked`, `error`
- `code`
- `message`
- `phase`
- `source`
- `affected_pages`
- `affected_candidates`
- `safe_to_continue`
- `user_action_required`
- `diagnostic_only`

Blocking entries use `safe_to_continue=False`. Diagnostic-only entries use
`diagnostic_only=True` and should not block when the primary normalized body
signature gate passes.

## Draft Codes

Blocking or fail-closed codes:

- `missing_review_decisions`
- `raw_would_exclude_not_allowed`
- `rejected_candidate_blocked`
- `unsure_candidate_blocked`
- `body_region_candidate_blocked`
- `layout_placeholder_blocked`
- `non_default_policy_unsupported`
- `unsafe_page_number_behavior`
- `body_text_loss_detected`
- `table_text_loss_detected`
- `callout_text_loss_detected`
- `list_text_loss_detected`
- `residual_header_footer_pollution`
- `large_document_bounded_only`

Diagnostic/non-blocking draft codes:

- `strict_exact_fragment_mismatch_diagnostic`
- `diagnostic_report_local_only`
- `public_api_not_enabled`

## Example Warning Entry

```python
{
    "severity": "blocked",
    "code": "missing_review_decisions",
    "message": "Explicit review decisions are required before migration can run.",
    "phase": "review_validation",
    "source": "reviewed_header_footer_migration",
    "affected_pages": [],
    "affected_candidates": [],
    "safe_to_continue": False,
    "user_action_required": True,
    "diagnostic_only": False,
}
```

## Remaining Work

Before public exposure:

- Finalize option naming.
- Finalize public warning/error schema.
- Define public review decision schema or automatic safe mode.
- Add public-safe fixtures.
- Add documentation and privacy guidance.
- Validate fail-closed behavior through public-facing workflows.
- Define backward compatibility rules.

This work remains future. Phase 5E does not implement public behavior.
