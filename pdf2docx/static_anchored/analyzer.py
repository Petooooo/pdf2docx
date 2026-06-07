# -*- coding: utf-8 -*-

"""Internal analysis helpers for static source-page anchored fidelity mode."""

import copy
import re
from collections import defaultdict


REGION_TOP = 'top'
REGION_BOTTOM = 'bottom'
REGION_BODY = 'body'
ROLE_HEADER = 'header'
ROLE_FOOTER = 'footer'
ROLE_PAGE_NUMBER = 'page_number'
STATIC_MODE_SOURCE = 'internal_static_anchored_visual_fidelity'


def build_static_anchored_plan(layout: dict) -> dict:
    """Build a JSON-serializable static anchored plan from a layout report."""
    source_analysis = analyze_source_pages(layout)
    static_labels = static_page_label_records(source_analysis)
    variable_families = variable_text_families(
        source_analysis,
        excluded_ref_keys=visual_item_ref_keys(static_labels))
    variable_records = variable_family_records(variable_families)
    static_items = static_labels + variable_records
    source_map = build_source_page_layout_map(source_analysis)
    source_line_groups = build_source_line_groups(
        source_analysis,
        source_map,
        static_items)
    candidates = static_filter_candidates(
        source_analysis,
        static_items,
        source_analysis.get('page_count', 0))
    report = {
        'mode': 'static_anchored',
        'page_count': source_analysis.get('page_count', 0),
        'static_label_count': len(static_labels),
        'variable_family_count': len(variable_families),
        'variable_record_count': len(variable_records),
        'filter_candidate_count': len(candidates),
        'detected_policy_types': source_analysis.get('detected_policy_types', []),
        'detected_coverage_policies': source_analysis.get('detected_coverage_policies', []),
        'source_line_group_count': len(source_line_groups),
    }
    return {
        'mode': 'static_anchored',
        'source_analysis': source_analysis,
        'source_page_layout_map': source_map,
        'static_labels': static_labels,
        'variable_families': variable_families,
        'variable_records': variable_records,
        'static_items': static_items,
        'source_line_groups': source_line_groups,
        'filter_candidates': candidates,
        'report': report,
    }


def analyze_source_pages(layout: dict) -> dict:
    pages = layout.get('pages', []) or []
    page_count = len(pages)
    observations = []
    for page in pages:
        for block in page.get('text_blocks', []) or []:
            if block.get('region') not in {REGION_TOP, REGION_BOTTOM}:
                continue
            if not is_candidate_boundary_text(block):
                continue
            observations.append(observation_from_block(page, block))

    repeated = repeated_boundary_families(observations, page_count)
    headers = [family for family in repeated if family['role'] == ROLE_HEADER]
    footers = [family for family in repeated if family['role'] == ROLE_FOOTER]
    page_number_family = source_page_number_family(observations, page_count)
    odd_even_pair = detect_odd_even_pair(headers)
    delayed_policies = {
        'front_matter_excluded',
        'delayed_start',
        'contiguous_suffix',
        'contiguous_range',
    }
    if odd_even_pair:
        selected_headers = [odd_even_pair['odd_family'], odd_even_pair['even_family']]
    else:
        selected_headers = [
            family for family in headers
            if family.get('coverage_policy') in {
                'all_pages',
                'all_pages_except_first',
                *delayed_policies,
            } and family.get('safe_for_static_anchored')
        ][:1]
    selected_footers = [
        family for family in footers
        if family.get('coverage_policy') in {
            'all_pages',
            'all_pages_except_first',
            *delayed_policies,
            'odd_pages',
            'even_pages',
        } and family.get('safe_for_static_anchored')
    ][:2]
    policy_types = []
    if odd_even_pair:
        policy_types.append('first_page_excluded_odd_even')
    elif selected_headers:
        policy_types.append(selected_headers[0]['coverage_policy'])
    if selected_footers:
        policy_types.append('footer_' + selected_footers[0]['coverage_policy'])
    if page_number_family:
        policy_types.append('page_number_' + page_number_family['sequence_status'])
    detected_coverage = sorted({
        family.get('coverage_policy', '')
        for family in repeated
        if family.get('coverage_policy')
    })
    return {
        'page_count': page_count,
        'observations': observations,
        'source_page_body_texts': source_page_body_texts(layout),
        'repeated_families': repeated,
        'header_families': headers,
        'footer_families': footers,
        'selected_header_families': selected_headers,
        'selected_footer_families': selected_footers,
        'page_number_family': page_number_family,
        'odd_even_pair': odd_even_pair,
        'first_page_excluded': bool(
            odd_even_pair or
            any(family.get('coverage_policy') == 'all_pages_except_first' for family in headers)),
        'detected_policy_types': policy_types,
        'detected_coverage_policies': detected_coverage,
        'delayed_start_detected': any(
            policy in detected_coverage
            for policy in {'delayed_start', 'contiguous_suffix'}),
        'front_matter_excluded_detected': 'front_matter_excluded' in detected_coverage,
    }


