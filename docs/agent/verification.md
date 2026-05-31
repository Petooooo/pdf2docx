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

## Phase 2B

Date: 2026-05-31

### Scope

Phase 2B added a local-review body-filtering diff report helper in `LayoutAnalyzer.py`. The helper summarizes which blocks would be removed or kept by the reviewed filtering prototype, grouped by page and approved candidate.

Production conversion behavior did not change:

- No `Converter.convert()` behavior changed.
- No public CLI behavior changed.
- No production page body content is mutated.
- No DOCX headers or footers are generated.
- No paragraphs are merged.
- No table, image, or shape behavior changed.

### Local diff report

Generated ignored local-only file:

```text
local_reports/body-filtering-diff-report.md
```

The file may contain short extracted previews and was not staged or committed.

### Review and diff counts

Parsed local review decisions:

- `approve_exclude`: 4.
- `reject_exclude`: 3.
- `unsure`: 2.

Sample diff summary:

- Original blocks: 790.
- Would-remove blocks: 48.
- Kept blocks: 742.
- Approved candidates: 4.
- Blocked candidates: 5.
- Removed by role: 12 `page_number`, 12 `header`, 24 `footer`.
- Safety warnings: none.
- Unapproved removed candidates: 0.
- Rejected removed candidates: 0.
- Unsure removed candidates: 0.
- Layout-placeholder removed candidates: 0.

### Tests added

- Diff report includes removed and kept counts.
- Removed blocks are grouped by approved candidate.
- Rejected, unsure, and layout-placeholder candidates remain kept.
- Report generation does not mutate input summaries.
- Safety warning appears if an unapproved candidate would be removed.
- Disabled mode produces zero removed blocks.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 39 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 39 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
git status --short --ignored
```

Result: confirmed local PDF/report/review/diff files, `.venv/`, and generated caches remain ignored. No local report or review file was staged.

### Phase 2C recommendation

Phase 2C is reasonable to attempt only as another opt-in/internal step. It should still avoid default conversion changes, use explicit manual approvals, and add fixture-level checks that compare retained body text before any integration with production `Pages`, `Page`, `Blocks`, or DOCX generation paths.

## Phase 2C

Date: 2026-05-31

### Scope

Phase 2C added a report-only paragraph integrity validation helper. It compares original page summaries with the reviewed filtering diff, simulates filtered summaries in memory, and reports whether approved header/footer/page-number removal would damage body text continuity.

Production conversion behavior did not change:

- No `Converter.convert()` behavior changed.
- No public CLI behavior changed.
- No production `Pages`, `Page`, `Blocks`, table, image, or shape behavior changed.
- No DOCX header/footer generation was added.
- No production paragraph merging or body filtering was added.

Existing paragraph-like grouping remains in the normal pipeline: `Blocks.parse_block()` joins physical lines and `Lines.split_vertically_by_text()` splits text into paragraph-like `TextBlock` objects later in layout parsing. Phase 2C did not refactor that pipeline.

### Local paragraph integrity report

Generated ignored local-only file:

```text
local_reports/paragraph-integrity-report.md
```

The file may contain short extracted previews and was not staged or committed.

### Sample summary

- Original blocks: 790.
- Filtered blocks: 742.
- Removed blocks: 48.
- Body-region kept blocks: 520.
- Body-region removed blocks: 0.
- Top-region removed blocks: 12.
- Bottom-region removed blocks: 36.
- Top/bottom removed blocks: 48.
- Suspicious paragraph/body-loss warning count: 0.
- Possible cross-page continuation candidates after filtering: 11 `unlikely`, 0 `weak`, 0 `candidate`.
- Line-level body content remains available for later paragraph reconstruction.

The report indicates that the approved removals are limited to reviewed top/bottom artifacts for the sample. It does not prove paragraph reconstruction quality by itself; it only confirms this filtering prototype does not remove body-region line/block summaries.

### Tests added

- Paragraph integrity report detects no body loss when only approved top/bottom artifacts are removed.
- Paragraph integrity report warns if a body-region block would be removed.
- Paragraph integrity report warns if a page loses an unusually high number of body blocks.
- Paragraph integrity report keeps line-level body blocks available for later paragraph grouping.
- Report generation does not mutate original page summaries.
- Disabled mode keeps original summaries unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 45 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 45 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
git status --short --ignored
```

