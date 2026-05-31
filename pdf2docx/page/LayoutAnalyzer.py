# -*- coding: utf-8 -*-

'''Small pure helpers for document-level layout analysis.

This module intentionally does not integrate with the converter pipeline yet.
It works with simplified page dictionaries so tests and debug tools can build
header/footer analysis incrementally without changing conversion output.
'''

import re
from collections import Counter, defaultdict


PAGE_NUMBER_PLACEHOLDER = '<PAGE_NUMBER>'
IMAGE_PLACEHOLDER = '<IMAGE>'
REGION_TOP = 'top'
REGION_BODY = 'body'
REGION_BOTTOM = 'bottom'
ACTION_WOULD_EXCLUDE = 'would_exclude'
ACTION_REVIEW = 'review'
ACTION_KEEP = 'keep'
ROLE_HEADER = 'header'
ROLE_FOOTER = 'footer'
ROLE_PAGE_NUMBER = 'page_number'
ROLE_LAYOUT_PLACEHOLDER = 'layout_placeholder'
ROLE_REVIEW_ONLY = 'review_only'
ROLE_KEEP_BODY = 'keep_body'
DECISION_APPROVE_EXCLUDE = 'approve_exclude'
DECISION_REJECT_EXCLUDE = 'reject_exclude'
DECISION_UNSURE = 'unsure'
DECISION_NONE = 'none'
DECISION_CONFLICT = 'conflict'
DEFAULT_TOP_RATIO = 0.15
DEFAULT_BOTTOM_RATIO = 0.15
DEFAULT_NEAR_BODY_EDGE_RATIO = 0.12
MIN_MEANINGFUL_TEXT_LENGTH = 12
MIN_MEANINGFUL_WORDS = 2
STRONG_SENTENCE_END_PUNC = '.．。?？!！'

_SPACE_RE = re.compile(r'\s+')
_PLACEHOLDER_RE = re.compile(r'^<[^<>]+>$')
_REVIEW_SECTION_RE = re.compile(
    r'^###\s+([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*$')
_REVIEW_FIELD_RE = re.compile(r'^-\s+([a-zA-Z_]+):\s*(.*)$')
_REVIEW_DECISION_RE = re.compile(
    r'(approve_exclude|reject_exclude|unsure):\s*\[([^\]]*)\]')
_PAGE_NUMBER_RE_LIST = (
    re.compile(r'^(?:page|p\.?)\s*\d+$', re.IGNORECASE),
    re.compile(r'^(?:page|p\.?)\s*\d+\s*(?:/|of)\s*\d+$', re.IGNORECASE),
    re.compile(r'^\d+\s*(?:/|of)\s*\d+$', re.IGNORECASE),
    re.compile(r'^-?\s*\d+\s*-?$'),
)
_NUMBERED_HEADING_RE = re.compile(r'^\d+(?:\.\d+)*\.?\s+\S+')
_SECTION_HEADING_RE = re.compile(
    r'^(?:chapter|section|part|appendix|article)\b',
    re.IGNORECASE)
_LIST_MARKER_RE = re.compile(
    r'^\s*(?:[-*+]|(?:\d+|[A-Za-z])[.)])\s+\S+')


def normalize_text(text) -> str:
    '''Normalize text for layout-level comparison.'''
    if text is None:
        return ''
    return _SPACE_RE.sub(' ', str(text)).strip()


def normalize_page_number(text, placeholder: str = PAGE_NUMBER_PLACEHOLDER) -> str:
    '''Replace simple standalone page-number strings with a stable placeholder.'''
    normalized = normalize_text(text)
    if not normalized:
        return ''

    for pattern in _PAGE_NUMBER_RE_LIST:
        if pattern.match(normalized):
            return placeholder

    return normalized


def normalize_style_key(style=None) -> str:
    '''Create a compact style key from a simplified style dictionary.'''
    if not style:
        return ''

    font = normalize_text(style.get('font') or style.get('font_family')).lower()
    size = style.get('size', style.get('font_size', ''))
    if isinstance(size, float):
        size = round(size, 2)
    elif isinstance(size, int):
        size = int(size)
    else:
        size = normalize_text(size)

    flags = normalize_text(style.get('flags', '')).lower()
    return '|'.join(str(item) for item in (font, size, flags) if item != '')


def make_text_fingerprint(
        text,
        y_band: str = '',
        style=None,
        normalize_page_numbers: bool = True) -> dict:
    '''Create a JSON-serializable fingerprint for repeated text analysis.'''
    normalized = normalize_text(text).lower()
    if normalize_page_numbers:
        normalized = normalize_page_number(normalized).lower()

    style_key = normalize_style_key(style)
    band_key = normalize_text(y_band).lower()
    parts = [normalized]
    if band_key:
        parts.append(band_key)
    if style_key:
        parts.append(style_key)

    return {
        'text': normalized,
        'y_band': band_key,
        'style': style_key,
        'key': '||'.join(parts),
    }


def text_quality_signals(text) -> dict:
    '''Return conservative semantic-quality signals for report scoring.'''
    normalized = normalize_text(text)
    comparable = _comparison_text(normalized)
    placeholder_kind = _placeholder_kind(comparable)
    words = comparable.split()
    alnum_count = sum(1 for char in comparable if char.isalnum())
    short_text = alnum_count < MIN_MEANINGFUL_TEXT_LENGTH and len(words) < MIN_MEANINGFUL_WORDS
    placeholder_like = bool(placeholder_kind)
    meaningful_text = bool(comparable) and not placeholder_like and not short_text

    if placeholder_kind == 'page_number':
        semantic_weight = 0.85
    elif placeholder_like:
        semantic_weight = 0.35
    elif short_text:
        semantic_weight = 0.55
    else:
        semantic_weight = 1.0

    return {
        'normalized_text': comparable,
        'character_count': len(normalized),
        'alnum_count': alnum_count,
        'word_count': len(words),
        'placeholder_like': placeholder_like,
        'placeholder_kind': placeholder_kind,
        'short_text': short_text,
        'meaningful_text': meaningful_text,
        'semantic_weight': semantic_weight,
    }


def classify_y_band(
        bbox,
        page_height: float,
        top_ratio: float = DEFAULT_TOP_RATIO,
        bottom_ratio: float = DEFAULT_BOTTOM_RATIO) -> str:
    '''Classify a bbox into top/body/bottom page bands.'''
    if page_height <= 0:
        raise ValueError('page_height must be positive.')
    if top_ratio < 0 or bottom_ratio < 0 or top_ratio + bottom_ratio >= 1:
        raise ValueError('top_ratio and bottom_ratio must be non-negative and sum to less than 1.')
    if not bbox or len(bbox) < 4:
        return REGION_BODY

    y0, y1 = float(bbox[1]), float(bbox[3])
    center_y = (y0 + y1) / 2.0
    if center_y < page_height * top_ratio:
        return REGION_TOP
    if center_y > page_height * (1.0 - bottom_ratio):
        return REGION_BOTTOM
    return REGION_BODY


def text_block_records(
        pages: list,
        top_ratio: float = DEFAULT_TOP_RATIO,
        bottom_ratio: float = DEFAULT_BOTTOM_RATIO) -> list:
    '''Convert simplified page dictionaries into JSON-serializable block records.'''
    records = []
    for fallback_page_index, page in enumerate(pages or []):
        page_index = page.get('page_index', page.get('id', fallback_page_index))
        page_height = page.get('height', page.get('page_height', 0))
        blocks = page.get('blocks', page.get('text_blocks', [])) or []

        for block_index, block in enumerate(blocks):
            text = normalize_text(block.get('text', ''))
            if not text:
                continue

            bbox = _json_bbox(block.get('bbox'))
            region = classify_y_band(bbox, page_height, top_ratio, bottom_ratio)
            style = block.get('style') or _style_from_block(block)
            fingerprint = make_text_fingerprint(text, region, style=None)
            quality = text_quality_signals(text)

            records.append({
                'page_index': page_index,
                'block_index': block_index,
                'text': text,
                'normalized_text': fingerprint['text'],
                'bbox': bbox,
                'region': region,
                'style': normalize_style_key(style),
                'fingerprint': fingerprint['key'],
                'signals': quality,
            })

    return records


def find_repeated_text_candidates(
        pages: list,
        min_pages: int = 2,
        top_ratio: float = DEFAULT_TOP_RATIO,
        bottom_ratio: float = DEFAULT_BOTTOM_RATIO,
        regions: tuple = (REGION_TOP, REGION_BOTTOM)) -> list:
    '''Find repeated text candidates across simplified page dictionaries.'''
    total_pages = len(pages or [])
    records = text_block_records(pages, top_ratio, bottom_ratio)
    allowed_regions = set(regions or [])
    grouped = defaultdict(list)

    for record in records:
        if allowed_regions and record['region'] not in allowed_regions:
            continue
        if not record['normalized_text']:
            continue
        grouped[record['fingerprint']].append(record)

    candidates = []
    for key, group in grouped.items():
        pages_seen = sorted({record['page_index'] for record in group})
        if len(pages_seen) < min_pages:
            continue

        regions_seen = sorted({record['region'] for record in group})
        support = len(pages_seen)
        confidence = round(support / total_pages, 3) if total_pages else 0.0
        support_level = _support_level(support, total_pages)
        adjacent_only = _is_adjacent_only(pages_seen, total_pages)
        quality = text_quality_signals(group[0]['normalized_text'])
        semantic_confidence = _semantic_confidence(
            confidence,
            support,
            total_pages,
            quality)
        confidence_label = _confidence_label(
            semantic_confidence,
            support_level,
            adjacent_only,
            quality)
        candidates.append({
            'fingerprint': key,
            'text': group[0]['normalized_text'],
            'pages': pages_seen,
            'count': len(group),
            'regions': regions_seen,
            'confidence': confidence,
            'semantic_confidence': semantic_confidence,
            'confidence_label': confidence_label,
            'reason': _repeated_candidate_reason(
                semantic_confidence,
                support_level,
                adjacent_only,
                quality),
            'signals': {
                'support_pages': support,
                'total_pages': total_pages,
                'support_ratio': confidence,
                'support_level': support_level,
                'adjacent_only': adjacent_only,
                'instance_count': len(group),
                'regions': regions_seen,
                'text_quality': quality,
            },
            'instances': group,
        })

    candidates.sort(key=lambda item: (-len(item['pages']), item['fingerprint']))
    return candidates


def build_header_footer_exclusion_dry_run(
        repeated_text_candidates: list,
        page_count: int = None) -> dict:
    '''Simulate future header/footer exclusion without mutating content.'''
    candidates = []
    for index, candidate in enumerate(repeated_text_candidates or []):
        candidates.append(_dry_run_candidate(candidate, index, page_count))

    action_counts = defaultdict(int)
    role_counts = defaultdict(int)
    region_counts = defaultdict(int)
    affected_pages = set()
    for candidate in candidates:
        action_counts[candidate['action']] += 1
        role_counts[candidate['proposed_role']] += 1
        for region in candidate['regions']:
            region_counts[region] += 1
        affected_pages.update(candidate['affected_pages'])

    return {
        'policy': 'non_destructive_report_only',
        'summary': {
            'candidate_count': len(candidates),
            'action_counts': dict(sorted(action_counts.items())),
            'role_counts': dict(sorted(role_counts.items())),
            'region_counts': dict(sorted(region_counts.items())),
            'affected_pages': sorted(affected_pages),
        },
        'candidates': candidates,
    }


def load_exclusion_review_decisions(path: str) -> dict:
    '''Read a local review markdown file and parse manual decisions.'''
    with open(path, 'r', encoding='utf-8') as stream:
        return parse_exclusion_review_markdown(stream.read())


def parse_exclusion_review_markdown(markdown_text: str) -> dict:
    '''Parse Phase 1G local review markdown into structured decisions.'''
    decisions = []
    current = None

    def flush_current():
        if not current:
            return
        if current.get('candidate_id') or current.get('fingerprint'):
            current.setdefault('manual_decision', DECISION_NONE)
            current.setdefault('checked_decisions', [])
            decisions.append(current.copy())

    for raw_line in (markdown_text or '').splitlines():
        line = raw_line.strip()
        section = _REVIEW_SECTION_RE.match(line)
        if section:
            flush_current()
            current = {
                'candidate_id': normalize_text(section.group(1)),
                'proposed_role': normalize_text(section.group(2)),
                'action': normalize_text(section.group(3)),
            }
            continue

        if current is None:
            continue

        field = _REVIEW_FIELD_RE.match(line)
        if not field:
            continue

        field_name = field.group(1)
        field_value = field.group(2)
        if field_name == 'fingerprint':
            current['fingerprint'] = _strip_inline_code(field_value)
        elif field_name == 'review_recommendation':
            current['review_recommendation'] = _strip_inline_code(field_value)
        elif field_name == 'human_decision':
            decision, checked = _parse_human_decision(field_value)
            current['manual_decision'] = decision
            current['checked_decisions'] = checked

    flush_current()

    decision_counts = defaultdict(int)
    for decision in decisions:
        decision_counts[decision.get('manual_decision', DECISION_NONE)] += 1

    return {
        'decisions': decisions,
        'summary': {
            'candidate_count': len(decisions),
            'decision_counts': dict(sorted(decision_counts.items())),
        },
    }