def observation_from_block(page: dict, block: dict) -> dict:
    bbox = [float(value) for value in (block.get('bbox', []) or [])]
    width = float(page.get('width') or 0.0)
    height = float(page.get('height') or 0.0)
    x_center = (bbox[0] + bbox[2]) / 2.0 if len(bbox) >= 4 else None
    y_center = (bbox[1] + bbox[3]) / 2.0 if len(bbox) >= 4 else None
    style = block.get('style_properties') or {}
    page_index = int(page.get('page_index', 0))
    region = block.get('region', '')
    normalized = block.get('normalized_text') or normalize_text(block.get('text', ''))
    return {
        'source_page_index': page_index,
        'source_page_number_one_based': page_index + 1,
        'source_page_parity': 'odd' if page_index % 2 == 0 else 'even',
        'text': clean_visible_text(block.get('text', '')),
        'normalized_text': normalized,
        'fingerprint': block.get('fingerprint', ''),
        'block_index': block.get('block_index'),
        'region': region,
        'role': observation_role(block),
        'bbox': bbox,
        'x_center_normalized': round(x_center / width, 5) if width and x_center is not None else 0.0,
        'y_center_normalized': round(y_center / height, 5) if height and y_center is not None else 0.0,
        'font_name': style.get('font_name', ''),
        'font_size': style.get('font_size'),
        'bold': style.get('bold'),
        'italic': style.get('italic'),
        'color': style.get('color'),
        'alignment': infer_zone_from_bbox(bbox, width),
        'page_width': width,
        'page_height': height,
        'page_number_template': parse_page_number_template(block.get('text', '')),
    }


def is_candidate_boundary_text(block: dict) -> bool:
    text = normalize_text(block.get('text', ''))
    normalized = normalize_text(block.get('normalized_text', ''))
    if not text:
        return False
    if normalized in {'<image>', '<shape>'}:
        return False
    if text.startswith('<') and text.endswith('>') and normalized != '<page_number>':
        return False
    return True


def observation_role(block: dict) -> str:
    if block.get('normalized_text') == '<page_number>':
        return ROLE_PAGE_NUMBER
    if block.get('region') == REGION_TOP:
        return ROLE_HEADER
    if block.get('region') == REGION_BOTTOM:
        return ROLE_FOOTER
    return 'diagnostic'


def repeated_boundary_families(observations: list, page_count: int) -> list:
    grouped = defaultdict(list)
    for item in observations:
        if item.get('role') == ROLE_PAGE_NUMBER:
            continue
        grouped[(item.get('role'), item.get('region'), item.get('normalized_text'))].append(item)

    families = []
    for index, ((role, region, text), items) in enumerate(grouped.items(), start=1):
        pages = sorted({item['source_page_index'] for item in items})
        if len(pages) < 2:
            continue
        coverage_info = coverage_info_for_pages(pages, page_count)
        family_items = list(items)
        if coverage_info['coverage_policy'] == 'sparse_or_unstable' and 0 in pages:
            without_first = [item for item in items if item['source_page_index'] > 0]
            without_first_pages = sorted({item['source_page_index'] for item in without_first})
            without_first_info = coverage_info_for_pages(without_first_pages, page_count)
            if without_first_info['coverage_policy'] in {
                    'odd_pages',
                    'even_pages',
                    'all_pages_except_first',
                    'front_matter_excluded',
                    'delayed_start',
                    'contiguous_suffix'}:
                coverage_info = without_first_info
                family_items = without_first
                pages = without_first_pages
        geometry = geometry_summary(family_items)
        families.append({
            'family_id': f'{role}-{index}',
            'role': role,
            'region': region,
            'text': clean_visible_text(items[0].get('text', '')),
            'normalized_text': text,
            'fingerprint': items[0].get('fingerprint', ''),
            'observations': family_items,
            'pages': pages,
            'coverage_policy': coverage_info['coverage_policy'],
            'coverage': coverage_info,
            'geometry': geometry,
            'safe_for_static_anchored': bool(
                geometry['stable'] and
                coverage_info.get('applicable_support_ratio', 0) >= 0.9 and
                len(pages) >= 2),
        })
    return families


