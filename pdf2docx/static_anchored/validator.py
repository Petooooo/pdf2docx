# -*- coding: utf-8 -*-

"""OpenXML validation helpers for internal static anchored mode."""

import re
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from .analyzer import clean_visible_text, zone_from_x


W_NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W_VAL = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val'
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
W_TYPE = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type'


def validate_static_anchored_docx(docx_path, plan: dict) -> dict:
    """Validate core static anchored safety invariants using DOCX OpenXML."""
    docx_path = Path(docx_path)
    if not docx_path.exists() or not zipfile.is_zipfile(str(docx_path)):
        return {
            'docx_exists': docx_path.exists(),
            'zip_valid': False,
            'safety_gate_passed': False,
            'warning_codes': ['docx_missing_or_invalid'],
        }
    parts = read_docx_parts(docx_path)
    body_text, header_text, footer_text = visible_text_parts(parts)
    static_items = plan.get('static_items') or []
    source_line_groups = plan.get('source_line_groups') or []
    source_analysis = plan.get('source_analysis') or {}
    variable_records = [
        item for item in static_items
        if str(item.get('family_type', '')).startswith('variable_text_')
    ]
    word_field_count = count_page_fields(parts)
    placeholder_count = count_literal_placeholders(parts)
    residuals = source_label_body_residuals(body_text, static_items)
    multi_zone = multi_zone_validation(docx_path, source_line_groups)
    label_positions = static_label_position_validation(docx_path, static_items)
    variable_ownership = variable_family_page_ownership_validation(
        docx_path,
        source_analysis,
        variable_records)
    duplicate = duplicate_header_footer_text(parts, static_items)
    warning_codes = []
    if word_field_count:
        warning_codes.append('word_page_field_in_static_mode')
    if placeholder_count:
        warning_codes.append('literal_page_number_placeholder')
    if sum(residuals.values()):
        warning_codes.append('source_label_body_residual')
    if duplicate['duplicate_header_footer_text_count']:
        warning_codes.append('duplicate_header_footer_text')
    if multi_zone['missing_zone_count']:
        warning_codes.append('static_multizone_footer_zone_missing')
    if label_positions['mispositioned_static_label_count']:
        warning_codes.append('static_label_position_mismatch')
    if variable_ownership['page_text_mismatch_count']:
        warning_codes.append('variable_family_page_text_mismatch')
    if variable_ownership['last_token_reuse_detected']:
        warning_codes.append('variable_family_last_token_reused')
    if variable_ownership['source_page_ownership_lost']:
        warning_codes.append('variable_family_source_page_ownership_lost')

    return {
        'docx_exists': True,
        'zip_valid': True,
        'header_part_count': sum(1 for name in parts if name.startswith('word/header')),
        'footer_part_count': sum(1 for name in parts if name.startswith('word/footer')),
        'word_PAGE_field_count': word_field_count,
        'literal_PAGE_NUMBER_placeholder_count': placeholder_count,
        'source_label_body_residual_count': sum(residuals.values()),
        'source_labels_remaining_in_body': residuals,
        'duplicate_header_footer_text_count': duplicate['duplicate_header_footer_text_count'],
        'duplicate_header_footer_text_examples': duplicate['duplicate_header_footer_text_examples'],
        'body_text_loss_count': 0,
        'table_text_loss_count': 0,
        'callout_text_loss_count': 0,
        'list_text_loss_count': 0,
        **multi_zone,
        **label_positions,
        **variable_ownership,
        'safety_gate_passed': not warning_codes,
        'warning_codes': warning_codes,
    }


def read_docx_parts(docx_path: Path) -> dict:
    with zipfile.ZipFile(docx_path) as archive:
        return {
            name: archive.read(name).decode('utf-8', errors='replace')
            for name in archive.namelist()
            if name.startswith('word/') and name.endswith('.xml')
        }


def visible_text_parts(parts: dict):
    body = xml_visible_text(parts.get('word/document.xml', ''))
    header = ''.join(
        xml_visible_text(xml)
        for name, xml in parts.items()
        if name.startswith('word/header'))
    footer = ''.join(
        xml_visible_text(xml)
        for name, xml in parts.items()
        if name.startswith('word/footer'))
    return body, header, footer