def build_reviewed_header_footer_filter_report(
        page_summaries: list,
        dry_run_report: dict,
        review_decisions,
        enabled: bool = False,
        apply: bool = False) -> dict:
    '''Build an opt-in reviewed header/footer filtering report.

    The default disabled mode never filters. When enabled, only candidates with
    explicit approve_exclude review decisions and safe dry-run roles are eligible.
    '''
    dry_run_candidates = _dry_run_candidates(dry_run_report)
    decision_map = _review_decision_map(review_decisions)
    approved, blocked = _reviewed_exclusion_candidates(dry_run_candidates, decision_map)
    approved_by_fingerprint = {item['fingerprint']: item for item in approved}
    should_apply = bool(enabled and apply)

    pages_report = []
    filtered_pages = []
    original_block_count = 0
    would_remove_block_count = 0
    removed_block_count = 0
    kept_block_count = 0

    for page in page_summaries or []:
        page_index = page.get('page_index')
        blocks = page.get('text_blocks', []) or []
        kept_blocks = []
        removed_blocks = []

        for block in blocks:
            original_block_count += 1
            candidate = approved_by_fingerprint.get(block.get('fingerprint'))
            if candidate and _block_matches_reviewed_candidate(block, page_index, candidate):
                removed_blocks.append(_removed_block_summary(block, candidate))
                continue
            kept_blocks.append(dict(block))

        would_remove_block_count += len(removed_blocks)
        if should_apply:
            removed_block_count += len(removed_blocks)
            kept_block_count += len(kept_blocks)
            filtered_pages.append(_filtered_page_summary(page, kept_blocks))
        else:
            kept_block_count += len(blocks)

        pages_report.append({
            'page_index': page_index,
            'original_block_count': len(blocks),
            'would_remove_block_count': len(removed_blocks),
            'removed_block_count': len(removed_blocks) if should_apply else 0,
            'kept_block_count': len(kept_blocks) if should_apply else len(blocks),
            'removed_blocks': removed_blocks if enabled else [],
        })

    return {
        'enabled': bool(enabled),
        'applied': should_apply,
        'policy': 'review_decision_based',
        'approved_candidate_count': len(approved),
        'blocked_candidate_count': len(blocked),
        'approved_fingerprints': sorted(approved_by_fingerprint),
        'blocked_candidates': blocked,
        'summary': {
            'original_block_count': original_block_count,
            'would_remove_block_count': would_remove_block_count if enabled else 0,
            'removed_block_count': removed_block_count,
            'kept_block_count': kept_block_count,
        },
        'pages': pages_report,
        'filtered_pages': filtered_pages if should_apply else [],
    }


def build_body_filtering_diff_report(
        page_summaries: list,
        dry_run_report: dict,
        review_decisions,
        enabled: bool = False,
        filtering_report: dict = None) -> dict:
    '''Build a local-review diff report for reviewed header/footer filtering.'''
    review_decisions = review_decisions or {}
    if filtering_report is None:
        filtering_report = build_reviewed_header_footer_filter_report(
            page_summaries,
            dry_run_report,
            review_decisions,
            enabled=enabled,
            apply=False)

    removed_keys, removed_by_key = _removed_block_lookup(filtering_report)
    decision_counts = _decision_counts(review_decisions)
    approved_fingerprints = set(filtering_report.get('approved_fingerprints', []))
    blocked_candidates = filtering_report.get('blocked_candidates', []) or []
    blocked_by_fingerprint = {
        item.get('fingerprint'): item
        for item in blocked_candidates
        if item.get('fingerprint')
    }

    removed_by_page = []
    kept_by_page = []
    removed_by_candidate = defaultdict(lambda: {
        'candidate_id': '',
        'fingerprint': '',
        'proposed_role': '',
        'manual_decision': '',
        'removed_count': 0,
        'blocks': [],
    })
    safety = _new_safety_summary()
    original_block_count = 0
    would_remove_block_count = 0
    kept_block_count = 0

    for page in page_summaries or []:
        page_index = page.get('page_index')
        page_removed = []
        page_kept = []

        for block in page.get('text_blocks', []) or []:
            original_block_count += 1
            key = (page_index, block.get('block_index'))
            removed = removed_by_key.get(key)
            if enabled and key in removed_keys:
                summary = _diff_removed_block_summary(page_index, block, removed)
                page_removed.append(summary)
                _append_candidate_removed_block(removed_by_candidate, summary)
                _record_safety_for_removed_block(
                    safety,
                    summary,
                    approved_fingerprints,
                    blocked_by_fingerprint)
                continue
            page_kept.append(_kept_block_summary(page_index, block))

        would_remove_block_count += len(page_removed)
        kept_block_count += len(page_kept)
        removed_by_page.append({
            'page_index': page_index,
            'page_number': _human_page_number(page_index),
            'removed_count': len(page_removed),
            'blocks': page_removed,
        })
        kept_by_page.append({
            'page_index': page_index,
            'page_number': _human_page_number(page_index),
            'kept_count': len(page_kept),
            'blocks': page_kept,
        })

    removed_by_candidate_list = sorted(
        removed_by_candidate.values(),
        key=lambda item: (item['candidate_id'], item['fingerprint']))
    _finalize_safety_warnings(safety)

    blocked_decision_counts = defaultdict(int)
    for item in blocked_candidates:
        blocked_decision_counts[item.get('manual_decision', DECISION_NONE)] += 1

    return {
        'enabled': bool(enabled),
        'policy': 'reviewed_filtering_diff_only',
        'summary': {
            'original_block_count': original_block_count,
            'would_remove_block_count': would_remove_block_count if enabled else 0,
            'kept_block_count': kept_block_count,
            'approved_candidate_count': filtering_report.get('approved_candidate_count', 0),
            'blocked_candidate_count': filtering_report.get('blocked_candidate_count', 0),
            'retained_candidate_count': len(blocked_candidates),
            'decision_counts': decision_counts,
            'blocked_decision_counts': dict(sorted(blocked_decision_counts.items())),
        },
        'removed_blocks_by_page': removed_by_page,
        'kept_blocks_by_page': kept_by_page,
        'removed_blocks_by_candidate': removed_by_candidate_list,
        'retained_candidates': blocked_candidates,
        'safety': safety,
    }


def build_paragraph_integrity_report(
        page_summaries: list,
        body_filtering_diff_report: dict = None,
        enabled: bool = False,
        high_body_loss_ratio: float = 0.2) -> dict:
    '''Validate paragraph-oriented body integrity after reviewed filtering.'''
    diff_report = body_filtering_diff_report or {}
    removed_lookup = _diff_report_removed_lookup(diff_report) if enabled else {}
    filtered_pages = []
    pages_report = []
    body_loss_warnings = []
    paragraph_gap_warnings = []
    original_block_count = 0
    filtered_block_count = 0
    removed_block_count = 0
    body_region_kept_count = 0
    body_region_removed_count = 0
    top_removed_count = 0
    bottom_removed_count = 0

    for page in page_summaries or []:
        page_index = page.get('page_index')
        blocks = page.get('text_blocks', []) or []
        original_block_count += len(blocks)
        kept_blocks = []
        removed_blocks = []

        for block in blocks:
            key = (page_index, block.get('block_index'))
            if key in removed_lookup:
                summary = _integrity_removed_block_summary(
                    page_index,
                    block,
                    removed_lookup[key])
                removed_blocks.append(summary)
                removed_block_count += 1

                if block.get('region') == REGION_BODY:
                    body_region_removed_count += 1
                elif block.get('region') == REGION_TOP:
                    top_removed_count += 1
                elif block.get('region') == REGION_BOTTOM:
                    bottom_removed_count += 1
                continue

            kept_blocks.append(dict(block))
            if block.get('region') == REGION_BODY:
                body_region_kept_count += 1

        filtered_block_count += len(kept_blocks)
        filtered_page = _filtered_page_summary(page, kept_blocks)
        filtered_pages.append(filtered_page)

        page_report = _paragraph_integrity_page_report(
            page,
            kept_blocks,
            removed_blocks,
            high_body_loss_ratio)
        pages_report.append(page_report)
        body_loss_warnings.extend(page_report['body_loss_warnings'])
        paragraph_gap_warnings.extend(page_report['paragraph_gap_warnings'])

    continuation_candidates = find_paragraph_continuation_candidates(filtered_pages)
    diff_safety_warnings = (diff_report.get('safety') or {}).get('warnings', [])
    warning_count = (
        len(body_loss_warnings) +
        len(paragraph_gap_warnings) +
        len(diff_safety_warnings))
    safe = warning_count == 0 and body_region_removed_count == 0

    return {
        'enabled': bool(enabled),
        'policy': 'paragraph_integrity_report_only',
        'summary': {
            'original_block_count': original_block_count,
            'filtered_block_count': filtered_block_count if enabled else original_block_count,
            'removed_block_count': removed_block_count if enabled else 0,
            'body_region_kept_count': body_region_kept_count,
            'body_region_removed_count': body_region_removed_count if enabled else 0,
            'top_removed_count': top_removed_count if enabled else 0,
            'bottom_removed_count': bottom_removed_count if enabled else 0,
            'top_bottom_removed_count': (top_removed_count + bottom_removed_count) if enabled else 0,
            'line_level_body_blocks_available': body_region_kept_count > 0,
            'suspicious_warning_count': warning_count if enabled else 0,
        },
        'pages': pages_report,
        'filtered_pages': filtered_pages if enabled else _copy_page_summaries(page_summaries),
        'suspicious_body_loss_warnings': body_loss_warnings if enabled else [],
        'suspicious_paragraph_gap_warnings': paragraph_gap_warnings if enabled else [],
        'diff_safety_warnings': diff_safety_warnings if enabled else [],
        'possible_cross_page_continuation_candidates': continuation_candidates if enabled else [],
        'recommendation': {
            'safe_to_attempt_phase_2d': bool(enabled and safe),
            'reason': _paragraph_integrity_recommendation(enabled, safe, warning_count),
        },
    }


def build_paragraph_reconstruction_validation_report(
        page_summaries: list,
        paragraph_integrity_report: dict = None,
        body_filtering_diff_report: dict = None,
        enabled: bool = False,
        max_line_gap_ratio: float = 1.6,
        paragraph_gap_ratio: float = 2.4,
        indent_tolerance: float = 16.0,
        single_line_fragment_ratio: float = 0.75,
        short_fragment_length: int = 45,
        low_average_blocks_per_group: float = 1.5) -> dict:
    '''Estimate paragraph grouping quality from filtered page summaries.'''
    original_pages = _copy_page_summaries(page_summaries)
    filtered_pages = _reconstruction_filtered_pages(
        page_summaries,
        paragraph_integrity_report,
        body_filtering_diff_report,
        enabled)

    body_before_count = sum(
        len(_body_blocks(page))
        for page in original_pages)
    body_after_count = sum(
        len(_body_blocks(page))
        for page in filtered_pages)

    if not enabled:
        return {
            'enabled': False,
            'policy': 'paragraph_reconstruction_validation_report_only',
            'summary': {
                'body_block_count_before_filtering': body_before_count,
                'body_block_count_after_filtering': body_before_count,
                'estimated_paragraph_group_count': 0,
                'average_blocks_per_estimated_paragraph': 0.0,
                'suspicious_single_line_paragraph_count': 0,
                'suspicious_short_fragment_count': 0,
                'possible_cross_page_continuation_count': 0,
                'cross_page_continuation_warning_count': 0,
                'warning_count': 0,
                'line_level_body_blocks_available': body_before_count > 0,
            },
            'pages': [],
            'filtered_pages': original_pages,
            'possible_cross_page_continuation_candidates': [],
            'diagnostics': _empty_paragraph_grouping_diagnostics(),
            'warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2e': False,
                'reason': 'Paragraph reconstruction validation is disabled; no grouping assumptions were evaluated.',
            },
        }

    original_by_page = {
        page.get('page_index'): page
        for page in original_pages
    }
    pages_report = []
    warnings = []
    estimated_group_count = 0
    suspicious_single_line_count = 0
    suspicious_short_fragment_count = 0

    for page in filtered_pages:
        original_page = original_by_page.get(page.get('page_index'), page)
        page_report = _paragraph_reconstruction_page_report(
            original_page,
            page,
            max_line_gap_ratio,
            paragraph_gap_ratio,
            indent_tolerance,
            single_line_fragment_ratio,
            short_fragment_length)
        pages_report.append(page_report)
        warnings.extend(page_report['warnings'])
        estimated_group_count += page_report['estimated_paragraph_group_count']
        suspicious_single_line_count += page_report['suspicious_single_line_paragraph_count']
        suspicious_short_fragment_count += page_report['suspicious_short_fragment_count']

    continuation_candidates = find_paragraph_continuation_candidates(filtered_pages)
    possible_continuations = [
        candidate for candidate in continuation_candidates
        if candidate.get('label') in {'candidate', 'weak'}
    ]
    continuation_warnings = [
        _cross_page_continuation_warning(candidate)
        for candidate in possible_continuations
    ]
    warnings.extend(continuation_warnings)

    average_blocks_per_group = _safe_ratio(
        body_after_count,
        estimated_group_count)
    if (estimated_group_count >= 10 and
            0.0 < average_blocks_per_group < low_average_blocks_per_group):
        warnings.append({
            'type': 'low_average_blocks_per_estimated_paragraph',
            'message': 'Estimated paragraph groups average very few body blocks; paragraph reconstruction may remain fragmented.',
            'estimated_paragraph_group_count': estimated_group_count,
            'body_block_count_after_filtering': body_after_count,
            'average_blocks_per_estimated_paragraph': average_blocks_per_group,
        })

    diagnostics = _paragraph_grouping_diagnostics(
        pages_report,
        warnings,
        possible_continuations)

    warning_count = len(warnings)
    safe = warning_count == 0 and body_after_count > 0
    return {
        'enabled': True,
        'policy': 'paragraph_reconstruction_validation_report_only',
        'summary': {
            'body_block_count_before_filtering': body_before_count,
            'body_block_count_after_filtering': body_after_count,
            'estimated_paragraph_group_count': estimated_group_count,
            'average_blocks_per_estimated_paragraph': average_blocks_per_group,
            'suspicious_single_line_paragraph_count': suspicious_single_line_count,
            'suspicious_short_fragment_count': suspicious_short_fragment_count,
            'possible_cross_page_continuation_count': len(possible_continuations),
            'cross_page_continuation_warning_count': len(continuation_warnings),
            'warning_count': warning_count,
            'line_level_body_blocks_available': body_after_count > 0,
            'groups_by_line_count': diagnostics['groups_by_line_count'],
            'groups_by_block_count': diagnostics['groups_by_block_count'],
            'one_line_group_ratio': diagnostics['one_line_group_ratio'],
            'short_fragment_ratio': diagnostics['short_fragment_ratio'],
        },
        'pages': pages_report,
        'filtered_pages': filtered_pages,
        'possible_cross_page_continuation_candidates': possible_continuations,
        'diagnostics': diagnostics,
        'warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2e': bool(safe),
            'reason': _paragraph_reconstruction_recommendation(safe, warning_count),
        },
    }


