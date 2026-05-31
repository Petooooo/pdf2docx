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


def build_document_parse_filtering_simulation_report(
        page_summaries: list = None,
        dry_run_report: dict = None,
        review_decisions=None,
        body_filtering_diff_report: dict = None,
        paragraph_integrity_report: dict = None,
        enabled: bool = False,
        apply: bool = False,
        expected_removed_count: int = 48,
        expected_kept_count: int = 742,
        expected_body_region_removed_count: int = 0) -> dict:
    '''Simulate reviewed filtering at the document-parse insertion point.

    This helper never mutates production page/raw-page objects. It works on
    copied layout-analysis page summaries and reports what a future
    Pages._parse_document() opt-in experiment would remove.
    '''
    original_pages = _copy_page_summaries(page_summaries)
    original_block_count = _page_summary_block_count(original_pages)
    if not enabled:
        return {
            'enabled': False,
            'applied': False,
            'policy': 'document_parse_filtering_simulation_report_only',
            'insertion_point': 'document_parse',
            'summary': {
                'original_block_count': original_block_count,
                'would_remove_block_count': 0,
                'simulated_removed_count': 0,
                'simulated_kept_count': original_block_count,
                'approved_candidate_count': 0,
                'blocked_candidate_count': 0,
                'body_region_removed_count': 0,
                'rejected_removed_count': 0,
                'unsure_removed_count': 0,
                'layout_placeholder_removed_count': 0,
            },
            'dry_run': {
                'would_remove_block_count': 0,
                'removed_block_count': 0,
                'kept_block_count': original_block_count,
            },
            'simulated_apply': {
                'applied': False,
                'removed_block_count': 0,
                'kept_block_count': original_block_count,
                'filtered_pages': original_pages,
            },
            'removed_counts_by_role': {},
            'removed_counts_by_page': [],
            'downstream_availability': _document_parse_downstream_availability(
                original_pages,
                original_pages,
                []),
            'consistency_checks': {},
            'safety_warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2l': False,
                'reason': 'Document-parse filtering simulation is disabled; no production integration assumptions were evaluated.',
            },
        }

    review_decisions = review_decisions or {}
    dry_filter = build_reviewed_header_footer_filter_report(
        original_pages,
        dry_run_report,
        review_decisions,
        enabled=True,
        apply=False)
    diff_report = build_body_filtering_diff_report(
        original_pages,
        dry_run_report,
        review_decisions,
        enabled=True,
        filtering_report=dry_filter)
    apply_filter = build_reviewed_header_footer_filter_report(
        original_pages,
        dry_run_report,
        review_decisions,
        enabled=True,
        apply=True)
    simulated_pages = (
        apply_filter.get('filtered_pages', [])
        if apply else _copy_page_summaries(original_pages))
    removed_blocks = _document_parse_removed_blocks(diff_report)
    would_remove_count = len(removed_blocks)
    would_keep_count = original_block_count - would_remove_count
    simulated_removed_count = would_remove_count if apply else 0
    simulated_kept_count = would_keep_count if apply else original_block_count
    region_counts = _document_parse_removed_region_counts(removed_blocks)
    safety = diff_report.get('safety') or _new_safety_summary()
    consistency_checks = _document_parse_consistency_checks(
        original_block_count,
        would_remove_count,
        would_keep_count,
        region_counts.get(REGION_BODY, 0),
        body_filtering_diff_report,
        paragraph_integrity_report,
        expected_removed_count,
        expected_kept_count,
        expected_body_region_removed_count)
    warnings = _document_parse_simulation_warnings(
        review_decisions,
        dry_filter,
        safety,
        consistency_checks,
        region_counts)

    return {
        'enabled': True,
        'applied': bool(apply),
        'policy': 'document_parse_filtering_simulation_report_only',
        'insertion_point': 'document_parse',
        'summary': {
            'original_block_count': original_block_count,
            'would_remove_block_count': would_remove_count,
            'would_keep_block_count': would_keep_count,
            'simulated_removed_count': simulated_removed_count,
            'simulated_kept_count': simulated_kept_count,
            'approved_candidate_count': dry_filter.get('approved_candidate_count', 0),
            'blocked_candidate_count': dry_filter.get('blocked_candidate_count', 0),
            'body_region_removed_count': region_counts.get(REGION_BODY, 0),
            'rejected_removed_count': safety.get('rejected_removed_candidate_count', 0),
            'unsure_removed_count': safety.get('unsure_removed_candidate_count', 0),
            'layout_placeholder_removed_count': safety.get('layout_placeholder_removed_candidate_count', 0),
        },
        'dry_run': {
            'would_remove_block_count': would_remove_count,
            'removed_block_count': 0,
            'kept_block_count': original_block_count,
            'removed_blocks_by_page': diff_report.get('removed_blocks_by_page', []),
        },
        'simulated_apply': {
            'applied': bool(apply),
            'removed_block_count': simulated_removed_count,
            'kept_block_count': simulated_kept_count,
            'filtered_pages': simulated_pages,
        },
        'removed_counts_by_role': _document_parse_removed_counts_by_role(removed_blocks),
        'removed_counts_by_page': _document_parse_removed_counts_by_page(diff_report),
        'removed_blocks_by_page': diff_report.get('removed_blocks_by_page', []),
        'retained_candidates': diff_report.get('retained_candidates', []),
        'downstream_availability': _document_parse_downstream_availability(
            original_pages,
            simulated_pages,
            removed_blocks),
        'consistency_checks': consistency_checks,
        'safety_warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2l': _document_parse_safe_for_phase_2l(warnings, region_counts),
            'reason': _document_parse_recommendation(warnings, region_counts),
        },
    }


def build_document_parse_filtering_hook_report(
        page_summaries: list = None,
        dry_run_report: dict = None,
        review_decisions=None,
        body_filtering_diff_report: dict = None,
        paragraph_integrity_report: dict = None,
        phase_2k_simulation_report: dict = None,
        enabled: bool = False,
        apply: bool = False,
        expected_removed_count: int = 48,
        expected_kept_count: int = 742,
        expected_body_region_removed_count: int = 0) -> dict:
    '''Build the internal Pages._parse_document() hook dry-run report.

    The hook scaffold is report-only. Even when ``apply`` is requested, the
    underlying simulation works on copied summaries and never mutates
    production page/raw-page objects.
    '''
    simulation = build_document_parse_filtering_simulation_report(
        page_summaries,
        dry_run_report,
        review_decisions,
        body_filtering_diff_report=body_filtering_diff_report,
        paragraph_integrity_report=paragraph_integrity_report,
        enabled=enabled,
        apply=apply,
        expected_removed_count=expected_removed_count,
        expected_kept_count=expected_kept_count,
        expected_body_region_removed_count=expected_body_region_removed_count)
    summary = dict(simulation.get('summary') or {})
    summary.update({
        'default_behavior_changed': False,
        'production_objects_mutated': False,
        'production_removed_count': 0,
        'hook_report_stored': bool(enabled),
    })
    phase_2k_consistency = _document_parse_hook_phase_2k_consistency(
        simulation,
        phase_2k_simulation_report)
    safety_warnings = list(simulation.get('safety_warnings') or [])
    recommendation = _document_parse_hook_recommendation(
        enabled,
        safety_warnings,
        summary)

    return {
        'enabled': bool(enabled),
        'applied': bool(simulation.get('applied')),
        'production_applied': False,
        'policy': 'document_parse_hook_scaffold_report_only',
        'hook_location': 'Pages._parse_document()',
        'insertion_point': 'document_parse',
        'mode': 'dry_run_report_only',
        'summary': summary,
        'dry_run': simulation.get('dry_run', {}),
        'simulated_apply': simulation.get('simulated_apply', {}),
        'simulation': simulation,
        'phase_2k_consistency': phase_2k_consistency,
        'safety_warnings': safety_warnings,
        'recommendation': {
            'safe_to_attempt_phase_2m': recommendation[0],
            'reason': recommendation[1],
        },
    }


def build_document_parse_raw_object_mapping_report(
        page_summaries: list = None,
        raw_object_pages: list = None,
        dry_run_report: dict = None,
        review_decisions=None,
        enabled: bool = False,
        expected_would_remove_count: int = None,
        exact_bbox_tolerance: float = 0.75,
        fuzzy_bbox_tolerance: float = 3.0) -> dict:
    '''Validate reviewed summary-to-raw-object mapping without mutating input.

    This is an internal document-parse diagnostic. It proves whether approved
    layout-summary removal candidates can be matched to exactly one raw-page
    object near ``Pages._parse_document()``.
    '''
    page_summaries = _copy_page_summaries(page_summaries)
    raw_records = _raw_object_records(raw_object_pages)
    if not enabled:
        return {
            'enabled': False,
            'policy': 'document_parse_raw_object_mapping_report_only',
            'insertion_point': 'document_parse',
            'mapping_target': 'raw_page.blocks after clean_up/process_font',
            'summary': _raw_mapping_empty_summary(expected_would_remove_count),
            'mappings': [],
            'mapping_quality_by_page': [],
            'mapping_quality_by_role': {},
            'safety_warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2n': False,
                'reason': 'Raw-object mapping validation is disabled.',
            },
        }

    dry_run_report = dry_run_report or {}
    review_decisions = review_decisions or {}
    filtering_report = build_reviewed_header_footer_filter_report(
        page_summaries,
        dry_run_report,
        review_decisions,
        enabled=True,
        apply=False)
    blocked_fingerprints = {
        candidate.get('fingerprint')
        for candidate in filtering_report.get('blocked_candidates', []) or []
        if candidate.get('fingerprint')
    }
    expected_blocks = _raw_mapping_expected_blocks(
        page_summaries,
        dry_run_report,
        review_decisions)
    raw_by_page = defaultdict(list)
    for record in raw_records:
        raw_by_page[record.get('page_index')].append(record)

    mappings = []
    for expected in expected_blocks:
        mappings.append(_raw_mapping_for_expected_block(
            expected,
            raw_by_page.get(expected.get('page_index'), []),
            blocked_fingerprints,
            exact_bbox_tolerance,
            fuzzy_bbox_tolerance))

    summary = _raw_mapping_summary(
        mappings,
        filtering_report,
        expected_would_remove_count)
    warnings = _raw_mapping_warnings(summary, mappings)
    return {
        'enabled': True,
        'policy': 'document_parse_raw_object_mapping_report_only',
        'insertion_point': 'document_parse',
        'mapping_target': 'raw_page.blocks after clean_up/process_font',
        'summary': summary,
        'mappings': mappings,
        'mapping_quality_by_page': _raw_mapping_quality_by_page(mappings),
        'mapping_quality_by_role': _raw_mapping_quality_by_role(mappings),
        'safety_warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2n': _raw_mapping_safe_for_phase_2n(summary, warnings),
            'reason': _raw_mapping_recommendation(summary, warnings),
        },
    }


