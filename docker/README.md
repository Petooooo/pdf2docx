# Static Anchored Docker Image

This directory contains the internal Docker packaging surface for the static
anchored smoke image. The image is intentionally small and does not include any
private PDFs, local reports, closed-network bundles, generated DOCX files, or
local sample artifacts.

The image installs the project wheel built from the current checkout and copies
one public smoke script:

```text
/opt/wheels/pdf2docx-*.whl
/opt/pdf2docx/examples/static_anchored_smoke.py
```

Build:

```bash
python -m build --wheel
docker build \
  -f docker/Dockerfile \
  -t petooooo/pdf2docx:0.5.13-py311-static \
  -t petooooo/pdf2docx:latest \
  .
```

Help smoke:

```bash
docker run --rm petooooo/pdf2docx:0.5.13-py311-static \
  python -m pdf2docx.static_anchored.cli --help
```

DOCX-only smoke:

```bash
docker run --rm \
  -v "$PWD/local_reports/docker_static_anchored_docx_only:/work/out" \
  petooooo/pdf2docx:0.5.13-py311-static \
  python /opt/pdf2docx/examples/static_anchored_smoke.py --out-dir /work/out
```

Report-mode smoke:

```bash
docker run --rm \
  -v "$PWD/local_reports/docker_static_anchored_smoke:/work/out" \
  petooooo/pdf2docx:0.5.13-py311-static \
  python /opt/pdf2docx/examples/static_anchored_smoke.py --out-dir /work/out --with-report
```

The smoke script creates a synthetic PDF at runtime using PyMuPDF. It does not
read `local_samples/`.