def build_paragraph_production_comparison_report(
        estimator_report: dict = None,
        production_pages: list = None,
        enabled: bool = False,
        top_ratio: float = DEFAULT_TOP_RATIO,
        bottom_ratio: float = DEFAULT_BOTTOM_RATIO,
        short_fragment_length: int = 45) -> dict:
    '''Compare report-only paragraph estimates with observed production TextBlocks.'''
    estimator_metrics = _estimator_grouping_metrics(estimator_report)
    if not enabled:
        return {
            'enabled': False,
            'policy': 'paragraph_production_comparison_report_only',
            'estimator': estimator_metrics,
            'production_observed': {
                'available': False,
                'reason': 'Production grouping comparison is disabled.',
            },
            'mismatch': {
                'available': False,
                'reason': 'Comparison is disabled.',
            },
            'warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2g': False,
                'reason': 'Production comparison is disabled; no integration assumptions were evaluated.',
            },
        }

    warnings = []
    if not production_pages:
        warnings.append({
            'type': 'production_metrics_unavailable',
            'message': 'No serialized production pages were provided for comparison.',
        })
        return {
            'enabled': True,
            'policy': 'paragraph_production_comparison_report_only',
            'estimator': estimator_metrics,
            'production_observed': {
                'available': False,
                'reason': 'No serialized production pages were provided.',
            },
            'mismatch': {
                'available': False,
                'reason': 'Production-observed metrics are unavailable.',
            },
            'warnings': warnings,
            'recommendation': {
                'safe_to_attempt_phase_2g': False,
                'reason': 'Collect production-observed TextBlock metrics before any integration attempt.',
            },
        }

    production_metrics = _production_observed_grouping_metrics(
        production_pages,
        top_ratio,
        bottom_ratio,
        short_fragment_length)
    mismatch = _paragraph_grouping_mismatch(estimator_metrics, production_metrics)
    if mismatch.get('group_count_delta_ratio', 0.0) > 0.5:
        warnings.append({
            'type': 'high_group_count_mismatch',
            'message': 'Estimator and production-observed paragraph counts differ substantially.',
            'group_count_delta_ratio': mismatch.get('group_count_delta_ratio', 0.0),
        })

    warning_count = len(warnings)
    return {
        'enabled': True,
        'policy': 'paragraph_production_comparison_report_only',
        'estimator': estimator_metrics,
        'production_observed': production_metrics,
        'mismatch': mismatch,
        'warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2g': warning_count == 0,
            'reason': _production_comparison_recommendation(warning_count, mismatch),
        },
    }


def build_paragraph_mismatch_analysis_report(
        estimator_report: dict = None,
        production_comparison_report: dict = None,
        production_pages: list = None,
        enabled: bool = False,
        top_ratio: float = DEFAULT_TOP_RATIO,
        bottom_ratio: float = DEFAULT_BOTTOM_RATIO,
        short_fragment_length: int = 45,
        page_limit: int = 8) -> dict:
    '''Explain estimator-vs-production paragraph grouping mismatches.'''
    estimator_metrics = _estimator_grouping_metrics(estimator_report)
    if not enabled:
        return {
            'enabled': False,
            'policy': 'paragraph_mismatch_analysis_report_only',
            'estimator': estimator_metrics,
            'production_observed': {
                'available': False,
                'reason': 'Mismatch analysis is disabled.',
            },
            'summary': {
                'available': False,
                'reason': 'Mismatch analysis is disabled.',
            },
            'pages': [],
            'warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2h': False,
                'reason': 'Mismatch analysis is disabled; no integration assumptions were evaluated.',
            },
        }

    comparison = production_comparison_report or {}
    if not comparison.get('enabled') and production_pages:
        comparison = build_paragraph_production_comparison_report(
            estimator_report,
            production_pages=production_pages,
            enabled=True,
            top_ratio=top_ratio,
            bottom_ratio=bottom_ratio,
            short_fragment_length=short_fragment_length)

    production_metrics = comparison.get('production_observed') or {}
    warnings = []
    if not production_metrics.get('available'):
        warnings.append({
            'type': 'production_metrics_unavailable',
            'message': 'Production-observed grouping metrics are unavailable for mismatch analysis.',
        })
        return {
            'enabled': True,
            'policy': 'paragraph_mismatch_analysis_report_only',
            'estimator': estimator_metrics,
            'production_observed': production_metrics or {
                'available': False,
                'reason': 'Production-observed metrics are unavailable.',
            },
            'summary': {
                'available': False,
                'reason': 'Production-observed metrics are unavailable.',
            },
            'pages': [],
            'warnings': warnings,
            'recommendation': {
                'safe_to_attempt_phase_2h': False,
                'reason': 'Collect production-observed TextBlock metrics before further diagnostics.',
            },
        }

    page_analyses = _paragraph_mismatch_page_analyses(
        estimator_report,
        production_metrics)
    cause_counts = Counter(
        page['likely_cause']
        for page in page_analyses
        if page.get('likely_cause'))
    dominant_cause = cause_counts.most_common(1)[0][0] if cause_counts else 'insufficient_data'
    mismatch = comparison.get('mismatch') or _paragraph_grouping_mismatch(
        estimator_metrics,
        production_metrics)

    if mismatch.get('group_count_delta_ratio', 0.0) > 0.5:
        warnings.append({
            'type': 'high_group_count_mismatch',
            'message': 'Estimator and production-observed paragraph counts differ substantially.',
            'group_count_delta_ratio': mismatch.get('group_count_delta_ratio', 0.0),
        })

    return {
        'enabled': True,
        'policy': 'paragraph_mismatch_analysis_report_only',
        'estimator': estimator_metrics,
        'production_observed': production_metrics,
        'summary': {
            'available': True,
            'estimator_group_count': mismatch.get('estimator_group_count', 0),
            'production_group_count': mismatch.get('production_group_count', 0),
            'absolute_group_count_delta': mismatch.get('absolute_group_count_delta', 0),
            'signed_group_count_delta': mismatch.get('signed_group_count_delta', 0),
            'group_count_delta_ratio': mismatch.get('group_count_delta_ratio', 0.0),
            'dominant_mismatch_cause': dominant_cause,
            'cause_counts': dict(sorted(cause_counts.items())),
            'mostly_estimator_over_splitting': mismatch.get('signed_group_count_delta', 0) > 0,
            'mostly_production_over_merging': (
                mismatch.get('signed_group_count_delta', 0) > 0 and
                dominant_cause == 'production_possible_over_merge'),
        },
        'pages': page_analyses[:page_limit],
        'warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2h': False,
            'reason': _mismatch_analysis_recommendation(dominant_cause, warnings),
        },
    }


def build_layout_analysis_report(
        pages: list,
        min_pages: int = 2,
        top_ratio: float = DEFAULT_TOP_RATIO,
        bottom_ratio: float = DEFAULT_BOTTOM_RATIO) -> dict:
    '''Build a JSON-serializable document layout analysis report.'''
    pages = pages or []
    records = text_block_records(pages, top_ratio, bottom_ratio)
    records_by_page = defaultdict(list)
    for record in records:
        records_by_page[record['page_index']].append(record)

    page_summaries = []
    for fallback_page_index, page in enumerate(pages):
        page_index = page.get('page_index', page.get('id', fallback_page_index))
        page_records = records_by_page.get(page_index, [])
        region_counts = {
            REGION_TOP: 0,
            REGION_BODY: 0,
            REGION_BOTTOM: 0,
        }
        for record in page_records:
            region_counts[record['region']] += 1

        page_summaries.append({
            'page_index': page_index,
            'width': _json_number(page.get('width', page.get('page_width', 0.0))),
            'height': _json_number(page.get('height', page.get('page_height', 0.0))),
            'text': normalize_text(' '.join(record['text'] for record in page_records)),
            'text_block_count': len(page_records),
            'region_counts': region_counts,
            'text_blocks': page_records,
        })

    repeated = find_repeated_text_candidates(
        pages,
        min_pages=min_pages,
        top_ratio=top_ratio,
        bottom_ratio=bottom_ratio)
    dry_run = build_header_footer_exclusion_dry_run(
        repeated,
        page_count=len(pages))
    continuations = find_paragraph_continuation_candidates(
        page_summaries,
        repeated_text_candidates=repeated,
        top_ratio=top_ratio,
        bottom_ratio=bottom_ratio)

    return {
        'page_count': len(pages),
        'settings': {
            'min_pages': min_pages,
            'top_ratio': top_ratio,
            'bottom_ratio': bottom_ratio,
        },
        'pages': page_summaries,
        'repeated_text_candidates': repeated,
        'header_footer_exclusion_dry_run': dry_run,
        'paragraph_continuation_candidates': continuations,
        'signals': {
            'text_block_count': len(records),
            'repeated_text_candidate_count': len(repeated),
            'header_footer_exclusion_dry_run_candidate_count': len(dry_run['candidates']),
            'paragraph_continuation_candidate_count': len(continuations),
        },
    }


def find_paragraph_continuation_candidates(
        page_summaries: list,
        repeated_text_candidates: list = None,
        top_ratio: float = DEFAULT_TOP_RATIO,
        bottom_ratio: float = DEFAULT_BOTTOM_RATIO,
        near_edge_ratio: float = DEFAULT_NEAR_BODY_EDGE_RATIO) -> list:
    '''Score adjacent-page paragraph continuation candidates.'''
    candidates = []
    page_summaries = page_summaries or []
    repeated_boundary_texts = _likely_repeated_boundary_texts(repeated_text_candidates)
    for index, previous_page in enumerate(page_summaries[:-1]):
        next_page = page_summaries[index+1]
        previous_block = _last_body_block(
            previous_page,
            excluded_texts=repeated_boundary_texts)
        next_block = _first_body_block(
            next_page,
            excluded_texts=repeated_boundary_texts)
        candidates.append(score_paragraph_continuation(
            previous_page,
            next_page,
            previous_block,
            next_block,
            repeated_boundary_texts=repeated_boundary_texts,
            top_ratio=top_ratio,
            bottom_ratio=bottom_ratio,
            near_edge_ratio=near_edge_ratio))
    return candidates


def score_paragraph_continuation(
        previous_page: dict,
        next_page: dict,
        previous_block: dict = None,
        next_block: dict = None,
        repeated_boundary_texts: set = None,
        top_ratio: float = DEFAULT_TOP_RATIO,
        bottom_ratio: float = DEFAULT_BOTTOM_RATIO,
        near_edge_ratio: float = DEFAULT_NEAR_BODY_EDGE_RATIO) -> dict:
    '''Score a possible paragraph continuation across two adjacent pages.'''
    positive, negative = [], []
    score = 0.0

    from_page = previous_page.get('page_index')
    to_page = next_page.get('page_index')

    if not previous_block:
        negative.append('no_previous_body_block')
    if not next_block:
        negative.append('no_next_body_block')
    if not previous_block or not next_block:
        return _continuation_result(
            from_page, to_page, previous_block, next_block, 0.0,
            positive, negative)

    positive.append('previous_block_body_region')
    positive.append('next_block_body_region')
    score += 0.2

    previous_text = normalize_text(previous_block.get('text', ''))
    next_text = normalize_text(next_block.get('text', ''))
    previous_bbox = previous_block.get('bbox', [0.0, 0.0, 0.0, 0.0])
    next_bbox = next_block.get('bbox', [0.0, 0.0, 0.0, 0.0])
    repeated_boundary_texts = repeated_boundary_texts or set()
    previous_quality = text_quality_signals(previous_text)
    next_quality = text_quality_signals(next_text)

    score += _text_quality_score_delta('previous', previous_quality, negative)
    score += _text_quality_score_delta('next', next_quality, negative)

    if _comparison_text(previous_text) in repeated_boundary_texts:
        negative.append('previous_repeated_boundary_text')
        score -= 0.35
    if _comparison_text(next_text) in repeated_boundary_texts:
        negative.append('next_repeated_boundary_text')
        score -= 0.35

    if _near_body_bottom(previous_bbox, previous_page, bottom_ratio, near_edge_ratio):
        positive.append('previous_near_body_bottom')
        score += 0.15
    else:
        negative.append('previous_not_near_body_bottom')
        score -= 0.05

    if _near_body_top(next_bbox, next_page, top_ratio, near_edge_ratio):
        positive.append('next_near_body_top')
        score += 0.15
    else:
        negative.append('next_not_near_body_top')
        score -= 0.05

    if _ends_with_strong_sentence_punctuation(previous_text):
        negative.append('previous_strong_sentence_end')
        score -= 0.5
    else:
        positive.append('previous_text_open_ended')
        score += 0.15

    if _ends_with_hyphenated_word(previous_text):
        positive.append('previous_hyphenated_word')
        score += 0.2

    previous_style = normalize_text(previous_block.get('style', ''))
    next_style = normalize_text(next_block.get('style', ''))
    if previous_style and next_style:
        if previous_style == next_style:
            positive.append('style_match')
            score += 0.1
        else:
            negative.append('style_mismatch')
            score -= 0.1

    if _left_boundary_similar(previous_bbox, next_bbox):
        positive.append('left_boundary_similar')
        score += 0.1
    elif _next_indented_like_new_paragraph(previous_bbox, next_bbox):
        negative.append('next_indented_like_new_paragraph')
        score -= 0.15
    else:
        negative.append('left_boundary_mismatch')
        score -= 0.05

    if _right_boundary_similar(previous_bbox, next_bbox):
        positive.append('right_boundary_similar')
        score += 0.05
    else:
        negative.append('right_boundary_mismatch')
        score -= 0.05

    if _looks_like_heading(next_text):
        negative.append('next_looks_like_heading')
        score -= 0.5

    score = min(max(score, 0.0), 1.0)
    return _continuation_result(
        from_page, to_page, previous_block, next_block, score,
        positive, negative)


