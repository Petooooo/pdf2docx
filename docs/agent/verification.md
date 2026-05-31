# Verification

## Phase 1A

Date: 2026-05-31

### Commands run

```bash
pytest -q test/test_layout_analyzer.py
```

Result: not run in this local shell because `pytest` is not installed.

```bash
python3 -m pytest -q test/test_layout_analyzer.py
```

Result: not run in this local Python environment because the `pytest` module is not installed.

```bash
python3 -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
python3 -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 8 tests ran successfully.

### Notes

- Phase 1A tests use synthetic dictionaries and do not require real PDF rendering.
- The new internal utility is not imported by `Converter`, `Pages`, public package exports, or the CLI.
- Existing PDF-to-DOCX conversion output should be unchanged because no conversion pipeline code was modified.
- Full existing conversion tests were not run in this local environment because project test dependencies such as `pytest` and `PyMuPDF` are not installed here.

## Phase 1B

Date: 2026-05-31

### Commands run

```bash
python3 -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
python3 -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 9 tests ran successfully.

```bash
python3 -m pytest -q test/test_layout_analyzer.py
```

Result: not run in this local Python environment because the `pytest` module is not installed.

```bash
git diff --check
```

Result: passed.

### Notes

- Phase 1B adds an opt-in `layout_analysis=True` report path during document parsing.
- Normal conversion output should remain unchanged because the report is only built on explicit opt-in and no body/table/image/shape structures are mutated.
- `Converter.store()` includes `layout_analysis` only when a report exists, so the default serialize/debug payload remains unchanged.
- No deviations from the Phase 1 plan were needed.
- Full existing conversion tests were not run in this local environment because project test dependencies such as `pytest` and `PyMuPDF` are not installed here.

## Phase 1C

Date: 2026-05-31

### Commands run

```bash
python3 -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
python3 -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 14 tests ran successfully.

```bash
python3 -m pytest -q test/test_layout_analyzer.py
```

Result: not run in this local Python environment because the `pytest` module is not installed.

```bash
git diff --check
```

Result: passed.

### Notes

- Phase 1C adds paragraph continuation candidate scoring to the existing opt-in `layout_analysis` report only.
- The report now includes `paragraph_continuation_candidates` with previews, score, label, positive/negative signals, and a reason summary.
- No DOCX generation path, body/header/footer filtering, table/image/shape behavior, public CLI, or paragraph mutation code was modified.
- Normal conversion output should remain unchanged by design because the new logic only runs while building the explicit opt-in analysis report.
- Full existing conversion tests were not run in this local environment because project test dependencies such as `pytest` and `PyMuPDF` are not installed here.

## Test Environment Verification and Phase 1D

Date: 2026-05-31

### Repository test configuration

- Inspected `requirements.txt`, `setup.py`, `.github/workflows/test.yml`, and `.github/workflows/publish.yml`.
- `pyproject.toml`, `tox.ini`, `pytest.ini`, and `setup.cfg` were not present.
- The CI workflow installs project requirements, installs `pytest`, runs `python setup.py develop`, and then runs `pytest -v ./test/test.py::TestConversion`.
- Phase 1D used the narrower layout-analysis commands requested for this local validation task.

### Environment and dependency status

```bash
python3 --version
```

Result: Python 3.10.12.

```bash
python3 -m pip --version
```

Result: system pip 22.0.2.

```bash
python3 -m pip show pytest
python3 -m pip show PyMuPDF
python3 -c "import fitz; print(fitz.__doc__[:120])"
```

Result: `pytest` and `PyMuPDF` were not installed in the system Python environment, and `fitz` import failed.

```bash
python3 -m venv .venv
```

Result: failed because this system Python does not have `ensurepip` / `python3.10-venv` available.

```bash
python3 -m pip install --target /tmp/pdf2docx-venv-bootstrap virtualenv
PYTHONPATH=/tmp/pdf2docx-venv-bootstrap python3 -m virtualenv --clear .venv
.venv/bin/python -m pip install -e . pytest
.venv/bin/python -m pip install 'pytest<9'
```

Result: created a local `.venv` and installed project dependencies locally. No project dependency files were changed.

- Local `pytest`: 8.4.2.
- Local `PyMuPDF`: 1.27.2.3.
- Local `fitz` import: available.

### Commands run

```bash
.venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: failed when `TMP` / `TEMP` pointed to the Windows temp directory under `/mnt/c/.../Temp`; pytest capture hit `FileNotFoundError` while truncating a temporary file. This is an environment temp-file issue, not a layout analyzer assertion failure.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 14 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 14 tests ran successfully.

