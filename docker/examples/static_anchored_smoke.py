#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Generate a tiny public PDF and run the internal static anchored smoke."""

import argparse
import json
from pathlib import Path

import fitz

from pdf2docx.static_anchored.cli import write_markdown_report
from pdf2docx.static_anchored.converter import convert_static_anchored_pdf


def build_parser():
    parser = argparse.ArgumentParser(
        description='Create a synthetic PDF and run static anchored conversion.')
    parser.add_argument(
        '--out-dir',
        default='/work/out',
        help='Directory for generated smoke artifacts.')
    parser.add_argument(
        '--with-report',
        action='store_true',
        help='Also write JSON and Markdown static anchored reports.')
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing generated smoke artifacts.')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = out_dir / 'sample.pdf'
    docx_path = out_dir / 'sample.static.docx'
    report_path = out_dir / 'sample.static.report.json'
    markdown_path = out_dir / 'sample.static.report.md'

    if not args.overwrite:
        existing = [
            path for path in (pdf_path, docx_path, report_path, markdown_path)
            if path.exists()
        ]
        if existing:
            names = ', '.join(str(path) for path in existing)
            raise FileExistsError(
                f'Generated smoke artifact already exists: {names}. '
                'Use --overwrite or an empty --out-dir.')

    create_sample_pdf(pdf_path)
    report = convert_static_anchored_pdf(
        pdf_path,
        docx_path,
        report_path=report_path if args.with_report else None,
        overwrite=True)
    if args.with_report:
        write_markdown_report(markdown_path, report)
        assert_report_gate(report)

    if report.get('status') != 'converted':
        raise RuntimeError(
            'Static anchored smoke did not convert successfully: '
            f"{report.get('status')} {report.get('warning_codes')}")

    print('static anchored smoke: ok')
    print(f'pdf: {pdf_path}')
    print(f'docx: {docx_path}')
    print(f"status: {report.get('status')}")
    if args.with_report:
        validation = report.get('validation') or {}
        print(f'report_json: {report_path}')
        print(f'report_markdown: {markdown_path}')
        print(
            'validation: '
            + json.dumps({
                'body_residual_count': validation.get('body_residual_count'),
                'missing_removed_source_ref_count': validation.get(
                    'missing_removed_source_ref_count'),
                'word_PAGE_field_count': validation.get('word_PAGE_field_count'),
                'literal_PAGE_NUMBER_placeholder_count': validation.get(
                    'literal_PAGE_NUMBER_placeholder_count'),
            }, sort_keys=True))
    return 0


def create_sample_pdf(path: Path):
    doc = fitz.open()
    try:
        for page_index in range(3):
            page = doc.new_page(width=612, height=792)
            page.insert_text(
                (54, 36),
                'DOCKER STATIC HEADER',
                fontsize=9)
            page.insert_text(
                (72, 138),
                f'Docker smoke body paragraph page {page_index + 1}.',
                fontsize=11)
            page.insert_text(
                (72, 160),
                'This body text must remain in the DOCX body.',
                fontsize=11)
            page.insert_text(
                (54, 758),
                'DOCKER STATIC FOOTER',
                fontsize=9)
            page.insert_text(
                (506, 758),
                f'Page {page_index + 1} of 3',
                fontsize=9)
        doc.save(str(path))
    finally:
        doc.close()


def assert_report_gate(report: dict):
    validation = report.get('validation') or {}
    checks = {
        'status': report.get('status') == 'converted',
        'body_residual_count': validation.get('body_residual_count') == 0,
        'word_PAGE_field_count': validation.get('word_PAGE_field_count') == 0,
        'literal_PAGE_NUMBER_placeholder_count': (
            validation.get('literal_PAGE_NUMBER_placeholder_count') == 0),
        'missing_removed_source_ref_count': (
            validation.get('missing_removed_source_ref_count') == 0),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AssertionError(f'Static anchored report gate failed: {failed}')


if __name__ == '__main__':
    raise SystemExit(main())