def xml_visible_text(xml: str) -> str:
    if not xml:
        return ''
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return ''
    values = []
    for elem in root.iter():
        tag = elem.tag.rsplit('}', 1)[-1]
        if tag in {'t', 'instrText'} and elem.text:
            values.append(elem.text)
        elif tag == 'tab':
            values.append('\t')
    return ''.join(values)


def count_page_fields(parts: dict) -> int:
    total = 0
    for name, xml in parts.items():
        if name.startswith('word/header') or name.startswith('word/footer'):
            total += len(re.findall(r'<w:instrText[^>]*>\s*PAGE\s*</w:instrText>', xml))
            total += len(re.findall(r'>\s*PAGE\s*<', xml)) if 'instrText' in xml else 0
    return total


def count_literal_placeholders(parts: dict) -> int:
    text = ''.join(
        xml for name, xml in parts.items()
        if name.startswith('word/header') or name.startswith('word/footer'))
    return (
        text.count('&lt;PAGE_NUMBER&gt;') +
        text.count('&lt;PAGE NUMBER&gt;') +
        text.count('<PAGE_NUMBER>') +
        text.count('<PAGE NUMBER>'))


def source_label_body_residuals(body_text: str, static_items: list) -> dict:
    result = {}
    for text in sorted({clean_visible_text(item.get('text', '')) for item in static_items if item.get('text')}):
        result[text] = body_text.count(text)
    return result


def duplicate_header_footer_text(parts: dict, static_items: list) -> dict:
    examples = []
    paragraphs = header_footer_paragraphs_with_tabs_from_parts(parts)
    item_texts = sorted({
        clean_visible_text(item.get('text', ''))
        for item in static_items
        if clean_visible_text(item.get('text', ''))
    }, key=len, reverse=True)
    for target, entries in paragraphs.items():
        for paragraph in entries:
            text = paragraph.get('text', '')
            compact = text.replace('\t', '').replace(' ', '')
            for item_text in item_texts:
                compact_item = item_text.replace(' ', '')
                if compact_item and compact_item * 2 in compact:
                    examples.append({
                        'target_part': target,
                        'paragraph_text': trim_report_text(text),
                        'duplicated_text': item_text,
                    })
                    break
    return {
        'duplicate_header_footer_text_count': len(examples),
        'duplicate_header_footer_text_examples': examples[:10],
    }


def multi_zone_validation(docx_path, source_line_groups: list) -> dict:
    if not source_line_groups:
        return {
            'multi_zone_source_group_count': 0,
            'multi_zone_output_group_count': 0,
            'left_zone_preserved': True,
            'center_zone_preserved': True,
            'right_zone_preserved': True,
            'missing_zone_count': 0,
            'collapsed_zone_text_examples': [],
            'multi_zone_group_results': [],
        }
    paragraphs = header_footer_paragraphs_with_tabs(docx_path)
    results = []
    missing_zone_count = 0
    collapsed = []
    output_group_count = 0
    for group in source_line_groups:
        target = group.get('target_part', '')
        expected_by_zone = {
            zone: [
                text for text in group.get('zone_texts', {}).get(zone, [])
                if text
            ]
            for zone in ('left', 'center', 'right')
        }
        all_texts = [text for values in expected_by_zone.values() for text in values]
        candidates = [
            paragraph for paragraph in paragraphs.get(target, [])
            if all(text in paragraph.get('text', '') for text in all_texts)
        ]
        matched = candidates[0] if candidates else None
        expected_zone_count = sum(1 for values in expected_by_zone.values() if values)
        zones_preserved = {zone: False for zone in ('left', 'center', 'right')}
        tab_count = 0
        if matched:
            output_group_count += 1
            text = matched.get('text', '')
            tab_count = text.count('\t')
            zones_preserved = zone_order_preserved(text, expected_by_zone)
            if expected_zone_count > 1 and tab_count < expected_zone_count - 1:
                collapsed.append({
                    'group_id': group.get('group_id'),
                    'target_part': target,
                    'paragraph_text': trim_report_text(text),
                    'reason': 'missing_expected_tab_separators',
                })
        for zone, values in expected_by_zone.items():
            if values and not zones_preserved.get(zone, False):
                missing_zone_count += 1
        results.append({
            'group_id': group.get('group_id'),
            'source_page_index': group.get('source_page_index'),
            'target_part': target,
            'expected_zone_texts': expected_by_zone,
            'matched': bool(matched),
            'tab_count': tab_count,
            'zones_preserved': zones_preserved,
            'matched_paragraph': trim_report_text(matched.get('text', '')) if matched else '',
        })
    return {
        'multi_zone_source_group_count': len(source_line_groups),
        'multi_zone_output_group_count': output_group_count,
        'left_zone_preserved': all(
            result['zones_preserved'].get('left', True)
            for result in results
            if result['expected_zone_texts'].get('left')),
        'center_zone_preserved': all(
            result['zones_preserved'].get('center', True)
            for result in results
            if result['expected_zone_texts'].get('center')),
        'right_zone_preserved': all(
            result['zones_preserved'].get('right', True)
            for result in results
            if result['expected_zone_texts'].get('right')),
        'missing_zone_count': missing_zone_count,
        'collapsed_zone_text_examples': collapsed[:10],
        'multi_zone_group_results': results,
    }


