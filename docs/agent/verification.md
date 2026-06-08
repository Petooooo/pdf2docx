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

## Phase 2M

Date: 2026-06-01

### Scope

Phase 2M added an internal/report-only raw-object mapping validation helper for the `document_parse` boundary. The helper checks whether reviewed layout-analysis removal candidates map safely to actual `raw_page.blocks` objects after cleanup and font processing, before any future body filtering experiment.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No production raw page, `Page`, `Blocks`, `Lines`, `TextBlock`, table, image, or shape behavior changed.
- No header/footer content is removed from production page content.
- No DOCX header/footer generation was added.
- No production paragraph merge or body filtering was added.

### Mapping target

- Insertion point: `document_parse`.
- Target location: `raw_page.blocks` after `RawPage.clean_up()` and `RawPage.process_font()`, near `Pages._parse_document()`.
- Matching signals: page index, normalized text fingerprint, top/body/bottom region, bbox proximity/overlap, placeholder kind, and reviewed role.
- The report uses only explicit `approve_exclude` decisions and never raw `would_exclude` labels alone.

### Local report

Generated ignored local-only file:

```text
local_reports/document-parse-raw-object-mapping-report.md
```

The report was not staged or committed. The local sample PDF, layout report, review pack, hook report, and generated mapping report remained ignored.

### Sample summary

- Approved candidate count: 4.
- Blocked candidate count: 5.
- Expected would-remove count: 48.
- Observed would-remove count: 48.
- Mapped raw object count: 48.
- Exact match count: 48.
- Fuzzy match count: 0.
- Ambiguous match count: 0.
- Missing match count: 0.
- Unsafe match count: 0.
- Body-region matched-for-removal count: 0.
- Rejected/unsure/layout-placeholder matched-for-removal count: 0.
- All expected blocks mapped once: yes.
- Safety warnings: none.

Mapping by role:

- `header`: 12 exact matches.
- `footer`: 24 exact matches.
- `page_number`: 12 exact matches.

### Tests added

- Approved summary candidate maps to exactly one raw-like object.
- Rejected candidates do not map for removal.
- Unsure candidates do not map for removal.
- Layout-placeholder candidates do not map for removal.
- Body-region raw-like objects are not mapped for removal.
- Missing raw objects produce clear warnings.
- Ambiguous multiple raw matches produce clear warnings.
- Fuzzy bbox/text matches are reported separately from exact matches.
- Mapping report does not mutate input raw-like objects or summaries.
- Disabled/default behavior remains unchanged.
- The internal `Pages` mapping validation path stores a report without mutating fake raw pages.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 112 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 112 tests ran successfully.

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

### Phase 2N recommendation

Phase 2N is safe to attempt only as an explicitly opt-in copied-object experiment. The next step should still avoid mutating production raw pages by default, but it can test whether a copied `raw_page.blocks` collection can be filtered using the validated one-to-one raw-object mapping.

## Phase 2N

Date: 2026-06-01

### Scope

Phase 2N added an internal/report-only copied raw-page filtering apply experiment. It uses the reviewed one-to-one raw-object mapping from Phase 2M, but removes matched objects only from copied raw-page-like dictionaries. Production raw pages and downstream parser objects are not mutated.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No production raw page, `Page`, `Blocks`, `Lines`, `TextBlock`, table, image, or shape behavior changed.
- No header/footer content is removed from production page content.
- No DOCX header/footer generation was added.
- No production paragraph merge or body filtering was added.

### Local report

Generated ignored local-only file:

```text
local_reports/copied-raw-page-filtering-apply-report.md
```

The report was not staged or committed. The local sample PDF, layout report, review pack, hook report, raw-object mapping report, and generated copied-apply report remained ignored.

### Sample summary

- Original raw block count: 790.
- Copied filtered block count: 742.
- Removed copied block count: 48.
- Approved candidate count: 4.
- Blocked candidate count: 5.
- Phase 2M mapped raw object count: 48.
- Expected mapping count: 48.
- Body-region removed count: 0.
- Rejected/unsure/layout-placeholder removed count: 0.
- Original raw pages mutated: no.
- Removed count matches Phase 2M mapping count: yes.
- Safety warnings: none.

Removed counts by role:

- `header`: 12.
- `footer`: 24.
- `page_number`: 12.

Removed counts by page:

- 4 copied raw blocks per page across 12 pages.

Downstream copied-input checks:

- Margin input count before/after: 790 / 742.
- Section input count before/after: 790 / 742.
- Body block count before/after: 520 / 520.
- Image/shape placeholder count before/after: 86 / 86.
- Table risk note: body-region raw objects remain preserved in the copied data.
- Paragraph grouping risk note: body-region line/block objects remain preserved in the copied data.

### Tests added

- Copied apply removes only approved mapped raw-like objects.
- Original raw-like objects are not mutated.
- Copied raw-like objects are filtered as expected.
- Rejected candidates remain.
- Unsure candidates remain.
- Layout-placeholder candidates remain.
- Body-region objects remain.
- Missing mapping blocks apply partially and report a warning.
- Ambiguous mapping blocks apply partially and report a warning.
- Copied apply count matches the Phase 2M expected mapping count in the safe case.
- Disabled/default behavior remains unchanged.
- The internal `Pages` copied-apply path stores a report without mutating fake raw pages.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 122 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 122 tests ran successfully.

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

### Phase 2O recommendation

Phase 2O is safe to attempt only as an explicitly opt-in, non-default experiment. The next phase can consider a guarded production-object apply path, but it should remain disabled by default and should first verify that raw-page object mutation can be isolated, reversible, and covered by conversion-regression checks.

## Phase 2O

Date: 2026-06-01

### Scope

Phase 2O added an internal/report-only guarded apply/restore experiment for actual `raw_page.blocks` objects at the `document_parse` boundary. The experiment snapshots the original block object list, applies reviewed filtering inside a guarded window, validates the temporary filtered state, and restores the original block object list before returning.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No persistent production raw-page filtering was enabled.
- No `Page`, `Blocks`, `Lines`, `TextBlock`, table, image, or shape behavior changed by default.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.

### Local report

Generated ignored local-only file:

```text
local_reports/guarded-raw-page-apply-restore-report.md
```

The report was not staged or committed. The local sample PDF, layout report, review pack, raw-object mapping report, copied apply report, and generated guarded apply/restore report remained ignored.

### Sample summary

- Experiment mode: `guarded_apply_restore`.
- Original raw block count before apply: 790.
- Filtered raw block count during apply: 742.
- Restored raw block count after restore: 790.
- Removed during apply count: 48.
- Approved candidate count: 4.
- Blocked candidate count: 5.
- Body-region removed count: 0.
- Rejected/unsure/layout-placeholder removed count: 0.
- Snapshot created: yes.
- Restore completed: yes.
- Restore exact count match: yes.
- Restore fingerprint match: yes.
- Original raw pages left mutated: no.
- Safety warnings: none.

Removed counts by role:

- `header`: 12.
- `footer`: 24.
- `page_number`: 12.

Removed counts by page:

- 4 raw blocks per page across 12 pages during the guarded apply window.

Downstream guarded-window checks:

- Margin input count before/during: 790 / 742.
- Section input count before/during: 790 / 742.
- Body block count before/during: 520 / 520.
- Image/shape placeholder count before/during: 86 / 86.
- Table risk note: body-region raw objects remain preserved during the apply window.
- Paragraph grouping risk note: body-region line/block objects remain preserved during the apply window.

Consistency:

- Phase 2M mapped raw object count: 48.
- Phase 2N copied apply removed count: 48.
- Removed during guarded apply: 48.
- Removed count matches Phase 2M: yes.
- Removed count matches Phase 2N: yes.
- Expected mapping count matches Phase 2M: yes.

### Tests added

- Guarded apply removes only approved mapped raw-like objects during the apply window.
- Original raw-like objects are restored after the experiment.
- Restore count matches the original count.
- Restore fingerprint matches the original fingerprint.
- Rejected candidates remain.
- Unsure candidates remain.
- Layout-placeholder candidates remain.
- Body-region objects remain.
- Missing mapping prevents unsafe apply and reports warnings.
- Ambiguous mapping prevents unsafe apply and reports warnings.
- Guarded apply count matches Phase 2M and Phase 2N in the safe case.
- Disabled/default behavior remains unchanged.
- The internal `Pages` guarded apply path stores a report and leaves fake raw pages restored.

Implementation note:

- The guarded restore path restores the collection's exact internal object list instead of using `Blocks.reset()`, because `reset()` can skip falsey bbox objects and would not be exact enough for this safety experiment.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 129 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 129 tests ran successfully.

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

### Phase 2P recommendation

Phase 2P is safe to attempt only as an explicitly opt-in, non-default production experiment. The next phase can consider leaving reviewed filtering applied through downstream parsing under a private guard, but it must still avoid public CLI exposure and must compare parse/conversion behavior before any default-path change.

## Phase 2P

Date: 2026-06-01

### Scope

Phase 2P added an internal, explicitly opt-in filtered parse experiment at the `document_parse` boundary. The experiment applies reviewed header/footer/page-number filtering to actual `raw_page.blocks` only inside the private experiment window, collects baseline-vs-filtered parse metrics from temporary downstream parse copies, and restores the original raw-page block list before normal parsing continues.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering is not default-on.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.
- No production body filtering is connected to the default parse path.

### Local report

Generated ignored local-only file:

```text
local_reports/filtered-parse-experiment-report.md
```

The report was not staged or committed. The local sample PDF, layout report, review pack, mapping report, copied apply report, guarded apply/restore report, and generated filtered parse report remained ignored.

### Sample summary

- Baseline raw block count: 790.
- Filtered raw block count: 742.
- Removed raw block count: 48.
- Removed counts by role: 12 `header`, 24 `footer`, 12 `page_number`.
- Removed counts by page: 4 per page across 12 pages.
- Baseline parsed text block count: 523.
- Filtered parsed text block count: 486.
- Baseline body `TextBlock` count: 393.
- Filtered body `TextBlock` count: 393.
- Baseline paragraph-like `TextBlock` count: 523.
- Filtered paragraph-like `TextBlock` count: 486.
- Baseline table count: 139.
- Filtered table count: 127.
- Baseline image count: 0.
- Filtered image count: 0.
- Baseline section count: 50.
- Filtered section count: 50.
- Body-region removed count: 0.
- Rejected/unsure/layout-placeholder removed count: 0.
- Raw pages restored or reloaded after experiment: yes.
- Restore fingerprint match: yes.

Safety warnings:

- `table_count_changed`: baseline 139, filtered 127.

Interpretation:

- Body-region text block count remained unchanged, so the reviewed removals did not drop parsed body text in this sample.
- Section and image counts remained unchanged.
- The table-count decrease should be manually reviewed before any production integration. It may indicate reduced header/footer pollution in stream-table detection, but Phase 2P records it as a warning rather than treating it as proof.

### Tests added

- Filtered parse experiment reports baseline and filtered parse metrics.
- Disabled/default path remains unchanged.
- Approved raw objects are removed only during the filtered parse experiment.
- Rejected, unsure, layout-placeholder, and body-region objects remain.
- Baseline and filtered parse metrics are both reported.
- Experiment restores raw-page state after completion.
- Warning logic reports table/body/paragraph-fragmentation risks.
- Default conversion tests still pass.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 135 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 135 tests ran successfully.

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

### Phase 2Q recommendation

Phase 2Q is safe to attempt only as another explicitly opt-in, non-default experiment. The next phase should investigate the table-count delta and compare parse outputs more deeply before any persistent production filtering path is enabled.

## Phase 2Q

Date: 2026-06-01

### Scope

Phase 2Q added an internal/report-only table-count delta investigation helper. The helper compares baseline and filtered parse table summaries from the opt-in filtered parse experiment, classifies baseline-only, filtered-only, and changed common tables, and checks whether baseline-only tables overlap approved header/footer/page-number removals.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering remains opt-in and non-default.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.
- No production body filtering was enabled.

### Table parsing context

The existing production pipeline detects tables inside `Layout.parse()` before paragraph grouping:

- `Layout._parse_table()` calls `TablesConstructor.lattice_tables()` for explicit bordered tables.
- `Layout._parse_table()` calls `TablesConstructor.stream_tables()` for borderless/layout-derived tables.
- `Blocks.collect_stream_lines()` identifies possible stream-table line groups from row/flow-layout signals.
- `Blocks.assign_to_tables()` replaces assigned line/table content with `TableBlock` objects.
- `TableBlock.store()` represents table geometry through bbox, rows, cells, and nested cell blocks.

Phase 2Q did not modify any of that behavior; it only records table summaries in the opt-in parse metrics.

### Local report

Generated ignored local-only file:

```text
local_reports/table-delta-investigation-report.md
```

The report was not staged or committed. The local sample PDF, layout report, review pack, mapping report, guarded apply/restore report, filtered parse report, and generated table delta report remained ignored.

### Sample summary

- Baseline table count: 139.
- Filtered table count: 127.
- Table-count delta: -12.
- Baseline-only table count: 12.
- Filtered-only table count: 0.
- Changed common table count: 11.
- Body-region baseline-only table count: 1.
- Top/bottom baseline-only table count: 11.
- Tables overlapping removed header/footer/page-number candidates: 12.
- Suspicious body table loss count: 1.
- Likely header/footer false-positive table count: 11.
- Table changes limited to top/bottom: no.
- Table changes affect body region: yes.
- Classification: `unsafe`.

Interpretation:

- 11 of 12 baseline-only tables are bottom-region 1x3 stream-table-like structures overlapping approved removals, so they are likely header/footer/page-number pollution removed by the experiment.
- 1 baseline-only table is classified as body-region, even though it overlaps removed candidates; this is not safe to dismiss without fixture-level inspection.
- 11 common tables changed bbox after filtering, including body-region changes on pages 5, 8, and 10.
- The table delta therefore remains a blocking warning for production integration.

Safety warnings:

- `body_region_table_disappeared`: 1.
- `common_table_changed`: 11.
- `not_all_baseline_only_tables_explained_by_removed_candidates`: 11 explained out of 12 baseline-only tables.

### Tests added

- Table delta report detects baseline-only tables.
- Top/bottom baseline-only tables overlapping approved removals are classified as likely pollution removed.
- Body-region baseline-only tables trigger a safety warning.
- Changed common table geometry triggers a warning.
- Unchanged table counts produce no delta warning.
- Filtered-only tables are reported clearly.
- Input baseline/filtered parse outputs are not mutated.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 143 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 143 tests ran successfully.

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

### Phase 2R recommendation

Phase 2R is not safe as a production integration step yet. The next phase should remain opt-in/report-only and inspect the body-region baseline-only table plus changed common body tables before any persistent filtering behavior is attempted.

## Phase 2R

Date: 2026-06-01

### Scope

Phase 2R added an internal/report-only body table delta root-cause helper. The helper focuses on the unsafe Phase 2Q table deltas by classifying baseline-only and changed common tables with removed-candidate overlap, nearest removed-candidate distance, region, bbox, row/column/cell counts, and severity.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering remains opt-in and non-default.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.
- No production body filtering was enabled.

### Local report

Generated ignored local-only file:

```text
local_reports/body-table-delta-root-cause-report.md
```

The report was not staged or committed. The local sample PDF, layout report, review pack, filtered parse report, table delta report, and generated root-cause report remained ignored.

### Sample summary

- Body-region baseline-only table count: 1.
- Changed common table count: 11.
- Pages affected: 1 through 12.
- Likely false-positive table count: 1.
- Likely header/footer pollution table count: 11.
- Possible real body table loss count: 0.
- Unsafe table delta count: 8.
- Review table delta count: 4.
- Safe table delta count: 11.
- Changed body table geometry count: 8.
- Top/bottom-only table delta count: 14.
- Classification: `unsafe`.

Overlap/proximity summary:

- Tables overlapping removed candidates: 12.
- Tables near removed candidates: 12.
- Nearest distance min/max: 0.0 / 115.8.
- Overlap roles: `footer` 24, `page_number` 12.

Interpretation:

- The 11 top/bottom baseline-only tables are likely header/footer/page-number pollution removed by reviewed filtering.
- The single body-region baseline-only table is a small 1x3 structure overlapping approved removals and is classified as `baseline_false_positive_table`, but severity remains `review`.
- The 11 changed common tables are bbox-only changes, but 8 are body-region geometry changes with insufficient evidence, so they remain `unsafe`.
- No possible real body table loss was proven, but production integration remains blocked because body table geometry changed.

Safety warnings:

- `unsafe_table_delta`: 8.
- `changed_body_table_geometry`: 8.
- `insufficient_table_delta_evidence`: 11.

### Tests added

- Body-region baseline-only table is classified as unsafe by default.
- Top/bottom baseline-only table overlapping approved removed candidates is classified as likely pollution removed.
- Changed common table near removed top/bottom artifacts can be classified as safe when body impact is absent.
- Changed common body table cell loss triggers unsafe.
- False-positive body table can be classified separately when evidence supports it.
- Overlap and distance-to-removed-candidate metrics are reported.
- Input baseline/filtered parse outputs are not mutated.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 151 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 151 tests ran successfully.

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

### Phase 2S recommendation

Phase 2S is not safe as production integration. The next phase should remain internal/report-only and inspect the 8 changed body table geometries, especially whether bbox-only changes are harmless stream-table boundary shifts or signs of body table structure instability.

## Phase 2S

Date: 2026-06-01

### Scope

Phase 2S added an internal/report-only body table geometry delta safety helper. The helper focuses only on changed common body-region tables from Phase 2R and compares baseline vs filtered table structure using bbox deltas, row/column/cell counts, cell bbox summaries, and cell text signatures.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering remains opt-in and non-default.
- No production body filtering was enabled.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.

### Local report

Generated ignored local-only file:

```text
local_reports/body-table-geometry-delta-safety-report.md
```

The report was not staged or committed. The local sample PDF, layout report, review pack, filtered parse report, table delta report, root-cause report, and generated geometry safety report remained ignored.

### Sample summary

- Changed body table geometry count: 8.
- Harmless bbox-only shift count: 0.
- Stream-table boundary adjustment count: 8.
- Possible body table structure change count: 0.
- Possible cell loss count: 0.
- Unchanged row/column/cell count: 8.
- Changed row/column/cell count: 0.
- Text/cell signature preserved count: 8.
- Text/cell signature changed count: 0.
- Unsafe count: 0.
- Review count: 8.
- Safe count: 0.
- Affected pages: 5, 8, and 10.
- Classification: `review`.

Interpretation:

- The 8 changed body table geometries no longer look like body table loss.
- Row count, column count, cell count, and cell text signatures were preserved for all 8 changed body tables.
- The remaining changes are best treated as stream-table boundary adjustments, not as safe production behavior yet.
- Because severity remains `review`, Phase 2T should stay internal, explicitly opt-in, and guarded.

Safety warnings:

- None from the Phase 2S helper.

### Tests added

- Bbox-only shift with unchanged rows, columns, cells, and text is classified as harmless/review-safe.
- Row count change triggers unsafe.
- Column count change triggers unsafe.
- Cell count change triggers unsafe.
- Cell text signature change triggers unsafe.
- Bbox edge shift near an approved removed candidate is detected.
- Body-intersecting bbox shrink without text/cell loss is classified as review.
- Insufficient evidence remains review.
- Input baseline/filtered parse outputs are not mutated.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 161 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 161 tests ran successfully.

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

### Phase 2T recommendation

Phase 2T is safe to attempt only as another internal, explicitly opt-in, guarded diagnostic phase. It should not be production integration yet; the 8 body table geometry changes are structurally preserved but still review-level stream-table boundary adjustments.

## Phase 2T

Date: 2026-06-01

### Scope

Phase 2T added an internal/local-only table geometry visual review pack helper. The helper turns Phase 2S changed body table geometry findings into JSON-serializable review items with baseline/filtered bbox data, row/column/cell counts, preserved signature indicators, likely cause, current severity, local visual artifact metadata, and blank human decision fields.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering remains opt-in and non-default.
- No production body filtering was enabled.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.

### Local review pack

Generated ignored local-only files:

```text
local_reports/table-geometry-visual-review.md
local_reports/table-geometry-review-data.json
local_reports/table_geometry_review/
```

The local sample PDF, source reports, generated review pack, JSON data, and review images remained ignored and were not staged or committed.

### Sample summary

- Visual review item count: 8.
- Affected pages: 5, 8, and 10.
- Row/column/cell count preservation: 8 of 8.
- Text/cell signature preservation: 8 of 8.
- Items requiring human approval: 8.
- Generated visual artifacts: 8 crop images.
- Automatically unsafe items: 0.
- Review classification: 8 `likely_safe_but_needs_human_approval`.

Interpretation:

- The 8 body table geometry changes are structurally preserved, but still require human visual approval.
- The local review markdown includes blank decision fields: `approve_safe_boundary_shift`, `reject_unsafe_table_change`, and `unsure`.
- The rendered crops label baseline table bbox, filtered table bbox, and nearest approved removed header/footer/page-number candidate.
- Phase 2U should remain blocked until the local visual review pack is manually reviewed.

### Tests added

- Visual review pack includes all changed table geometry items.
- Each review item includes baseline/filtered bbox and row/column/cell counts.
- Each review item includes human decision fields.
- Preserved row/column/cell/text signatures are marked as likely safe but still requiring human approval.
- Unsafe synthetic geometry changes are marked unsafe.
- Missing visual rendering support is reported clearly.
- Input reports are not mutated.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 167 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 167 tests ran successfully.

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

Result: confirmed local PDF/report/review image files, `.venv/`, generated caches, and conversion test outputs remain ignored. No local sample, generated report, review JSON, or review image was staged.

### Phase 2U recommendation

Phase 2U is not safe to attempt until the local visual review pack is manually reviewed. If the 8 items are explicitly marked `approve_safe_boundary_shift`, Phase 2U may remain internal, opt-in, and guarded; it still should not be production integration by default.

## Phase 2U

Date: 2026-06-01

### Scope

Phase 2U added an internal/report-only table visual approval gate. The gate parses the local table geometry visual review markdown and blocks any future filtered parse integration unless all expected changed body table geometry items are explicitly approved and structural preservation signals remain intact.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering remains opt-in and non-default.
- No production body filtering was enabled.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.

### Local gate report

Generated ignored local-only file:

```text
local_reports/table-visual-approval-gate-report.md
```

The local sample PDF, source reports, visual review markdown, visual review JSON, review images, and generated gate report remained ignored and were not staged or committed.

