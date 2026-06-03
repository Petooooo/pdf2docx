# Reviewed Filtering Internal API Surface

## Status

This document drafts the internal-only request/config surface for the reviewed
header/footer migration MVP. It is not a public API proposal and it does not
enable migration in default conversion.

The surface is intentionally narrow:

- Internal-only.
- Disabled by default.
- Explicit opt-in required.
- Explicit review decisions required when enabled.
- Default conversion unchanged.
- Public CLI/API closed.
- No production header/footer migration wired in this phase.

## Request Shape

The internal helper is:

- `build_reviewed_header_footer_internal_request`
- `summarize_reviewed_header_footer_internal_request`
- `validate_reviewed_header_footer_internal_request`

The request is JSON-serializable and diagnostic. A disabled default request has
this shape in summary form:

```python
{
    "enabled": False,
    "surface": "internal_only",
    "mode": "default_policy_migration_smoke",
    "requires_review_decisions": True,
    "page_number_behavior": "placeholder_only",
    "quality_gate": "normalized_token_ngram",
    "public_cli": False,
    "public_api": False,
}
```

The helper embeds the existing internal migration profile summary and exposes
the derived private reviewed-filtering config for future internal adapters, but
it does not call `Pages.parse`, write DOCX files, or mutate converter output.

## Opt-In Rules

An internal caller must set:

- `enabled=True`
- explicit review decisions through `review_decisions` or
  `review_decisions_path`

The request remains blocked if enabled without review decisions. Raw
`would_exclude` candidates are not enough. Rejected and unsure candidates remain
blocked. Body-region candidates and layout placeholders remain protected.

## Modes

Supported request modes:

- `default_policy_migration_smoke`
- `filtered_parse_experiment`

Documented future modes remain disabled:

- `first_page_migration_smoke`
- `odd_even_migration_smoke`
- `section_scoped_migration_smoke`
- `production_default_migration`

Selecting a future mode is fail-closed and does not execute migration.

## Migration Profile Relationship

The request auto-builds a migration profile from safe internal defaults unless
a profile/config is supplied. The generated profile preserves the Phase 4J
rules:

- parse mode: `filtered_parse_experiment`
- explicit approval required
- raw `would_exclude` blocked
- rejected/unsure blocked
- body region protected
- layout placeholders protected
- local output limited to temporary or ignored paths
- public exposure: `none`

The request summary includes the migration profile summary, writer settings,
DOCX header/footer plan requirements, and reviewed filtering config for future
private adapters.

## Policy Limitations

Only the `default` header/footer policy is allowed for current writer
application. These policies remain fail-closed:

- `first_page`
- `odd_even`
- `section_scoped`
- `unsupported`

The request surface must not silently coerce non-default policies into
`default`.

## Page Numbers

Page-number behavior remains explicit:

- `placeholder_only`: default diagnostic behavior.
- `word_field`: explicit internal-only Word `PAGE` field behavior.
- `static_text`: diagnostic/static literal behavior only.
- `unsupported`: fail-closed.

`word_field` is not selected by default and is not public.

## Quality Gate

The request records the Phase 4G/5A safety gates:

- normalized token/ngram body signature is primary.
- strict exact-fragment mismatch is diagnostic-only.
- true body text loss fails closed.
- table text loss fails closed.
- callout text loss fails closed.
- list text loss fails closed.
- residual header/footer pollution fails closed.
- unsafe policy and unsafe page-number behavior fail closed.

## Local Output Rules

Local output policy is `temp_or_ignored_only`.

Generated local reports, review packs, DOCX files, images, subset PDFs, caches,
and local sample PDFs must remain ignored and must not be committed.

## Public Readiness

Public/default exposure remains blocked because:

- local evidence is ignored and non-committed.
- positive local smoke evidence is still narrow.
- non-default policy writing is not implemented.
- image/logo header/footer migration is not implemented.
- paragraph continuation merge is not implemented.
- production/default integration has not been designed or approved.

Future public API or CLI exposure would require a separate phase with broader
fixtures, policy support, safety review, and product-facing semantics.
