# -*- coding: utf-8 -*-

"""Internal module entrypoint for static anchored conversion.

This module is intentionally not exposed as a public console script. It exists
so private wheel smoke tests can run:

    python -m pdf2docx.static_anchored.cli --input input.pdf --output out.docx --report out.json
"""

import argparse
import json
from pathlib import Path

from .converter import convert_static_anchored_pdf


def build_parser():
    parser = argparse.ArgumentParser(
        description='Internal static anchored PDF-to-DOCX conversion helper.')
    parser.add_argument('--input', required=True, help='Input PDF path.')
    parser.add_argument('--output', required=True, help='Output DOCX path.')
    parser.add_argument(
        '--report',
        default='',
        help='Optional output JSON report path.')
    parser.add_argument(
        '--markdown-report',
        default='',
        help='Optional Markdown report path.')
    parser.add_argument('--password', default=None, help='PDF password if required.')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite output DOCX/report.')
    parser.add_argument(
        '--preview-dir',
        default='',
        help='Optional directory for source PDF page preview PNGs.')
    parser.add_argument(
        '--preview-pages',
        type=int,
        default=3,
        help='Number of source PDF pages to render when --preview-dir is used.')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    report = convert_static_anchored_pdf(
        args.input,
        args.output,
        report_path=args.report,
        password=args.password,
        overwrite=args.overwrite,
        preview_dir=args.preview_dir or None,
        preview_pages=args.preview_pages)
    if args.markdown_report:
        write_markdown_report(Path(args.markdown_report), report)
    print(f"status: {report.get('status')}")
    print(f"output: {args.output}")
    print(f"output_written: {report.get('output_written')}")
    print(f"output_kind: {report.get('output_kind')}")
    if report.get('diagnostic_output'):
        print(f"diagnostic_output_reason: {report.get('diagnostic_output_reason')}")
    if args.report:
        print(f"report: {args.report}")
    if args.markdown_report:
        print(f"markdown_report: {args.markdown_report}")
    if report.get('warning_codes'):
        print('warnings: ' + ', '.join(report.get('warning_codes', [])))
    return 0 if report.get('status') == 'converted' else 1


def write_markdown_report(path: Path, report: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    validation = report.get('validation', {}) or {}
    plan_summary = report.get('plan_summary', {}) or {}
    lines = [
        '# Static Anchored Conversion Report',
        '',
        f"- input: `{report.get('input_pdf', '')}`",
        f"- output: `{report.get('output_docx', '')}`",
        f"- status: `{report.get('status', '')}`",
        f"- output_written: `{report.get('output_written', False)}`",
        f"- output_kind: `{report.get('output_kind', '')}`",
        f"- diagnostic_output: `{report.get('diagnostic_output', False)}`",
        f"- diagnostic_output_reason: `{report.get('diagnostic_output_reason', '')}`",
        f"- warning_codes: `{', '.join(report.get('warning_codes', []))}`",
        '',
        '## Plan Summary',
        '',
        '```json',
        json.dumps(plan_summary, ensure_ascii=False, indent=2),
        '```',
        '',
        '## Validation',
        '',
        '```json',
        json.dumps({
            'word_PAGE_field_count': validation.get('word_PAGE_field_count'),
            'literal_PAGE_NUMBER_placeholder_count': validation.get(
                'literal_PAGE_NUMBER_placeholder_count'),
            'source_label_body_residual_count': validation.get(
                'source_label_body_residual_count'),
            'duplicate_header_footer_text_count': validation.get(
                'duplicate_header_footer_text_count'),
            'multi_zone_missing_count': validation.get('missing_zone_count'),
            'mispositioned_static_label_count': validation.get(
                'mispositioned_static_label_count'),
            'variable_family_page_text_mismatch_count': validation.get(
                'variable_family_page_text_mismatch_count'),
            'last_token_reuse_detected': validation.get('last_token_reuse_detected'),
            'safety_gate_passed': validation.get('safety_gate_passed'),
        }, ensure_ascii=False, indent=2),
        '```',
    ]
    if report.get('preview_images'):
        lines.extend([
            '',
            '## Preview Images',
            '',
        ])
        lines.extend(f"- `{path}`" for path in report.get('preview_images', []))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