Result: confirmed local PDF/report/review/diff/paragraph-integrity files, `.venv/`, and generated caches remain ignored. No local sample or generated report was staged.

### Phase 2D recommendation

Phase 2D is safe to attempt only as another explicit opt-in/internal step. Before any production parse-path integration, keep the reviewed filtering gate, preserve a dry-run comparison, and add paragraph reconstruction checks that validate retained line-level body blocks can still be grouped into sensible DOCX paragraphs.

## Phase 2D

Date: 2026-05-31

### Scope

Phase 2D added an internal/report-only paragraph reconstruction validation helper. It uses the filtered page-summary copy from the reviewed filtering/integrity reports and estimates whether retained body line/block summaries can form sensible paragraph groups.

Production conversion behavior did not change:

- No `Converter.convert()` behavior changed.
- No public CLI behavior changed.
- No production `Pages`, `Page`, `Blocks`, table, image, or shape behavior changed.
- No DOCX header/footer generation was added.
- No production paragraph merge or body filtering was added.

### Existing paragraph grouping pipeline

The existing pdf2docx pipeline already has paragraph-like grouping later in layout parsing:

- `Blocks.clean_up()` flattens PyMuPDF text/image blocks into line-level objects and removes invalid or overlapped lines.
- `Blocks.parse_block()` sorts content in reading order.
- `Blocks._join_lines_vertically()` joins adjacent lines with similar vertical spacing and line properties into `TextBlock` candidates.
- `Blocks._split_text_block_vertically()` calls `Lines.split_vertically_by_text()`.
- `Lines.split_vertically_by_text()` splits grouped lines into paragraph-like groups using sentence-ending punctuation, line width/free-space, and new-paragraph indentation signals.
- `TextBlock.make_docx()` creates one DOCX paragraph for each parsed `TextBlock`.

Phase 2D did not refactor or call this production grouping pipeline. It only estimates reconstruction quality from layout-analysis summaries.

### Local paragraph reconstruction report

Generated ignored local-only file:

```text
local_reports/paragraph-reconstruction-validation-report.md
```

The file may contain short extracted previews and was not staged or committed.

### Sample summary

- Body blocks before filtering: 520.
- Body blocks after filtering: 520.
- Estimated paragraph groups: 388.
- Average blocks per estimated paragraph: 1.34.
- Suspicious single-line paragraph count: 153.
- Suspicious short-fragment count: 151.
- Suspicious fragmentation warning count: 1.
- Suspicious vertical-gap warning count: 0.
- Possible cross-page continuation warnings: 0.
- Integrity continuation labels remained conservative: 11 `unlikely`, 0 `weak`, 0 `candidate`.

The sample confirms reviewed header/footer filtering does not reduce body block count, but the estimated paragraph grouping remains fragmented. This supports keeping Phase 2E internal and report-driven before any production DOCX paragraph merge path is attempted.

### Tests added

