FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY dist/*.whl /opt/wheels/

RUN python -m pip install --upgrade pip \
    && python -m pip install /opt/wheels/pdf2docx-*.whl

COPY docker/examples/static_anchored_smoke.py /opt/pdf2docx/examples/static_anchored_smoke.py

WORKDIR /work

CMD ["sh", "-lc", "python -m pdf2docx.static_anchored.cli --help && printf '\\nRun: python /opt/pdf2docx/examples/static_anchored_smoke.py --out-dir /work/out\\n'"]