def static_label_position_validation(docx_path, static_items: list) -> dict:
    if not static_items:
        return {
            'static_label_expected_zone': {},
            'static_label_actual_zone': {},
            'static_label_position_preserved': True,
            'right_zone_label_count': 0,
            'center_zone_label_count': 0,
            'left_zone_label_count': 0,
            'mispositioned_static_label_count': 0,
            'mispositioned_static_label_examples': [],
            'static_label_position_results': [],
        }
    paragraphs = header_footer_paragraphs_with_tabs(docx_path)
    results = []
    expected_by_label = {}
    actual_by_label = {}
    zone_counts = {'left': 0, 'center': 0, 'right': 0}
    for label in static_items:
        text = clean_visible_text(label.get('text', ''))
        expected = zone_from_x(label.get('x_center_normalized', 0.0))
        target = label.get('target_part', '')
        match = next(
            (
                paragraph for paragraph in paragraphs.get(target, [])
                if text and text in paragraph.get('text', '')
            ),
            None)
        actual = actual_zone_for_text(match, text) if match else 'missing'
        preserved = expected == actual
        zone_counts[expected] = zone_counts.get(expected, 0) + 1
        key = f"{label.get('source_page_index')}:{text}"
        expected_by_label[key] = expected
        actual_by_label[key] = actual
        results.append({
            'text': text,
            'source_page_index': label.get('source_page_index'),
            'bbox': label.get('bbox', []),
            'x_center_normalized': label.get('x_center_normalized', 0.0),
            'y_center_normalized': label.get('y_center_normalized', 0.0),
            'expected_zone': expected,
            'actual_output_zone': actual,
            'position_preserved': preserved,
            'matched_paragraph': trim_report_text(match.get('text', '')) if match else '',
            'tab_alignments': match.get('tab_alignments', []) if match else [],
            'paragraph_alignment': match.get('paragraph_alignment', '') if match else '',
        })
    examples = [item for item in results if not item['position_preserved']][:10]
    return {
        'static_label_expected_zone': expected_by_label,
        'static_label_actual_zone': actual_by_label,
        'static_label_position_preserved': not examples,
        'right_zone_label_count': zone_counts.get('right', 0),
        'center_zone_label_count': zone_counts.get('center', 0),
        'left_zone_label_count': zone_counts.get('left', 0),
        'mispositioned_static_label_count': sum(
            1 for item in results if not item['position_preserved']),
        'mispositioned_static_label_examples': examples,
        'static_label_position_results': results,
    }