### Sample summary

- Expected review item count: 8.
- Parsed review item count: 8.
- `approve_safe_boundary_shift`: 8.
- `reject_unsafe_table_change`: 0.
- `unsure`: 0.
- Missing decision count: 0.
- Conflict decision count: 0.
- Row/column/cell preservation count: 8.
- Text/cell signature preservation count: 8.
- Gate status: `passed`.
- Blocking reasons: none.

Interpretation:

- The local visual approval gate passed for the 8 changed body table geometry items.
- This only removes the Phase 2T manual-review blocker for the next internal experiment.
- Production integration remains blocked by policy; Phase 2V must remain internal, opt-in, and guarded.

### Tests added

- Gate passes when all expected items are approved.
- Gate blocks when any item is rejected.
- Gate blocks when any item is unsure.
- Gate blocks when any item has a missing decision.
- Gate blocks when parsed item count does not match expected count.
- Gate blocks when row/column/cell preservation is false.
- Gate blocks when text/cell signature preservation is false.
- Local review markdown parsing is robust to whitespace.
- Input reports are not mutated.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 177 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 177 tests ran successfully.

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

Result: confirmed local PDF/report/review image files, `.venv/`, generated caches, and conversion test outputs remain ignored. No local sample, generated report, review JSON, or review image was staged.

### Phase 2V recommendation

Phase 2V is safe to attempt only as another internal, explicitly opt-in, guarded diagnostic phase. The table visual approval gate passed, but reviewed filtering must still not become default behavior and must not be connected to production conversion without another approval step.

## Phase 2V

Date: 2026-06-01

### Scope

Phase 2V added an internal/report-only filtered DOCX generation comparison helper and ran a local-only experiment that generated baseline and reviewed-filtered DOCX files under ignored paths. The filtered DOCX generation was gated by the Phase 2U table visual approval report and used only explicit `approve_exclude` header/footer/page-number review decisions.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering remains opt-in and non-default.
- No production body filtering was enabled.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.

### Local artifacts

Generated ignored local-only files:

```text
local_reports/docx_compare/baseline.docx
local_reports/docx_compare/filtered.docx
local_reports/docx_compare/normal-check.docx
local_reports/filtered-docx-generation-comparison-report.md
```

The local sample PDF, source reports, visual review files/images, generated DOCX files, and generated comparison report remained ignored and were not staged or committed.

### Sample summary

- Baseline DOCX path: `local_reports/docx_compare/baseline.docx`.
- Filtered DOCX path: `local_reports/docx_compare/filtered.docx`.
- Table visual approval gate status: `passed`.
- Baseline raw block count: 790.
- Filtered raw block count: 742.
- Removed approved header/footer/page-number count: 48.
- Baseline parsed text block count: 523.
- Filtered parsed text block count: 486.
- Baseline body TextBlock count: 393.
- Filtered body TextBlock count: 393.
- Baseline table count: 139.
- Filtered table count: 127.
- Baseline image count: 0.
- Filtered image count: 0.
- Baseline section count: 50.
- Filtered section count: 50.
- Body-region removed count: 0.
- Rejected/unsure/layout-placeholder removed count: 0.
- Baseline DOCX paragraph count: 364.
- Filtered DOCX paragraph count: 351.
- Baseline DOCX table count: 139.
- Filtered DOCX table count: 127.

DOCX file checks:

- Baseline DOCX exists and is non-empty: 280904 bytes.
- Filtered DOCX exists and is non-empty: 279079 bytes.
- Normal conversion after the experiment still works: yes.
- State restored or reloaded after the experiment: yes.

Header/footer pollution reduction:

- Removed boundary raw block count: 48.
- Removed header/footer/page-number count: 48.
- Parsed text block delta: 37.
- Body text block delta: 0.

Body serialization residual check:

- Exact removed-text residual check found 1 residual unique string out of 15 removed strings.
- This is recorded as a local diagnostic count only; no extracted text was committed.

Table delta explanation:

- The table count delta remains the known Phase 2P/2Q/2R/2S/2U delta.
- Phase 2S showed the changed body table geometry items preserve row/column/cell counts and text/cell signatures.
- Phase 2U visual approval gate passed for all 8 changed body table geometry items.

Safety warnings:

- None from the Phase 2V comparison helper.

### Tests added

- Filtered DOCX experiment requires explicit enablement.
- Filtered DOCX experiment blocks when table visual approval gate is missing.
- Filtered DOCX experiment blocks when table visual approval gate failed.
- Baseline and filtered DOCX output paths are local-only/ignored-style paths.
- Approved header/footer/page-number removal count is reported.
- Body-region removal count remains zero.
- Baseline vs filtered structural metrics are reported.
- Generated DOCX path validation reports missing/empty files clearly.
- Experiment requires restore/reload confirmation.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 184 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/common/docx.py pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 184 tests ran successfully.

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

Result: confirmed local PDF/report/review image/generated DOCX files, `.venv/`, generated caches, and conversion test outputs remain ignored. No local sample, generated report, review JSON, review image, or DOCX output was staged.

### Phase 2W recommendation

Phase 2W is safe to attempt only as another internal, explicitly opt-in, guarded diagnostic phase. The local filtered DOCX experiment produced non-empty baseline and filtered DOCX outputs, preserved body TextBlock, image, and section counts, and produced no blocking warnings; it still must not become default production behavior.

## Phase 2W

Date: 2026-06-01

### Scope

Phase 2W added an internal/report-only DOCX residual and OpenXML structure validation helper. The helper inspects baseline and filtered DOCX files as ZIP/OpenXML packages, checks `word/document.xml`, table cells, and optional header/footer XML parts, then classifies any removed-text residuals by location.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering remains opt-in and non-default.
- No production body filtering was enabled.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.

### Local report

Generated ignored local-only file:

```text
local_reports/filtered-docx-residual-structure-report.md
```

The local sample PDF, source reports, visual review files/images, generated DOCX files, and generated residual/structure report remained ignored and were not staged or committed.

### Sample summary

- Baseline DOCX body paragraph count: 364.
- Filtered DOCX body paragraph count: 351.
- Paragraph delta: -13.
- Baseline DOCX table count: 139.
- Filtered DOCX table count: 127.
- Table delta: -12.
- Baseline OpenXML section count: 69.
- Filtered OpenXML section count: 69.
- Header XML part count: 0.
- Footer XML part count: 0.
- Removed-string count inspected: 15.
- Residual removed-string count: 1.
- Residual locations: `table_cell`: 1.
- Residual classification: `legitimate_body_or_table_content`.
- True residual header/footer pollution count: 0.
- Legitimate body/table duplicate count: 1.
- Body text loss warning count: 0.
- Table text loss warning count: 0.
- Suspicious residual count: 0.
- Overall classification: `safe`.

Interpretation:

- The single residual removed string is present only in filtered DOCX table-cell content.
- It is not present in DOCX header/footer XML parts.
- It is not classified as repeated header/footer pollution in the filtered DOCX body.
- The residual is classified as legitimate body/table content and does not block the next internal diagnostic phase.

Safety warnings:

- None from the Phase 2W helper.

### Tests added

- Residual string in body paragraph is reported with body location.
- Residual string in table cell is reported with table-cell location.
- Residual string in header/footer XML is reported separately.
- Legitimate body duplicate is classified separately from true residual pollution.
- True repeated header/footer residual triggers a warning.
- Paragraph/table count deltas are reported.
- Missing DOCX file is reported clearly.
- Empty DOCX file is reported clearly.
- Generated report does not mutate DOCX files.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 193 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 193 tests ran successfully.

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

Result: confirmed local PDF/report/review image/generated DOCX files, `.venv/`, generated caches, and conversion test outputs remain ignored. No local sample, generated report, review JSON, review image, or DOCX output was staged.

### Phase 2X recommendation

Phase 2X is safe to attempt only as another internal, explicitly opt-in, guarded diagnostic phase. Phase 2W found no true residual header/footer pollution in the filtered DOCX and no blocking OpenXML structure warnings; production integration must still remain disabled by default.

## Phase 2X

Date: 2026-06-01

### Scope

Phase 2X added an internal/report-only feature-readiness gate for reviewed
header/footer filtering. The gate aggregates prior local evidence from the
review decisions, raw-object mapping, filtered parse, table visual approval,
filtered DOCX generation, DOCX residual inspection, and verification commands.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering remains opt-in and non-default.
- No production body filtering was enabled.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.

### Local report

Generated ignored local-only file:

```text
local_reports/reviewed-filtering-feature-readiness-report.md
```

The local sample PDF, local reports, visual review files/images, generated DOCX
files, `.venv/`, caches, and conversion outputs remained ignored and were not
staged or committed.

### Readiness gate summary

- Readiness gate status:
  `ready_for_internal_opt_in_integration_experiment`.
- Blocking reasons: 0.
- Non-blocking risks: 5.
- Header/footer review approvals: passed.
- Table visual approval gate: passed.
- Expected removed count: 48.
- Actual removed count: 48.
- Body-region removed count: 0.
- Rejected/unsure/layout-placeholder removed count: 0.
- Raw-object exact match count: 48.
- Raw-object ambiguous/missing/unsafe match counts: 0 / 0 / 0.
- Body TextBlock count preserved: yes.
- Image count preserved: yes.
- Section count preserved: yes.
- Known table delta approved: yes.
- Baseline and filtered DOCX files: present and non-empty.
- True residual header/footer pollution count: 0.
- Body text loss warnings: 0.
- Table text loss warnings: 0.

Non-blocking risks:

- Evidence still depends on ignored local sample artifacts.
- Synthetic fixtures are planned but not yet committed.
- No committed end-to-end regression fixture exists yet.
- Production default integration remains disabled.
- Public CLI behavior remains disabled.

Synthetic fixtures were only planned in Phase 2X. No synthetic PDFs or generated
fixtures were added or committed.

### Planning document

Added `docs/agent/reviewed-filtering-integration-readiness.md` with:

- validated evidence summary,
- local-only limitations,
- reasons production default integration remains blocked,
- required synthetic fixture coverage,
- recommended Phase 2Y direction.

No extracted sample text or copyrighted content was added to committed
documentation.

### Tests added

- Readiness gate passes when all required evidence is safe.
- Readiness gate blocks when header/footer approval is missing.
- Readiness gate blocks when the table visual approval gate is missing or
  failed.
- Readiness gate blocks when body-region removal is nonzero.
- Readiness gate blocks when true residual header/footer pollution is nonzero.
- Readiness gate blocks when body text loss warnings are nonzero.
- Readiness gate blocks when table text loss warnings are nonzero.
- Readiness gate records local-sample dependency as a non-blocking risk.
- Readiness report does not mutate input reports.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 203 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 203 tests ran successfully.

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

Result: confirmed local PDF/report/review image/generated DOCX files, `.venv/`,
generated caches, and conversion test outputs remain ignored. No local sample,
generated report, review JSON, review image, or DOCX output was staged.

### Phase 2Y recommendation

Phase 2Y is safe to attempt only as another internal, explicitly opt-in,
non-default phase. The recommended direction is to create committed synthetic
fixture coverage or fixture-generation scaffolding first, then run the readiness
gate against safe fixtures before any production integration attempt.

## Phase 2Y0

Date: 2026-06-01

### Scope

Phase 2Y0 added an internal/local-only corpus validation summary helper and ran
analysis-only diagnostics on five additional ignored local sample PDFs. This
phase did not consume raw `would_exclude` labels as approval and did not run the
full Phase 2V/2W DOCX generation comparison for the new samples.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering remains opt-in and non-default.
- No production body filtering was enabled.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.

### Local artifacts

Generated ignored local-only reports:

```text
local_reports/corpus_validation/input2-corpus-summary.md
local_reports/corpus_validation/input3-corpus-summary.md
local_reports/corpus_validation/input4-corpus-summary.md
local_reports/corpus_validation/input5-corpus-summary.md
local_reports/corpus_validation/input6-large-corpus-summary.md
local_reports/corpus-validation-summary.md
```

Local-only review packs were also generated under
`local_reports/corpus_validation/`. They contain no approvals; every candidate
remains for possible manual review only.

The local sample PDFs and generated reports/review packs remained ignored and
were not staged or committed.

### Corpus summary

- Sample count: 5.
- Samples analyzed successfully: 5.
- Samples failed analysis: 0.
- Samples skipped or partially analyzed: 1.
- Samples with likely valid header/footer candidates: 2.
- Samples with suspicious body-region candidates: 0.
- Samples needing manual review: 2.
- Samples too large for full pipeline: 1.

Per-sample analysis:

- `input2.pdf`: 18/18 pages analyzed, 371 blocks, 3 repeated candidates, 0
  would-exclude candidates, warnings: none.
- `input3.pdf`: 5/5 pages analyzed, 150 blocks, 5 repeated candidates, 1
  would-exclude candidate, estimated 5 would-remove blocks, warnings: none.
- `input4.pdf`: 4/4 pages analyzed, 68 blocks, 1 repeated placeholder
  candidate, 0 would-exclude candidates, warnings: none.
- `input5.pdf`: 21/21 pages analyzed, 593 blocks, 2 repeated candidates, 0
  would-exclude candidates, warnings: none.
- `input6_large.pdf`: 15/756 pages analyzed with bounded analysis, 678 blocks,
  3 repeated candidates, 2 would-exclude candidates, estimated 30 would-remove
  blocks, warnings: `large_sample_analysis_only`,
  `partial_or_bounded_analysis`.

Recommended for deeper local Phase 2Y1 manual review:

- `input3.pdf`
- `input6_large.pdf` using bounded review strategy first

Not recommended for deeper manual review yet:

- `input2.pdf`, `input4.pdf`, and `input5.pdf` did not produce would-exclude
  candidates in this analysis pass.

### Tests added

- Corpus summary builder handles multiple sample results.
- Failed sample analysis is reported clearly.
- Large sample is marked analysis-only/bounded unless explicitly allowed.
- Corpus report generation does not mutate input reports.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 208 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 208 tests ran successfully.

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

Result: confirmed local sample PDFs, local corpus reports/review packs,
`.venv/`, generated caches, and conversion test outputs remain ignored. No
local sample PDF, generated report, review pack, image, or DOCX output was
staged.

### Phase 2Y0 recommendation

Committed synthetic fixture work can proceed after this phase, but it should use
safe generated content only and should not reuse local sample text. Before any
production integration attempt, Phase 2Y1 should manually review the local
corpus candidates from `input3.pdf` and the bounded `input6_large.pdf` analysis.

## Phase 2Y1

Date: 2026-06-01

### Scope

Phase 2Y1 added internal/local-only manual review pack helpers for selected
corpus samples and generated richer review packs for the two samples Phase 2Y0
recommended for deeper review.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering remains opt-in and non-default.
- No production body filtering was enabled.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.
- No filtered parse or DOCX generation experiment was run for these corpus
  samples.

### Local artifacts

Generated ignored local-only review files:

```text
local_reports/corpus_validation/input3-header-footer-review.md
local_reports/corpus_validation/input6-large-header-footer-review.md
local_reports/corpus-manual-review-summary.md
```

The local sample PDFs, Phase 2Y0 corpus reports, Phase 2Y1 review packs, `.venv/`,
generated caches, and conversion outputs remained ignored and were not staged or
committed.

### Selected samples

- `input3.pdf`
- `input6_large.pdf`

`input6_large.pdf` was processed with bounded analysis only. The analyzed page
numbers were:

- 1-5
- 377-381
- 752-756

No subset PDFs were created.

### Manual review pack summary

Overall:

- Selected sample count: 2.
- Review packs ready for human approval: 2.
- Total candidate count: 8.
- Total would-exclude candidate count: 3.
- Total would-remove block count: 35.
- Manual approval required count: 2.
- Auto-approved decision count: 0.

Per selected sample:

- `input3.pdf`: 5 candidates, 1 would-exclude candidate, 5 would-remove blocks,
  4 review-only candidates, 1 cautious candidate, 1 placeholder candidate,
  warnings: none, recommended next action:
  `manual_approve_then_full_local_pipeline`.
- `input6_large.pdf`: 3 candidates, 2 would-exclude candidates, 30
  would-remove blocks in the bounded subset, 1 review-only candidate, 0 cautious
  candidates, 0 placeholder candidates, warnings:
  `bounded_large_sample_review`, recommended next action:
  `analysis_only_large_sample`.

Manual approval is required before Phase 2Y2. No candidate was approved or
applied in Phase 2Y1.

### Tests added

- Manual review summary builder handles multiple selected samples.
- Selected samples with candidates are marked ready for manual review.
- Large sample is marked bounded-analysis-only.
- No auto-approval is created.
- Missing review pack/report is reported clearly.
- Local review pack generation does not mutate inputs.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 215 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 215 tests ran successfully.

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

Result: confirmed local sample PDFs, generated review packs/reports, `.venv/`,
generated caches, and conversion test outputs remain ignored. No local sample
PDF, generated report, review pack, image, or DOCX output was staged.

### Phase 2Y2 recommendation

Phase 2Y2 should remain local-only and should consume only explicit human
decisions from the Phase 2Y1 review packs. `input3.pdf` may proceed to a local
manual-approval-driven pipeline only after review decisions are filled in.
`input6_large.pdf` should remain bounded until a later explicit approval allows
larger or full-document processing.

## Phase 2Y2

Date: 2026-06-01

### Scope

Phase 2Y2 consumed explicit human decisions from the local-only corpus review
packs and ran approved-only local validation for the selected corpus samples.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering remains opt-in and non-default.
- No production body filtering was enabled.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.

### Local artifacts

Generated ignored local-only reports:

```text
local_reports/corpus_validation/input3-approved-filtering-validation-report.md
local_reports/corpus_validation/input3-filtered-docx-validation-report.md
local_reports/corpus_validation/input6-large-bounded-approved-validation-report.md
local_reports/corpus-approval-validation-summary.md
```

Generated ignored local-only DOCX comparison files for `input3.pdf`:

```text
local_reports/corpus_validation/input3_docx_compare/baseline.docx
local_reports/corpus_validation/input3_docx_compare/filtered.docx
local_reports/corpus_validation/input3_docx_compare/normal-check.docx
```

The local sample PDFs, subset paths, generated reports, generated DOCX files,
`.venv/`, generated caches, and conversion test outputs remained ignored and
were not staged or committed.

### Approval counts

`input3.pdf`:

- Candidate count: 5.
- Explicit decisions: 5.
- `approve_exclude`: 3.
- `reject_exclude`: 0.
- `unsure`: 2.
- Missing/conflicting decisions: 0.
- Eligible approved filtering candidates: 1.
- Blocked candidates: 4.
- Approved removed blocks: 5.
- Body-region removed count: 0.
- Rejected/unsure/layout-placeholder removed count: 0.

`input6_large.pdf` bounded subset:

- Candidate count: 3.
- Explicit decisions: 3.
- `approve_exclude`: 3.
- `reject_exclude`: 0.
- `unsure`: 0.
- Missing/conflicting decisions: 0.
- Eligible approved filtering candidates: 2.
- Blocked candidates: 1.
- Approved removed blocks: 30.
- Body-region removed count: 0.
- Rejected/unsure/layout-placeholder removed count: 0.

### Input3 deeper validation

`input3.pdf` ran the full local-only manual-approval-driven validation path:

- Document-parse simulation/mapping/copy/guarded/filtered-parse checks ran.
- Raw-object mapping exact matches: 5.
- Ambiguous/missing mapping matches: 0 / 0.
- Copied apply removed blocks: 5.
- Guarded apply/restore removed blocks: 5.
- Filtered parse removed blocks: 5.
- Body-region removed count: 0.
- Generated baseline and filtered DOCX files in ignored local paths.
- Residual removed string count in filtered DOCX: 0.
- True residual header/footer pollution count: 0.
- Body text loss warnings from residual inspection: 0.
- Table text loss warnings from residual inspection: 0.
- Safety warning: `body_text_block_count_changed`.

Because the filtered DOCX comparison showed a body TextBlock count delta, this
sample is useful evidence but not production-integration approval.

### Input6 large bounded validation

`input6_large.pdf` remained bounded-subset only:

- Pages analyzed: 15 of 756.
- Full-document filtered parse was skipped.
- Full-document DOCX generation was skipped.
- Raw-object mapping exact matches on the bounded subset: 30.
- Ambiguous/missing mapping matches: 0 / 0.
- Copied apply removed blocks on the bounded subset: 30.
- Body-region removed count: 0.
- Rejected/unsure/layout-placeholder removed count: 0.
- Warning: full large-document DOCX validation remains blocked.

### Tests added

- Approval validation passes when all candidates have explicit decisions.
- Approval validation blocks missing decisions.
- Approval validation reports `unsure` candidates without applying them.
- Only approved eligible candidates are removed.
- Rejected candidates remain blocked.
- Bounded large samples cannot run full DOCX validation by default.
- Local corpus validation reports do not mutate inputs.
- Disabled/default behavior remains unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 223 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 223 tests ran successfully.

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

Result: confirmed local sample PDFs, generated reports, generated DOCX files,
`.venv/`, generated caches, and conversion test outputs remain ignored.

### Phase 2Y2 recommendation

Committed synthetic fixture work should proceed next, using only safe generated
documents. Production integration should remain blocked until the synthetic
fixtures cover the approval flow and the `input3.pdf` body TextBlock delta has a
committed regression analogue or a follow-up explanation.

## Phase 2Z

Date: 2026-06-01

### Scope

Phase 2Z added committed synthetic regression coverage for reviewed
header/footer filtering. The tests generate small PDFs at runtime with PyMuPDF
in temporary directories and use only artificial test text.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- Reviewed filtering remains opt-in and non-default.
- No production body filtering was enabled.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.

### Synthetic fixture strategy

- Synthetic PDFs are generated during tests using existing PyMuPDF/`fitz`
  support.
- Generated PDF binaries are temporary and are not committed.
- The tests reuse internal layout-analysis/report helpers and internal
  document-parse diagnostic hooks.
- Heavy DOCX comparison is not run for every synthetic case; tests focus on
  layout analysis, dry-run reviewed filtering, raw-object mapping, copied or
  guarded diagnostics, and body text signature preservation.

### Committed scenarios covered

- Repeated text header, footer, and page numbers.
- Body table-like content near a footer.
- No-header/no-footer negative control.
- Raw `would_exclude` without explicit approval.
- First-page different header plus odd/even header variation.
- Hyphenated paragraph continuation across a page break.

### Validation results