def _style_from_block(block: dict) -> dict:
    return {
        'font': block.get('font', block.get('font_family', '')),
        'size': block.get('size', block.get('font_size', '')),
        'flags': block.get('flags', ''),
    }


def _json_bbox(bbox) -> list:
    if not bbox or len(bbox) < 4:
        return [0.0, 0.0, 0.0, 0.0]
    return [round(float(value), 2) for value in bbox[:4]]


def _json_number(value) -> float:
    return round(float(value or 0.0), 2)


def _strip_inline_code(text: str) -> str:
    value = normalize_text(text)
    if value.startswith('`') and value.endswith('`') and len(value) >= 2:
        return value[1:-1]
    return value


def _parse_human_decision(text: str) -> tuple:
    checked = [
        name for name, marker in _REVIEW_DECISION_RE.findall(text or '')
        if normalize_text(marker).lower() == 'x'
    ]
    if len(checked) == 1:
        return checked[0], checked
    if not checked:
        return DECISION_NONE, checked
    return DECISION_CONFLICT, checked


def _dry_run_candidates(dry_run_report: dict) -> list:
    dry_run_report = dry_run_report or {}
    if 'header_footer_exclusion_dry_run' in dry_run_report:
        dry_run_report = dry_run_report.get('header_footer_exclusion_dry_run') or {}
    return dry_run_report.get('candidates', []) or []


def _review_decision_map(review_decisions) -> dict:
    if isinstance(review_decisions, dict):
        decisions = review_decisions.get('decisions', [])
    else:
        decisions = review_decisions or []

    mapping = {}
    for decision in decisions:
        manual_decision = decision.get('manual_decision', DECISION_NONE)
        for key in (decision.get('fingerprint'), decision.get('candidate_id')):
            if key:
                mapping[key] = manual_decision
    return mapping


def _decision_counts(review_decisions) -> dict:
    if isinstance(review_decisions, dict):
        summary = review_decisions.get('summary', {}) or {}
        counts = summary.get('decision_counts')
        if counts is not None:
            return dict(counts)
        decisions = review_decisions.get('decisions', [])
    else:
        decisions = review_decisions or []

    counts = defaultdict(int)
    for decision in decisions:
        counts[decision.get('manual_decision', DECISION_NONE)] += 1
    return dict(sorted(counts.items()))


def _reviewed_exclusion_candidates(candidates: list, decision_map: dict) -> tuple:
    approved = []
    blocked = []
    for candidate in candidates or []:
        decision = (
            decision_map.get(candidate.get('fingerprint')) or
            decision_map.get(candidate.get('candidate_id')) or
            DECISION_NONE)
        allowed, reason = _reviewed_candidate_allowed(candidate, decision)
        item = {
            'candidate_id': candidate.get('candidate_id', ''),
            'fingerprint': candidate.get('fingerprint', ''),
            'proposed_role': candidate.get('proposed_role', ''),
            'action': candidate.get('action', ''),
            'manual_decision': decision,
            'reason': reason,
            'affected_pages': list(candidate.get('affected_pages', []) or []),
            'regions': list(candidate.get('regions', []) or []),
        }
        if allowed:
            approved.append(item)
        else:
            blocked.append(item)
    return approved, blocked


def _reviewed_candidate_allowed(candidate: dict, decision: str) -> tuple:
    if decision != DECISION_APPROVE_EXCLUDE:
        return False, 'manual_decision_not_approved'
    if candidate.get('action') != ACTION_WOULD_EXCLUDE:
        return False, 'dry_run_action_not_would_exclude'

    role = candidate.get('proposed_role')
    if role == ROLE_LAYOUT_PLACEHOLDER:
        return False, 'layout_placeholder_not_filterable'
    if role not in {ROLE_HEADER, ROLE_FOOTER, ROLE_PAGE_NUMBER}:
        return False, 'role_not_filterable'
    return True, 'approved_review_decision'


def _block_matches_reviewed_candidate(block: dict, page_index, candidate: dict) -> bool:
    if block.get('fingerprint') != candidate.get('fingerprint'):
        return False
    affected_pages = set(candidate.get('affected_pages', []) or [])
    if affected_pages and page_index not in affected_pages:
        return False
    regions = set(candidate.get('regions', []) or [])
    return not regions or block.get('region') in regions


def _removed_block_summary(block: dict, candidate: dict) -> dict:
    return {
        'block_index': block.get('block_index'),
        'fingerprint': block.get('fingerprint', ''),
        'region': block.get('region', ''),
        'candidate_id': candidate.get('candidate_id', ''),
        'proposed_role': candidate.get('proposed_role', ''),
        'manual_decision': candidate.get('manual_decision', ''),
        'explicit_approval': candidate.get('manual_decision') == DECISION_APPROVE_EXCLUDE,
        'removal_reason': candidate.get('reason', ''),
        'text_preview': _preview_text(block, max_length=80),
    }


def _filtered_page_summary(page: dict, kept_blocks: list) -> dict:
    filtered = dict(page)
    blocks = [dict(block) for block in kept_blocks]
    region_counts = {
        REGION_TOP: 0,
        REGION_BODY: 0,
        REGION_BOTTOM: 0,
    }
    for block in blocks:
        region = block.get('region')
        if region in region_counts:
            region_counts[region] += 1

    filtered['text_blocks'] = blocks
    filtered['text_block_count'] = len(blocks)
    filtered['region_counts'] = region_counts
    filtered['text'] = normalize_text(' '.join(block.get('text', '') for block in blocks))
    return filtered


def _removed_block_lookup(filtering_report: dict) -> tuple:
    removed_keys = set()
    removed_by_key = {}
    for page in filtering_report.get('pages', []) or []:
        page_index = page.get('page_index')
        for block in page.get('removed_blocks', []) or []:
            key = (page_index, block.get('block_index'))
            removed_keys.add(key)
            removed_by_key[key] = block
    return removed_keys, removed_by_key


def _diff_removed_block_summary(page_index, block: dict, removed: dict) -> dict:
    return {
        'page_index': page_index,
        'page_number': _human_page_number(page_index),
        'block_index': block.get('block_index'),
        'candidate_id': removed.get('candidate_id', ''),
        'fingerprint': block.get('fingerprint', ''),
        'proposed_role': removed.get('proposed_role', ''),
        'manual_decision': removed.get('manual_decision', ''),
        'explicit_approval': bool(removed.get('explicit_approval')),
        'region': block.get('region', ''),
        'reason': removed.get('removal_reason', ''),
        'short_preview': _preview_text(block, max_length=100),
    }


def _kept_block_summary(page_index, block: dict) -> dict:
    return {
        'page_index': page_index,
        'page_number': _human_page_number(page_index),
        'block_index': block.get('block_index'),
        'fingerprint': block.get('fingerprint', ''),
        'region': block.get('region', ''),
        'short_preview': _preview_text(block, max_length=100),
    }


def _append_candidate_removed_block(grouped, summary: dict):
    key = summary.get('candidate_id') or summary.get('fingerprint')
    item = grouped[key]
    if not item['candidate_id']:
        item['candidate_id'] = summary.get('candidate_id', '')
        item['fingerprint'] = summary.get('fingerprint', '')
        item['proposed_role'] = summary.get('proposed_role', '')
        item['manual_decision'] = summary.get('manual_decision', '')
    item['removed_count'] += 1
    item['blocks'].append(summary)


def _new_safety_summary() -> dict:
    return {
        'warnings': [],
        'unapproved_removed_candidate_count': 0,
        'unapproved_removed_candidates': [],
        'rejected_removed_candidate_count': 0,
        'unsure_removed_candidate_count': 0,
        'layout_placeholder_removed_candidate_count': 0,
    }


def _record_safety_for_removed_block(
        safety: dict,
        summary: dict,
        approved_fingerprints: set,
        blocked_by_fingerprint: dict):
    fingerprint = summary.get('fingerprint')
    blocked = blocked_by_fingerprint.get(fingerprint)
    manual_decision = summary.get('manual_decision')
    proposed_role = summary.get('proposed_role')

    if fingerprint not in approved_fingerprints:
        _add_unique_safety_candidate(
            safety,
            'unapproved_removed_candidates',
            summary)
        safety['unapproved_removed_candidate_count'] = len(
            safety['unapproved_removed_candidates'])

    effective_decision = blocked.get('manual_decision') if blocked else manual_decision
    if effective_decision == DECISION_REJECT_EXCLUDE:
        safety['rejected_removed_candidate_count'] += 1
    elif effective_decision == DECISION_UNSURE:
        safety['unsure_removed_candidate_count'] += 1

    if proposed_role == ROLE_LAYOUT_PLACEHOLDER:
        safety['layout_placeholder_removed_candidate_count'] += 1


def _add_unique_safety_candidate(safety: dict, key: str, summary: dict):
    candidate = {
        'candidate_id': summary.get('candidate_id', ''),
        'fingerprint': summary.get('fingerprint', ''),
        'manual_decision': summary.get('manual_decision', ''),
        'proposed_role': summary.get('proposed_role', ''),
    }
    if candidate not in safety[key]:
        safety[key].append(candidate)


def _finalize_safety_warnings(safety: dict):
    if safety['unapproved_removed_candidate_count']:
        safety['warnings'].append('Unapproved candidates would be removed.')
    if safety['rejected_removed_candidate_count']:
        safety['warnings'].append('Rejected candidates would be removed.')
    if safety['unsure_removed_candidate_count']:
        safety['warnings'].append('Unsure candidates would be removed.')
    if safety['layout_placeholder_removed_candidate_count']:
        safety['warnings'].append('Layout placeholder candidates would be removed.')


def _human_page_number(page_index):
    if isinstance(page_index, int):
        return page_index + 1
    return page_index


def _diff_report_removed_lookup(diff_report: dict) -> dict:
    lookup = {}
    for page in (diff_report or {}).get('removed_blocks_by_page', []) or []:
        page_index = page.get('page_index')
        for block in page.get('blocks', []) or []:
            lookup[(page_index, block.get('block_index'))] = block
    return lookup


def _integrity_removed_block_summary(page_index, block: dict, removed: dict) -> dict:
    return {
        'page_index': page_index,
        'page_number': _human_page_number(page_index),
        'block_index': block.get('block_index'),
        'region': block.get('region', ''),
        'fingerprint': block.get('fingerprint', ''),
        'candidate_id': removed.get('candidate_id', ''),
        'proposed_role': removed.get('proposed_role', ''),
        'explicit_approval': bool(removed.get('explicit_approval')),
        'short_preview': _preview_text(block, max_length=100),
    }


def _paragraph_integrity_page_report(
        page: dict,
        kept_blocks: list,
        removed_blocks: list,
        high_body_loss_ratio: float) -> dict:
    page_index = page.get('page_index')
    original_blocks = page.get('text_blocks', []) or []
    original_body_blocks = [
        block for block in original_blocks
        if block.get('region') == REGION_BODY
    ]
    kept_body_blocks = [
        block for block in kept_blocks
        if block.get('region') == REGION_BODY
    ]
    removed_body_blocks = [
        block for block in removed_blocks
        if block.get('region') == REGION_BODY
    ]
    body_loss_warnings = []
    paragraph_gap_warnings = []

    if removed_body_blocks:
        body_loss_warnings.append({
            'page_index': page_index,
            'page_number': _human_page_number(page_index),
            'type': 'body_region_removed',
            'message': 'Body-region blocks would be removed.',
            'removed_body_count': len(removed_body_blocks),
            'blocks': removed_body_blocks,
        })

    body_loss_ratio = (
        len(removed_body_blocks) / len(original_body_blocks)
        if original_body_blocks else 0.0)
    if body_loss_ratio > high_body_loss_ratio:
        body_loss_warnings.append({
            'page_index': page_index,
            'page_number': _human_page_number(page_index),
            'type': 'high_body_loss_ratio',
            'message': 'Page would lose an unusually high share of body-region blocks.',
            'removed_body_count': len(removed_body_blocks),
            'original_body_count': len(original_body_blocks),
            'body_loss_ratio': round(body_loss_ratio, 3),
        })

    paragraph_gap_warnings.extend(_paragraph_gap_warnings(
        page_index,
        original_blocks,
        kept_blocks,
        removed_blocks))

    return {
        'page_index': page_index,
        'page_number': _human_page_number(page_index),
        'original_block_count': len(original_blocks),
        'filtered_block_count': len(kept_blocks),
        'removed_block_count': len(removed_blocks),
        'body_region_original_count': len(original_body_blocks),
        'body_region_kept_count': len(kept_body_blocks),
        'body_region_removed_count': len(removed_body_blocks),
        'top_bottom_removed_count': sum(
            1 for block in removed_blocks
            if block.get('region') in {REGION_TOP, REGION_BOTTOM}),
        'removed_blocks': removed_blocks,
        'body_loss_warnings': body_loss_warnings,
        'paragraph_gap_warnings': paragraph_gap_warnings,
    }


def _paragraph_gap_warnings(
        page_index,
        original_blocks: list,
        kept_blocks: list,
        removed_blocks: list) -> list:
    warnings = []
    removed_body_indices = {
        block.get('block_index')
        for block in removed_blocks
        if block.get('region') == REGION_BODY
    }
    if not removed_body_indices:
        return warnings

    kept_body_indices = {
        block.get('block_index')
        for block in kept_blocks
        if block.get('region') == REGION_BODY
    }
    original_body_blocks = [
        block for block in sorted(
            original_blocks,
            key=lambda item: item.get('block_index', 0))
        if block.get('region') == REGION_BODY
    ]

    for index, block in enumerate(original_body_blocks):
        block_index = block.get('block_index')
        if block_index not in removed_body_indices:
            continue

        previous_kept = any(
            item.get('block_index') in kept_body_indices
            for item in original_body_blocks[:index])
        next_kept = any(
            item.get('block_index') in kept_body_indices
            for item in original_body_blocks[index+1:])
        if previous_kept and next_kept:
            warnings.append({
                'page_index': page_index,
                'page_number': _human_page_number(page_index),
                'type': 'body_flow_gap',
                'message': 'Removed body-region block sits between kept body blocks.',
                'block_index': block_index,
                'short_preview': _preview_text(block, max_length=100),
            })

    return warnings