- Consistent line-level body blocks are grouped into one estimated paragraph.
- Hard paragraph breaks are detected when indentation, gap, or style changes.
- Excessive one-line paragraph fragmentation triggers a warning.
- Possible cross-page continuation is reported without merging pages.
- Original page summaries are not mutated.
- Disabled/default behavior keeps original summaries unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 51 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 51 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
git status --short --ignored
```

Result: confirmed local PDF/report/review/diff/integrity/reconstruction files, `.venv/`, and generated caches remain ignored. No local sample or generated report was staged.

### Phase 2E recommendation

Phase 2E is not ready for production parse-path integration. It is safe to attempt only as another internal/report-only phase focused on improving paragraph grouping signals and validation metrics, not production body mutation or DOCX paragraph merging yet.

## Phase 2E

Date: 2026-05-31

### Scope

Phase 2E improved the internal/report-only paragraph grouping estimator and diagnostics after reviewed header/footer filtering. The estimator now groups same-row text fragments into report-only line units before estimating paragraph groups, then records split-boundary reasons and document-level fragmentation diagnostics.

Production conversion behavior did not change:

- No `Converter.convert()` behavior changed.
- No public CLI behavior changed.
- No production `Pages`, `Page`, `Blocks`, table, image, or shape behavior changed.
- No DOCX header/footer generation was added.
- No production paragraph merge or body filtering was added.

### Production comparison

The production layout path remains unchanged. Phase 2E only made the report estimator closer to the existing production grouping ideas:

- Production `Blocks._join_lines_vertically()` first groups nearby physical lines with compatible spacing.
- Production `Lines.split_vertically_by_text()` then uses sentence endings, line width/free-space, and new-paragraph indentation to split paragraph-like groups.
- Phase 2E mirrors those concepts only in simplified JSON summary analysis by adding same-row fragment grouping, indentation/width/edge diagnostics, list/heading signals, sentence-end free-space signals, and hyphenated-continuation handling.

### Local diagnostics report

Generated ignored local-only file:

```text
local_reports/paragraph-grouping-diagnostics-report.md
```

The file may contain short extracted previews and was not staged or committed.

### Phase 2D vs Phase 2E metrics

- Body blocks before/after filtering: 520 / 520.
- Estimated paragraph groups: 388 -> 125.
- Average blocks per estimated paragraph: 1.34 -> 4.16.
- Suspicious single-line paragraph count: 153 -> 36.
- Suspicious short-fragment count: 151 -> 16.
- One-line group ratio: 0.472.
- Short-fragment ratio: 0.128.
- Warning count: 1 report-only suspicious vertical gap.

### Most common split reasons

- `indentation_change`: 67.
- `style_change`: 26.
- `sentence_end_with_trailing_space`: 16.
- `previous_heading_like`: 10.
- `list_marker`: 9.
- `large_vertical_gap`: 8.
- `previous_list_item`: 8.
- `heading_like`: 2.

### Tests added

- Same-row fragments are grouped as one report-only line unit.
- Consistent multi-line body text is grouped into one estimated paragraph.
- Sentence-ending punctuation can end a paragraph only with visible trailing-space signals.
- Heading-like short lines split from body prose.
- Bullet/list-like lines stay separate from surrounding prose.
- Hyphenated line endings act as continuation evidence.
- Split reasons are recorded on paragraph boundaries.
- Fragmentation diagnostics report one-line ratio and worst pages.
- Original summaries are not mutated.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 56 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 56 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
git status --short --ignored
```

Result: confirmed local PDF/report/review/diff/integrity/reconstruction/diagnostics files, `.venv/`, and generated caches remain ignored. No local sample or generated report was staged.

### Phase 2F recommendation

Phase 2F is safe to attempt only as another internal/report-only phase. The estimator is much less fragmented than Phase 2D, but the remaining warning and split-reason distribution should be reviewed before any production paragraph merge or DOCX integration is considered.

## Phase 2F

Date: 2026-05-31

### Scope

Phase 2F added an internal/report-only comparison helper that compares Phase 2E paragraph estimator metrics with production-observed `TextBlock` grouping metrics. Production metrics are read from serialized `Converter.parse().store()` output only.

Production conversion behavior did not change:

- No `Converter.convert()` behavior changed.
- No public CLI behavior changed.
- No production `Pages`, `Page`, `Blocks`, table, image, or shape behavior changed.
- No DOCX header/footer generation was added.
- No production paragraph merge or body filtering was added.
- No DOCX was generated for the sample comparison.

### Local comparison report

Generated ignored local-only file:

```text
local_reports/paragraph-production-comparison-report.md
```

The file was not staged or committed.

### Comparison method

The comparison uses:

- Phase 2E report-only estimated paragraph groups from filtered page summaries.
- Production-observed serialized `TextBlock` groups from an in-memory `Converter.parse()` call.
- Body-region classification of production `TextBlock` bounding boxes for approximate comparison with the body-only estimator.

This is an observation adapter, not a production parser change.

### Sample metrics

Estimator metrics:

- Paragraph group count: 125.
- Body block count: 520.
- Average blocks per group: 4.16.
- Suspicious single-line count: 36.
- Suspicious short-fragment count: 16.

Production-observed metrics:

- Serialized production pages: 12.
- All production text groups: 87.
- Body-region production text groups: 52.
- Total body-region production lines: 152.
- Average production lines per body group: 2.923.
- Production suspicious single-line count: 8.
- Production suspicious short-fragment count: 8.

Mismatch summary:

- Estimator group count: 125.
- Production body `TextBlock` count: 52.
- Absolute group-count delta: 73.
- Estimator-to-production group ratio: 2.404.
- Group-count delta ratio: 1.404.
- Warning count: 1 `high_group_count_mismatch`.
- Largest page-level mismatches were on pages 4, 10, 7, 3, and 5.

The estimator remains more fragmented than the observed production grouping. This is useful because it means production already performs stronger grouping than the report estimator in the current sample, but it also means report-only heuristics still should not be connected to production paragraph merging without another validation phase.

### Tests added

- Comparison report includes estimator metrics.
- Comparison report includes production-observed metrics when serialized pages are available.
- Group-count mismatch ratio is computed.
- Missing production metrics are reported clearly.
- Input estimator reports and serialized production pages are not mutated.
- Disabled/default behavior remains explicit and non-observing.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 61 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 61 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
git status --short --ignored
```

Result: confirmed local PDF/report/review/diff/integrity/reconstruction/diagnostics/comparison files, `.venv/`, and generated caches remain ignored. No local sample or generated report was staged.

### Phase 2G recommendation

Phase 2G is safe to attempt only as another internal/report-only diagnostic phase. Do not connect filtering, paragraph merging, or DOCX generation yet; first investigate why the report estimator still reports substantially more groups than production-observed `TextBlock` grouping.

## Phase 2G

Date: 2026-05-31

### Scope

Phase 2G added an internal/report-only mismatch analysis helper. It explains the page-level difference between the Phase 2E estimator and production-observed serialized `TextBlock` grouping.

Production conversion behavior did not change:

- No `Converter.convert()` behavior changed.
- No public CLI behavior changed.
- No production `Pages`, `Page`, `Blocks`, table, image, or shape behavior changed.
- No DOCX header/footer generation was added.
- No production paragraph merge or body filtering was added.
- No DOCX was generated for the sample analysis.

### Local mismatch analysis report

Generated ignored local-only file:

```text
local_reports/paragraph-mismatch-analysis-report.md
```

The file may contain short extracted previews and was not staged or committed.

### Sample summary

- Estimator body paragraph groups: 125.
- Production-observed body `TextBlock` groups: 52.
- Absolute group-count delta: 73.
- Dominant mismatch cause: `estimator_over_split_by_indentation`.
- Mostly estimator over-splitting: yes.
- Mostly production over-merging: no.
- Warning count: 1 `high_group_count_mismatch`.

Cause counts:

- `estimator_over_split_by_indentation`: 9 pages.
- `estimator_over_split_by_style_change`: 1 page.
- `production_possible_over_split`: 1 page.
- `counts_aligned`: 1 page.

Worst mismatch pages:

- Page 4.
- Page 10.
- Page 7.
- Page 3.
- Page 5.

The mismatch appears mostly caused by the report estimator treating indentation changes as paragraph boundaries more aggressively than the production grouping pipeline. Production-observed `TextBlock` grouping is not clearly over-merging in this sample; it appears to preserve larger paragraph-like groups than the estimator.

### Tests added

- Mismatch report identifies estimator over-splitting.
- Mismatch report identifies possible production over-merge.
- Mismatch report lists worst mismatch pages.
- Mismatch cause classification is included.
- Missing production metrics are handled clearly.
- Input estimator reports and production-observed pages are not mutated.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 67 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 67 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
git status --short --ignored
```

Result: confirmed local PDF/report/review/diagnostics/comparison/mismatch files, `.venv/`, and generated caches remain ignored. No local sample or generated report was staged.

### Phase 2H recommendation

Phase 2H is safe to attempt only as another internal/report-only diagnostic phase. The next useful step is to inspect indentation-sensitive estimator split rules against production `Blocks._join_lines_vertically()` / `Lines.split_vertically_by_text()` behavior before any production integration is considered.

## Phase 2H

Date: 2026-05-31

### Scope

Phase 2H added an internal/report-only indentation rule comparison helper. It analyzes estimator paragraph boundaries caused by indentation changes and classifies how production-like grouping rules would likely treat those boundaries.

Production conversion behavior did not change:

- No `Converter.convert()` behavior changed.
- No public CLI behavior changed.
- No production `Pages`, `Page`, `Blocks`, `Lines`, `TextBlock`, table, image, or shape behavior changed.
- No DOCX header/footer generation was added.
- No production paragraph merge or body filtering was added.
- No DOCX was generated for the sample analysis.