Synthetic repeated header/footer/page-number fixture:

- Detected top/bottom/page-number candidates.
- Explicitly approved candidates removed 12 synthetic boundary objects in the
  internal report/guarded path.
- Body-region removed count: 0.
- Raw-object mapping exact matches: 12.
- Guarded apply/restore restored the original raw-page fingerprint.

Synthetic body table-like content near footer:

- Approved footer/page-number filtering removed only boundary artifacts.
- Body-region removed count: 0.
- Body table-like text remained in the filtered body signature.

Synthetic no-header/no-footer negative control:

- No removable candidates were produced.
- A separate repeated-boundary fixture confirmed raw `would_exclude` labels
  remove nothing without explicit approval.

Synthetic first-page/odd-even variation:

- Repeated odd/even headers were low-support/review-gated.
- No approved removal occurred from approving review-only top-region candidates.

Synthetic paragraph continuity:

- Cross-page continuation candidate was reported.
- Approved header/footer filtering removed no body-region text.
- Body text signature was preserved.
- A simulated body TextBlock count delta is classified as
  `acceptable_boundary_or_grouping_shift` when the text signature is preserved.

### Remaining gaps

- Callout/text-box content that looks table-like is not yet covered by committed
  synthetic tests.
- List item and heading boundary interactions are not yet covered by committed
  synthetic tests.
- Synthetic filtered DOCX residual comparison is still local/manual rather than
  committed.
- Synthetic true table geometry delta coverage remains to be added before
  production integration.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 228 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 228 tests ran successfully.

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

Result: confirmed local sample PDFs, generated local reports, `.venv/`,
generated caches, and conversion test outputs remain ignored. No generated PDF
fixture binary was committed; synthetic PDFs were created only in temporary test
directories.

Generated ignored local-only report:

```text
local_reports/synthetic-fixture-regression-report.md
```

### Phase 2Z recommendation

Production integration should remain blocked. The next phase should add the
remaining synthetic fixture coverage for callout/text-box content, list/heading
boundaries, and synthetic table geometry/DOCX residual behavior before any
default or public opt-in integration is attempted.

## Phase 3A

Date: 2026-06-01

### Scope

Phase 3A added a minimal internal opt-in configuration scaffold for reviewed
header/footer filtering experiments. The scaffold is report/config only and does
not enable production filtering.

Production conversion behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public CLI flag was added.
- Reviewed filtering remains disabled by default.
- No production body filtering was enabled.
- No table parsing behavior was changed.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.

### Internal config fields

Default internal config values:

- `enabled`: `False`
- `mode`: `dry_run`
- `review_decisions_path`: empty
- `review_decisions`: `None`
- `require_explicit_approval`: `True`
- `allow_raw_would_exclude`: `False`
- `allow_unsure`: `False`
- `allow_rejected`: `False`
- `protect_body_region`: `True`
- `protect_layout_placeholders`: `True`
- `collect_diagnostics`: `True`
- `write_local_reports`: `False`
- `max_pages`: `None`
- `page_subset`: empty list
- `fail_closed_on_warning`: `True`

Supported internal modes:

- `dry_run`
- `simulation`
- `guarded_apply_restore`
- `filtered_parse_experiment`
- `future_apply`

`future_apply` is still blocked because permanent production filtering is not
implemented.

### Fail-closed behavior

The config report blocks internal experiments when:

- the config is missing or disabled
- review decisions are missing
- raw `would_exclude` candidates do not have explicit approval
- rejected or unsure decisions are present and protected
- body-region candidates are encountered while body protection is enabled
- layout placeholders are encountered while placeholder protection is enabled
- `future_apply` is requested

The scaffold can produce JSON-serializable diagnostics and translate a ready
internal config into existing private `Pages` diagnostic settings. It does not
connect to public CLI behavior and does not make filtering default-on.

### Tests added

- Default config disables reviewed filtering.
- Missing config preserves disabled behavior.
- `enabled=False` preserves disabled behavior.
- Enabled config without review decisions is blocked.
- Raw `would_exclude` without approval is blocked.
- Rejected and unsure decisions remain blocked.
- Body-region candidates remain protected.
- Layout-placeholder candidates remain protected.
- Config summaries are JSON-serializable.
- Public/default conversion settings remain unchanged.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 238 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 238 tests ran successfully.

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

Result: confirmed local sample PDFs, generated local reports, `.venv/`,
generated caches, and conversion test outputs remain ignored.

### Phase 3A recommendation

Phase 3B should remain internal and non-default. The next safe step is to use
the config scaffold to drive one narrow guarded diagnostic path in tests or local
experiments, while keeping public CLI/API exposure and production default
integration blocked.

## Phase 3B

Date: 2026-06-02

### Scope

Phase 3B connected the Phase 3A private internal config scaffold to an
explicitly opt-in filtered parse integration path at the `document_parse`
insertion point.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains disabled unless a private underscored config is
  supplied.
- No DOCX header/footer generation was added.
- No production paragraph merge was added.
- No production table parsing behavior was changed.

### Internal integration behavior

Config mode used in tests:

- `filtered_parse_experiment`

The private integration path now:

- requires `enabled=True`
- requires `activation_status=ready_for_internal_experiment`
- requires explicit `approve_exclude` review decisions
- blocks raw `would_exclude` without approval
- blocks missing review decisions
- blocks fail-closed rejected/unsure decisions
- protects body-region candidates
- protects layout-placeholder candidates
- runs existing dry-run, mapping, copied-apply, guarded-restore, and filtered
  parse diagnostics before applying
- applies reviewed filtering only to the current internal parse input when the
  config is ready
- records approval/removal counts and parse diagnostics

Synthetic fixture integration result:

- Approved repeated header/footer/page-number synthetic fixture applied
  internally through `Pages.parse()`.
- Removed approved raw blocks matched the reviewed filtering report count.
- Body-region removed count stayed at 0.
- Rejected/unsure/layout-placeholder removed count stayed at 0.
- Body text signature was preserved.
- Body TextBlock count deltas are recorded as diagnostics rather than silently
  accepted.
- Unsafe warning types still block through fail-closed behavior.

No local Phase 3B report was generated. Existing local sample PDFs, local
reports, review images, and generated DOCX files remained ignored.

### Tests added

- Missing config leaves the internal integration report unset.
- `enabled=False` stores diagnostics but does not apply filtering.
- Enabled config without review decisions blocks integration.
- Raw `would_exclude` without manual approval blocks integration.
- Approved synthetic review decisions run the internal filtered parse path.
- Fail-closed rejected/unsure decisions block integration.
- Body TextBlock count changes are reported with signature-preservation context.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "internal_config"
```

Result: passed. 9 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
git diff --check
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 245 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 245 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

```bash
git status --short --ignored
```

Result: only Phase 3B code/test/docs files were modified. Local sample PDFs,
generated local reports, `.venv/`, caches, and test outputs remained ignored.

### Phase 3B recommendation

Phase 3C should remain internal and non-default. The next direction should be
additional synthetic coverage for callout/text-box, list/heading, and synthetic
table-geometry cases before any public opt-in or production-default integration
is considered.

## Phase 3C

Date: 2026-06-02

### Scope

Phase 3C added internal test-only filtered DOCX generation comparison support
for synthetic fixtures. It validates that the Phase 3B private filtered parse
integration can flow through existing DOCX generation without changing default
conversion behavior.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- No Word section header/footer parts were generated.
- No content was moved into DOCX headers/footers.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Synthetic fixtures used

- `repeated_header_footer`
- `body_table_near_footer`
- `no_header_footer`

The DOCX comparison helper writes baseline, filtered, and post-experiment
default DOCX files only under temporary test directories.

Repeated header/footer/page-number fixture:

- Baseline vs filtered DOCX paragraphs: 27 / 15
- Baseline vs filtered DOCX tables: 0 / 0
- Removed approved header/footer/page-number count: 12
- True residual header/footer pollution count: 0
- Body text signature preserved: yes
- Body text loss warnings: 0
- Table text loss warnings: 0

Body table-like content near footer fixture:

- Baseline vs filtered DOCX paragraphs: 14 / 11
- Baseline vs filtered DOCX tables: 3 / 3
- Removed approved header/footer/page-number count: 6
- True residual header/footer pollution count: 0
- Body text signature preserved: yes
- Body table-like text preserved: yes
- Body text loss warnings: 0
- Table text loss warnings: 0

Negative/control behavior:

- No-header/no-footer content remained preserved.
- Raw `would_exclude` without approval removed nothing.
- Rejected/unsure decisions stayed blocked by fail-closed behavior.
- Body TextBlock count deltas are surfaced as diagnostics and are acceptable
  only when body text signature is preserved.
- Synthetic unsafe body text loss triggers fail-closed warnings.

No local Phase 3C report was generated. Generated DOCX files were temporary
test artifacts only and were not committed.

### Tests added

- Baseline and filtered DOCX generation comparison for repeated header/footer.
- Internal filtered DOCX generation requires explicit ready private config.
- Approved residual header/footer/page-number text is removed from body output.
- Body-region text signature remains preserved.
- Body table-like text near a footer remains preserved.
- No-header/no-footer negative control preserves body content.
- Raw `would_exclude` without approval removes nothing.
- Rejected/unsure decisions remain blocked.
- Unsafe body text loss fails closed.
- Generated DOCX paths are temp-only.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "filtered_docx"
```

Result: passed. 21 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 251 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 251 tests ran successfully.

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

Result: only Phase 3C test/docs files were modified. Local sample PDFs,
generated local reports, `.venv/`, caches, and test outputs remained ignored.
Synthetic DOCX outputs were generated only under temporary test directories.

### Phase 3C recommendation

Phase 3D should remain internal and non-default. The next useful direction is
to add synthetic coverage for callout/text-box, list/heading, and synthetic
table-geometry delta scenarios before any public opt-in or production-default
integration is considered.

## Phase 3D

Date: 2026-06-02

### Scope

Phase 3D added local-corpus DOCX smoke summary support for the private reviewed
filtering config path and generated an ignored local report for approved local
samples. This remains internal, explicitly opt-in, and non-default.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- No Word section header/footer parts were generated.
- No content was moved into DOCX headers/footers.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Local corpus smoke results

The ignored local report was generated at
`local_reports/phase3d-local-corpus-docx-smoke-report.md`.

Evaluated samples:

- `input.pdf`: passed.
- `input3.pdf`: passed.
- `input6_large.pdf`: bounded subset passed; full 756-page validation was not
  run.

Generated DOCX artifacts stayed under ignored `local_reports/phase3d/` paths.
The bounded large-document subset stayed under ignored `local_samples/subsets/`.

Summary:

- Sample count: 3.
- Passed count: 2.
- Bounded-subset passed count: 1.
- Blocked count: 0.
- Total approved header/footer/page-number removals: 83.
- True residual header/footer pollution count: 0.
- Body text loss warning count: 0.
- Table text loss warning count: 0.

Per-sample DOCX metrics:

- `input.pdf`: paragraphs 364 / 351, tables 139 / 127, removed approved blocks
  48.
- `input3.pdf`: paragraphs 49 / 43, tables 16 / 13, removed approved blocks 5.
- `input6_large.pdf` bounded subset: paragraphs 177 / 159, tables 10 / 10,
  removed approved blocks 30.

Body text signature preservation:

- `input.pdf`: preserved.
- `input3.pdf`: preserved.
- `input6_large.pdf` bounded subset: preserved.

Diagnostic deltas:

- `input.pdf`: DOCX table count delta -12, classified as reported with no
  table text loss.
- `input3.pdf`: body TextBlock delta -1 and DOCX table count delta -3,
  classified as acceptable diagnostics because body/table text loss warnings
  were zero.
- `input6_large.pdf` bounded subset: body TextBlock delta -1, classified as an
  acceptable diagnostic because body text signature was preserved.

Fail-closed warning behavior remained active for true residual header/footer
pollution, body text loss, table text loss, missing approval artifacts, missing
DOCX outputs, and non-local generated DOCX paths.

### Tests added

- Local corpus smoke summary builder handles multiple samples.
- Missing approval artifacts block a sample clearly.
- Large samples remain bounded-subset-only.
- Body text signature preservation is required.
- True residual header/footer pollution, body text loss, and table text loss
  fail closed.
- Body TextBlock count delta is reported as a diagnostic.
- Generated DOCX paths must be temporary or ignored local paths.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 258 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 258 tests ran successfully.

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

Result: local sample PDFs, generated local reports, generated DOCX files,
`.venv/`, caches, and test outputs remained ignored. Only Phase 3D code/test
and documentation files were staged for commit.

### Phase 3D recommendation

Phase 3E should remain internal and non-default. The next useful direction is
to broaden committed synthetic coverage for callout/text-box content,
list/heading boundaries, and table-geometry delta scenarios before any public
opt-in or production-default integration is considered.

## Phase 3E

Date: 2026-06-02

### Scope

Phase 3E broadened committed synthetic regression coverage for the remaining
thin reviewed-filtering scenarios before any DOCX header/footer part generation
or public opt-in design.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- No Word section header/footer parts were generated.
- No content was moved into DOCX headers/footers.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Synthetic scenarios added

Generated PDF scenarios added to the committed test helper:

- `callout_text_box_near_edges`
- `list_heading_boundaries`
- `table_geometry_delta_stress`
- `odd_even_body_heading_interaction`

The generated PDFs and DOCX files are created only in temporary test
directories and are not committed.

### Synthetic results

Callout/text-box preservation:

- Body callout text remained present after approved header/footer/page-number
  filtering.
- Table-like callout row text remained present.
- No callout body text was removed as header/footer content.
- Body text signature was preserved.

List/heading preservation:

- Body headings remained present after approved filtering.
- Bullet-list and numbered-list text remained present.
- Heading/list boundaries were not treated as removable header/footer content.
- Body text signature was preserved.

Synthetic table-geometry stress:

- Body table text remained present after approved footer/page-number filtering.
- Table text signature was preserved.
- Table count deltas are reported through diagnostics and classified as
  non-blocking only when table text loss is zero.
- Synthetic table text loss now triggers fail-closed warnings.

First-page/odd-even interaction:

- Varied first-page and odd/even header candidates remain review-gated.
- Body headings that resemble header text were not removed.
- Body text signature was preserved.

Fail-closed behavior:

- Body text loss remains unsafe.
- Table text loss remains unsafe.
- True residual header/footer pollution remains unsafe.
- Raw `would_exclude` without explicit approval still removes nothing.
- Rejected and unsure decisions remain blocked.
- Body-region and layout-placeholder candidates remain protected.

No Phase 3E local report was generated; all synthetic artifacts were temporary
test outputs only.

### Tests added

- Filtered DOCX comparison preserves callout/text-box body content.
- Filtered DOCX comparison preserves heading, bullet-list, and numbered-list
  content.
- Filtered DOCX comparison preserves table text signature under a synthetic
  table-geometry stress fixture.
- Table count delta with preserved table text signature is reported as a
  diagnostic.
- Table text loss fails closed.
- Odd/even body-heading interaction remains review-gated and preserves body
  text.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "callout or list_items or table_geometry or odd_even_body or table_count_delta or table_text_loss"
```

Result: passed. 24 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 264 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 264 tests ran successfully.

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

Result: local sample PDFs, generated local reports, generated DOCX files,
`.venv/`, caches, and test outputs remained ignored. Only Phase 3E test/docs
files were modified.

### Phase 3E recommendation

Phase 4A can start only as another internal/private design step for DOCX
header/footer part generation. Keep default conversion unchanged and keep
public CLI/API closed until header/footer part generation has its own tests and
approval gate.

## Phase 4A

Date: 2026-06-02

### Scope

Phase 4A added a minimal internal foundation for future DOCX header/footer part
generation from reviewed header/footer candidates. This remains internal,
disabled by default, and not wired into normal conversion.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content was moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Helper/design added

- `build_docx_header_footer_generation_plan()` in `LayoutAnalyzer.py` builds a
  JSON-serializable, plan-only representation of reviewed candidates.
- The plan includes simple semantic header text, simple semantic footer text,
  and page-number placeholders.
- Rejected and unsure decisions are not included.
- Layout-placeholder candidates are not represented as semantic header/footer
  text.
- Body-region candidates fail closed and are not represented.
- Page-number field generation is deferred and represented as
  `<PAGE_NUMBER>` placeholder text only.
- Section scope is document-level only.
- First-page and odd/even behavior are deferred.
- Images/logos and complex layout remain out of scope.

`apply_header_footer_text_plan()` in `pdf2docx/common/docx.py` can write the
simple internal plan to a provided `python-docx` `Document` object only when
explicitly enabled. It is not called by `Converter.convert()`.

### Temp DOCX validation

A focused test created a temporary DOCX with `python-docx`, applied the simple
internal header/footer text plan, saved the file under a temporary directory,
and inspected the resulting ZIP/OpenXML package.

Result:

- `word/header1.xml` was present.
- `word/footer1.xml` was present.
- Planned header text was present in the header part.
- Planned footer text was present in the footer part.
- Page-number placeholder text was present in the footer part.
- Real Word page-number field generation was not implemented.

No Phase 4A local report was generated; generated DOCX files were temporary
test outputs only.

### Tests added

- Header/footer generation plan is JSON-serializable.
- Reviewed header/footer/page-number candidates summarize into a simple plan.
- Rejected and unsure candidates are not included in the plan.
- Layout-placeholder candidates are not represented as semantic text.
- Body-region candidates are not represented and fail closed.
- Simple temp DOCX header/footer writing works with `python-docx`.
- Generated temp DOCX header/footer XML can be inspected.
- Header/footer text application is disabled by default.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "docx_header_footer or header_footer_text_plan"
```

Result: passed. 5 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 269 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/common/docx.py pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 269 tests ran successfully.

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

Result: local sample PDFs, generated local reports, generated DOCX files,
`.venv/`, caches, and test outputs remained ignored. Only Phase 4A code/test
and documentation files were modified.

### Phase 4A recommendation

Phase 4B should remain internal and private. The next safe direction is to
prototype how an explicitly enabled DOCX generation experiment can consume the
header/footer plan while keeping default conversion and public CLI/API behavior
unchanged.

## Phase 4B

Date: 2026-06-02

### Scope

Phase 4B added committed synthetic coverage for an internal combined
experiment: reviewed filtering removes approved repeated boundary content from
the DOCX body, then the Phase 4A simple text plan writer places approved
header/footer content into DOCX header/footer parts.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Synthetic fixtures used

- `repeated_header_footer`
- `callout_text_box_near_edges`

### Header/footer output validation

The repeated header/footer fixture generated a temporary filtered DOCX, then
explicitly applied the simple DOCX header/footer plan.

Result:

- Header/footer plan generation succeeded.
- Planned header text count: 1.
- Planned footer text count: 1.
- Planned page-number placeholder count: 1.
- `word/header*.xml` contained the approved header text.
- `word/footer*.xml` contained the approved footer text.
- `word/footer*.xml` contained the diagnostic `<PAGE_NUMBER>` placeholder.
- `word/document.xml` did not contain the approved repeated header/footer body
  residuals.
- Body residual header/footer pollution count: 0.
- Body text signature was preserved.

Page-number behavior remains placeholder-only. Real Word page-number field
generation was deferred.

### Protection and fail-closed behavior

- Rejected and unsure candidates were not written to header/footer parts.
- Layout-placeholder candidates were not written to header/footer parts.
- Body-region candidates were not written to header/footer parts.
- Unsafe header/footer plans now fail closed in
  `apply_header_footer_text_plan()` instead of partially applying safe-looking
  entries.
- Callout/table-like body content remained in `word/document.xml` and did not
  appear in DOCX header/footer XML.

No Phase 4B local report was generated; generated DOCX files were temporary
test outputs only.

### Tests added

- Combined internal filtered body + DOCX header/footer generation works on a
  synthetic repeated header/footer fixture.
- DOCX header XML contains approved header text.
- DOCX footer XML contains approved footer text and page-number placeholder.
- DOCX body XML no longer contains approved repeated header/footer residuals.
- Body text signature is preserved.
- Body callout/table-like content is preserved in the body.
- Rejected, unsure, layout-placeholder, and body-region candidates do not
  appear in DOCX header/footer parts.
- Unsafe plans fail closed before writing header/footer parts.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "docx_header_footer or header_footer_text_plan or filtered_body_docx_header_footer_output"
```

Result: passed. 8 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 272 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 272 tests ran successfully.

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

Result: local sample PDFs, generated local reports, generated DOCX files,
`.venv/`, caches, and test outputs remained ignored. Only Phase 4B code/test
and documentation files were modified.

### Phase 4B recommendation

Phase 4C should remain internal and private. The next safe direction is either
to broaden the simple text header/footer experiment across more committed
synthetic scenarios or to design the next private section/page-number
experiment while keeping default conversion and public CLI/API behavior closed.

## Phase 4C

Date: 2026-06-02

### Scope

Phase 4C added an internal DOCX header/footer policy layer for classifying
review-approved header/footer candidates before any future section-aware DOCX
writing. This remains internal, diagnostic, and disabled by default.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Policy types supported

The internal plan now includes `header_footer_policy` with these conservative
classifications:

- `default`
- `first_page`
- `odd_even`
- `section_scoped`
- `unsupported`

Classification results from committed synthetic tests:

- Default repeated candidates classified as `default`.
- First-page-different candidates classified as `first_page`.
- Odd/even alternating candidates classified as `odd_even`.
- Contiguous page-range candidates classified as `section_scoped`.
- Ambiguous patterns classified as `unsupported`.

Only `default` is safe for the current simple internal writer. `first_page`,
`odd_even`, `section_scoped`, and `unsupported` policies fail closed before
DOCX writing.

### Protection and limitations

- Rejected and unsure candidates do not enter semantic header/footer policies.
- Raw `would_exclude` without approval does not enter the policy.
- Body-region candidates are excluded and fail closed.
- Layout-placeholder candidates are excluded from semantic policy.
- Page-number behavior remains `placeholder_only`.
- Robust Word page-number field generation was not implemented.
- Actual first-page/odd-even temp DOCX writing was deferred.
- Production section-specific mapping remains future work.
- Images/logos, complex layout, and paragraph continuation remain future work.

No Phase 4C local report was generated; no local DOCX artifacts were generated
outside test temporary directories.

### Tests added

- Default repeated header/footer candidates produce a `default` policy.
- First-page-different candidates produce a `first_page` policy.
- Odd/even candidates produce an `odd_even` policy.
- Contiguous page-range candidates produce a `section_scoped` policy.
- Ambiguous candidates produce an `unsupported` policy.
- Rejected, unsure, raw, body-region, and layout-placeholder candidates are
  excluded from semantic policies.
- Unsupported policies fail closed before DOCX writing.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "header_footer_policy or docx_header_footer_generation_plan or header_footer_text_plan or filtered_body_docx_header_footer_output"
```