def _copy_page_summaries(page_summaries: list) -> list:
    copied = []
    for page in page_summaries or []:
        copied_page = dict(page)
        copied_page['text_blocks'] = [
            dict(block)
            for block in page.get('text_blocks', []) or []
        ]
        copied.append(copied_page)
    return copied


def _paragraph_integrity_recommendation(
        enabled: bool,
        safe: bool,
        warning_count: int) -> str:
    if not enabled:
        return 'Paragraph integrity validation is disabled; no filtering assumptions were evaluated.'
    if safe:
        return 'No suspicious body loss or paragraph-gap warnings were detected in the report-only validation.'
    return f'Found {warning_count} warning(s); do not connect filtering to production parsing yet.'


def _reconstruction_filtered_pages(
        page_summaries: list,
        paragraph_integrity_report: dict,
        body_filtering_diff_report: dict,
        enabled: bool) -> list:
    if not enabled:
        return _copy_page_summaries(page_summaries)

    if paragraph_integrity_report and paragraph_integrity_report.get('filtered_pages') is not None:
        return _copy_page_summaries(paragraph_integrity_report.get('filtered_pages'))

    if body_filtering_diff_report:
        integrity_report = build_paragraph_integrity_report(
            page_summaries,
            body_filtering_diff_report,
            enabled=True)
        return _copy_page_summaries(integrity_report.get('filtered_pages'))

    return _copy_page_summaries(page_summaries)


def _paragraph_reconstruction_page_report(
        original_page: dict,
        filtered_page: dict,
        max_line_gap_ratio: float,
        paragraph_gap_ratio: float,
        indent_tolerance: float,
        single_line_fragment_ratio: float,
        short_fragment_length: int) -> dict:
    page_index = filtered_page.get('page_index')
    original_body_blocks = _body_blocks(original_page)
    filtered_body_blocks = _body_blocks(filtered_page)
    groups, gap_warnings, split_boundaries = _estimate_paragraph_groups(
        filtered_page,
        filtered_body_blocks,
        max_line_gap_ratio,
        paragraph_gap_ratio,
        indent_tolerance,
        short_fragment_length)
    suspicious_single_line = [
        group for group in groups
        if group.get('suspicious_single_line_paragraph')
    ]
    suspicious_short_fragments = [
        group for group in groups
        if group.get('suspicious_short_fragment')
    ]
    warnings = list(gap_warnings)

    if filtered_body_blocks and not groups:
        warnings.append({
            'page_index': page_index,
            'page_number': _human_page_number(page_index),
            'type': 'missing_paragraph_groups',
            'message': 'Body blocks are present, but no estimated paragraph groups were produced.',
        })

    if groups:
        single_line_ratio = len(suspicious_single_line) / len(groups)
        if len(groups) >= 3 and single_line_ratio >= single_line_fragment_ratio:
            warnings.append({
                'page_index': page_index,
                'page_number': _human_page_number(page_index),
                'type': 'excessive_one_line_fragmentation',
                'message': 'Most estimated paragraph groups contain only one body line/block.',
                'single_line_group_count': len(suspicious_single_line),
                'estimated_paragraph_group_count': len(groups),
                'single_line_group_ratio': round(single_line_ratio, 3),
            })

        short_fragment_ratio = len(suspicious_short_fragments) / len(groups)
        if len(suspicious_short_fragments) >= 3 and short_fragment_ratio >= 0.5:
            warnings.append({
                'page_index': page_index,
                'page_number': _human_page_number(page_index),
                'type': 'many_short_fragments',
                'message': 'Many estimated paragraph groups are short fragments.',
                'short_fragment_count': len(suspicious_short_fragments),
                'estimated_paragraph_group_count': len(groups),
                'short_fragment_ratio': round(short_fragment_ratio, 3),
            })

    if original_body_blocks and not filtered_body_blocks:
        warnings.append({
            'page_index': page_index,
            'page_number': _human_page_number(page_index),
            'type': 'body_blocks_missing_after_filtering',
            'message': 'Original body blocks exist, but none remain in the filtered summary.',
            'original_body_block_count': len(original_body_blocks),
        })

    return {
        'page_index': page_index,
        'page_number': _human_page_number(page_index),
        'body_block_count_before_filtering': len(original_body_blocks),
        'body_block_count_after_filtering': len(filtered_body_blocks),
        'estimated_paragraph_group_count': len(groups),
        'average_blocks_per_estimated_paragraph': _safe_ratio(
            len(filtered_body_blocks),
            len(groups)),
        'suspicious_single_line_paragraph_count': len(suspicious_single_line),
        'suspicious_short_fragment_count': len(suspicious_short_fragments),
        'estimated_paragraph_groups': groups,
        'split_boundaries': split_boundaries,
        'warnings': warnings,
    }


def _estimate_paragraph_groups(
        page: dict,
        body_blocks: list,
        max_line_gap_ratio: float,
        paragraph_gap_ratio: float,
        indent_tolerance: float,
        short_fragment_length: int) -> tuple:
    groups = []
    warnings = []
    split_boundaries = []
    if not body_blocks:
        return groups, warnings, split_boundaries

    sorted_blocks = sorted(
        [dict(block) for block in body_blocks],
        key=lambda block: block.get('block_index', 0))
    line_units = _body_line_units(sorted_blocks)
    if not line_units:
        return groups, warnings, split_boundaries

    metrics = _paragraph_line_metrics(sorted_blocks)
    current_units = [line_units[0]]
    break_before_reasons = []

    for unit in line_units[1:]:
        previous = current_units[-1]
        break_reasons, gap_warning, boundary_signals = _paragraph_break_reasons(
            previous,
            unit,
            metrics,
            max_line_gap_ratio,
            paragraph_gap_ratio,
            indent_tolerance)
        if gap_warning:
            warnings.append(_paragraph_gap_warning(page, previous, unit, gap_warning))

        if break_reasons:
            groups.append(_estimated_paragraph_group(
                page,
                len(groups),
                current_units,
                break_before_reasons,
                short_fragment_length))
            split_boundaries.append(_paragraph_split_boundary(
                page,
                len(split_boundaries),
                previous,
                unit,
                break_reasons,
                boundary_signals))
            current_units = [unit]
            break_before_reasons = break_reasons
        else:
            current_units.append(unit)

    groups.append(_estimated_paragraph_group(
        page,
        len(groups),
        current_units,
        break_before_reasons,
        short_fragment_length))
    return groups, warnings, split_boundaries


def _body_line_units(blocks: list) -> list:
    units = []
    current = []
    for block in sorted(blocks or [], key=lambda item: item.get('block_index', 0)):
        if current and not _same_physical_row(_union_bbox(current), block.get('bbox', [])):
            units.append(_line_unit_from_blocks(current, len(units)))
            current = []
        current.append(dict(block))

    if current:
        units.append(_line_unit_from_blocks(current, len(units)))
    return units


def _line_unit_from_blocks(blocks: list, line_index: int) -> dict:
    ordered_blocks = sorted(
        [dict(block) for block in blocks or []],
        key=lambda block: (
            _bbox_value(block.get('bbox'), 0),
            block.get('block_index', 0)))
    text = normalize_text(' '.join(block.get('text', '') for block in ordered_blocks))
    styles = _unique_styles(ordered_blocks)
    block_indexes = [block.get('block_index') for block in ordered_blocks]
    bbox = _union_bbox(ordered_blocks)
    return {
        'line_index': line_index,
        'block_index': block_indexes[0] if block_indexes else None,
        'block_indexes': block_indexes,
        'block_count': len(ordered_blocks),
        'row_fragment_count': len(ordered_blocks),
        'text': text,
        'bbox': bbox,
        'style': styles[0] if len(styles) == 1 else 'mixed',
        'styles': styles,
        'width': round(max(0.0, bbox[2] - bbox[0]), 2),
    }


def _same_physical_row(previous_bbox, current_bbox) -> bool:
    if not previous_bbox or not current_bbox or len(previous_bbox) < 4 or len(current_bbox) < 4:
        return False

    previous_height = max(_block_height(previous_bbox), 1.0)
    current_height = max(_block_height(current_bbox), 1.0)
    overlap = min(float(previous_bbox[3]), float(current_bbox[3])) - max(
        float(previous_bbox[1]),
        float(current_bbox[1]))
    if overlap > 0.0 and overlap / min(previous_height, current_height) >= 0.35:
        return True

    previous_center = (float(previous_bbox[1]) + float(previous_bbox[3])) / 2.0
    current_center = (float(current_bbox[1]) + float(current_bbox[3])) / 2.0
    return abs(previous_center - current_center) <= max(previous_height, current_height) * 0.45


def _paragraph_break_reasons(
        previous: dict,
        current: dict,
        metrics: dict,
        max_line_gap_ratio: float,
        paragraph_gap_ratio: float,
        indent_tolerance: float) -> tuple:
    reasons = []
    warning = None
    previous_bbox = previous.get('bbox', [0.0, 0.0, 0.0, 0.0])
    current_bbox = current.get('bbox', [0.0, 0.0, 0.0, 0.0])
    insufficient_metadata = (
        not previous_bbox or len(previous_bbox) < 4 or
        not current_bbox or len(current_bbox) < 4)
    line_height = max(
        metrics.get('median_line_height', 0.0),
        _block_height(previous_bbox),
        _block_height(current_bbox),
        1.0)
    vertical_gap = max(0.0, float(current_bbox[1]) - float(previous_bbox[3]))
    gap_ratio = vertical_gap / line_height
    previous_text = normalize_text(previous.get('text', ''))
    current_text = normalize_text(current.get('text', ''))
    previous_sentence_end = _ends_with_strong_sentence_punctuation(previous_text)
    previous_hyphenated = _ends_with_hyphenated_word(previous_text)
    previous_heading = _looks_like_heading(previous_text)
    current_heading = _looks_like_heading(current_text)
    previous_list = _looks_like_list_item(previous_text)
    current_list = _looks_like_list_item(current_text)
    left_delta = float(current_bbox[0]) - float(previous_bbox[0])
    right_delta = float(current_bbox[2]) - float(previous_bbox[2])
    previous_width = max(0.0, float(previous_bbox[2]) - float(previous_bbox[0]))
    current_width = max(0.0, float(current_bbox[2]) - float(current_bbox[0]))
    body_width = max(float(metrics.get('max_right', 0.0)) - float(metrics.get('min_left', 0.0)), 1.0)
    right_gap_ratio = max(0.0, float(metrics.get('max_right', 0.0)) - float(previous_bbox[2])) / body_width
    previous_width_ratio = previous_width / body_width
    width_delta_ratio = abs(previous_width - current_width) / max(previous_width, current_width, 1.0)
    significant_style_change = _significant_style_change(previous, current)

    signals = {
        'vertical_gap': round(vertical_gap, 2),
        'gap_ratio': round(gap_ratio, 3),
        'left_delta': round(left_delta, 2),
        'right_delta': round(right_delta, 2),
        'right_edge_similar': abs(right_delta) <= 18.0,
        'width_delta_ratio': round(width_delta_ratio, 3),
        'width_similar': width_delta_ratio <= 0.18,
        'previous_sentence_end': previous_sentence_end,
        'previous_hyphenated': previous_hyphenated,
        'previous_heading_like': previous_heading,
        'current_heading_like': current_heading,
        'previous_list_marker': previous_list,
        'current_list_marker': current_list,
        'style_change': previous.get('style') != current.get('style'),
        'significant_style_change': significant_style_change,
        'previous_width_ratio': round(previous_width_ratio, 3),
        'previous_right_gap_ratio': round(right_gap_ratio, 3),
        'insufficient_metadata': insufficient_metadata,
    }

    if insufficient_metadata:
        reasons.append('insufficient_metadata')

    if current_list:
        reasons.append('list_marker')
    elif previous_list:
        reasons.append('previous_list_item')

    if current_heading:
        reasons.append('heading_like')
    elif previous_heading:
        reasons.append('previous_heading_like')

    if gap_ratio >= paragraph_gap_ratio:
        reasons.append('large_vertical_gap')
    elif gap_ratio > max_line_gap_ratio and not previous_hyphenated:
        warning = {
            'type': 'suspicious_vertical_gap_inside_paragraph',
            'vertical_gap': round(vertical_gap, 2),
            'gap_ratio': round(gap_ratio, 3),
        }

    if significant_style_change and not previous_hyphenated:
        reasons.append('style_change')

    if abs(left_delta) > indent_tolerance and not previous_hyphenated:
        if left_delta > 0.0 or previous_sentence_end or gap_ratio > max_line_gap_ratio:
            reasons.append('indentation_change')

    if (previous_sentence_end and
            right_gap_ratio >= 0.12 and
            previous_width_ratio <= 0.88 and
            not previous_hyphenated):
        reasons.append('sentence_end_with_trailing_space')

    if reasons:
        warning = None

    return sorted(set(reasons)), warning, signals