### Production rule comparison

The production grouping inspection showed:

- `Blocks._join_lines_vertically()` primarily joins lines into text blocks based on table/image boundaries and vertical spacing. It does not treat indentation alone as a primary paragraph split.
- `Blocks._split_text_block_vertically()` delegates text-block splitting to `Lines.split_vertically_by_text()`.
- `Lines.split_vertically_by_text()` uses indentation/free-space as a new-paragraph signal only with stronger context, especially sentence-ending and free-space conditions.

This explains the Phase 2G mismatch: the report-only estimator was more eager to split on indentation than the production grouping path.

### Local indentation comparison report

Generated ignored local-only file:

```text
local_reports/indentation-rule-comparison-report.md
```

The file may contain short extracted previews and was not staged or committed.

The report was regenerated from `local_reports/input-layout-analysis-report.json` and `local_reports/header-footer-exclusion-review.md` using an inline `.venv/bin/python` script. The script rebuilt the reviewed filtering diff, paragraph integrity report, paragraph reconstruction estimator, and indentation comparison report in memory, then wrote only the ignored local report.

### Sample summary

- Total indentation-sensitive boundaries: 67.
- `estimator_should_merge`: 46.
- `estimator_should_split`: 21.
- `needs_more_metadata`: 0.
- `production_behavior_unclear`: 0.

Production-like behavior counts:

- `keep_together`: 46.
- `split`: 13.
- `treat_as_heading_list_table_boundary`: 8.

Most common production keep reason:

- `no_sentence_end_free_space_signal`: 46.

Pages with the most indentation-sensitive boundaries:

- Page 4: 10 total, 7 merge recommendations, 3 split recommendations.
- Page 5: 9 total, 5 merge recommendations, 4 split recommendations.
- Page 6: 9 total, 5 merge recommendations, 4 split recommendations.
- Page 3: 7 total, 5 merge recommendations, 2 split recommendations.
- Page 8: 7 total, 6 merge recommendations, 1 split recommendation.

The result supports the Phase 2G finding: the mismatch is mostly estimator over-splitting by indentation, not clear production over-merging.

### Tests added

- Small indentation deltas with strong continuation signals are classified as `estimator_should_merge`.
- Clear new-paragraph indentation/free-space signals are classified as `estimator_should_split`.
- Heading/list/table-like boundaries are not forced to merge.
- Missing metadata is reported clearly.
- Summary counts are produced.
- Input reports and page summaries are not mutated.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 74 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 74 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
git status --short --ignored
```

Result: confirmed local PDF/report files, `.venv/`, and generated caches remain ignored. No local sample or generated report was staged.

### Phase 2I recommendation

Phase 2I is safe to attempt only as another internal/report-only refinement phase. The next useful step is to tune estimator diagnostics around indentation and sentence/free-space signals before any production body filtering, production paragraph merging, or DOCX integration is attempted.

## Phase 2I

Date: 2026-05-31

### Scope

Phase 2I tuned only the internal/report-only paragraph grouping estimator. Weak indentation changes no longer force paragraph splits unless supported by stronger production-like signals such as sentence-ending/free-space evidence, heading/list boundaries, large vertical gaps, or strong style changes.

Production conversion behavior did not change:

- No `Converter.convert()` behavior changed.
- No public CLI behavior changed.
- No production `Pages`, `Page`, `Blocks`, `Lines`, `TextBlock`, table, image, or shape behavior changed.
- No DOCX header/footer generation was added.
- No production paragraph merge or body filtering was added.
- No DOCX was generated.

### Local reports regenerated

Regenerated ignored local-only files:

```text
local_reports/paragraph-grouping-diagnostics-report.md
local_reports/paragraph-production-comparison-report.md
local_reports/paragraph-mismatch-analysis-report.md
local_reports/indentation-rule-comparison-report.md
```

The reports may contain short extracted previews and were not staged or committed. They were regenerated from `local_reports/input-layout-analysis-report.json`, `local_reports/header-footer-exclusion-review.md`, and an in-memory `Converter.parse()` production-observation pass.

### Phase 2H to Phase 2I comparison

Estimator and production comparison:

- Phase 2H estimator paragraph groups: 125.
- Phase 2I estimator paragraph groups: 79.
- Production-observed body `TextBlock` groups: 52.
- Phase 2H absolute delta: 73.
- Phase 2I absolute delta: 27.
- Phase 2H estimator/production ratio: 2.404.
- Phase 2I estimator/production ratio: 1.519.

Indentation split comparison:

- Phase 2H indentation-sensitive boundaries: 67.
- Phase 2I indentation-sensitive split boundaries: 22.
- Phase 2H `estimator_should_merge`: 46.
- Phase 2I `estimator_should_merge`: 0.
- Phase 2H `estimator_should_split`: 21.
- Phase 2I `estimator_should_split`: 22.
- Phase 2I ignored weak indentation boundaries: 84.

Fragmentation comparison:

- Phase 2H suspicious single-line paragraph count: 36.
- Phase 2I suspicious single-line paragraph count: 14.
- Phase 2H suspicious short-fragment count: 16.
- Phase 2I suspicious short-fragment count: 5.

Remaining mismatch summary:

- Remaining absolute delta: 27.
- Remaining group-count delta ratio: 0.519.
- Worst mismatch pages: 7, 4, 10, 3, and 5.
- Dominant mismatch cause remains `estimator_over_split_by_indentation`, but it is reduced from 9 pages to 6 pages.
- Remaining warning count across estimator/comparison/mismatch reports: 3.

The estimator is now substantially closer to production-observed grouping, but the mismatch is still large enough that production integration should remain gated.

### Tests added or updated

- Indentation-only changes no longer force a split when continuation signals are strong.
- Indentation with sentence-ending/free-space evidence can still split.
- Heading-like indentation boundaries still split.
- List/bullet-like indentation boundaries still split.
- Large vertical gaps and strong style changes still split.
- Diagnostics record ignored weak indentation evidence.
- Weak indentation relaxation reduces estimated group fragmentation.
- Input reports and page summaries are not mutated.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 79 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 79 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
git status --short --ignored
```