def coverage_info_for_pages(pages: list, page_count: int) -> dict:
    pages = sorted(set(page for page in pages if page is not None))
    base = {
        'coverage_policy': 'sparse_or_unstable',
        'start_page_index': pages[0] if pages else None,
        'end_page_index': pages[-1] if pages else None,
        'applicable_page_indices': [],
        'observed_page_indices': pages,
        'applicable_support_ratio': 0.0,
        'global_support_ratio': ratio(len(pages), page_count),
        'front_matter_excluded_page_count': 0,
    }
    if not pages or page_count <= 0:
        return base
    all_pages = list(range(page_count))
    all_except_first = list(range(1, page_count))
    odd_pages = [index for index in range(page_count) if index % 2 == 0]
    even_pages = [index for index in range(page_count) if index % 2 == 1]
    odd_after_first = [index for index in odd_pages if index > 0]
    policy = 'sparse_or_unstable'
    applicable = []
    if pages == all_pages:
        policy = 'all_pages'
        applicable = all_pages
    elif pages == all_except_first and page_count > 1:
        policy = 'all_pages_except_first'
        applicable = all_except_first
    elif pages == odd_pages and len(pages) >= 2:
        policy = 'odd_pages'
        applicable = odd_pages
    elif pages == odd_after_first and len(pages) >= 2:
        policy = 'odd_pages_after_front_matter'
        applicable = odd_after_first
    elif pages == even_pages and len(pages) >= 2:
        policy = 'even_pages'
        applicable = even_pages
    elif is_contiguous(pages):
        start = pages[0]
        end = pages[-1]
        applicable = list(range(start, end + 1))
        if end == page_count - 1 and len(pages) >= 2:
            applicable = list(range(start, page_count))
            policy = 'front_matter_excluded' if start <= 2 else 'delayed_start'
            if start > 0:
                base['contiguous_suffix'] = True
        else:
            policy = 'contiguous_range'
    else:
        sequence = arithmetic_page_sequence_info(pages, page_count)
        if sequence.get('supported'):
            base.update(sequence)
            return base
    base.update({
        'coverage_policy': policy,
        'applicable_page_indices': applicable,
        'applicable_support_ratio': ratio(
            len(set(pages).intersection(applicable)),
            len(applicable)),
        'front_matter_excluded_page_count': (
            pages[0] if policy in {
                'front_matter_excluded',
                'delayed_start',
                'contiguous_suffix',
                'odd_pages_after_front_matter'} else 0),
    })
    return base


def arithmetic_page_sequence_info(pages: list, page_count: int) -> dict:
    pages = sorted(set(page for page in pages if page is not None))
    if len(pages) < 2:
        return {'supported': False}
    diffs = [b - a for a, b in zip(pages, pages[1:])]
    if not diffs or len(set(diffs)) != 1:
        return {'supported': False}
    step = diffs[0]
    if step <= 0:
        return {'supported': False}
    start = pages[0]
    applicable = list(range(start, page_count, step))
    if set(pages) != set(applicable):
        applicable = list(range(start, pages[-1] + 1, step))
    support_ratio = ratio(len(set(pages).intersection(applicable)), len(applicable))
    if support_ratio < 0.9:
        return {'supported': False}
    one_based = [page + 1 for page in pages]
    if step == 2 and all(value % 2 == 1 for value in one_based):
        policy = 'odd_pages_after_front_matter' if start > 0 else 'odd_pages'
    elif step == 2 and all(value % 2 == 0 for value in one_based):
        policy = 'even_pages_after_front_matter' if start > 0 else 'even_pages'
    else:
        policy = f'every_{step}_pages_after_start'
    return {
        'supported': True,
        'coverage_policy': policy,
        'start_page_index': start,
        'end_page_index': pages[-1],
        'applicable_page_indices': applicable,
        'observed_page_indices': pages,
        'applicable_support_ratio': support_ratio,
        'global_support_ratio': ratio(len(pages), page_count),
        'front_matter_excluded_page_count': start,
        'step': step,
    }


def detect_odd_even_pair(headers: list):
    odd_candidates = [
        family for family in headers
        if family.get('coverage_policy') in {'odd_pages', 'odd_pages_after_front_matter'} and
        family.get('geometry', {}).get('stable')
    ]
    even_candidates = [
        family for family in headers
        if family.get('coverage_policy') in {'even_pages', 'even_pages_after_front_matter'} and
        family.get('geometry', {}).get('stable')
    ]
    if not odd_candidates or not even_candidates:
        return None
    best = None
    best_score = -1
    for odd in odd_candidates:
        for even in even_candidates:
            y_delta = abs(
                (odd.get('geometry', {}).get('y_center_median') or 0) -
                (even.get('geometry', {}).get('y_center_median') or 0))
            if y_delta > 0.02:
                continue
            mirrored = (
                odd.get('geometry', {}).get('alignment_values') !=
                even.get('geometry', {}).get('alignment_values'))
            score = 2 - y_delta + (0.2 if mirrored else 0)
            if score > best_score:
                best_score = score
                best = {
                    'policy_type': 'first_page_excluded_odd_even',
                    'odd_family': odd,
                    'even_family': even,
                    'y_delta': round(y_delta, 5),
                    'mirrored_alignment': mirrored,
                    'safe_for_static_anchored': True,
                }
    return best