def build_document_parse_copied_raw_page_filtering_apply_report(
        page_summaries: list = None,
        raw_object_pages: list = None,
        dry_run_report: dict = None,
        review_decisions=None,
        raw_object_mapping_report: dict = None,
        enabled: bool = False,
        expected_mapping_count: int = None) -> dict:
    '''Apply reviewed filtering to copied raw-page-like data only.

    This helper is an internal experiment. It never mutates source raw pages;
    it removes validated mapping targets only from copied ``raw_object_pages``.
    '''
    original_raw_pages = _copy_raw_object_pages(raw_object_pages)
    original_count = _raw_object_page_count(original_raw_pages)
    if not enabled:
        return {
            'enabled': False,
            'applied_to_copy': False,
            'production_applied': False,
            'policy': 'copied_raw_page_filtering_apply_report_only',
            'insertion_point': 'document_parse',
            'summary': _copied_apply_disabled_summary(original_count, expected_mapping_count),
            'copied_filtered_pages': original_raw_pages,
            'removed_objects_by_page': [],
            'removed_counts_by_role': {},
            'removed_counts_by_page': [],
            'downstream_inputs': _copied_apply_downstream_inputs(
                original_raw_pages,
                original_raw_pages,
                []),
            'consistency_with_phase_2m': {},
            'safety_warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2o': False,
                'reason': 'Copied raw-page filtering experiment is disabled.',
            },
        }

    mapping_report = raw_object_mapping_report or build_document_parse_raw_object_mapping_report(
        page_summaries,
        raw_object_pages,
        dry_run_report,
        review_decisions,
        enabled=True,
        expected_would_remove_count=expected_mapping_count)
    removal_plan = _copied_apply_removal_plan(mapping_report)
    filtered_pages, removed_objects_by_page, missing_apply_targets = _copied_apply_filter_pages(
        original_raw_pages,
        removal_plan)
    removed_objects = [
        removed
        for page in removed_objects_by_page
        for removed in page.get('objects', []) or []
    ]
    consistency = _copied_apply_phase_2m_consistency(
        mapping_report,
        len(removed_objects),
        expected_mapping_count)
    summary = _copied_apply_summary(
        original_raw_pages,
        filtered_pages,
        removed_objects,
        mapping_report,
        consistency)
    warnings = _copied_apply_warnings(
        summary,
        mapping_report,
        consistency,
        missing_apply_targets)

    return {
        'enabled': True,
        'applied_to_copy': True,
        'production_applied': False,
        'policy': 'copied_raw_page_filtering_apply_report_only',
        'insertion_point': 'document_parse',
        'summary': summary,
        'copied_filtered_pages': filtered_pages,
        'removed_objects_by_page': removed_objects_by_page,
        'removed_counts_by_role': _copied_apply_removed_counts_by_role(removed_objects),
        'removed_counts_by_page': _copied_apply_removed_counts_by_page(removed_objects_by_page),
        'downstream_inputs': _copied_apply_downstream_inputs(
            original_raw_pages,
            filtered_pages,
            removed_objects),
        'consistency_with_phase_2m': consistency,
        'safety_warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2o': _copied_apply_safe_for_phase_2o(summary, warnings),
            'reason': _copied_apply_recommendation(summary, warnings),
        },
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
                'ignored_split_boundary_count': 0,
                'ignored_split_reason_counts': {},
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
            'ignored_split_boundary_count': diagnostics['ignored_split_boundary_count'],
            'ignored_split_reason_counts': diagnostics['ignored_split_reason_counts'],
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


def build_indentation_rule_comparison_report(
        estimator_report: dict = None,
        enabled: bool = False,
        new_paragraph_free_space_ratio: float = 0.85,
        small_indent_tolerance: float = 24.0,
        page_limit: int = 8) -> dict:
    '''Compare estimator indentation splits with production-like split rules.'''
    estimator_report = estimator_report or {}
    if not enabled:
        return {
            'enabled': False,
            'policy': 'indentation_rule_comparison_report_only',
            'summary': {
                'total_indentation_split_boundaries': 0,
                'estimator_should_merge_count': 0,
                'estimator_should_split_count': 0,
                'needs_more_metadata_count': 0,
                'production_behavior_unclear_count': 0,
            },
            'pages': [],
            'boundaries': [],
            'warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2i': False,
                'reason': 'Indentation rule comparison is disabled; no integration assumptions were evaluated.',
            },
        }

    boundaries = []
    for page in estimator_report.get('pages', []) or []:
        for boundary in page.get('split_boundaries', []) or []:
            if 'indentation_change' not in (boundary.get('reasons', []) or []):
                continue
            boundaries.append(_indentation_boundary_comparison(
                page,
                boundary,
                new_paragraph_free_space_ratio,
                small_indent_tolerance))

    recommendation_counts = Counter(
        boundary['recommendation']
        for boundary in boundaries)
    keep_reasons = Counter(
        boundary.get('production_keep_reason', '')
        for boundary in boundaries
        if boundary.get('production_keep_reason'))
    pages = _indentation_pages_summary(boundaries, page_limit)
    return {
        'enabled': True,
        'policy': 'indentation_rule_comparison_report_only',
        'summary': {
            'total_indentation_split_boundaries': len(boundaries),
            'estimator_should_merge_count': recommendation_counts.get('estimator_should_merge', 0),
            'estimator_should_split_count': recommendation_counts.get('estimator_should_split', 0),
            'needs_more_metadata_count': recommendation_counts.get('needs_more_metadata', 0),
            'production_behavior_unclear_count': recommendation_counts.get('production_behavior_unclear', 0),
            'most_common_production_keep_reasons': _counter_top_items(keep_reasons),
        },
        'pages': pages,
        'boundaries': boundaries,
        'warnings': [],
        'recommendation': {
            'safe_to_attempt_phase_2i': False,
            'reason': _indentation_rule_recommendation(recommendation_counts),
        },
    }