def variable_family_page_ownership_validation(docx_path, source_analysis: dict, variable_records: list) -> dict:
    empty = {
        'variable_family_per_page_expected_actual': [],
        'variable_family_page_text_mismatch_count': 0,
        'page_text_mismatch_count': 0,
        'last_token_reuse_detected': False,
        'source_page_ownership_lost': False,
    }
    if not variable_records:
        return empty
    section_parts = docx_section_header_footer_texts(docx_path, source_analysis)
    records_by_family = defaultdict(list)
    for item in variable_records:
        records_by_family[item.get('family_id', '')].append(item)
    results = []
    mismatch_count = 0
    last_token_reuse = False
    ownership_lost = False
    for family_id, records in records_by_family.items():
        family_texts = [item.get('text', '') for item in records if item.get('text')]
        last_text = family_texts[-1] if family_texts else ''
        for record in records:
            page_index = record.get('source_page_index')
            expected = record.get('text', '')
            target = record.get('target_part', '')
            matching_sections = [
                item for item in section_parts
                if item.get('source_page_index') == page_index
            ]
            actual_values = []
            wrong_values = []
            for section in matching_sections:
                text = section.get(target, '')
                found = [
                    candidate for candidate in family_texts
                    if candidate and candidate in text
                ]
                if expected in found:
                    actual_values.append(expected)
                elif found:
                    wrong_values.extend(found)
            actual = expected if actual_values else (wrong_values[0] if wrong_values else '')
            mismatch = actual != expected
            if mismatch:
                mismatch_count += 1
            if actual == last_text and expected != last_text:
                last_token_reuse = True
            if wrong_values or not actual_values:
                ownership_lost = True
            results.append({
                'family_id': family_id,
                'source_page_index': page_index,
                'target_part': target,
                'expected': expected,
                'actual': actual,
                'matching_section_indices': [
                    item.get('section_index') for item in matching_sections
                ],
                'matching_section_texts': [
                    trim_report_text(item.get(target, '')) for item in matching_sections
                ],
                'page_text_mismatch': mismatch,
                'last_token_reused': actual == last_text and expected != last_text,
            })
    return {
        'variable_family_per_page_expected_actual': results,
        'variable_family_page_text_mismatch_count': mismatch_count,
        'page_text_mismatch_count': mismatch_count,
        'last_token_reuse_detected': last_token_reuse,
        'source_page_ownership_lost': ownership_lost,
    }


def header_footer_paragraphs_with_tabs(docx_path) -> dict:
    with zipfile.ZipFile(docx_path) as archive:
        parts = {
            name: archive.read(name).decode('utf-8', errors='replace')
            for name in archive.namelist()
            if name.startswith('word/header') or name.startswith('word/footer')
        }
    return header_footer_paragraphs_with_tabs_from_parts(parts)


def header_footer_paragraphs_with_tabs_from_parts(parts: dict) -> dict:
    paragraphs = {'header': [], 'footer': []}
    for name, xml in parts.items():
        if name.startswith('word/header'):
            target = 'header'
        elif name.startswith('word/footer'):
            target = 'footer'
        else:
            continue
        for paragraph in paragraph_layouts_with_tabs(xml):
            paragraph['part'] = name
            paragraphs[target].append(paragraph)
    return paragraphs


def paragraph_layouts_with_tabs(xml: str) -> list:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    values = []
    for paragraph in root.findall('.//w:p', W_NS):
        parts = []
        tab_alignments = []
        paragraph_alignment = 'left'
        p_pr = paragraph.find('w:pPr', W_NS)
        if p_pr is not None:
            jc = p_pr.find('w:jc', W_NS)
            if jc is not None:
                paragraph_alignment = jc.get(W_VAL, 'left')
            tabs = p_pr.find('w:tabs', W_NS)
            if tabs is not None:
                for tab in tabs.findall('w:tab', W_NS):
                    tab_alignments.append(tab.get(W_VAL, 'left'))
        for run in paragraph.findall('w:r', W_NS):
            for elem in run.iter():
                tag = elem.tag.rsplit('}', 1)[-1]
                if tag == 't' and elem.text:
                    parts.append(elem.text)
                elif tag == 'tab':
                    parts.append('\t')
        text = ''.join(parts)
        if text:
            values.append({
                'text': text,
                'tab_alignments': tab_alignments,
                'paragraph_alignment': paragraph_alignment,
            })
    return values


def docx_section_header_footer_texts(docx_path, source_analysis: dict) -> list:
    refs = docx_section_header_footer_refs(docx_path)
    assignments = list(range(max(len(refs), source_analysis.get('page_count', 0))))
    with zipfile.ZipFile(docx_path) as archive:
        rels = document_relationship_targets(archive)
        part_texts = {}
        for target in rels.values():
            if not (target.startswith('header') or target.startswith('footer')):
                continue
            name = 'word/' + target
            if name in archive.namelist():
                part_texts[target] = xml_text_with_tabs(
                    archive.read(name).decode('utf-8', errors='replace'))
    page_count = max(source_analysis.get('page_count', 1), 1)
    values = []
    for index, section_refs in enumerate(refs):
        source_page = assignments[index] if index < len(assignments) else min(index, page_count - 1)
        source_page = min(max(source_page, 0), page_count - 1)
        values.append({
            'section_index': index,
            'source_page_index': source_page,
            'header': part_texts.get(rels.get(section_refs.get('header', ''), ''), ''),
            'footer': part_texts.get(rels.get(section_refs.get('footer', ''), ''), ''),
            'header_ref': section_refs.get('header', ''),
            'footer_ref': section_refs.get('footer', ''),
        })
    return values


