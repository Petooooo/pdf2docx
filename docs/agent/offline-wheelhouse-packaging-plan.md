# Offline Wheelhouse Packaging Plan

## Scope

This plan prepares the current private fork for wheel-based, offline use in a
closed network. It does not expose reviewed header/footer migration publicly,
does not enable reviewed filtering by default, and does not change normal
PDF-to-DOCX conversion behavior.

## Packaging Metadata Summary

Current package metadata is defined in `setup.py`.

- Package name: `pdf2docx`
- Version source: `version.txt`
- Declared Python support: `python_requires=">=3.10"`
- Build backend file: no committed `pyproject.toml`
- Additional setup config: no committed `setup.cfg`
- Console entry point: `pdf2docx=pdf2docx.main:main`
- Project package code: pure Python
- Dependency wheelhouse: platform-specific because dependencies include
  PyMuPDF, numpy, and opencv-python-headless

Current runtime dependencies from `requirements.txt`:

- `PyMuPDF>=1.26.7`
- `python-docx>=0.8.10`
- `fonttools>=4.24.0`
- `numpy>=1.17.2`
- `opencv-python-headless>=4.5`
- `fire>=0.3.0`

The source wheel for this project is expected to be `py3-none-any`, but a
complete offline wheelhouse must be built on the target OS/architecture/Python
version, or with an explicitly compatible wheel download strategy.

## Python Compatibility Plan

Do not broaden the declared support below Python 3.10 in this phase.

Compatibility should be reported as:

- Declared minimum: Python 3.10.
- Locally tested interpreter: the interpreter used to build the wheel.
- Untested interpreters: listed as checklist targets, not claimed support.

Suggested future test matrix, only where interpreters and dependency wheels are
available:

- Python 3.10
- Python 3.11
- Python 3.12
- Python 3.13, if PyMuPDF, numpy, opencv-python-headless, python-docx,
  fonttools, and fire all provide compatible wheels

If an older interpreter fails because of `python_requires`, package metadata,
syntax, typing, or dependency wheels, keep the failure documented rather than
forcing compatibility.

## Build Project Wheel

Use an existing local development environment:

```bash
python -m pip install --upgrade pip build wheel
python -m build --wheel
```

If `build` is unavailable, use pip wheel as a fallback:

```bash
python -m pip wheel -w wheelhouse .
```

Expected generated artifacts:

- `dist/*.whl`
- `*.egg-info/`

These artifacts are build outputs and must not be committed.

## Build Dependency Wheelhouse

Build the project wheel and all runtime dependency wheels into a local
wheelhouse:

```bash
python -m pip wheel -w wheelhouse .
```

For closed-network use, preserve the exact wheelhouse built for the target
platform and Python version. Do not mix Windows, Linux, macOS, x86_64, arm64,
or Python ABI targets unless that is intentional and tested.

## Fresh Offline-Style Install

Create a fresh test environment:

```bash
python -m venv .venv-wheel-smoke
. .venv-wheel-smoke/bin/activate
```

Windows alternative:

```bat
python -m venv .venv-wheel-smoke
.venv-wheel-smoke\Scripts\activate
```

Install without the network:

```bash
python -m pip install --no-index --find-links wheelhouse pdf2docx
```

Or install the exact built wheel:

```bash
python -m pip install --no-index --find-links wheelhouse dist/*.whl
```

## Import Smoke

After installation, verify that the installed package imports:

```bash
python -c "import pdf2docx; print(pdf2docx.__file__)"
```

Run this from outside the checkout root when possible. The printed path should
point inside the fresh environment, not the checkout source directory.

## Conversion Smoke

Use a private or committed-safe PDF. The smoke script is generic and does not
embed any private sample text:

```bash
python scripts/smoke_convert_pdf_to_docx.py input.pdf output.docx
```

For this repository, a committed demo PDF may be used for packaging smoke:

```bash
python scripts/smoke_convert_pdf_to_docx.py test/samples/demo.pdf local_reports/wheel_smoke/demo.docx
```

If private `local_samples/input.pdf` exists, it can be used for local visual
inspection:

```bash
python scripts/smoke_convert_pdf_to_docx.py local_samples/input.pdf local_reports/wheel_smoke/input.docx
```

Generated DOCX files must remain ignored and must not be committed.

## Static Anchored Internal Smoke

The static source-page anchored fidelity helper is internal-only and not
enabled by default. It is packaged as an importable module, not as a public
console script:

