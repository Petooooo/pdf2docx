#!/usr/bin/env python3
"""Private wheel smoke test for PDF-to-DOCX conversion."""

import argparse
import os
import sys
import traceback
from pathlib import Path


def parse_pages(value):
    """Parse a comma-separated page list for Converter.convert()."""
    if value in {None, ""}:
        return None
    pages = []
    for raw_part in str(value).split(","):
        part = raw_part.strip()
        if not part:
            continue
        try:
            pages.append(int(part))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"invalid page index {part!r}; use comma-separated integers"
            ) from exc
    return pages or None


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run a private pdf2docx wheel conversion smoke test.")
    parser.add_argument("input_pdf", help="Input PDF path.")
    parser.add_argument("output_docx", help="Output DOCX path.")
    parser.add_argument("--password", default=None, help="PDF password, if needed.")
    parser.add_argument("--start", type=int, default=0, help="Zero-based start page.")
    parser.add_argument("--end", type=int, default=None, help="Zero-based end page.")
    parser.add_argument(
        "--pages",
        type=parse_pages,
        default=None,
        help="Comma-separated zero-based page indexes, for example 0,2,4.")
    parser.add_argument(
        "--allow-local-source",
        action="store_true",
        help="Allow importing pdf2docx from the checkout source tree.")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print a traceback when conversion fails.")
    return parser


def convert_pdf_to_docx(
        input_pdf,
        output_docx,
        password=None,
        start=0,
        end=None,
        pages=None,
        allow_local_source=False):
    input_path = Path(input_pdf)
    output_path = Path(output_docx)
    if not input_path.is_file():
        raise FileNotFoundError(f"input PDF not found: {input_path}")

    import pdf2docx

    if _is_checkout_source_import(pdf2docx) and not allow_local_source:
        raise RuntimeError(
            "pdf2docx was imported from the checkout source tree; install the "
            "built wheel in a fresh environment or pass --allow-local-source.")

    from pdf2docx import Converter

    output_path.parent.mkdir(parents=True, exist_ok=True)
    converter = Converter(str(input_path), password)
    try:
        converter.convert(
            str(output_path),
            start=start,
            end=end,
            pages=pages)
    finally:
        converter.close()

    if not output_path.is_file():
        raise RuntimeError(f"conversion did not create DOCX: {output_path}")
    size = output_path.stat().st_size
    if size <= 0:
        raise RuntimeError(f"conversion created an empty DOCX: {output_path}")
    return {
        "input_pdf": str(input_path),
        "output_docx": str(output_path),
        "output_size_bytes": size,
        "pdf2docx_module": str(Path(pdf2docx.__file__).resolve()),
    }


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    allow_local_source = (
        args.allow_local_source or
        os.environ.get("PDF2DOCX_SMOKE_ALLOW_LOCAL_SOURCE") == "1")
    try:
        result = convert_pdf_to_docx(
            args.input_pdf,
            args.output_docx,
            password=args.password,
            start=args.start,
            end=args.end,
            pages=args.pages,
            allow_local_source=allow_local_source)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: conversion smoke failed: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return 1

    print("SUCCESS: pdf2docx conversion smoke completed")
    print(f"input_pdf: {result['input_pdf']}")
    print(f"output_docx: {result['output_docx']}")
    print(f"output_size_bytes: {result['output_size_bytes']}")
    print(f"pdf2docx_module: {result['pdf2docx_module']}")
    return 0


def _is_checkout_source_import(module):
    module_file = getattr(module, "__file__", "")
    if not module_file:
        return False
    source_tree = Path(__file__).resolve().parents[1] / "pdf2docx"
    try:
        Path(module_file).resolve().relative_to(source_tree.resolve())
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