def _estimated_paragraph_group(
        page: dict,
        group_index: int,
        line_units: list,
        break_before_reasons: list,
        short_fragment_length: int) -> dict:
    text = normalize_text(' '.join(unit.get('text', '') for unit in line_units))
    quality = text_quality_signals(text)
    line_count = len(line_units)
    block_count = sum(unit.get('block_count', 1) for unit in line_units)
    one_line = line_count == 1
    looks_like_heading = _looks_like_heading(text)
    looks_like_list = _looks_like_list_item(text)
    suspicious_single_line = (
        one_line and
        quality.get('meaningful_text') and
        not looks_like_heading and
        not looks_like_list)
    suspicious_short = (
        suspicious_single_line and
        len(text) < short_fragment_length)

    page_index = page.get('page_index')
    block_indexes = [
        block_index
        for unit in line_units
        for block_index in unit.get('block_indexes', [])
    ]
    return {
        'page_index': page_index,
        'page_number': _human_page_number(page_index),
        'group_index': group_index,
        'block_count': block_count,
        'line_count': line_count,
        'block_indexes': block_indexes,
        'start_block_index': block_indexes[0] if block_indexes else None,
        'end_block_index': block_indexes[-1] if block_indexes else None,
        'bbox': _union_bbox(line_units),
        'text_preview': _preview_text({'text': text}, max_length=120),
        'break_before_reasons': list(break_before_reasons or []),
        'starts_with_list_marker': bool(looks_like_list),
        'heading_like': bool(looks_like_heading),
        'suspicious_single_line_paragraph': bool(suspicious_single_line),
        'suspicious_short_fragment': bool(suspicious_short),
    }


def _paragraph_split_boundary(
        page: dict,
        boundary_index: int,
        previous: dict,
        current: dict,
        reasons: list,
        signals: dict) -> dict:
    page_index = page.get('page_index')
    return {
        'page_index': page_index,
        'page_number': _human_page_number(page_index),
        'boundary_index': boundary_index,
        'previous_line_index': previous.get('line_index'),
        'next_line_index': current.get('line_index'),
        'previous_block_indexes': list(previous.get('block_indexes', []) or []),
        'next_block_indexes': list(current.get('block_indexes', []) or []),
        'reasons': list(reasons or []),
        'signals': dict(signals or {}),
        'previous_text_preview': _preview_text(previous, max_length=100),
        'next_text_preview': _preview_text(current, max_length=100),
    }


def _paragraph_gap_warning(page: dict, previous: dict, current: dict, gap: dict) -> dict:
    page_index = page.get('page_index')
    return {
        'page_index': page_index,
        'page_number': _human_page_number(page_index),
        'type': gap.get('type'),
        'message': 'Adjacent body blocks have a larger-than-expected gap but were kept in one estimated group.',
        'previous_block_index': previous.get('block_index'),
        'next_block_index': current.get('block_index'),
        'vertical_gap': gap.get('vertical_gap'),
        'gap_ratio': gap.get('gap_ratio'),
        'previous_preview': _preview_text(previous, max_length=80),
        'next_preview': _preview_text(current, max_length=80),
    }


def _cross_page_continuation_warning(candidate: dict) -> dict:
    return {
        'from_page': candidate.get('from_page'),
        'to_page': candidate.get('to_page'),
        'type': 'possible_cross_page_continuation',
        'message': 'Adjacent-page body blocks may belong to the same paragraph; report only, no merge applied.',
        'split_reasons': ['page_boundary'],
        'label': candidate.get('label'),
        'score': candidate.get('score'),
        'reason': candidate.get('reason'),
        'previous_text_preview': candidate.get('previous_text_preview', ''),
        'next_text_preview': candidate.get('next_text_preview', ''),
    }


def _paragraph_reconstruction_recommendation(safe: bool, warning_count: int) -> str:
    if safe:
        return 'No paragraph reconstruction warnings were detected in the report-only validation.'
    return f'Found {warning_count} paragraph reconstruction warning(s); keep production DOCX integration gated.'


def _estimator_grouping_metrics(estimator_report: dict) -> dict:
    estimator_report = estimator_report or {}
    summary = estimator_report.get('summary') or {}
    pages = []
    for page in estimator_report.get('pages', []) or []:
        pages.append({
            'page_index': page.get('page_index'),
            'page_number': page.get('page_number'),
            'paragraph_group_count': page.get('estimated_paragraph_group_count', 0),
            'body_block_count': page.get('body_block_count_after_filtering', 0),
            'average_blocks_per_group': page.get('average_blocks_per_estimated_paragraph', 0.0),
            'suspicious_single_line_count': page.get('suspicious_single_line_paragraph_count', 0),
            'suspicious_short_fragment_count': page.get('suspicious_short_fragment_count', 0),
        })

    return {
        'available': bool(estimator_report),
        'paragraph_group_count': summary.get('estimated_paragraph_group_count', 0),
        'body_block_count': summary.get('body_block_count_after_filtering', 0),
        'average_blocks_per_group': summary.get('average_blocks_per_estimated_paragraph', 0.0),
        'suspicious_single_line_count': summary.get('suspicious_single_line_paragraph_count', 0),
        'suspicious_short_fragment_count': summary.get('suspicious_short_fragment_count', 0),
        'one_line_group_ratio': summary.get('one_line_group_ratio', 0.0),
        'short_fragment_ratio': summary.get('short_fragment_ratio', 0.0),
        'pages': pages,
        'diagnostics': estimator_report.get('diagnostics', {}),
    }


def _production_observed_grouping_metrics(
        production_pages: list,
        top_ratio: float,
        bottom_ratio: float,
        short_fragment_length: int) -> dict:
    page_reports = []
    all_groups = []
    body_groups = []
    for fallback_page_index, page in enumerate(production_pages or []):
        page_index = page.get('page_index', page.get('id', fallback_page_index))
        page_height = page.get('height', page.get('page_height', 0.0))
        groups = _production_text_groups(
            page,
            page_index,
            page_height,
            top_ratio,
            bottom_ratio,
            short_fragment_length)
        page_body_groups = [
            group for group in groups
            if group.get('region') == REGION_BODY
        ]
        page_report = _production_page_grouping_metrics(
            page,
            page_index,
            groups,
            page_body_groups,
            short_fragment_length)
        page_reports.append(page_report)
        all_groups.extend(groups)
        body_groups.extend(page_body_groups)

    return {
        'available': True,
        'policy': 'serialized_production_textblock_observation',
        'page_count': len(production_pages or []),
        'all_text_group_count': len(all_groups),
        'body_text_group_count': len(body_groups),
        'paragraph_group_count': len(body_groups),
        'total_body_line_count': sum(group.get('line_count', 0) for group in body_groups),
        'average_lines_per_group': _safe_ratio(
            sum(group.get('line_count', 0) for group in body_groups),
            len(body_groups)),
        'average_blocks_per_group': _safe_ratio(
            sum(group.get('line_count', 0) for group in body_groups),
            len(body_groups)),
        'suspicious_single_line_count': sum(
            1 for group in body_groups
            if group.get('suspicious_single_line_paragraph')),
        'suspicious_short_fragment_count': sum(
            1 for group in body_groups
            if group.get('suspicious_short_fragment')),
        'one_line_group_ratio': _safe_ratio(
            sum(1 for group in body_groups if group.get('line_count') == 1),
            len(body_groups)),
        'short_fragment_ratio': _safe_ratio(
            sum(1 for group in body_groups if group.get('suspicious_short_fragment')),
            len(body_groups)),
        'pages': page_reports,
    }


def _production_text_groups(
        page: dict,
        page_index,
        page_height: float,
        top_ratio: float,
        bottom_ratio: float,
        short_fragment_length: int) -> list:
    groups = []
    group_index = 0
    for section in page.get('sections', []) or []:
        for column_index, column in enumerate(section.get('columns', []) or []):
            for block in column.get('blocks', []) or []:
                if block.get('type') != 0:
                    continue
                group = _production_text_group(
                    block,
                    page_index,
                    _human_page_number(page_index),
                    group_index,
                    column_index,
                    page_height,
                    top_ratio,
                    bottom_ratio,
                    short_fragment_length)
                groups.append(group)
                group_index += 1
    return groups


def _production_text_group(
        block: dict,
        page_index,
        page_number,
        group_index: int,
        column_index: int,
        page_height: float,
        top_ratio: float,
        bottom_ratio: float,
        short_fragment_length: int) -> dict:
    lines = block.get('lines', []) or []
    text = normalize_text(' '.join(_production_line_text(line) for line in lines))
    bbox = _json_bbox(block.get('bbox'))
    region = classify_y_band(bbox, page_height, top_ratio, bottom_ratio) if page_height else REGION_BODY
    quality = text_quality_signals(text)
    line_count = len(lines)
    looks_like_heading = _looks_like_heading(text)
    looks_like_list = _looks_like_list_item(text)
    suspicious_single_line = (
        line_count == 1 and
        quality.get('meaningful_text') and
        not looks_like_heading and
        not looks_like_list)
    suspicious_short = suspicious_single_line and len(text) < short_fragment_length
    return {
        'page_index': page_index,
        'page_number': page_number,
        'group_index': group_index,
        'column_index': column_index,
        'region': region,
        'bbox': bbox,
        'line_count': line_count,
        'block_count': line_count,
        'text_preview': _preview_text({'text': text}, max_length=120),
        'heading_like': bool(looks_like_heading),
        'starts_with_list_marker': bool(looks_like_list),
        'suspicious_single_line_paragraph': bool(suspicious_single_line),
        'suspicious_short_fragment': bool(suspicious_short),
    }


def _production_page_grouping_metrics(
        page: dict,
        page_index,
        groups: list,
        body_groups: list,
        short_fragment_length: int) -> dict:
    single_line_count = sum(
        1 for group in body_groups
        if group.get('line_count') == 1 and
        group.get('suspicious_single_line_paragraph'))
    short_fragment_count = sum(
        1 for group in body_groups
        if group.get('suspicious_short_fragment') and
        len(group.get('text_preview', '')) < short_fragment_length)
    line_count = sum(group.get('line_count', 0) for group in body_groups)
    return {
        'page_index': page_index,
        'page_number': _human_page_number(page_index),
        'all_text_group_count': len(groups),
        'paragraph_group_count': len(body_groups),
        'body_text_group_count': len(body_groups),
        'line_count': line_count,
        'average_lines_per_group': _safe_ratio(line_count, len(body_groups)),
        'suspicious_single_line_count': single_line_count,
        'suspicious_short_fragment_count': short_fragment_count,
        'one_line_group_ratio': _safe_ratio(
            sum(1 for group in body_groups if group.get('line_count') == 1),
            len(body_groups)),
        'body_text_groups': [
            _production_group_summary(group)
            for group in body_groups
        ],
    }


def _production_line_text(line: dict) -> str:
    texts = []
    for span in line.get('spans', []) or []:
        text = span.get('text', '')
        if text:
            texts.append(text)
    return normalize_text(''.join(texts))


def _paragraph_grouping_mismatch(estimator: dict, production: dict) -> dict:
    if not production.get('available'):
        return {
            'available': False,
            'reason': 'Production metrics are unavailable.',
        }

    estimator_count = int(estimator.get('paragraph_group_count') or 0)
    production_count = int(production.get('paragraph_group_count') or 0)
    delta = estimator_count - production_count
    page_mismatches = _paragraph_grouping_page_mismatches(
        estimator.get('pages', []),
        production.get('pages', []))
    return {
        'available': True,
        'estimator_group_count': estimator_count,
        'production_group_count': production_count,
        'absolute_group_count_delta': abs(delta),
        'signed_group_count_delta': delta,
        'estimator_to_production_group_ratio': _safe_ratio(estimator_count, production_count),
        'group_count_delta_ratio': _safe_ratio(abs(delta), production_count),
        'average_group_size_delta': round(
            float(estimator.get('average_blocks_per_group') or 0.0) -
            float(production.get('average_lines_per_group') or 0.0),
            3),
        'one_line_ratio_delta': round(
            float(estimator.get('one_line_group_ratio') or 0.0) -
            float(production.get('one_line_group_ratio') or 0.0),
            3),
        'pages_with_largest_mismatch': page_mismatches[:5],
        'likely_reason': _paragraph_grouping_mismatch_reason(delta, page_mismatches),
    }


def _paragraph_grouping_page_mismatches(estimator_pages: list, production_pages: list) -> list:
    estimator_by_page = {
        page.get('page_index'): page
        for page in estimator_pages or []
    }
    production_by_page = {
        page.get('page_index'): page
        for page in production_pages or []
    }
    page_indexes = sorted(set(estimator_by_page) | set(production_by_page))
    mismatches = []
    for page_index in page_indexes:
        estimator_page = estimator_by_page.get(page_index, {})
        production_page = production_by_page.get(page_index, {})
        estimator_count = int(estimator_page.get('paragraph_group_count') or 0)
        production_count = int(production_page.get('paragraph_group_count') or 0)
        delta = estimator_count - production_count
        mismatches.append({
            'page_index': page_index,
            'page_number': _human_page_number(page_index),
            'estimator_group_count': estimator_count,
            'production_group_count': production_count,
            'absolute_group_count_delta': abs(delta),
            'signed_group_count_delta': delta,
            'delta_ratio': _safe_ratio(abs(delta), production_count),
        })

    return sorted(
        mismatches,
        key=lambda item: (
            -item['absolute_group_count_delta'],
            item['page_number']))


def _paragraph_grouping_mismatch_reason(delta: int, page_mismatches: list) -> str:
    if delta == 0:
        return 'Estimator and production-observed body TextBlock counts match.'
    if delta > 0:
        return 'Estimator has more groups than production-observed TextBlocks; report-only grouping may still be more fragmented.'
    return 'Production-observed TextBlocks exceed estimator groups; production may split by layout, tables, columns, or formatting beyond report-only signals.'


def _production_comparison_recommendation(warning_count: int, mismatch: dict) -> str:
    if warning_count:
        return 'Review production comparison warnings before attempting any production integration.'
    if mismatch.get('group_count_delta_ratio', 0.0) <= 0.25:
        return 'Estimator is close enough to production-observed grouping for another report-only validation phase.'
    return 'Keep comparison report-only; mismatch remains large enough to require further diagnostics.'