def source_page_number_family(observations: list, page_count: int):
    records = [
        item for item in observations
        if item.get('role') == ROLE_PAGE_NUMBER and
        item.get('region') in {REGION_TOP, REGION_BOTTOM} and
        item.get('page_number_template', {}).get('supported')
    ]
    if not records:
        return None
    grouped = defaultdict(list)
    for item in records:
        template = item['page_number_template']
        grouped[(item['region'], template['prefix'], template['suffix'])].append(item)
    best = None
    best_score = -1
    for (region, prefix, suffix), items in grouped.items():
        by_page = {}
        for item in sorted(items, key=lambda value: (
                value['source_page_index'],
                abs((value.get('y_center_normalized') or 0) - (0.96 if region == REGION_BOTTOM else 0.04)))):
            by_page.setdefault(item['source_page_index'], item)
        unique = [by_page[index] for index in sorted(by_page)]
        if len(unique) < 2:
            continue
        numbers = [item['page_number_template']['number'] for item in unique]
        pages = [item['source_page_index'] for item in unique]
        offsets = [number - page for number, page in zip(numbers, pages)]
        consecutive = all(
            numbers[index + 1] - numbers[index] == pages[index + 1] - pages[index]
            for index in range(len(numbers) - 1))
        offset_consistent = len(set(offsets)) == 1
        geometry = geometry_summary(unique)
        coverage = coverage_info_for_pages(pages, page_count)
        score = len(unique) + (2 if consecutive else 0) + (2 if offset_consistent else 0)
        if geometry['stable']:
            score += 1
        if score > best_score:
            best_score = score
            best = {
                'family_id': f'page-number-{region}',
                'role': ROLE_PAGE_NUMBER,
                'region': region,
                'target_part': 'header' if region == REGION_TOP else 'footer',
                'prefix': prefix,
                'suffix': suffix,
                'start_number': numbers[0],
                'numbers': numbers,
                'pages': pages,
                'source_offsets': offsets,
                'sequence_status': (
                    'offset_consistent' if offset_consistent else
                    'consecutive' if consecutive else
                    'diagnostic'),
                'coverage_policy': coverage['coverage_policy'],
                'coverage': coverage,
                'geometry': geometry,
                'observations': unique,
                'safe_for_static_anchored': bool(
                    (consecutive or offset_consistent) and
                    coverage.get('coverage_policy') in {
                        'all_pages',
                        'all_pages_except_first',
                        'odd_pages',
                        'even_pages',
                        'odd_pages_after_front_matter',
                        'even_pages_after_front_matter',
                    }),
            }
    return best


def static_page_label_records(source_analysis: dict) -> list:
    records = []
    seen = set()
    family_ref_keys = page_number_family_ref_keys(source_analysis.get('page_number_family'))
    for item in source_analysis.get('observations', []) or []:
        region = item.get('region', '')
        if region not in {REGION_TOP, REGION_BOTTOM}:
            continue
        text = clean_visible_text(item.get('text', ''))
        if not text or text == '<image>':
            continue
        if not is_static_page_label_observation(item, family_ref_keys):
            continue
        key = (item.get('source_page_index'), item.get('block_index'), region)
        if key in seen:
            continue
        seen.add(key)
        record = dict(item)
        record.update({
            'text': text,
            'target_part': 'footer' if region == REGION_BOTTOM else 'header',
            'family_type': 'static_page_label',
            'source_ref': source_ref_from_observation(item),
        })
        records.append(record)
    return sorted(records, key=observation_sort_key)


def variable_text_families(source_analysis: dict, excluded_ref_keys=None) -> list:
    excluded_ref_keys = excluded_ref_keys or set()
    observations = []
    for item in source_analysis.get('observations', []) or []:
        region = item.get('region', '')
        if region not in {REGION_TOP, REGION_BOTTOM}:
            continue
        text = clean_visible_text(item.get('text', ''))
        if not text or text == '<image>' or text.startswith('<'):
            continue
        ref_key = (item.get('source_page_index'), item.get('block_index'), region)
        if ref_key in excluded_ref_keys:
            continue
        observations.append(item)

    buckets = defaultdict(list)
    for item in observations:
        zone = zone_from_x(item.get('x_center_normalized', 0.0))
        y_band = round(float(item.get('y_center_normalized') or 0.0) / 0.025)
        font_size = round(float(item.get('font_size') or 0), 1)
        buckets[(item.get('region', ''), zone, y_band, font_size)].append(item)

    families = []
    for index, ((region, zone, y_band, font_size), records) in enumerate(sorted(buckets.items())):
        if len(records) < 2:
            continue
        records = sorted(records, key=lambda item: item.get('source_page_index', -1))
        pages = [item.get('source_page_index') for item in records]
        texts = [clean_visible_text(item.get('text', '')) for item in records]
        template = common_variable_template(texts)
        if not template.get('supported'):
            continue
        coverage = coverage_info_for_pages(pages, source_analysis.get('page_count', 0))
        if coverage.get('coverage_policy') == 'sparse_or_unstable':
            sequence = arithmetic_page_sequence_info(pages, source_analysis.get('page_count', 0))
            if sequence.get('supported'):
                coverage.update(sequence)
        if coverage.get('coverage_policy') == 'sparse_or_unstable':
            continue
        geometry = variable_geometry_status(records, zone)
        if not geometry.get('stable'):
            continue
        families.append({
            'family_id': f'variable-{region}-{index + 1}',
            'family_type': f"variable_text_{'footer' if region == REGION_BOTTOM else 'header'}",
            'stable_prefix': template['stable_prefix'],
            'stable_suffix': template['stable_suffix'],
            'variable_tokens': template['variable_tokens'],
            'variable_token_type': template['variable_token_type'],
            'template_pattern': template.get('template_pattern', ''),
            'numeric_sequence': numeric_sequence(template['variable_tokens']),
            'step': numeric_step(template['variable_tokens']),
            'start_source_page_index': pages[0] if pages else None,
            'source_page_indices': pages,
            'pages': pages,
            'coverage_policy': coverage.get('coverage_policy', ''),
            'coverage': coverage,
            'target_part': 'footer' if region == REGION_BOTTOM else 'header',
            'region': region,
            'zone': zone,
            'y_line_band': y_band,
            'bbox_stability': geometry,
            'style_stability': variable_style_status(records),
            'confidence': 0.96,
            'safe_for_static_anchored': True,
            'observations': records,
        })
    return families