Result: passed. 13 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 279 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 279 tests ran successfully.

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

Result: local sample PDFs, generated local reports, generated DOCX files,
`.venv/`, caches, and test outputs remained ignored. Only Phase 4C code/test
and documentation files were modified.

### Phase 4C recommendation

Phase 4D should remain internal and private. The next safe direction is to
prototype first-page or odd/even DOCX writing only in temporary synthetic tests,
or to improve section-aware diagnostics further before any production
integration is considered.

## Phase 4D

Date: 2026-06-03

### Scope

Phase 4D added an internal single-section `default` policy migration smoke
helper and tests. This remains test-only and does not wire header/footer
generation into normal conversion.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Synthetic fixtures used

- `repeated_header_footer`
- `callout_text_box_near_edges`

### Default policy migration smoke result

The smoke helper generated temporary baseline/default-after/filtered DOCX files
from the repeated-header synthetic fixture, applied only explicit review
approvals, required the plan policy to be `default`, and then wrote the plan to
DOCX header/footer parts.

Result:

- Default policy migration smoke passed.
- DOCX body XML did not contain approved header/footer residuals.
- DOCX header XML contained the approved header text.
- DOCX footer XML contained the approved footer text.
- DOCX footer XML contained the diagnostic `<PAGE_NUMBER>` placeholder.
- Body residual header/footer pollution count: 0.
- Body text signature was preserved.
- Body text loss warning count: 0.
- Table text loss warning count: 0.
- Page-number behavior: `placeholder_only`.
- Page-number field generation: deferred placeholder only.

The callout/body-protection smoke confirmed that callout/table-like body text
remained in DOCX body XML and did not appear in DOCX header/footer XML.

### Blocked non-default policies

The writer remained fail-closed for:

- `first_page`
- `odd_even`
- `section_scoped`
- `unsupported`

Each non-default policy produced fail-closed warnings before DOCX writing. No
header/footer paragraphs were written for those policies.

No Phase 4D local report was generated; generated DOCX/PDF files were temporary
test outputs only.

### Tests added

- Default-policy migration smoke passes for a synthetic repeated
  header/footer/page-number fixture.