```bash
git diff --check
```

Result: passed.

### Local sample handling

- Copied the provided PDF to `local_samples/input.pdf`.
- Generated the opt-in report at `local_reports/input-layout-analysis-report.json`.
- Added `.venv/`, `local_samples/`, and `local_reports/` to `.gitignore`.
- Confirmed `local_samples/input.pdf` and the generated JSON report are ignored and not tracked by Git.
- No DOCX was generated for this validation.

### Phase 1D sample report summary

The report was generated with `layout_analysis=True` through `Converter.parse()` only. No normal DOCX conversion path was invoked or changed.

- Pages analyzed: 12.
- Text blocks / placeholders summarized: 790.
- Region totals: 164 top, 520 body, 106 bottom.
- Repeated text candidate clusters: 9 total.
- Repeated candidate regions: 4 top-region clusters and 5 bottom-region clusters.
- Repeated candidate support counts: four clusters appeared on all 12 pages; one appeared on 10 pages; one appeared on 8 pages; three appeared on 2 adjacent pages.
- Paragraph continuation entries: 11 page-pair entries.
- Continuation labels: 9 `unlikely`, 2 `weak`, 0 `candidate`.
- Continuation score range: 0.0 to 0.45.

Header/footer observations without extracted text:

- The analyzer found a strong all-page top-region candidate that looks like a document title/header.
- The analyzer found strong all-page bottom-region candidates including a normalized page-number placeholder and footer-like repeated text.
- Repeated image placeholders were also clustered in top/bottom regions. These are useful as layout signals, but they need image identity and position metadata before being treated as true semantic headers or footers.
- Low-support two-page top/bottom repeated clusters appear likely to be false positives from body content near page boundaries rather than real headers or footers.

Paragraph continuation observations:

- No page pair crossed the current `candidate` threshold.
- The two `weak` entries look risky rather than clearly correct because they involve very short text or placeholder-like next/previous blocks.
- Several `unlikely` entries were correctly suppressed by sentence-ending punctuation, heading-like next blocks, style mismatch, or boundary mismatch signals.

### Remaining risks and next recommendation

- The analyzer is still text-block centric; it needs better handling for image placeholders, list markers, and very short blocks before any body mutation is safe.
- Repeated body text near page boundaries can still look like a header/footer candidate when it appears on adjacent pages.
- Section-specific headers and first-page exceptions need explicit modeling before Phase 2 header/footer removal.
- Next phase should remain report-only or introduce more debug-only scoring signals first: minimum text length filters, placeholder-specific handling, list/number-only suppression, repeated-cluster exclusion during continuation scoring, and richer body-region margin inference.

## Phase 1E

Date: 2026-05-31

### Scope

Phase 1E hardened the opt-in `layout_analysis` report only. No body filtering, header/footer removal, paragraph merge, DOCX generation behavior, public CLI behavior, table behavior, image behavior, or shape behavior was changed.

### Heuristics improved

- Added per-block text-quality signals for short text, placeholder-like text, placeholder kind, word count, and semantic weight.
- Added repeated-candidate `semantic_confidence`, `confidence_label`, support level, adjacent-only signal, and reason text while preserving the raw support-based `confidence`.
- Down-scored placeholder-like and very short text in paragraph continuation scoring.
- Excluded likely repeated top/bottom boundary text from continuation endpoint selection when building the opt-in report.
- Added clearer continuation reasons for short text, placeholder text, and repeated boundary text.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 19 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 19 tests ran successfully.