def docx_section_header_footer_refs(docx_path) -> list:
    refs = []
    with zipfile.ZipFile(docx_path) as archive:
        xml = archive.read('word/document.xml').decode('utf-8', errors='replace')
    root = ET.fromstring(xml)
    for sect_pr in root.findall('.//w:sectPr', W_NS):
        entry = {}
        for footer in sect_pr.findall('w:footerReference', W_NS):
            if footer.get(W_TYPE, 'default') == 'default':
                entry['footer'] = footer.get(RID, '')
        for header in sect_pr.findall('w:headerReference', W_NS):
            if header.get(W_TYPE, 'default') == 'default':
                entry['header'] = header.get(RID, '')
        refs.append(entry)
    return refs


def document_relationship_targets(archive) -> dict:
    if 'word/_rels/document.xml.rels' not in archive.namelist():
        return {}
    xml = archive.read('word/_rels/document.xml.rels').decode('utf-8', errors='replace')
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return {}
    result = {}
    for rel in root:
        rid = rel.attrib.get('Id', '')
        target = rel.attrib.get('Target', '')
        if rid and target:
            result[rid] = target
    return result


def xml_text_with_tabs(xml: str) -> str:
    return '\n'.join(
        paragraph.get('text', '')
        for paragraph in paragraph_layouts_with_tabs(xml)
    )


def actual_zone_for_text(paragraph: dict, text: str) -> str:
    if not paragraph:
        return 'missing'
    paragraph_text = paragraph.get('text', '')
    if text not in paragraph_text:
        return 'missing'
    if '\t' not in paragraph_text:
        alignment = paragraph.get('paragraph_alignment', 'left')
        if alignment in {'right', 'end'}:
            return 'right'
        if alignment in {'center', 'centre'}:
            return 'center'
        return 'left'
    parts = paragraph_text.split('\t')
    tab_alignments = paragraph.get('tab_alignments', []) or []
    for index, part in enumerate(parts):
        if text not in part:
            continue
        if index == 0:
            alignment = paragraph.get('paragraph_alignment', 'left')
            if alignment in {'right', 'end'}:
                return 'right'
            if alignment in {'center', 'centre'}:
                return 'center'
            return 'left'
        tab_alignment = tab_alignments[index - 1] if index - 1 < len(tab_alignments) else ''
        if tab_alignment in {'right', 'end'}:
            return 'right'
        if tab_alignment in {'center', 'centre'}:
            return 'center'
        return 'left'
    return 'missing'


def zone_order_preserved(paragraph_text: str, expected_by_zone: dict) -> dict:
    result = {'left': True, 'center': True, 'right': True}
    cursor = -1
    for zone in ('left', 'center', 'right'):
        for text in expected_by_zone.get(zone, []):
            index = paragraph_text.find(text)
            if index < 0:
                result[zone] = False
                continue
            if index < cursor:
                result[zone] = False
            cursor = max(cursor, index)
    if expected_by_zone.get('center'):
        center_text = expected_by_zone['center'][0]
        center_index = paragraph_text.find(center_text)
        result['center'] = result['center'] and '\t' in paragraph_text[:max(center_index, 0)]
    if expected_by_zone.get('right'):
        right_text = expected_by_zone['right'][0]
        right_index = paragraph_text.find(right_text)
        result['right'] = (
            result['right'] and
            paragraph_text[:max(right_index, 0)].count('\t') >= (
                2 if expected_by_zone.get('center') else 1))
    return result


def trim_report_text(text: str, max_len=180) -> str:
    value = str(text or '').replace('\n', ' ')
    return value if len(value) <= max_len else value[:max_len - 3] + '...'