def _production_group_summary(group: dict) -> dict:
    return {
        'page_index': group.get('page_index'),
        'page_number': group.get('page_number'),
        'group_index': group.get('group_index'),
        'line_count': group.get('line_count', 0),
        'block_count': group.get('block_count', 0),
        'region': group.get('region', ''),
        'bbox': list(group.get('bbox', []) or []),
        'text_preview': group.get('text_preview', ''),
        'suspicious_single_line_paragraph': bool(group.get('suspicious_single_line_paragraph')),
        'suspicious_short_fragment': bool(group.get('suspicious_short_fragment')),
    }


def _paragraph_mismatch_page_analyses(
        estimator_report: dict,
        production_metrics: dict) -> list:
    estimator_pages = (estimator_report or {}).get('pages', []) or []
    estimator_by_page = {
        page.get('page_index'): page
        for page in estimator_pages
    }
    production_by_page = {
        page.get('page_index'): page
        for page in production_metrics.get('pages', []) or []
    }
    page_indexes = sorted(set(estimator_by_page) | set(production_by_page))
    analyses = []
    for page_index in page_indexes:
        estimator_page = estimator_by_page.get(page_index, {})
        production_page = production_by_page.get(page_index, {})
        analyses.append(_paragraph_mismatch_page_analysis(
            page_index,
            estimator_page,
            production_page))

    return sorted(
        analyses,
        key=lambda item: (
            -item['absolute_group_count_delta'],
            item['page_number']))


def _paragraph_mismatch_page_analysis(
        page_index,
        estimator_page: dict,
        production_page: dict) -> dict:
    estimator_count = int(estimator_page.get('estimated_paragraph_group_count') or 0)
    production_count = int(production_page.get('paragraph_group_count') or 0)
    delta = estimator_count - production_count
    split_reason_counts = _page_split_reason_counts(estimator_page)
    production_line_counts = [
        group.get('line_count', 0)
        for group in production_page.get('body_text_groups', []) or []
    ]
    cause = _classify_mismatch_cause(
        delta,
        split_reason_counts,
        production_line_counts,
        estimator_page,
        production_page)
    return {
        'page_index': page_index,
        'page_number': _human_page_number(page_index),
        'estimator_group_count': estimator_count,
        'production_group_count': production_count,
        'absolute_group_count_delta': abs(delta),
        'signed_group_count_delta': delta,
        'delta_ratio': _safe_ratio(abs(delta), production_count),
        'estimator_split_reason_counts': dict(sorted(split_reason_counts.items())),
        'production_textblock_line_counts': production_line_counts,
        'production_average_lines_per_group': _safe_ratio(
            sum(production_line_counts),
            len(production_line_counts)),
        'likely_cause': cause,
        'cause_signals': _mismatch_cause_signals(
            delta,
            split_reason_counts,
            production_line_counts,
            estimator_page,
            production_page),
        'estimator_group_previews': _estimator_group_previews(estimator_page),
        'production_group_previews': _production_group_previews(production_page),
    }


def _page_split_reason_counts(estimator_page: dict) -> Counter:
    counts = Counter()
    for boundary in estimator_page.get('split_boundaries', []) or []:
        for reason in boundary.get('reasons', []) or []:
            counts[reason] += 1
    return counts


