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
        overwrite=False,
        preview_dir=None,
        preview_pages=3) -> dict:
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
        'output_written': False,
        'output_kind': 'none',
        'diagnostic_output': False,
        'diagnostic_output_reason': '',
        'preview_images': [],
        'preview_report': {},
        'elapsed_seconds': 0.0,
    }
    if preview_dir:
        preview_report = render_pdf_preview_images(
            input_pdf,
            preview_dir,
            page_limit=preview_pages,
            password=password)
        report['preview_report'] = preview_report
        report['preview_images'] = preview_report.get('images', [])
        report['warning_codes'].extend(preview_report.get('warning_codes', []))

    if not plan.get('filter_candidates'):
        report['status'] = 'diagnostic_only'
        report['warning_codes'].append('no_static_source_page_candidates')
        fallback = convert_default_body(input_pdf, output_docx, password)
        report['conversion'] = fallback
        if fallback.get('status') == 'converted':
            mark_output_report(
                report,
                output_docx,
                'diagnostic_default_conversion',
                diagnostic=True,
                reason='no_static_source_page_candidates')
        else:
            report['warning_codes'].extend(fallback.get('warning_codes', []))
        finish_report(report_path, report, started)
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
            if filtered_docx.exists():
                preserve_output_docx(
                    filtered_docx,
                    output_docx,
                    report,
                    'diagnostic_filtered_body_conversion',
                    reason='filtered_body_conversion_blocked')
            else:
                fallback = convert_default_body(input_pdf, output_docx, password)
                report['diagnostic_fallback_conversion'] = fallback
                if fallback.get('status') == 'converted':
                    mark_output_report(
                        report,
                        output_docx,
                        'diagnostic_default_conversion',
                        diagnostic=True,
                        reason='filtered_body_conversion_blocked')
                else:
                    report['warning_codes'].extend(fallback.get('warning_codes', []))
            finish_report(report_path, report, started)
            return report

        document = Document(str(filtered_docx))
        apply_report = apply_static_anchored_plan(document, plan)
        report['apply_report'] = apply_report
        if not apply_report.get('applied'):
            report['status'] = 'blocked'
            report['warning_codes'].extend(apply_report.get('warning_codes', []))
            if filtered_docx.exists():
                preserve_output_docx(
                    filtered_docx,
                    output_docx,
                    report,
                    'diagnostic_filtered_body_without_static_parts',
                    reason='static_anchored_plan_not_applied')
            finish_report(report_path, report, started)
            return report
        temp_output = tmp / f'static-{output_docx.name}'
        document.save(str(temp_output))
        validation = validate_static_anchored_docx(temp_output, plan, conversion)
        report['validation'] = validation
        report['warning_codes'].extend(validation.get('warning_codes', []))
        if not validation.get('safety_gate_passed'):
            report['status'] = 'blocked'
            preserve_output_docx(
                temp_output,
                output_docx,
                report,
                'diagnostic_static_validation_failed',
                reason='static_anchored_validation_failed')
            finish_report(report_path, report, started)
            return report
        shutil.move(str(temp_output), str(output_docx))
        mark_output_report(
            report,
            output_docx,
            'static_anchored_validated',
            diagnostic=False,
            reason='')

    report['status'] = 'converted'
    finish_report(report_path, report, started)
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
            'internal_filtered_parse_report': internal_report,
            'warning_codes': warning_codes,
            'size_bytes': output_docx.stat().st_size if output_docx.exists() else 0,
        }
    finally:
        converter.close()


def convert_default_body(input_pdf: Path, output_docx: Path, password) -> dict:
    """Write a normal DOCX so callers always have an inspectable artifact."""
    converter = Converter(str(input_pdf), password)
    try:
        output_docx.parent.mkdir(parents=True, exist_ok=True)
        if output_docx.exists():
            output_docx.unlink()
        converter.convert(str(output_docx))
        return {
            'status': 'converted' if output_docx.exists() else 'failed',
            'mode': 'default_converter_fallback',
            'warning_codes': [],
            'size_bytes': output_docx.stat().st_size if output_docx.exists() else 0,
        }
    except Exception as exc:
        return {
            'status': 'failed',
            'mode': 'default_converter_fallback',
            'warning_codes': ['diagnostic_default_conversion_failed'],
            'error': f'{type(exc).__name__}: {exc}',
            'size_bytes': output_docx.stat().st_size if output_docx.exists() else 0,
        }
    finally:
        converter.close()


def preserve_output_docx(
        source_docx: Path,
        output_docx: Path,
        report: dict,
        output_kind: str,
        reason: str):
    """Copy a blocked intermediate DOCX to the requested output path."""
    if not source_docx.exists():
        report['warning_codes'].append('diagnostic_output_missing')
        mark_output_report(
            report,
            output_docx,
            'none',
            diagnostic=True,
            reason=reason)
        return
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    if output_docx.exists():
        output_docx.unlink()
    shutil.copy2(str(source_docx), str(output_docx))
    mark_output_report(
        report,
        output_docx,
        output_kind,
        diagnostic=True,
        reason=reason)


def mark_output_report(
        report: dict,
        output_docx: Path,
        output_kind: str,
        diagnostic: bool,
        reason: str):
    report['output_written'] = output_docx.exists()
    report['output_kind'] = output_kind
    report['diagnostic_output'] = bool(diagnostic)
    report['diagnostic_output_reason'] = reason
    report['output_size_bytes'] = (
        output_docx.stat().st_size if output_docx.exists() else 0)


def render_pdf_preview_images(
        input_pdf: Path,
        preview_dir,
        page_limit=3,
        password=None) -> dict:
    """Render a few source PDF page previews for local visual QA."""
    preview_dir = Path(preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)
    images = []
    warnings = []
    try:
        import fitz

        doc = fitz.open(str(input_pdf))
        try:
            if password:
                doc.authenticate(password)
            limit = max(0, int(page_limit or 0))
            for page_index in range(min(limit, len(doc))):
                page = doc.load_page(page_index)
                pix = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0), alpha=False)
                image_path = preview_dir / f'page-{page_index + 1:03d}.png'
                pix.save(str(image_path))
                images.append(str(image_path))
        finally:
            doc.close()
    except Exception as exc:
        warnings.append('preview_image_render_failed')
        return {
            'status': 'failed',
            'images': images,
            'warning_codes': warnings,
            'error': f'{type(exc).__name__}: {exc}',
        }
    return {
        'status': 'rendered',
        'images': images,
        'page_count': len(images),
        'warning_codes': warnings,
    }


def finish_report(report_path, report: dict, started):
    report['elapsed_seconds'] = round(time.perf_counter() - started, 3)
    report['warning_codes'] = sorted(set(report.get('warning_codes', [])))
    write_json_report(report_path, report)


def write_json_report(report_path, report: dict):
    if not report_path:
        return
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding='utf-8')