Result: confirmed local PDF/report files, `.venv/`, and generated caches remain ignored. No local sample or generated report was staged.

### Phase 2J recommendation

Phase 2J is safe to attempt only as another internal/report-only validation phase. The estimator is closer to production grouping, but the remaining delta and warnings mean production paragraph merging, production body filtering, and DOCX integration should stay disconnected.

## Phase 2J

Date: 2026-05-31

### Scope

Phase 2J added an internal/report-only insertion point analysis helper for future reviewed header/footer filtering. It compares where filtering could be inserted in the existing PDF-to-DOCX pipeline and records risk, complexity, rollback, testing, and recommendation fields for each stage.

Production conversion behavior did not change:

- No `Converter.convert()` behavior changed.
- No public CLI behavior changed.
- No production `Pages`, `Page`, `Blocks`, `Lines`, `TextBlock`, table, image, or shape behavior changed.
- No DOCX header/footer generation was added.
- No production paragraph merge or body filtering was added.
- No DOCX was generated.

### Pipeline reference

The inspected production flow is:

```text
Converter.load_pages()
  -> Converter.parse_document()
  -> Pages.parse()
  -> RawPage.restore()
  -> RawPage.clean_up()
  -> RawPage.process_font()
  -> Pages._parse_document()
  -> RawPage.calculate_margin()
  -> RawPage.parse_section()
  -> Converter.parse_pages()
  -> Page.parse()
  -> Layout.parse()
  -> Blocks.parse_block()
  -> Lines.split_vertically_by_text()
  -> TextBlock.make_docx()
```

`Pages._parse_document()` is currently a placeholder, which makes it the least invasive future location for an opt-in document-aware experiment.

### Local report

Generated ignored local-only file:

```text
local_reports/filter-insertion-point-analysis-report.md
```

The report was not staged or committed. It was generated from the ignored sample PDF, layout report, review pack, and in-memory regenerated Phase 2I diagnostics. No DOCX output was generated.

### Evaluated insertion points

- `raw_page_cleanup`: avoid.
- `document_parse`: preferred.
- `before_page_parse`: possible.
- `before_blocks_cleanup_or_grouping`: possible, but only the after-cleanup/before-grouping variant is plausible.
- `after_textblock_grouping`: avoid.
- `docx_generation`: avoid.

Preferred insertion point:

- `document_parse`, specifically the document-level `Pages._parse_document()` stage after raw pages are cleaned and layout candidates are available, but before margin, section, table, and paragraph grouping consume the page body.

Insertion points to avoid:

- `raw_page_cleanup`, because repeated candidates and reviewed fingerprints are not safely available before normalized line-level cleanup.
- `after_textblock_grouping`, because header/footer text may already be merged into body `TextBlock` objects.
- `docx_generation`, because it would hide pollution only at render time and would not repair body parsing, grouping, sections, or tables.

### Sample summary

- Evaluated insertion points: 6.
- Preferred insertion point: `document_parse`.
- Possible insertion points: `before_page_parse`, `before_blocks_cleanup_or_grouping`.
- Avoid insertion points: `raw_page_cleanup`, `after_textblock_grouping`, `docx_generation`.
- Dry-run candidates: 9.
- Approved candidates: 4.
- Blocked candidates: 5.
- Expected sample removal count: 48.
- Body-region removed count: 0.
- Estimator paragraph groups: 79.
- Production-observed body `TextBlock` groups: 52.
- Absolute group-count delta: 27.
- Estimator/production ratio: 1.519.
- Remaining warning: `paragraph_grouping_mismatch_remaining`.

### Main risks

- The preferred insertion point still needs a strict opt-in dry-run/apply split before any mutation is attempted.
- Remaining paragraph grouping mismatch means Phase 2K must stay report-only or local-only.
- Filtering before cleanup is too early because raw blocks are not normalized.
- Filtering after `TextBlock` grouping is too late because body pollution may already affect paragraphs.
- DOCX-generation-only filtering is incomplete because semantic body structure remains polluted.
- Table detection and image/shape handling must remain protected from any future filtering experiment.

### Tests added

- Insertion point analysis includes all candidate stages.
- Each stage includes risk, complexity, and recommendation fields.
- Document-level stage can be marked preferred when reviewed filtering preserves body content.
- DOCX-generation-only stage is marked risky/incomplete.
- Post-`TextBlock` filtering is marked risky when header/footer may already merge into body text blocks.
- Missing reports or metrics are reported clearly.
- Input reports are not mutated.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 87 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 87 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
git status --short --ignored
```

Result: confirmed local PDF/report files, `.venv/`, and generated caches remain ignored. No local sample or generated report was staged.

### Phase 2K recommendation

Phase 2K is safe to attempt only as an internal, opt-in, report-only or local-only simulation at the `document_parse` insertion point. Do not connect filtering to default conversion, public CLI, production DOCX generation, or production paragraph merging yet.

## Phase 2K

Date: 2026-05-31

### Scope

Phase 2K added an internal/report-only simulation helper for reviewed header/footer filtering at the preferred `document_parse` insertion point. The helper works on copied page summaries and never mutates production `Pages`, `Page`, raw pages, `Blocks`, `Lines`, `TextBlock`, table, image, or shape objects.

Production conversion behavior did not change:

- No `Converter.convert()` behavior changed.
- No public CLI behavior changed.
- No production `Pages._parse_document()` filtering was added.
- No production `Page`, `Layout`, `Blocks`, `Lines`, or `TextBlock` behavior changed.
- No DOCX header/footer generation was added.
- No production paragraph merge or body filtering was added.
- No DOCX was generated.

### Local report

Generated ignored local-only file:

```text
local_reports/document-parse-filtering-simulation-report.md
```

The report was not staged or committed. It was generated from the ignored layout report and review pack using copied summaries only.

### Simulation summary

- Insertion point simulated: `document_parse`.
- Original block count: 790.
- Would-remove block count: 48.
- Simulated removed count: 48.
- Simulated kept count: 742.
- Approved candidate count: 4.
- Blocked candidate count: 5.
- Body-region removed count: 0.
- Rejected removed count: 0.
- Unsure removed count: 0.
- Layout-placeholder removed count: 0.

Removed counts by role:

- `header`: 12.
- `footer`: 24.
- `page_number`: 12.

Removed counts by page:

- 4 simulated removals per page across 12 pages.

### Downstream availability

- Margin input block count after simulated copy filtering: 742.
- Section input block count after simulated copy filtering: 742.
- Table input body block count: 520.
- Paragraph grouping body block count: 520.
- Body-region blocks preserved: yes.
- Image/shape data mutated: no.
- Layout placeholders removed: 0.

Risk notes:

- Margin, section, and table parsing still receive body-region content in the copied simulation.
- Line-level body summaries remain available for later paragraph grouping.
- This remains a simulation only; no raw page or production parse objects are filtered yet.

### Consistency checks

- Phase 2B expected removed count: 48.
- Phase 2B expected kept count: 742.
- Phase 2B removed count match: yes.
- Phase 2B kept count match: yes.
- Phase 2C expected body-region removed count: 0.
- Phase 2C body-region removed count match: yes.
- Safety warnings: none.

### Tests added

- Document-parse simulation removes only approved candidates.
- Rejected candidates remain.
- Unsure candidates remain.
- Layout-placeholder candidates remain.
- Body-region blocks remain.
- Dry-run mode removes zero blocks but reports would-remove counts.
- Simulated apply mode works only on copied data.
- Original inputs are not mutated.
- Simulation counts match expected reviewed filtering counts.
- Missing review decisions are reported clearly.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 95 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 95 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
git status --short --ignored
```