def variable_family_records(families: list) -> list:
    records = []
    for family in families or []:
        for item in family.get('observations', []) or []:
            record = dict(item)
            record.update({
                'text': clean_visible_text(item.get('text', '')),
                'target_part': family.get('target_part', ''),
                'family_id': family.get('family_id', ''),
                'family_type': family.get('family_type', ''),
                'stable_prefix': family.get('stable_prefix', ''),
                'stable_suffix': family.get('stable_suffix', ''),
                'variable_token_type': family.get('variable_token_type', ''),
                'source_ref': source_ref_from_observation(item),
            })
            records.append(record)
    return sorted(records, key=observation_sort_key)


def build_source_page_layout_map(source_analysis: dict) -> dict:
    page_count = source_analysis.get('page_count', 0)
    pages = []
    for page_index in range(page_count):
        header_family = family_for_page(source_analysis.get('selected_header_families', []), page_index)
        footer_family = family_for_page(source_analysis.get('selected_footer_families', []), page_index)
        page_number_family = source_analysis.get('page_number_family')
        pages.append({
            'source_page_index': page_index,
            'source_page_number_one_based': page_index + 1,
            'source_page_parity': 'odd' if page_index % 2 == 0 else 'even',
            'header_policy': header_family.get('coverage_policy', 'none') if header_family else 'none',
            'header_family_id': header_family.get('family_id', '') if header_family else '',
            'footer_policy': footer_family.get('coverage_policy', 'none') if footer_family else 'none',
            'footer_family_id': footer_family.get('family_id', '') if footer_family else '',
            'page_number_family_id': (
                page_number_family.get('family_id', '')
                if page_number_family and page_index in page_number_family.get('pages', [])
                else ''),
        })
    return {
        'source_page_count': page_count,
        'policy': 'source_pdf_page_index_anchored',
        'pages': pages,
    }


def build_source_line_groups(source_analysis: dict, source_map: dict, static_items: list) -> list:
    items_by_page = labels_by_source_page(static_items)
    groups = []
    for page_entry in source_map.get('pages', []) or []:
        page_index = page_entry['source_page_index']
        for part_name, family_key, target_part in (
                ('header', 'selected_header_families', 'header'),
                ('footer', 'selected_footer_families', 'footer')):
            items = []
            for family in families_for_page(source_analysis.get(family_key, []), page_index):
                observation = family_observation_for_page(family, page_index)
                items.append(static_item_from_observation(
                    family.get('text', ''),
                    observation,
                    target_part,
                    'family'))
            for label in items_by_page.get(page_index, []):
                if label.get('target_part') == target_part:
                    items.append(static_item_from_observation(
                        label.get('text', ''),
                        label,
                        target_part,
                        'static_label'))
            for index, group in enumerate(group_line_items(items)):
                zones = {item.get('zone', 'left') for item in group.get('items', [])}
                if len(zones) < 2:
                    continue
                groups.append({
                    'group_id': f'{page_index}-{part_name}-{index}',
                    'source_page_index': page_index,
                    'target_part': target_part,
                    'y_center': group.get('y_center', 0.0),
                    'zones': sorted(zones),
                    'zone_texts': {
                        zone: [
                            item.get('text', '')
                            for item in group.get('items', [])
                            if item.get('zone') == zone
                        ]
                        for zone in ('left', 'center', 'right')
                    },
                    'items': group.get('items', []),
                })
    return groups


def static_filter_candidates(source_analysis: dict, static_items: list, page_count: int) -> list:
    grouped = defaultdict(list)
    for record in static_items or []:
        region = record.get('region', '')
        role = static_candidate_role(record)
        grouped[(region, role)].append(record)
    candidates = []
    for (region, role), records in sorted(grouped.items()):
        candidates.append(static_filter_candidate(region, role, records, page_count))
    return candidates


def static_filter_candidate(region: str, role: str, records: list, page_count: int) -> dict:
    first = records[0]
    return {
        'candidate_id': f'static-source-label-{region}-{role}',
        'fingerprint': f'static-source-label-{region}-{role}',
        'action': 'would_exclude',
        'proposed_role': role,
        'region': region,
        'regions': [region],
        'affected_pages': sorted({item.get('source_page_index') for item in records}),
        'support_count': len(records),
        'page_count': page_count,
        'automatic_decision': 'auto_exclude',
        'automatic_confidence': 0.95,
        'automatic_evidence': [
            'source_page_static_visual_label',
            'exact_source_block_ref_filtering',
            f"target_part:{'footer' if region == REGION_BOTTOM else 'header'}",
            f'static_candidate_role:{role}',
        ],
        'filter_fingerprints': sorted({
            item.get('fingerprint', '')
            for item in records
            if item.get('fingerprint')
        }),
        'filter_block_refs': [
            source_ref_from_observation(item)
            for item in records
        ],
        'metadata_override': metadata_from_observation(first),
        'reason': 'Internal static source-page visual fidelity candidate.',
    }