```bash
python -m pdf2docx.static_anchored.cli \
  --input input.pdf \
  --output input.static.docx \
  --report input.static.report.json \
  --markdown-report input.static.report.md \
  --overwrite
```

The source-tree convenience wrapper remains available for local development:

```bash
python -m scripts.internal.static_anchored_convert \
  --input input.pdf \
  --output input.static.docx \
  --report input.static.report.json \
  --overwrite
```

When testing an installed wheel, run the module command from outside the
checkout root and confirm `pdf2docx.__file__`,
`pdf2docx.static_anchored.__file__`, and
`pdf2docx.static_anchored.cli.__file__` all point inside the fresh
environment's `site-packages`.

Static anchored smoke output should report:

- `word_PAGE_field_count == 0`
- `literal_PAGE_NUMBER_placeholder_count == 0`
- `source_label_body_residual_count == 0`
- `duplicate_header_footer_text_count == 0`
- `missing_zone_count == 0`
- `mispositioned_static_label_count == 0`
- `variable_family_page_text_mismatch_count == 0`
- `last_token_reuse_detected == false`

## Offline Bundle Layout

A practical closed-network bundle can contain:

- `wheelhouse/`
- a short install README copied from this plan
- optional smoke script: `scripts/smoke_convert_pdf_to_docx.py`
- optional checksum manifest generated outside the repository

Do not include private PDFs unless the target environment explicitly requires
them and the transfer is approved.

## Files That Must Not Be Committed

- `dist/`
- `build/`
- `wheelhouse/`
- `.venv/`
- `.venv-wheel-smoke/`
- `*.whl`
- `*.egg-info/`
- generated DOCX files
- generated PDF files
- local sample PDFs
- local reports
- generated logs
- large extracted text

## Closed-Network Verification Checklist

Inside the closed network:

- Confirm the Python version matches the wheelhouse target.
- Create a fresh virtual environment.
- Install with `--no-index --find-links wheelhouse`.
- Run the import smoke.
- Run the conversion smoke on an approved small PDF.
- Open the generated DOCX for visual inspection.
- Record the package version, Python version, platform, and wheelhouse source.

## Current Public/API Status

- Public CLI/API reviewed header/footer migration option: not exposed.
- Default conversion behavior: unchanged.
- Reviewed filtering: internal-only and disabled by default.
- DOCX header/footer migration: not enabled by default.

## Recommended Phase 6B Direction

Phase 6B should repeat the wheelhouse smoke on the actual target Python and
platform matrix, record dependency wheel availability, and define the offline
bundle transfer/checksum procedure.

Phase 6B local smoke on Windows Python 3.12 produced
`dist/pdf2docx-0.5.13-py3-none-any.whl` and a wheelhouse containing platform
specific dependencies such as PyMuPDF, NumPy, lxml, and OpenCV. Rebuild the
wheelhouse for each closed-network target Python/platform combination.

## Phase 6C Bundle Layout

Phase 6C prepared a closed-network import bundle under an ignored local path:

```text
local_dist/pdf2docx-static-anchored-bundle/
```

The bundle contains:

- `wheels/pdf2docx-0.5.13-py3-none-any.whl`
- `wheelhouse/*.whl`
- `scripts/install_offline.sh`
- `scripts/install_offline.ps1`
- `scripts/smoke_static_anchored.py`
- `scripts/smoke_static_anchored.sh`
- `samples/demo.pdf`
- `README.md`
- `MANIFEST.json`
- `SHA256SUMS.txt`

The bundle directory is ignored and must not be committed.

Closed-network install from the bundle root:

```bash
python -m venv .venv-pdf2docx-static
.venv-pdf2docx-static/bin/python -m pip install --no-index --find-links wheelhouse pdf2docx
```

Static anchored quality smoke:

```bash
python -m pdf2docx.static_anchored.cli \
  --input approved-input.pdf \
  --output reports/approved-input.static.docx \
  --report reports/approved-input.static.report.json \
  --markdown-report reports/approved-input.static.report.md \
  --overwrite
```

Phase 6C local bundle smoke installed from only the bundle wheelhouse into a
fresh venv, imported from `site-packages` outside the checkout, and converted
`local_samples/input4.pdf` with all static-mode safety counts passing. The
included `samples/demo.pdf` is an install/import smoke sample only and is
expected to return `diagnostic_only`.