Result: confirmed local PDF/report files, `.venv/`, and generated caches remain ignored. No local sample or generated report was staged.

### Phase 2L recommendation

Phase 2L is safe to attempt only as another internal opt-in/local-only experiment at the `document_parse` boundary. The next step should still avoid default conversion changes, public CLI exposure, production DOCX header/footer generation, and production paragraph merging.

## Phase 2L

Date: 2026-06-01

### Scope

Phase 2L added an internal opt-in hook scaffold around the future `document_parse` insertion point, represented by `Pages._parse_document()`. The hook is disabled by default and stores only a private diagnostic report when explicitly enabled through internal settings.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No production raw page, `Page`, `Blocks`, `Lines`, `TextBlock`, table, image, or shape behavior changed.
- No header/footer content is removed from production page content.
- No DOCX header/footer generation was added.
- No production paragraph merge or body filtering was added.

### Hook behavior

- Hook location: `Pages._parse_document()`.
- Hook mode: dry-run/report-only.
- Default `Pages._parse_document()` behavior remains `('', '')`.
- The hook calls the existing document-parse simulation helper on copied layout summaries.
- The hook uses only explicit `approve_exclude` review decisions.
- Rejected, unsure, review-only, layout-placeholder, and body-region content remain protected.
- The hook report is JSON-serializable and stored only in a private `Pages` diagnostic field.

### Local report

Generated ignored local-only file:

```text
local_reports/document-parse-hook-dry-run-report.md
```

The report was not staged or committed. The local sample PDF, layout report, review pack, and generated hook report remained ignored.

### Sample summary

- Original block count: 790.
- Would-remove block count: 48.
- Simulated removed count in hook dry-run mode: 0.
- Simulated kept count in hook dry-run mode: 790.
- Production removed count: 0.
- Approved candidate count: 4.
- Blocked candidate count: 5.
- Body-region removed count: 0.
- Rejected removed count: 0.
- Unsure removed count: 0.
- Layout-placeholder removed count: 0.
- Phase 2K/expected count consistency: match.
- Safety warnings: none.

Would-remove counts by role:

- `header`: 12.
- `footer`: 24.
- `page_number`: 12.

### Tests added

- Default `Pages._parse_document()` behavior remains unchanged when the hook is disabled.
- The hook can be invoked in internal dry-run mode.
- The hook stores a report without mutating input summaries.
- The hook uses only explicit `approve_exclude` decisions.
- Rejected candidates, unsure candidates, layout placeholders, and body-region blocks remain protected.
- Dry-run mode reports would-remove counts but removes zero production blocks.
- Hook report counts match the Phase 2K simulation helper.
- Missing review decisions are reported clearly.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 102 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 102 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

```bash
git status --short --ignored
```

Result: confirmed local PDF/report files, `.venv/`, generated caches, and conversion test outputs remain ignored. No local sample or generated report was staged.

### Phase 2M recommendation

Phase 2M is safe to attempt only as another explicitly opt-in experiment. The next phase should still avoid default conversion changes and should not mutate production raw pages until the hook can prove, in a guarded path, that reviewed filtering decisions map reliably to the actual raw-page block objects.
