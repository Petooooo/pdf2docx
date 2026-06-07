# -*- coding: utf-8 -*-

"""Internal conversion facade for static source-page anchored DOCX output."""

import json
import shutil
import tempfile
import time
from pathlib import Path

from docx import Document

from pdf2docx import Converter
from pdf2docx.page import LayoutAnalyzer

from .analyzer import build_static_anchored_plan, build_static_filtering_config
from .validator import validate_static_anchored_docx
from .writer import apply_static_anchored_plan


def convert_static_anchored_pdf(
        input_pdf,
        output_docx,
        report_path=None,
        password=None,
        overwrite=False) -> dict:
    """Convert a PDF using the internal static anchored visual fidelity mode."""
    started = time.perf_counter()
    input_pdf = Path(input_pdf)
    output_docx = Path(output_docx)
    if output_docx.exists() and not overwrite:
        raise FileExistsError(f'Output DOCX already exists: {output_docx}')

    layout = parse_layout_analysis(input_pdf, password)
    plan = build_static_anchored_plan(layout)
    report = {
        'mode': 'static_anchored',
        'input_pdf': str(input_pdf),
        'output_docx': str(output_docx),
        'status': '',
        'plan_summary': plan.get('report', {}),
        'conversion': {},
        'apply_report': {},
        'validation': {},
        'warning_codes': [],
        'elapsed_seconds': 0.0,
    }
    if not plan.get('filter_candidates'):
        report['status'] = 'diagnostic_only'
        report['warning_codes'].append('no_static_source_page_candidates')
        write_json_report(report_path, report)
        return report

    config = build_static_filtering_config(plan, LayoutAnalyzer)
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    if output_docx.exists():
        output_docx.unlink()

    with tempfile.TemporaryDirectory(prefix='static_anchored_internal_') as tmp:
        tmp = Path(tmp)
        filtered_docx = tmp / output_docx.name
        conversion = convert_filtered_body(input_pdf, filtered_docx, password, config)
        report['conversion'] = conversion
        if conversion.get('status') != 'converted':
            report['status'] = 'blocked'
            report['warning_codes'].extend(conversion.get('warning_codes', []))
            report['warning_codes'].append('filtered_body_conversion_blocked')
            write_json_report(report_path, report)
            return report

        document = Document(str(filtered_docx))
        apply_report = apply_static_anchored_plan(document, plan)
        report['apply_report'] = apply_report
        if not apply_report.get('applied'):
            report['status'] = 'blocked'
            report['warning_codes'].extend(apply_report.get('warning_codes', []))
            write_json_report(report_path, report)
            return report
        temp_output = tmp / f'static-{output_docx.name}'
        document.save(str(temp_output))
        validation = validate_static_anchored_docx(temp_output, plan)
        report['validation'] = validation
        report['warning_codes'].extend(validation.get('warning_codes', []))
        if not validation.get('safety_gate_passed'):
            report['status'] = 'blocked'
            write_json_report(report_path, report)
            return report
        shutil.move(str(temp_output), str(output_docx))

    report['status'] = 'converted'
    report['elapsed_seconds'] = round(time.perf_counter() - started, 3)
    report['warning_codes'] = sorted(set(report['warning_codes']))
    write_json_report(report_path, report)
    return report


def parse_layout_analysis(input_pdf: Path, password=None) -> dict:
    converter = Converter(str(input_pdf), password)
    settings = converter.default_settings.copy()
    settings.update({'layout_analysis': True})
    try:
        converter.load_pages().parse_document(**settings)
        return converter.pages.layout_analysis_report or {}
    finally:
        converter.close()


def convert_filtered_body(input_pdf: Path, output_docx: Path, password, config: dict) -> dict:
    converter = Converter(str(input_pdf), password)
    try:
        converter.convert(
            str(output_docx),
            layout_analysis=True,
            _reviewed_header_footer_filtering_config=config)
        internal_report = getattr(
            converter.pages,
            '_reviewed_filtering_internal_filtered_parse_report',
            {}) or {}
        warnings = list(internal_report.get('safety_warnings', []) or [])
        warning_codes = sorted({
            warning.get('type', '')
            for warning in warnings
            if warning.get('type')
        })
        applied = bool(internal_report.get('applied_to_parse'))
        return {
            'status': 'converted' if applied and output_docx.exists() else 'blocked',
            'applied_to_parse': applied,
            'internal_filtered_parse_summary': internal_report.get('summary', {}),
            'warning_codes': warning_codes,
            'size_bytes': output_docx.stat().st_size if output_docx.exists() else 0,
        }
    finally:
        converter.close()


def write_json_report(report_path, report: dict):
    if not report_path:
        return
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding='utf-8')