- Default-policy migration preserves callout/table-like body content.
- First-page policy remains blocked before DOCX writing.
- Odd/even policy remains blocked before DOCX writing.
- Section-scoped policy remains blocked before DOCX writing.
- Unsupported policy remains blocked before DOCX writing.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "default_policy_header_footer_migration_smoke or default_policy_migration or header_footer_policy or filtered_body_docx_header_footer_output"
```

Result: passed. 11 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 282 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 282 tests ran successfully.

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

Result: local sample PDFs, generated local reports, generated DOCX files,
`.venv/`, caches, and test outputs remained ignored. Only Phase 4D test and
documentation files were modified.

### Phase 4D recommendation

Phase 4E should remain internal and private. The next safe direction is to
prototype first-page or odd/even DOCX writing only in temporary synthetic tests,
or continue improving section-aware policy diagnostics before any production
integration is considered.

## Phase 4E

Date: 2026-06-03

### Scope

Phase 4E added local-only default-policy migration smoke summary support for
approved ignored local corpus samples. It does not wire DOCX header/footer
migration into normal conversion.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Local corpus result

Evaluated local-only samples:

- `input.pdf`: classified as `default`; smoke blocked by strict DOCX body
  signature validation.
- `input3.pdf`: classified as `default`; smoke blocked by strict DOCX body
  signature validation.
- `input6_large.pdf`: bounded subset only; classified as `unsupported` because
  the bounded evidence has incomplete header/footer page coverage; full
  756-page migration and DOCX generation were skipped.

Local smoke summary:

- Sample count: 3.
- Passed: 0.
- Skipped: 1.
- Blocked: 2.
- Body residual header/footer pollution count: 0.
- Table text loss warning count: 0.
- Body text loss warning count from the strict DOCX signature gate: 12.
- Page-number behavior: placeholder-only; no Word page-number field generation.

For the two `default` samples, approved header/footer text was written to
ignored local DOCX header/footer XML, and approved residual header/footer
pollution did not remain in the body. The stricter local DOCX body-signature
gate still fail-closed, so Phase 4F should investigate that mismatch before
any broader migration work.

Generated ignored local artifacts:

- `local_reports/phase4e-local-corpus-default-policy-migration-report.md`
- `local_reports/phase4e/input/*.docx`
- `local_reports/phase4e/input3/*.docx`

### Tests added

- Local corpus migration summary handles multiple samples.
- Missing approval artifacts block clearly.
- Non-default policies are skipped/fail-closed.
- Default-policy smoke safety loss blocks.
- Non-local generated DOCX paths block.
- Page-number placeholder expectation is represented separately from
  placeholder presence.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "local_corpus_default_policy_migration or default_policy_header_footer_migration_smoke or default_policy_migration"
```

Result: passed. 8 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 287 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 287 tests ran successfully.

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

Result: local sample PDFs, generated local reports, generated local DOCX files,
`.venv/`, caches, and test outputs remained ignored. Only Phase 4E test and
documentation files were modified.

### Phase 4E recommendation

Phase 4F should remain internal. The next safe direction is to reconcile the
local corpus strict DOCX body-signature gate with the previously passing raw
body-region signature evidence before adding first-page, odd/even, section, or
production migration behavior.

## Phase 4F

Date: 2026-06-03

### Scope

Phase 4F added a local/test-only DOCX body-signature mismatch investigation
helper. It does not wire header/footer migration into normal conversion and
does not change the internal writer policy.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Local mismatch investigation

Samples investigated:

- `input.pdf`
- `input3.pdf`

Skipped:

- `input6_large.pdf`: bounded subset only and still `unsupported` from Phase
  4E, so full 756-page migration and DOCX generation remained skipped.

Results:

- Strict exact body-signature gate failed for 2 samples.
- Normalized token/ngram body-signature gate passed for 2 samples.
- Approved migration-explained missing text count: 0.
- Serialization/normalization mismatch count: 12.
- True body text loss count: 0.
- Table text loss count: 0.
- Callout text loss count: 0.
- List text loss count: 0.
- Residual header/footer pollution count: 0.
- Raw body-region signature preservation: true for both investigated samples.

Classification:

- `input.pdf`: `docx_serialization_mismatch`
- `input3.pdf`: `docx_serialization_mismatch`

The Phase 4E blocker was classified as a verification/signature-normalization
issue, not observed real body text loss. Normalized body signature validation
is safe to use as a supplemental local corpus gate only with fail-closed checks
for true body text loss, table/callout/list loss, residual header/footer
pollution, and missing evidence.

Generated ignored local report:

- `local_reports/phase4f-docx-body-signature-mismatch-report.md`

### Tests added

- Exact fragment mismatch can be classified as DOCX serialization mismatch
  when normalized text is preserved.
- Approved header/footer strings removed from body are not counted as body text
  loss.
- True body text loss remains fail-closed.
- Table/callout/list text loss remains fail-closed.
- Missing evidence remains blocked.
- Strict exact gate and normalized gate results are recorded separately.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "docx_body_signature_mismatch or local_corpus_default_policy_migration"
```

Result: passed. 10 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 292 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 292 tests ran successfully.

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

Result: local sample PDFs, generated local reports, generated local DOCX files,
`.venv/`, caches, and test outputs remained ignored. Only Phase 4F test and
documentation files were modified.

### Phase 4F recommendation

Phase 4G should remain internal. The next safe direction is to refine the local
corpus validation gate so it uses normalized body-signature evidence as a
supplement to strict exact-fragment diagnostics, while retaining fail-closed
behavior for true body text loss, table/callout/list loss, residual
header/footer pollution, and missing evidence.

## Phase 4G

Date: 2026-06-03

### Scope

Phase 4G refined the local/test-only default-policy migration smoke gate to use
Phase 4F normalized token/ngram body-signature evidence as the primary local
DOCX body preservation criterion. The strict exact-fragment result remains
reported as a diagnostic.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Local normalized gate result

Samples evaluated:

- `input.pdf`
- `input3.pdf`
- `input6_large.pdf` bounded subset only

Final gate status:

- `input.pdf`: passed.
- `input3.pdf`: passed.
- `input6_large.pdf`: skipped because bounded subset policy coverage remained
  `unsupported`; full 756-page migration and DOCX generation remained skipped.

Gate metrics:

- Strict exact-fragment gate failed for 2 eligible samples and was recorded as
  diagnostic warnings.
- Normalized body-signature gate passed for 2 eligible samples.
- True body text loss count: 0.
- Table text loss count: 0.
- Callout text loss count: 0.
- List text loss count: 0.
- Residual header/footer pollution count: 0.
- Blocked sample count: 0.
- Skipped sample count: 1.

Generated ignored local report:

- `local_reports/phase4g-local-corpus-normalized-migration-gate-report.md`

Generated ignored DOCX artifacts:

- `local_reports/phase4g/input/*.docx`
- `local_reports/phase4g/input3/*.docx`

Fail-closed behavior remains:

- True body text loss blocks.
- Table text loss blocks.
- Callout/list text loss blocks.
- Residual header/footer pollution blocks.
- Missing normalized evidence blocks.
- Non-default policies remain skipped or blocked.
- Bounded large-document evidence does not pass as full-document evidence.

### Tests added

- Local corpus gate passes when strict exact-fragment matching fails but the
  normalized body-signature gate passes.
- Strict exact-fragment mismatch is recorded as a diagnostic warning.
- True body text loss remains fail-closed.
- Table/callout/list text loss remains fail-closed.
- Residual header/footer pollution remains fail-closed.
- Non-default bounded samples remain skipped and are not promoted to
  full-document evidence.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "local_corpus_gate or local_corpus_default_policy_migration or docx_body_signature_mismatch"
```

Result: passed. 15 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 297 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 297 tests ran successfully.

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

Result: local sample PDFs, generated local reports, generated local DOCX files,
`.venv/`, caches, and test outputs remained ignored. Only Phase 4G test and
documentation files were modified.

### Phase 4G recommendation

Phase 4H should remain internal. The next safe direction is to build on the
normalized local corpus gate without proceeding to page-number handling, public
API exposure, default integration, or broader migration.

## Phase 4H

Phase 4H defines and validates internal page-number handling for DOCX
header/footer migration. The work remains private, opt-in, and disabled by
default.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Page-number behavior modes

Internal modes added:

- `placeholder_only`
- `static_text`
- `word_field`
- `unsupported`

Default mode:

- `placeholder_only`

Mode behavior:

- `placeholder_only` remains the safe diagnostic default and does not claim to
  be a Word field.
- `static_text` writes literal diagnostic/static placeholder text only.
- `word_field` is internal-only and writes a Word `PAGE` field when explicitly
  requested by tests or diagnostics.
- `unsupported` fails closed.

OpenXML validation:

- Internal temp-DOCX tests validated that `word_field` mode writes PAGE field
  instructions into footer OpenXML.
- Static/placeholder tests validated that literal placeholder behavior does not
  emit `w:instrText` PAGE field XML.

Fail-closed behavior remains:

- Dynamic page-number requirements fail closed unless `word_field` mode is
  explicitly selected.
- Unsupported page-number behavior fails closed.
- Non-default header/footer policies remain blocked before simple writer
  application.
- Public/default conversion remains unchanged.

Generated ignored local report:

- `local_reports/phase4h-page-number-handling-report.md`

### Tests added

- Page-number behavior modes are explicit in the header/footer generation plan.
- Dynamic page-number requirements fail closed for placeholder/static modes and
  pass only with internal `word_field` mode.
- Internal `word_field` mode writes PAGE field OpenXML in a temp DOCX.
- Static page-number behavior remains diagnostic/static and is not a Word field.
- Unsafe/non-default policies do not write PAGE fields.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "page_number_modes or dynamic_page_number or word_page_field or static_page_number or unsafe_policy"
```

Result: passed. 5 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 302 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 302 tests ran successfully.

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

Result: local sample PDFs, generated local reports, generated local DOCX files,
`.venv/`, caches, and test outputs remained ignored. Only Phase 4H code,
tests, and documentation files were modified.

### Phase 4H recommendation

Phase 4I should remain internal. The next safe direction is to decide whether
the internal `word_field` mode should be exercised in the default-policy
synthetic/local migration smoke gates, without exposing public API/CLI behavior
or changing default conversion.

## Phase 4I

Phase 4I validates explicit internal `word_field` page-number behavior inside
the existing default-policy DOCX header/footer migration smoke path.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- `word_field` is not the default page-number behavior.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Page-number smoke result

Default page-number behavior:

- `placeholder_only`

Explicit `word_field` smoke:

- Synthetic repeated header/footer/page-number fixture passed.
- The header/footer policy remained `default`.
- Approved header/footer/page-number residuals were absent from DOCX body XML.
- Approved header text appeared in header XML.
- Approved footer text appeared in footer XML.
- Footer OpenXML contained a Word `PAGE` field instruction.
- Literal `<PAGE_NUMBER>` placeholder text was not written in `word_field` mode.
- Body text signature was preserved.
- Body residual header/footer/page-number pollution count: 0.
- Body text loss warning count: 0.
- Table text loss warning count: 0.

Placeholder/static behavior:

- Placeholder smoke remained `placeholder_only`.
- Placeholder smoke did not contain PAGE field OpenXML.
- Static-text smoke wrote only literal diagnostic/static placeholder text.
- Static-text smoke did not contain PAGE field OpenXML.

Protection and fail-closed behavior:

- Rejected page-number candidates did not produce PAGE fields.
- Unsure page-number candidates did not produce PAGE fields.
- Body-region page-number-like candidates were not represented and remained
  fail-closed.
- Non-default and unsafe policies remain blocked before writer application.

Generated ignored local report:

- `local_reports/phase4i-page-number-word-field-migration-report.md`

### Tests added

- Default-policy migration smoke supports explicit `word_field` behavior.
- Placeholder/default smoke remains placeholder-only and contains no PAGE field.
- Static-text smoke contains no PAGE field.
- PAGE field generation requires explicit page-number approval.
- Unsure page-number candidates do not generate PAGE fields.
- Body-region page-number-like candidates do not generate PAGE fields.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "default_policy_migration_smoke or word_field or static_page_number"
```

Result: passed. 6 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 307 tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 307 tests ran successfully.

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

Result: local sample PDFs, generated local reports, generated local DOCX files,
`.venv/`, caches, and test outputs remained ignored. Only Phase 4I tests and
documentation files were modified.

### Phase 4I recommendation

Phase 4J should remain internal. The next safe direction is an optional
bounded local-corpus `word_field` smoke for default-policy samples, still
without public CLI/API exposure, default conversion changes, or broader
migration behavior.

## Phase 4J

Phase 4J consolidates the reviewed header/footer migration controls into a
single internal migration profile. The profile is diagnostic, JSON-serializable,
private, and disabled by default.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

### Migration profile behavior

Default profile:

- `enabled=False`.
- Parse mode: `filtered_parse_experiment`.
- Page-number behavior: `placeholder_only`.
- Body signature gate: `normalized_token_ngram`.
- Strict exact-fragment gate: `diagnostic_only`.
- Local output policy: `temp_or_ignored_only`.
- Public exposure: `none`.

Enabled profile:

- Requires explicit review approvals.
- Blocks raw `would_exclude`, rejected, and unsure candidates.
- Protects body-region candidates and layout placeholders.
- Produces the existing internal filtered parse config for
  `filtered_parse_experiment`.
- Records DOCX header/footer plan requirements for the simple default-policy
  writer.
- Keeps normalized token/ngram signature as the primary migration gate.

Policy and page-number behavior:

- Only `default` policy is allowed for the current simple writer.
- Non-default and unsupported policies fail closed.
- `placeholder_only` is the default page-number behavior.
- `word_field` can be selected only explicitly and remains internal-only.
- `static_text` is diagnostic-only.
- Unsupported page-number behavior fails closed.

Fail-closed conditions:

- `true_body_text_loss`
- `table_text_loss`
- `callout_text_loss`
- `list_text_loss`
- `residual_header_footer_pollution`
- `unsafe_policy`
- `unsafe_page_number_behavior`
- `missing_review_decisions`

Generated ignored local report:

- `local_reports/phase4j-internal-migration-profile-report.md`

### Tests added

- Default profile is disabled and JSON-serializable.
- Enabled profile builds the internal filtered parse config.
- Missing review decisions fail closed.
- Raw `would_exclude`, rejected, unsure, body-region, and layout-placeholder
  candidates remain blocked/protected.
- Only default policy is accepted by the profile validation.
- Explicit `word_field` behavior is supported and not the default.
- Unsupported page-number behavior fails closed.
- Strict exact-fragment mismatch is diagnostic-only when the normalized
  token/ngram body gate passes.
- Body/table/callout/list loss and residual header/footer pollution are
  fail-closed conditions.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "migration_profile"
```

Result: passed. 7 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 314 tests and 10 subtests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 314 tests ran successfully.

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

Result: modified files were limited to Phase 4J code, tests, and committed
documentation. `.venv/`, caches, `local_samples/`, `local_reports/`, and test
outputs remained ignored.

### Phase 4J recommendation

Phase 5A should keep this profile internal and use it as the single entry point
for any next bounded default-policy smoke path. Production/default conversion,
public CLI/API exposure, non-default policy writing, and cross-page paragraph
merge should remain out of scope until a later explicit phase.

## Phase 5A

Phase 5A adds an internal quality evaluation pack for the reviewed
header/footer migration MVP. It evaluates current evidence and readiness
without expanding behavior.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

Quality evaluation document:

- `docs/agent/reviewed-filtering-quality-evaluation.md`

Generated ignored local report:

- `local_reports/phase5a-quality-evaluation-pack-report.md`

### Quality status

Internal MVP readiness:

- `ready_for_internal_quality_review`

Public/default readiness:

- `not_public_ready`

Synthetic coverage summary:

- Repeated header/footer/page-number detection covered.
- Approval-gated reviewed filtering covered.
- Filtered body plus DOCX header/footer XML covered.
- Default-policy migration smoke covered.
- Explicit internal `word_field` PAGE field smoke covered.
- Callout/list/heading/table preservation covered.
- Non-default policy fail-closed behavior covered.

Local corpus evidence summary:

- Local evidence came from ignored Phase 4G/4H/4I/4J reports.
- `input.pdf`: passed normalized local migration gate.
- `input3.pdf`: passed normalized local migration gate.
- `input6_large.pdf`: bounded subset only; skipped because policy remained
  `unsupported` under incomplete coverage.
- True body text loss count: 0.
- Table text loss count: 0.
- Callout text loss count: 0.
- List text loss count: 0.
- Residual header/footer pollution count: 0.
- Local corpus evidence remains ignored and non-committed.

Fail-closed safety summary:

- Explicit review approval required.
- Raw `would_exclude` blocked.
- Rejected/unsure blocked.
- Body-region protected.
- Layout-placeholder protected.
- Normalized token/ngram body signature remains primary.
- Strict exact-fragment mismatch remains diagnostic-only.
- True body/table/callout/list loss fails closed.
- Residual header/footer pollution fails closed.
- Non-default policies fail closed.
- Unsupported page-number behavior fails closed.

Remaining gaps:

- Public CLI/API option is not exposed.
- Production/default migration is not enabled.
- First-page Word header/footer writing is not implemented.
- Odd/even Word header/footer writing is not implemented.
- Full section-specific production mapping is not implemented.
- Image/logo header/footer migration is not implemented.
- Cross-page paragraph continuation merge is not implemented.
- Large document evidence remains bounded for `input6_large`.

### Tests added

- Quality summary marks public/default readiness as not ready.
- Quality summary recognizes internal MVP evidence.
- Quality summary records synthetic coverage.
- Quality summary records local corpus evidence.
- True body/table/callout/list loss blocks quality readiness.
- Residual header/footer pollution blocks quality readiness.
- Non-default policy support remains fail-closed.
- Default page-number behavior remains `placeholder_only`.
- `word_field` remains internal-only.
- Quality summary is JSON-serializable.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "quality_evaluation"
```

Result: passed. 6 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 320 tests and 10 subtests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 320 tests ran successfully.

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

Result: modified files were limited to Phase 5A code, tests, and committed
documentation. `.venv/`, caches, `local_samples/`, `local_reports/`, and test
outputs remained ignored.

### Phase 5A recommendation

Phase 5B should stay internal and bounded. Use the quality pack as the
checklist for any next profile-driven default-policy smoke. Public/default
integration, non-default policy writing, image/logo migration, paragraph merge,
and table parser changes remain future work.

## Phase 5B

Phase 5B expands the internal quality evaluation over available ignored local
corpus reports. It classifies local samples without adding production behavior
or rerunning heavy full-document local conversions.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

Quality evaluation document:

- `docs/agent/reviewed-filtering-quality-evaluation.md`

Generated ignored local report:

- `local_reports/phase5b-local-corpus-quality-review-report.md`

### Local corpus summary

Local corpus samples summarized:

- `input.pdf`
- `input2.pdf`
- `input3.pdf`
- `input4.pdf`
- `input5.pdf`
- `input6_large.pdf`

Passed/internal migration smoke samples:

- `input.pdf`
- `input3.pdf`

Negative/control samples:

- `input2.pdf`
- `input4.pdf`
- `input5.pdf`

Bounded/skipped samples:

- `input6_large.pdf`

Unsupported/missing samples:

- `input6_large.pdf` remains unsupported under bounded coverage.
- Missing expected local sample artifacts: 0.

Loss and pollution summary:

- True body text loss count: 0.
- Table text loss count: 0.
- Callout text loss count: 0.
- List text loss count: 0.
- Residual header/footer pollution count: 0.

Fail-closed safety summary:

- Positive local smoke remains limited to default-policy samples.
- Negative/control samples are not treated as migration passes.
- Bounded `input6_large.pdf` evidence is not treated as full-document pass.
- Unsupported policy evidence is not treated as pass.
- Body/table/callout/list loss and residual pollution remain blockers.
- Public/default readiness remains blocked.

Remaining gaps:

- Local corpus evidence remains ignored and non-committed.
- Large document evidence remains bounded for `input6_large`.
- Public CLI/API option is not exposed.
- Production/default migration is not enabled.
- First-page, odd/even, and section-scoped Word header/footer writing are not
  implemented.
- Image/logo header/footer migration is not implemented.
- Cross-page paragraph continuation merge is not implemented.

### Tests added

- Local corpus quality summary classifies passed samples.
- No-candidate samples are classified as negative/control.
- Bounded large sample remains bounded-only.
- Missing artifacts are reported clearly.
- Body/table/callout/list loss blocks pass classification.
- Residual header/footer pollution blocks pass classification.
- Unsupported policy is not treated as pass.
- Local corpus quality summary is JSON-serializable.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "local_corpus_quality_review"
```

Result: passed. 8 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 328 tests and 10 subtests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 328 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

### Phase 5B recommendation

Phase 5C should remain internal and evidence-driven. Keep default conversion
closed while deciding whether to extend bounded local quality evidence,
formalize additional negative controls, or design a separately approved
non-default-policy investigation.

## Phase 5C

Phase 5C drafts and validates an internal-only request/config surface for the
reviewed header/footer migration MVP. The surface describes how future private
callers can request migration safely, but it does not execute migration or
change default conversion behavior.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

Internal API/config surface document:

- `docs/agent/reviewed-filtering-internal-api-surface.md`

Generated ignored local report:

- `local_reports/phase5c-internal-api-surface-report.md`

### Internal request summary

Default enabled state:

- `enabled=False`.
- `surface=internal_only`.
- `mode=default_policy_migration_smoke`.
- The request does not execute migration.

Review-decision requirement:

- Enabled requests require explicit review decisions through `review_decisions`
  or `review_decisions_path`.
- Raw `would_exclude` remains blocked.
- Rejected and unsure candidates remain blocked.

Migration profile relationship:

- The request embeds or auto-builds the Phase 4J migration profile from safe
  defaults.
- The generated profile keeps `filtered_parse_experiment` as the parse mode.
- The derived reviewed-filtering config remains private/internal.

Page-number behavior:

- `placeholder_only` remains the default.
- `word_field` can be selected explicitly for internal-only requests.
- Unsupported page-number behavior fails closed.
- `static_text` remains diagnostic/static only.

Quality gate:

- Normalized token/ngram body signature remains primary.
- Strict exact-fragment mismatch remains diagnostic-only.
- Body/table/callout/list loss and residual header/footer pollution remain
  fail-closed blockers.

Policy and local output:

- Only `default` policy is allowed for writer application.
- Non-default and future modes remain fail-closed/disabled.
- Local output policy remains `temp_or_ignored_only`.

Public exposure status:

- Public CLI: false.
- Public API: false.
- Public exposure: `none`.
- Production/default integration: false.

### Tests added

- Internal request is disabled by default.
- Internal request requires explicit enablement and review decisions.
- Internal request refuses raw `would_exclude`-only input.
- Internal request embeds the migration profile and private reviewed-filtering
  config.
- Internal request defaults to `placeholder_only`.
- Internal request can explicitly select `word_field`.
- Unsupported page-number behavior fails closed.
- Only default policy is allowed for writer application.
- Future/non-default modes remain fail-closed.
- Normalized body signature and strict exact-fragment gates are recorded.
- Public CLI/API remain false.
- Request summary and validation are JSON-serializable.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "internal_request"
```

Result: passed. 9 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 337 tests and 10 subtests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 337 tests ran successfully.

```bash
git diff --check
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

### Phase 5C recommendation

Phase 5D should keep this surface private and validation-only unless a later
phase explicitly adds a private adapter. Public/default integration,
non-default policy writing, image/logo migration, paragraph merge, and table
parser changes remain future work.

## Phase 5D

Phase 5D creates a public/default readiness checklist for the reviewed
header/footer migration MVP. It defines what must be true before any future
public opt-in or default-on integration can be considered.

Production/default behavior did not change:

- No `Converter.convert()` default behavior changed.
- No public CLI behavior changed.
- No public API option was added.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

Public readiness checklist:

- `docs/agent/reviewed-filtering-public-readiness-checklist.md`

Generated ignored local report:

- `local_reports/phase5d-public-readiness-checklist-report.md`

### Readiness status

Internal MVP readiness:

- `internal_mvp_ready=True`

Public opt-in readiness:

- `public_opt_in_ready=False`

Default-on readiness:

- `default_on_ready=False`

Key public blockers:

- No public API or CLI option.
- API shape remains internal-only.
- Review decisions are not user-facing.
- Local report/output policy is not user-facing.
- Public warning/error model is missing.
- End-user documentation is missing.
- Public option backward compatibility policy is missing.

Key default-on blockers:

- Only `default` policy writing is supported.
- `first_page`, `odd_even`, `section_scoped`, and `unsupported` policies still
  fail closed.
- Image/logo header/footer migration is not implemented.
- Paragraph continuation merge is not implemented.
- Large document evidence remains bounded for `input6_large`.
- Local corpus evidence is ignored and non-committed.
- Public regression fixture set is limited.
- Performance characteristics are not fully evaluated.
- Manual review approval is still required.

Recommended next phase:

- Phase 5E: public option naming and warning model draft.

### Tests added

- Checklist marks internal MVP as ready.
- Checklist marks public opt-in as not ready.
- Checklist marks default-on as not ready.
- Checklist includes non-default policy blockers.
- Checklist includes paragraph continuation blockers.
- Checklist includes image/logo migration blockers.
- Checklist includes large corpus/performance blockers.
- Checklist includes required public/default gates.
- Checklist summary is JSON-serializable.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "public_readiness_checklist"
```

Result: passed. 7 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 344 tests and 10 subtests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 344 tests ran successfully.

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

Result: modified files were limited to Phase 5D code, tests, and committed
documentation. `.venv/`, caches, `local_samples/`, `local_reports/`, and test
outputs remained ignored.

### Phase 5D recommendation

Phase 5E should draft public option naming and a public warning/error model
without exposing behavior. Public/default integration, non-default policy
writing, image/logo migration, paragraph merge, and table parser changes remain
future work.

## Phase 5E

Phase 5E drafted the future public option naming and warning/error model for
reviewed header/footer migration. The phase remains design-only and
internal/test-only; it does not expose a CLI flag or public API option.

### Default/public behavior

Production/default conversion changed:

- No.

Public CLI/API changed:

- No.

Default conversion behavior:

- Unchanged.
- Reviewed filtering remains private/internal and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

Public option/warning model document:

- `docs/agent/reviewed-filtering-public-option-warning-model.md`

Generated ignored local report:

- `local_reports/phase5e-public-option-warning-model-report.md`

### Public option draft

Recommended future option name:

- `reviewed_header_footer_migration`

Recommended future CLI flag, not implemented:

- `--reviewed-header-footer-migration`

Public exposure status:

- `enabled=False`
- `implemented=False`
- `public_option_available=False`
- `public_cli_exposed=False`
- `public_api_exposed=False`
- `production_default_enabled=False`

Future public modes drafted:

- `disabled`
- `diagnose`
- `reviewed_migration`
- future `auto_safe`

Page-number behavior summary:

- `placeholder_only` remains the default.
- `word_field` is an explicit future/internal-only behavior.
- `static_text` remains static/diagnostic.
- `unsupported` fails closed.

Policy behavior summary:

- Only `default` policy is eligible for writer application.
- `first_page`, `odd_even`, `section_scoped`, and `unsupported` remain
  fail-closed until future phases add support.

Quality gate summary:

- Normalized token/ngram body signature remains the primary gate.
- Strict exact-fragment mismatch remains diagnostic-only.
- True body/table/callout/list loss remains fail-closed.
- Residual header/footer pollution remains fail-closed.

### Warning/error model

Warning severities drafted:

- `info`
- `warning`
- `blocked`
- `error`

Warning entry fields:

- `severity`
- `code`
- `message`
- `phase`
- `source`
- `affected_pages`
- `affected_candidates`
- `safe_to_continue`
- `user_action_required`
- `diagnostic_only`
- `blocking`

Blocking warning codes:

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

Diagnostic-only warning codes:

- `strict_exact_fragment_mismatch_diagnostic`
- `diagnostic_report_local_only`
- `public_api_not_enabled`

### Tests added

- Public option draft is disabled/not implemented.
- Public option draft states public CLI/API is not exposed.
- Recommended option name is stable and JSON-serializable.
- Warning entries include severity/code/message/safe-to-continue/user-action
  fields.
- Warning model includes blocking codes for body/table/callout/list loss.
- Warning model includes blocking codes for missing review decisions.
- Warning model records strict exact-fragment mismatch as diagnostic-only.
- Warning model includes unsupported policy and unsafe page-number behavior
  codes.
- Warning model summary is JSON-serializable.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "public_option_draft or warning_model"
```

Result: passed. 8 selected tests and 21 subtests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 352 tests and 31 subtests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 352 tests ran successfully.

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

Result: modified files were limited to Phase 5E helper code, tests, and
committed documentation. `.venv/`, caches, `local_samples/`, `local_reports/`,
and test outputs remained ignored.

### Phase 5E recommendation

Phase 5F should expand committed public-safe fixtures and public-facing
warning/error expectations before any public opt-in implementation is
considered. Public/default integration, non-default policy writing,
image/logo migration, paragraph merge, and table parser changes remain future
work.

## Phase 5F

Phase 5F expanded committed public-safe synthetic/generated fixture coverage
for reviewed header/footer migration. It did not use ignored local PDFs or
local extracted text, and it did not commit generated PDF/DOCX binaries.

### Default/public behavior

Production/default conversion changed:

- No.

Public CLI/API changed:

- No.

Existing conversion tests passed:

- Yes.

Default conversion behavior:

- Unchanged.
- Reviewed filtering remains internal-only and disabled by default.
- DOCX header/footer generation remains disabled by default.
- No content is moved into DOCX headers/footers during normal conversion.
- No cross-page paragraph merge was added.
- No production table parsing behavior was changed.

Generated ignored local report:

- `local_reports/phase5f-public-safe-fixture-expansion-report.md`

### Synthetic fixture scenarios added

Runtime-generated public-safe PDF scenarios:

- `phase5f_first_page_policy`
- `phase5f_odd_even_policy`
- `phase5f_section_scoped_policy`
- `phase5f_body_heading_similarity`
- `phase5f_no_header_footer_control`

Additional synthetic/test-only plan coverage:

- Default page-number placeholder vs explicit `word_field`.
- Strict exact-fragment mismatch with normalized token/ngram body signature
  preserved.
- Public warning model mapping for blocking and diagnostic-only codes.

Public-safe fixture policy:

- Synthetic text uses artificial `Synthetic public safe ...` content.
- Ignored local PDF text is not used.
- Generated PDFs and DOCX files are created only in temporary directories.
- No generated PDF/DOCX binary fixture is committed.
- `local_samples/` and `local_reports/` remain ignored.

### Coverage results

Policy fail-closed coverage:

- `first_page` policy remains fail-closed for the simple writer.
- `odd_even` policy remains fail-closed for the simple writer.
- `section_scoped` policy remains fail-closed and still requires future
  section mapping.

Body preservation coverage:

- Header/footer text that partially resembles a body heading does not remove
  the body heading.
- Body-region removal count remains 0 for the similarity fixture.
- Body text signature remains preserved.

Page-number field coverage:

- Placeholder mode does not emit a Word `PAGE` field.
- Explicit `word_field` mode emits PAGE field OpenXML.
- `word_field` remains opt-in and internal/test-only.

Normalized gate coverage:

- Normalized token/ngram body signature gate passes for the artificial
  fragmentation case.
- Strict exact-fragment mismatch remains diagnostic-only.

Warning model coverage:

- Missing review decisions map to `missing_review_decisions`.
- Unsafe/non-default policy maps to `non_default_policy_unsupported`.
- Unsafe page-number behavior maps to `unsafe_page_number_behavior`.
- Body/table text loss maps to `body_text_loss_detected` and
  `table_text_loss_detected`.
- Residual pollution maps to `residual_header_footer_pollution`.
- Strict exact-fragment mismatch maps to
  `strict_exact_fragment_mismatch_diagnostic`.

Negative/control coverage:

- Public-safe no-header/footer control produces 0 migration candidates.
- No reviewed filtering removal occurs without eligible candidates.

### Remaining gaps

- Public CLI/API option remains unimplemented.
- Production/default migration remains disabled.
- First-page Word header/footer writing is not implemented.
- Odd/even Word header/footer writing is not implemented.
- Full section-specific production mapping is not implemented.
- Image/logo header/footer migration is not implemented.
- Cross-page paragraph continuation merge is not implemented.
- Broader public-safe fixture diversity is still needed.
- Performance/stress evidence remains future work.
- Local corpus evidence remains ignored and non-committed.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "phase5f"
```

Result: passed. 6 selected tests and 9 subtests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 358 tests and 40 subtests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m unittest discover -s test -p 'test_layout_analyzer.py'
```

Result: passed. 358 tests ran successfully.

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

Result: modified tracked files were limited to Phase 5F tests and committed
documentation before commit. `.venv/`, caches, `local_samples/`,
`local_reports/`, and test outputs remained ignored.

### Phase 5F recommendation

Phase 5G should evaluate performance/stress behavior or continue expanding
public-safe fixtures. Public/default integration, non-default policy writing,
image/logo migration, paragraph merge, and table parser changes remain future
work.

## Phase 6A

Packaging Phase 6A prepared private/offline wheelhouse usage documentation and
a generic wheel conversion smoke script. This phase is private packaging work
only; it does not expose reviewed header/footer migration publicly and does not
change default conversion behavior.

### Default/public behavior

Production/default conversion changed:

- No.

Public CLI/API changed:

- No.

Existing conversion tests passed:

- Yes.

Reviewed filtering status:

- Internal-only and disabled by default.
- No public CLI flag was added.
- No public API option was added.
- No production table parsing behavior was changed.

### Packaging metadata summary

Packaging metadata files inspected:

- `setup.py`
- `requirements.txt`
- `.gitignore`
- `MANIFEST.in`

Absent metadata files:

- No committed `pyproject.toml`.
- No committed `setup.cfg`.

Declared package metadata:

- Package name: `pdf2docx`
- Version source: `version.txt`
- Built version: `0.5.13`
- Declared Python support: `Requires-Python: >=3.10`
- Console entry point: `pdf2docx=pdf2docx.main:main`
- Project wheel tag: `py3-none-any`
- Wheel metadata: `Root-Is-Purelib: true`

Runtime dependency constraints:

- `PyMuPDF>=1.26.7`
- `python-docx>=0.8.10`
- `fonttools>=4.24.0`
- `numpy>=1.17.2`
- `opencv-python-headless>=4.5`
- `fire>=0.3.0`

Packaging interpretation:

- The project package wheel is pure Python.
- The offline wheelhouse is platform/Python-target specific because PyMuPDF,
  numpy, opencv-python-headless, lxml, and fonttools provide platform wheels.

### Python compatibility

Tested full packaging/install/conversion interpreter:

- Python 3.12.13, Windows 11, `win-amd64`.

Dependency wheels built for the local wheelhouse:

- CPython 3.12 / Windows AMD64 where platform-specific.
- PyMuPDF wheel: `cp310-abi3-win_amd64`.
- opencv wheel: `cp37-abi3-win_amd64`.

Additional local interpreter check:

- `/usr/bin/python3.10` was available.
- Python 3.10 syntax/compile check passed for the touched smoke script and
  core files.
- Python 3.10 dependency install/test matrix was not run because the built
  wheelhouse targets Windows/AMD64 Python 3.12, not the local Linux Python
  3.10 interpreter.

Unsupported/not tested:

- Python 2.7 and Python 3.6 are below the declared `>=3.10` minimum and were
  not tested.
- Python 3.11 and Python 3.13 interpreters were not available locally in the
  tested environment.

### Files added

Committed packaging plan:

- `docs/agent/offline-wheelhouse-packaging-plan.md`

Committed smoke script:

- `scripts/smoke_convert_pdf_to_docx.py`

Git ignore additions:

- `.venv-wheel-smoke/`
- `wheelhouse/`
- `*.whl`

### Commands run

Focused Phase 6A tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "phase6a"
```

Result: passed. 3 selected tests ran successfully.

Required layout analyzer tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 361 tests and 40 subtests ran successfully.

Required compile check plus smoke script compile:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py test/test_layout_analyzer.py scripts/smoke_convert_pdf_to_docx.py
```

Result: passed.

Python 3.10 syntax/compile check:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp python3.10 -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/converter.py scripts/smoke_convert_pdf_to_docx.py test/test_layout_analyzer.py
```

Result: passed.

Whitespace check:

```bash
git diff --check
```

Result: passed.

Required conversion tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

Install build tools:

```bash
.venv/bin/python -m pip install --upgrade build wheel
```

Result: passed. Installed `build==1.5.0`, `wheel==0.47.0`, and
`pyproject_hooks==1.2.0` into the ignored `.venv/`.

Build project wheel:

```bash
.venv/bin/python -m build --wheel
```

Result: passed. Built `dist/pdf2docx-0.5.13-py3-none-any.whl`.

Build dependency wheelhouse:

```bash
.venv/bin/python -m pip wheel -w wheelhouse .
```

Result: passed. Built `wheelhouse/` with the project wheel and runtime
dependency wheels.

Create fresh wheel smoke environment:

```bash
.venv/bin/python -m venv .venv-wheel-smoke
```

Result: passed. Fresh environment created with
`.venv-wheel-smoke/Scripts/python.exe`.

Offline-style install from wheelhouse:

```bash
.venv-wheel-smoke/Scripts/python.exe -m pip install --no-index --find-links wheelhouse pdf2docx
```

Result: passed. Installed `pdf2docx==0.5.13` and runtime dependencies from
`wheelhouse/` only.

Import smoke:

```bash
/mnt/d/Workspaces/Codex/pdf2docx/.venv-wheel-smoke/Scripts/python.exe -c "import sys, platform, pdf2docx; print(sys.version); print(platform.platform()); print(pdf2docx.__file__)"
```

Run from `/tmp`.

Result: passed. `pdf2docx.__file__` resolved to
`.venv-wheel-smoke/Lib/site-packages/pdf2docx/__init__.py`.

Conversion smoke with committed demo PDF:

```bash
/mnt/d/Workspaces/Codex/pdf2docx/.venv-wheel-smoke/Scripts/python.exe D:/Workspaces/Codex/pdf2docx/scripts/smoke_convert_pdf_to_docx.py D:/Workspaces/Codex/pdf2docx/test/samples/demo.pdf D:/Workspaces/Codex/pdf2docx/local_reports/wheel_smoke/demo.docx
```

Result: passed. Output:

- `local_reports/wheel_smoke/demo.docx`
- Size: 440087 bytes
- Imported module: `.venv-wheel-smoke/Lib/site-packages/pdf2docx/__init__.py`

Private local sample conversion smoke:

```bash
/mnt/d/Workspaces/Codex/pdf2docx/.venv-wheel-smoke/Scripts/python.exe D:/Workspaces/Codex/pdf2docx/scripts/smoke_convert_pdf_to_docx.py D:/Workspaces/Codex/pdf2docx/local_samples/input.pdf D:/Workspaces/Codex/pdf2docx/local_reports/wheel_smoke/input.docx
```

Result: passed because `local_samples/input.pdf` was present. Output:

- `local_reports/wheel_smoke/input.docx`
- Size: 280904 bytes
- Imported module: `.venv-wheel-smoke/Lib/site-packages/pdf2docx/__init__.py`

### Generated artifacts

Generated and ignored:

- `build/`
- `dist/pdf2docx-0.5.13-py3-none-any.whl`
- `wheelhouse/`
- `.venv-wheel-smoke/`
- `pdf2docx.egg-info/`
- `local_reports/wheel_smoke/demo.docx`
- `local_reports/wheel_smoke/input.docx`
- `local_reports/wheel_smoke/*.docx` temporary/lock files
- caches and `__pycache__/`

Ignore verification:

- `dist/` ignored by `.gitignore`.
- `wheelhouse/` ignored by `.gitignore`.
- `.venv-wheel-smoke/` ignored by `.gitignore`.
- wheel files ignored by `.gitignore`.
- wheel smoke DOCX outputs ignored through `local_reports/`.

### Compatibility limitations

- Full wheel install and conversion smoke were run only on Python 3.12.13
  Windows AMD64.
- Python 3.10 was compile-checked but not dependency-installed/tested.
- Linux/macOS wheelhouses were not built in this phase.
- Python 3.11 and Python 3.13 were not tested locally.
- Dependency wheel availability must be verified per closed-network target.

### Phase 6A recommendation

Phase 6B should run the same wheelhouse install and conversion smoke on the
actual closed-network target OS/Python matrix, record dependency wheel
availability, and define checksum/transfer procedures for the offline bundle.

## Header/Footer Role Mapping Bugfix

Date: 2026-06-04

### Observed bug summary

A local quality review reported that bottom footer text appeared to behave like
Word header content, while expected top header content was missing from the DOCX
header. Packaging Phase 6B was stopped so the internal reviewed header/footer
migration path could be inspected first.

### Files inspected

- `docs/agent/verification.md`
- `docs/agent/reviewed-filtering-integration-readiness.md`
- `docs/agent/reviewed-filtering-quality-evaluation.md`
- `pdf2docx/page/LayoutAnalyzer.py`
- `pdf2docx/common/docx.py`
- `test/test_layout_analyzer.py`
- `scripts/smoke_convert_pdf_to_docx.py`
- `local_reports/quality_batch_convert/output_docx/input.docx`
- `local_reports/phase4g/input/filtered-body-with-header-footer.docx`
- `local_reports/phase4g/input3/filtered-body-with-header-footer.docx`

### OpenXML inspection result

- The default batch DOCX for `input.pdf` had no `word/header*.xml` or
  `word/footer*.xml` parts, so its visual editing behavior is outside the
  internal migration writer path.
- The Phase 4G internal migration DOCX for `input.pdf` had top header text in
  `word/header1.xml` and bottom footer/page-number placeholder text in
  `word/footer1.xml`.
- The Phase 4G internal migration DOCX for `input3.pdf` had footer text in
  `word/footer1.xml` and an empty header part. The top repeated strings were
  `review_only`/`action=review`, so they stayed blocked rather than becoming
  representable header entries.

Local ignored investigation reports:

- `local_reports/header_footer_role_bug/docx-openxml-role-inspection.md`
- `local_reports/header_footer_role_bug/header-footer-plan-inspection.json`
- `local_reports/header_footer_role_bug/role-mapping-root-cause.md`

### Root cause

The current local OpenXML artifacts did not reproduce a completed
header/footer role swap. However, the internal plan/writer path trusted
`proposed_role` too much: a bottom-region candidate mislabeled as `header`, or
a top-region candidate mislabeled as `footer`, could be represented and written
to the wrong DOCX part.

That was unsafe for the reviewed migration MVP because role assignment and
y-position evidence must agree before content is moved into DOCX header/footer
parts.

### Fix summary

- `build_docx_header_footer_generation_plan()` now fails closed when
  header/footer/page-number roles conflict with top/bottom/body region
  evidence.
- `apply_header_footer_text_plan()` now validates plan `entries` before writing
  and fails closed on role/target-part/region mismatches.
- Page-number entries remain footer-targeted and bottom-region-only for the
  current simple writer.
- Default conversion behavior remains unchanged.
- Public CLI/API remains unchanged and closed.

### New regression tests

- Role/region mismatch candidates fail closed at plan generation.
- Writer blocks an unsafe plan that would put footer text in header XML or
  header text in footer XML.
- Role-specific OpenXML assertions verify top header text appears only in
  header XML, bottom footer text appears only in footer XML, page-number
  placeholder appears only in footer XML, and body text remains in body XML.

### Commands run

Focused regression command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "header_footer_role or default_policy_migration or word_field"
```

Result: passed. 16 selected tests and 4 subtests ran successfully.

Full layout analyzer tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 364 tests and 40 subtests ran successfully.

Compile check:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/common/docx.py test/test_layout_analyzer.py
```

Result: passed.

Whitespace check:

```bash
git diff --check
```

Result: passed.

Existing conversion tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

### Remaining risks

- The default converter still does not migrate PDF headers/footers into Word
  header/footer parts.
- `input3.pdf` top repeated text remains blocked because it is review-only, not
  an eligible header candidate under the current safety policy.
- First-page, odd/even, section-scoped, image/logo, and paragraph continuation
  behavior remains out of scope.

## Header/Footer Fidelity Improvement

### Observed quality issue

Manual reviewed-output inspection showed that header/footer role separation was
structurally correct, but visual fidelity was weak. Header/footer text appeared
in the correct Word parts, but font size, font family, bold/italic, color,
alignment, and dynamic page-number output were not preserved well.

### Metadata availability result

- Page summaries already expose page width/height and text block bboxes.
- Text spans already expose font, size, flags, and color.
- The internal layout-analysis summary now preserves color when available and
  keeps a separate style payload for writer hints.
- Candidate entries now carry lightweight bbox, page-size, style, alignment,
  and line-index metadata.

Local ignored investigation reports:

- `local_reports/header_footer_fidelity/metadata-availability-report.md`
- `local_reports/header_footer_fidelity/reviewed-output-openxml-fidelity-report.md`
- `local_reports/header_footer_fidelity/fidelity-root-cause.md`

### Root cause

The internal generation plan flattened approved candidates into plain text
lists, and the writer assigned paragraph text directly. That discarded available
layout/style hints before DOCX header/footer XML was written.

### Implementation summary

- Added styled `header_items`, `footer_items`, and `page_number_items` while
  keeping existing text-list keys for compatibility.
- Added conservative alignment inference from bbox center and page width.
- Applied simple paragraph alignment and run font size, font family, bold,
  italic, and color hints in the internal DOCX writer.
- Kept `placeholder_only` diagnostic and required explicit `word_field` for
  real Word PAGE fields.
- Default conversion behavior remains unchanged.
- Public CLI/API remains unchanged and closed.

### New regression tests

- Styled header/footer plans write role-specific OpenXML with alignment, font
  size, bold/italic, and color markers.
- Alignment inference covers left, center, right, and unknown.
- `word_field` page-number output writes a PAGE field and avoids literal
  `<PAGE_NUMBER>` visible text.
- Missing style metadata still writes header/footer text without crashing.
- Existing role-mapping and word-field tests continue to inspect header/footer
  XML separately.

### Local smoke result

The first smoke attempt against the default reviewed batch output path failed
because the existing `input.docx` was locked by another process. A second smoke
run used isolated ignored output paths under
`local_reports/header_footer_fidelity/smoke/` and passed:

- default converted/skipped-existing: 1
- reviewed converted: 1
- failed: 0
- reviewed DOCX has `word/header1.xml` and `word/footer1.xml`
- footer XML contains a Word PAGE field when `word_field` is selected
- footer XML does not contain literal `<PAGE_NUMBER>`
- header and footer XML contain style/alignment markers

### Commands run

Focused regression command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "header_footer_fidelity or header_footer_role or page_number or word_field"
```

Result: passed. 24 selected tests and 6 subtests ran successfully.

Full layout analyzer tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 369 tests and 40 subtests ran successfully.

Compile check:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py test/test_layout_analyzer.py
```

Result: passed.

Whitespace check:

```bash
git diff --check
```

Result: passed.

Existing conversion tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

Local reviewed smoke:

```bash
.venv/bin/python local_reports/reviewed_migration_batch_compare/batch_compare_reviewed_migration.py --overwrite --allow-source-tree --page-number-behavior word_field --default-output-dir local_reports/header_footer_fidelity/smoke/output_docx_default --reviewed-output-dir local_reports/header_footer_fidelity/smoke/output_docx_reviewed --report-dir local_reports/header_footer_fidelity/smoke/reports --log-dir local_reports/header_footer_fidelity/smoke/logs
```

Result: passed. Local artifacts remain ignored.

### Remaining limitations

- Exact PDF absolute positioning is not implemented.
- Image/logo header/footer migration is not implemented.
- First-page, odd/even, and section-scoped writer application remains
  fail-closed.
- `placeholder_only` and `static_text` remain diagnostic literal modes.

## Header/Footer Fidelity Follow-up

### Observed issues

Manual inspection after the first fidelity improvement showed three remaining
questions:

- Header/footer text appeared gray.
- `Page 123`-style page numbers became a bare PAGE field starting at `1`.
- First-page header text appeared slightly clipped near the top.

### Color investigation result

- Latest reviewed smoke output contains `w:color w:val="000000"` in header XML.
- Footer text and page-number runs also contain `w:color w:val="000000"`.
- PDF layout-analysis metadata exposes black as color value `0`, and the
  internal plan preserves it as `#000000`.
- The gray appearance is consistent with Word's normal dimmed display for
  header/footer content while editing the document body, not an incorrect gray
  run color.

### Page-number template/start result

- The local sample page-number candidate has a consecutive sequence:
  `Page 123`, `Page 124`, through `Page 134`.
- The internal plan now parses simple one-number templates and records prefix,
  suffix, start number, sequence numbers, and consecutive status.
- For explicit `word_field`, the writer now emits prefix/suffix runs around the
  PAGE field and sets section page numbering start when the sequence is safe.
- Latest smoke footer XML contains `Page `, a PAGE field instruction, cached
  field text `123`, and no literal `<PAGE_NUMBER>`.
- Latest smoke `word/document.xml` contains `<w:pgNumType w:start="123"/>`.

### Clipping investigation result

- Latest smoke section margins include `w:header="720"` and `w:footer="720"`.
- Generated header/footer paragraphs now contain
  `<w:spacing w:before="0" w:after="0"/>`.
- Generated header/footer XML does not contain `w:lineRule="exact"` or
  `w:line=` exact line-height attributes.
- This is a conservative clipping-risk reduction, not exact PDF positioning.

Ignored local investigation reports:

- `local_reports/header_footer_fidelity_followup/color-openxml-report.md`
- `local_reports/header_footer_fidelity_followup/page-number-template-report.md`
- `local_reports/header_footer_fidelity_followup/header-clipping-root-cause.md`

### Implementation summary

- Added simple page-number template parsing for one arabic numeric run.
- Added consecutive page-number sequence inference for internal plan metadata.
- Added page-number prefix/suffix and start-number metadata to plan entries and
  section plans.
- Updated the internal DOCX writer to write prefix/suffix around PAGE fields.
- Updated the internal DOCX writer to set `w:pgNumType w:start` when safe.
- Preserved black `0` as `#000000` and tested missing color does not force gray.
- Normalized generated header/footer paragraph before/after spacing while
  avoiding exact line-height.
- Default conversion remains unchanged.
- Public CLI/API remains unchanged and closed.

### Tests added

- Black color `0`, colored values, and missing color behavior.
- Page-number template parsing for `Page 123`, `- 123 -`, and `123`.
- Consecutive and non-consecutive page-number sequence inference.
- Generation-plan metadata for `Page 123` prefix and start number.
- Word PAGE field output with prefix, cached `123`, and `w:start="123"`.
- Header/footer clipping guard against exact line-height.

### Commands run

Focused regression command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "header_footer_fidelity or page_number_template or word_field or clipping or color"
```

Result: passed. 16 selected tests ran successfully.

Full layout analyzer tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 375 tests and 40 subtests ran successfully.

Compile check:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py test/test_layout_analyzer.py
```

Result: passed.

Whitespace check:

```bash
git diff --check
```

Result: passed.

Existing conversion tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

Local reviewed smoke:

```bash
.venv/bin/python local_reports/reviewed_migration_batch_compare/batch_compare_reviewed_migration.py --overwrite --allow-source-tree --page-number-behavior word_field --default-output-dir local_reports/header_footer_fidelity_followup/smoke/output_docx_default --reviewed-output-dir local_reports/header_footer_fidelity_followup/smoke/output_docx_reviewed --report-dir local_reports/header_footer_fidelity_followup/smoke/reports --log-dir local_reports/header_footer_fidelity_followup/smoke/logs
```

Result: passed. Reviewed converted count was 1 and failed count was 0. Local
artifacts remain ignored.

### Remaining limitations

- Only simple one-number page-number templates are supported.
- Multi-number forms such as `Page 1 of 10` remain unsupported/diagnostic.
- Exact PDF absolute positioning is not implemented.
- Image/logo header/footer migration is not implemented.
- First-page, odd/even, and section-scoped writer application remains
  fail-closed.

## Header/Footer Pagination Follow-up

### Observed issues

Manual inspection after page-number fidelity improvements showed that layout and
pagination fidelity were still imperfect:

- DOCX body reflow can create extra Word pages, causing dynamic PAGE fields to
  drift from original PDF page labels.
- Footer text and the page-number field were written as separate paragraphs even
  when their PDF bboxes shared the same bottom-line baseline.
- First-page top clipping remained a visual concern.

### Footer line grouping root cause

The internal plan had individual `footer_items` and `page_number_items`, and the
writer emitted one paragraph per item. For `input.pdf`, the left footer,
center page number, and right footer share the same vertical center, but the
writer produced three footer paragraphs. This made the page number appear one
line lower and added avoidable footer height.

### Implementation summary

- Added internal `header_line_groups` and `footer_line_groups` to the generation
  plan while preserving existing text/item fields.
- Footer line groups can combine footer text and page-number items only within
  the footer part when their y centers are close.
- Header items group only with header items.
- Line groups are sorted top-to-bottom; items are sorted left-to-right.
- The writer now uses one paragraph per line group.
- Grouped paragraphs use approximate center/right tab stops based on section
  writable width.
- `Page { PAGE }`, cached `123`, and `w:start="123"` remain preserved.
- Default conversion remains unchanged.
- Public CLI/API remains unchanged and closed.

### Pagination drift explanation

The Word PAGE field is dynamic Word pagination. It follows Word-generated page
breaks, not source PDF page boundaries. Preserving `Page 123` and
`w:start="123"` fixes the template and start number, but it cannot guarantee
source PDF page labels when DOCX body layout reflows. Exact source-label
preservation remains future work and likely requires stronger page-boundary
fidelity, a source-static/page-label mode, or per-page section mapping.

The plan summary now records:

- `page_number_semantics`: `word_dynamic`
- `page_number_drift_risk`: `depends_on_word_pagination`

### Clipping follow-up

- Generated header/footer paragraphs continue to normalize spacing before/after
  to 0.
- Generated header/footer XML does not contain unsafe exact line-height.
- Same-line footer grouping reduces footer paragraph count and footer height
  pressure.
- No broad header/footer distance rewrite was added because changing section
  margins can affect body layout and needs a separate explicit policy.

Ignored local investigation reports:

- `local_reports/header_footer_pagination_followup/footer-line-grouping-report.md`
- `local_reports/header_footer_pagination_followup/pagination-drift-root-cause.md`
- `local_reports/header_footer_pagination_followup/header-clipping-followup.md`

### Tests added

- Same-baseline footer text and page-number items group into one footer
  paragraph.
- Distinct footer y centers remain separate line groups.
- Header line grouping does not pollute footer XML.
- Plan summary documents dynamic Word PAGE semantics and drift risk.
- Existing clipping, style, role, and word-field tests still inspect
  role-specific OpenXML.

### Commands run

Focused regression command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "footer_line_grouping or pagination_drift or clipping or header_footer_fidelity or word_field"
```

Result: passed. 17 selected tests ran successfully.

Full layout analyzer tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 379 tests and 40 subtests ran successfully.

Compile check:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py test/test_layout_analyzer.py
```

Result: passed.

Whitespace check:

```bash
git diff --check
```

Result: passed.

Existing conversion tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

Local reviewed smoke:

```bash
.venv/bin/python local_reports/reviewed_migration_batch_compare/batch_compare_reviewed_migration.py --overwrite --allow-source-tree --page-number-behavior word_field --default-output-dir local_reports/header_footer_pagination_followup/smoke/output_docx_default --reviewed-output-dir local_reports/header_footer_pagination_followup/smoke/output_docx_reviewed --report-dir local_reports/header_footer_pagination_followup/smoke/reports --log-dir local_reports/header_footer_pagination_followup/smoke/logs
```

Result: passed. Reviewed converted count was 1 and failed count was 0.

Local OpenXML inspection confirmed:

- footer paragraph count: 1
- same paragraph contains left footer text, `Page ` prefix, PAGE field, cached
  `123`, and right footer text
- center/right tab stops are present
- literal `<PAGE_NUMBER>` is absent
- `w:pgNumType w:start="123"` is present
- unsafe exact line-height is absent

### Remaining limitations

- Dynamic PAGE labels can still drift when Word pagination differs from source
  PDF pagination.
- Exact PDF absolute positioning is not implemented.
- Static/source page-label mode is not implemented.
- Per-page section mapping is not implemented.
- Image/logo migration remains out of scope.

## Header Alignment and Pagination Blank-Page Follow-up

### Observed issues

Manual inspection after same-line grouping showed a mixed result:

- Footer grouping was much closer to the source layout.
- A single top-right header appeared shifted because header line grouping used
  the same tab-stop layout as multi-item footer lines.
- Pagination drift and possible blank pages still needed OpenXML inspection.
- First-page clipping remained a visual concern near the upper body/header
  boundary.

### Header alignment root cause

OpenXML inspection of the latest reviewed smoke output showed that
`word/header1.xml` contained one header paragraph with `w:jc w:val="left"`, a
right tab stop, and a leading tab run. That is appropriate for footer lines
with multiple horizontal zones, but too aggressive for a single right-aligned
header item.

### Implementation summary

- The internal DOCX writer now uses direct paragraph alignment for single-item
  or single-zone line groups.
- Tab-stop layout is reserved for multi-item line groups that span different
  horizontal zones.
- Footer same-line grouping remains tab-based for left/center/right footer
  content and page fields.
- Header/footer role separation remains unchanged.
- Default conversion remains unchanged.
- Public CLI/API remains unchanged and closed.

### Blank page and pagination investigation

OpenXML inspection found no explicit `w:br w:type="page"` page breaks and no
`w:pageBreakBefore` settings in the reviewed output. The document still
contains many section-property paragraphs and empty paragraphs, and the same
broad structure is present in default conversion output. This indicates the
pagination drift risk is mainly existing body/section layout reconstruction,
not a new reviewed header/footer writer page-break insertion.

Dynamic Word PAGE fields still follow Word pagination. If body reflow creates
extra Word pages, page labels can drift from source PDF page labels even when
the prefix and `w:start="123"` are preserved.

### First-page clipping investigation

The visually clipped upper content is present in `word/document.xml` body
content, not in the generated DOCX header part. Generated header/footer
paragraphs still use zero before/after spacing and avoid exact line-height.
No broad body-layout or margin patch was made in this phase.

Ignored local investigation reports:

- `local_reports/pagination_blank_page_followup/header-alignment-regression-report.md`
- `local_reports/pagination_blank_page_followup/blank-page-openxml-report.md`
- `local_reports/pagination_blank_page_followup/pagination-drift-analysis.md`

### Tests added

- Single right-aligned header line group writes a right-aligned header
  paragraph without unnecessary tab stops or leading tab runs.
- Single center header line group writes a center-aligned header paragraph.
- Multi-item same-line header groups still use tab-stop layout when horizontal
  zones differ.
- Existing footer same-line grouping and PAGE field tests continue to pass.

### Commands run

Focused regression command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "header_alignment or footer_line_grouping or pagination_drift or blank_page or clipping or word_field"
```

Result: passed. 15 selected tests ran successfully.

Full layout analyzer tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 382 tests and 40 subtests ran successfully.

Compile check:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py test/test_layout_analyzer.py
```

Result: passed.

Whitespace check:

```bash
git diff --check
```

Result: passed.

Existing conversion tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

Local reviewed smoke:

```bash
.venv/bin/python local_reports/reviewed_migration_batch_compare/batch_compare_reviewed_migration.py --overwrite --allow-source-tree --page-number-behavior word_field --default-output-dir local_reports/pagination_blank_page_followup/smoke/output_docx_default --reviewed-output-dir local_reports/pagination_blank_page_followup/smoke/output_docx_reviewed --report-dir local_reports/pagination_blank_page_followup/smoke/reports --log-dir local_reports/pagination_blank_page_followup/smoke/logs
```

Result: passed. Reviewed converted count was 1 and failed count was 0.

Latest local OpenXML inspection confirmed:

- header paragraph count: 1
- header alignment: `right`
- header tab-stop count: 0
- header leading tab runs: 0
- footer paragraph count: 1
- footer tab-stop layout remains present
- footer contains `Page ` prefix and PAGE field
- literal `<PAGE_NUMBER>` is absent
- `w:pgNumType w:start="123"` is present
- no explicit page breaks were introduced by reviewed migration

### Remaining limitations

- Dynamic PAGE labels can still drift when Word pagination differs from source
  PDF pagination.
- Existing body/section reconstruction can still create many section-property
  paragraphs and empty paragraphs.
- Exact PDF absolute positioning is not implemented.
- Static/source page-label mode is not implemented.
- Cross-page paragraph merge remains out of scope.

## Automatic Header/Footer Classification MVP

### Motivation

Manual review is not the final workflow for a high-quality converter. This
phase added an internal automatic decision layer that can classify repeated
boundary artifacts as `auto_exclude`, `auto_keep`, or `auto_diagnostic` without
changing default conversion behavior.

### Automatic classifier design

The classifier remains internal/local-only. It does not alter the existing
manual review parser and does not weaken reviewed filtering gates.

High-confidence `auto_exclude` requires:

- repeated evidence across enough pages
- top/bottom boundary-region evidence
- stable bbox y-band evidence
- consistent role-region mapping
- no body-region overlap
- no layout-placeholder signal
- no table/callout/list protection signal
- parseable consecutive page-number sequence for page-number migration

`auto_keep` protects body-like and structurally risky candidates. `auto_diagnostic`
records uncertain candidates without blocking conversion.

Only `auto_exclude` candidates are translated into a private dry-run override
plus generated `approve_exclude` decisions for the existing internal reviewed
filtering and DOCX header/footer plan. Public CLI/API remains closed and
`Converter.convert()` defaults remain unchanged.

### Implementation summary

- Added automatic classification helpers in `pdf2docx/page/LayoutAnalyzer.py`.
- Added an internal automatic migration plan helper that produces:
  - automatic decision report
  - transformed dry-run candidates for `auto_exclude` only
  - generated internal review decisions
  - reviewed filtering config with a private dry-run override
  - DOCX header/footer generation plan
- Added a private dry-run override pass-through for internal filtered-parse
  experiments in `LayoutAnalyzer.py` and `Pages.py`.
- Added a local-only ignored batch helper:
  `local_reports/automatic_reviewed_batch/auto_batch_convert.py`

### Tests added

- Repeated top header auto-excludes and writes to header XML.
- Repeated bottom footer auto-excludes and writes to footer XML.
- Consecutive `Page 123`, `Page 124`, `Page 125` auto-excludes as a page
  number and preserves `Page ` prefix, PAGE field, and start number.
- Body-heading similarity is protected.
- Weak `action=review` candidates remain diagnostic.
- Layout placeholders are never auto-excluded.
- Table/callout/list protection signals remain body/keep.
- Non-default or incomplete policy patterns fail closed for migration.
- Automatic filtered parse can run without a manual review file.
- Automatic summaries are JSON-serializable.

### Local smoke result

Command:

```bash
.venv/bin/python local_reports/automatic_reviewed_batch/auto_batch_convert.py --input-dir local_samples --allow-source-tree --overwrite --page-number-behavior word_field --max-pages 100 --verbose
```

Result:

- total PDFs considered: 7
- default converted: 6
- automatic reviewed converted: 3
- automatic diagnostic/skipped: 3
- blocked: 0
- skipped large: 1
- failed: 0

Converted automatically:

- `input.pdf`
- `input3.pdf`
- `subsets/input6_large_phase3d_subset.pdf`

Diagnostic/skipped:

- `input2.pdf`: no high-confidence auto-exclude candidates
- `input4.pdf`: no high-confidence auto-exclude candidates
- `input5.pdf`: no high-confidence auto-exclude candidates
- `input6_large.pdf`: skipped as a large document by local `--max-pages 100`

Ignored local artifacts:

- `local_reports/automatic_reviewed_batch/output_docx_default/`
- `local_reports/automatic_reviewed_batch/output_docx_auto_reviewed/`
- `local_reports/automatic_reviewed_batch/reports/`
- `local_reports/automatic_reviewed_batch/logs/batch_summary.json`
- `local_reports/automatic_reviewed_batch/logs/batch_summary.csv`

### Commands run

Focused regression command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "automatic_header_footer or auto_reviewed or header_footer_fidelity or page_number"
```

Result: passed. 35 selected tests ran successfully.

Full layout analyzer tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 389 tests and 40 subtests ran successfully.

Compile check:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py test/test_layout_analyzer.py
```

Result: passed.

Whitespace check:

```bash
git diff --check
```

Result: passed.

Existing conversion tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

Repository status check:

```bash
git status --short --ignored
```

Result: tracked changes were limited to code, tests, and docs. Local samples,
local reports, generated DOCX output, wheelhouse/dist/venv/cache artifacts, and
test outputs remained ignored.

### Current status

- Default conversion changed: no.
- Public CLI/API changed: no.
- Reviewed filtering default-on: no.
- Automatic mode public exposure: none.
- Manual review path: preserved.

### Remaining limitations

- Automatic promotion is conservative and still skips some local samples.
- Non-default policies remain fail-closed.
- Dynamic PAGE fields still follow Word pagination.
- Exact PDF page-label preservation remains future work when DOCX pagination
  drifts.
- Image/logo header/footer migration is not implemented.
- Cross-page paragraph merge remains out of scope.

## Automatic Header/Footer Classification v2

### Why v1 was insufficient

The first automatic classifier proved the internal path could avoid manual
review for simple repeated default-policy artifacts, but local inspection showed
two gaps:

- page-number recognition was too narrow and could miss common forms.
- odd/even header patterns were not surfaced clearly by the automatic layer.

The v2 policy is more permissive during candidate recognition while preserving
strict migration gates.

### Page-number classifier v2

The internal page-number parser now supports broader arabic page-label forms:

- bare numbers such as `123`
- labeled forms such as `Page 123`, `page 123`, `PAGE 123`, `p. 123`,
  `P. 123`
- decorated forms such as `- 123 -`, `— 123 —`, `123 |`, `| 123`
- total-page forms such as `Page 123 of 456` and `123 / 456`
- Korean-labeled forms such as `페이지 123`

Sequence inference now reports:

- `consecutive`
- `mostly_consecutive`
- `single_candidate`
- `not_sequence`

For `word_field`, supported consecutive sequences preserve prefix/suffix
metadata, insert a Word PAGE field, and carry the inferred start number for
`w:pgNumType`.

The classifier also fixed a protection-signal false positive where the word
`stable` was accidentally matching the substring `table`, causing real page
numbers to be kept as table-protected content.

### Odd/even handling

Automatic classification now detects strong odd/even header/footer patterns:

- source odd pages use one repeated boundary candidate
- source even pages use another repeated boundary candidate
- bbox and role-region evidence are stable
- body/layout-placeholder/table/callout/list protections are clean

The current writer remains default-policy-only. Therefore detected odd/even
candidates are reported as `auto_diagnostic` with
`odd_even_writer_not_supported`; they are not removed from the body and are not
written into odd/even DOCX parts yet.

### Tests added

- Broader page-number parser coverage for labels, decoration, total-page
  suffixes, and Korean labels.
- Consecutive, mostly-consecutive, single-candidate, and non-sequence page
  number inference.
- Automatic migration for decorated page-number labels with `word_field`.
- Automatic migration for `Page 123 of 456` preserving suffix around PAGE field.
- Body-region page-number-like text remains protected.
- Unstable page-number sequences remain diagnostic.
- Odd/even top headers are detected as diagnostic-only policy.
- Odd/even footers are detected as diagnostic-only policy.
- Alternating body headings are not treated as odd/even headers.
- The `stable`/`table` false-positive protection bug is covered.

### Local smoke result

Command:

```bash
.venv/bin/python local_reports/automatic_reviewed_batch/auto_batch_convert.py --input-dir local_reports/automatic_reviewed_batch_v2/input_pdf --default-output-dir local_reports/automatic_reviewed_batch_v2/output_docx_default --output-dir local_reports/automatic_reviewed_batch_v2/output_docx_auto_reviewed --report-dir local_reports/automatic_reviewed_batch_v2/reports --log-dir local_reports/automatic_reviewed_batch_v2/logs --allow-source-tree --overwrite --page-number-behavior word_field --max-pages 100 --verbose
```

Result:

- total PDFs: 5
- default converted: 5
- automatic reviewed converted: 2
- automatic diagnostic/skipped: 3
- blocked: 0
- skipped large: 0
- failed: 0

Files converted automatically:

- `input.pdf`
- `input3.pdf`

Files remaining diagnostic:

- `input2.pdf`: footer and page-number candidates were recognized as
  `auto_exclude`, but migration stayed diagnostic because the internal default
  policy plan had incomplete page coverage.
- `input4.pdf`: no high-confidence semantic auto-exclude candidate.
- `input5.pdf`: no high-confidence semantic auto-exclude candidate.

Observed improvement:

- `input.pdf` now auto-excludes one page-number candidate in addition to
  header/footer candidates.
- `input2.pdf` now recognizes footer plus page-number candidates as
  `auto_exclude`, but strict policy coverage blocks DOCX migration.

Ignored local artifacts:

- `local_reports/automatic_reviewed_batch_v2/input_pdf/`
- `local_reports/automatic_reviewed_batch_v2/output_docx_default/`
- `local_reports/automatic_reviewed_batch_v2/output_docx_auto_reviewed/`
- `local_reports/automatic_reviewed_batch_v2/reports/`
- `local_reports/automatic_reviewed_batch_v2/logs/`

### Commands run

Focused regression command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "automatic_header_footer or auto_reviewed or page_number_template or odd_even or header_footer_fidelity"
```

Result: passed. 29 selected tests and 9 subtests ran successfully.

Full layout analyzer tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 398 tests and 49 subtests ran successfully.

Compile check:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py test/test_layout_analyzer.py
```

Result: passed.

Whitespace check:

```bash
git diff --check
```

Result: passed.

Existing conversion tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

### Current status

- Default conversion changed: no.
- Public CLI/API changed: no.
- Reviewed filtering default-on: no.
- Automatic mode public exposure: none.
- Manual review code path: preserved.

### Remaining limitations

- Odd/even writing is still not implemented; detection is diagnostic-only.
- Incomplete default-policy coverage still blocks migration.
- Dynamic PAGE fields still follow Word pagination.
- Exact source PDF page-label preservation remains future work if pagination
  drifts.
- Image/logo header/footer migration is not implemented.
- Cross-page paragraph merge remains out of scope.

## Automatic Header/Footer Classification v3

### Why v3 was needed

Classifier v2 still relied too heavily on global page coverage. That caused
common book/manual patterns to remain diagnostic when a candidate was expected
to appear only on odd pages, only on even pages, or on every page except the
first. Page numbers also needed sequence-family reasoning because visible page
number text changes on every page and can alternate left/right by page parity.

### Implementation summary

- Added applicable-page coverage metadata for `all_pages`,
  `all_pages_except_first`, `odd_pages`, `even_pages`, `odd_even_pair`,
  `contiguous_range`, and `sparse_or_unstable`.
- Automatic decisions now use applicable support ratio rather than only global
  support ratio.
- Added parity-aware page-number sequence inference with
  `parity_consecutive`, `odd_alignment`, `even_alignment`, and
  `coverage_policy`.
- Preserved parity-specific metadata when translating automatic decisions into
  the existing reviewed migration gate.
- Added internal DOCX writer support for `odd_even` policies using Word
  odd/even header/footer parts.
- Added internal support for `first_page_excluded_default` by enabling an empty
  first-page header/footer while writing the repeated later-page default part.
- Default `Converter.convert()` behavior remains unchanged.
- Public CLI/API remains closed.

### Tests added

- Applicable-page coverage classification for all-page, first-page-excluded,
  odd-page, and sparse candidates.
- Strong odd/even header migration into separate Word header parts.
- Strong odd/even footer migration into separate Word footer parts.
- Parity-alternating page-number sequence migration using `word_field`.
- Existing same-line footer grouping, style, word-field, body protection, and
  conversion regressions continue to pass.

### Local v3 smoke

Command:

```bash
.venv/bin/python local_reports/automatic_reviewed_batch/auto_batch_convert.py --input-dir local_reports/automatic_reviewed_batch_v3/input_pdf --default-output-dir local_reports/automatic_reviewed_batch_v3/output_docx_default --output-dir local_reports/automatic_reviewed_batch_v3/output_docx_auto_reviewed --report-dir local_reports/automatic_reviewed_batch_v3/reports --log-dir local_reports/automatic_reviewed_batch_v3/logs --page-number-behavior word_field --allow-source-tree --overwrite --max-pages 100
```

Result:

- total PDFs: 5
- default converted: 5
- automatic reviewed converted: 2
- automatic diagnostic/skipped: 3
- blocked: 0
- skipped large: 0
- failed: 0

Automatic reviewed outputs:

- `local_reports/automatic_reviewed_batch_v3/output_docx_auto_reviewed/input.docx`
- `local_reports/automatic_reviewed_batch_v3/output_docx_auto_reviewed/input3.docx`

Input3 investigation:

- The all-page footer migrated safely.
- The page-number-like top `8` family was not migrated because it was a
  non-consecutive top-region numeric family with unstable y-band evidence.
- Odd/even top header coverage was detected, but the odd-side header y-band was
  unstable, so the pair remained diagnostic.
- Reports were written under
  `local_reports/automatic_reviewed_batch_v3/input3-investigation/`.

### Commands run

Focused regression command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "applicable_page or automatic_header_footer or page_number or odd_even"
```

Result: passed. 46 selected tests and 15 subtests ran successfully.

Full layout analyzer tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 402 tests and 47 subtests ran successfully.

Compile check:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py test/test_layout_analyzer.py
```

Result: passed.

Whitespace check:

```bash
git diff --check
```

Result: passed.

Existing conversion tests:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

### Current status

- Default conversion changed: no.
- Public CLI/API changed: no.
- Reviewed filtering default-on: no.
- Automatic mode public exposure: none.
- Odd/even writer support: internal-only.

### Remaining limitations

- `input3.pdf` still has diagnostic header/page-number families because the
  available evidence was not strong enough for safe migration.
- Section-scoped policy remains diagnostic/fail-closed.
- Full first-page different content writing remains out of scope; only
  first-page-excluded default repetition is supported internally.
- Dynamic PAGE fields still follow Word pagination.
- Exact source PDF page-label preservation remains future work if pagination
  drifts.
- Image/logo header/footer migration is not implemented.
- Cross-page paragraph merge remains out of scope.

## Automatic Header/Footer Classification v4

### Why v3 was insufficient

Classifier v3 still relied too much on repeated dry-run candidates. In the
`input3.pdf` local sample, the real source page labels appeared as bottom
boundary strings such as `8-1`, `8-2`, and `8-3`. These labels changed on every
page and could be mixed into a broader `<page_number>` fingerprint with an
unrelated bottom-region number. As a result, the repeated candidate looked
non-consecutive and unstable.

### Implementation summary

- Added top-region page-number targeting: top page numbers map to DOCX header
  parts, bottom page numbers map to DOCX footer parts.
- Added chapter-prefixed page-label parsing such as `8-1` as prefix `8-` plus
  dynamic `PAGE`.
- Added automatic boundary page-number family generation from `page_summaries`
  even when no repeated dry-run candidate exists.
- Added combined source-offset/page-index sequence evidence for changing
  page-label text.
- Added block-level filter refs so a generated page-number family can remove
  only the exact source blocks it owns, not unrelated numeric blocks sharing the
  same normalized fingerprint.
- Preserved all-page header/footer text in both odd/even Word parts when
  parity-specific page numbers force an `odd_even` writer policy.
- Kept top running-head candidates diagnostic when first-page title content is
  mixed into the same family and safe odd/even first-page-excluded running-head
  writing is not yet implemented.

### Local v4 smoke

Command:

```bash
.venv/bin/python local_reports/automatic_reviewed_batch/auto_batch_convert.py --input-dir local_samples --default-output-dir local_reports/automatic_reviewed_batch_v4/output_docx_default --output-dir local_reports/automatic_reviewed_batch_v4/output_docx_auto_reviewed --report-dir local_reports/automatic_reviewed_batch_v4/reports --log-dir local_reports/automatic_reviewed_batch_v4/logs --page-number-behavior word_field --allow-source-tree --overwrite
```

Result:

- total PDFs considered: 7, including an ignored subset PDF under
  `local_samples/subsets/`
- default converted: 6
- automatic reviewed converted: 3
- automatic diagnostic/skipped: 3
- blocked: 0
- skipped large: 1
- failed: 0

Core local samples:

- `input.pdf`: converted automatic reviewed, unchanged high-quality result.
- `input2.pdf`: diagnostic only; no safe auto-exclude candidates.
- `input3.pdf`: converted automatic reviewed; bottom `8-1`..`8-5` page labels
  now migrate as odd/even footer PAGE fields with prefix `8-` and start number
  `1`.
- `input4.pdf`: diagnostic only; no safe auto-exclude candidates.
- `input5.pdf`: diagnostic only; no safe auto-exclude candidates.
- `input6_large.pdf`: skipped as large/bounded-only.

Input3 investigation reports:

- `local_reports/automatic_reviewed_batch_v4/input3-investigation/top-page-number-family-report.md`
- `local_reports/automatic_reviewed_batch_v4/input3-investigation/running-head-family-report.md`
- `local_reports/automatic_reviewed_batch_v4/input3-investigation/robust-geometry-report.md`
- `local_reports/automatic_reviewed_batch_v4/input3-investigation/v3-v4-decision-comparison.md`

### Commands run

Focused regression commands:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "running_head or robust_geometry or applicable_page or automatic_header_footer or page_number or odd_even"
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "dirty_page_number_fingerprint_family or boundary_page_number_family or page_number or automatic_header_footer"
```

Result: passed. The primary v4 focused selector ran 53 tests plus 15 subtests.

Full verification commands:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py test/test_layout_analyzer.py
git diff --check
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
git status --short --ignored
```

Result:

- `test/test_layout_analyzer.py`: passed, 409 tests plus 47 subtests.
- `py_compile`: passed.
- `git diff --check`: passed.
- `test/test.py::TestConversion`: passed, 5 tests.
- `git status --short --ignored`: only related tracked files were modified;
  local reports, local samples, generated build artifacts, venvs, and caches
  remained ignored.

### Current status

- Default conversion changed: no.
- Public CLI/API changed: no.
- Automatic mode public exposure: none.
- Local v4 smoke generated ignored DOCX outputs only.

### Remaining limitations

- `input3.pdf` top odd/even running headers remain diagnostic because page 1
  shares text with a first-page title at a different y band.
- Safe odd/even first-page-excluded running-head writing remains future work.
- Dynamic Word PAGE fields still follow Word pagination, not source PDF page
  boundaries.
- Section-scoped policy, image/logo migration, and paragraph continuation merge
  remain out of scope.

## Automatic Layout Fidelity v5

### Observed v4 issues

Manual inspection of the v4 `input3.docx` showed that structural page-number
migration was incomplete:

- Bottom `8-1`..`8-5` page labels were represented as footer PAGE fields, but
  the source labels also remained in `word/document.xml`.
- Literal `<PAGE_NUMBER>` placeholders appeared in `word/header*.xml` even
  though input3 page labels belonged in the footer.
- Pagination still drifted, and the body area needed a conservative
  source-geometry-based review before promoting more odd/even running heads.

### Root cause

The automatic v4 synthetic page-number family correctly carried exact
`filter_block_refs`, but raw-object mapping still built expected blocks from a
single `approved_by_fingerprint` mapping and did not honor
`filter_fingerprints`/`filter_block_refs`. The filtered parse therefore removed
the shared footer text but not the synthetic page-label refs.

The header placeholder came from the writer fallback path: an explicitly empty
`odd_header_page_number_items` list was treated the same as a missing legacy
field list, causing `page_number_placeholders` to fall back into header parts.

### Implementation summary

- Raw-object expected mapping now honors approved candidates' exact
  `filter_fingerprints` and `filter_block_refs`.
- Added internal migrated source-block accounting for planned refs, removed
  refs, unexpected removals, parsed/body residuals, and DOCX body residuals.
- Added fail-closed writer invariants for `word_field` mode:
  literal page-number placeholders must not be written, and actual
  header/footer PAGE field counts must match expected structured item counts.
- Changed the DOCX writer item fallback so an explicitly present empty split
  item list remains empty instead of falling back to legacy placeholders.
- Added a conservative body-area plan based on detected header/footer extents,
  bounded safety gaps, and nonzero top/bottom margin limits. This is applied
  only by the internal header/footer writer helper.

### Local v5 smoke

Command:

```bash
.venv/bin/python local_reports/automatic_reviewed_batch/auto_batch_convert.py --input-dir local_reports/automatic_layout_fidelity_v5/input_pdf --default-output-dir local_reports/automatic_layout_fidelity_v5/output_docx_default --output-dir local_reports/automatic_layout_fidelity_v5/output_docx_auto_reviewed --report-dir local_reports/automatic_layout_fidelity_v5/reports --log-dir local_reports/automatic_layout_fidelity_v5/logs --page-number-behavior word_field --allow-source-tree --overwrite
```

Result:

- total PDFs considered: 5 (`input.pdf` through `input5.pdf`)
- default converted: 5
- automatic reviewed converted: 2 (`input.pdf`, `input3.pdf`)
- automatic diagnostic/skipped: 3 (`input2.pdf`, `input4.pdf`, `input5.pdf`)
- blocked: 0
- failed: 0

Input3 v5 OpenXML/accounting result:

- planned source refs: 10
- matched/removed source refs: 10
- DOCX body residual count for migrated source labels: 0
- `8-1` through `8-5` body counts: 0
- header PAGE field count: 0
- footer PAGE field count: 2
- header/footer literal placeholder count: 0
- explicit page break count: 0
- `pageBreakBefore` count: 0
- section break count: 5
- empty paragraph count: 23
- consecutive empty paragraph count: 5
- trailing table paragraph indicator: 1

Ignored input3 investigation reports:

- `local_reports/automatic_layout_fidelity_v5/input3-investigation/body-area-and-pagination-report.md`
- `local_reports/automatic_layout_fidelity_v5/input3-investigation/page-number-source-removal-report.md`
- `local_reports/automatic_layout_fidelity_v5/input3-investigation/page-field-routing-report.md`
- `local_reports/automatic_layout_fidelity_v5/input3-investigation/odd-even-running-head-report.md`

### Commands run

Focused regression command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "body_area or pagination or source_removal or page_field_routing or page_number or odd_even or automatic_header_footer"
```

Result: passed, 56 tests plus 15 subtests.

Full verification commands:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py test/test_layout_analyzer.py
git diff --check
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
git status --short --ignored
```

Result: pending final verification.

Final result:

- `test/test_layout_analyzer.py`: passed, 412 tests plus 47 subtests.
- `py_compile`: passed.
- `git diff --check`: passed.
- `test/test.py::TestConversion`: passed, 5 tests.
- Final `git status --short --ignored`: tracked changes were limited to the
  internal helper/writer code, focused tests, and committed documentation;
  generated/local reports and smoke outputs remained ignored.

### Current status

- Default conversion changed: no.
- Public CLI/API changed: no.
- Automatic mode public exposure: none.
- Local v5 smoke generated ignored DOCX outputs only.

### Remaining limitations

- Word PAGE fields still follow Word pagination, so exact source page-label
  fidelity depends on controlling body pagination.
- input3 odd/even running heads remain diagnostic until parity safety is
  reliable enough.
- Empty paragraphs, section breaks, and trailing table paragraphs remain the
  most likely next pagination-drift investigation targets.

## First Page Body Clipping Investigation

### Observed issue

Manual inspection of the best local static anchored `input.docx` showed the
first-page body title `CHAPTER 13 HEADERS AND FOOTERS` clipped near the top.
This was investigated before packaging because static anchored header/footer
quality was otherwise suitable for closed-network inspection.

### OpenXML and PDF result

The title text is in `word/document.xml` as a normal body paragraph:

- docx part: `word/document.xml`
- container: paragraph
- header/footer content: no
- table cell/textbox/frame: no
- largest title run font size: 28 pt
- paragraph line spacing: 10.3 pt
- line spacing rule: exact
- line-height/font ratio: 0.368

PyMuPDF inspection of the source first page showed the corresponding PDF title
line had an approximately 32 pt bbox height with a 28 pt largest glyph. The
DOCX exact line-height was therefore much smaller than the actual text and was
the likely clipping cause.

Ignored local reports:

- `local_reports/body_clipping_investigation/chapter-title-location-report.md`
- `local_reports/body_clipping_investigation/chapter-title-bbox-vs-docx-report.md`
- `local_reports/body_clipping_investigation/chapter-title-clipping-root-cause.md`
- `local_reports/body_clipping_investigation/variant-validation-report.md`
- `local_reports/body_clipping_investigation/final-recommendation.md`

### Implementation summary

Added a narrow internal TextBlock guard for exact line spacing. Exact line
spacing remains unchanged when it is safely larger than the paragraph's maximum
run font size. When exact spacing is less than `max_font_size * 1.15`, the
writer now uses Word `atLeast` line spacing of `max_font_size * 1.25`.

This is a body text clipping guard, not a header/footer migration change.

### Tests added

- Exact 10.3 pt line spacing with 28 pt text is relaxed to 35 pt `atLeast`.
- Safe exact spacing remains exact.
- A synthetic TextBlock writes `w:lineRule="atLeast"` and `w:line="700"` for
  the clipping-risk large-title case.

### Local variants

Generated ignored local variants:

- `local_reports/body_clipping_investigation/variants/input.fix-line-spacing.docx`
- `local_reports/body_clipping_investigation/variants/input.fix-title-padding.docx`
- `local_reports/body_clipping_investigation/variants/input.fix-body-top-safe-gap.docx`

OpenXML validation found no header/footer hash changes, no Word PAGE fields in
static mode, no literal page-number placeholders, no source-label body
residuals, and no paragraph/section/page-break count increase.

LibreOffice/soffice was not available locally, so render-based visual
verification was skipped. Manual Word inspection remains recommended.

### Commands run

Focused command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "clipping or line_height or body_top"
```

Result: passed, 4 tests.

Full verification:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/text/TextBlock.py test/test_layout_analyzer.py
git diff --check
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
git status --short --ignored
```

Result:

- `test/test_layout_analyzer.py`: passed, 415 tests plus 47 subtests.
- `py_compile`: passed.
- `git diff --check`: passed.
- `test/test.py::TestConversion`: passed, 5 tests.

### Status

- Default conversion changed: yes, narrowly for clipping-risk exact
  line-height body paragraphs.
- `Converter.convert()` API/default invocation changed: no.
- Public CLI/API changed: no.
- Header/footer static anchored behavior changed: no.
- Recommended next step: regenerate closed-network wheel smoke outputs after
  manual inspection confirms the fixed first-page title no longer clips.

## Static Anchored Internal Helper Promotion

### Goal

Promote the successful local static anchored v5 prototype into tracked
internal code so it can be used by a private wrapper and later wheel smoke
testing, without changing default conversion or exposing a public CLI/API.

### Local evidence

The revalidation root was:

- `local_reports/static_anchored_v5_after_clipping_fix/`

The local revalidation produced static anchored outputs for `input.pdf`,
`input2.pdf`, `input3.pdf`, `input4.pdf`, and `input5.pdf`. Static mode safety
counts were clean:

- Word PAGE field count: 0
- literal `<PAGE_NUMBER>` count: 0
- source label body residual count: 0
- duplicate header/footer text count: 0
- multi-zone missing count: 0
- mispositioned static label count: 0
- variable family page text mismatch count: 0
- last token reuse: false

The first-page title clipping recheck also confirmed the regenerated
`input.pdf` body title paragraph used `w:line="700"` with
`w:lineRule="atLeast"`.

### Implementation summary

Added tracked internal modules under `pdf2docx/static_anchored/`:

- `analyzer.py`: source-page visual family detection, static label records,
  variable family detection, coverage policies, source refs, and internal
  filtering config generation.
- `writer.py`: source-page section header/footer static text writer with
  left/center/right tab-stop grouping and style hints.
- `validator.py`: OpenXML safety validation for static mode.
- `converter.py`: internal PDF-to-DOCX facade that uses the existing reviewed
  filtered-parse hook, applies static anchored headers/footers, and validates
  before writing final output.

Added tracked internal script:

```bash
python -m scripts.internal.static_anchored_convert --input input.pdf --output input.docx --report input.report.json
```

The script is not registered as a public console entry point.

### Synthetic tests added

- Three-zone footer preservation.
- Left/right footer right-tab preservation.
- Static page label preservation.
- Chapter-prefixed label preservation.
- Variable footer family per-source-page ownership.
- Delayed every-other variable family detection.
- Last-token reuse detection.
- Source-label body residual detection.
- Static-mode PAGE field rejection.
- Literal `<PAGE_NUMBER>` rejection.
- Multi-zone missing detection.
- Mispositioned static label detection.
- Mode selector recommendation for representative input/input2/input3/input4/input5-style fixtures.

### Commands run

Focused command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "static_anchored or static_visual or source_page_fidelity or variable_family or multi_zone or delayed"
```

Result: passed, 13 tests.

Script help:

```bash
.venv/bin/python -m scripts.internal.static_anchored_convert --help
```

Result: passed.

Internal script smoke:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m scripts.internal.static_anchored_convert --input local_reports/static_anchored_internal_smoke/static-anchored-smoke.pdf --output local_reports/static_anchored_internal_smoke/static-anchored-smoke.docx --report local_reports/static_anchored_internal_smoke/static-anchored-smoke.report.json --markdown-report local_reports/static_anchored_internal_smoke/static-anchored-smoke.report.md --overwrite
```

Result: passed, status `converted`. The synthetic PDF/DOCX/report remained
under ignored `local_reports/`.

Full verification:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/page/LayoutAnalyzer.py pdf2docx/page/Pages.py pdf2docx/common/docx.py pdf2docx/text/TextBlock.py pdf2docx/static_anchored/__init__.py pdf2docx/static_anchored/analyzer.py pdf2docx/static_anchored/writer.py pdf2docx/static_anchored/validator.py pdf2docx/static_anchored/converter.py test/test_layout_analyzer.py scripts/internal/static_anchored_convert.py
git diff --check
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
git status --short --ignored
```

Result:

- `test/test_layout_analyzer.py`: passed, 428 tests plus 47 subtests.
- `py_compile`: passed.
- `git diff --check`: passed.
- `test/test.py::TestConversion`: passed, 5 tests.

### Status

- Default `Converter.convert()` behavior changed: no.
- Public CLI/API changed: no.
- Public console script exposed: no.
- Generated local DOCX/reports committed: no.
- Next step: private/offline wheel packaging smoke using the internal helper.

## Packaging Phase 6B: Static Anchored Wheel Smoke

### Scope

Verified that the internal static anchored helper can be imported and executed
from an installed wheel in a fresh environment outside the checkout source
tree.

The default `Converter.convert()` behavior remains unchanged, and no public
CLI/API or console script was exposed.

### Packaging metadata result

- `setup.py` uses `find_packages(...)`, so `pdf2docx.static_anchored` is
  included in the wheel.
- `scripts/internal/static_anchored_convert.py` is source-tree convenience
  only; top-level `scripts/` is not packaged.
- Added packaged internal module entrypoint:

```bash
python -m pdf2docx.static_anchored.cli --input input.pdf --output input.docx --report input.report.json
```

The source-tree wrapper now delegates to that packaged module. No public
`console_scripts` entry was added.

### Wheel build and contents

Command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m build --wheel
```

Result: passed.

Wheel:

```text
dist/pdf2docx-0.5.13-py3-none-any.whl
```

Wheel contents check confirmed:

```text
pdf2docx/static_anchored/__init__.py
pdf2docx/static_anchored/analyzer.py
pdf2docx/static_anchored/cli.py
pdf2docx/static_anchored/converter.py
pdf2docx/static_anchored/validator.py
pdf2docx/static_anchored/writer.py
```

### Fresh wheel install smoke

Fresh venv:

```text
.venv-static-wheel-smoke/
```

Install command:

```bash
.venv-static-wheel-smoke/Scripts/python.exe -m pip install dist/*.whl
```

Import smoke was run from `/tmp`; imports resolved to installed
`site-packages`, not the checkout source tree:

```text
D:\Workspaces\Codex\pdf2docx\.venv-static-wheel-smoke\Lib\site-packages\pdf2docx\__init__.py
D:\Workspaces\Codex\pdf2docx\.venv-static-wheel-smoke\Lib\site-packages\pdf2docx\static_anchored\__init__.py
D:\Workspaces\Codex\pdf2docx\.venv-static-wheel-smoke\Lib\site-packages\pdf2docx\static_anchored\cli.py
```

### Installed static anchored conversion smoke

Command shape:

```bash
python -m pdf2docx.static_anchored.cli \
  --input <pdf> \
  --output <docx> \
  --report <json> \
  --markdown-report <md> \
  --overwrite
```

Committed sample:

- `test/samples/demo.pdf`: `diagnostic_only`,
  `no_static_source_page_candidates`.

Local sample results from installed wheel:

- `local_samples/input.pdf`: `converted`.
- `local_samples/input2.pdf`: `converted`.
- `local_samples/input3.pdf`: `converted`.
- `local_samples/input4.pdf`: `converted`.
- `local_samples/input5.pdf`: `converted`.
- `local_samples/input6_large.pdf`: skipped.

Ignored output root:

```text
local_reports/static_anchored_wheel_smoke/
```

Static-mode safety counts for the five local samples:

- `word_PAGE_field_count`: 0.
- `literal_PAGE_NUMBER_placeholder_count`: 0.
- `source_label_body_residual_count`: 0.
- `duplicate_header_footer_text_count`: 0.
- `missing_zone_count`: 0.
- `mispositioned_static_label_count`: 0.
- `variable_family_page_text_mismatch_count`: 0.
- `last_token_reuse_detected`: `false`.

For `input.pdf`, the first-page title clipping guard remains present in
OpenXML:

```text
w:line="700"
w:lineRule="atLeast"
```

For `input4.pdf`, per-source-page variable footer ownership remained correct
for `__1`, `__2`, `__3`, and `__4`.

For `input5.pdf`, delayed/every-other static visual family ownership remained
valid with no page-text mismatch.

### Smoke fix

The first installed-wheel pass revealed a validator false positive for
`input2.pdf`: static label `Page i` was counted inside ordinary body text such
as `Page is`. The fix was intentionally narrow:

- `source_label_body_residuals()` now counts residual labels with
  alphanumeric boundary guards.
- A synthetic regression test verifies that `Page i` is not counted inside
  `Odd Page is...`.
- The existing positive residual test still detects a true body residual.

This did not change default conversion behavior or expose a public API.

### Wheelhouse smoke

Wheelhouse command:

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pip wheel -w wheelhouse .
```

Fresh offline-style venv:

```text
.venv-static-wheelhouse-smoke/
```

Install command:

```bash
.venv-static-wheelhouse-smoke/Scripts/python.exe -m pip install --no-index --find-links wheelhouse pdf2docx
```

Result: passed. Import smoke from `/tmp` resolved to
`.venv-static-wheelhouse-smoke/.../site-packages`.

Conversion smoke:

- input: `local_samples/input4.pdf`.
- status: `converted`.
- all static-mode safety counts above were 0/false as expected.

The wheelhouse contains platform/Python-version-specific dependency wheels
such as PyMuPDF, NumPy, lxml, and OpenCV. It must be rebuilt for the target
closed-network Python/platform.

### Commands run

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pip install --upgrade build wheel setuptools
rm -rf build dist *.egg-info pdf2docx.egg-info
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m build --wheel
rm -rf .venv-static-wheel-smoke
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m venv .venv-static-wheel-smoke
.venv-static-wheel-smoke/Scripts/python.exe -m pip install --upgrade pip
.venv-static-wheel-smoke/Scripts/python.exe -m pip install dist/*.whl
cd /tmp && /mnt/d/Workspaces/Codex/pdf2docx/.venv-static-wheel-smoke/Scripts/python.exe -c "import pdf2docx, pdf2docx.static_anchored, pdf2docx.static_anchored.cli; print(pdf2docx.__file__); print(pdf2docx.static_anchored.__file__); print(pdf2docx.static_anchored.cli.__file__)"
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pip wheel -w wheelhouse .
rm -rf .venv-static-wheelhouse-smoke
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m venv .venv-static-wheelhouse-smoke
.venv-static-wheelhouse-smoke/Scripts/python.exe -m pip install --no-index --find-links wheelhouse pdf2docx
```

Full regression commands are listed in the final Phase 6B verification run.

## Packaging Phase 6C: Closed-Network Import Bundle

### Scope

Prepared a closed-network import bundle for the internal static anchored helper.

The default `Converter.convert()` behavior remains unchanged. No public
CLI/API, public `console_scripts` entry point, or PyPI publish happened during
bundle creation.

### Bundle path

Ignored local bundle root:

```text
local_dist/pdf2docx-static-anchored-bundle/
```

Created structure:

```text
wheels/
wheelhouse/
scripts/
samples/
docs/
reports/
README.md
MANIFEST.json
SHA256SUMS.txt
```

The bundle directory is ignored by `.gitignore` and was not committed.

### Bundle contents

Project wheel:

```text
wheels/pdf2docx-0.5.13-py3-none-any.whl
```

Dependency wheelhouse:

- 10 wheels total, including the project wheel and runtime dependencies.
- Platform/Python target: Windows AMD64 / Python 3.12 dependency wheels.

Scripts:

```text
scripts/install_offline.sh
scripts/install_offline.ps1
scripts/smoke_static_anchored.py
scripts/smoke_static_anchored.sh
scripts/static_anchored_convert.py
```

Committed-safe sample:

```text
samples/demo.pdf
```

`demo.pdf` is for install/import smoke only and is expected to report
`diagnostic_only` because it has no static source-page candidates.

### Bundle install command

Manual offline install:

```bash
python -m venv .venv-pdf2docx-static
.venv-pdf2docx-static/bin/python -m pip install --no-index --find-links wheelhouse pdf2docx
```

Windows manual install:

```powershell
python -m venv .venv-pdf2docx-static
.venv-pdf2docx-static\Scripts\python.exe -m pip install --no-index --find-links wheelhouse pdf2docx
```

Bundle helper:

```bash
scripts/install_offline.sh
```

### Bundle smoke command

Internal module command:

```bash
python -m pdf2docx.static_anchored.cli \
  --input input.pdf \
  --output output.docx \
  --report output.report.json \
  --markdown-report output.report.md \
  --overwrite
```

Bundle smoke wrapper:

```bash
python scripts/smoke_static_anchored.py \
  --input samples/demo.pdf \
  --output reports/demo.static.docx \
  --report reports/demo.static.report.json \
  --allow-diagnostic \
  --overwrite
```

### Manifest and checksums

Created:

```text
local_dist/pdf2docx-static-anchored-bundle/MANIFEST.json
local_dist/pdf2docx-static-anchored-bundle/SHA256SUMS.txt
```

`MANIFEST.json` records:

- creation time
- git commit
- Python version used
- platform
- project wheel name, size, and sha256
- dependency wheel list with size and sha256
- internal module command
- Phase 6B smoke summary
- Phase 6C bundle smoke summary

Checksum verification:

```bash
cd local_dist/pdf2docx-static-anchored-bundle
sha256sum -c SHA256SUMS.txt
```

Result: passed for all 28 bundle files.

### Closed-bundle install smoke

Fresh venv:

```text
.venv-closed-bundle-smoke/
```

Install command:

```bash
.venv-closed-bundle-smoke/Scripts/python.exe -m pip install --no-index --find-links local_dist/pdf2docx-static-anchored-bundle/wheelhouse pdf2docx
```

Result: passed.

Import smoke was run from `/tmp`; imports resolved to:

```text
.venv-closed-bundle-smoke\Lib\site-packages\pdf2docx\__init__.py
.venv-closed-bundle-smoke\Lib\site-packages\pdf2docx\static_anchored\__init__.py
.venv-closed-bundle-smoke\Lib\site-packages\pdf2docx\static_anchored\cli.py
```

Quality conversion smoke:

- input: `local_samples/input4.pdf`
- output:
  `local_dist/pdf2docx-static-anchored-bundle/reports/input4.bundle-smoke.docx`
- status: `converted`
- warnings: none

Static-mode validation:

- `word_PAGE_field_count`: 0
- `literal_PAGE_NUMBER_placeholder_count`: 0
- `source_label_body_residual_count`: 0
- `duplicate_header_footer_text_count`: 0
- `missing_zone_count`: 0
- `mispositioned_static_label_count`: 0
- `variable_family_page_text_mismatch_count`: 0
- `last_token_reuse_detected`: `false`
- `safety_gate_passed`: `true`

Bundle smoke runner:

- input: `samples/demo.pdf`
- status: `diagnostic_only`
- warnings: `no_static_source_page_candidates`
- result: accepted with `--allow-diagnostic`.

### Remaining closed-network steps

- Rebuild the wheelhouse for each target Python/platform combination.
- Transfer the bundle with `MANIFEST.json` and `SHA256SUMS.txt`.
- Verify checksums in the closed network.
- Install into a fresh venv with `--no-index --find-links wheelhouse`.
- Run import smoke from outside any source checkout.
- Run static anchored conversion smoke on an approved representative PDF.
- Perform visual QA in Word/LibreOffice or an approved renderer.

## Initial PC Static Anchored Recheck

Date: 2026-06-08.

Purpose: revalidate the static anchored v5/internal helper after returning to
the initial PC, using the latest code already pushed to GitHub plus copied
ignored local samples/reports/bundle artifacts.

### Repository state

- Current HEAD: `68f4980 docs: document closed-network static anchored bundle`.
- Branch: `master` tracking `origin/master`.
- `git pull` was not needed because local `master` matched `origin/master`.
- Recent commit history included:
  - `feat: add internal static anchored conversion helper`
  - `fix: package static anchored internal entrypoint`
  - `docs: document closed-network static anchored bundle`
  - `fix: reduce first page body title clipping`

Ignored local artifacts remained ignored:

- `local_samples/`
- `local_reports/`
- `local_dist/`
- `.venv/`
- generated caches and test outputs

### Environment

Python:

```text
/usr/bin/python3
Python 3.10.12
```

The system `python3 -m venv .venv` command failed because `ensurepip` /
`python3.10-venv` was unavailable and `sudo` required a password. To keep a
fresh venv without changing system packages, `virtualenv` was installed in the
user environment and used only as a local environment creation tool.

Actual test Python:

```text
.venv/bin/python
```

### Local samples

Required samples were present:

- `local_samples/input.pdf`
- `local_samples/input2.pdf`
- `local_samples/input3.pdf`
- `local_samples/input4.pdf`
- `local_samples/input5.pdf`

`local_samples/input6_large.pdf` was also present but was not part of this
five-sample recheck.

### Static anchored tests

Commands run:

```bash
.venv/bin/python -m pdf2docx.static_anchored.cli --help
```

Result: passed. The internal module CLI help was available.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py -k "static_anchored or static_visual or source_page_fidelity or variable_family or multi_zone or delayed"
```

Result: passed. 14 selected tests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test_layout_analyzer.py
```

Result: passed. 429 tests and 47 subtests ran successfully.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m py_compile pdf2docx/static_anchored/__init__.py pdf2docx/static_anchored/analyzer.py pdf2docx/static_anchored/writer.py pdf2docx/static_anchored/validator.py pdf2docx/static_anchored/converter.py pdf2docx/static_anchored/cli.py scripts/internal/static_anchored_convert.py pdf2docx/text/TextBlock.py test/test_layout_analyzer.py
```

Result: passed.

```bash
git diff --check
```

Result: passed.

```bash
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pytest -q test/test.py::TestConversion
```

Result: passed. 5 conversion tests ran successfully.

### Local sample recheck

Output directory:

```text
local_reports/initial_pc_static_anchored_recheck/
```

Generated summary reports:

```text
local_reports/initial_pc_static_anchored_recheck/recheck-summary.json
local_reports/initial_pc_static_anchored_recheck/recheck-summary.md
```

Sample results:

| sample | status | safety gate | static labels | variable records |
| --- | --- | --- | ---: | ---: |
| `input.pdf` | `converted` | passed | 12 | 0 |
| `input2.pdf` | `converted` | passed | 16 | 0 |
| `input3.pdf` | `converted` | passed | 5 | 0 |
| `input4.pdf` | `converted` | passed | 0 | 4 |
| `input5.pdf` | `converted` | passed | 0 | 10 |

All five reports had:

- `validation.word_PAGE_field_count == 0`
- `validation.literal_PAGE_NUMBER_placeholder_count == 0`
- `validation.source_label_body_residual_count == 0`
- `validation.duplicate_header_footer_text_count == 0`
- `validation.missing_zone_count == 0`
- `validation.mispositioned_static_label_count == 0`
- `validation.variable_family_page_text_mismatch_count == 0`
- `validation.last_token_reuse_detected == false`

Focused sample checks:

- `input.pdf`: the generated DOCX body contained the `CHAPTER 13` title; footer
  left/center/right zones were preserved for 12 groups.
- `input2.pdf`: `Page i`, `Page 1 of 15`, `Page 2 of 15`, and
  `Page 15 of 15` were preserved in the right footer zone.
- `input3.pdf`: `8-1` through `8-5` had zero body residuals and were anchored
  to source-page footer zones.
- `input4.pdf`: `SPSCC Student Computing Center__Headers and Footers __1`
  through `__4` matched the expected source pages; `__4` was not repeatedly
  reused.
- `input5.pdf`: the every-other variable footer family from source page index
  2 onward was detected and matched without page-text mismatch.

### Wheel and wheelhouse

Commands run:

```bash
rm -rf build dist wheelhouse *.egg-info pdf2docx.egg-info
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m build --wheel
TMPDIR=/tmp TEMP=/tmp TMP=/tmp .venv/bin/python -m pip wheel -w wheelhouse .
```

Result: passed.

Generated project wheel:

```text
dist/pdf2docx-0.5.13-py3-none-any.whl
```

The wheel contained:

```text
pdf2docx/static_anchored/__init__.py
pdf2docx/static_anchored/analyzer.py
pdf2docx/static_anchored/cli.py
pdf2docx/static_anchored/converter.py
pdf2docx/static_anchored/validator.py
pdf2docx/static_anchored/writer.py
```

### Installed wheel smoke

Fresh environment:

```text
.venv-static-wheel-smoke/
```

Installed `dist/*.whl` with `--force-reinstall`, then imported from `/tmp`.
Imports resolved to:

```text
.venv-static-wheel-smoke/lib/python3.10/site-packages/pdf2docx/__init__.py
.venv-static-wheel-smoke/lib/python3.10/site-packages/pdf2docx/static_anchored/__init__.py
.venv-static-wheel-smoke/lib/python3.10/site-packages/pdf2docx/static_anchored/cli.py
```

Installed-wheel `input4.pdf` static anchored smoke:

- status: `converted`
- safety gate: passed
- all required static-mode safety counts: passed

Generated ignored outputs:

```text
local_reports/initial_pc_static_anchored_recheck/input4.installed-wheel.docx
local_reports/initial_pc_static_anchored_recheck/input4.installed-wheel.report.json
local_reports/initial_pc_static_anchored_recheck/input4.installed-wheel.report.md
```

### Wheelhouse offline smoke

Fresh environment:

```text
.venv-static-wheelhouse-smoke/
```

Install command:

```bash
.venv-static-wheelhouse-smoke/bin/python -m pip install --no-index --find-links wheelhouse pdf2docx
```

Result: passed. Imports from `/tmp` resolved to:

```text
.venv-static-wheelhouse-smoke/lib/python3.10/site-packages/pdf2docx/__init__.py
.venv-static-wheelhouse-smoke/lib/python3.10/site-packages/pdf2docx/static_anchored/__init__.py
.venv-static-wheelhouse-smoke/lib/python3.10/site-packages/pdf2docx/static_anchored/cli.py
```

Wheelhouse `input4.pdf` static anchored smoke:

- status: `converted`
- safety gate: passed
- all required static-mode safety counts: passed

### Closed-network bundle

Copied bundle path:

```text
local_dist/pdf2docx-static-anchored-bundle/
```

Checksum command:

```bash
cd local_dist/pdf2docx-static-anchored-bundle
sha256sum -c SHA256SUMS.txt
```

Result: passed for every listed bundle file.

The copied bundle was not regenerated because checksum validation passed. The
current PC wheel and wheelhouse were regenerated separately under ignored
`dist/` and `wheelhouse/`.

### Public/default behavior

- Public CLI/API was not changed.
- Default `Converter.convert()` behavior was not changed.
- Static anchored remains internal-only.
- No code changes were required.

### Initial PC recheck recommendation

The initial PC can run the static anchored internal helper, installed wheel,
and wheelhouse offline smoke successfully. The existing copied closed-network
bundle is intact by checksum. If a Linux/Python 3.10 closed-network bundle is
needed, create it as a separate ignored bundle from the regenerated
`wheelhouse/`; otherwise no bundle regeneration was required in this recheck.