```bash
git diff --check
```

Result: passed.

### Local sample recheck

Regenerated the ignored local report at `local_reports/input-layout-analysis-report.json` from the ignored sample `local_samples/input.pdf`.

- Pages analyzed: 12.
- Text blocks / placeholders summarized: 790.
- Repeated text candidate clusters: 9 total.
- Repeated confidence labels after hardening: 4 `strong`, 2 `placeholder`, 3 `cautious`.
- Repeated placeholder kinds: 1 page-number placeholder cluster, 2 image-placeholder clusters, 6 normal text clusters.
- Paragraph continuation entries: 11 page-pair entries.
- Continuation labels after hardening: 11 `unlikely`, 0 `weak`, 0 `candidate`.
- The two previously weak continuation entries were down-scored by short-text, placeholder, repeated-boundary, or mismatch signals.

### Local-only file status

- `.venv/`, `local_samples/`, and `local_reports/` remained ignored by Git.
- The sample PDF and generated JSON report were not staged or committed.
- No generated DOCX files were created for Phase 1E.

### Remaining risks before Phase 2

- The report is still heuristic and text-block centric; it does not prove safe removal or paragraph merging.
- Image placeholders are now down-scored semantically, but image identity and placement still need richer metadata.
- Low-support repeated clusters are marked cautious, but section-specific repeated content still needs explicit section modeling.
- Continuation scoring remains conservative; Phase 2 should add more debug-only review on varied fixtures before mutating body content.

## Phase 1F

Date: 2026-05-31

### Scope

Phase 1F added a non-destructive `header_footer_exclusion_dry_run` section to the opt-in `layout_analysis` report. It simulates future header/footer exclusion candidates from repeated text clusters, but it does not remove, rewrite, merge, or mutate any page body content.

No production DOCX conversion behavior, public CLI behavior, table behavior, image behavior, shape behavior, or paragraph merging behavior was changed.

### Dry-run policy added

- Strong high-support top-region repeated text is marked as a future `header` candidate with action `would_exclude`.
- Strong high-support bottom-region repeated text is marked as a future `footer` candidate with action `would_exclude`.
- Stable bottom page-number placeholders are marked as `page_number` candidates with action `would_exclude`, not semantic body text.
- Image placeholders are marked as `layout_placeholder` with action `review`, not semantic header/footer text.
- Cautious low-support or adjacent-only boundary clusters are preserved as `review`.
- Body-region repeated candidates are kept as body content when the dry-run helper is used with body-region candidates.
- Every dry-run item includes positive/negative signals and a reason string. The section is JSON-serializable and report-only.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 26 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 26 tests ran successfully.

```bash
git diff --check
```

Result: passed.

### Local sample recheck

Regenerated the ignored local report at `local_reports/input-layout-analysis-report.json` from the ignored sample `local_samples/input.pdf`.

- Pages analyzed: 12.
- Text blocks / placeholders summarized: 790.
- Repeated text candidate clusters: 9 total.
- Dry-run candidates: 9 total.
- Dry-run actions: 4 `would_exclude`, 5 `review`, 0 `keep`.
- Dry-run proposed roles: 1 `header`, 2 `footer`, 1 `page_number`, 2 `layout_placeholder`, 3 `review_only`.
- Dry-run regions: 4 top-region candidates and 5 bottom-region candidates.
- Affected pages: all 12 pages had at least one dry-run candidate signal.

### Local-only file status

- `.venv/`, `local_samples/`, and `local_reports/` remained ignored by Git.
- The sample PDF and generated JSON report were not staged or committed.
- No generated DOCX files were created for Phase 1F.

### Remaining risks before actual body filtering

- `would_exclude` means only "future exclusion candidate"; no destructive action should use it until more fixture review is complete.
- Image placeholders are still layout-only signals and need image identity or placement analysis before semantic treatment.
- Page-number/footer handling still needs section, first-page, odd/even, and margin modeling before DOCX header/footer generation.
- Body filtering should remain blocked until a review command or fixture evaluation can compare dry-run candidates against expected retained body text.