def _classify_mismatch_cause(
        delta: int,
        split_reason_counts: Counter,
        production_line_counts: list,
        estimator_page: dict,
        production_page: dict) -> str:
    if not estimator_page or not production_page:
        return 'insufficient_data'
    if delta < 0:
        return 'production_possible_over_split'
    if delta == 0:
        return 'counts_aligned'

    if split_reason_counts.get('indentation_change', 0) >= max(2, abs(delta) // 3):
        return 'estimator_over_split_by_indentation'
    if split_reason_counts.get('style_change', 0) >= max(2, abs(delta) // 3):
        return 'estimator_over_split_by_style_change'
    if split_reason_counts.get('sentence_end_with_trailing_space', 0) >= 2:
        return 'estimator_over_split_by_sentence_end'
    heading_list_count = (
        split_reason_counts.get('heading_like', 0) +
        split_reason_counts.get('previous_heading_like', 0) +
        split_reason_counts.get('list_marker', 0) +
        split_reason_counts.get('previous_list_item', 0))
    if heading_list_count >= 2:
        return 'heading_or_list_boundary_difference'
    if production_line_counts and max(production_line_counts) >= 6:
        return 'production_possible_over_merge'
    if estimator_page.get('body_block_count_after_filtering') and production_page.get('line_count'):
        if estimator_page.get('body_block_count_after_filtering') > production_page.get('line_count') * 2:
            return 'estimator_missing_line_join_metadata'
    return 'estimator_over_splitting'


def _mismatch_cause_signals(
        delta: int,
        split_reason_counts: Counter,
        production_line_counts: list,
        estimator_page: dict,
        production_page: dict) -> dict:
    return {
        'estimator_has_more_groups': delta > 0,
        'production_has_more_groups': delta < 0,
        'max_production_lines_per_group': max(production_line_counts or [0]),
        'estimator_body_block_count': estimator_page.get('body_block_count_after_filtering', 0),
        'production_line_count': production_page.get('line_count', 0),
        'dominant_split_reason': (
            split_reason_counts.most_common(1)[0][0]
            if split_reason_counts else ''),
        'dominant_split_reason_count': (
            split_reason_counts.most_common(1)[0][1]
            if split_reason_counts else 0),
    }


def _estimator_group_previews(estimator_page: dict, limit: int = 3) -> list:
    return [
        {
            'group_index': group.get('group_index'),
            'line_count': group.get('line_count', 0),
            'block_count': group.get('block_count', 0),
            'break_before_reasons': list(group.get('break_before_reasons', []) or []),
            'text_preview': group.get('text_preview', ''),
        }
        for group in (estimator_page.get('estimated_paragraph_groups', []) or [])[:limit]
    ]


def _production_group_previews(production_page: dict, limit: int = 3) -> list:
    return [
        {
            'group_index': group.get('group_index'),
            'line_count': group.get('line_count', 0),
            'text_preview': group.get('text_preview', ''),
        }
        for group in (production_page.get('body_text_groups', []) or [])[:limit]
    ]


def _mismatch_analysis_recommendation(dominant_cause: str, warnings: list) -> str:
    if warnings:
        return 'Keep the work report-only and investigate the mismatch causes before production integration.'
    if dominant_cause in {'counts_aligned'}:
        return 'Counts align in this report, but keep the next phase internal before integration.'
    return f'Dominant mismatch cause is {dominant_cause}; keep Phase 2H diagnostic/report-only.'


def _empty_paragraph_grouping_diagnostics() -> dict:
    return {
        'groups_by_line_count': {},
        'groups_by_block_count': {},
        'one_line_group_ratio': 0.0,
        'short_fragment_ratio': 0.0,
        'split_reason_counts': {},
        'most_common_split_reasons': [],
        'pages_with_worst_fragmentation': [],
        'warning_counts': {},
        'split_boundary_count': 0,
    }


def _paragraph_grouping_diagnostics(
        pages_report: list,
        warnings: list,
        possible_continuations: list) -> dict:
    groups = [
        group
        for page in pages_report or []
        for group in page.get('estimated_paragraph_groups', []) or []
    ]
    split_boundaries = [
        boundary
        for page in pages_report or []
        for boundary in page.get('split_boundaries', []) or []
    ]
    split_reason_counts = Counter()
    for boundary in split_boundaries:
        for reason in boundary.get('reasons', []) or []:
            split_reason_counts[reason] += 1
    if possible_continuations:
        split_reason_counts['page_boundary'] += len(possible_continuations)

    one_line_count = sum(1 for group in groups if group.get('line_count') == 1)
    short_fragment_count = sum(
        1 for group in groups
        if group.get('suspicious_short_fragment'))
    warning_counts = Counter(warning.get('type') for warning in warnings or [])

    if possible_continuations:
        warning_counts['possible_cross_page_continuation'] += len(possible_continuations)

    return {
        'groups_by_line_count': _groups_by_size(groups, 'line_count'),
        'groups_by_block_count': _groups_by_size(groups, 'block_count'),
        'one_line_group_ratio': _safe_ratio(one_line_count, len(groups)),
        'short_fragment_ratio': _safe_ratio(short_fragment_count, len(groups)),
        'split_reason_counts': dict(sorted(split_reason_counts.items())),
        'most_common_split_reasons': _counter_top_items(split_reason_counts),
        'pages_with_worst_fragmentation': _pages_with_worst_fragmentation(pages_report),
        'warning_counts': dict(sorted(warning_counts.items())),
        'split_boundary_count': len(split_boundaries),
    }


def _groups_by_size(groups: list, key: str) -> dict:
    counts = Counter()
    for group in groups or []:
        size = int(group.get(key) or 0)
        bucket = '5+' if size >= 5 else str(size)
        counts[bucket] += 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def _counter_top_items(counter: Counter, limit: int = 8) -> list:
    return [
        {'reason': key, 'count': value}
        for key, value in counter.most_common(limit)
    ]


def _pages_with_worst_fragmentation(pages_report: list, limit: int = 5) -> list:
    page_items = []
    for page in pages_report or []:
        group_count = int(page.get('estimated_paragraph_group_count') or 0)
        if not group_count:
            continue
        one_line_count = int(page.get('suspicious_single_line_paragraph_count') or 0)
        short_count = int(page.get('suspicious_short_fragment_count') or 0)
        page_items.append({
            'page_index': page.get('page_index'),
            'page_number': page.get('page_number'),
            'estimated_paragraph_group_count': group_count,
            'body_block_count_after_filtering': page.get('body_block_count_after_filtering', 0),
            'one_line_group_ratio': _safe_ratio(one_line_count, group_count),
            'short_fragment_ratio': _safe_ratio(short_count, group_count),
            'suspicious_single_line_paragraph_count': one_line_count,
            'suspicious_short_fragment_count': short_count,
        })

    return sorted(
        page_items,
        key=lambda item: (
            -item['one_line_group_ratio'],
            -item['suspicious_single_line_paragraph_count'],
            item['page_number']))[:limit]


def _body_blocks(page: dict) -> list:
    return [
        block for block in (page or {}).get('text_blocks', []) or []
        if block.get('region') == REGION_BODY
    ]


def _paragraph_line_metrics(blocks: list) -> dict:
    heights = [
        _block_height(block.get('bbox', []))
        for block in blocks
        if _block_height(block.get('bbox', [])) > 0.0
    ]
    bboxes = [
        block.get('bbox', [])
        for block in blocks or []
        if block.get('bbox') and len(block.get('bbox')) >= 4
    ]
    gaps = []
    sorted_blocks = sorted(
        [block for block in blocks or [] if block.get('bbox') and len(block.get('bbox')) >= 4],
        key=lambda item: item.get('block_index', 0))
    for previous, current in zip(sorted_blocks, sorted_blocks[1:]):
        if _same_physical_row(previous.get('bbox'), current.get('bbox')):
            continue
        gaps.append(max(0.0, float(current['bbox'][1]) - float(previous['bbox'][3])))

    return {
        'median_line_height': _median_number(heights) or 1.0,
        'median_vertical_gap': _median_number(gaps),
        'min_left': min((float(bbox[0]) for bbox in bboxes), default=0.0),
        'max_right': max((float(bbox[2]) for bbox in bboxes), default=0.0),
    }


def _block_height(bbox) -> float:
    if not bbox or len(bbox) < 4:
        return 0.0
    return max(0.0, float(bbox[3]) - float(bbox[1]))


def _median_number(values: list) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(float(value) for value in values)
    middle = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return sorted_values[middle]
    return (sorted_values[middle-1] + sorted_values[middle]) / 2.0


def _safe_ratio(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 3)


def _bbox_value(bbox, index: int) -> float:
    if not bbox or len(bbox) <= index:
        return 0.0
    return float(bbox[index])


def _union_bbox(blocks: list) -> list:
    bboxes = [
        block.get('bbox', [])
        for block in blocks
        if block.get('bbox') and len(block.get('bbox')) >= 4
    ]
    if not bboxes:
        return [0.0, 0.0, 0.0, 0.0]
    return [
        round(min(float(bbox[0]) for bbox in bboxes), 2),
        round(min(float(bbox[1]) for bbox in bboxes), 2),
        round(max(float(bbox[2]) for bbox in bboxes), 2),
        round(max(float(bbox[3]) for bbox in bboxes), 2),
    ]


def _unique_styles(blocks: list) -> list:
    styles = []
    for block in blocks or []:
        style = normalize_text(block.get('style', ''))
        if style and style not in styles:
            styles.append(style)
    return styles


def _significant_style_change(previous: dict, current: dict) -> bool:
    previous_style = normalize_text(previous.get('style', ''))
    current_style = normalize_text(current.get('style', ''))
    if not previous_style or not current_style or previous_style == current_style:
        return False
    if 'mixed' in {previous_style, current_style}:
        return False

    previous_font, previous_size = _style_font_size(previous_style)
    current_font, current_size = _style_font_size(current_style)
    if previous_size and current_size and abs(previous_size - current_size) >= 0.75:
        return True
    if previous_font and current_font and previous_font != current_font:
        return True
    return previous_size is None or current_size is None


def _style_font_size(style: str) -> tuple:
    if isinstance(style, dict):
        style = normalize_style_key(style)
    parts = normalize_text(style).split('|')
    font = parts[0] if parts else ''
    size = None
    if len(parts) > 1:
        try:
            size = float(parts[1])
        except (TypeError, ValueError):
            size = None
    return font, size


def _dry_run_candidate(candidate: dict, index: int, page_count: int = None) -> dict:
    signals = candidate.get('signals', {}) or {}
    quality = signals.get('text_quality') or text_quality_signals(candidate.get('text', ''))
    support = int(signals.get('support_pages') or len(candidate.get('pages', []) or []))
    total_pages = int(page_count or signals.get('total_pages') or support or 0)
    regions = sorted(candidate.get('regions') or signals.get('regions') or [])
    if not regions:
        regions = [REGION_BODY]

    confidence_label = candidate.get('confidence_label', '')
    semantic_confidence = float(candidate.get('semantic_confidence') or 0.0)
    support_level = signals.get('support_level') or _support_level(support, total_pages)
    adjacent_only = bool(signals.get('adjacent_only'))
    placeholder_kind = quality.get('placeholder_kind', '')

    positive, negative = [], []
    action = ACTION_KEEP
    proposed_role = ROLE_KEEP_BODY

    if support_level == 'high':
        positive.append('high_support')
    elif support_level == 'medium':
        positive.append('medium_support')
    else:
        negative.append('low_support')

    if adjacent_only:
        negative.append('adjacent_only_repetition')

    if REGION_BODY in regions:
        negative.append('body_region_repetition')
        action = ACTION_KEEP
        proposed_role = ROLE_KEEP_BODY
    elif placeholder_kind == 'image':
        positive.append('layout_placeholder_signal')
        negative.append('placeholder_not_semantic_text')
        action = ACTION_REVIEW
        proposed_role = ROLE_LAYOUT_PLACEHOLDER
    elif placeholder_kind and placeholder_kind != 'page_number':
        positive.append('placeholder_signal')
        negative.append('placeholder_not_semantic_text')
        action = ACTION_REVIEW
        proposed_role = ROLE_LAYOUT_PLACEHOLDER
    elif placeholder_kind == 'page_number':
        positive.append('page_number_placeholder')
        proposed_role = ROLE_PAGE_NUMBER
        if REGION_BOTTOM in regions and _high_support_for_exclusion(support_level, adjacent_only):
            positive.append('bottom_region')
            action = ACTION_WOULD_EXCLUDE
        else:
            action = ACTION_REVIEW
            negative.append('page_number_not_stable_footer')
    elif confidence_label == 'strong' and _high_support_for_exclusion(support_level, adjacent_only):
        if REGION_TOP in regions and REGION_BOTTOM not in regions:
            positive.append('top_region')
            action = ACTION_WOULD_EXCLUDE
            proposed_role = ROLE_HEADER
        elif REGION_BOTTOM in regions and REGION_TOP not in regions:
            positive.append('bottom_region')
            action = ACTION_WOULD_EXCLUDE
            proposed_role = ROLE_FOOTER
        else:
            action = ACTION_REVIEW
            proposed_role = ROLE_REVIEW_ONLY
            negative.append('mixed_or_unknown_boundary_region')
    elif regions and set(regions).issubset({REGION_TOP, REGION_BOTTOM}):
        action = ACTION_REVIEW
        proposed_role = ROLE_REVIEW_ONLY
        negative.append('not_safe_for_automatic_exclusion')
    else:
        negative.append('not_boundary_region')

    return {
        'candidate_id': f'repeated-{index+1}',
        'fingerprint': candidate.get('fingerprint', ''),
        'region': regions[0] if len(regions) == 1 else 'mixed',
        'regions': regions,
        'proposed_role': proposed_role,
        'action': action,
        'confidence_label': confidence_label,
        'confidence': candidate.get('confidence', 0.0),
        'semantic_confidence': round(semantic_confidence, 3),
        'support_count': support,
        'page_count': total_pages,
        'affected_pages': list(candidate.get('pages', []) or []),
        'positive_signals': positive,
        'negative_signals': negative,
        'reason': _dry_run_reason(action, proposed_role, positive, negative),
    }


def _high_support_for_exclusion(support_level: str, adjacent_only: bool) -> bool:
    return support_level == 'high' and not adjacent_only


def _dry_run_reason(
        action: str,
        proposed_role: str,
        positive: list,
        negative: list) -> str:
    if action == ACTION_WOULD_EXCLUDE:
        if proposed_role == ROLE_HEADER:
            return 'Dry-run only: high-support repeated top text could become a future header exclusion candidate.'
        if proposed_role == ROLE_FOOTER:
            return 'Dry-run only: high-support repeated bottom text could become a future footer exclusion candidate.'
        if proposed_role == ROLE_PAGE_NUMBER:
            return 'Dry-run only: stable bottom page-number placeholder could become a future page-number/footer candidate.'
    if 'body_region_repetition' in negative:
        return 'Repeated text is in the body region, so this dry run keeps it as body content.'
    if proposed_role == ROLE_LAYOUT_PLACEHOLDER:
        return 'Placeholder-like layout signal requires review and is not treated as semantic header/footer text.'
    if 'low_support' in negative or 'adjacent_only_repetition' in negative:
        return 'Repeated boundary text has limited support, so automatic exclusion is blocked.'
    if 'not_safe_for_automatic_exclusion' in negative:
        return 'Boundary repetition is reportable, but not safe enough for automatic exclusion.'
    if positive or negative:
        return 'Dry-run candidate requires manual review before any future body filtering.'
    return 'No header/footer exclusion signal was strong enough.'


def _last_body_block(page_summary: dict, excluded_texts: set = None):
    body_blocks = _body_blocks(page_summary, excluded_texts=excluded_texts)
    if not body_blocks:
        return None
    return sorted(body_blocks, key=lambda block: (block['bbox'][3], block['block_index']))[-1]


def _first_body_block(page_summary: dict, excluded_texts: set = None):
    body_blocks = _body_blocks(page_summary, excluded_texts=excluded_texts)
    if not body_blocks:
        return None
    return sorted(body_blocks, key=lambda block: (block['bbox'][1], block['block_index']))[0]


def _body_blocks(page_summary: dict, excluded_texts: set = None) -> list:
    blocks = page_summary.get('text_blocks', []) or []
    excluded_texts = excluded_texts or set()
    return [
        block for block in blocks
        if block.get('region') == REGION_BODY and normalize_text(block.get('text'))
        and _comparison_text(block.get('text', '')) not in excluded_texts
    ]


def _comparison_text(text) -> str:
    return normalize_page_number(normalize_text(text)).lower()


def _placeholder_kind(text) -> str:
    comparable = _comparison_text(text)
    if not comparable:
        return ''
    if comparable == PAGE_NUMBER_PLACEHOLDER.lower():
        return 'page_number'
    if comparable == IMAGE_PLACEHOLDER.lower():
        return 'image'
    if _PLACEHOLDER_RE.match(comparable):
        return 'generic'
    return ''


def _support_level(support: int, total_pages: int) -> str:
    if not total_pages:
        return 'none'
    if support <= 2 and total_pages > 2:
        return 'low'

    ratio = support / total_pages
    if ratio >= 0.75:
        return 'high'
    if ratio >= 0.5:
        return 'medium'
    return 'low'


def _is_adjacent_only(pages_seen: list, total_pages: int) -> bool:
    if len(pages_seen) < 2 or len(pages_seen) == total_pages:
        return False
    return pages_seen == list(range(pages_seen[0], pages_seen[-1]+1))


def _semantic_confidence(
        confidence: float,
        support: int,
        total_pages: int,
        quality: dict) -> float:
    support_penalty = 0.6 if support <= 2 and total_pages > 2 else 1.0
    semantic_weight = float(quality.get('semantic_weight', 1.0))
    return round(max(0.0, min(1.0, confidence * support_penalty * semantic_weight)), 3)


def _confidence_label(
        semantic_confidence: float,
        support_level: str,
        adjacent_only: bool,
        quality: dict) -> str:
    placeholder_kind = quality.get('placeholder_kind')
    if placeholder_kind and placeholder_kind != 'page_number':
        return 'placeholder'
    if support_level == 'low' or adjacent_only:
        return 'cautious'
    if semantic_confidence >= 0.75:
        return 'strong'
    if semantic_confidence >= 0.4:
        return 'moderate'
    return 'cautious'


def _repeated_candidate_reason(
        semantic_confidence: float,
        support_level: str,
        adjacent_only: bool,
        quality: dict) -> str:
    placeholder_kind = quality.get('placeholder_kind')
    if placeholder_kind == 'image':
        return 'Repeated image placeholder is reportable, but not strong semantic header/footer evidence by itself.'
    if placeholder_kind and placeholder_kind != 'page_number':
        return 'Repeated placeholder-like text is reportable, but semantic confidence is limited.'
    if support_level == 'low' or adjacent_only:
        return 'Low-support repeated boundary text; preserve as a cautious candidate.'
    if quality.get('short_text'):
        return 'Repeated short text has limited semantic confidence.'
    if semantic_confidence >= 0.75:
        return 'Repeated boundary text has strong support across pages.'
    if semantic_confidence >= 0.4:
        return 'Repeated boundary text has moderate support.'
    return 'Repeated boundary text has weak or mixed support signals.'


def _likely_repeated_boundary_texts(candidates: list) -> set:
    texts = set()
    for candidate in candidates or []:
        regions = set(candidate.get('regions', []) or [])
        if not regions.intersection({REGION_TOP, REGION_BOTTOM}):
            continue

        signals = candidate.get('signals', {}) or {}
        support = int(signals.get('support_pages') or 0)
        confidence = float(candidate.get('confidence') or 0.0)
        if support >= 3 or confidence >= 0.5:
            texts.add(_comparison_text(candidate.get('text', '')))
    return texts


def _text_quality_score_delta(prefix: str, quality: dict, negative: list) -> float:
    delta = 0.0
    if quality.get('placeholder_like'):
        negative.append(f'{prefix}_placeholder_text')
        delta -= 0.45
    if quality.get('short_text'):
        negative.append(f'{prefix}_short_text')
        delta -= 0.25
    if not quality.get('meaningful_text'):
        negative.append(f'{prefix}_low_meaningful_text')
        delta -= 0.15
    return delta


def _near_body_bottom(bbox, page_summary, bottom_ratio: float, near_edge_ratio: float) -> bool:
    page_height = float(page_summary.get('height') or 0.0)
    if page_height <= 0:
        return False
    body_bottom = page_height * (1.0 - bottom_ratio)
    return float(bbox[3]) >= body_bottom - page_height * near_edge_ratio


def _near_body_top(bbox, page_summary, top_ratio: float, near_edge_ratio: float) -> bool:
    page_height = float(page_summary.get('height') or 0.0)
    if page_height <= 0:
        return False
    body_top = page_height * top_ratio
    return float(bbox[1]) <= body_top + page_height * near_edge_ratio


def _ends_with_strong_sentence_punctuation(text: str) -> bool:
    return normalize_text(text).endswith(tuple(STRONG_SENTENCE_END_PUNC))


def _ends_with_hyphenated_word(text: str) -> bool:
    text = normalize_text(text)
    return bool(text) and text.endswith('-') and not text.endswith('--')


def _left_boundary_similar(previous_bbox, next_bbox, tolerance: float = 12.0) -> bool:
    return abs(float(previous_bbox[0]) - float(next_bbox[0])) <= tolerance


def _right_boundary_similar(previous_bbox, next_bbox, tolerance: float = 18.0) -> bool:
    return abs(float(previous_bbox[2]) - float(next_bbox[2])) <= tolerance


def _next_indented_like_new_paragraph(previous_bbox, next_bbox, tolerance: float = 18.0) -> bool:
    return float(next_bbox[0]) - float(previous_bbox[0]) > tolerance


def _looks_like_heading(text: str) -> bool:
    text = normalize_text(text)
    if not text or len(text) > 80:
        return False
    if _ends_with_strong_sentence_punctuation(text):
        return False
    if _SECTION_HEADING_RE.match(text) or _NUMBERED_HEADING_RE.match(text):
        return True

    words = text.split()
    letters = ''.join(c for c in text if c.isalpha())
    if len(words) <= 8 and len(letters) >= 4 and letters.upper() == letters:
        return True
    title_like = sum(1 for word in words if word[:1].isupper())
    return bool(words) and len(words) <= 6 and title_like == len(words)


def _looks_like_list_item(text: str) -> bool:
    return bool(_LIST_MARKER_RE.match(normalize_text(text)))


def _continuation_result(
        from_page,
        to_page,
        previous_block,
        next_block,
        score: float,
        positive_signals: list,
        negative_signals: list) -> dict:
    score = round(score, 3)
    return {
        'from_page': from_page,
        'to_page': to_page,
        'previous_text_preview': _preview_text(previous_block),
        'next_text_preview': _preview_text(next_block),
        'score': score,
        'label': _continuation_label(score),
        'positive_signals': positive_signals,
        'negative_signals': negative_signals,
        'reason': _continuation_reason(score, positive_signals, negative_signals),
    }


def _preview_text(block, max_length: int = 120) -> str:
    if not block:
        return ''
    text = normalize_text(block.get('text', ''))
    if len(text) <= max_length:
        return text
    return f'{text[:max_length-3]}...'


def _continuation_label(score: float) -> str:
    if score >= 0.65:
        return 'candidate'
    if score >= 0.4:
        return 'weak'
    return 'unlikely'


def _continuation_reason(score: float, positive: list, negative: list) -> str:
    if 'no_previous_body_block' in negative or 'no_next_body_block' in negative:
        return 'Missing body text candidate on one side of the page break.'
    if 'previous_repeated_boundary_text' in negative or 'next_repeated_boundary_text' in negative:
        return 'Candidate endpoint matches likely repeated header/footer boundary text.'
    if 'previous_placeholder_text' in negative or 'next_placeholder_text' in negative:
        return 'Candidate endpoint is placeholder-like text, so continuation confidence is limited.'
    if 'previous_short_text' in negative or 'next_short_text' in negative:
        return 'Candidate endpoint text is too short to be strong continuation evidence.'
    if 'previous_strong_sentence_end' in negative:
        return 'Previous text ends with strong sentence punctuation.'
    if 'next_looks_like_heading' in negative:
        return 'Next text looks like a heading or section title.'
    if 'previous_hyphenated_word' in positive:
        return 'Hyphenated page break with body-position continuation signals.'
    if score >= 0.65:
        return 'Adjacent body text blocks have continuation-like layout and text signals.'
    if score >= 0.4:
        return 'Some continuation signals are present, but confidence is limited.'
    return 'Continuation signals are weak or contradicted.'