def build_filter_insertion_point_analysis_report(
        layout_analysis_report: dict = None,
        review_decisions=None,
        body_filtering_diff_report: dict = None,
        paragraph_integrity_report: dict = None,
        paragraph_grouping_report: dict = None,
        production_comparison_report: dict = None,
        paragraph_mismatch_report: dict = None,
        indentation_rule_report: dict = None,
        enabled: bool = False) -> dict:
    '''Compare future header/footer filtering insertion points without applying filtering.'''
    if not enabled:
        return {
            'enabled': False,
            'policy': 'filter_insertion_point_analysis_report_only',
            'summary': {
                'evaluated_insertion_point_count': 0,
                'preferred_insertion_point': '',
                'possible_insertion_points': [],
                'avoid_insertion_points': [],
                'missing_inputs': [],
            },
            'metrics': {},
            'insertion_points': [],
            'warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2k': False,
                'reason': 'Insertion point analysis is disabled; no production integration assumptions were evaluated.',
            },
        }

    metrics = _filter_insertion_metrics(
        layout_analysis_report,
        review_decisions,
        body_filtering_diff_report,
        paragraph_integrity_report,
        paragraph_grouping_report,
        production_comparison_report,
        paragraph_mismatch_report,
        indentation_rule_report)
    warnings = _filter_insertion_warnings(metrics)
    insertion_points = [
        _filter_insertion_point_analysis(spec, metrics)
        for spec in _filter_insertion_point_specs()
    ]
    preferred = [
        point['candidate_id']
        for point in insertion_points
        if point['recommendation'] == 'preferred'
    ]
    possible = [
        point['candidate_id']
        for point in insertion_points
        if point['recommendation'] == 'possible'
    ]
    avoid = [
        point['candidate_id']
        for point in insertion_points
        if point['recommendation'] == 'avoid'
    ]

    return {
        'enabled': True,
        'policy': 'filter_insertion_point_analysis_report_only',
        'summary': {
            'evaluated_insertion_point_count': len(insertion_points),
            'preferred_insertion_point': preferred[0] if preferred else '',
            'possible_insertion_points': possible,
            'avoid_insertion_points': avoid,
            'missing_inputs': metrics['missing_inputs'],
        },
        'metrics': metrics,
        'insertion_points': insertion_points,
        'warnings': warnings,
        'safest_next_experiment': _filter_insertion_next_experiment(preferred, metrics),
        'recommendation': {
            'safe_to_attempt_phase_2k': bool(preferred and not metrics['body_region_removed_count']),
            'reason': _filter_insertion_recommendation(preferred, warnings, metrics),
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


def _page_summary_block_count(pages: list) -> int:
    return sum(len(page.get('text_blocks', []) or []) for page in pages or [])


def _document_parse_removed_blocks(diff_report: dict) -> list:
    return [
        dict(block)
        for page in (diff_report or {}).get('removed_blocks_by_page', []) or []
        for block in page.get('blocks', []) or []
    ]


def _document_parse_removed_counts_by_role(removed_blocks: list) -> dict:
    counts = Counter(block.get('proposed_role', '') for block in removed_blocks or [])
    return dict(sorted(counts.items()))


def _document_parse_removed_counts_by_page(diff_report: dict) -> list:
    return [
        {
            'page_index': page.get('page_index'),
            'page_number': page.get('page_number'),
            'removed_count': page.get('removed_count', 0),
        }
        for page in (diff_report or {}).get('removed_blocks_by_page', []) or []
    ]


def _document_parse_removed_region_counts(removed_blocks: list) -> dict:
    counts = Counter(block.get('region', '') for block in removed_blocks or [])
    return dict(sorted(counts.items()))


def _document_parse_downstream_availability(
        original_pages: list,
        simulated_pages: list,
        removed_blocks: list) -> dict:
    original_body_count = sum(len(_body_blocks(page)) for page in original_pages or [])
    simulated_body_count = sum(len(_body_blocks(page)) for page in simulated_pages or [])
    removed_region_counts = _document_parse_removed_region_counts(removed_blocks)
    return {
        'margin_input_block_count': _page_summary_block_count(simulated_pages),
        'section_input_block_count': _page_summary_block_count(simulated_pages),
        'table_input_body_block_count': simulated_body_count,
        'paragraph_grouping_body_block_count': simulated_body_count,
        'body_region_blocks_preserved': simulated_body_count == original_body_count,
        'body_region_removed_count': removed_region_counts.get(REGION_BODY, 0),
        'top_region_removed_count': removed_region_counts.get(REGION_TOP, 0),
        'bottom_region_removed_count': removed_region_counts.get(REGION_BOTTOM, 0),
        'image_shape_data_mutated': False,
        'layout_placeholder_removed_count': sum(
            1 for block in removed_blocks or []
            if block.get('proposed_role') == ROLE_LAYOUT_PLACEHOLDER),
        'margin_section_table_risk_note': (
            'Simulation keeps body-region blocks available for margin, section, and table parsing.'
            if simulated_body_count == original_body_count else
            'Simulation would remove body-region blocks; do not integrate production filtering.'),
        'paragraph_grouping_risk_note': (
            'Line-level body summaries remain available for later paragraph grouping.'
            if simulated_body_count == original_body_count else
            'Paragraph grouping may be damaged because body-region blocks would be removed.'),
    }


def _document_parse_consistency_checks(
        original_block_count: int,
        would_remove_count: int,
        would_keep_count: int,
        body_region_removed_count: int,
        body_filtering_diff_report: dict,
        paragraph_integrity_report: dict,
        expected_removed_count: int,
        expected_kept_count: int,
        expected_body_region_removed_count: int) -> dict:
    diff_summary = (body_filtering_diff_report or {}).get('summary') or {}
    integrity_summary = (paragraph_integrity_report or {}).get('summary') or {}
    diff_expected_removed = diff_summary.get('would_remove_block_count')
    diff_expected_kept = diff_summary.get('kept_block_count')
    integrity_body_removed = integrity_summary.get('body_region_removed_count')
    return {
        'phase_2b_expected_removed_count': expected_removed_count,
        'phase_2b_expected_kept_count': expected_kept_count,
        'phase_2b_removed_match': would_remove_count == expected_removed_count,
        'phase_2b_kept_match': would_keep_count == expected_kept_count,
        'phase_2b_report_removed_count': diff_expected_removed,
        'phase_2b_report_kept_count': diff_expected_kept,
        'phase_2b_report_removed_match': (
            diff_expected_removed is None or diff_expected_removed == would_remove_count),
        'phase_2b_report_kept_match': (
            diff_expected_kept is None or diff_expected_kept == would_keep_count),
        'phase_2c_expected_body_region_removed_count': expected_body_region_removed_count,
        'phase_2c_body_region_removed_count': body_region_removed_count,
        'phase_2c_body_region_removed_match': (
            body_region_removed_count == expected_body_region_removed_count),
        'phase_2c_report_body_region_removed_count': integrity_body_removed,
        'phase_2c_report_body_region_removed_match': (
            integrity_body_removed is None or integrity_body_removed == body_region_removed_count),
        'original_block_count': original_block_count,
    }


def _document_parse_simulation_warnings(
        review_decisions,
        filtering_report: dict,
        safety: dict,
        consistency_checks: dict,
        region_counts: dict) -> list:
    warnings = []
    decision_map = _review_decision_map(review_decisions or {})
    if not decision_map:
        warnings.append({
            'type': 'missing_review_decisions',
            'message': 'No explicit review decisions were provided; no reviewed filtering should be applied.',
        })
    if not filtering_report.get('approved_candidate_count', 0):
        warnings.append({
            'type': 'no_approved_candidates',
            'message': 'No candidates have explicit approve_exclude decisions.',
        })
    if region_counts.get(REGION_BODY, 0):
        warnings.append({
            'type': 'body_region_removed',
            'message': 'Simulation would remove body-region blocks.',
            'count': region_counts.get(REGION_BODY, 0),
        })
    if safety.get('rejected_removed_candidate_count', 0):
        warnings.append({
            'type': 'rejected_candidate_removed',
            'message': 'Simulation would remove rejected candidates.',
            'count': safety.get('rejected_removed_candidate_count', 0),
        })
    if safety.get('unsure_removed_candidate_count', 0):
        warnings.append({
            'type': 'unsure_candidate_removed',
            'message': 'Simulation would remove unsure candidates.',
            'count': safety.get('unsure_removed_candidate_count', 0),
        })
    if safety.get('layout_placeholder_removed_candidate_count', 0):
        warnings.append({
            'type': 'layout_placeholder_removed',
            'message': 'Simulation would remove layout-placeholder candidates.',
            'count': safety.get('layout_placeholder_removed_candidate_count', 0),
        })
    for key in (
            'phase_2b_removed_match',
            'phase_2b_kept_match',
            'phase_2b_report_removed_match',
            'phase_2b_report_kept_match',
            'phase_2c_body_region_removed_match',
            'phase_2c_report_body_region_removed_match'):
        if not consistency_checks.get(key, True):
            warnings.append({
                'type': 'consistency_check_failed',
                'check': key,
                'message': f'{key} did not match expected Phase 2B/2C counts.',
            })
    return warnings


def _document_parse_safe_for_phase_2l(warnings: list, region_counts: dict) -> bool:
    blocking_warning_types = {
        'body_region_removed',
        'rejected_candidate_removed',
        'unsure_candidate_removed',
        'layout_placeholder_removed',
        'consistency_check_failed',
        'missing_review_decisions',
        'no_approved_candidates',
    }
    warning_types = {warning.get('type') for warning in warnings or []}
    return not warning_types.intersection(blocking_warning_types) and not region_counts.get(REGION_BODY, 0)


def _document_parse_recommendation(warnings: list, region_counts: dict) -> str:
    if _document_parse_safe_for_phase_2l(warnings, region_counts):
        return 'Document-parse simulation matches reviewed filtering counts and preserves body-region blocks; Phase 2L can remain opt-in and local-only.'
    return 'Do not connect production filtering yet; resolve simulation warnings before Phase 2L.'


def _document_parse_hook_phase_2k_consistency(
        simulation: dict,
        phase_2k_simulation_report: dict = None) -> dict:
    summary = (simulation or {}).get('summary') or {}
    if phase_2k_simulation_report:
        phase_summary = phase_2k_simulation_report.get('summary') or {}
        phase_removed = phase_summary.get(
            'would_remove_block_count',
            phase_summary.get('simulated_removed_count'))
        phase_kept = phase_summary.get(
            'would_keep_block_count',
            phase_summary.get('simulated_kept_count'))
        return {
            'phase_2k_report_available': True,
            'phase_2k_would_remove_count': phase_removed,
            'phase_2k_would_keep_count': phase_kept,
            'would_remove_count_matches_phase_2k': (
                phase_removed is None or
                summary.get('would_remove_block_count') == phase_removed),
            'would_keep_count_matches_phase_2k': (
                phase_kept is None or
                summary.get('would_keep_block_count') == phase_kept),
            'reason': 'Compared hook dry-run counts with the supplied Phase 2K simulation report.',
        }

    checks = (simulation or {}).get('consistency_checks') or {}
    return {
        'phase_2k_report_available': False,
        'would_remove_count_matches_phase_2k': checks.get('phase_2b_removed_match', False),
        'would_keep_count_matches_phase_2k': checks.get('phase_2b_kept_match', False),
        'body_region_removed_count_matches_phase_2k': checks.get(
            'phase_2c_body_region_removed_match',
            False),
        'reason': 'No Phase 2K report was supplied; using expected Phase 2B/2C count consistency.',
    }


def _document_parse_hook_recommendation(
        enabled: bool,
        warnings: list,
        summary: dict) -> tuple:
    if not enabled:
        return (
            False,
            'Hook scaffold is disabled; no production integration should be attempted.')

    blocking_counts = (
        summary.get('body_region_removed_count', 0),
        summary.get('rejected_removed_count', 0),
        summary.get('unsure_removed_count', 0),
        summary.get('layout_placeholder_removed_count', 0),
        summary.get('production_removed_count', 0),
    )
    if warnings or any(blocking_counts):
        return (
            False,
            'Resolve hook safety warnings before any Phase 2M production experiment.')

    return (
        True,
        'Hook scaffold is dry-run/report-only and preserves production objects; Phase 2M can remain opt-in and guarded.')


def _raw_mapping_empty_summary(expected_would_remove_count: int = None) -> dict:
    return {
        'approved_candidate_count': 0,
        'expected_would_remove_count': expected_would_remove_count or 0,
        'mapped_raw_object_count': 0,
        'exact_match_count': 0,
        'fuzzy_match_count': 0,
        'ambiguous_match_count': 0,
        'missing_match_count': 0,
        'unsafe_match_count': 0,
        'body_region_matched_for_removal_count': 0,
        'rejected_unsure_layout_placeholder_matched_for_removal_count': 0,
        'all_expected_blocks_mapped_once': False,
    }


def _raw_mapping_expected_blocks(
        page_summaries: list,
        dry_run_report: dict,
        review_decisions) -> list:
    decision_map = _review_decision_map(review_decisions or {})
    approved, _ = _reviewed_exclusion_candidates(
        _dry_run_candidates(dry_run_report),
        decision_map)
    approved_by_fingerprint = {
        item.get('fingerprint'): item
        for item in approved
        if item.get('fingerprint')
    }
    expected_blocks = []
    for page in page_summaries or []:
        page_index = page.get('page_index')
        for block in page.get('text_blocks', []) or []:
            candidate = approved_by_fingerprint.get(block.get('fingerprint'))
            if not candidate or not _block_matches_reviewed_candidate(block, page_index, candidate):
                continue
            expected_blocks.append(_raw_mapping_expected_block(page_index, block, candidate))
    return expected_blocks


def _raw_mapping_expected_block(page_index, block: dict, candidate: dict) -> dict:
    return {
        'page_index': page_index,
        'page_number': _human_page_number(page_index),
        'block_index': block.get('block_index'),
        'fingerprint': block.get('fingerprint', ''),
        'normalized_text': block.get('normalized_text') or _comparison_text(block.get('text', '')),
        'region': block.get('region', ''),
        'bbox': _json_bbox(block.get('bbox')),
        'candidate_id': candidate.get('candidate_id', ''),
        'proposed_role': candidate.get('proposed_role', ''),
        'manual_decision': candidate.get('manual_decision', ''),
        'text_preview': _preview_text(block, max_length=100),
    }


def _raw_object_records(raw_object_pages: list) -> list:
    records = []
    for fallback_page_index, page in enumerate(raw_object_pages or []):
        page_index = page.get('page_index', page.get('id', fallback_page_index))
        page_height = page.get('height', page.get('page_height', 0))
        objects = (
            page.get('raw_objects') or
            page.get('objects') or
            page.get('blocks') or
            page.get('text_blocks') or
            [])
        for fallback_index, raw_object in enumerate(objects):
            record = _raw_object_record(
                page_index,
                page_height,
                raw_object,
                fallback_index)
            if record:
                records.append(record)
    return records


def _raw_object_record(page_index, page_height, raw_object: dict, fallback_index: int) -> dict:
    text = normalize_text(raw_object.get('text', ''))
    if not text:
        return {}

    bbox = _json_bbox(raw_object.get('bbox'))
    region = raw_object.get('region') or classify_y_band(bbox, page_height)
    fingerprint = raw_object.get('fingerprint') or make_text_fingerprint(
        text,
        region,
        style=None).get('key')
    raw_object_id = raw_object.get(
        'raw_object_id',
        raw_object.get('object_id', raw_object.get('block_index', fallback_index)))
    return {
        'page_index': page_index,
        'page_number': _human_page_number(page_index),
        'raw_object_id': raw_object_id,
        'object_index': raw_object.get('object_index', fallback_index),
        'block_index': raw_object.get('block_index', fallback_index),
        'object_type': raw_object.get('object_type', ''),
        'text': text,
        'normalized_text': _comparison_text(text),
        'fingerprint': fingerprint,
        'region': region,
        'bbox': bbox,
        'placeholder_kind': raw_object.get('placeholder_kind') or _placeholder_kind(text),
        'text_preview': _preview_text(raw_object, max_length=100),
    }


def _raw_mapping_for_expected_block(
        expected: dict,
        raw_records: list,
        blocked_fingerprints: set,
        exact_bbox_tolerance: float,
        fuzzy_bbox_tolerance: float) -> dict:
    candidates = []
    for raw_record in raw_records or []:
        candidate = _raw_mapping_candidate(
            expected,
            raw_record,
            blocked_fingerprints,
            exact_bbox_tolerance,
            fuzzy_bbox_tolerance)
        if candidate:
            candidates.append(candidate)

    safe_candidates = [
        candidate for candidate in candidates
        if not candidate.get('unsafe_signals')
    ]
    if not safe_candidates:
        status = 'missing_match'
        selected = []
    elif len(safe_candidates) == 1:
        status = safe_candidates[0]['match_quality']
        selected = safe_candidates
    else:
        status = 'ambiguous_match'
        selected = safe_candidates

    unsafe_candidates = [
        candidate for candidate in candidates
        if candidate.get('unsafe_signals')
    ]
    return {
        'page_index': expected.get('page_index'),
        'page_number': expected.get('page_number'),
        'block_index': expected.get('block_index'),
        'candidate_id': expected.get('candidate_id', ''),
        'fingerprint': expected.get('fingerprint', ''),
        'proposed_role': expected.get('proposed_role', ''),
        'region': expected.get('region', ''),
        'expected_bbox': expected.get('bbox', []),
        'expected_preview': expected.get('text_preview', ''),
        'mapping_status': status,
        'safe_match_count': len(safe_candidates),
        'unsafe_match_count': len(unsafe_candidates),
        'selected_raw_objects': selected,
        'candidate_raw_objects': candidates,
        'reason': _raw_mapping_reason(status, safe_candidates, unsafe_candidates),
    }


def _raw_mapping_candidate(
        expected: dict,
        raw_record: dict,
        blocked_fingerprints: set,
        exact_bbox_tolerance: float,
        fuzzy_bbox_tolerance: float) -> dict:
    if expected.get('page_index') != raw_record.get('page_index'):
        return {}

    text_match = (
        expected.get('fingerprint') == raw_record.get('fingerprint') or
        expected.get('normalized_text') == raw_record.get('normalized_text'))
    if not text_match:
        return {}

    region_match = expected.get('region') == raw_record.get('region')
    bbox_delta = _bbox_max_delta(expected.get('bbox'), raw_record.get('bbox'))
    bbox_overlap = _bbox_overlap_ratio(expected.get('bbox'), raw_record.get('bbox'))
    if not region_match and bbox_delta > fuzzy_bbox_tolerance:
        return {}
    if bbox_delta > fuzzy_bbox_tolerance and bbox_overlap < 0.7:
        return {}

    unsafe = []
    positive = []
    if region_match:
        positive.append('region_match')
    else:
        unsafe.append('region_mismatch')
    if raw_record.get('region') == REGION_BODY:
        unsafe.append('body_region_raw_object')
    if raw_record.get('fingerprint') in blocked_fingerprints:
        unsafe.append('blocked_review_decision_fingerprint')
    if raw_record.get('placeholder_kind') == 'image':
        unsafe.append('layout_placeholder_raw_object')

    if bbox_delta <= exact_bbox_tolerance:
        quality = 'exact_match'
        positive.append('bbox_exact_or_near_exact')
    else:
        quality = 'fuzzy_match'
        positive.append('bbox_fuzzy_match')
    if bbox_overlap:
        positive.append('bbox_overlap')

    return {
        'raw_object_id': raw_record.get('raw_object_id'),
        'object_index': raw_record.get('object_index'),
        'block_index': raw_record.get('block_index'),
        'object_type': raw_record.get('object_type', ''),
        'fingerprint': raw_record.get('fingerprint', ''),
        'region': raw_record.get('region', ''),
        'bbox': raw_record.get('bbox', []),
        'match_quality': quality,
        'bbox_max_delta': round(bbox_delta, 2),
        'bbox_overlap_ratio': round(bbox_overlap, 3),
        'placeholder_kind': raw_record.get('placeholder_kind', ''),
        'positive_signals': positive,
        'unsafe_signals': unsafe,
        'text_preview': raw_record.get('text_preview', ''),
    }


def _raw_mapping_summary(
        mappings: list,
        filtering_report: dict,
        expected_would_remove_count: int = None) -> dict:
    exact_count = sum(1 for item in mappings if item.get('mapping_status') == 'exact_match')
    fuzzy_count = sum(1 for item in mappings if item.get('mapping_status') == 'fuzzy_match')
    ambiguous_count = sum(1 for item in mappings if item.get('mapping_status') == 'ambiguous_match')
    missing_count = sum(1 for item in mappings if item.get('mapping_status') == 'missing_match')
    unsafe_count = sum(item.get('unsafe_match_count', 0) for item in mappings)
    selected = [
        raw_object
        for item in mappings
        if item.get('mapping_status') in {'exact_match', 'fuzzy_match'}
        for raw_object in item.get('selected_raw_objects', []) or []
    ]
    body_matched_count = sum(1 for item in selected if item.get('region') == REGION_BODY)
    blocked_matched_count = sum(
        1 for item in selected
        if (
            'blocked_review_decision_fingerprint' in item.get('unsafe_signals', []) or
            'layout_placeholder_raw_object' in item.get('unsafe_signals', [])))
    expected_count = len(mappings)
    expected_would_remove_count = (
        expected_would_remove_count
        if expected_would_remove_count is not None else
        expected_count)
    mapped_count = exact_count + fuzzy_count
    return {
        'approved_candidate_count': filtering_report.get('approved_candidate_count', 0),
        'blocked_candidate_count': filtering_report.get('blocked_candidate_count', 0),
        'expected_would_remove_count': expected_would_remove_count,
        'observed_would_remove_count': expected_count,
        'mapped_raw_object_count': mapped_count,
        'exact_match_count': exact_count,
        'fuzzy_match_count': fuzzy_count,
        'ambiguous_match_count': ambiguous_count,
        'missing_match_count': missing_count,
        'unsafe_match_count': unsafe_count,
        'body_region_matched_for_removal_count': body_matched_count,
        'rejected_unsure_layout_placeholder_matched_for_removal_count': blocked_matched_count,
        'all_expected_blocks_mapped_once': (
            mapped_count == expected_count and
            not ambiguous_count and
            not missing_count and
            not unsafe_count and
            not body_matched_count and
            not blocked_matched_count),
    }


def _raw_mapping_quality_by_page(mappings: list) -> list:
    grouped = defaultdict(list)
    for mapping in mappings or []:
        grouped[mapping.get('page_index')].append(mapping)
    rows = []
    for page_index, items in sorted(grouped.items()):
        rows.append(_raw_mapping_quality_row(
            {'page_index': page_index, 'page_number': _human_page_number(page_index)},
            items))
    return rows


def _raw_mapping_quality_by_role(mappings: list) -> dict:
    grouped = defaultdict(list)
    for mapping in mappings or []:
        grouped[mapping.get('proposed_role', '')].append(mapping)
    return {
        role: _raw_mapping_quality_counts(items)
        for role, items in sorted(grouped.items())
    }


def _raw_mapping_quality_row(base: dict, mappings: list) -> dict:
    row = dict(base)
    row.update(_raw_mapping_quality_counts(mappings))
    return row


def _raw_mapping_quality_counts(mappings: list) -> dict:
    counts = Counter(item.get('mapping_status') for item in mappings or [])
    return {
        'expected_count': len(mappings or []),
        'mapped_count': counts.get('exact_match', 0) + counts.get('fuzzy_match', 0),
        'exact_match_count': counts.get('exact_match', 0),
        'fuzzy_match_count': counts.get('fuzzy_match', 0),
        'ambiguous_match_count': counts.get('ambiguous_match', 0),
        'missing_match_count': counts.get('missing_match', 0),
        'unsafe_match_count': sum(item.get('unsafe_match_count', 0) for item in mappings or []),
    }


def _raw_mapping_warnings(summary: dict, mappings: list) -> list:
    warnings = []
    if summary.get('expected_would_remove_count') != summary.get('observed_would_remove_count'):
        warnings.append({
            'type': 'expected_would_remove_count_mismatch',
            'expected': summary.get('expected_would_remove_count'),
            'observed': summary.get('observed_would_remove_count'),
        })
    for key, warning_type in (
            ('missing_match_count', 'missing_raw_object_match'),
            ('ambiguous_match_count', 'ambiguous_raw_object_match'),
            ('unsafe_match_count', 'unsafe_raw_object_match'),
            ('body_region_matched_for_removal_count', 'body_region_raw_object_matched'),
            ('rejected_unsure_layout_placeholder_matched_for_removal_count',
             'blocked_candidate_raw_object_matched')):
        count = summary.get(key, 0)
        if count:
            warnings.append({
                'type': warning_type,
                'count': count,
            })
    if not summary.get('approved_candidate_count', 0):
        warnings.append({
            'type': 'no_approved_candidates',
            'message': 'No approved candidates were available for raw-object mapping.',
        })
    return warnings


def _raw_mapping_safe_for_phase_2n(summary: dict, warnings: list) -> bool:
    return bool(summary.get('all_expected_blocks_mapped_once')) and not warnings


def _raw_mapping_recommendation(summary: dict, warnings: list) -> str:
    if _raw_mapping_safe_for_phase_2n(summary, warnings):
        return 'Every reviewed would-remove summary block maps to exactly one safe raw-page object; Phase 2N can remain opt-in and copied-object only.'
    return 'Do not apply production filtering yet; resolve raw-object mapping warnings first.'


def _copied_apply_disabled_summary(
        original_count: int,
        expected_mapping_count: int = None) -> dict:
    return {
        'original_raw_block_count': original_count,
        'copied_filtered_block_count': original_count,
        'removed_copied_block_count': 0,
        'expected_mapping_count': expected_mapping_count or 0,
        'body_region_removed_count': 0,
        'rejected_unsure_layout_placeholder_removed_count': 0,
        'original_objects_mutated': False,
        'copied_objects_filtered': False,
    }


def _copied_apply_removal_plan(mapping_report: dict) -> list:
    plan = []
    for mapping in (mapping_report or {}).get('mappings', []) or []:
        if mapping.get('mapping_status') not in {'exact_match', 'fuzzy_match'}:
            continue
        selected = mapping.get('selected_raw_objects', []) or []
        if len(selected) != 1:
            continue
        raw_object = selected[0]
        if raw_object.get('unsafe_signals'):
            continue
        plan.append({
            'page_index': mapping.get('page_index'),
            'page_number': mapping.get('page_number'),
            'raw_object_id': raw_object.get('raw_object_id'),
            'block_index': raw_object.get('block_index'),
            'object_index': raw_object.get('object_index'),
            'fingerprint': mapping.get('fingerprint', ''),
            'candidate_id': mapping.get('candidate_id', ''),
            'proposed_role': mapping.get('proposed_role', ''),
            'region': raw_object.get('region', mapping.get('region', '')),
            'mapping_status': mapping.get('mapping_status'),
            'text_preview': raw_object.get('text_preview', ''),
        })
    return plan


def _copied_apply_filter_pages(raw_object_pages: list, removal_plan: list) -> tuple:
    remove_by_key = {
        (item.get('page_index'), item.get('raw_object_id')): item
        for item in removal_plan or []
    }
    seen_keys = set()
    filtered_pages = []
    removed_by_page = []
    for page in raw_object_pages or []:
        page_index = page.get('page_index')
        kept_objects = []
        removed_objects = []
        for raw_object in page.get('raw_objects', []) or []:
            key = (page_index, raw_object.get('raw_object_id'))
            plan_item = remove_by_key.get(key)
            if plan_item:
                removed = dict(raw_object)
                removed.update({
                    'candidate_id': plan_item.get('candidate_id', ''),
                    'proposed_role': plan_item.get('proposed_role', ''),
                    'mapping_status': plan_item.get('mapping_status', ''),
                    'removal_reason': 'approved_reviewed_raw_object_mapping',
                    'text_preview': plan_item.get('text_preview', ''),
                })
                removed_objects.append(removed)
                seen_keys.add(key)
            else:
                kept_objects.append(dict(raw_object))

        filtered_page = dict(page)
        filtered_page['raw_objects'] = kept_objects
        filtered_page['raw_object_count'] = len(kept_objects)
        filtered_pages.append(filtered_page)
        removed_by_page.append({
            'page_index': page_index,
            'page_number': page.get('page_number', _human_page_number(page_index)),
            'removed_count': len(removed_objects),
            'objects': removed_objects,
        })

    missing_apply_targets = [
        item for item in removal_plan or []
        if (item.get('page_index'), item.get('raw_object_id')) not in seen_keys
    ]
    return filtered_pages, removed_by_page, missing_apply_targets


def _copied_apply_summary(
        original_pages: list,
        filtered_pages: list,
        removed_objects: list,
        mapping_report: dict,
        consistency: dict) -> dict:
    original_count = _raw_object_page_count(original_pages)
    filtered_count = _raw_object_page_count(filtered_pages)
    mapping_summary = (mapping_report or {}).get('summary') or {}
    return {
        'original_raw_block_count': original_count,
        'copied_filtered_block_count': filtered_count,
        'removed_copied_block_count': len(removed_objects),
        'approved_candidate_count': mapping_summary.get('approved_candidate_count', 0),
        'blocked_candidate_count': mapping_summary.get('blocked_candidate_count', 0),
        'phase_2m_mapped_raw_object_count': mapping_summary.get('mapped_raw_object_count', 0),
        'expected_mapping_count': consistency.get('expected_mapping_count', 0),
        'body_region_removed_count': sum(
            1 for item in removed_objects or []
            if item.get('region') == REGION_BODY),
        'rejected_unsure_layout_placeholder_removed_count': sum(
            1 for item in removed_objects or []
            if (
                item.get('proposed_role') == ROLE_LAYOUT_PLACEHOLDER or
                item.get('placeholder_kind') == 'image' or
                'blocked_review_decision_fingerprint' in item.get('unsafe_signals', []))),
        'original_objects_mutated': False,
        'copied_objects_filtered': bool(removed_objects),
        'removed_count_matches_phase_2m': consistency.get('removed_count_matches_phase_2m', False),
    }


def _copied_apply_phase_2m_consistency(
        mapping_report: dict,
        removed_count: int,
        expected_mapping_count: int = None) -> dict:
    mapping_summary = (mapping_report or {}).get('summary') or {}
    mapped_count = mapping_summary.get('mapped_raw_object_count', 0)
    expected_mapping_count = (
        expected_mapping_count
        if expected_mapping_count is not None else
        mapped_count)
    return {
        'phase_2m_mapped_raw_object_count': mapped_count,
        'expected_mapping_count': expected_mapping_count,
        'removed_count': removed_count,
        'removed_count_matches_phase_2m': removed_count == mapped_count,
        'expected_mapping_count_matches_phase_2m': expected_mapping_count == mapped_count,
    }


def _copied_apply_removed_counts_by_role(removed_objects: list) -> dict:
    counts = Counter(item.get('proposed_role', '') for item in removed_objects or [])
    return dict(sorted(counts.items()))


def _copied_apply_removed_counts_by_page(removed_by_page: list) -> list:
    return [
        {
            'page_index': page.get('page_index'),
            'page_number': page.get('page_number'),
            'removed_count': page.get('removed_count', 0),
        }
        for page in removed_by_page or []
    ]


def _copied_apply_downstream_inputs(
        original_pages: list,
        filtered_pages: list,
        removed_objects: list) -> dict:
    original_body_count = _raw_object_region_count(original_pages, REGION_BODY)
    filtered_body_count = _raw_object_region_count(filtered_pages, REGION_BODY)
    original_placeholder_count = _raw_object_placeholder_count(original_pages)
    filtered_placeholder_count = _raw_object_placeholder_count(filtered_pages)
    return {
        'margin_input_count_before': _raw_object_page_count(original_pages),
        'margin_input_count_after': _raw_object_page_count(filtered_pages),
        'section_input_count_before': _raw_object_page_count(original_pages),
        'section_input_count_after': _raw_object_page_count(filtered_pages),
        'body_block_count_before': original_body_count,
        'body_block_count_after': filtered_body_count,
        'image_shape_placeholder_count_before': original_placeholder_count,
        'image_shape_placeholder_count_after': filtered_placeholder_count,
        'table_risk_note': (
            'Copied filtering preserves body-region raw objects for table detection.'
            if filtered_body_count == original_body_count else
            'Copied filtering removed body-region raw objects; table detection may be damaged.'),
        'paragraph_grouping_risk_note': (
            'Copied filtering preserves body-region line/block objects for paragraph grouping.'
            if filtered_body_count == original_body_count else
            'Copied filtering removed body-region line/block objects; paragraph grouping may be damaged.'),
        'removed_top_bottom_count': sum(
            1 for item in removed_objects or []
            if item.get('region') in {REGION_TOP, REGION_BOTTOM}),
    }


def _copied_apply_warnings(
        summary: dict,
        mapping_report: dict,
        consistency: dict,
        missing_apply_targets: list) -> list:
    warnings = []
    for warning in (mapping_report or {}).get('safety_warnings', []) or []:
        warnings.append({
            'type': f'mapping_{warning.get("type", "warning")}',
            'message': warning.get('message', ''),
            'count': warning.get('count'),
        })
    if missing_apply_targets:
        warnings.append({
            'type': 'missing_copied_apply_target',
            'count': len(missing_apply_targets),
        })
    if summary.get('body_region_removed_count', 0):
        warnings.append({
            'type': 'body_region_removed_from_copy',
            'count': summary.get('body_region_removed_count'),
        })
    if summary.get('rejected_unsure_layout_placeholder_removed_count', 0):
        warnings.append({
            'type': 'blocked_or_placeholder_removed_from_copy',
            'count': summary.get('rejected_unsure_layout_placeholder_removed_count'),
        })
    if not consistency.get('removed_count_matches_phase_2m', False):
        warnings.append({
            'type': 'removed_count_mismatch_phase_2m',
            'expected': consistency.get('phase_2m_mapped_raw_object_count'),
            'observed': consistency.get('removed_count'),
        })
    if not consistency.get('expected_mapping_count_matches_phase_2m', True):
        warnings.append({
            'type': 'expected_mapping_count_mismatch_phase_2m',
            'expected': consistency.get('expected_mapping_count'),
            'observed': consistency.get('phase_2m_mapped_raw_object_count'),
        })
    return warnings


def _copied_apply_safe_for_phase_2o(summary: dict, warnings: list) -> bool:
    return (
        bool(summary.get('copied_objects_filtered')) and
        bool(summary.get('removed_count_matches_phase_2m')) and
        not warnings and
        not summary.get('body_region_removed_count', 0) and
        not summary.get('rejected_unsure_layout_placeholder_removed_count', 0) and
        not summary.get('original_objects_mutated', False))


def _copied_apply_recommendation(summary: dict, warnings: list) -> str:
    if _copied_apply_safe_for_phase_2o(summary, warnings):
        return 'Copied raw-page filtering removed only validated reviewed objects; Phase 2O can remain opt-in and non-default.'
    return 'Do not apply production filtering yet; resolve copied-apply warnings first.'


def _copy_raw_object_pages(raw_object_pages: list) -> list:
    copied = []
    for page in raw_object_pages or []:
        copied_page = dict(page)
        page_height = page.get('height', page.get('page_height', 0))
        copied_page['raw_objects'] = [
            _copy_raw_object(raw_object, page_height)
            for raw_object in page.get('raw_objects', []) or []
        ]
        copied.append(copied_page)
    return copied


def _copy_raw_object(raw_object: dict, page_height: float) -> dict:
    copied = dict(raw_object)
    text = normalize_text(copied.get('text', ''))
    bbox = _json_bbox(copied.get('bbox'))
    region = copied.get('region') or classify_y_band(bbox, page_height)
    copied['text'] = text
    copied['bbox'] = bbox
    copied['region'] = region
    copied.setdefault('normalized_text', _comparison_text(text))
    copied.setdefault('fingerprint', make_text_fingerprint(text, region, style=None).get('key'))
    copied.setdefault('placeholder_kind', _placeholder_kind(text))
    return copied


def _raw_object_page_count(raw_object_pages: list) -> int:
    return sum(len(page.get('raw_objects', []) or []) for page in raw_object_pages or [])


def _raw_object_region_count(raw_object_pages: list, region: str) -> int:
    return sum(
        1
        for page in raw_object_pages or []
        for raw_object in page.get('raw_objects', []) or []
        if raw_object.get('region') == region)


def _raw_object_placeholder_count(raw_object_pages: list) -> int:
    return sum(
        1
        for page in raw_object_pages or []
        for raw_object in page.get('raw_objects', []) or []
        if (
            raw_object.get('placeholder_kind') == 'image' or
            _placeholder_kind(raw_object.get('text', '')) == 'image'))


def _raw_mapping_reason(status: str, safe_candidates: list, unsafe_candidates: list) -> str:
    if status == 'exact_match':
        return 'Exactly one raw object matched by page, text fingerprint, region, and near-identical bbox.'
    if status == 'fuzzy_match':
        return 'Exactly one raw object matched by page, text fingerprint, region, and fuzzy bbox proximity.'
    if status == 'ambiguous_match':
        return f'{len(safe_candidates)} raw objects matched; manual/raw-object disambiguation is required.'
    if unsafe_candidates:
        return 'Only unsafe raw-object matches were found.'
    return 'No matching raw object was found for this reviewed summary block.'


def _bbox_max_delta(first, second) -> float:
    first = _json_bbox(first)
    second = _json_bbox(second)
    return max(abs(float(a) - float(b)) for a, b in zip(first, second))


def _bbox_overlap_ratio(first, second) -> float:
    first = _json_bbox(first)
    second = _json_bbox(second)
    width = min(first[2], second[2]) - max(first[0], second[0])
    height = min(first[3], second[3]) - max(first[1], second[1])
    if width <= 0 or height <= 0:
        return 0.0
    intersection = width * height
    first_area = max((first[2] - first[0]) * (first[3] - first[1]), 0.0)
    second_area = max((second[2] - second[0]) * (second[3] - second[1]), 0.0)
    denominator = min(first_area, second_area)
    return intersection / denominator if denominator else 0.0


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
    groups, gap_warnings, split_boundaries, ignored_split_boundaries = _estimate_paragraph_groups(
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
        'ignored_split_boundaries': ignored_split_boundaries,
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
    ignored_split_boundaries = []
    if not body_blocks:
        return groups, warnings, split_boundaries, ignored_split_boundaries

    sorted_blocks = sorted(
        [dict(block) for block in body_blocks],
        key=lambda block: block.get('block_index', 0))
    line_units = _body_line_units(sorted_blocks)
    if not line_units:
        return groups, warnings, split_boundaries, ignored_split_boundaries

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
        elif boundary_signals.get('ignored_split_reasons'):
            ignored_split_boundaries.append(_paragraph_ignored_split_boundary(
                page,
                len(ignored_split_boundaries),
                previous,
                unit,
                boundary_signals))
            current_units.append(unit)
        else:
            current_units.append(unit)

    groups.append(_estimated_paragraph_group(
        page,
        len(groups),
        current_units,
        break_before_reasons,
        short_fragment_length))
    return groups, warnings, split_boundaries, ignored_split_boundaries


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
    current_width_ratio = current_width / body_width
    current_left_gap_ratio = max(0.0, float(current_bbox[0]) - float(metrics.get('min_left', 0.0))) / body_width
    width_delta_ratio = abs(previous_width - current_width) / max(previous_width, current_width, 1.0)
    significant_style_change = _significant_style_change(previous, current)
    sentence_end_with_trailing_space = (
        previous_sentence_end and
        right_gap_ratio >= 0.12 and
        previous_width_ratio <= 0.88 and
        not previous_hyphenated)

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
        'current_width_ratio': round(current_width_ratio, 3),
        'previous_right_gap_ratio': round(right_gap_ratio, 3),
        'current_left_gap_ratio': round(current_left_gap_ratio, 3),
        'sentence_end_with_trailing_space': sentence_end_with_trailing_space,
        'ignored_split_reasons': [],
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

    if sentence_end_with_trailing_space:
        reasons.append('sentence_end_with_trailing_space')

    indentation_candidate = abs(left_delta) > indent_tolerance and not previous_hyphenated
    if indentation_candidate:
        if _indentation_supported_by_strong_break_signal(
                left_delta,
                gap_ratio,
                max_line_gap_ratio,
                previous_sentence_end,
                sentence_end_with_trailing_space,
                current_left_gap_ratio,
                current_width_ratio,
                reasons):
            reasons.append('indentation_change')
        else:
            signals['ignored_split_reasons'].append('weak_indentation_change')

    if reasons:
        warning = None

    return sorted(set(reasons)), warning, signals


def _indentation_supported_by_strong_break_signal(
        left_delta: float,
        gap_ratio: float,
        max_line_gap_ratio: float,
        previous_sentence_end: bool,
        sentence_end_with_trailing_space: bool,
        current_left_gap_ratio: float,
        current_width_ratio: float,
        reasons: list) -> bool:
    if any(reason in reasons for reason in (
            'heading_like',
            'previous_heading_like',
            'list_marker',
            'previous_list_item',
            'large_vertical_gap',
            'style_change')):
        return True

    if sentence_end_with_trailing_space:
        return True

    clear_first_line_indent = (
        previous_sentence_end and
        left_delta > 0.0 and
        current_left_gap_ratio >= 0.08 and
        current_width_ratio <= 0.92)
    if clear_first_line_indent:
        return True

    return previous_sentence_end and gap_ratio > max_line_gap_ratio


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
        'previous_bbox': list(previous.get('bbox', []) or []),
        'next_bbox': list(current.get('bbox', []) or []),
        'previous_left': _bbox_value(previous.get('bbox'), 0),
        'previous_right': _bbox_value(previous.get('bbox'), 2),
        'next_left': _bbox_value(current.get('bbox'), 0),
        'next_right': _bbox_value(current.get('bbox'), 2),
        'reasons': list(reasons or []),
        'signals': dict(signals or {}),
        'previous_text_preview': _preview_text(previous, max_length=100),
        'next_text_preview': _preview_text(current, max_length=100),
    }


def _paragraph_ignored_split_boundary(
        page: dict,
        boundary_index: int,
        previous: dict,
        current: dict,
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
        'previous_bbox': list(previous.get('bbox', []) or []),
        'next_bbox': list(current.get('bbox', []) or []),
        'ignored_reasons': list(signals.get('ignored_split_reasons', []) or []),
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


def _indentation_boundary_comparison(
        page: dict,
        boundary: dict,
        new_paragraph_free_space_ratio: float,
        small_indent_tolerance: float) -> dict:
    signals = boundary.get('signals', {}) or {}
    reasons = boundary.get('reasons', []) or []
    classification = _classify_indentation_boundary(
        signals,
        reasons,
        new_paragraph_free_space_ratio,
        small_indent_tolerance)
    previous_bbox = boundary.get('previous_bbox') or []
    next_bbox = boundary.get('next_bbox') or []
    return {
        'page_index': boundary.get('page_index', page.get('page_index')),
        'page_number': boundary.get('page_number', page.get('page_number')),
        'boundary_index': boundary.get('boundary_index'),
        'previous_text_preview': boundary.get('previous_text_preview', ''),
        'next_text_preview': boundary.get('next_text_preview', ''),
        'previous_bbox': previous_bbox,
        'next_bbox': next_bbox,
        'previous_left': boundary.get('previous_left', _bbox_value(previous_bbox, 0)),
        'previous_right': boundary.get('previous_right', _bbox_value(previous_bbox, 2)),
        'next_left': boundary.get('next_left', _bbox_value(next_bbox, 0)),
        'next_right': boundary.get('next_right', _bbox_value(next_bbox, 2)),
        'indentation_delta': signals.get('left_delta'),
        'line_width_signal': {
            'width_delta_ratio': signals.get('width_delta_ratio'),
            'width_similar': signals.get('width_similar'),
            'previous_width_ratio': signals.get('previous_width_ratio'),
            'previous_right_gap_ratio': signals.get('previous_right_gap_ratio'),
        },
        'sentence_ending_signal': {
            'previous_sentence_end': signals.get('previous_sentence_end'),
            'previous_hyphenated': signals.get('previous_hyphenated'),
        },
        'style_signal': {
            'style_change': signals.get('style_change'),
            'significant_style_change': signals.get('significant_style_change'),
        },
        'estimator_split_reasons': list(reasons),
        'production_like_expected_behavior': classification['production_like_expected_behavior'],
        'recommendation': classification['recommendation'],
        'production_keep_reason': classification.get('production_keep_reason', ''),
        'reason': classification['reason'],
    }


def _classify_indentation_boundary(
        signals: dict,
        reasons: list,
        new_paragraph_free_space_ratio: float,
        small_indent_tolerance: float) -> dict:
    if signals.get('insufficient_metadata'):
        return _indentation_classification(
            'requires_more_metadata',
            'needs_more_metadata',
            'Boundary is missing bbox or line-width metadata.')

    heading_or_list = any(reason in reasons for reason in (
        'heading_like',
        'previous_heading_like',
        'list_marker',
        'previous_list_item'))
    if heading_or_list:
        return _indentation_classification(
            'treat_as_heading_list_table_boundary',
            'estimator_should_split',
            'Heading/list-like signals should remain split in the report.')

    left_delta = abs(float(signals.get('left_delta') or 0.0))
    previous_sentence_end = bool(signals.get('previous_sentence_end'))
    previous_hyphenated = bool(signals.get('previous_hyphenated'))
    previous_width_ratio = float(signals.get('previous_width_ratio') or 0.0)
    previous_right_gap_ratio = float(signals.get('previous_right_gap_ratio') or 0.0)
    width_similar = bool(signals.get('width_similar'))
    significant_style_change = bool(signals.get('significant_style_change'))
    gap_ratio = float(signals.get('gap_ratio') or 0.0)

    production_start_signal = (
        previous_sentence_end and
        previous_width_ratio > 0.0 and
        (1.0 - previous_width_ratio) >= new_paragraph_free_space_ratio)
    production_end_signal = (
        previous_sentence_end and
        previous_right_gap_ratio >= 0.12 and
        previous_width_ratio <= 0.88)

    if production_start_signal or production_end_signal:
        return _indentation_classification(
            'split',
            'estimator_should_split',
            'Production-like punctuation/free-space signal supports a paragraph boundary.')

    if previous_hyphenated:
        return _indentation_classification(
            'keep_together',
            'estimator_should_merge',
            'Hyphenated line ending is continuation evidence.',
            production_keep_reason='hyphenated_continuation')

    if left_delta <= small_indent_tolerance and width_similar and not significant_style_change:
        return _indentation_classification(
            'keep_together',
            'estimator_should_merge',
            'Indentation delta is small and width/style signals look continuous.',
            production_keep_reason='small_indent_with_consistent_width_style')

    if not previous_sentence_end and gap_ratio <= 1.6 and not significant_style_change:
        return _indentation_classification(
            'keep_together',
            'estimator_should_merge',
            'Production splits indentation after sentence-ending/free-space signals, which are absent here.',
            production_keep_reason='no_sentence_end_free_space_signal')

    if significant_style_change or gap_ratio >= 2.4:
        return _indentation_classification(
            'split',
            'estimator_should_split',
            'Style or vertical-gap signal supports a real paragraph boundary.')

    return _indentation_classification(
        'requires_more_metadata',
        'production_behavior_unclear',
        'Indentation signal is ambiguous without richer production row metrics.')


def _indentation_classification(
        production_like_expected_behavior: str,
        recommendation: str,
        reason: str,
        production_keep_reason: str = '') -> dict:
    return {
        'production_like_expected_behavior': production_like_expected_behavior,
        'recommendation': recommendation,
        'reason': reason,
        'production_keep_reason': production_keep_reason,
    }


def _indentation_pages_summary(boundaries: list, page_limit: int) -> list:
    by_page = defaultdict(list)
    for boundary in boundaries:
        by_page[boundary.get('page_index')].append(boundary)

    pages = []
    for page_index, page_boundaries in by_page.items():
        recommendation_counts = Counter(
            boundary.get('recommendation')
            for boundary in page_boundaries)
        pages.append({
            'page_index': page_index,
            'page_number': _human_page_number(page_index),
            'indentation_split_boundary_count': len(page_boundaries),
            'estimator_should_merge_count': recommendation_counts.get('estimator_should_merge', 0),
            'estimator_should_split_count': recommendation_counts.get('estimator_should_split', 0),
            'needs_more_metadata_count': recommendation_counts.get('needs_more_metadata', 0),
            'production_behavior_unclear_count': recommendation_counts.get('production_behavior_unclear', 0),
        })

    return sorted(
        pages,
        key=lambda item: (
            -item['indentation_split_boundary_count'],
            item['page_number']))[:page_limit]


def _indentation_rule_recommendation(recommendation_counts: Counter) -> str:
    merge_count = recommendation_counts.get('estimator_should_merge', 0)
    unclear_count = recommendation_counts.get('production_behavior_unclear', 0)
    metadata_count = recommendation_counts.get('needs_more_metadata', 0)
    if merge_count:
        return 'Several indentation splits look mergeable under production-like rules; keep Phase 2I report-only and tune estimator diagnostics first.'
    if unclear_count or metadata_count:
        return 'Some indentation splits remain unclear; collect richer line-width/row metadata before production integration.'
    return 'Indentation splits look consistent in this report, but keep any next step internal before production integration.'


def _filter_insertion_metrics(
        layout_analysis_report: dict,
        review_decisions,
        body_filtering_diff_report: dict,
        paragraph_integrity_report: dict,
        paragraph_grouping_report: dict,
        production_comparison_report: dict,
        paragraph_mismatch_report: dict,
        indentation_rule_report: dict) -> dict:
    layout_analysis_report = layout_analysis_report or {}
    body_filtering_diff_report = body_filtering_diff_report or {}
    paragraph_integrity_report = paragraph_integrity_report or {}
    paragraph_grouping_report = paragraph_grouping_report or {}
    production_comparison_report = production_comparison_report or {}
    paragraph_mismatch_report = paragraph_mismatch_report or {}
    indentation_rule_report = indentation_rule_report or {}

    diff_summary = body_filtering_diff_report.get('summary') or {}
    integrity_summary = paragraph_integrity_report.get('summary') or {}
    grouping_summary = paragraph_grouping_report.get('summary') or {}
    comparison_estimator = production_comparison_report.get('estimator') or {}
    comparison_production = production_comparison_report.get('production_observed') or {}
    comparison_mismatch = production_comparison_report.get('mismatch') or {}
    mismatch_summary = paragraph_mismatch_report.get('summary') or {}
    indentation_summary = indentation_rule_report.get('summary') or {}
    dry_run = layout_analysis_report.get('header_footer_exclusion_dry_run') or {}
    dry_run_summary = dry_run.get('summary') or {}

    missing_inputs = []
    if not layout_analysis_report:
        missing_inputs.append('layout_analysis_report')
    if not body_filtering_diff_report:
        missing_inputs.append('body_filtering_diff_report')
    if not paragraph_integrity_report:
        missing_inputs.append('paragraph_integrity_report')
    if not paragraph_grouping_report:
        missing_inputs.append('paragraph_grouping_report')
    if not production_comparison_report:
        missing_inputs.append('production_comparison_report')
    if not paragraph_mismatch_report:
        missing_inputs.append('paragraph_mismatch_report')
    if not indentation_rule_report:
        missing_inputs.append('indentation_rule_report')

    estimator_count = (
        comparison_estimator.get('paragraph_group_count') or
        grouping_summary.get('estimated_paragraph_group_count') or 0)
    production_count = comparison_production.get('paragraph_group_count') or 0
    absolute_delta = (
        comparison_mismatch.get('absolute_group_count_delta')
        if comparison_mismatch.get('absolute_group_count_delta') is not None
        else abs(int(estimator_count or 0) - int(production_count or 0)))

    return {
        'page_count': layout_analysis_report.get('page_count', len(layout_analysis_report.get('pages', []) or [])),
        'dry_run_candidate_count': dry_run_summary.get(
            'candidate_count',
            len(dry_run.get('candidates', []) or [])),
        'approved_candidate_count': diff_summary.get('approved_candidate_count', 0),
        'blocked_candidate_count': diff_summary.get('blocked_candidate_count', 0),
        'would_remove_block_count': diff_summary.get('would_remove_block_count', 0),
        'body_region_removed_count': integrity_summary.get('body_region_removed_count', 0),
        'paragraph_integrity_warning_count': integrity_summary.get('suspicious_warning_count', 0),
        'estimator_paragraph_group_count': estimator_count,
        'production_body_textblock_count': production_count,
        'absolute_group_count_delta': absolute_delta,
        'estimator_to_production_group_ratio': comparison_mismatch.get('estimator_to_production_group_ratio', 0.0),
        'group_count_delta_ratio': comparison_mismatch.get('group_count_delta_ratio', 0.0),
        'dominant_mismatch_cause': mismatch_summary.get('dominant_mismatch_cause', ''),
        'mismatch_warning_count': len(paragraph_mismatch_report.get('warnings', []) or []),
        'comparison_warning_count': len(production_comparison_report.get('warnings', []) or []),
        'indentation_split_boundary_count': indentation_summary.get('total_indentation_split_boundaries', 0),
        'indentation_should_merge_count': indentation_summary.get('estimator_should_merge_count', 0),
        'indentation_should_split_count': indentation_summary.get('estimator_should_split_count', 0),
        'review_decision_counts': _decision_counts(review_decisions or {}),
        'missing_inputs': missing_inputs,
    }


def _filter_insertion_warnings(metrics: dict) -> list:
    warnings = []
    for name in metrics.get('missing_inputs', []):
        warnings.append({
            'type': 'missing_input',
            'input': name,
            'message': f'{name} was not provided; insertion risk is less certain.',
        })

    if metrics.get('body_region_removed_count', 0):
        warnings.append({
            'type': 'body_region_removal_risk',
            'message': 'Reviewed filtering simulation removed body-region blocks; do not integrate production filtering.',
            'body_region_removed_count': metrics.get('body_region_removed_count', 0),
        })

    if not metrics.get('production_body_textblock_count', 0):
        warnings.append({
            'type': 'production_grouping_metrics_unavailable',
            'message': 'Production-observed TextBlock metrics are unavailable.',
        })

    if metrics.get('group_count_delta_ratio', 0.0) > 0.5:
        warnings.append({
            'type': 'paragraph_grouping_mismatch_remaining',
            'message': 'Estimator and production grouping still differ enough to keep integration gated.',
            'group_count_delta_ratio': metrics.get('group_count_delta_ratio', 0.0),
        })

    return warnings


def _filter_insertion_point_specs() -> list:
    return [
        {
            'candidate_id': 'raw_page_cleanup',
            'stage_name': 'raw-page cleanup stage',
            'pipeline_location': 'RawPage.restore() / RawPage.clean_up() before document-level repeated-candidate analysis',
        },
        {
            'candidate_id': 'document_parse',
            'stage_name': 'document-level Pages._parse_document() stage',
            'pipeline_location': 'Pages.parse() after raw pages are cleaned and analyzed, before margin/section parsing',
        },
        {
            'candidate_id': 'before_page_parse',
            'stage_name': 'before Page.parse() / Layout.parse()',
            'pipeline_location': 'After Page.sections are created, before Sections.parse() calls Layout.parse()',
        },
        {
            'candidate_id': 'before_blocks_cleanup_or_grouping',
            'stage_name': 'before Blocks.clean_up() or block grouping',
            'pipeline_location': 'Either before RawPage block cleanup or before Blocks.parse_block() paragraph grouping',
        },
        {
            'candidate_id': 'after_textblock_grouping',
            'stage_name': 'after TextBlock grouping',
            'pipeline_location': 'After Blocks.parse_block() has created TextBlock/TableBlock structures',
        },
        {
            'candidate_id': 'docx_generation',
            'stage_name': 'DOCX generation stage',
            'pipeline_location': 'Page.make_docx() / Blocks.make_docx() while writing paragraphs and tables',
        },
    ]


def _filter_insertion_point_analysis(spec: dict, metrics: dict) -> dict:
    candidate_id = spec['candidate_id']
    if candidate_id == 'document_parse':
        return _document_parse_insertion_point(spec, metrics)
    if candidate_id == 'before_page_parse':
        return _before_page_parse_insertion_point(spec, metrics)
    if candidate_id == 'raw_page_cleanup':
        return _raw_page_cleanup_insertion_point(spec, metrics)
    if candidate_id == 'before_blocks_cleanup_or_grouping':
        return _before_blocks_cleanup_or_grouping_insertion_point(spec, metrics)
    if candidate_id == 'after_textblock_grouping':
        return _after_textblock_grouping_insertion_point(spec, metrics)
    return _docx_generation_insertion_point(spec, metrics)


def _base_insertion_point(spec: dict, metrics: dict) -> dict:
    return {
        'candidate_id': spec['candidate_id'],
        'stage_name': spec['stage_name'],
        'pipeline_location': spec['pipeline_location'],
        'header_footer_candidates_available': metrics.get('dry_run_candidate_count', 0) > 0,
        'manual_review_decisions_safe_to_apply': metrics.get('approved_candidate_count', 0) > 0,
        'body_text_accidental_removal_risk': 'unknown',
        'paragraph_grouping_impact': '',
        'table_detection_impact': '',
        'image_shape_extraction_impact': '',
        'future_header_footer_generation_possible': True,
        'page_number_handling_possible': True,
        'rollback_ease': 'medium',
        'testing_ease': 'medium',
        'implementation_complexity': 'medium',
        'risk_level': 'medium',
        'recommendation': 'possible',
        'positive_signals': [],
        'negative_signals': [],
        'reason': '',
    }


def _document_parse_insertion_point(spec: dict, metrics: dict) -> dict:
    point = _base_insertion_point(spec, metrics)
    safe_reviewed_filter = (
        metrics.get('approved_candidate_count', 0) > 0 and
        metrics.get('body_region_removed_count', 0) == 0)
    point.update({
        'body_text_accidental_removal_risk': 'low' if safe_reviewed_filter else 'medium',
        'paragraph_grouping_impact': 'Likely helps downstream grouping because repeated top/bottom artifacts can be excluded before section and paragraph parsing.',
        'table_detection_impact': 'Low risk when restricted to approved top/bottom candidates; table detection still sees body lines.',
        'image_shape_extraction_impact': 'Low risk if layout placeholders and image candidates remain blocked from exclusion.',
        'rollback_ease': 'high',
        'testing_ease': 'high',
        'implementation_complexity': 'medium',
        'risk_level': 'low' if safe_reviewed_filter else 'medium',
        'recommendation': 'preferred' if safe_reviewed_filter else 'possible',
        'positive_signals': [
            'repeated candidates are available after raw-page cleanup',
            'manual review decisions can gate every exclusion',
            'downstream section/table/paragraph parsing can run on cleaner body input',
        ],
        'negative_signals': [
            'requires a carefully isolated opt-in copy/apply boundary before mutating raw pages',
        ],
        'reason': 'This is the safest future insertion point because it is document-aware and still precedes body layout grouping.',
    })
    return point


def _before_page_parse_insertion_point(spec: dict, metrics: dict) -> dict:
    point = _base_insertion_point(spec, metrics)
    point.update({
        'body_text_accidental_removal_risk': 'medium',
        'paragraph_grouping_impact': 'Can help paragraph grouping, but page margins and section layout may already include header/footer artifacts.',
        'table_detection_impact': 'Medium risk because section/column assignment may already be influenced by repeated artifacts.',
        'image_shape_extraction_impact': 'Low to medium risk if only text lines are filtered and image placeholders remain blocked.',
        'future_header_footer_generation_possible': True,
        'page_number_handling_possible': True,
        'rollback_ease': 'medium',
        'testing_ease': 'medium',
        'implementation_complexity': 'medium',
        'risk_level': 'medium',
        'recommendation': 'possible',
        'positive_signals': [
            'reviewed candidates can still be matched to page summaries',
            'filtering remains before Blocks.parse_block() paragraph grouping',
        ],
        'negative_signals': [
            'page margin and section detection have already consumed unfiltered content',
        ],
        'reason': 'This is a possible fallback, but it is later than the document-level stage.',
    })
    return point


def _raw_page_cleanup_insertion_point(spec: dict, metrics: dict) -> dict:
    point = _base_insertion_point(spec, metrics)
    point.update({
        'header_footer_candidates_available': False,
        'manual_review_decisions_safe_to_apply': False,
        'body_text_accidental_removal_risk': 'high',
        'paragraph_grouping_impact': 'Unclear; filtering before cleanup may remove or misidentify raw text blocks before line normalization.',
        'table_detection_impact': 'High risk because raw blocks have not yet been normalized into reliable line-level geometry.',
        'image_shape_extraction_impact': 'Medium to high risk because floating image identification happens during cleanup.',
        'future_header_footer_generation_possible': False,
        'page_number_handling_possible': False,
        'rollback_ease': 'low',
        'testing_ease': 'low',
        'implementation_complexity': 'high',
        'risk_level': 'high',
        'recommendation': 'avoid',
        'positive_signals': [
            'earliest possible location if a future raw-copy experiment needs observation only',
        ],
        'negative_signals': [
            'document-level repeated candidates are not known yet',
            'manual review decisions cannot be matched safely before normalized fingerprints exist',
            'cleanup also handles floating images and overlapped lines',
        ],
        'reason': 'Too early for reviewed semantic filtering; keep this stage observational only.',
    })
    return point


def _before_blocks_cleanup_or_grouping_insertion_point(spec: dict, metrics: dict) -> dict:
    point = _base_insertion_point(spec, metrics)
    point.update({
        'body_text_accidental_removal_risk': 'medium',
        'paragraph_grouping_impact': 'Potentially helpful if applied after cleanup but before parse_block(); risky if applied before clean_up().',
        'table_detection_impact': 'Medium to high risk because stream/lattice table detection depends on line collections and shapes.',
        'image_shape_extraction_impact': 'Medium risk around inline/floating image placeholder handling.',
        'future_header_footer_generation_possible': True,
        'page_number_handling_possible': True,
        'rollback_ease': 'medium',
        'testing_ease': 'medium',
        'implementation_complexity': 'medium',
        'risk_level': 'medium',
        'recommendation': 'possible',
        'positive_signals': [
            'line-level geometry can be available before paragraph grouping',
        ],
        'negative_signals': [
            'the label spans two very different timings; before clean_up is too early',
            'table detection may be sensitive to missing lines',
        ],
        'reason': 'Only the after-cleanup/before-grouping variant is plausible; the before-cleanup variant should be avoided.',
    })
    return point


def _after_textblock_grouping_insertion_point(spec: dict, metrics: dict) -> dict:
    point = _base_insertion_point(spec, metrics)
    point.update({
        'body_text_accidental_removal_risk': 'high',
        'paragraph_grouping_impact': 'Risky because header/footer text may already be merged into TextBlocks or affect spacing.',
        'table_detection_impact': 'Incomplete because table detection and paragraph grouping have already run.',
        'image_shape_extraction_impact': 'Low direct image risk, but mixed TextBlock/image content may be hard to split safely.',
        'future_header_footer_generation_possible': 'partial',
        'page_number_handling_possible': 'partial',
        'rollback_ease': 'medium',
        'testing_ease': 'medium',
        'implementation_complexity': 'high',
        'risk_level': 'high',
        'recommendation': 'avoid',
        'positive_signals': [
            'serialized TextBlock metrics are observable for diagnostics',
        ],
        'negative_signals': [
            'header/footer may have already merged into or polluted body TextBlocks',
            'removing part of a TextBlock would require text/line surgery',
            'downstream paragraph grouping cannot benefit retroactively',
        ],
        'reason': 'Too late for safe body cleanup; use this stage for comparison reports only.',
    })
    return point


def _docx_generation_insertion_point(spec: dict, metrics: dict) -> dict:
    point = _base_insertion_point(spec, metrics)
    point.update({
        'body_text_accidental_removal_risk': 'high',
        'paragraph_grouping_impact': 'Incomplete because body pollution remains through parsing and only disappears at rendering time.',
        'table_detection_impact': 'Incomplete because table and spacing decisions have already been made.',
        'image_shape_extraction_impact': 'Low direct extraction risk, but no chance to repair polluted layout semantics.',
        'future_header_footer_generation_possible': 'partial',
        'page_number_handling_possible': 'partial',
        'rollback_ease': 'high',
        'testing_ease': 'low',
        'implementation_complexity': 'medium',
        'risk_level': 'high',
        'recommendation': 'avoid',
        'positive_signals': [
            'easy to guard behind output-only experiments',
        ],
        'negative_signals': [
            'does not prevent header/footer from affecting body parsing',
            'cannot improve paragraph grouping, sectioning, or table detection',
            'risks hiding rather than fixing semantic structure problems',
        ],
        'reason': 'DOCX-only filtering is incomplete; it leaves the parsed body model polluted.',
    })
    return point


def _filter_insertion_next_experiment(preferred: list, metrics: dict) -> dict:
    selected = preferred[0] if preferred else 'document_parse'
    return {
        'selected_insertion_point': selected,
        'experiment_type': 'report_only_simulation_at_selected_insertion_point',
        'requirements': [
            'opt-in only',
            'explicit approve_exclude review decisions only',
            'dry-run/apply split',
            'no default conversion behavior change',
            'no DOCX header/footer generation yet',
        ],
        'expected_sample_removal_count': metrics.get('would_remove_block_count', 0),
        'body_region_removed_count': metrics.get('body_region_removed_count', 0),
    }


def _filter_insertion_recommendation(
        preferred: list,
        warnings: list,
        metrics: dict) -> str:
    if metrics.get('body_region_removed_count', 0):
        return 'Do not attempt production insertion while body-region removals are present.'
    if not preferred:
        return 'No preferred insertion point was established; keep the next phase report-only.'
    if warnings:
        return 'A preferred insertion point exists, but remaining diagnostics require Phase 2K to stay opt-in and report-only.'
    return 'Document-level insertion is the preferred future path, but the next phase should still be an opt-in local simulation.'


def _empty_paragraph_grouping_diagnostics() -> dict:
    return {
        'groups_by_line_count': {},
        'groups_by_block_count': {},
        'one_line_group_ratio': 0.0,
        'short_fragment_ratio': 0.0,
        'split_reason_counts': {},
        'most_common_split_reasons': [],
        'ignored_split_reason_counts': {},
        'most_common_ignored_split_reasons': [],
        'ignored_split_boundary_count': 0,
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
    ignored_split_boundaries = [
        boundary
        for page in pages_report or []
        for boundary in page.get('ignored_split_boundaries', []) or []
    ]
    split_reason_counts = Counter()
    for boundary in split_boundaries:
        for reason in boundary.get('reasons', []) or []:
            split_reason_counts[reason] += 1
    ignored_reason_counts = Counter()
    for boundary in ignored_split_boundaries:
        for reason in boundary.get('ignored_reasons', []) or []:
            ignored_reason_counts[reason] += 1
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
        'ignored_split_reason_counts': dict(sorted(ignored_reason_counts.items())),
        'most_common_ignored_split_reasons': _counter_top_items(ignored_reason_counts),
        'ignored_split_boundary_count': len(ignored_split_boundaries),
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