def build_static_filtering_config(plan: dict, LayoutAnalyzer):
    """Build the existing internal filtered-parse config for a static plan."""
    candidates = copy.deepcopy(plan.get('filter_candidates') or [])
    decisions = {
        'decisions': [decision_for_candidate(candidate) for candidate in candidates],
        'summary': {
            'candidate_count': len(candidates),
            'decision_counts': {'approve_exclude': len(candidates)},
            'manual_review_required': False,
            'source': STATIC_MODE_SOURCE,
        },
    }
    dry_run = {
        'candidates': candidates,
        'summary': {
            'candidate_count': len(candidates),
            'static_source_label_candidate_count': len(candidates),
        },
    }
    return LayoutAnalyzer.build_reviewed_filtering_internal_config({
        'enabled': bool(candidates),
        'mode': 'filtered_parse_experiment',
        'review_decisions': decisions,
        'dry_run_report_override': dry_run,
        'require_explicit_approval': True,
        'allow_raw_would_exclude': False,
        'allow_unsure': False,
        'allow_rejected': False,
        'protect_body_region': True,
        'protect_layout_placeholders': True,
        'fail_closed_on_warning': False,
    })


def recommend_static_anchored_mode(validation: dict, plan: dict) -> str:
    if not validation.get('safety_gate_passed'):
        return 'diagnostic_only'
    if plan.get('static_items') or plan.get('variable_families'):
        return 'static_anchored'
    return 'existing_auto_reviewed'


def decision_for_candidate(candidate: dict) -> dict:
    return {
        'candidate_id': candidate.get('candidate_id', ''),
        'fingerprint': candidate.get('fingerprint', ''),
        'proposed_role': candidate.get('proposed_role', ''),
        'manual_decision': 'approve_exclude',
        'explicit_approval': True,
        'reason': STATIC_MODE_SOURCE,
    }


def static_candidate_role(record: dict) -> str:
    family_type = record.get('family_type', '')
    region = record.get('region', '')
    if family_type == 'variable_text_footer':
        return ROLE_FOOTER
    if family_type == 'variable_text_header':
        return ROLE_HEADER
    if region == REGION_TOP and record.get('role') == ROLE_HEADER:
        return ROLE_HEADER
    return ROLE_PAGE_NUMBER


def labels_by_source_page(static_items: list) -> dict:
    grouped = defaultdict(list)
    for record in static_items or []:
        grouped[record.get('source_page_index')].append(record)
    return grouped


def families_for_page(families: list, page_index: int) -> list:
    return [
        family for family in families or []
        if page_index in set(family.get('pages', []) or [])
    ]


def family_for_page(families: list, page_index: int):
    matches = families_for_page(families, page_index)
    return matches[0] if matches else None


def family_observation_for_page(family: dict, page_index: int) -> dict:
    for item in family.get('observations', []) or []:
        if item.get('source_page_index') == page_index:
            return item
    return (family.get('observations') or [{}])[0]


def static_item_from_observation(text: str, observation: dict, target_part: str, source_kind: str) -> dict:
    x = observation.get('x_center_normalized', 0.0)
    return {
        'text': clean_visible_text(text),
        'observation': observation,
        'alignment': zone_from_x(x),
        'zone': zone_from_x(x),
        'x': x,
        'y': observation.get('y_center_normalized', 0.0),
        'target_part': target_part,
        'source_kind': source_kind,
        'family_id': observation.get('family_id', ''),
        'family_type': observation.get('family_type', ''),
        'source_ref': observation.get('source_ref') or source_ref_from_observation(observation),
    }