## Phase 1G

Date: 2026-05-31

### Scope

Phase 1G created a local-only review pack from the existing `header_footer_exclusion_dry_run` report. The review pack is intended for human approval before any future Phase 2A body filtering.

No production conversion behavior changed. No PDF page content, body blocks, paragraphs, tables, images, shapes, DOCX output, public CLI behavior, or `Converter.convert()` behavior was modified.

### Local review artifact

Generated local-only file:

```text
local_reports/header-footer-exclusion-review.md
```

The file is ignored through `local_reports/` and must not be committed because it may contain short extracted PDF previews for review.

Review pack contents:

- candidate id / fingerprint
- proposed role and action
- region and affected pages
- support count
- confidence label and semantic confidence
- positive and negative signals
- reason summary
- short local-only preview
- review recommendation
- manual decision fields: `approve_exclude`, `reject_exclude`, `unsure`

### Review pack counts

- Dry-run candidates included: 9.
- Actions: 4 `would_exclude`, 5 `review`, 0 `keep`.
- Review recommendations: 4 `safe_candidate`, 5 `needs_manual_review`, 0 `keep_body`.
- Proposed roles: 1 `header`, 2 `footer`, 1 `page_number`, 2 `layout_placeholder`, 3 `review_only`.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 26 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 26 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
git status --short --ignored
```

Result: confirmed `local_samples/`, `local_reports/`, `.venv/`, generated caches, and the local review pack remain ignored. The only commit-intended file from Phase 1G is documentation under `docs/agent/`.

### Recommendation for Phase 2A

Phase 2A should not consume raw `would_exclude` labels directly. It should start from explicit review decisions in the local review pack, keep filtering opt-in, and include tests that prove default conversion output remains unchanged.

## Phase 2A

Date: 2026-05-31

### Scope

Phase 2A added an internal reviewed header/footer filtering prototype in `LayoutAnalyzer.py`. The helper parses manual review decisions and can build an opt-in dry-run/apply filtering report from existing layout-analysis page summaries.

Default behavior remains unchanged:

- No normal PDF-to-DOCX conversion output changes by default.
- No `Converter.convert()` behavior changed.
- No public CLI behavior changed.
- No paragraphs are merged.
- No DOCX headers or footers are generated.
- No table, image, or shape behavior changed.
- No filtering runs unless the internal helper is called with `enabled=True`.

### Review decision counts

Parsed local review pack:

- `approve_exclude`: 4.
- `reject_exclude`: 3.
- `unsure`: 2.

The reviewed filtering helper treated only the 4 explicit `approve_exclude` candidates as eligible. The 3 rejected and 2 unsure candidates were blocked. Raw `would_exclude` labels without manual approval are not sufficient.

Local sample summary from the ignored report and review pack:

- Approved candidates: 4.
- Blocked candidates: 5.
- Opt-in dry-run `would_remove_block_count`: 48.
- Opt-in dry-run `removed_block_count`: 0.
- Internal apply-mode sample summary: 48 removed, 742 kept.

### Tests added

- Review markdown decision parsing.
- Approved candidate is filtered only when opt-in is enabled.
- Rejected candidates are not filtered.
- Unsure candidates are not filtered.
- Raw `would_exclude` without manual approval is not filtered.
- Layout placeholders are not filtered.
- Default disabled mode does not mutate page summaries.
- Filtering report includes original, would-remove, removed, and kept counts.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 33 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 33 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
git status --short --ignored
```

Result: confirmed local PDF/report/review files, `.venv/`, and generated caches remain ignored. No local report or review file was staged.

### Remaining risks

- This is still an internal prototype over layout-analysis summaries, not production body filtering.
- The sample apply-mode count is only a review aid and must not be treated as a production deletion result.
- Phase 2B or later should keep filtering opt-in, connect only to explicitly reviewed decisions, and include fixture-level visual/body-retention checks before any conversion-path integration.