def group_line_items(items: list) -> list:
    groups = []
    for item in sorted(items or [], key=lambda value: (value.get('y', 0.0), value.get('x', 0.0))):
        if not item.get('text'):
            continue
        placed = False
        for group in groups:
            if abs(group['y_center'] - item.get('y', 0.0)) <= 0.018:
                group['items'].append(item)
                values = [member.get('y', 0.0) for member in group['items']]
                group['y_center'] = sum(values) / len(values)
                placed = True
                break
        if not placed:
            groups.append({'y_center': item.get('y', 0.0), 'items': [item]})
    result = []
    for group in groups:
        unique = []
        seen = set()
        for item in sorted(group['items'], key=lambda value: value.get('x', 0.0)):
            ref = item.get('source_ref') or {}
            key = (
                item.get('zone'),
                clean_visible_text(item.get('text', '')),
                ref.get('page_index'),
                ref.get('block_index'),
                ref.get('region'),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        if unique:
            result.append({'y_center': group['y_center'], 'items': unique})
    return sorted(result, key=lambda group: group['y_center'])


def source_ref_from_observation(item: dict) -> dict:
    return {
        'fingerprint': item.get('fingerprint', ''),
        'page_index': item.get('source_page_index'),
        'block_index': item.get('block_index'),
        'region': item.get('region', ''),
    }


def metadata_from_observation(observation: dict) -> dict:
    return {
        'bbox': observation.get('bbox', []),
        'page_width': observation.get('page_width'),
        'page_height': observation.get('page_height'),
        'font_name': observation.get('font_name'),
        'font_size': observation.get('font_size'),
        'bold': observation.get('bold'),
        'italic': observation.get('italic'),
        'color': observation.get('color'),
        'alignment': observation.get('alignment') or zone_from_x(observation.get('x_center_normalized', 0.0)),
        'region': observation.get('region'),
    }


def is_static_page_label_observation(item: dict, family_ref_keys: set) -> bool:
    text = clean_visible_text(item.get('text', ''))
    normalized = item.get('normalized_text', '')
    region = item.get('region', '')
    ref_key = (item.get('source_page_index'), item.get('block_index'), region)
    if region == REGION_BOTTOM and item.get('role') == ROLE_PAGE_NUMBER and ref_key in family_ref_keys:
        return True
    if looks_like_explicit_page_label(text):
        return True
    if region == REGION_BOTTOM and normalized == '<page_number>' and ref_key in family_ref_keys:
        return True
    return False


def looks_like_explicit_page_label(text: str) -> bool:
    value = clean_visible_text(text)
    if not value:
        return False
    lower = value.lower()
    roman = r'[ivxlcdm]+'
    patterns = [
        rf'^page\s+({roman}|\d+)(\s+of\s+\d+)?$',
        rf'^p\.\s*({roman}|\d+)(\s+of\s+\d+)?$',
        r'^페이지\s+\d+$',
        r'^[-–—]\s*\d+\s*[-–—]$',
        r'^\d+\s*/\s*\d+$',
        r'^\d+[-–—]\d+$',
        r'^page\s+\d+\s*/\s*\d+$',
    ]
    return any(re.match(pattern, lower) for pattern in patterns)


def page_number_family_ref_keys(family: dict) -> set:
    keys = set()
    for item in (family or {}).get('observations', []) or []:
        keys.add((item.get('source_page_index'), item.get('block_index'), item.get('region')))
    return keys


def visual_item_ref_keys(items: list) -> set:
    keys = set()
    for item in items or []:
        ref = item.get('source_ref') or {}
        keys.add((ref.get('page_index'), ref.get('block_index'), ref.get('region')))
    return keys


def common_variable_template(texts: list) -> dict:
    if len(set(texts)) == 1:
        return {'supported': False, 'reason': 'text_not_variable'}
    pipe_template = pipe_numeric_template(texts)
    if pipe_template.get('supported'):
        return pipe_template
    prefix = common_prefix(texts)
    suffix = common_suffix([text[len(prefix):] for text in texts])
    tokens = []
    for text in texts:
        end = len(text) - len(suffix) if suffix else len(text)
        tokens.append(text[len(prefix):end])
    if not prefix or any(not token for token in tokens):
        return {'supported': False, 'reason': 'missing_prefix_or_token'}
    token_type = variable_token_type(tokens)
    if token_type == 'unknown':
        return {'supported': False, 'reason': 'unsupported_variable_token'}
    return {
        'supported': True,
        'stable_prefix': prefix,
        'stable_suffix': suffix,
        'variable_tokens': tokens,
        'variable_token_type': token_type,
        'template_pattern': 'common_prefix_suffix',
    }


def pipe_numeric_template(texts: list) -> dict:
    matches = []
    for text in texts:
        match = re.match(r'^(?P<title>.+?)\s*\|\s*(?P<number>\d+)\s*$', text)
        if not match:
            return {'supported': False, 'reason': 'not_pipe_numeric_template'}
        matches.append(match)
    numbers = [match.group('number') for match in matches]
    if variable_token_type(numbers) != 'arabic':
        return {'supported': False, 'reason': 'pipe_token_not_numeric'}
    titles = [match.group('title') for match in matches]
    title_prefix = common_prefix(titles).rstrip()
    return {
        'supported': True,
        'stable_prefix': (title_prefix + ' | ') if title_prefix else '',
        'stable_suffix': '',
        'variable_tokens': numbers,
        'variable_token_type': 'arabic',
        'template_pattern': 'pipe_numeric_suffix',
        'variable_titles': titles,
    }


def parse_page_number_template(text: str) -> dict:
    raw = normalize_text(text)
    patterns = [
        r'^(?P<prefix>Page\s+)(?P<number>\d+)(?P<suffix>\s+of\s+\d+)?$',
        r'^(?P<prefix>p\.\s*)(?P<number>\d+)(?P<suffix>)$',
        r'^(?P<prefix>페이지\s+)(?P<number>\d+)(?P<suffix>)$',
        r'^(?P<prefix>[-—]\s*)(?P<number>\d+)(?P<suffix>\s*[-—])$',
        r'^(?P<prefix>)(?P<number>\d+)(?P<suffix>\s*/\s*\d+)$',
        r'^(?P<prefix>\d+[-–—])(?P<number>\d+)(?P<suffix>)$',
        r'^(?P<prefix>)(?P<number>\d+)(?P<suffix>)$',
    ]
    for pattern in patterns:
        match = re.match(pattern, raw, re.IGNORECASE)
        if match:
            return {
                'raw_text': raw,
                'supported': True,
                'prefix': match.group('prefix') or '',
                'number': int(match.group('number')),
                'suffix': match.group('suffix') or '',
                'number_style': 'arabic',
            }
    return {'raw_text': raw, 'supported': False}


def geometry_summary(items: list) -> dict:
    xs = [float(item.get('x_center_normalized') or 0) for item in items]
    ys = [float(item.get('y_center_normalized') or 0) for item in items]
    alignments = sorted({zone_from_x(value) for value in xs})
    if not xs or not ys:
        return {'stable': False}
    return {
        'stable': max(xs) - min(xs) <= 0.08 and max(ys) - min(ys) <= 0.03,
        'x_center_min': min(xs),
        'x_center_max': max(xs),
        'y_center_min': min(ys),
        'y_center_max': max(ys),
        'x_center_median': median(xs),
        'y_center_median': median(ys),
        'alignment_values': alignments,
    }


def variable_geometry_status(records: list, zone=None) -> dict:
    xs = [geometry_anchor_x(item, zone) for item in records]
    ys = [float(item.get('y_center_normalized') or 0) for item in records]
    return {
        'stable': bool(xs and ys and max(xs) - min(xs) <= 0.05 and max(ys) - min(ys) <= 0.025),
        'x_anchor': zone or 'center',
        'x_min': min(xs) if xs else None,
        'x_max': max(xs) if xs else None,
        'y_min': min(ys) if ys else None,
        'y_max': max(ys) if ys else None,
    }


def variable_style_status(records: list) -> dict:
    sizes = {round(float(item.get('font_size') or 0), 1) for item in records}
    fonts = {item.get('font_name') for item in records if item.get('font_name')}
    return {
        'stable': len(sizes) <= 1 and len(fonts) <= 1,
        'font_sizes': sorted(sizes),
        'font_names': sorted(fonts),
    }


def geometry_anchor_x(item: dict, zone=None) -> float:
    bbox = item.get('bbox', []) or []
    width = float(item.get('page_width') or 0)
    if len(bbox) >= 4 and width:
        if zone == 'left':
            return round(float(bbox[0]) / width, 5)
        if zone == 'right':
            return round(float(bbox[2]) / width, 5)
    return float(item.get('x_center_normalized') or 0)


def infer_zone_from_bbox(bbox, page_width) -> str:
    if not bbox or len(bbox) < 4 or not page_width:
        return 'left'
    return zone_from_x(((float(bbox[0]) + float(bbox[2])) / 2.0) / float(page_width))


def zone_from_x(x) -> str:
    try:
        value = float(x)
    except Exception:
        return 'left'
    if value < 0.38:
        return 'left'
    if value > 0.62:
        return 'right'
    return 'center'


def source_page_body_texts(layout: dict) -> list:
    values = []
    for page in layout.get('pages', []) or []:
        texts = [
            clean_visible_text(block.get('text', ''))
            for block in page.get('text_blocks', []) or []
            if block.get('region') == REGION_BODY and
            clean_visible_text(block.get('text', '')) and
            not clean_visible_text(block.get('text', '')).startswith('<')
        ]
        values.append(' '.join(texts))
    return values


def clean_visible_text(text: str) -> str:
    return normalize_text(str(text or '').replace('\xa0', ' '))


def normalize_text(text: str) -> str:
    return ' '.join(str(text or '').split())


def is_contiguous(values: list) -> bool:
    values = sorted(values)
    return all(values[index] + 1 == values[index + 1] for index in range(len(values) - 1))


def ratio(count, total) -> float:
    return round(float(count) / float(total), 4) if total else 0.0


def median(values: list):
    values = sorted(value for value in values if value is not None)
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return round(values[middle], 5)
    return round((values[middle - 1] + values[middle]) / 2.0, 5)


def common_prefix(values: list) -> str:
    if not values:
        return ''
    prefix = values[0]
    for value in values[1:]:
        while prefix and not value.startswith(prefix):
            prefix = prefix[:-1]
    return prefix


def common_suffix(values: list) -> str:
    if not values:
        return ''
    return common_prefix([value[::-1] for value in values])[::-1]


def variable_token_type(tokens: list) -> str:
    stripped = [str(token).strip() for token in tokens]
    if all(re.fullmatch(r'\d+', token) for token in stripped):
        return 'arabic'
    if all(re.fullmatch(r'[ivxlcdm]+', token, flags=re.I) for token in stripped):
        return 'roman'
    if all(re.fullmatch(r'\d+[-–—]\d+', token) for token in stripped):
        return 'chapter_page'
    return 'unknown'


def numeric_sequence(tokens: list) -> list:
    values = []
    for token in tokens or []:
        value = str(token).strip()
        if not re.fullmatch(r'\d+', value):
            return []
        values.append(int(value))
    return values


def numeric_step(tokens: list):
    values = numeric_sequence(tokens)
    if len(values) < 2:
        return None
    diffs = [b - a for a, b in zip(values, values[1:])]
    return diffs[0] if diffs and len(set(diffs)) == 1 else None


def observation_sort_key(item: dict):
    bbox = item.get('bbox', [0, 0, 0, 0]) or [0, 0, 0, 0]
    return (
        item.get('source_page_index', -1),
        item.get('target_part', ''),
        bbox[1] if len(bbox) > 1 else 0,
        bbox[0] if bbox else 0,
    )
