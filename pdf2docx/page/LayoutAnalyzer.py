# -*- coding: utf-8 -*-

'''Small pure helpers for document-level layout analysis.

This module intentionally does not integrate with the converter pipeline yet.
It works with simplified page dictionaries so tests and debug tools can build
header/footer analysis incrementally without changing conversion output.
'''

import re
import os
import zipfile
import xml.etree.ElementTree as ET
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
PAGE_NUMBER_BEHAVIOR_PLACEHOLDER_ONLY = 'placeholder_only'
PAGE_NUMBER_BEHAVIOR_STATIC_TEXT = 'static_text'
PAGE_NUMBER_BEHAVIOR_WORD_FIELD = 'word_field'
PAGE_NUMBER_BEHAVIOR_UNSUPPORTED = 'unsupported'
PAGE_NUMBER_BEHAVIORS = {
    PAGE_NUMBER_BEHAVIOR_PLACEHOLDER_ONLY,
    PAGE_NUMBER_BEHAVIOR_STATIC_TEXT,
    PAGE_NUMBER_BEHAVIOR_WORD_FIELD,
    PAGE_NUMBER_BEHAVIOR_UNSUPPORTED,
}
MIGRATION_PROFILE_BODY_SIGNATURE_GATE = 'normalized_token_ngram'
MIGRATION_PROFILE_STRICT_EXACT_FRAGMENT_GATE = 'diagnostic_only'
MIGRATION_PROFILE_LOCAL_OUTPUT_POLICY = 'temp_or_ignored_only'
MIGRATION_PROFILE_PUBLIC_EXPOSURE = 'none'
MIGRATION_PROFILE_REQUIRED_POLICY = 'default'
MIGRATION_PROFILE_FAIL_CLOSED_ON = (
    'true_body_text_loss',
    'table_text_loss',
    'callout_text_loss',
    'list_text_loss',
    'residual_header_footer_pollution',
    'unsafe_policy',
    'unsafe_page_number_behavior',
    'missing_review_decisions',
)
DECISION_APPROVE_EXCLUDE = 'approve_exclude'
DECISION_REJECT_EXCLUDE = 'reject_exclude'
DECISION_UNSURE = 'unsure'
DECISION_NONE = 'none'
DECISION_CONFLICT = 'conflict'
REVIEWED_FILTERING_MODE_DRY_RUN = 'dry_run'
REVIEWED_FILTERING_MODE_SIMULATION = 'simulation'
REVIEWED_FILTERING_MODE_GUARDED_APPLY_RESTORE = 'guarded_apply_restore'
REVIEWED_FILTERING_MODE_FILTERED_PARSE_EXPERIMENT = 'filtered_parse_experiment'
REVIEWED_FILTERING_MODE_FUTURE_APPLY = 'future_apply'
REVIEWED_FILTERING_MODES = {
    REVIEWED_FILTERING_MODE_DRY_RUN,
    REVIEWED_FILTERING_MODE_SIMULATION,
    REVIEWED_FILTERING_MODE_GUARDED_APPLY_RESTORE,
    REVIEWED_FILTERING_MODE_FILTERED_PARSE_EXPERIMENT,
    REVIEWED_FILTERING_MODE_FUTURE_APPLY,
}
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
_TABLE_VISUAL_REVIEW_SECTION_RE = re.compile(
    r'^###\s+([^|]+?)\s*\|\s*Page\s+(\d+)\s*$',
    re.IGNORECASE)
_TABLE_VISUAL_DECISION_RE = re.compile(
    r'(approve_safe_boundary_shift|reject_unsafe_table_change|unsure):\s*\[([^\]]*)\]',
    re.IGNORECASE)
_COUNT_PAIR_RE = re.compile(r'(-?\d+)\s*->\s*(-?\d+)')
_WORD_XML_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
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


def load_table_geometry_visual_review_decisions(path: str) -> dict:
    '''Read a local table geometry visual review markdown file.'''
    with open(path, 'r', encoding='utf-8') as stream:
        return parse_table_geometry_visual_review_markdown(stream.read())


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


def parse_table_geometry_visual_review_markdown(markdown_text: str) -> dict:
    '''Parse local table-geometry visual review decisions.'''
    items = []
    current = None

    def flush_current():
        if not current:
            return
        if current.get('review_item_id'):
            current.setdefault('manual_decision', DECISION_NONE)
            current.setdefault('checked_decisions', [])
            current.setdefault('row_column_cell_counts_preserved', False)
            current.setdefault('text_cell_signature_preserved', False)
            items.append(current.copy())

    for raw_line in (markdown_text or '').splitlines():
        line = raw_line.strip()
        section = _TABLE_VISUAL_REVIEW_SECTION_RE.match(line)
        if section:
            flush_current()
            current = {
                'review_item_id': normalize_text(section.group(1)),
                'page_number': int(section.group(2)),
            }
            continue

        if current is None:
            continue

        field = _REVIEW_FIELD_RE.match(line)
        if not field:
            continue

        field_name = field.group(1)
        field_value = field.group(2).strip()
        if field_name in {
                'baseline_table_id',
                'filtered_table_id',
                'likely_cause',
                'current_severity',
                'review_classification'}:
            current[field_name] = _strip_inline_code(field_value)
        elif field_name == 'row_count_before_after':
            before, after = _parse_count_pair(field_value)
            current['row_count_before'] = before
            current['row_count_after'] = after
        elif field_name == 'column_count_before_after':
            before, after = _parse_count_pair(field_value)
            current['column_count_before'] = before
            current['column_count_after'] = after
        elif field_name == 'cell_count_before_after':
            before, after = _parse_count_pair(field_value)
            current['cell_count_before'] = before
            current['cell_count_after'] = after
        elif field_name == 'text_cell_signature_preserved':
            current['text_cell_signature_preserved'] = _parse_bool(field_value)
        elif field_name == 'human_decision':
            decision, checked = _parse_table_visual_human_decision(field_value)
            current['manual_decision'] = decision
            current['checked_decisions'] = checked

        current['row_column_cell_counts_preserved'] = _table_visual_counts_preserved(current)

    flush_current()

    decision_counts = defaultdict(int)
    for item in items:
        decision_counts[item.get('manual_decision', DECISION_NONE)] += 1

    return {
        'items': items,
        'summary': {
            'review_item_count': len(items),
            'decision_counts': dict(sorted(decision_counts.items())),
        },
    }


def build_reviewed_filtering_internal_config(config: dict = None, **overrides) -> dict:
    '''Build a JSON-serializable internal config for reviewed filtering experiments.'''
    merged = _default_reviewed_filtering_internal_config()
    if config:
        merged.update(dict(config))
    if overrides:
        merged.update(overrides)

    mode = normalize_text(merged.get('mode') or REVIEWED_FILTERING_MODE_DRY_RUN)
    if not mode:
        mode = REVIEWED_FILTERING_MODE_DRY_RUN

    page_subset = merged.get('page_subset', [])
    if page_subset is None:
        page_subset = []
    elif isinstance(page_subset, (tuple, set)):
        page_subset = list(page_subset)
    elif not isinstance(page_subset, list):
        page_subset = [page_subset]

    max_pages = merged.get('max_pages')
    if max_pages in ('', None):
        max_pages = None
    else:
        max_pages = _reviewed_filtering_config_int_or_none(max_pages)

    normalized = {
        'enabled': bool(merged.get('enabled', False)),
        'mode': mode,
        'review_decisions_path': normalize_text(merged.get('review_decisions_path', '')),
        'review_decisions': merged.get('review_decisions'),
        'require_explicit_approval': bool(merged.get('require_explicit_approval', True)),
        'allow_raw_would_exclude': bool(merged.get('allow_raw_would_exclude', False)),
        'allow_unsure': bool(merged.get('allow_unsure', False)),
        'allow_rejected': bool(merged.get('allow_rejected', False)),
        'protect_body_region': bool(merged.get('protect_body_region', True)),
        'protect_layout_placeholders': bool(merged.get('protect_layout_placeholders', True)),
        'collect_diagnostics': bool(merged.get('collect_diagnostics', True)),
        'write_local_reports': bool(merged.get('write_local_reports', False)),
        'max_pages': max_pages,
        'page_subset': page_subset,
        'fail_closed_on_warning': bool(merged.get('fail_closed_on_warning', True)),
        'public_cli_exposed': False,
        'production_default_enabled': False,
    }
    return normalized


def build_reviewed_filtering_internal_config_report(
        config: dict = None,
        dry_run_report: dict = None,
        review_decisions=None,
        enabled: bool = True) -> dict:
    '''Summarize an internal reviewed-filtering config without applying filtering.'''
    internal_config = build_reviewed_filtering_internal_config(config)
    if review_decisions is None:
        review_decisions = internal_config.get('review_decisions')
    candidates = _dry_run_candidates(dry_run_report)
    candidate_rows = _reviewed_filtering_config_candidate_rows(
        candidates,
        review_decisions,
        internal_config)
    summary = _reviewed_filtering_config_summary(
        internal_config,
        candidate_rows,
        review_decisions,
        enabled=enabled)
    warnings = _reviewed_filtering_config_warnings(
        internal_config,
        summary,
        candidate_rows,
        review_decisions,
        enabled=enabled)
    activation_status = _reviewed_filtering_config_activation_status(
        internal_config,
        summary,
        warnings,
        enabled=enabled)
    summary['activation_status'] = activation_status

    return {
        'enabled': bool(enabled and internal_config.get('enabled', False)),
        'policy': 'internal_reviewed_header_footer_filtering_config_only',
        'config': internal_config,
        'summary': summary,
        'candidates': candidate_rows,
        'warnings': warnings,
        'document_parse_settings': reviewed_filtering_config_to_document_parse_settings(
            internal_config,
            review_decisions=review_decisions,
            activation_status=activation_status),
        'recommendation': {
            'safe_for_internal_experiment': activation_status == 'ready_for_internal_experiment',
            'reason': _reviewed_filtering_config_recommendation(
                activation_status,
                warnings),
        },
    }


def reviewed_filtering_config_to_document_parse_settings(
        config: dict = None,
        review_decisions=None,
        activation_status: str = '') -> dict:
    '''Translate a ready internal config into existing private Pages settings.'''
    internal_config = build_reviewed_filtering_internal_config(config)
    if activation_status and activation_status != 'ready_for_internal_experiment':
        return {}
    if not internal_config.get('enabled', False):
        return {}
    if review_decisions is None:
        review_decisions = internal_config.get('review_decisions')
    if not review_decisions:
        return {}

    mode = internal_config.get('mode')
    if mode not in REVIEWED_FILTERING_MODES:
        return {}
    if mode == REVIEWED_FILTERING_MODE_FUTURE_APPLY:
        return {}

    settings = {
        'layout_analysis': True,
        '_document_parse_filtering_review_decisions': review_decisions,
    }
    if mode in {
            REVIEWED_FILTERING_MODE_DRY_RUN,
            REVIEWED_FILTERING_MODE_SIMULATION,
            REVIEWED_FILTERING_MODE_GUARDED_APPLY_RESTORE,
            REVIEWED_FILTERING_MODE_FILTERED_PARSE_EXPERIMENT}:
        settings['_document_parse_filtering_hook_enabled'] = bool(
            internal_config.get('collect_diagnostics', True))
        settings['_document_parse_filtering_apply'] = False
    if mode in {
            REVIEWED_FILTERING_MODE_GUARDED_APPLY_RESTORE,
            REVIEWED_FILTERING_MODE_FILTERED_PARSE_EXPERIMENT}:
        settings['_document_parse_raw_object_mapping_enabled'] = True
        settings['_document_parse_copied_raw_filtering_enabled'] = True
        settings['_document_parse_guarded_raw_apply_restore_enabled'] = True
    if mode == REVIEWED_FILTERING_MODE_FILTERED_PARSE_EXPERIMENT:
        settings['_document_parse_filtered_parse_experiment_enabled'] = True
    return settings


def build_reviewed_header_footer_migration_profile(
        config: dict = None,
        **overrides) -> dict:
    '''Build an internal reviewed header/footer migration profile.

    The profile is diagnostic and private. It consolidates the reviewed
    filtering config, DOCX header/footer writer requirements, page-number mode,
    and local migration gates without wiring any behavior into default
    conversion.
    '''
    profile = _reviewed_header_footer_migration_profile_payload(
        config,
        overrides)
    reviewed_filtering_config = _migration_profile_reviewed_filtering_config(
        profile)
    summary = summarize_reviewed_header_footer_migration_profile(profile)
    validation = validate_reviewed_header_footer_migration_profile(profile)
    return {
        'enabled': bool(profile.get('enabled', False)),
        'policy': 'internal_reviewed_header_footer_migration_profile_only',
        'profile': profile,
        'summary': summary,
        'reviewed_filtering_internal_config': reviewed_filtering_config,
        'document_parse_settings': reviewed_filtering_config_to_document_parse_settings(
            reviewed_filtering_config,
            review_decisions=reviewed_filtering_config.get('review_decisions')),
        'docx_header_footer_generation_plan_requirements': (
            _migration_profile_docx_plan_requirements(profile)),
        'writer_settings': _migration_profile_writer_settings(profile),
        'migration_gate_expectations': (
            _migration_profile_gate_expectations(profile)),
        'validation': validation,
        'recommendation': {
            'safe_for_internal_migration_profile': bool(
                validation.get('summary', {}).get('safe_for_internal_migration_profile')),
            'reason': validation.get('recommendation', {}).get('reason', ''),
        },
    }


def summarize_reviewed_header_footer_migration_profile(
        profile: dict = None) -> dict:
    '''Return a compact JSON-serializable summary of the internal profile.'''
    normalized = _reviewed_header_footer_migration_profile_from_input(profile)
    return {
        'enabled': bool(normalized.get('enabled', False)),
        'default_enabled': False,
        'parse_mode': normalized.get('parse_mode', ''),
        'reviewed_filtering_enabled': bool(normalized.get('enabled', False)),
        'docx_header_footer_generation_enabled': bool(normalized.get('enabled', False)),
        'require_explicit_approval': bool(
            normalized.get('require_explicit_approval', True)),
        'allow_raw_would_exclude': bool(
            normalized.get('allow_raw_would_exclude', False)),
        'allow_rejected': bool(normalized.get('allow_rejected', False)),
        'allow_unsure': bool(normalized.get('allow_unsure', False)),
        'protect_body_region': bool(normalized.get('protect_body_region', True)),
        'protect_layout_placeholders': bool(
            normalized.get('protect_layout_placeholders', True)),
        'header_footer_policy_required': normalized.get(
            'header_footer_policy_required', ''),
        'allow_non_default_policy': bool(
            normalized.get('allow_non_default_policy', False)),
        'page_number_behavior': normalized.get('page_number_behavior', ''),
        'page_number_behavior_explicitly_requested': bool(
            normalized.get('page_number_behavior_explicitly_requested', False)),
        'page_number_word_field_selected': (
            normalized.get('page_number_behavior') ==
            PAGE_NUMBER_BEHAVIOR_WORD_FIELD),
        'body_signature_gate': normalized.get('body_signature_gate', ''),
        'strict_exact_fragment_gate': normalized.get(
            'strict_exact_fragment_gate', ''),
        'strict_exact_fragment_gate_blocks': False,
        'fail_closed_on': list(normalized.get('fail_closed_on', []) or []),
        'local_output_policy': normalized.get('local_output_policy', ''),
        'public_exposure': normalized.get('public_exposure', ''),
        'public_cli_exposed': bool(normalized.get('public_cli_exposed', False)),
        'public_api_exposed': bool(normalized.get('public_api_exposed', False)),
        'production_default_enabled': bool(
            normalized.get('production_default_enabled', False)),
        'default_conversion_changed': bool(
            normalized.get('default_conversion_changed', False)),
    }


def validate_reviewed_header_footer_migration_profile(
        profile: dict = None,
        reviewed_filtering_config: dict = None,
        docx_header_footer_plan: dict = None,
        migration_gate_report: dict = None) -> dict:
    '''Validate that internal migration wiring remains conservative.

    Optional existing reports can be supplied to validate that they match the
    consolidated profile. Blocking issues are reported as fail-closed warnings;
    strict exact-fragment mismatches remain diagnostics when the normalized
    token/ngram gate passes.
    '''
    normalized = _reviewed_header_footer_migration_profile_from_input(profile)
    warnings = []
    diagnostics = []

    if not normalized.get('enabled', False):
        diagnostics.append({'type': 'migration_profile_disabled'})
    if normalized.get('parse_mode') != REVIEWED_FILTERING_MODE_FILTERED_PARSE_EXPERIMENT:
        warnings.append({
            'type': 'unsafe_parse_mode',
            'parse_mode': normalized.get('parse_mode', ''),
        })
    if not normalized.get('require_explicit_approval', True):
        warnings.append({'type': 'explicit_review_approval_not_required'})
    if normalized.get('allow_raw_would_exclude', False):
        warnings.append({'type': 'raw_would_exclude_allowed'})
    if normalized.get('allow_rejected', False):
        warnings.append({'type': 'rejected_candidates_allowed'})
    if normalized.get('allow_unsure', False):
        warnings.append({'type': 'unsure_candidates_allowed'})
    if not normalized.get('protect_body_region', True):
        warnings.append({'type': 'body_region_not_protected'})
    if not normalized.get('protect_layout_placeholders', True):
        warnings.append({'type': 'layout_placeholders_not_protected'})
    if (
            normalized.get('header_footer_policy_required') !=
            MIGRATION_PROFILE_REQUIRED_POLICY or
            normalized.get('allow_non_default_policy', False)):
        warnings.append({
            'type': 'unsafe_policy',
            'policy_required': normalized.get('header_footer_policy_required', ''),
            'allow_non_default_policy': bool(
                normalized.get('allow_non_default_policy', False)),
        })

    page_number_behavior = normalized.get('page_number_behavior')
    if page_number_behavior == PAGE_NUMBER_BEHAVIOR_UNSUPPORTED:
        warnings.append({'type': 'unsafe_page_number_behavior'})
    elif page_number_behavior == PAGE_NUMBER_BEHAVIOR_STATIC_TEXT:
        diagnostics.append({
            'type': 'static_text_page_number_behavior_diagnostic_only',
        })
    elif (
            page_number_behavior == PAGE_NUMBER_BEHAVIOR_WORD_FIELD and
            not normalized.get('page_number_behavior_explicitly_requested', False)):
        warnings.append({
            'type': 'unsafe_page_number_behavior',
            'reason': 'word_field_not_explicitly_requested',
        })

    if (
            normalized.get('enabled', False) and
            not normalized.get('review_decisions') and
            not normalized.get('review_decisions_path')):
        warnings.append({'type': 'missing_review_decisions'})
    if normalized.get('body_signature_gate') != MIGRATION_PROFILE_BODY_SIGNATURE_GATE:
        warnings.append({
            'type': 'unsafe_body_signature_gate',
            'body_signature_gate': normalized.get('body_signature_gate', ''),
        })
    if (
            normalized.get('strict_exact_fragment_gate') !=
            MIGRATION_PROFILE_STRICT_EXACT_FRAGMENT_GATE):
        warnings.append({
            'type': 'strict_exact_fragment_gate_not_diagnostic_only',
            'strict_exact_fragment_gate': normalized.get(
                'strict_exact_fragment_gate', ''),
        })
    if normalized.get('local_output_policy') != MIGRATION_PROFILE_LOCAL_OUTPUT_POLICY:
        warnings.append({
            'type': 'local_output_not_temp_or_ignored_only',
            'local_output_policy': normalized.get('local_output_policy', ''),
        })
    if (
            normalized.get('public_exposure') != MIGRATION_PROFILE_PUBLIC_EXPOSURE or
            normalized.get('public_cli_exposed', False) or
            normalized.get('public_api_exposed', False)):
        warnings.append({'type': 'public_exposure_enabled'})
    if (
            normalized.get('production_default_enabled', False) or
            normalized.get('default_conversion_changed', False)):
        warnings.append({'type': 'production_default_conversion_changed'})

    missing_fail_closed = [
        item for item in MIGRATION_PROFILE_FAIL_CLOSED_ON
        if item not in set(normalized.get('fail_closed_on', []) or [])
    ]
    if missing_fail_closed:
        warnings.append({
            'type': 'fail_closed_conditions_incomplete',
            'missing': missing_fail_closed,
        })

    _extend_profile_filtering_config_warnings(
        warnings,
        normalized,
        reviewed_filtering_config)
    _extend_profile_docx_plan_warnings(
        warnings,
        diagnostics,
        normalized,
        docx_header_footer_plan)
    _extend_profile_migration_gate_warnings(
        warnings,
        diagnostics,
        migration_gate_report)

    blocking_warning_count = len(warnings)
    if not normalized.get('enabled', False):
        status = 'disabled'
    elif blocking_warning_count:
        status = 'blocked'
    else:
        status = 'ready_for_internal_migration_profile'

    return {
        'enabled': bool(normalized.get('enabled', False)),
        'policy': 'internal_reviewed_header_footer_migration_profile_validation_only',
        'summary': {
            'status': status,
            'blocking_warning_count': blocking_warning_count,
            'diagnostic_warning_count': len(diagnostics),
            'safe_for_internal_migration_profile': (
                status == 'ready_for_internal_migration_profile'),
            'strict_exact_fragment_gate_blocks': False,
            'normalized_body_signature_gate_primary': (
                normalized.get('body_signature_gate') ==
                MIGRATION_PROFILE_BODY_SIGNATURE_GATE),
            'public_exposure': normalized.get('public_exposure', ''),
            'production_default_enabled': bool(
                normalized.get('production_default_enabled', False)),
        },
        'warnings': warnings,
        'diagnostics': diagnostics,
        'fail_closed_on': list(normalized.get('fail_closed_on', []) or []),
        'recommendation': {
            'safe_for_internal_migration_profile': (
                status == 'ready_for_internal_migration_profile'),
            'reason': _reviewed_header_footer_migration_profile_recommendation(
                status,
                warnings),
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


def build_docx_header_footer_generation_plan(
        page_summaries: list = None,
        dry_run_report: dict = None,
        review_decisions=None,
        enabled: bool = False,
        page_number_behavior: str = PAGE_NUMBER_BEHAVIOR_PLACEHOLDER_ONLY,
        require_dynamic_page_number: bool = False) -> dict:
    '''Build an internal plan for future DOCX header/footer generation.

    This helper is intentionally plan-only. It does not mutate page content and
    does not write DOCX files. Only explicit approve_exclude decisions for
    header/footer/page-number candidates can become representable entries.
    '''
    page_number_behavior = _normalize_docx_page_number_behavior(page_number_behavior)
    dry_run_candidates = _dry_run_candidates(dry_run_report)
    decision_map = _review_decision_map(review_decisions)
    approved, blocked = _reviewed_exclusion_candidates(dry_run_candidates, decision_map)
    text_lookup = _docx_header_footer_text_lookup(page_summaries)

    if not enabled:
        return _docx_header_footer_generation_plan_result(
            enabled=False,
            candidates=dry_run_candidates,
            approved=approved,
            blocked=blocked,
            entries=[],
            unrepresentable=[],
            warnings=[{'type': 'docx_header_footer_generation_plan_disabled'}],
            page_number_behavior=page_number_behavior,
            require_dynamic_page_number=require_dynamic_page_number)

    entries = []
    unrepresentable = []
    warnings = []
    for candidate in approved:
        entry, warning = _docx_header_footer_plan_entry(
            candidate,
            text_lookup,
            page_number_behavior)
        if entry:
            entries.append(entry)
        else:
            item = dict(candidate)
            item['blocked_reason'] = warning.get('type', 'unrepresentable_candidate')
            unrepresentable.append(item)
            warnings.append(warning)

    return _docx_header_footer_generation_plan_result(
        enabled=True,
        candidates=dry_run_candidates,
        approved=approved,
        blocked=blocked,
        entries=entries,
        unrepresentable=unrepresentable,
        warnings=warnings,
        page_number_behavior=page_number_behavior,
        require_dynamic_page_number=require_dynamic_page_number)


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


def reviewed_raw_object_removal_plan(raw_object_mapping_report: dict) -> list:
    '''Return safe reviewed raw-object removal targets from a mapping report.'''
    return _copied_apply_removal_plan(raw_object_mapping_report)


def build_document_parse_guarded_raw_page_apply_restore_report(
        raw_object_pages_before: list = None,
        raw_object_pages_during: list = None,
        raw_object_pages_after: list = None,
        removed_objects_by_page: list = None,
        raw_object_mapping_report: dict = None,
        copied_apply_report: dict = None,
        enabled: bool = False,
        snapshot_created: bool = False,
        restore_completed: bool = False,
        expected_mapping_count: int = None,
        apply_skipped_reason: str = '') -> dict:
    '''Report a guarded production raw-page apply/restore experiment.'''
    before = _copy_raw_object_pages(raw_object_pages_before)
    during = _copy_raw_object_pages(raw_object_pages_during or raw_object_pages_before)
    after = _copy_raw_object_pages(raw_object_pages_after or raw_object_pages_before)
    removed_by_page = [
        {
            'page_index': page.get('page_index'),
            'page_number': page.get('page_number'),
            'removed_count': page.get('removed_count', 0),
            'objects': [dict(raw_object) for raw_object in page.get('objects', []) or []],
        }
        for page in removed_objects_by_page or []
    ]
    removed_objects = [
        raw_object
        for page in removed_by_page
        for raw_object in page.get('objects', []) or []
    ]
    if not enabled:
        original_count = _raw_object_page_count(before)
        return {
            'enabled': False,
            'experiment_mode': 'guarded_apply_restore',
            'production_applied': False,
            'policy': 'guarded_raw_page_apply_restore_report_only',
            'insertion_point': 'document_parse',
            'summary': _guarded_apply_disabled_summary(original_count),
            'removed_objects_by_page': [],
            'removed_counts_by_role': {},
            'removed_counts_by_page': [],
            'downstream_risk_notes': _guarded_apply_downstream_risk_notes(before, before),
            'consistency': {},
            'safety_warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2p': False,
                'reason': 'Guarded raw-page apply/restore experiment is disabled.',
            },
        }

    consistency = _guarded_apply_consistency(
        raw_object_mapping_report,
        copied_apply_report,
        len(removed_objects),
        expected_mapping_count)
    summary = _guarded_apply_summary(
        before,
        during,
        after,
        removed_objects,
        raw_object_mapping_report,
        snapshot_created,
        restore_completed,
        consistency)
    warnings = _guarded_apply_warnings(
        summary,
        raw_object_mapping_report,
        consistency,
        apply_skipped_reason)
    return {
        'enabled': True,
        'experiment_mode': 'guarded_apply_restore',
        'production_applied': False,
        'policy': 'guarded_raw_page_apply_restore_report_only',
        'insertion_point': 'document_parse',
        'summary': summary,
        'removed_objects_by_page': removed_by_page,
        'removed_counts_by_role': _copied_apply_removed_counts_by_role(removed_objects),
        'removed_counts_by_page': _copied_apply_removed_counts_by_page(removed_by_page),
        'downstream_risk_notes': _guarded_apply_downstream_risk_notes(before, during),
        'consistency': consistency,
        'safety_warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2p': _guarded_apply_safe_for_phase_2p(summary, warnings),
            'reason': _guarded_apply_recommendation(summary, warnings),
        },
    }


def build_document_parse_filtered_parse_experiment_report(
        raw_object_pages_before: list = None,
        raw_object_pages_filtered: list = None,
        raw_object_pages_after: list = None,
        removed_objects_by_page: list = None,
        baseline_parse_metrics: dict = None,
        filtered_parse_metrics: dict = None,
        raw_object_mapping_report: dict = None,
        copied_apply_report: dict = None,
        guarded_apply_restore_report: dict = None,
        enabled: bool = False,
        restore_completed: bool = False,
        restore_fingerprint_match: bool = False,
        expected_mapping_count: int = None,
        apply_skipped_reason: str = '') -> dict:
    '''Compare baseline parse metrics with an opt-in filtered parse experiment.'''
    before = _copy_raw_object_pages(raw_object_pages_before)
    filtered = _copy_raw_object_pages(raw_object_pages_filtered or raw_object_pages_before)
    after = _copy_raw_object_pages(raw_object_pages_after or raw_object_pages_before)
    removed_by_page = [
        {
            'page_index': page.get('page_index'),
            'page_number': page.get('page_number'),
            'removed_count': page.get('removed_count', 0),
            'objects': [dict(raw_object) for raw_object in page.get('objects', []) or []],
        }
        for page in removed_objects_by_page or []
    ]
    removed_objects = [
        raw_object
        for page in removed_by_page
        for raw_object in page.get('objects', []) or []
    ]
    baseline_metrics = _copy_parse_metrics(baseline_parse_metrics)
    filtered_metrics = _copy_parse_metrics(filtered_parse_metrics or baseline_metrics)

    if not enabled:
        original_count = _raw_object_page_count(before)
        disabled_metrics = _filtered_parse_empty_metrics(original_count)
        return {
            'enabled': False,
            'experiment_mode': 'filtered_parse_experiment',
            'production_applied': False,
            'policy': 'filtered_parse_experiment_report_only',
            'insertion_point': 'document_parse',
            'baseline_parse_metrics': baseline_metrics or disabled_metrics,
            'filtered_parse_metrics': baseline_metrics or disabled_metrics,
            'summary': _filtered_parse_disabled_summary(
                original_count,
                baseline_metrics or disabled_metrics),
            'removed_objects_by_page': [],
            'removed_counts_by_role': {},
            'removed_counts_by_page': [],
            'header_footer_pollution_reduction': {},
            'consistency': {},
            'safety_warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2q': False,
                'reason': 'Filtered parse experiment is disabled.',
            },
        }

    consistency = _filtered_parse_consistency(
        raw_object_mapping_report,
        copied_apply_report,
        guarded_apply_restore_report,
        len(removed_objects),
        expected_mapping_count)
    summary = _filtered_parse_summary(
        before,
        filtered,
        after,
        removed_objects,
        baseline_metrics,
        filtered_metrics,
        raw_object_mapping_report,
        restore_completed,
        restore_fingerprint_match,
        consistency)
    warnings = _filtered_parse_warnings(
        summary,
        baseline_metrics,
        filtered_metrics,
        raw_object_mapping_report,
        consistency,
        apply_skipped_reason)
    return {
        'enabled': True,
        'experiment_mode': 'filtered_parse_experiment',
        'production_applied': False,
        'policy': 'filtered_parse_experiment_report_only',
        'insertion_point': 'document_parse',
        'baseline_parse_metrics': baseline_metrics,
        'filtered_parse_metrics': filtered_metrics,
        'summary': summary,
        'removed_objects_by_page': removed_by_page,
        'removed_counts_by_role': _copied_apply_removed_counts_by_role(removed_objects),
        'removed_counts_by_page': _copied_apply_removed_counts_by_page(removed_by_page),
        'header_footer_pollution_reduction': _filtered_parse_pollution_reduction(
            removed_objects,
            baseline_metrics,
            filtered_metrics),
        'consistency': consistency,
        'safety_warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2q': _filtered_parse_safe_for_phase_2q(summary, warnings),
            'reason': _filtered_parse_recommendation(summary, warnings),
        },
    }


def build_table_delta_investigation_report(
        filtered_parse_experiment_report: dict = None,
        baseline_parse_metrics: dict = None,
        filtered_parse_metrics: dict = None,
        removed_objects_by_page: list = None,
        enabled: bool = False) -> dict:
    '''Investigate table-count deltas from a filtered parse experiment.'''
    experiment_report = filtered_parse_experiment_report or {}
    baseline_metrics = _copy_parse_metrics(
        baseline_parse_metrics or experiment_report.get('baseline_parse_metrics') or {})
    filtered_metrics = _copy_parse_metrics(
        filtered_parse_metrics or experiment_report.get('filtered_parse_metrics') or {})
    removed_by_page = _copy_removed_objects_by_page(
        removed_objects_by_page or experiment_report.get('removed_objects_by_page') or [])

    baseline_tables = _table_delta_records(baseline_metrics)
    filtered_tables = _table_delta_records(filtered_metrics)
    if not enabled:
        return {
            'enabled': False,
            'policy': 'table_delta_investigation_report_only',
            'insertion_point': 'document_parse',
            'summary': _table_delta_disabled_summary(baseline_tables, filtered_tables),
            'baseline_only_tables': [],
            'filtered_only_tables': [],
            'changed_common_tables': [],
            'baseline_only_tables_by_page': [],
            'baseline_only_tables_by_region': {},
            'safety_warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2r': False,
                'reason': 'Table delta investigation is disabled.',
            },
        }

    comparison = _compare_table_records(baseline_tables, filtered_tables)
    removed_objects = [
        raw_object
        for page in removed_by_page
        for raw_object in page.get('objects', []) or []
    ]
    baseline_only = [
        _classify_baseline_only_table(table, removed_objects)
        for table in comparison['baseline_only_tables']
    ]
    filtered_only = comparison['filtered_only_tables']
    changed_common = comparison['changed_common_tables']
    summary = _table_delta_summary(
        baseline_tables,
        filtered_tables,
        baseline_only,
        filtered_only,
        changed_common)
    warnings = _table_delta_warnings(summary, baseline_only, filtered_only, changed_common)

    return {
        'enabled': True,
        'policy': 'table_delta_investigation_report_only',
        'insertion_point': 'document_parse',
        'summary': summary,
        'baseline_only_tables': baseline_only,
        'filtered_only_tables': filtered_only,
        'changed_common_tables': changed_common,
        'baseline_only_tables_by_page': _table_delta_by_page(baseline_only),
        'baseline_only_tables_by_region': _table_delta_by_region(baseline_only),
        'safety_warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2r': _table_delta_safe_for_phase_2r(summary, warnings),
            'reason': _table_delta_recommendation(summary, warnings),
        },
    }


def build_body_table_delta_root_cause_report(
        filtered_parse_experiment_report: dict = None,
        table_delta_report: dict = None,
        baseline_parse_metrics: dict = None,
        filtered_parse_metrics: dict = None,
        removed_objects_by_page: list = None,
        enabled: bool = False) -> dict:
    '''Investigate body/table root causes for unsafe table deltas.'''
    experiment_report = filtered_parse_experiment_report or {}
    baseline_metrics = _copy_parse_metrics(
        baseline_parse_metrics or experiment_report.get('baseline_parse_metrics') or {})
    filtered_metrics = _copy_parse_metrics(
        filtered_parse_metrics or experiment_report.get('filtered_parse_metrics') or {})
    removed_by_page = _copy_removed_objects_by_page(
        removed_objects_by_page or experiment_report.get('removed_objects_by_page') or [])
    removed_objects = [
        raw_object
        for page in removed_by_page
        for raw_object in page.get('objects', []) or []
    ]
    delta_report = table_delta_report or build_table_delta_investigation_report(
        filtered_parse_experiment_report=experiment_report,
        baseline_parse_metrics=baseline_metrics,
        filtered_parse_metrics=filtered_metrics,
        removed_objects_by_page=removed_by_page,
        enabled=bool(enabled))

    if not enabled:
        return {
            'enabled': False,
            'policy': 'body_table_delta_root_cause_report_only',
            'insertion_point': 'document_parse',
            'summary': _body_table_root_disabled_summary(delta_report),
            'baseline_only_findings': [],
            'changed_common_findings': [],
            'overlap_proximity_summary': {},
            'safety_warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2s': False,
                'reason': 'Body table delta root-cause investigation is disabled.',
            },
        }

    baseline_only_findings = [
        _body_table_root_baseline_only_finding(table, removed_objects)
        for table in delta_report.get('baseline_only_tables', []) or []
    ]
    changed_common_findings = [
        _body_table_root_changed_common_finding(change, removed_objects)
        for change in delta_report.get('changed_common_tables', []) or []
    ]
    findings = baseline_only_findings + changed_common_findings
    summary = _body_table_root_summary(
        baseline_only_findings,
        changed_common_findings)
    warnings = _body_table_root_warnings(summary, findings)

    return {
        'enabled': True,
        'policy': 'body_table_delta_root_cause_report_only',
        'insertion_point': 'document_parse',
        'summary': summary,
        'baseline_only_findings': baseline_only_findings,
        'changed_common_findings': changed_common_findings,
        'overlap_proximity_summary': _body_table_root_overlap_summary(findings),
        'safety_warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2s': _body_table_root_safe_for_phase_2s(summary, warnings),
            'reason': _body_table_root_recommendation(summary, warnings),
        },
    }


def build_body_table_geometry_delta_safety_report(
        filtered_parse_experiment_report: dict = None,
        table_delta_report: dict = None,
        body_table_root_cause_report: dict = None,
        baseline_parse_metrics: dict = None,
        filtered_parse_metrics: dict = None,
        removed_objects_by_page: list = None,
        enabled: bool = False) -> dict:
    '''Evaluate changed body table geometries without changing table parsing.'''
    experiment_report = filtered_parse_experiment_report or {}
    baseline_metrics = _copy_parse_metrics(
        baseline_parse_metrics or experiment_report.get('baseline_parse_metrics') or {})
    filtered_metrics = _copy_parse_metrics(
        filtered_parse_metrics or experiment_report.get('filtered_parse_metrics') or {})
    removed_by_page = _copy_removed_objects_by_page(
        removed_objects_by_page or experiment_report.get('removed_objects_by_page') or [])
    delta_report = table_delta_report or build_table_delta_investigation_report(
        filtered_parse_experiment_report=experiment_report,
        baseline_parse_metrics=baseline_metrics,
        filtered_parse_metrics=filtered_metrics,
        removed_objects_by_page=removed_by_page,
        enabled=bool(enabled))
    root_report = body_table_root_cause_report or build_body_table_delta_root_cause_report(
        filtered_parse_experiment_report=experiment_report,
        table_delta_report=delta_report,
        baseline_parse_metrics=baseline_metrics,
        filtered_parse_metrics=filtered_metrics,
        removed_objects_by_page=removed_by_page,
        enabled=bool(enabled))

    if not enabled:
        return {
            'enabled': False,
            'policy': 'body_table_geometry_delta_safety_report_only',
            'insertion_point': 'document_parse',
            'summary': _body_table_geometry_disabled_summary(root_report),
            'findings': [],
            'safety_warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2t': False,
                'reason': 'Body table geometry delta safety investigation is disabled.',
            },
        }

    body_changes = [
        change for change in delta_report.get('changed_common_tables', []) or []
        if change.get('region') == REGION_BODY
    ]
    removed_objects = [
        raw_object
        for page in removed_by_page
        for raw_object in page.get('objects', []) or []
    ]
    findings = [
        _body_table_geometry_finding(change, removed_objects)
        for change in body_changes
    ]
    summary = _body_table_geometry_summary(findings)
    warnings = _body_table_geometry_warnings(summary, findings)

    return {
        'enabled': True,
        'policy': 'body_table_geometry_delta_safety_report_only',
        'insertion_point': 'document_parse',
        'summary': summary,
        'findings': findings,
        'safety_warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2t': _body_table_geometry_safe_for_phase_2t(summary, warnings),
            'reason': _body_table_geometry_recommendation(summary, warnings),
        },
    }


def build_table_geometry_visual_review_pack(
        body_table_geometry_delta_safety_report: dict = None,
        visual_artifacts: list = None,
        visual_rendering: dict = None,
        enabled: bool = False) -> dict:
    '''Build local-only review data for changed body table geometries.'''
    safety_report = body_table_geometry_delta_safety_report or {}
    rendering = dict(visual_rendering or {})
    artifacts = [
        dict(artifact) for artifact in visual_artifacts or []
    ]
    if not enabled:
        return {
            'enabled': False,
            'policy': 'table_geometry_visual_review_pack_local_only',
            'summary': _table_geometry_visual_review_disabled_summary(safety_report),
            'review_items': [],
            'visual_rendering': _table_geometry_visual_rendering_summary(
                rendering,
                artifacts),
            'safety_warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2u': False,
                'reason': 'Table geometry visual review pack generation is disabled.',
            },
        }

    findings = [
        dict(finding) for finding in safety_report.get('findings', []) or []
    ]
    artifact_map = _table_geometry_visual_artifact_map(artifacts)
    review_items = [
        _table_geometry_visual_review_item(index, finding, artifact_map)
        for index, finding in enumerate(findings, start=1)
    ]
    rendering_summary = _table_geometry_visual_rendering_summary(
        rendering,
        artifacts)
    summary = _table_geometry_visual_review_summary(
        review_items,
        rendering_summary)
    warnings = _table_geometry_visual_review_warnings(
        summary,
        rendering_summary,
        safety_report)

    return {
        'enabled': True,
        'policy': 'table_geometry_visual_review_pack_local_only',
        'source_policy': safety_report.get('policy', ''),
        'summary': summary,
        'review_items': review_items,
        'visual_rendering': rendering_summary,
        'safety_warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2u': _table_geometry_visual_review_safe_for_phase_2u(summary, warnings),
            'reason': _table_geometry_visual_review_recommendation(summary, warnings),
        },
    }


def build_table_geometry_visual_approval_gate_report(
        visual_review_decisions: dict = None,
        visual_review_markdown: str = None,
        table_geometry_visual_review_pack: dict = None,
        expected_review_item_count: int = 8,
        enabled: bool = False) -> dict:
    '''Validate human approvals for table geometry review items.'''
    if visual_review_decisions is not None:
        decisions = _copy_table_visual_decisions(visual_review_decisions)
    elif visual_review_markdown is not None:
        decisions = parse_table_geometry_visual_review_markdown(visual_review_markdown)
    else:
        decisions = _table_visual_decisions_from_pack(table_geometry_visual_review_pack)

    if not enabled:
        return {
            'enabled': False,
            'policy': 'table_geometry_visual_approval_gate_report_only',
            'summary': _table_geometry_visual_gate_disabled_summary(
                decisions,
                expected_review_item_count),
            'items': [],
            'blocking_reasons': [],
            'gate_status': 'blocked',
            'recommendation': {
                'safe_to_attempt_phase_2v': False,
                'reason': 'Table geometry visual approval gate is disabled.',
            },
        }

    items = [
        dict(item) for item in decisions.get('items', []) or []
    ]
    summary = _table_geometry_visual_gate_summary(
        items,
        expected_review_item_count)
    blocking_reasons = _table_geometry_visual_gate_blocking_reasons(summary)
    gate_status = 'passed' if not blocking_reasons else 'blocked'
    summary['gate_status'] = gate_status

    return {
        'enabled': True,
        'policy': 'table_geometry_visual_approval_gate_report_only',
        'summary': summary,
        'items': items,
        'blocking_reasons': blocking_reasons,
        'gate_status': gate_status,
        'recommendation': {
            'safe_to_attempt_phase_2v': gate_status == 'passed',
            'reason': _table_geometry_visual_gate_recommendation(gate_status, blocking_reasons),
        },
    }


def build_filtered_docx_generation_comparison_report(
        filtered_parse_experiment_report: dict = None,
        table_visual_approval_gate_report: dict = None,
        baseline_docx_path: str = '',
        filtered_docx_path: str = '',
        baseline_docx_metrics: dict = None,
        filtered_docx_metrics: dict = None,
        normal_conversion_check: dict = None,
        body_serialization_residual_check: dict = None,
        enabled: bool = False) -> dict:
    '''Build a report for a local-only filtered DOCX generation experiment.'''
    experiment_report = filtered_parse_experiment_report or {}
    gate_report = table_visual_approval_gate_report or {}
    baseline_metrics = dict(baseline_docx_metrics or {})
    filtered_metrics = dict(filtered_docx_metrics or {})
    normal_check = dict(normal_conversion_check or {})
    residual_check = dict(body_serialization_residual_check or {})

    if not enabled:
        return {
            'enabled': False,
            'policy': 'filtered_docx_generation_comparison_local_only',
            'summary': _filtered_docx_disabled_summary(
                baseline_docx_path,
                filtered_docx_path,
                experiment_report,
                gate_report),
            'docx_files': _filtered_docx_files_report(
                baseline_docx_path,
                filtered_docx_path,
                baseline_metrics,
                filtered_metrics),
            'safety_warnings': [],
            'gate_report': _filtered_docx_gate_summary(gate_report),
            'body_serialization_residual_check': residual_check,
            'normal_conversion_check': normal_check,
            'recommendation': {
                'safe_to_attempt_phase_2w': False,
                'reason': 'Filtered DOCX generation comparison is disabled.',
            },
        }

    summary = _filtered_docx_summary(
        experiment_report,
        gate_report,
        baseline_metrics,
        filtered_metrics,
        normal_check)
    docx_files = _filtered_docx_files_report(
        baseline_docx_path,
        filtered_docx_path,
        baseline_metrics,
        filtered_metrics)
    warnings = _filtered_docx_warnings(
        summary,
        docx_files,
        gate_report,
        normal_check)

    return {
        'enabled': True,
        'policy': 'filtered_docx_generation_comparison_local_only',
        'summary': summary,
        'docx_files': docx_files,
        'gate_report': _filtered_docx_gate_summary(gate_report),
        'header_footer_pollution_reduction': dict(
            experiment_report.get('header_footer_pollution_reduction') or {}),
        'body_serialization_residual_check': residual_check,
        'normal_conversion_check': normal_check,
        'safety_warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2w': _filtered_docx_safe_for_phase_2w(summary, warnings),
            'reason': _filtered_docx_recommendation(summary, warnings),
        },
    }


def build_filtered_docx_residual_structure_report(
        baseline_docx_path: str = '',
        filtered_docx_path: str = '',
        removed_strings: list = None,
        enabled: bool = False) -> dict:
    '''Inspect filtered DOCX residual removed text and OpenXML structure.'''
    removed = _normalize_removed_strings(removed_strings or [])
    baseline = _inspect_docx_openxml(baseline_docx_path, removed)
    filtered = _inspect_docx_openxml(filtered_docx_path, removed)

    if not enabled:
        return {
            'enabled': False,
            'policy': 'filtered_docx_residual_structure_report_only',
            'summary': _filtered_docx_residual_disabled_summary(
                baseline,
                filtered,
                removed),
            'baseline_docx': baseline,
            'filtered_docx': filtered,
            'residuals': [],
            'safety_warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2x': False,
                'reason': 'Filtered DOCX residual structure inspection is disabled.',
            },
        }

    residuals = _filtered_docx_residual_items(baseline, filtered, removed)
    summary = _filtered_docx_residual_summary(baseline, filtered, removed, residuals)
    warnings = _filtered_docx_residual_warnings(baseline, filtered, summary, residuals)

    return {
        'enabled': True,
        'policy': 'filtered_docx_residual_structure_report_only',
        'summary': summary,
        'baseline_docx': baseline,
        'filtered_docx': filtered,
        'residuals': residuals,
        'safety_warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2x': _filtered_docx_residual_safe_for_phase_2x(summary, warnings),
            'reason': _filtered_docx_residual_recommendation(summary, warnings),
        },
    }


def build_reviewed_filtering_feature_readiness_report(
        header_footer_review_report: dict = None,
        raw_object_mapping_report: dict = None,
        filtered_parse_experiment_report: dict = None,
        table_visual_approval_gate_report: dict = None,
        body_table_geometry_delta_safety_report: dict = None,
        filtered_docx_comparison_report: dict = None,
        docx_residual_structure_report: dict = None,
        verification_status: dict = None,
        evidence_overrides: dict = None,
        enabled: bool = False) -> dict:
    '''Aggregate prior report evidence into an internal readiness gate.'''
    evidence = _reviewed_filtering_readiness_evidence(
        header_footer_review_report,
        raw_object_mapping_report,
        filtered_parse_experiment_report,
        table_visual_approval_gate_report,
        body_table_geometry_delta_safety_report,
        filtered_docx_comparison_report,
        docx_residual_structure_report,
        verification_status,
        evidence_overrides)

    if not enabled:
        return {
            'enabled': False,
            'policy': 'reviewed_filtering_feature_readiness_gate_report_only',
            'readiness_status': 'blocked',
            'evidence_summary': evidence,
            'blocking_reasons': [{
                'type': 'readiness_gate_disabled',
                'message': 'Feature readiness gate is disabled.',
            }],
            'non_blocking_risks': _reviewed_filtering_non_blocking_risks(evidence),
            'required_synthetic_fixture_coverage': _reviewed_filtering_fixture_coverage(),
            'recommendation': {
                'safe_to_attempt_phase_2y': False,
                'reason': 'Enable the internal readiness gate before attempting Phase 2Y.',
            },
        }

    blocking_reasons = _reviewed_filtering_readiness_blocking_reasons(evidence)
    non_blocking_risks = _reviewed_filtering_non_blocking_risks(evidence)
    readiness_status = (
        'ready_for_internal_opt_in_integration_experiment'
        if not blocking_reasons else
        'blocked')

    return {
        'enabled': True,
        'policy': 'reviewed_filtering_feature_readiness_gate_report_only',
        'readiness_status': readiness_status,
        'evidence_summary': evidence,
        'blocking_reasons': blocking_reasons,
        'non_blocking_risks': non_blocking_risks,
        'required_synthetic_fixture_coverage': _reviewed_filtering_fixture_coverage(),
        'recommendation': {
            'safe_to_attempt_phase_2y': readiness_status != 'blocked',
            'reason': _reviewed_filtering_readiness_recommendation(
                readiness_status,
                blocking_reasons,
                non_blocking_risks),
        },
    }


def build_local_corpus_validation_summary_report(
        sample_results: list = None,
        enabled: bool = False,
        large_page_threshold: int = 100) -> dict:
    '''Summarize local-only corpus diagnostics without approving removals.'''
    if not enabled:
        return {
            'enabled': False,
            'policy': 'local_corpus_validation_report_only',
            'summary': _corpus_validation_empty_summary(),
            'samples': [],
            'warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2y1': False,
                'reason': 'Local corpus validation is disabled.',
            },
        }

    samples = [
        _corpus_sample_summary(sample, large_page_threshold)
        for sample in sample_results or []
    ]
    summary = _corpus_validation_summary(samples)
    warnings = _corpus_validation_warnings(samples)
    return {
        'enabled': True,
        'policy': 'local_corpus_validation_report_only',
        'summary': summary,
        'samples': samples,
        'warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2y1': summary['samples_analyzed_successfully'] > 0,
            'reason': _corpus_validation_recommendation(summary, warnings),
        },
    }


def build_local_corpus_manual_review_pack(
        sample_result: dict = None,
        enabled: bool = False) -> dict:
    '''Build local-only manual review data for one corpus sample.'''
    sample = sample_result or {}
    if not enabled:
        return {
            'enabled': False,
            'policy': 'local_corpus_manual_review_pack_only',
            'summary': _corpus_manual_review_disabled_summary(sample),
            'review_items': [],
            'warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2y2': False,
                'reason': 'Corpus manual review pack generation is disabled.',
            },
        }

    missing_inputs = []
    if not sample_result:
        missing_inputs.append('corpus_sample_report')
    layout_report = sample.get('layout_analysis_report') or {}
    if not layout_report:
        missing_inputs.append('layout_analysis_report')

    items = _corpus_manual_review_items(layout_report) if layout_report else []
    summary = _corpus_manual_review_pack_summary(sample, items, missing_inputs)
    warnings = _corpus_manual_review_pack_warnings(summary, missing_inputs)
    return {
        'enabled': True,
        'policy': 'local_corpus_manual_review_pack_only',
        'sample_name': summary.get('sample_name', ''),
        'summary': summary,
        'review_items': items,
        'warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2y2': bool(
                summary.get('ready_for_human_approval', False)),
            'reason': _corpus_manual_review_pack_recommendation(summary, warnings),
        },
    }


def build_local_corpus_manual_review_summary_report(
        review_packs: list = None,
        enabled: bool = False) -> dict:
    '''Summarize selected local corpus manual review packs.'''
    if not enabled:
        return {
            'enabled': False,
            'policy': 'local_corpus_manual_review_summary_only',
            'summary': _corpus_manual_review_summary_empty(),
            'samples': [],
            'warnings': [],
            'recommendation': {
                'safe_to_attempt_phase_2y2': False,
                'reason': 'Corpus manual review summary is disabled.',
            },
        }

    samples = [
        _corpus_manual_review_sample_row(pack)
        for pack in review_packs or []
    ]
    summary = _corpus_manual_review_summary(samples)
    warnings = _corpus_manual_review_summary_warnings(samples)
    return {
        'enabled': True,
        'policy': 'local_corpus_manual_review_summary_only',
        'summary': summary,
        'samples': samples,
        'warnings': warnings,
        'recommendation': {
            'safe_to_attempt_phase_2y2': bool(summary.get('review_packs_ready_count', 0)),
            'reason': _corpus_manual_review_summary_recommendation(summary, warnings),
        },
    }


def build_local_corpus_approval_validation_report(
        layout_analysis_report: dict = None,
        review_decisions=None,
        sample_name: str = '',
        bounded_analysis_only: bool = False,
        full_docx_validation_allowed: bool = False,
        enabled: bool = False) -> dict:
    '''Validate local corpus review approvals without enabling production filtering.'''
    if not enabled:
        return {
            'enabled': False,
            'policy': 'local_corpus_approval_validation_report_only',
            'sample_name': sample_name,
            'summary': _corpus_approval_disabled_summary(
                sample_name,
                bounded_analysis_only,
                full_docx_validation_allowed),
            'candidates': [],
            'filtering_report': {},
            'warnings': [],
            'recommendation': {
                'safe_to_run_approved_only_validation': False,
                'reason': 'Local corpus approval validation is disabled.',
            },
        }

    layout_report = layout_analysis_report or {}
    dry_run = layout_report.get('header_footer_exclusion_dry_run') or {}
    page_summaries = layout_report.get('pages') or []
    decisions = review_decisions or {}
    filtering_report = build_reviewed_header_footer_filter_report(
        page_summaries,
        dry_run,
        decisions,
        enabled=True,
        apply=True)
    candidates = _corpus_approval_candidate_rows(dry_run, decisions, filtering_report)
    summary = _corpus_approval_summary(
        sample_name,
        bounded_analysis_only,
        full_docx_validation_allowed,
        candidates,
        filtering_report)
    warnings = _corpus_approval_warnings(summary)
    return {
        'enabled': True,
        'policy': 'local_corpus_approval_validation_report_only',
        'sample_name': sample_name,
        'summary': summary,
        'candidates': candidates,
        'filtering_report': filtering_report,
        'warnings': warnings,
        'recommendation': {
            'safe_to_run_approved_only_validation': bool(
                summary.get('explicit_decisions_complete') and
                summary.get('eligible_approved_candidate_count', 0) > 0 and
                summary.get('unsafe_removed_count', 0) == 0),
            'reason': _corpus_approval_recommendation(summary, warnings),
        },
    }


def build_local_corpus_approval_validation_summary_report(
        validation_reports: list = None,
        enabled: bool = False) -> dict:
    '''Summarize local corpus approval validation reports.'''
    if not enabled:
        return {
            'enabled': False,
            'policy': 'local_corpus_approval_validation_summary_only',
            'summary': _corpus_approval_summary_empty(),
            'samples': [],
            'warnings': [],
            'recommendation': {
                'safe_to_attempt_committed_synthetic_fixtures': False,
                'reason': 'Local corpus approval validation summary is disabled.',
            },
        }

    samples = [
        _corpus_approval_summary_row(report)
        for report in validation_reports or []
    ]
    summary = _corpus_approval_validation_summary(samples)
    warnings = _corpus_approval_summary_warnings(samples)
    return {
        'enabled': True,
        'policy': 'local_corpus_approval_validation_summary_only',
        'summary': summary,
        'samples': samples,
        'warnings': warnings,
        'recommendation': {
            'safe_to_attempt_committed_synthetic_fixtures': bool(
                summary.get('samples_validated_count', 0)),
            'reason': _corpus_approval_summary_recommendation(summary, warnings),
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


def _parse_table_visual_human_decision(text: str) -> tuple:
    checked = [
        name.lower() for name, marker in _TABLE_VISUAL_DECISION_RE.findall(text or '')
        if normalize_text(marker).lower() == 'x'
    ]
    if len(checked) == 1:
        return checked[0], checked
    if not checked:
        return DECISION_NONE, checked
    return DECISION_CONFLICT, checked


def _parse_count_pair(text: str) -> tuple:
    match = _COUNT_PAIR_RE.search(text or '')
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _parse_bool(text: str) -> bool:
    return normalize_text(text).lower() in {'true', 'yes', '1'}


def _table_visual_counts_preserved(item: dict) -> bool:
    return (
        item.get('row_count_before') is not None and
        item.get('row_count_before') == item.get('row_count_after') and
        item.get('column_count_before') is not None and
        item.get('column_count_before') == item.get('column_count_after') and
        item.get('cell_count_before') is not None and
        item.get('cell_count_before') == item.get('cell_count_after'))


def _default_reviewed_filtering_internal_config() -> dict:
    return {
        'enabled': False,
        'mode': REVIEWED_FILTERING_MODE_DRY_RUN,
        'review_decisions_path': '',
        'review_decisions': None,
        'require_explicit_approval': True,
        'allow_raw_would_exclude': False,
        'allow_unsure': False,
        'allow_rejected': False,
        'protect_body_region': True,
        'protect_layout_placeholders': True,
        'collect_diagnostics': True,
        'write_local_reports': False,
        'max_pages': None,
        'page_subset': [],
        'fail_closed_on_warning': True,
    }


def _default_reviewed_header_footer_migration_profile() -> dict:
    return {
        'enabled': False,
        'parse_mode': REVIEWED_FILTERING_MODE_FILTERED_PARSE_EXPERIMENT,
        'review_decisions_path': '',
        'review_decisions': None,
        'require_explicit_approval': True,
        'allow_raw_would_exclude': False,
        'allow_rejected': False,
        'allow_unsure': False,
        'protect_body_region': True,
        'protect_layout_placeholders': True,
        'header_footer_policy_required': MIGRATION_PROFILE_REQUIRED_POLICY,
        'allow_non_default_policy': False,
        'page_number_behavior': PAGE_NUMBER_BEHAVIOR_PLACEHOLDER_ONLY,
        'page_number_behavior_explicitly_requested': False,
        'require_dynamic_page_number': False,
        'body_signature_gate': MIGRATION_PROFILE_BODY_SIGNATURE_GATE,
        'strict_exact_fragment_gate': MIGRATION_PROFILE_STRICT_EXACT_FRAGMENT_GATE,
        'fail_closed_on': list(MIGRATION_PROFILE_FAIL_CLOSED_ON),
        'local_output_policy': MIGRATION_PROFILE_LOCAL_OUTPUT_POLICY,
        'public_exposure': MIGRATION_PROFILE_PUBLIC_EXPOSURE,
        'public_cli_exposed': False,
        'public_api_exposed': False,
        'production_default_enabled': False,
        'default_conversion_changed': False,
        'collect_diagnostics': True,
        'write_local_reports': False,
        'max_pages': None,
        'page_subset': [],
        'fail_closed_on_warning': True,
    }


def _reviewed_header_footer_migration_profile_payload(
        config: dict = None,
        overrides: dict = None) -> dict:
    config = dict(config or {})
    overrides = dict(overrides or {})
    merged = _default_reviewed_header_footer_migration_profile()
    merged.update(config)
    merged.update(overrides)

    explicit_page_number = (
        'page_number_behavior' in config or
        'page_number_behavior' in overrides or
        bool(merged.get('page_number_behavior_explicitly_requested', False)))
    page_number_behavior = _normalize_docx_page_number_behavior(
        merged.get('page_number_behavior'))
    if page_number_behavior != PAGE_NUMBER_BEHAVIOR_WORD_FIELD:
        explicit_page_number = bool(
            explicit_page_number and
            page_number_behavior != PAGE_NUMBER_BEHAVIOR_PLACEHOLDER_ONLY)

    page_subset = merged.get('page_subset', [])
    if page_subset is None:
        page_subset = []
    elif isinstance(page_subset, (tuple, set)):
        page_subset = list(page_subset)
    elif not isinstance(page_subset, list):
        page_subset = [page_subset]

    max_pages = merged.get('max_pages')
    if max_pages in ('', None):
        max_pages = None
    else:
        max_pages = _reviewed_filtering_config_int_or_none(max_pages)

    fail_closed_on = _migration_profile_fail_closed_on(
        merged.get('fail_closed_on'))

    return {
        'enabled': bool(merged.get('enabled', False)),
        'parse_mode': normalize_text(
            merged.get('parse_mode') or
            REVIEWED_FILTERING_MODE_FILTERED_PARSE_EXPERIMENT),
        'review_decisions_path': normalize_text(
            merged.get('review_decisions_path', '')),
        'review_decisions': merged.get('review_decisions'),
        'require_explicit_approval': bool(
            merged.get('require_explicit_approval', True)),
        'allow_raw_would_exclude': bool(
            merged.get('allow_raw_would_exclude', False)),
        'allow_rejected': bool(merged.get('allow_rejected', False)),
        'allow_unsure': bool(merged.get('allow_unsure', False)),
        'protect_body_region': bool(merged.get('protect_body_region', True)),
        'protect_layout_placeholders': bool(
            merged.get('protect_layout_placeholders', True)),
        'header_footer_policy_required': normalize_text(
            merged.get('header_footer_policy_required') or
            MIGRATION_PROFILE_REQUIRED_POLICY),
        'allow_non_default_policy': bool(
            merged.get('allow_non_default_policy', False)),
        'page_number_behavior': page_number_behavior,
        'page_number_behavior_explicitly_requested': bool(explicit_page_number),
        'require_dynamic_page_number': bool(
            merged.get('require_dynamic_page_number', False)),
        'body_signature_gate': normalize_text(
            merged.get('body_signature_gate') or
            MIGRATION_PROFILE_BODY_SIGNATURE_GATE),
        'strict_exact_fragment_gate': normalize_text(
            merged.get('strict_exact_fragment_gate') or
            MIGRATION_PROFILE_STRICT_EXACT_FRAGMENT_GATE),
        'fail_closed_on': fail_closed_on,
        'local_output_policy': normalize_text(
            merged.get('local_output_policy') or
            MIGRATION_PROFILE_LOCAL_OUTPUT_POLICY),
        'public_exposure': normalize_text(
            merged.get('public_exposure') or
            MIGRATION_PROFILE_PUBLIC_EXPOSURE),
        'public_cli_exposed': bool(merged.get('public_cli_exposed', False)),
        'public_api_exposed': bool(merged.get('public_api_exposed', False)),
        'production_default_enabled': bool(
            merged.get('production_default_enabled', False)),
        'default_conversion_changed': bool(
            merged.get('default_conversion_changed', False)),
        'collect_diagnostics': bool(merged.get('collect_diagnostics', True)),
        'write_local_reports': bool(merged.get('write_local_reports', False)),
        'max_pages': max_pages,
        'page_subset': page_subset,
        'fail_closed_on_warning': bool(
            merged.get('fail_closed_on_warning', True)),
    }


def _reviewed_header_footer_migration_profile_from_input(profile: dict = None) -> dict:
    profile = profile or {}
    if isinstance(profile, dict) and 'profile' in profile:
        profile = profile.get('profile') or {}
    return _reviewed_header_footer_migration_profile_payload(profile)


def _migration_profile_fail_closed_on(value) -> list:
    if value in (None, ''):
        values = list(MIGRATION_PROFILE_FAIL_CLOSED_ON)
    elif isinstance(value, str):
        values = [normalize_text(value)]
    else:
        values = [normalize_text(item) for item in value or []]

    result = []
    for item in values:
        if item and item not in result:
            result.append(item)
    return result


def _migration_profile_reviewed_filtering_config(profile: dict) -> dict:
    return build_reviewed_filtering_internal_config({
        'enabled': bool(profile.get('enabled', False)),
        'mode': profile.get('parse_mode'),
        'review_decisions_path': profile.get('review_decisions_path', ''),
        'review_decisions': profile.get('review_decisions'),
        'require_explicit_approval': profile.get('require_explicit_approval', True),
        'allow_raw_would_exclude': profile.get('allow_raw_would_exclude', False),
        'allow_rejected': profile.get('allow_rejected', False),
        'allow_unsure': profile.get('allow_unsure', False),
        'protect_body_region': profile.get('protect_body_region', True),
        'protect_layout_placeholders': profile.get(
            'protect_layout_placeholders', True),
        'collect_diagnostics': profile.get('collect_diagnostics', True),
        'write_local_reports': profile.get('write_local_reports', False),
        'max_pages': profile.get('max_pages'),
        'page_subset': list(profile.get('page_subset', []) or []),
        'fail_closed_on_warning': profile.get('fail_closed_on_warning', True),
    })


def _migration_profile_docx_plan_requirements(profile: dict) -> dict:
    return {
        'enabled': bool(profile.get('enabled', False)),
        'plan_helper': 'build_docx_header_footer_generation_plan',
        'required_policy_type': profile.get('header_footer_policy_required', ''),
        'allow_non_default_policy': bool(
            profile.get('allow_non_default_policy', False)),
        'page_number_behavior': profile.get('page_number_behavior', ''),
        'require_dynamic_page_number': bool(
            profile.get('require_dynamic_page_number', False)),
        'body_region_candidates_protected': bool(
            profile.get('protect_body_region', True)),
        'layout_placeholders_protected': bool(
            profile.get('protect_layout_placeholders', True)),
        'requires_explicit_review_approval': bool(
            profile.get('require_explicit_approval', True)),
    }


def _migration_profile_writer_settings(profile: dict) -> dict:
    return {
        'enabled': bool(profile.get('enabled', False)),
        'writer_helper': 'apply_header_footer_text_plan',
        'allowed_policy_type': profile.get('header_footer_policy_required', ''),
        'allow_non_default_policy': bool(
            profile.get('allow_non_default_policy', False)),
        'page_number_behavior': profile.get('page_number_behavior', ''),
        'page_number_behavior_explicitly_requested': bool(
            profile.get('page_number_behavior_explicitly_requested', False)),
        'simple_default_writer_only': True,
    }


def _migration_profile_gate_expectations(profile: dict) -> dict:
    return {
        'body_signature_gate': profile.get('body_signature_gate', ''),
        'primary_body_gate': MIGRATION_PROFILE_BODY_SIGNATURE_GATE,
        'strict_exact_fragment_gate': profile.get(
            'strict_exact_fragment_gate', ''),
        'strict_exact_fragment_gate_blocks': False,
        'fail_closed_on': list(profile.get('fail_closed_on', []) or []),
        'local_output_policy': profile.get('local_output_policy', ''),
    }


def _extend_profile_filtering_config_warnings(
        warnings: list,
        profile: dict,
        reviewed_filtering_config: dict):
    if not reviewed_filtering_config:
        return

    expected = _migration_profile_reviewed_filtering_config(profile)
    comparisons = (
        ('enabled', 'reviewed_filtering_config_enabled_mismatch'),
        ('mode', 'reviewed_filtering_config_mode_mismatch'),
        ('require_explicit_approval', 'reviewed_filtering_config_approval_gate_mismatch'),
        ('allow_raw_would_exclude', 'reviewed_filtering_config_raw_gate_mismatch'),
        ('allow_rejected', 'reviewed_filtering_config_rejected_gate_mismatch'),
        ('allow_unsure', 'reviewed_filtering_config_unsure_gate_mismatch'),
        ('protect_body_region', 'reviewed_filtering_config_body_protection_mismatch'),
        ('protect_layout_placeholders', 'reviewed_filtering_config_placeholder_protection_mismatch'),
    )
    for key, warning_type in comparisons:
        if reviewed_filtering_config.get(key) != expected.get(key):
            warnings.append({
                'type': warning_type,
                'expected': expected.get(key),
                'actual': reviewed_filtering_config.get(key),
            })


def _extend_profile_docx_plan_warnings(
        warnings: list,
        diagnostics: list,
        profile: dict,
        docx_header_footer_plan: dict):
    if not docx_header_footer_plan:
        return

    plan = docx_header_footer_plan or {}
    policy = plan.get('header_footer_policy') or {}
    summary = plan.get('summary') or {}
    policy_type = policy.get(
        'policy_type',
        summary.get('header_footer_policy_type', ''))
    if (
            policy_type and
            policy_type != profile.get('header_footer_policy_required') and
            not profile.get('allow_non_default_policy', False)):
        warnings.append({
            'type': 'unsafe_policy',
            'policy_type': policy_type,
        })
    if (
            policy.get('fail_closed') and
            policy_type != profile.get('header_footer_policy_required')):
        warnings.append({
            'type': 'unsafe_policy',
            'reason': 'docx_header_footer_policy_fail_closed',
            'policy_type': policy_type or 'unknown',
        })

    plan_page_behavior = (
        summary.get('page_number_behavior') or
        policy.get('page_number_behavior') or
        PAGE_NUMBER_BEHAVIOR_PLACEHOLDER_ONLY)
    if plan_page_behavior != profile.get('page_number_behavior'):
        warnings.append({
            'type': 'unsafe_page_number_behavior',
            'expected': profile.get('page_number_behavior'),
            'actual': plan_page_behavior,
        })
    for warning in plan.get('safety_warnings', []) or []:
        warning_type = warning.get('type')
        if warning_type in {
                'unsupported_page_number_behavior',
                'dynamic_page_number_field_required'}:
            warnings.append({
                'type': 'unsafe_page_number_behavior',
                'source_warning': warning_type,
            })
        elif warning_type in {
                'first_page_docx_header_footer_writing_deferred',
                'odd_even_docx_header_footer_writing_deferred',
                'section_scoped_docx_header_footer_mapping_deferred',
                'ambiguous_header_footer_policy'}:
            warnings.append({
                'type': 'unsafe_policy',
                'source_warning': warning_type,
            })
        else:
            diagnostics.append({
                'type': 'docx_header_footer_plan_diagnostic',
                'source_warning': warning_type,
            })


def _extend_profile_migration_gate_warnings(
        warnings: list,
        diagnostics: list,
        migration_gate_report: dict):
    if not migration_gate_report:
        return

    summary = migration_gate_report.get('summary') or {}
    normalized_gate_passed = bool(
        summary.get('normalized_body_signature_gate_passed', False))
    strict_gate_passed = bool(
        summary.get('strict_exact_fragment_gate_passed', False))
    if normalized_gate_passed and not strict_gate_passed:
        diagnostics.append({
            'type': 'strict_exact_fragment_mismatch_diagnostic_only',
            'strict_missing_fragment_count': int(
                summary.get('strict_missing_fragment_count', 0) or 0),
        })
    if not normalized_gate_passed:
        warnings.append({'type': 'true_body_text_loss'})

    for count_key, warning_type in (
            ('true_body_text_loss_count', 'true_body_text_loss'),
            ('table_text_loss_count', 'table_text_loss'),
            ('callout_text_loss_count', 'callout_text_loss'),
            ('list_text_loss_count', 'list_text_loss')):
        if int(summary.get(count_key, 0) or 0):
            warnings.append({
                'type': warning_type,
                'count': int(summary.get(count_key, 0) or 0),
            })
    residual_count = int(
        summary.get(
            'true_residual_header_footer_pollution_count',
            summary.get('body_residual_header_footer_pollution_count', 0)) or 0)
    if residual_count:
        warnings.append({
            'type': 'residual_header_footer_pollution',
            'count': residual_count,
        })
    for warning in migration_gate_report.get('safety_warnings', []) or []:
        warning_type = warning.get('type')
        if warning_type in {
                'true_body_text_loss',
                'table_text_loss',
                'callout_text_loss',
                'list_text_loss',
                'true_residual_header_footer_pollution',
                'residual_header_footer_pollution',
                'missing_docx_body_signature_evidence',
                'raw_body_signature_not_preserved'}:
            warnings.append({
                'type': (
                    'residual_header_footer_pollution'
                    if warning_type == 'true_residual_header_footer_pollution' else
                    warning_type),
            })


def _reviewed_header_footer_migration_profile_recommendation(
        status: str,
        warnings: list) -> str:
    if status == 'disabled':
        return 'Reviewed header/footer migration profile remains disabled by default.'
    if status == 'ready_for_internal_migration_profile':
        return 'Internal migration profile is ready for a private default-policy experiment only.'
    warning_types = sorted({warning.get('type') for warning in warnings or []})
    return f'Internal migration profile is fail-closed; resolve warnings first: {warning_types}.'


def _reviewed_filtering_config_int_or_none(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _reviewed_filtering_config_candidate_rows(
        candidates: list,
        review_decisions,
        config: dict) -> list:
    decision_map = _review_decision_map(review_decisions)
    return [
        _reviewed_filtering_config_candidate_row(candidate, decision_map, config)
        for candidate in candidates or []
    ]


def _reviewed_filtering_config_candidate_row(
        candidate: dict,
        decision_map: dict,
        config: dict) -> dict:
    decision = (
        decision_map.get(candidate.get('fingerprint')) or
        decision_map.get(candidate.get('candidate_id')) or
        DECISION_NONE)
    eligible, reason = _reviewed_filtering_config_candidate_allowed(
        candidate,
        decision,
        config)
    return {
        'candidate_id': candidate.get('candidate_id', ''),
        'fingerprint': candidate.get('fingerprint', ''),
        'proposed_role': candidate.get('proposed_role', ''),
        'action': candidate.get('action', ''),
        'region': candidate.get('region', ''),
        'regions': list(candidate.get('regions', []) or []),
        'manual_decision': decision,
        'eligible_for_reviewed_filtering': bool(eligible),
        'blocked_reason': '' if eligible else reason,
        'support_count': _readiness_int(candidate.get('support_count', 0)),
        'page_count': _readiness_int(candidate.get('page_count', 0)),
        'affected_pages': list(candidate.get('affected_pages', []) or []),
    }


def _reviewed_filtering_config_candidate_allowed(
        candidate: dict,
        decision: str,
        config: dict) -> tuple:
    if not config.get('enabled', False):
        return False, 'config_disabled'
    if config.get('mode') not in REVIEWED_FILTERING_MODES:
        return False, 'invalid_mode'
    if candidate.get('action') != ACTION_WOULD_EXCLUDE:
        return False, 'dry_run_action_not_would_exclude'
    if (
            config.get('protect_body_region', True) and
            _candidate_regions(candidate).intersection({REGION_BODY})):
        return False, 'body_region_protected'
    if (
            config.get('protect_layout_placeholders', True) and
            candidate.get('proposed_role') == ROLE_LAYOUT_PLACEHOLDER):
        return False, 'layout_placeholder_protected'
    if decision == DECISION_REJECT_EXCLUDE and not config.get('allow_rejected', False):
        return False, 'rejected_candidate_blocked'
    if decision == DECISION_UNSURE and not config.get('allow_unsure', False):
        return False, 'unsure_candidate_blocked'
    if decision in {DECISION_NONE, ''} and not config.get('allow_raw_would_exclude', False):
        return False, 'explicit_review_decision_required'
    if (
            config.get('require_explicit_approval', True) and
            decision != DECISION_APPROVE_EXCLUDE):
        return False, 'manual_decision_not_approved'

    role = candidate.get('proposed_role')
    if role not in {ROLE_HEADER, ROLE_FOOTER, ROLE_PAGE_NUMBER}:
        return False, 'role_not_filterable'
    return True, 'approved_review_decision'


def _candidate_regions(candidate: dict) -> set:
    regions = set(candidate.get('regions', []) or [])
    if candidate.get('region'):
        regions.add(candidate.get('region'))
    return regions


def _reviewed_filtering_config_summary(
        config: dict,
        candidate_rows: list,
        review_decisions,
        enabled: bool) -> dict:
    decision_counts = _decision_counts(review_decisions)
    row_decision_counts = Counter(
        row.get('manual_decision', DECISION_NONE)
        for row in candidate_rows or [])
    return {
        'enabled': bool(enabled and config.get('enabled', False)),
        'mode': config.get('mode'),
        'default_enabled': False,
        'public_cli_exposed': False,
        'production_default_enabled': False,
        'require_explicit_approval': bool(config.get('require_explicit_approval', True)),
        'allow_raw_would_exclude': bool(config.get('allow_raw_would_exclude', False)),
        'allow_unsure': bool(config.get('allow_unsure', False)),
        'allow_rejected': bool(config.get('allow_rejected', False)),
        'protect_body_region': bool(config.get('protect_body_region', True)),
        'protect_layout_placeholders': bool(config.get('protect_layout_placeholders', True)),
        'collect_diagnostics': bool(config.get('collect_diagnostics', True)),
        'write_local_reports': bool(config.get('write_local_reports', False)),
        'fail_closed_on_warning': bool(config.get('fail_closed_on_warning', True)),
        'review_decision_count': sum(decision_counts.values()),
        'approve_count': row_decision_counts.get(DECISION_APPROVE_EXCLUDE, 0),
        'reject_count': row_decision_counts.get(DECISION_REJECT_EXCLUDE, 0),
        'unsure_count': row_decision_counts.get(DECISION_UNSURE, 0),
        'none_count': row_decision_counts.get(DECISION_NONE, 0),
        'candidate_count': len(candidate_rows or []),
        'eligible_candidate_count': sum(
            1 for row in candidate_rows or []
            if row.get('eligible_for_reviewed_filtering')),
        'blocked_candidate_count': sum(
            1 for row in candidate_rows or []
            if not row.get('eligible_for_reviewed_filtering')),
        'body_region_candidate_count': sum(
            1 for row in candidate_rows or []
            if REGION_BODY in _candidate_regions(row)),
        'layout_placeholder_candidate_count': sum(
            1 for row in candidate_rows or []
            if row.get('proposed_role') == ROLE_LAYOUT_PLACEHOLDER),
        'max_pages': config.get('max_pages'),
        'page_subset': list(config.get('page_subset', []) or []),
    }


def _reviewed_filtering_config_warnings(
        config: dict,
        summary: dict,
        candidate_rows: list,
        review_decisions,
        enabled: bool) -> list:
    warnings = []
    if not enabled or not config.get('enabled', False):
        warnings.append({'type': 'reviewed_filtering_config_disabled'})
        return warnings
    if config.get('mode') not in REVIEWED_FILTERING_MODES:
        warnings.append({
            'type': 'invalid_reviewed_filtering_mode',
            'mode': config.get('mode'),
        })
    if not review_decisions:
        warnings.append({'type': 'missing_review_decisions'})
    if summary.get('none_count', 0) and not config.get('allow_raw_would_exclude', False):
        warnings.append({
            'type': 'raw_would_exclude_without_approval_blocked',
            'count': summary.get('none_count'),
        })
    if summary.get('reject_count', 0) and not config.get('allow_rejected', False):
        warnings.append({
            'type': 'rejected_candidates_blocked',
            'count': summary.get('reject_count'),
        })
    if summary.get('unsure_count', 0) and not config.get('allow_unsure', False):
        warnings.append({
            'type': 'unsure_candidates_blocked',
            'count': summary.get('unsure_count'),
        })
    if (
            summary.get('body_region_candidate_count', 0) and
            config.get('protect_body_region', True)):
        warnings.append({
            'type': 'body_region_candidates_protected',
            'count': summary.get('body_region_candidate_count'),
        })
    if (
            summary.get('layout_placeholder_candidate_count', 0) and
            config.get('protect_layout_placeholders', True)):
        warnings.append({
            'type': 'layout_placeholder_candidates_protected',
            'count': summary.get('layout_placeholder_candidate_count'),
        })
    if (
            summary.get('eligible_candidate_count', 0) == 0 and
            candidate_rows):
        warnings.append({'type': 'no_eligible_reviewed_filtering_candidates'})
    if config.get('mode') == REVIEWED_FILTERING_MODE_FUTURE_APPLY:
        warnings.append({
            'type': 'future_apply_not_implemented',
            'message': 'Permanent production filtering is intentionally unavailable.',
        })
    return warnings


def _reviewed_filtering_config_activation_status(
        config: dict,
        summary: dict,
        warnings: list,
        enabled: bool) -> str:
    if not enabled or not config.get('enabled', False):
        return 'disabled'
    warning_types = {warning.get('type') for warning in warnings or []}
    blocking = {
        'invalid_reviewed_filtering_mode',
        'missing_review_decisions',
        'raw_would_exclude_without_approval_blocked',
        'future_apply_not_implemented',
    }
    if config.get('fail_closed_on_warning', True) and warning_types:
        return 'blocked'
    if warning_types.intersection(blocking):
        return 'blocked'
    if summary.get('eligible_candidate_count', 0) <= 0:
        return 'blocked'
    return 'ready_for_internal_experiment'


def _reviewed_filtering_config_recommendation(
        activation_status: str,
        warnings: list) -> str:
    if activation_status == 'disabled':
        return 'Reviewed filtering remains disabled by default.'
    if activation_status == 'ready_for_internal_experiment':
        return 'Internal config is ready for a guarded, non-default experiment only.'
    warning_types = sorted({warning.get('type') for warning in warnings or []})
    return f'Reviewed filtering config is fail-closed; resolve warnings first: {warning_types}.'


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
            'support_count': _readiness_int(candidate.get('support_count', 0)),
            'page_count': _readiness_int(candidate.get('page_count', 0)),
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


def _docx_header_footer_text_lookup(page_summaries: list) -> dict:
    grouped = defaultdict(list)
    for page in page_summaries or []:
        for block in page.get('text_blocks', []) or []:
            fingerprint = block.get('fingerprint', '')
            text = normalize_text(block.get('text', ''))
            if fingerprint and text:
                grouped[fingerprint].append(text)

    lookup = {}
    for fingerprint, texts in grouped.items():
        counts = Counter(normalize_text(text) for text in texts if normalize_text(text))
        lookup[fingerprint] = counts.most_common(1)[0][0] if counts else ''
    return lookup


def _normalize_docx_page_number_behavior(value: str) -> str:
    behavior = normalize_text(value or PAGE_NUMBER_BEHAVIOR_PLACEHOLDER_ONLY)
    return behavior if behavior in PAGE_NUMBER_BEHAVIORS else PAGE_NUMBER_BEHAVIOR_UNSUPPORTED


def _docx_page_number_generation_status(behavior: str) -> str:
    if behavior == PAGE_NUMBER_BEHAVIOR_PLACEHOLDER_ONLY:
        return 'deferred_placeholder_only'
    if behavior == PAGE_NUMBER_BEHAVIOR_STATIC_TEXT:
        return 'static_text_diagnostic_only'
    if behavior == PAGE_NUMBER_BEHAVIOR_WORD_FIELD:
        return 'word_field_requested'
    return 'unsupported'


def _docx_header_footer_plan_entry(
        candidate: dict,
        text_lookup: dict,
        page_number_behavior: str) -> tuple:
    role = candidate.get('proposed_role', '')
    regions = _candidate_regions(candidate)
    if REGION_BODY in regions:
        return None, _docx_header_footer_warning(
            candidate,
            'body_region_candidate_not_represented',
            'Body-region candidates are not eligible for DOCX header/footer generation.')
    if role == ROLE_LAYOUT_PLACEHOLDER:
        return None, _docx_header_footer_warning(
            candidate,
            'layout_placeholder_not_semantic_header_footer',
            'Layout placeholders are not semantic DOCX header/footer text.')
    if role not in {ROLE_HEADER, ROLE_FOOTER, ROLE_PAGE_NUMBER}:
        return None, _docx_header_footer_warning(
            candidate,
            'role_not_supported_for_docx_header_footer',
            'Only header, footer, and page-number candidates are represented in Phase 4A.')

    text = _docx_header_footer_candidate_text(candidate, text_lookup)
    if role == ROLE_PAGE_NUMBER:
        text = PAGE_NUMBER_PLACEHOLDER
    elif not text:
        return None, _docx_header_footer_warning(
            candidate,
            'empty_header_footer_text',
            'Approved candidate has no representable text.')
    elif _placeholder_kind(_comparison_text(text)):
        return None, _docx_header_footer_warning(
            candidate,
            'placeholder_not_semantic_header_footer_text',
            'Placeholder-like text is not represented as semantic header/footer content.')

    target_part = 'header' if role == ROLE_HEADER else 'footer'
    return {
        'candidate_id': candidate.get('candidate_id', ''),
        'fingerprint': candidate.get('fingerprint', ''),
        'role': role,
        'target_part': target_part,
        'text': normalize_text(text),
        'text_kind': 'page_number_placeholder' if role == ROLE_PAGE_NUMBER else 'semantic_text',
        'section_scope': 'document',
        'affected_pages': list(candidate.get('affected_pages', []) or []),
        'regions': sorted(regions),
        'support_count': _readiness_int(candidate.get('support_count', 0)),
        'page_count': _readiness_int(candidate.get('page_count', 0)),
        'first_page_policy': 'deferred',
        'odd_even_policy': 'deferred',
        'page_number_behavior': (
            page_number_behavior if role == ROLE_PAGE_NUMBER else 'not_applicable'),
        'page_number_field_generation': (
            _docx_page_number_generation_status(page_number_behavior)
            if role == ROLE_PAGE_NUMBER else 'not_applicable'),
        'generation_status': (
            page_number_behavior if role == ROLE_PAGE_NUMBER else 'planned_text_only'),
    }, None


def _docx_header_footer_candidate_text(candidate: dict, text_lookup: dict) -> str:
    fingerprint = candidate.get('fingerprint', '')
    text = normalize_text(text_lookup.get(fingerprint, ''))
    if text:
        return text
    return normalize_text((fingerprint or '').split('||')[0])


def _docx_header_footer_warning(candidate: dict, warning_type: str, message: str) -> dict:
    return {
        'type': warning_type,
        'candidate_id': candidate.get('candidate_id', ''),
        'fingerprint': candidate.get('fingerprint', ''),
        'proposed_role': candidate.get('proposed_role', ''),
        'regions': sorted(_candidate_regions(candidate)),
        'message': message,
    }


def _docx_header_footer_generation_plan_result(
        enabled: bool,
        candidates: list,
        approved: list,
        blocked: list,
        entries: list,
        unrepresentable: list,
        warnings: list,
        page_number_behavior: str,
        require_dynamic_page_number: bool = False) -> dict:
    page_number_behavior = _normalize_docx_page_number_behavior(page_number_behavior)
    policy = _docx_header_footer_policy(
        entries,
        page_number_behavior,
        require_dynamic_page_number)
    warnings = list(warnings or []) + list(policy.get('warnings', []) or [])
    warning_types = {warning.get('type') for warning in warnings}
    if page_number_behavior == PAGE_NUMBER_BEHAVIOR_UNSUPPORTED:
        if 'unsupported_page_number_behavior' not in warning_types:
            warnings.append({'type': 'unsupported_page_number_behavior'})
            warning_types.add('unsupported_page_number_behavior')
    if (
            require_dynamic_page_number and
            page_number_behavior != PAGE_NUMBER_BEHAVIOR_WORD_FIELD):
        if 'dynamic_page_number_field_required' not in warning_types:
            warnings.append({'type': 'dynamic_page_number_field_required'})
            warning_types.add('dynamic_page_number_field_required')
    section_plan = _docx_header_footer_section_plan(entries, page_number_behavior)
    page_number_field_generation = _docx_page_number_generation_status(
        page_number_behavior)
    summary = {
        'enabled': bool(enabled),
        'candidate_count': len(candidates or []),
        'approved_candidate_count': len(approved or []),
        'blocked_candidate_count': len(blocked or []),
        'representable_entry_count': len(entries or []),
        'unrepresentable_approved_candidate_count': len(unrepresentable or []),
        'header_text_count': sum(1 for entry in entries if entry.get('role') == ROLE_HEADER),
        'footer_text_count': sum(1 for entry in entries if entry.get('role') == ROLE_FOOTER),
        'page_number_placeholder_count': sum(
            1 for entry in entries if entry.get('role') == ROLE_PAGE_NUMBER),
        'semantic_header_footer_text_count': sum(
            1 for entry in entries
            if entry.get('text_kind') == 'semantic_text'),
        'supported_page_number_behaviors': sorted(PAGE_NUMBER_BEHAVIORS),
        'page_number_behavior': page_number_behavior,
        'page_number_field_generation': page_number_field_generation,
        'page_number_dynamic_field_required': bool(require_dynamic_page_number),
        'page_number_word_field_supported': True,
        'section_scope': 'document',
        'first_page_policy': 'deferred',
        'odd_even_policy': 'deferred',
        'header_footer_policy_type': policy.get('policy_type', 'unsupported'),
        'header_footer_policy_safety_status': policy.get('safety_status', 'blocked'),
        'header_footer_policy_fail_closed': bool(policy.get('fail_closed', True)),
        'section_policy_count': len(policy.get('section_policies', []) or []),
        'public_cli_exposed': False,
        'production_default_enabled': False,
        'default_conversion_changed': False,
        'safety_warning_count': len(warnings or []),
    }
    return {
        'enabled': bool(enabled),
        'policy': 'internal_docx_header_footer_generation_plan_only',
        'summary': summary,
        'entries': entries,
        'sections': [section_plan],
        'header_footer_policy': policy,
        'blocked_candidates': blocked,
        'unrepresentable_approved_candidates': unrepresentable,
        'safety_warnings': warnings,
        'limitations': [
            'Plan-only helper; not wired into default conversion.',
            _docx_page_number_limitation(page_number_behavior),
            'First-page and odd/even section behavior is deferred.',
            'Images, logos, and complex layout are not represented.',
            'Paragraph continuation merging remains out of scope.',
        ],
        'recommendation': {
            'safe_for_internal_docx_header_footer_experiment': bool(
                enabled and not warnings and not policy.get('fail_closed', True)),
            'reason': (
                'Approved semantic header/footer candidates can be represented as simple DOCX text plans.'
                if enabled and not warnings and not policy.get('fail_closed', True) else
                'Keep DOCX header/footer generation disabled until unrepresentable approved candidates are resolved.'
            ),
        },
    }


def _docx_page_number_limitation(behavior: str) -> str:
    if behavior == PAGE_NUMBER_BEHAVIOR_WORD_FIELD:
        return 'Page-number Word PAGE fields are internal-only and require OpenXML validation.'
    if behavior == PAGE_NUMBER_BEHAVIOR_STATIC_TEXT:
        return 'Page numbers are represented as diagnostic static text, not dynamic Word fields.'
    if behavior == PAGE_NUMBER_BEHAVIOR_UNSUPPORTED:
        return 'Unsupported page-number behavior fails closed for migration.'
    return 'Page-number fields default to diagnostic placeholder-only behavior.'


def _docx_page_number_unsupported_features(behavior: str) -> list:
    features = [
        'image_or_logo_header_footer_migration',
        'paragraph_continuation_merge',
    ]
    if behavior != PAGE_NUMBER_BEHAVIOR_WORD_FIELD:
        features.insert(0, 'word_page_number_field_generation')
    return features


def _docx_header_footer_policy(
        entries: list,
        page_number_behavior: str = PAGE_NUMBER_BEHAVIOR_PLACEHOLDER_ONLY,
        require_dynamic_page_number: bool = False) -> dict:
    entries = list(entries or [])
    page_number_behavior = _normalize_docx_page_number_behavior(page_number_behavior)
    page_count = _docx_header_footer_policy_page_count(entries)
    base = {
        'policy_type': 'unsupported',
        'section_index': 0,
        'section_scope': 'document',
        'default_header_text': '',
        'default_footer_text': '',
        'first_page_header_text': '',
        'first_page_footer_text': '',
        'odd_header_text': '',
        'odd_footer_text': '',
        'even_header_text': '',
        'even_footer_text': '',
        'page_number_behavior': page_number_behavior,
        'page_number_field_generation': _docx_page_number_generation_status(
            page_number_behavior),
        'page_number_dynamic_field_required': bool(require_dynamic_page_number),
        'section_policies': [],
        'warnings': [],
        'unsupported_features': _docx_page_number_unsupported_features(
            page_number_behavior),
        'needs_section_mapping': False,
        'fail_closed': True,
        'safety_status': 'blocked',
    }
    if not entries:
        base['warnings'].append({'type': 'no_representable_header_footer_entries'})
        return base
    if page_count <= 0:
        base['warnings'].append({'type': 'missing_page_scope_for_header_footer_policy'})
        return base

    page_signatures = _docx_header_footer_page_signatures(entries, page_count)
    missing_pages = [
        index for index, signature in enumerate(page_signatures)
        if _docx_header_footer_signature_empty(signature)
    ]
    if missing_pages:
        base['warnings'].append({
            'type': 'incomplete_header_footer_page_coverage',
            'page_indices': missing_pages,
        })
        return base

    first_signature = page_signatures[0]
    if all(signature == first_signature for signature in page_signatures):
        base.update(_docx_header_footer_default_policy(
            first_signature,
            page_number_behavior,
            require_dynamic_page_number))
        return base

    if page_count > 1:
        remaining = page_signatures[1:]
        if remaining and all(signature == remaining[0] for signature in remaining):
            base.update(_docx_header_footer_first_page_policy(
                first_signature,
                remaining[0],
                page_number_behavior))
            return base

    odd_signatures = page_signatures[0::2]
    even_signatures = page_signatures[1::2]
    if (
            odd_signatures and even_signatures and
            all(signature == odd_signatures[0] for signature in odd_signatures) and
            all(signature == even_signatures[0] for signature in even_signatures) and
            odd_signatures[0] != even_signatures[0]):
        base.update(_docx_header_footer_odd_even_policy(
            odd_signatures[0],
            even_signatures[0],
            page_number_behavior))
        return base

    ranges = _docx_header_footer_signature_ranges(page_signatures)
    if len(ranges) > 1 and all(item['page_count'] > 1 for item in ranges):
        base.update(_docx_header_footer_section_scoped_policy(
            ranges,
            page_number_behavior))
        return base

    base['warnings'].append({
        'type': 'ambiguous_header_footer_policy',
        'message': (
            'Approved candidates do not form stable default, first-page, '
            'odd/even, or contiguous section-scoped groups.'),
    })
    base['unsupported_features'].append('ambiguous_header_footer_candidate_pattern')
    return base


def _docx_header_footer_policy_page_count(entries: list) -> int:
    page_count = 0
    for entry in entries or []:
        page_count = max(page_count, _readiness_int(entry.get('page_count', 0)))
        affected = [_readiness_int(page) for page in entry.get('affected_pages', []) or []]
        if affected:
            page_count = max(page_count, max(affected) + 1)
    return page_count


def _docx_header_footer_page_signatures(entries: list, page_count: int) -> list:
    signatures = [
        {'header': [], 'footer': [], 'page_number': []}
        for _ in range(page_count)
    ]
    for entry in entries or []:
        role = entry.get('role')
        text = normalize_text(entry.get('text', ''))
        if not text:
            continue
        key = (
            'header' if role == ROLE_HEADER else
            'footer' if role == ROLE_FOOTER else
            'page_number' if role == ROLE_PAGE_NUMBER else
            '')
        if not key:
            continue
        for page_index in entry.get('affected_pages', []) or []:
            page_index = _readiness_int(page_index)
            if 0 <= page_index < page_count and text not in signatures[page_index][key]:
                signatures[page_index][key].append(text)

    return [_docx_header_footer_freeze_signature(signature) for signature in signatures]


def _docx_header_footer_freeze_signature(signature: dict) -> dict:
    return {
        'header': tuple(signature.get('header', []) or []),
        'footer': tuple(signature.get('footer', []) or []),
        'page_number': tuple(signature.get('page_number', []) or []),
    }


def _docx_header_footer_signature_empty(signature: dict) -> bool:
    return not any(signature.get(key) for key in ('header', 'footer', 'page_number'))


def _docx_header_footer_signature_text(signature: dict, key: str) -> str:
    return ' | '.join(signature.get(key, []) or [])


def _docx_header_footer_default_policy(
        signature: dict,
        page_number_behavior: str,
        require_dynamic_page_number: bool = False) -> dict:
    warnings = []
    fail_closed = False
    safety_status = 'safe_for_simple_default_writer'
    if page_number_behavior == PAGE_NUMBER_BEHAVIOR_UNSUPPORTED:
        warnings.append({'type': 'unsupported_page_number_behavior'})
        fail_closed = True
        safety_status = 'blocked'
    if (
            require_dynamic_page_number and
            page_number_behavior != PAGE_NUMBER_BEHAVIOR_WORD_FIELD):
        warnings.append({'type': 'dynamic_page_number_field_required'})
        fail_closed = True
        safety_status = 'blocked'
    return {
        'policy_type': 'default',
        'default_header_text': _docx_header_footer_signature_text(signature, 'header'),
        'default_footer_text': _docx_header_footer_signature_text(signature, 'footer'),
        'page_number_behavior': page_number_behavior,
        'page_number_field_generation': _docx_page_number_generation_status(
            page_number_behavior),
        'page_number_dynamic_field_required': bool(require_dynamic_page_number),
        'warnings': warnings,
        'unsupported_features': _docx_page_number_unsupported_features(
            page_number_behavior),
        'fail_closed': fail_closed,
        'safety_status': safety_status,
    }


def _docx_header_footer_first_page_policy(
        first_signature: dict,
        default_signature: dict,
        page_number_behavior: str) -> dict:
    return {
        'policy_type': 'first_page',
        'default_header_text': _docx_header_footer_signature_text(default_signature, 'header'),
        'default_footer_text': _docx_header_footer_signature_text(default_signature, 'footer'),
        'first_page_header_text': _docx_header_footer_signature_text(first_signature, 'header'),
        'first_page_footer_text': _docx_header_footer_signature_text(first_signature, 'footer'),
        'page_number_behavior': page_number_behavior,
        'page_number_field_generation': _docx_page_number_generation_status(
            page_number_behavior),
        'warnings': [{'type': 'first_page_docx_header_footer_writing_deferred'}],
        'unsupported_features': ['first_page_docx_header_footer_writing'] +
        _docx_page_number_unsupported_features(page_number_behavior),
        'fail_closed': True,
        'safety_status': 'diagnostic_only',
    }


def _docx_header_footer_odd_even_policy(
        odd_signature: dict,
        even_signature: dict,
        page_number_behavior: str) -> dict:
    return {
        'policy_type': 'odd_even',
        'odd_header_text': _docx_header_footer_signature_text(odd_signature, 'header'),
        'odd_footer_text': _docx_header_footer_signature_text(odd_signature, 'footer'),
        'even_header_text': _docx_header_footer_signature_text(even_signature, 'header'),
        'even_footer_text': _docx_header_footer_signature_text(even_signature, 'footer'),
        'page_number_behavior': page_number_behavior,
        'page_number_field_generation': _docx_page_number_generation_status(
            page_number_behavior),
        'warnings': [{'type': 'odd_even_docx_header_footer_writing_deferred'}],
        'unsupported_features': ['odd_even_docx_header_footer_writing'] +
        _docx_page_number_unsupported_features(page_number_behavior),
        'fail_closed': True,
        'safety_status': 'diagnostic_only',
    }


def _docx_header_footer_signature_ranges(signatures: list) -> list:
    ranges = []
    start = 0
    while start < len(signatures):
        signature = signatures[start]
        end = start
        while end + 1 < len(signatures) and signatures[end + 1] == signature:
            end += 1
        ranges.append({
            'section_scope': 'page_range',
            'start_page_index': start,
            'end_page_index': end,
            'page_count': end - start + 1,
            'header_text': _docx_header_footer_signature_text(signature, 'header'),
            'footer_text': _docx_header_footer_signature_text(signature, 'footer'),
            'page_number_text': _docx_header_footer_signature_text(signature, 'page_number'),
        })
        start = end + 1
    return ranges


def _docx_header_footer_section_scoped_policy(
        ranges: list,
        page_number_behavior: str) -> dict:
    return {
        'policy_type': 'section_scoped',
        'section_policies': ranges,
        'page_number_behavior': page_number_behavior,
        'page_number_field_generation': _docx_page_number_generation_status(
            page_number_behavior),
        'warnings': [{'type': 'section_scoped_docx_header_footer_mapping_deferred'}],
        'unsupported_features': ['production_section_mapping'] +
        _docx_page_number_unsupported_features(page_number_behavior),
        'needs_section_mapping': True,
        'fail_closed': True,
        'safety_status': 'diagnostic_only',
    }


def _docx_header_footer_section_plan(
        entries: list,
        page_number_behavior: str = PAGE_NUMBER_BEHAVIOR_PLACEHOLDER_ONLY) -> dict:
    return {
        'section_scope': 'document',
        'first_page_policy': 'deferred',
        'odd_even_policy': 'deferred',
        'page_number_behavior': page_number_behavior,
        'header_texts': _unique_entry_texts(entries, ROLE_HEADER),
        'footer_texts': _unique_entry_texts(entries, ROLE_FOOTER),
        'page_number_placeholders': _unique_entry_texts(entries, ROLE_PAGE_NUMBER),
    }


def _unique_entry_texts(entries: list, role: str) -> list:
    values = []
    for entry in entries or []:
        if entry.get('role') != role:
            continue
        text = normalize_text(entry.get('text', ''))
        if text and text not in values:
            values.append(text)
    return values


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


def _guarded_apply_disabled_summary(original_count: int) -> dict:
    return {
        'original_raw_block_count_before_apply': original_count,
        'filtered_raw_block_count_during_apply': original_count,
        'restored_raw_block_count_after_restore': original_count,
        'removed_during_apply_count': 0,
        'body_region_removed_count': 0,
        'rejected_unsure_layout_placeholder_removed_count': 0,
        'snapshot_created': False,
        'restore_completed': False,
        'restore_exact_count_match': True,
        'restore_fingerprint_match': True,
        'original_raw_pages_left_mutated': False,
    }


def _guarded_apply_summary(
        before: list,
        during: list,
        after: list,
        removed_objects: list,
        mapping_report: dict,
        snapshot_created: bool,
        restore_completed: bool,
        consistency: dict) -> dict:
    before_fingerprint = _raw_object_page_fingerprint(before)
    after_fingerprint = _raw_object_page_fingerprint(after)
    original_count = _raw_object_page_count(before)
    filtered_count = _raw_object_page_count(during)
    restored_count = _raw_object_page_count(after)
    mapping_summary = (mapping_report or {}).get('summary') or {}
    body_removed = sum(1 for item in removed_objects or [] if item.get('region') == REGION_BODY)
    blocked_removed = sum(
        1 for item in removed_objects or []
        if (
            item.get('proposed_role') == ROLE_LAYOUT_PLACEHOLDER or
            item.get('placeholder_kind') == 'image' or
            'blocked_review_decision_fingerprint' in item.get('unsafe_signals', [])))
    count_match = original_count == restored_count
    fingerprint_match = before_fingerprint == after_fingerprint
    return {
        'original_raw_block_count_before_apply': original_count,
        'filtered_raw_block_count_during_apply': filtered_count,
        'restored_raw_block_count_after_restore': restored_count,
        'removed_during_apply_count': len(removed_objects),
        'approved_candidate_count': mapping_summary.get('approved_candidate_count', 0),
        'blocked_candidate_count': mapping_summary.get('blocked_candidate_count', 0),
        'body_region_removed_count': body_removed,
        'rejected_unsure_layout_placeholder_removed_count': blocked_removed,
        'snapshot_created': bool(snapshot_created),
        'restore_completed': bool(restore_completed),
        'restore_exact_count_match': count_match,
        'restore_fingerprint_match': fingerprint_match,
        'original_raw_pages_left_mutated': not (count_match and fingerprint_match),
        'phase_2m_mapped_raw_object_count': consistency.get('phase_2m_mapped_raw_object_count', 0),
        'phase_2n_removed_copied_block_count': consistency.get('phase_2n_removed_copied_block_count'),
        'removed_count_matches_phase_2m': consistency.get('removed_count_matches_phase_2m', False),
        'removed_count_matches_phase_2n': consistency.get('removed_count_matches_phase_2n', False),
    }


def _guarded_apply_consistency(
        mapping_report: dict,
        copied_apply_report: dict,
        removed_count: int,
        expected_mapping_count: int = None) -> dict:
    mapping_summary = (mapping_report or {}).get('summary') or {}
    copied_summary = (copied_apply_report or {}).get('summary') or {}
    mapped_count = mapping_summary.get('mapped_raw_object_count', 0)
    copied_removed_count = copied_summary.get('removed_copied_block_count')
    expected_mapping_count = (
        expected_mapping_count
        if expected_mapping_count is not None else
        mapped_count)
    return {
        'phase_2m_mapped_raw_object_count': mapped_count,
        'phase_2n_removed_copied_block_count': copied_removed_count,
        'expected_mapping_count': expected_mapping_count,
        'removed_during_apply_count': removed_count,
        'removed_count_matches_phase_2m': removed_count == mapped_count,
        'removed_count_matches_phase_2n': (
            copied_removed_count is None or removed_count == copied_removed_count),
        'expected_mapping_count_matches_phase_2m': expected_mapping_count == mapped_count,
    }


def _guarded_apply_downstream_risk_notes(before: list, during: list) -> dict:
    before_body_count = _raw_object_region_count(before, REGION_BODY)
    during_body_count = _raw_object_region_count(during, REGION_BODY)
    before_placeholder_count = _raw_object_placeholder_count(before)
    during_placeholder_count = _raw_object_placeholder_count(during)
    return {
        'margin_input_count_before': _raw_object_page_count(before),
        'margin_input_count_during_apply': _raw_object_page_count(during),
        'section_input_count_before': _raw_object_page_count(before),
        'section_input_count_during_apply': _raw_object_page_count(during),
        'body_block_count_before': before_body_count,
        'body_block_count_during_apply': during_body_count,
        'image_shape_placeholder_count_before': before_placeholder_count,
        'image_shape_placeholder_count_during_apply': during_placeholder_count,
        'table_risk_note': (
            'Guarded apply preserved body-region raw objects during the apply window.'
            if before_body_count == during_body_count else
            'Guarded apply removed body-region raw objects during the apply window.'),
        'paragraph_grouping_risk_note': (
            'Guarded apply preserved body-region line/block objects during the apply window.'
            if before_body_count == during_body_count else
            'Guarded apply removed body-region line/block objects during the apply window.'),
    }


def _guarded_apply_warnings(
        summary: dict,
        mapping_report: dict,
        consistency: dict,
        apply_skipped_reason: str = '') -> list:
    warnings = []
    for warning in (mapping_report or {}).get('safety_warnings', []) or []:
        warnings.append({
            'type': f'mapping_{warning.get("type", "warning")}',
            'message': warning.get('message', ''),
            'count': warning.get('count'),
        })
    if apply_skipped_reason:
        warnings.append({
            'type': 'guarded_apply_skipped',
            'reason': apply_skipped_reason,
        })
    for key, warning_type in (
            ('snapshot_created', 'snapshot_not_created'),
            ('restore_completed', 'restore_not_completed'),
            ('restore_exact_count_match', 'restore_count_mismatch'),
            ('restore_fingerprint_match', 'restore_fingerprint_mismatch')):
        if not summary.get(key, False):
            warnings.append({'type': warning_type})
    if summary.get('original_raw_pages_left_mutated'):
        warnings.append({'type': 'original_raw_pages_left_mutated'})
    if summary.get('body_region_removed_count', 0):
        warnings.append({
            'type': 'body_region_removed_during_guarded_apply',
            'count': summary.get('body_region_removed_count'),
        })
    if summary.get('rejected_unsure_layout_placeholder_removed_count', 0):
        warnings.append({
            'type': 'blocked_or_placeholder_removed_during_guarded_apply',
            'count': summary.get('rejected_unsure_layout_placeholder_removed_count'),
        })
    if not consistency.get('removed_count_matches_phase_2m', False):
        warnings.append({
            'type': 'removed_count_mismatch_phase_2m',
            'expected': consistency.get('phase_2m_mapped_raw_object_count'),
            'observed': consistency.get('removed_during_apply_count'),
        })
    if not consistency.get('removed_count_matches_phase_2n', True):
        warnings.append({
            'type': 'removed_count_mismatch_phase_2n',
            'expected': consistency.get('phase_2n_removed_copied_block_count'),
            'observed': consistency.get('removed_during_apply_count'),
        })
    if not consistency.get('expected_mapping_count_matches_phase_2m', True):
        warnings.append({
            'type': 'expected_mapping_count_mismatch_phase_2m',
            'expected': consistency.get('expected_mapping_count'),
            'observed': consistency.get('phase_2m_mapped_raw_object_count'),
        })
    return warnings


def _guarded_apply_safe_for_phase_2p(summary: dict, warnings: list) -> bool:
    return (
        bool(summary.get('removed_during_apply_count')) and
        bool(summary.get('snapshot_created')) and
        bool(summary.get('restore_completed')) and
        bool(summary.get('restore_exact_count_match')) and
        bool(summary.get('restore_fingerprint_match')) and
        bool(summary.get('removed_count_matches_phase_2m')) and
        bool(summary.get('removed_count_matches_phase_2n')) and
        not summary.get('original_raw_pages_left_mutated') and
        not summary.get('body_region_removed_count', 0) and
        not summary.get('rejected_unsure_layout_placeholder_removed_count', 0) and
        not warnings)


def _guarded_apply_recommendation(summary: dict, warnings: list) -> str:
    if _guarded_apply_safe_for_phase_2p(summary, warnings):
        return 'Guarded raw-page apply/restore removed only validated objects and restored the original raw pages; Phase 2P can remain opt-in and guarded.'
    return 'Do not enable persistent production filtering yet; resolve guarded apply/restore warnings first.'


def _copy_parse_metrics(metrics: dict) -> dict:
    if not metrics:
        return {}
    copied = dict(metrics)
    copied['tables'] = [
        _copy_table_record(table) for table in metrics.get('tables', []) or []
    ]
    copied['pages'] = [
        _copy_parse_metrics_page(page) for page in metrics.get('pages', []) or []
    ]
    copied['warnings'] = [
        dict(warning) for warning in metrics.get('warnings', []) or []
    ]
    return copied


def _copy_parse_metrics_page(page: dict) -> dict:
    copied = dict(page)
    copied['tables'] = [
        _copy_table_record(table) for table in page.get('tables', []) or []
    ]
    copied['warnings'] = [
        dict(warning) for warning in page.get('warnings', []) or []
    ]
    return copied


def _copy_table_record(table: dict) -> dict:
    copied = dict(table)
    copied['cell_summaries'] = [
        dict(cell) for cell in table.get('cell_summaries', []) or []
    ]
    copied['cell_text_signature'] = list(table.get('cell_text_signature', []) or [])
    copied['cell_bbox_signature'] = [
        list(bbox) for bbox in table.get('cell_bbox_signature', []) or []
    ]
    return copied


def _copy_removed_objects_by_page(removed_objects_by_page: list) -> list:
    copied = []
    for page in removed_objects_by_page or []:
        page_index = page.get('page_index')
        page_number = page.get('page_number')
        objects = []
        for raw_object in page.get('objects', []) or []:
            copied_object = dict(raw_object)
            copied_object.setdefault('page_index', page_index)
            copied_object.setdefault('page_number', page_number)
            objects.append(copied_object)
        copied.append({
            'page_index': page_index,
            'page_number': page_number,
            'removed_count': page.get('removed_count', len(objects)),
            'objects': objects,
        })
    return copied


def _filtered_parse_empty_metrics(raw_count: int) -> dict:
    return {
        'parse_metrics_available': False,
        'raw_block_count': raw_count,
        'body_raw_block_count': 0,
        'parsed_text_block_count': 0,
        'body_text_block_count': 0,
        'paragraph_like_text_block_count': 0,
        'table_count': 0,
        'image_count': 0,
        'section_count': 0,
        'tables': [],
        'pages': [],
        'warnings': [],
    }


def _filtered_parse_metric(metrics: dict, key: str, default=0):
    if not metrics:
        return default
    value = metrics.get(key, default)
    return default if value is None else value


def _filtered_parse_disabled_summary(original_count: int, baseline_metrics: dict) -> dict:
    return {
        'baseline_raw_block_count': original_count,
        'filtered_raw_block_count': original_count,
        'removed_raw_block_count': 0,
        'baseline_parsed_text_block_count': _filtered_parse_metric(
            baseline_metrics, 'parsed_text_block_count', 0),
        'filtered_parsed_text_block_count': _filtered_parse_metric(
            baseline_metrics, 'parsed_text_block_count', 0),
        'baseline_body_text_block_count': _filtered_parse_metric(
            baseline_metrics, 'body_text_block_count', 0),
        'filtered_body_text_block_count': _filtered_parse_metric(
            baseline_metrics, 'body_text_block_count', 0),
        'baseline_paragraph_like_text_block_count': _filtered_parse_metric(
            baseline_metrics, 'paragraph_like_text_block_count', 0),
        'filtered_paragraph_like_text_block_count': _filtered_parse_metric(
            baseline_metrics, 'paragraph_like_text_block_count', 0),
        'baseline_table_count': _filtered_parse_metric(baseline_metrics, 'table_count', 0),
        'filtered_table_count': _filtered_parse_metric(baseline_metrics, 'table_count', 0),
        'baseline_image_count': _filtered_parse_metric(baseline_metrics, 'image_count', 0),
        'filtered_image_count': _filtered_parse_metric(baseline_metrics, 'image_count', 0),
        'baseline_section_count': _filtered_parse_metric(baseline_metrics, 'section_count', 0),
        'filtered_section_count': _filtered_parse_metric(baseline_metrics, 'section_count', 0),
        'body_region_removed_count': 0,
        'rejected_unsure_layout_placeholder_removed_count': 0,
        'raw_pages_restored_or_reloaded': True,
        'restore_fingerprint_match': True,
        'production_default_changed': False,
    }


def _filtered_parse_consistency(
        mapping_report: dict,
        copied_apply_report: dict,
        guarded_apply_restore_report: dict,
        removed_count: int,
        expected_mapping_count: int = None) -> dict:
    mapping_summary = (mapping_report or {}).get('summary') or {}
    copied_summary = (copied_apply_report or {}).get('summary') or {}
    guarded_summary = (guarded_apply_restore_report or {}).get('summary') or {}
    mapped_count = mapping_summary.get('mapped_raw_object_count', 0)
    copied_removed_count = copied_summary.get('removed_copied_block_count')
    guarded_removed_count = guarded_summary.get('removed_during_apply_count')
    expected_mapping_count = (
        expected_mapping_count
        if expected_mapping_count is not None else
        mapped_count)
    return {
        'phase_2m_mapped_raw_object_count': mapped_count,
        'phase_2n_removed_copied_block_count': copied_removed_count,
        'phase_2o_removed_during_apply_count': guarded_removed_count,
        'expected_mapping_count': expected_mapping_count,
        'removed_raw_block_count': removed_count,
        'removed_count_matches_phase_2m': removed_count == mapped_count,
        'removed_count_matches_phase_2n': (
            copied_removed_count is None or removed_count == copied_removed_count),
        'removed_count_matches_phase_2o': (
            guarded_removed_count is None or removed_count == guarded_removed_count),
        'expected_mapping_count_matches_phase_2m': expected_mapping_count == mapped_count,
    }


def _filtered_parse_summary(
        before: list,
        filtered: list,
        after: list,
        removed_objects: list,
        baseline_metrics: dict,
        filtered_metrics: dict,
        mapping_report: dict,
        restore_completed: bool,
        restore_fingerprint_match: bool,
        consistency: dict) -> dict:
    mapping_summary = (mapping_report or {}).get('summary') or {}
    body_removed = sum(
        1 for item in removed_objects or []
        if item.get('region') == REGION_BODY)
    blocked_removed = sum(
        1 for item in removed_objects or []
        if (
            item.get('proposed_role') == ROLE_LAYOUT_PLACEHOLDER or
            item.get('placeholder_kind') == 'image' or
            'blocked_review_decision_fingerprint' in item.get('unsafe_signals', [])))
    return {
        'baseline_raw_block_count': _raw_object_page_count(before),
        'filtered_raw_block_count': _raw_object_page_count(filtered),
        'restored_raw_block_count': _raw_object_page_count(after),
        'removed_raw_block_count': len(removed_objects),
        'approved_candidate_count': mapping_summary.get('approved_candidate_count', 0),
        'blocked_candidate_count': mapping_summary.get('blocked_candidate_count', 0),
        'baseline_parsed_text_block_count': _filtered_parse_metric(
            baseline_metrics, 'parsed_text_block_count', 0),
        'filtered_parsed_text_block_count': _filtered_parse_metric(
            filtered_metrics, 'parsed_text_block_count', 0),
        'baseline_body_text_block_count': _filtered_parse_metric(
            baseline_metrics, 'body_text_block_count', 0),
        'filtered_body_text_block_count': _filtered_parse_metric(
            filtered_metrics, 'body_text_block_count', 0),
        'baseline_paragraph_like_text_block_count': _filtered_parse_metric(
            baseline_metrics, 'paragraph_like_text_block_count', 0),
        'filtered_paragraph_like_text_block_count': _filtered_parse_metric(
            filtered_metrics, 'paragraph_like_text_block_count', 0),
        'baseline_table_count': _filtered_parse_metric(baseline_metrics, 'table_count', 0),
        'filtered_table_count': _filtered_parse_metric(filtered_metrics, 'table_count', 0),
        'baseline_image_count': _filtered_parse_metric(baseline_metrics, 'image_count', 0),
        'filtered_image_count': _filtered_parse_metric(filtered_metrics, 'image_count', 0),
        'baseline_section_count': _filtered_parse_metric(baseline_metrics, 'section_count', 0),
        'filtered_section_count': _filtered_parse_metric(filtered_metrics, 'section_count', 0),
        'body_region_removed_count': body_removed,
        'rejected_unsure_layout_placeholder_removed_count': blocked_removed,
        'raw_pages_restored_or_reloaded': bool(restore_completed),
        'restore_fingerprint_match': bool(restore_fingerprint_match),
        'production_default_changed': False,
        'removed_count_matches_phase_2m': consistency.get('removed_count_matches_phase_2m', False),
        'removed_count_matches_phase_2n': consistency.get('removed_count_matches_phase_2n', False),
        'removed_count_matches_phase_2o': consistency.get('removed_count_matches_phase_2o', False),
    }


def _filtered_parse_warnings(
        summary: dict,
        baseline_metrics: dict,
        filtered_metrics: dict,
        mapping_report: dict,
        consistency: dict,
        apply_skipped_reason: str = '') -> list:
    warnings = []
    for warning in (mapping_report or {}).get('safety_warnings', []) or []:
        warnings.append({
            'type': f'mapping_{warning.get("type", "warning")}',
            'message': warning.get('message', ''),
            'count': warning.get('count'),
        })
    for warning in (baseline_metrics or {}).get('warnings', []) or []:
        warnings.append({
            'type': f'baseline_{warning.get("type", "parse_warning")}',
            'message': warning.get('message', ''),
            'page_number': warning.get('page_number'),
        })
    for warning in (filtered_metrics or {}).get('warnings', []) or []:
        warnings.append({
            'type': f'filtered_{warning.get("type", "parse_warning")}',
            'message': warning.get('message', ''),
            'page_number': warning.get('page_number'),
        })
    if apply_skipped_reason:
        warnings.append({
            'type': 'filtered_parse_apply_skipped',
            'reason': apply_skipped_reason,
        })
    if not summary.get('raw_pages_restored_or_reloaded'):
        warnings.append({'type': 'raw_pages_not_restored_or_reloaded'})
    if not summary.get('restore_fingerprint_match'):
        warnings.append({'type': 'restore_fingerprint_mismatch'})
    if summary.get('body_region_removed_count', 0):
        warnings.append({
            'type': 'body_region_removed_during_filtered_parse',
            'count': summary.get('body_region_removed_count'),
        })
    if summary.get('rejected_unsure_layout_placeholder_removed_count', 0):
        warnings.append({
            'type': 'blocked_or_placeholder_removed_during_filtered_parse',
            'count': summary.get('rejected_unsure_layout_placeholder_removed_count'),
        })
    for before_key, after_key, warning_type in (
            ('baseline_table_count', 'filtered_table_count', 'table_count_changed'),
            ('baseline_image_count', 'filtered_image_count', 'image_count_changed'),
            ('baseline_section_count', 'filtered_section_count', 'section_count_changed')):
        if summary.get(before_key, 0) != summary.get(after_key, 0):
            warnings.append({
                'type': warning_type,
                'baseline': summary.get(before_key, 0),
                'filtered': summary.get(after_key, 0),
            })
    if summary.get('filtered_body_text_block_count', 0) < summary.get('baseline_body_text_block_count', 0):
        warnings.append({
            'type': 'body_text_block_count_dropped',
            'baseline': summary.get('baseline_body_text_block_count', 0),
            'filtered': summary.get('filtered_body_text_block_count', 0),
        })
    if summary.get('filtered_paragraph_like_text_block_count', 0) > summary.get('baseline_paragraph_like_text_block_count', 0):
        warnings.append({
            'type': 'paragraph_fragmentation_increased',
            'baseline': summary.get('baseline_paragraph_like_text_block_count', 0),
            'filtered': summary.get('filtered_paragraph_like_text_block_count', 0),
        })
    if not consistency.get('removed_count_matches_phase_2m', False):
        warnings.append({
            'type': 'removed_count_mismatch_phase_2m',
            'expected': consistency.get('phase_2m_mapped_raw_object_count'),
            'observed': consistency.get('removed_raw_block_count'),
        })
    if not consistency.get('removed_count_matches_phase_2n', True):
        warnings.append({
            'type': 'removed_count_mismatch_phase_2n',
            'expected': consistency.get('phase_2n_removed_copied_block_count'),
            'observed': consistency.get('removed_raw_block_count'),
        })
    if not consistency.get('removed_count_matches_phase_2o', True):
        warnings.append({
            'type': 'removed_count_mismatch_phase_2o',
            'expected': consistency.get('phase_2o_removed_during_apply_count'),
            'observed': consistency.get('removed_raw_block_count'),
        })
    if not consistency.get('expected_mapping_count_matches_phase_2m', True):
        warnings.append({
            'type': 'expected_mapping_count_mismatch_phase_2m',
            'expected': consistency.get('expected_mapping_count'),
            'observed': consistency.get('phase_2m_mapped_raw_object_count'),
        })
    return warnings


def _filtered_parse_pollution_reduction(
        removed_objects: list,
        baseline_metrics: dict,
        filtered_metrics: dict) -> dict:
    removed_boundary_count = sum(
        1 for item in removed_objects or []
        if item.get('region') in {REGION_TOP, REGION_BOTTOM})
    return {
        'removed_boundary_raw_block_count': removed_boundary_count,
        'removed_header_footer_page_number_count': len(removed_objects or []),
        'parsed_text_block_delta': (
            _filtered_parse_metric(baseline_metrics, 'parsed_text_block_count', 0) -
            _filtered_parse_metric(filtered_metrics, 'parsed_text_block_count', 0)),
        'body_text_block_delta': (
            _filtered_parse_metric(baseline_metrics, 'body_text_block_count', 0) -
            _filtered_parse_metric(filtered_metrics, 'body_text_block_count', 0)),
    }


def _filtered_parse_safe_for_phase_2q(summary: dict, warnings: list) -> bool:
    blocking_types = {
        'mapping_ambiguous_raw_object_match',
        'mapping_missing_raw_object_match',
        'filtered_parse_apply_skipped',
        'raw_pages_not_restored_or_reloaded',
        'restore_fingerprint_mismatch',
        'body_region_removed_during_filtered_parse',
        'blocked_or_placeholder_removed_during_filtered_parse',
        'body_text_block_count_dropped',
        'paragraph_fragmentation_increased',
        'removed_count_mismatch_phase_2m',
        'removed_count_mismatch_phase_2n',
        'removed_count_mismatch_phase_2o',
    }
    warning_types = {warning.get('type') for warning in warnings or []}
    return (
        bool(summary.get('removed_raw_block_count')) and
        bool(summary.get('raw_pages_restored_or_reloaded')) and
        bool(summary.get('restore_fingerprint_match')) and
        bool(summary.get('removed_count_matches_phase_2m')) and
        bool(summary.get('removed_count_matches_phase_2n')) and
        bool(summary.get('removed_count_matches_phase_2o')) and
        not summary.get('body_region_removed_count', 0) and
        not summary.get('rejected_unsure_layout_placeholder_removed_count', 0) and
        not warning_types.intersection(blocking_types))


def _filtered_parse_recommendation(summary: dict, warnings: list) -> str:
    if _filtered_parse_safe_for_phase_2q(summary, warnings):
        if warnings:
            return 'Filtered parse experiment preserved reviewed/body safety invariants, but non-blocking parse metric changes still need manual review before Phase 2Q.'
        return 'Filtered parse experiment preserved reviewed/body safety invariants; Phase 2Q can remain opt-in and guarded.'
    return 'Do not connect reviewed filtering to default parsing yet; resolve filtered-parse warnings first.'


def _table_delta_records(parse_metrics: dict) -> list:
    metrics = parse_metrics or {}
    tables = [dict(table) for table in metrics.get('tables', []) or []]
    if not tables:
        for page in metrics.get('pages', []) or []:
            for table in page.get('tables', []) or []:
                record = dict(table)
                record.setdefault('page_index', page.get('page_index'))
                record.setdefault('page_number', page.get('page_number'))
                tables.append(record)

    records = []
    for index, table in enumerate(tables):
        record = dict(table)
        record['bbox'] = _json_bbox(record.get('bbox'))
        record.setdefault('table_id', f'table-{index}')
        record.setdefault('table_index', index)
        record.setdefault('region', REGION_BODY)
        record.setdefault('row_count', 0)
        record.setdefault('column_count', 0)
        record.setdefault('cell_count', 0)
        record.setdefault('text_preview', '')
        record['body_region_intersection'] = record.get('region') == REGION_BODY
        records.append(record)
    return records


def _table_delta_disabled_summary(baseline_tables: list, filtered_tables: list) -> dict:
    return {
        'baseline_table_count': len(baseline_tables),
        'filtered_table_count': len(filtered_tables),
        'table_count_delta': len(filtered_tables) - len(baseline_tables),
        'baseline_only_table_count': 0,
        'filtered_only_table_count': 0,
        'changed_common_table_count': 0,
        'body_region_baseline_only_table_count': 0,
        'top_bottom_baseline_only_table_count': 0,
        'tables_overlapping_removed_candidates_count': 0,
        'suspicious_body_table_loss_count': 0,
        'likely_header_footer_false_positive_table_count': 0,
        'table_changes_limited_to_top_bottom': True,
        'table_changes_affect_body_region': False,
        'classification': 'disabled',
    }


def _compare_table_records(baseline_tables: list, filtered_tables: list) -> dict:
    used_filtered = set()
    changed_common = []
    baseline_only = []

    for baseline in baseline_tables or []:
        match_index, match_kind = _best_table_match(baseline, filtered_tables, used_filtered)
        if match_index is None:
            baseline_only.append(dict(baseline))
            continue

        used_filtered.add(match_index)
        filtered = filtered_tables[match_index]
        changes = _table_record_changes(baseline, filtered, match_kind)
        if changes:
            changed_common.append({
                'baseline_table': dict(baseline),
                'filtered_table': dict(filtered),
                'match_kind': match_kind,
                'changes': changes,
                'region': baseline.get('region', ''),
                'page_index': baseline.get('page_index'),
                'page_number': baseline.get('page_number'),
                'classification': _changed_table_classification(baseline, changes),
            })

    filtered_only = [
        dict(table)
        for index, table in enumerate(filtered_tables or [])
        if index not in used_filtered
    ]
    return {
        'baseline_only_tables': baseline_only,
        'filtered_only_tables': filtered_only,
        'changed_common_tables': changed_common,
    }


def _best_table_match(baseline: dict, filtered_tables: list, used_filtered: set) -> tuple:
    best_index = None
    best_score = 0.0
    for index, filtered in enumerate(filtered_tables or []):
        if index in used_filtered:
            continue
        if baseline.get('page_index') != filtered.get('page_index'):
            continue

        bbox_delta = _bbox_max_delta(baseline.get('bbox'), filtered.get('bbox'))
        overlap = _bbox_overlap_ratio(baseline.get('bbox'), filtered.get('bbox'))
        same_shape = (
            int(baseline.get('row_count') or 0) == int(filtered.get('row_count') or 0) and
            int(baseline.get('column_count') or 0) == int(filtered.get('column_count') or 0) and
            int(baseline.get('cell_count') or 0) == int(filtered.get('cell_count') or 0))

        if bbox_delta <= 1.0 and same_shape:
            return index, 'exact'
        if overlap >= 0.75:
            score = overlap
        elif _bbox_gap(baseline.get('bbox'), filtered.get('bbox')) <= 3.0 and same_shape:
            score = 0.65
        else:
            continue

        if score > best_score:
            best_score = score
            best_index = index

    if best_index is None:
        return None, ''
    return best_index, 'fuzzy_overlap'


def _table_record_changes(baseline: dict, filtered: dict, match_kind: str) -> list:
    changes = []
    if match_kind != 'exact' and _bbox_max_delta(baseline.get('bbox'), filtered.get('bbox')) > 1.0:
        changes.append('bbox_changed')
    for key, label in (
            ('row_count', 'row_count_changed'),
            ('column_count', 'column_count_changed'),
            ('cell_count', 'cell_count_changed')):
        if int(baseline.get(key) or 0) != int(filtered.get(key) or 0):
            changes.append(label)
    return changes


def _changed_table_classification(table: dict, changes: list) -> str:
    if table.get('region') == REGION_BODY:
        return 'unsafe_body_table_changed'
    if changes:
        return 'suspicious_boundary_table_changed'
    return 'unchanged'


def _classify_baseline_only_table(table: dict, removed_objects: list) -> dict:
    record = dict(table)
    overlap = _removed_candidate_overlap(table, removed_objects)
    region = table.get('region', '')
    if region == REGION_BODY:
        classification = 'unsafe_body_table_loss'
        interpretation = 'Body-region table disappeared after filtering.'
    elif region in {REGION_TOP, REGION_BOTTOM} and overlap.get('overlap_count'):
        classification = 'likely_header_footer_false_positive'
        interpretation = 'Boundary-region baseline-only table overlaps or sits near approved removed header/footer/page-number objects.'
    elif region in {REGION_TOP, REGION_BOTTOM}:
        classification = 'ambiguous_boundary_table_loss'
        interpretation = 'Boundary-region baseline-only table did not clearly overlap approved removals.'
    else:
        classification = 'ambiguous_table_loss'
        interpretation = 'Table disappeared after filtering, but its region is unclear.'

    record.update({
        'removed_candidate_overlap': overlap,
        'classification': classification,
        'interpretation': interpretation,
    })
    return record


def _removed_candidate_overlap(table: dict, removed_objects: list) -> dict:
    matches = []
    table_bbox = table.get('bbox')
    for removed in removed_objects or []:
        if table.get('page_index') != removed.get('page_index'):
            continue
        overlap = _bbox_overlap_ratio(table_bbox, removed.get('bbox'))
        gap = _bbox_gap(table_bbox, removed.get('bbox'))
        if overlap <= 0.0 and gap > 12.0:
            continue
        matches.append({
            'candidate_id': removed.get('candidate_id', ''),
            'proposed_role': removed.get('proposed_role', ''),
            'region': removed.get('region', ''),
            'overlap_ratio': round(overlap, 3),
            'bbox_gap': round(gap, 2),
            'text_preview': removed.get('text_preview', '') or _preview_text(removed, max_length=80),
        })

    roles = Counter(match.get('proposed_role', '') for match in matches)
    return {
        'overlap_count': len(matches),
        'roles': dict(sorted(roles.items())),
        'matches': matches,
    }


def _bbox_gap(first, second) -> float:
    first = _json_bbox(first)
    second = _json_bbox(second)
    dx = max(float(second[0]) - float(first[2]), float(first[0]) - float(second[2]), 0.0)
    dy = max(float(second[1]) - float(first[3]), float(first[1]) - float(second[3]), 0.0)
    return (dx * dx + dy * dy) ** 0.5


def _table_delta_summary(
        baseline_tables: list,
        filtered_tables: list,
        baseline_only: list,
        filtered_only: list,
        changed_common: list) -> dict:
    baseline_only_regions = Counter(table.get('region', '') for table in baseline_only or [])
    overlap_count = sum(
        1 for table in baseline_only or []
        if table.get('removed_candidate_overlap', {}).get('overlap_count', 0))
    body_loss = [
        table for table in baseline_only or []
        if table.get('region') == REGION_BODY
    ]
    likely_pollution = [
        table for table in baseline_only or []
        if table.get('classification') == 'likely_header_footer_false_positive'
    ]
    changed_body = [
        table for table in changed_common or []
        if table.get('region') == REGION_BODY
    ]
    changes_affect_body = bool(body_loss or changed_body)
    top_bottom_loss = sum(
        count for region, count in baseline_only_regions.items()
        if region in {REGION_TOP, REGION_BOTTOM})
    if changes_affect_body:
        classification = 'unsafe'
    elif filtered_only or changed_common:
        classification = 'suspicious'
    elif not baseline_only:
        classification = 'no_delta'
    elif len(likely_pollution) == len(baseline_only or []):
        classification = 'expected'
    elif baseline_only:
        classification = 'ambiguous'

    return {
        'baseline_table_count': len(baseline_tables or []),
        'filtered_table_count': len(filtered_tables or []),
        'table_count_delta': len(filtered_tables or []) - len(baseline_tables or []),
        'baseline_only_table_count': len(baseline_only or []),
        'filtered_only_table_count': len(filtered_only or []),
        'changed_common_table_count': len(changed_common or []),
        'body_region_baseline_only_table_count': len(body_loss),
        'top_bottom_baseline_only_table_count': top_bottom_loss,
        'tables_overlapping_removed_candidates_count': overlap_count,
        'suspicious_body_table_loss_count': len(body_loss),
        'likely_header_footer_false_positive_table_count': len(likely_pollution),
        'table_changes_limited_to_top_bottom': (
            not changes_affect_body and
            len(baseline_only or []) == top_bottom_loss),
        'table_changes_affect_body_region': changes_affect_body,
        'classification': classification,
    }


def _table_delta_warnings(
        summary: dict,
        baseline_only: list,
        filtered_only: list,
        changed_common: list) -> list:
    warnings = []
    body_loss = [
        table for table in baseline_only or []
        if table.get('region') == REGION_BODY
    ]
    if body_loss:
        warnings.append({
            'type': 'body_region_table_disappeared',
            'count': len(body_loss),
        })
    ambiguous = [
        table for table in baseline_only or []
        if table.get('classification') in {
            'ambiguous_boundary_table_loss',
            'ambiguous_table_loss',
        }
    ]
    if ambiguous:
        warnings.append({
            'type': 'ambiguous_table_delta',
            'count': len(ambiguous),
        })
    if filtered_only:
        warnings.append({
            'type': 'filtered_only_table_detected',
            'count': len(filtered_only),
        })
    if changed_common:
        warnings.append({
            'type': 'common_table_changed',
            'count': len(changed_common),
        })
    if (
            summary.get('baseline_only_table_count') and
            summary.get('likely_header_footer_false_positive_table_count') !=
            summary.get('baseline_only_table_count')):
        warnings.append({
            'type': 'not_all_baseline_only_tables_explained_by_removed_candidates',
            'explained': summary.get('likely_header_footer_false_positive_table_count'),
            'baseline_only': summary.get('baseline_only_table_count'),
        })
    return warnings


def _table_delta_by_page(tables: list) -> list:
    pages = defaultdict(lambda: {'page_index': None, 'page_number': None, 'table_count': 0})
    for table in tables or []:
        page_index = table.get('page_index')
        pages[page_index]['page_index'] = page_index
        pages[page_index]['page_number'] = table.get('page_number')
        pages[page_index]['table_count'] += 1
    return sorted(pages.values(), key=lambda item: item.get('page_number') or 0)


def _table_delta_by_region(tables: list) -> dict:
    return dict(sorted(Counter(table.get('region', '') for table in tables or []).items()))


def _table_delta_safe_for_phase_2r(summary: dict, warnings: list) -> bool:
    warning_types = {warning.get('type') for warning in warnings or []}
    blocking = {
        'body_region_table_disappeared',
        'ambiguous_table_delta',
        'filtered_only_table_detected',
        'common_table_changed',
        'not_all_baseline_only_tables_explained_by_removed_candidates',
    }
    return (
        summary.get('classification') in {'expected', 'no_delta'} and
        not warning_types.intersection(blocking))


def _table_delta_recommendation(summary: dict, warnings: list) -> str:
    if _table_delta_safe_for_phase_2r(summary, warnings):
        if summary.get('classification') == 'expected':
            return 'Table delta is limited to boundary-region tables explained by approved removals; Phase 2R can remain opt-in and guarded.'
        return 'No table delta was detected; Phase 2R can remain opt-in and guarded.'
    if summary.get('table_changes_affect_body_region'):
        return 'Do not integrate production filtering yet; body-region table changes require inspection.'
    return 'Keep Phase 2R blocked or investigative until ambiguous/changed table deltas are reviewed.'


def _body_table_root_disabled_summary(table_delta_report: dict) -> dict:
    delta_summary = (table_delta_report or {}).get('summary') or {}
    return {
        'body_region_baseline_only_table_count': delta_summary.get('body_region_baseline_only_table_count', 0),
        'changed_common_table_count': delta_summary.get('changed_common_table_count', 0),
        'pages_affected': [],
        'likely_false_positive_table_count': 0,
        'likely_header_footer_pollution_table_count': 0,
        'possible_real_body_table_loss_count': 0,
        'unsafe_table_delta_count': 0,
        'changed_body_table_geometry_count': 0,
        'top_bottom_only_table_delta_count': 0,
        'classification': 'disabled',
    }


def _body_table_root_baseline_only_finding(table: dict, removed_objects: list) -> dict:
    table = dict(table)
    proximity = _table_removed_proximity(table, removed_objects)
    region = table.get('region', '')
    body_intersection = region == REGION_BODY
    boundary_intersection = region in {REGION_TOP, REGION_BOTTOM}
    small_artifact_shape = _small_artifact_like_table(table)
    roles = set((proximity.get('overlap', {}) or {}).get('roles', {}).keys())

    if boundary_intersection and proximity.get('overlap_count'):
        likely_cause = (
            'page_number_pollution_removed'
            if roles == {ROLE_PAGE_NUMBER} else
            'header_footer_pollution_removed')
        severity = 'safe'
    elif body_intersection and proximity.get('overlap_count') and small_artifact_shape:
        likely_cause = 'baseline_false_positive_table'
        severity = 'review'
    elif body_intersection:
        likely_cause = 'possible_real_body_table_loss'
        severity = 'unsafe'
    elif proximity.get('nearest_distance') is not None and proximity.get('nearest_distance') <= 24.0:
        likely_cause = 'table_geometry_changed_near_removed_artifact'
        severity = 'review'
    else:
        likely_cause = 'insufficient_evidence'
        severity = 'review'

    return {
        'finding_type': 'baseline_only_table',
        'page_index': table.get('page_index'),
        'page_number': table.get('page_number'),
        'baseline_table_id': table.get('table_id', ''),
        'matched_filtered_table_id': '',
        'region': region,
        'bbox': _json_bbox(table.get('bbox')),
        'row_count': int(table.get('row_count') or 0),
        'column_count': int(table.get('column_count') or 0),
        'cell_count': int(table.get('cell_count') or 0),
        'text_preview': _preview_text(table, max_length=100),
        'bbox_intersects_body_region': body_intersection,
        'bbox_intersects_top_bottom_artifact': boundary_intersection and bool(proximity.get('overlap_count')),
        'removed_candidate_proximity': proximity,
        'likely_cause': likely_cause,
        'severity': severity,
        'reason': _body_table_root_reason(likely_cause, severity),
    }


def _body_table_root_changed_common_finding(change: dict, removed_objects: list) -> dict:
    change = dict(change)
    baseline = dict(change.get('baseline_table') or {})
    filtered = dict(change.get('filtered_table') or {})
    proximity = _table_removed_proximity(baseline, removed_objects)
    region = change.get('region') or baseline.get('region', '')
    changes = list(change.get('changes', []) or [])
    structure_changed = any(
        item in changes
        for item in ('row_count_changed', 'column_count_changed', 'cell_count_changed'))
    body_intersection = region == REGION_BODY
    boundary_intersection = region in {REGION_TOP, REGION_BOTTOM}
    near_removed = (
        bool(proximity.get('overlap_count')) or
        (
            proximity.get('nearest_distance') is not None and
            proximity.get('nearest_distance') <= 24.0))

    if body_intersection and structure_changed:
        likely_cause = 'possible_real_body_table_loss'
        severity = 'unsafe'
    elif body_intersection and near_removed:
        likely_cause = 'table_geometry_changed_near_removed_artifact'
        severity = 'review'
    elif body_intersection:
        likely_cause = 'insufficient_evidence'
        severity = 'unsafe'
    elif boundary_intersection and near_removed:
        likely_cause = 'table_geometry_changed_near_removed_artifact'
        severity = 'safe' if not structure_changed else 'review'
    elif boundary_intersection:
        likely_cause = 'insufficient_evidence'
        severity = 'review'
    else:
        likely_cause = 'insufficient_evidence'
        severity = 'review'

    return {
        'finding_type': 'changed_common_table',
        'page_index': change.get('page_index'),
        'page_number': change.get('page_number'),
        'baseline_table_id': baseline.get('table_id', ''),
        'matched_filtered_table_id': filtered.get('table_id', ''),
        'region': region,
        'baseline_bbox': _json_bbox(baseline.get('bbox')),
        'filtered_bbox': _json_bbox(filtered.get('bbox')),
        'bbox': _json_bbox(baseline.get('bbox')),
        'row_count': int(baseline.get('row_count') or 0),
        'filtered_row_count': int(filtered.get('row_count') or 0),
        'column_count': int(baseline.get('column_count') or 0),
        'filtered_column_count': int(filtered.get('column_count') or 0),
        'cell_count': int(baseline.get('cell_count') or 0),
        'filtered_cell_count': int(filtered.get('cell_count') or 0),
        'changes': changes,
        'text_preview': _preview_text(baseline, max_length=100),
        'bbox_intersects_body_region': body_intersection,
        'bbox_intersects_top_bottom_artifact': boundary_intersection and bool(proximity.get('overlap_count')),
        'removed_candidate_proximity': proximity,
        'likely_cause': likely_cause,
        'severity': severity,
        'reason': _body_table_root_reason(likely_cause, severity),
    }


def _small_artifact_like_table(table: dict) -> bool:
    return (
        int(table.get('row_count') or 0) <= 1 and
        int(table.get('column_count') or 0) <= 3 and
        int(table.get('cell_count') or 0) <= 3)


def _table_removed_proximity(table: dict, removed_objects: list) -> dict:
    overlap = _removed_candidate_overlap(table, removed_objects)
    nearest = _nearest_removed_candidate(table, removed_objects)
    return {
        'overlap_count': overlap.get('overlap_count', 0),
        'overlap': overlap,
        'nearest_distance': nearest.get('distance'),
        'nearest_candidate': nearest.get('candidate'),
    }


def _nearest_removed_candidate(table: dict, removed_objects: list) -> dict:
    nearest = None
    for removed in removed_objects or []:
        if table.get('page_index') != removed.get('page_index'):
            continue
        distance = _bbox_gap(table.get('bbox'), removed.get('bbox'))
        candidate = {
            'candidate_id': removed.get('candidate_id', ''),
            'proposed_role': removed.get('proposed_role', ''),
            'region': removed.get('region', ''),
            'bbox_gap': round(distance, 2),
            'text_preview': removed.get('text_preview', '') or _preview_text(removed, max_length=80),
        }
        if nearest is None or distance < nearest['distance']:
            nearest = {'distance': distance, 'candidate': candidate}

    if nearest is None:
        return {'distance': None, 'candidate': {}}
    nearest['distance'] = round(nearest['distance'], 2)
    return nearest


def _body_table_root_reason(likely_cause: str, severity: str) -> str:
    if likely_cause == 'header_footer_pollution_removed':
        return 'Boundary table overlaps approved header/footer/page-number removals and is likely parser pollution.'
    if likely_cause == 'page_number_pollution_removed':
        return 'Boundary table is explained by approved page-number removals.'
    if likely_cause == 'baseline_false_positive_table':
        return 'Small body-region table overlaps approved removals; keep for manual review as a likely false positive.'
    if likely_cause == 'possible_real_body_table_loss':
        return 'Body-region table structure may have been lost or changed; production integration remains blocked.'
    if likely_cause == 'table_geometry_changed_near_removed_artifact':
        return f'Table geometry changed near approved removals; severity is {severity}.'
    return 'Insufficient evidence to classify this table delta safely.'


def _body_table_root_summary(
        baseline_only_findings: list,
        changed_common_findings: list) -> dict:
    findings = baseline_only_findings + changed_common_findings
    pages_affected = sorted({
        finding.get('page_number')
        for finding in findings
        if finding.get('page_number') is not None
    })
    cause_counts = Counter(finding.get('likely_cause', '') for finding in findings)
    severity_counts = Counter(finding.get('severity', '') for finding in findings)
    changed_body = [
        finding for finding in changed_common_findings
        if finding.get('region') == REGION_BODY
    ]
    top_bottom_only = [
        finding for finding in findings
        if finding.get('region') in {REGION_TOP, REGION_BOTTOM}
    ]
    body_baseline_only = [
        finding for finding in baseline_only_findings
        if finding.get('region') == REGION_BODY
    ]
    return {
        'body_region_baseline_only_table_count': len(body_baseline_only),
        'changed_common_table_count': len(changed_common_findings),
        'pages_affected': pages_affected,
        'likely_false_positive_table_count': cause_counts.get('baseline_false_positive_table', 0),
        'likely_header_footer_pollution_table_count': (
            cause_counts.get('header_footer_pollution_removed', 0) +
            cause_counts.get('page_number_pollution_removed', 0)),
        'possible_real_body_table_loss_count': cause_counts.get('possible_real_body_table_loss', 0),
        'unsafe_table_delta_count': severity_counts.get('unsafe', 0),
        'review_table_delta_count': severity_counts.get('review', 0),
        'safe_table_delta_count': severity_counts.get('safe', 0),
        'changed_body_table_geometry_count': len(changed_body),
        'top_bottom_only_table_delta_count': len(top_bottom_only),
        'likely_cause_counts': dict(sorted(cause_counts.items())),
        'severity_counts': dict(sorted(severity_counts.items())),
        'classification': 'unsafe' if severity_counts.get('unsafe', 0) else (
            'review' if severity_counts.get('review', 0) else 'safe'),
    }


def _body_table_root_overlap_summary(findings: list) -> dict:
    overlap_count = 0
    near_count = 0
    distances = []
    roles = Counter()
    for finding in findings or []:
        proximity = finding.get('removed_candidate_proximity') or {}
        if proximity.get('overlap_count', 0):
            overlap_count += 1
        distance = proximity.get('nearest_distance')
        if distance is not None:
            distances.append(float(distance))
            if float(distance) <= 24.0:
                near_count += 1
        for role, count in (proximity.get('overlap', {}).get('roles') or {}).items():
            roles[role] += count

    return {
        'tables_overlapping_removed_candidates': overlap_count,
        'tables_near_removed_candidates': near_count,
        'nearest_distance_min': round(min(distances), 2) if distances else None,
        'nearest_distance_max': round(max(distances), 2) if distances else None,
        'overlap_roles': dict(sorted(roles.items())),
    }


def _body_table_root_warnings(summary: dict, findings: list) -> list:
    warnings = []
    if summary.get('possible_real_body_table_loss_count', 0):
        warnings.append({
            'type': 'possible_real_body_table_loss',
            'count': summary.get('possible_real_body_table_loss_count'),
        })
    if summary.get('unsafe_table_delta_count', 0):
        warnings.append({
            'type': 'unsafe_table_delta',
            'count': summary.get('unsafe_table_delta_count'),
        })
    if summary.get('changed_body_table_geometry_count', 0):
        warnings.append({
            'type': 'changed_body_table_geometry',
            'count': summary.get('changed_body_table_geometry_count'),
        })
    insufficient = [
        finding for finding in findings or []
        if finding.get('likely_cause') == 'insufficient_evidence'
    ]
    if insufficient:
        warnings.append({
            'type': 'insufficient_table_delta_evidence',
            'count': len(insufficient),
        })
    return warnings


def _body_table_root_safe_for_phase_2s(summary: dict, warnings: list) -> bool:
    return (
        not summary.get('unsafe_table_delta_count', 0) and
        not summary.get('possible_real_body_table_loss_count', 0) and
        not warnings)


def _body_table_root_recommendation(summary: dict, warnings: list) -> str:
    if _body_table_root_safe_for_phase_2s(summary, warnings):
        return 'No unsafe body table delta remains; Phase 2S can remain opt-in and guarded.'
    if summary.get('possible_real_body_table_loss_count', 0):
        return 'Keep production integration blocked; inspect possible real body table loss before Phase 2S.'
    return 'Continue with report-only inspection before any production filtering integration.'


def _body_table_geometry_disabled_summary(root_report: dict) -> dict:
    root_summary = (root_report or {}).get('summary') or {}
    return {
        'changed_body_table_geometry_count': root_summary.get('changed_body_table_geometry_count', 0),
        'harmless_bbox_only_shift_count': 0,
        'header_footer_boundary_cleanup_count': 0,
        'stream_table_boundary_adjustment_count': 0,
        'possible_body_table_structure_change_count': 0,
        'possible_cell_loss_count': 0,
        'unchanged_row_column_cell_count': 0,
        'changed_row_column_cell_count': 0,
        'text_cell_signature_preserved_count': 0,
        'text_cell_signature_changed_count': 0,
        'affected_pages': [],
        'unsafe_count': 0,
        'review_count': 0,
        'safe_count': 0,
        'classification': 'disabled',
    }


def _body_table_geometry_finding(change: dict, removed_objects: list) -> dict:
    baseline = _copy_table_record(change.get('baseline_table') or {})
    filtered = _copy_table_record(change.get('filtered_table') or {})
    baseline_bbox = _json_bbox(baseline.get('bbox'))
    filtered_bbox = _json_bbox(filtered.get('bbox'))
    bbox_delta = _body_table_bbox_delta(baseline_bbox, filtered_bbox)
    count_delta = _body_table_count_delta(baseline, filtered)
    text_signature = _body_table_text_signature_summary(baseline, filtered)
    cell_bbox_summary = _body_table_cell_bbox_change_summary(baseline, filtered)
    proximity = _table_removed_proximity(baseline, removed_objects)
    top_bottom_edge_only = _body_table_top_bottom_edge_only(bbox_delta)
    changed_area_body_intersection = baseline.get('region') == REGION_BODY and _bbox_area_delta(
        baseline_bbox,
        filtered_bbox) > 0.0
    edge_near_removed = (
        proximity.get('nearest_distance') is not None and
        proximity.get('nearest_distance') <= 24.0)
    structure_counts_preserved = not any(count_delta.values())
    text_preserved = text_signature.get('preserved')
    only_outer_bbox_changed = (
        structure_counts_preserved and
        text_preserved is True and
        cell_bbox_summary.get('changed_cell_bbox_count', 0) == 0)
    likely_cause, severity = _body_table_geometry_classification(
        count_delta,
        text_signature,
        cell_bbox_summary,
        only_outer_bbox_changed,
        edge_near_removed,
        changed_area_body_intersection,
        top_bottom_edge_only)

    return {
        'page_index': change.get('page_index'),
        'page_number': change.get('page_number'),
        'baseline_table_id': baseline.get('table_id', ''),
        'filtered_table_id': filtered.get('table_id', ''),
        'baseline_bbox': baseline_bbox,
        'filtered_bbox': filtered_bbox,
        'bbox_delta': bbox_delta,
        'bbox_overlap_ratio': round(_bbox_overlap_ratio(baseline_bbox, filtered_bbox), 3),
        'row_count_before': int(baseline.get('row_count') or 0),
        'row_count_after': int(filtered.get('row_count') or 0),
        'column_count_before': int(baseline.get('column_count') or 0),
        'column_count_after': int(filtered.get('column_count') or 0),
        'cell_count_before': int(baseline.get('cell_count') or 0),
        'cell_count_after': int(filtered.get('cell_count') or 0),
        'row_column_cell_count_delta': count_delta,
        'cell_bbox_change_summary': cell_bbox_summary,
        'cell_text_signature_before': text_signature.get('before', []),
        'cell_text_signature_after': text_signature.get('after', []),
        'text_cell_signature_preserved': text_signature.get('preserved'),
        'text_cell_signature_changed': text_signature.get('changed'),
        'text_cell_content_appears_preserved': text_signature.get('preserved') is True,
        'only_outer_bbox_changed': only_outer_bbox_changed,
        'changed_bbox_edge_near_removed_candidate': edge_near_removed,
        'distance_to_nearest_removed_candidate': proximity.get('nearest_distance'),
        'nearest_removed_candidate': proximity.get('nearest_candidate'),
        'changed_area_intersects_body_text': changed_area_body_intersection,
        'changed_area_top_bottom_edge_only': top_bottom_edge_only,
        'likely_cause': likely_cause,
        'severity': severity,
        'reason': _body_table_geometry_reason(likely_cause, severity),
    }


def _body_table_bbox_delta(baseline_bbox: list, filtered_bbox: list) -> dict:
    width_before = max(float(baseline_bbox[2]) - float(baseline_bbox[0]), 0.0)
    width_after = max(float(filtered_bbox[2]) - float(filtered_bbox[0]), 0.0)
    height_before = max(float(baseline_bbox[3]) - float(baseline_bbox[1]), 0.0)
    height_after = max(float(filtered_bbox[3]) - float(filtered_bbox[1]), 0.0)
    return {
        'left': round(float(filtered_bbox[0]) - float(baseline_bbox[0]), 2),
        'top': round(float(filtered_bbox[1]) - float(baseline_bbox[1]), 2),
        'right': round(float(filtered_bbox[2]) - float(baseline_bbox[2]), 2),
        'bottom': round(float(filtered_bbox[3]) - float(baseline_bbox[3]), 2),
        'width': round(width_after - width_before, 2),
        'height': round(height_after - height_before, 2),
    }


def _body_table_count_delta(baseline: dict, filtered: dict) -> dict:
    return {
        'row_count_changed': int(baseline.get('row_count') or 0) != int(filtered.get('row_count') or 0),
        'column_count_changed': int(baseline.get('column_count') or 0) != int(filtered.get('column_count') or 0),
        'cell_count_changed': int(baseline.get('cell_count') or 0) != int(filtered.get('cell_count') or 0),
    }


def _body_table_text_signature_summary(baseline: dict, filtered: dict) -> dict:
    before = _body_table_text_signature(baseline)
    after = _body_table_text_signature(filtered)
    available = bool(before or after)
    preserved = before == after if available else None
    return {
        'before': before,
        'after': after,
        'available': available,
        'preserved': preserved,
        'changed': bool(available and before != after),
    }


def _body_table_text_signature(table: dict) -> list:
    signature = table.get('cell_text_signature')
    if signature:
        return list(signature)
    cell_summaries = table.get('cell_summaries', []) or []
    return [
        normalize_text(cell.get('text_preview', ''))
        for cell in cell_summaries
    ]


def _body_table_cell_bbox_change_summary(baseline: dict, filtered: dict) -> dict:
    before = _body_table_cell_bbox_signature(baseline)
    after = _body_table_cell_bbox_signature(filtered)
    available = bool(before or after)
    pair_count = min(len(before), len(after))
    changed = []
    for index in range(pair_count):
        if _bbox_max_delta(before[index], after[index]) > 1.0:
            changed.append({
                'cell_index': index,
                'bbox_delta': _body_table_bbox_delta(before[index], after[index]),
            })
    missing = abs(len(before) - len(after))
    return {
        'available': available,
        'cell_bbox_count_before': len(before),
        'cell_bbox_count_after': len(after),
        'changed_cell_bbox_count': len(changed),
        'missing_or_extra_cell_bbox_count': missing,
        'changed_cell_bboxes': changed[:5],
    }


def _body_table_cell_bbox_signature(table: dict) -> list:
    signature = table.get('cell_bbox_signature')
    if signature:
        return [_json_bbox(bbox) for bbox in signature]
    cell_summaries = table.get('cell_summaries', []) or []
    return [
        _json_bbox(cell.get('bbox'))
        for cell in cell_summaries
    ]


def _body_table_top_bottom_edge_only(bbox_delta: dict) -> bool:
    horizontal_stable = (
        abs(float(bbox_delta.get('left', 0.0))) <= 1.0 and
        abs(float(bbox_delta.get('right', 0.0))) <= 1.0 and
        abs(float(bbox_delta.get('width', 0.0))) <= 1.0)
    vertical_changed = (
        abs(float(bbox_delta.get('top', 0.0))) > 1.0 or
        abs(float(bbox_delta.get('bottom', 0.0))) > 1.0 or
        abs(float(bbox_delta.get('height', 0.0))) > 1.0)
    return horizontal_stable and vertical_changed


def _bbox_area_delta(first: list, second: list) -> float:
    first = _json_bbox(first)
    second = _json_bbox(second)
    first_area = max((first[2] - first[0]) * (first[3] - first[1]), 0.0)
    second_area = max((second[2] - second[0]) * (second[3] - second[1]), 0.0)
    overlap_width = max(min(first[2], second[2]) - max(first[0], second[0]), 0.0)
    overlap_height = max(min(first[3], second[3]) - max(first[1], second[1]), 0.0)
    overlap_area = overlap_width * overlap_height
    return (first_area - overlap_area) + (second_area - overlap_area)


def _body_table_geometry_classification(
        count_delta: dict,
        text_signature: dict,
        cell_bbox_summary: dict,
        only_outer_bbox_changed: bool,
        edge_near_removed: bool,
        changed_area_body_intersection: bool,
        top_bottom_edge_only: bool) -> tuple:
    if count_delta.get('cell_count_changed'):
        return 'possible_cell_loss', 'unsafe'
    if count_delta.get('row_count_changed') or count_delta.get('column_count_changed'):
        return 'possible_body_table_structure_change', 'unsafe'
    if text_signature.get('changed'):
        return 'possible_body_table_structure_change', 'unsafe'
    if not text_signature.get('available') and not cell_bbox_summary.get('available'):
        return 'insufficient_evidence', 'review'
    if only_outer_bbox_changed and edge_near_removed:
        return 'header_footer_boundary_cleanup', 'safe'
    if only_outer_bbox_changed:
        return 'harmless_bbox_boundary_shift', 'review' if changed_area_body_intersection else 'safe'
    if text_signature.get('preserved') is True and top_bottom_edge_only:
        return 'stream_table_boundary_adjustment', 'review' if changed_area_body_intersection else 'safe'
    if text_signature.get('preserved') is True and cell_bbox_summary.get('changed_cell_bbox_count', 0):
        return 'stream_table_boundary_adjustment', 'review'
    return 'insufficient_evidence', 'review'


def _body_table_geometry_reason(likely_cause: str, severity: str) -> str:
    if likely_cause == 'harmless_bbox_boundary_shift':
        return 'Rows, columns, cells, and cell text signatures are preserved; only bbox boundaries moved.'
    if likely_cause == 'header_footer_boundary_cleanup':
        return 'Table boundary shift is near approved header/footer/page-number removals with structure preserved.'
    if likely_cause == 'stream_table_boundary_adjustment':
        return 'Cell text is preserved but stream-table cell or outer boundaries shifted; keep under review.'
    if likely_cause == 'possible_body_table_structure_change':
        return 'Body table row/column or cell text signatures changed; production integration remains blocked.'
    if likely_cause == 'possible_cell_loss':
        return 'Body table cell count changed; treat as unsafe unless later evidence proves removed cells were artifacts.'
    return f'Insufficient table cell evidence; severity is {severity}.'


def _body_table_geometry_summary(findings: list) -> dict:
    cause_counts = Counter(finding.get('likely_cause', '') for finding in findings or [])
    severity_counts = Counter(finding.get('severity', '') for finding in findings or [])
    count_changed = [
        finding for finding in findings or []
        if any(finding.get('row_column_cell_count_delta', {}).values())
    ]
    text_preserved = [
        finding for finding in findings or []
        if finding.get('text_cell_signature_preserved') is True
    ]
    text_changed = [
        finding for finding in findings or []
        if finding.get('text_cell_signature_changed') is True
    ]
    return {
        'changed_body_table_geometry_count': len(findings or []),
        'harmless_bbox_only_shift_count': cause_counts.get('harmless_bbox_boundary_shift', 0),
        'header_footer_boundary_cleanup_count': cause_counts.get('header_footer_boundary_cleanup', 0),
        'stream_table_boundary_adjustment_count': cause_counts.get('stream_table_boundary_adjustment', 0),
        'possible_body_table_structure_change_count': cause_counts.get('possible_body_table_structure_change', 0),
        'possible_cell_loss_count': cause_counts.get('possible_cell_loss', 0),
        'unchanged_row_column_cell_count': len(findings or []) - len(count_changed),
        'changed_row_column_cell_count': len(count_changed),
        'text_cell_signature_preserved_count': len(text_preserved),
        'text_cell_signature_changed_count': len(text_changed),
        'affected_pages': sorted({
            finding.get('page_number')
            for finding in findings or []
            if finding.get('page_number') is not None
        }),
        'unsafe_count': severity_counts.get('unsafe', 0),
        'review_count': severity_counts.get('review', 0),
        'safe_count': severity_counts.get('safe', 0),
        'likely_cause_counts': dict(sorted(cause_counts.items())),
        'severity_counts': dict(sorted(severity_counts.items())),
        'classification': 'unsafe' if severity_counts.get('unsafe', 0) else (
            'review' if severity_counts.get('review', 0) else 'safe'),
    }


def _body_table_geometry_warnings(summary: dict, findings: list) -> list:
    warnings = []
    if summary.get('possible_cell_loss_count', 0):
        warnings.append({
            'type': 'possible_cell_loss',
            'count': summary.get('possible_cell_loss_count'),
        })
    if summary.get('possible_body_table_structure_change_count', 0):
        warnings.append({
            'type': 'possible_body_table_structure_change',
            'count': summary.get('possible_body_table_structure_change_count'),
        })
    if summary.get('unsafe_count', 0):
        warnings.append({
            'type': 'unsafe_body_table_geometry_delta',
            'count': summary.get('unsafe_count'),
        })
    insufficient = [
        finding for finding in findings or []
        if finding.get('likely_cause') == 'insufficient_evidence'
    ]
    if insufficient:
        warnings.append({
            'type': 'insufficient_body_table_geometry_evidence',
            'count': len(insufficient),
        })
    return warnings


def _body_table_geometry_safe_for_phase_2t(summary: dict, warnings: list) -> bool:
    return (
        not summary.get('unsafe_count', 0) and
        not summary.get('possible_cell_loss_count', 0) and
        not summary.get('possible_body_table_structure_change_count', 0) and
        not warnings)


def _body_table_geometry_recommendation(summary: dict, warnings: list) -> str:
    if _body_table_geometry_safe_for_phase_2t(summary, warnings):
        return 'Body table geometry deltas appear structurally preserved; Phase 2T can remain opt-in and guarded.'
    if summary.get('unsafe_count', 0):
        return 'Keep production integration blocked; changed body table geometry still has unsafe structure or text signals.'
    return 'Continue report-only inspection before any production filtering integration.'


def _table_geometry_visual_review_disabled_summary(safety_report: dict) -> dict:
    safety_summary = (safety_report or {}).get('summary') or {}
    return {
        'review_item_count': safety_summary.get('changed_body_table_geometry_count', 0),
        'affected_pages': safety_summary.get('affected_pages', []),
        'row_column_cell_counts_preserved_count': 0,
        'text_cell_signature_preserved_count': 0,
        'requiring_human_approval_count': 0,
        'automatically_unsafe_count': 0,
        'generated_visual_artifact_count': 0,
        'classification_counts': {},
        'classification': 'disabled',
    }


def _table_geometry_visual_artifact_map(artifacts: list) -> dict:
    artifact_map = {}
    for artifact in artifacts or []:
        for key in (
                artifact.get('review_item_id'),
                artifact.get('baseline_table_id'),
                artifact.get('filtered_table_id')):
            if key:
                artifact_map[key] = dict(artifact)
    return artifact_map


def _table_geometry_visual_review_item(index: int, finding: dict, artifact_map: dict) -> dict:
    review_item_id = f'table-geometry-review-{index:03d}'
    baseline_table_id = finding.get('baseline_table_id', '')
    filtered_table_id = finding.get('filtered_table_id', '')
    artifact = (
        artifact_map.get(review_item_id) or
        artifact_map.get(baseline_table_id) or
        artifact_map.get(filtered_table_id) or {})
    classification = _table_geometry_visual_review_classification(finding)
    return {
        'review_item_id': review_item_id,
        'page_index': finding.get('page_index'),
        'page_number': finding.get('page_number'),
        'baseline_table_id': baseline_table_id,
        'filtered_table_id': filtered_table_id,
        'baseline_bbox': _json_bbox(finding.get('baseline_bbox')),
        'filtered_bbox': _json_bbox(finding.get('filtered_bbox')),
        'bbox_delta': dict(finding.get('bbox_delta') or {}),
        'bbox_overlap_ratio': finding.get('bbox_overlap_ratio'),
        'row_count_before': int(finding.get('row_count_before') or 0),
        'row_count_after': int(finding.get('row_count_after') or 0),
        'column_count_before': int(finding.get('column_count_before') or 0),
        'column_count_after': int(finding.get('column_count_after') or 0),
        'cell_count_before': int(finding.get('cell_count_before') or 0),
        'cell_count_after': int(finding.get('cell_count_after') or 0),
        'cell_text_signature_before': list(finding.get('cell_text_signature_before') or []),
        'cell_text_signature_after': list(finding.get('cell_text_signature_after') or []),
        'text_cell_signature_preserved': finding.get('text_cell_signature_preserved'),
        'text_cell_signature_changed': finding.get('text_cell_signature_changed'),
        'nearest_removed_candidate': dict(finding.get('nearest_removed_candidate') or {}),
        'distance_to_nearest_removed_candidate': finding.get(
            'distance_to_nearest_removed_candidate'),
        'likely_cause': finding.get('likely_cause', ''),
        'current_severity': finding.get('severity', ''),
        'short_preview': finding.get('text_preview', ''),
        'review_classification': classification,
        'human_approval_required': classification != 'unsafe_do_not_integrate',
        'human_decision_fields': {
            'approve_safe_boundary_shift': '[ ]',
            'reject_unsafe_table_change': '[ ]',
            'unsure': '[ ]',
        },
        'reviewer_notes': '',
        'visual_artifact': artifact,
    }


def _table_geometry_visual_review_classification(finding: dict) -> str:
    count_delta = finding.get('row_column_cell_count_delta') or {}
    counts_changed = any(bool(value) for value in count_delta.values())
    if (
            finding.get('severity') == 'unsafe' or
            counts_changed or
            finding.get('text_cell_signature_changed')):
        return 'unsafe_do_not_integrate'
    if (
            finding.get('text_cell_signature_preserved') is True and
            not counts_changed and
            finding.get('severity') in ('review', 'safe')):
        return 'likely_safe_but_needs_human_approval'
    return 'suspicious_needs_more_review'


def _table_geometry_visual_rendering_summary(rendering: dict, artifacts: list) -> dict:
    generated_count = len(artifacts or [])
    supported = bool(rendering.get('supported', generated_count > 0))
    skipped_reason = rendering.get('skipped_reason', '')
    if not supported and not skipped_reason:
        skipped_reason = 'visual_rendering_support_not_available_or_not_requested'
    return {
        'supported': supported,
        'generated_artifact_count': generated_count,
        'output_directory': rendering.get('output_directory', ''),
        'skipped_reason': skipped_reason,
    }


def _table_geometry_visual_review_summary(review_items: list, rendering_summary: dict) -> dict:
    classification_counts = Counter(
        item.get('review_classification', '') for item in review_items or [])
    counts_preserved = [
        item for item in review_items or []
        if (
            item.get('row_count_before') == item.get('row_count_after') and
            item.get('column_count_before') == item.get('column_count_after') and
            item.get('cell_count_before') == item.get('cell_count_after'))
    ]
    text_preserved = [
        item for item in review_items or []
        if item.get('text_cell_signature_preserved') is True
    ]
    human_required = [
        item for item in review_items or []
        if item.get('human_approval_required')
    ]
    return {
        'review_item_count': len(review_items or []),
        'affected_pages': sorted({
            item.get('page_number')
            for item in review_items or []
            if item.get('page_number') is not None
        }),
        'row_column_cell_counts_preserved_count': len(counts_preserved),
        'text_cell_signature_preserved_count': len(text_preserved),
        'requiring_human_approval_count': len(human_required),
        'automatically_unsafe_count': classification_counts.get('unsafe_do_not_integrate', 0),
        'generated_visual_artifact_count': rendering_summary.get('generated_artifact_count', 0),
        'classification_counts': dict(sorted(classification_counts.items())),
        'classification': 'unsafe' if classification_counts.get('unsafe_do_not_integrate', 0) else (
            'review' if human_required else 'safe'),
    }


def _table_geometry_visual_review_warnings(
        summary: dict,
        rendering_summary: dict,
        safety_report: dict) -> list:
    warnings = []
    if not safety_report:
        warnings.append({
            'type': 'missing_geometry_safety_report',
            'message': 'No Phase 2S body table geometry safety report was provided.',
        })
    if summary.get('automatically_unsafe_count', 0):
        warnings.append({
            'type': 'unsafe_table_geometry_review_item',
            'count': summary.get('automatically_unsafe_count'),
        })
    if not rendering_summary.get('supported'):
        warnings.append({
            'type': 'visual_rendering_unavailable',
            'message': rendering_summary.get('skipped_reason'),
        })
    if summary.get('requiring_human_approval_count', 0):
        warnings.append({
            'type': 'human_approval_required',
            'count': summary.get('requiring_human_approval_count'),
        })
    return warnings


def _table_geometry_visual_review_safe_for_phase_2u(summary: dict, warnings: list) -> bool:
    warning_types = {warning.get('type') for warning in warnings or []}
    return (
        bool(summary.get('review_item_count', 0)) and
        not summary.get('automatically_unsafe_count', 0) and
        'missing_geometry_safety_report' not in warning_types and
        'human_approval_required' not in warning_types)


def _table_geometry_visual_review_recommendation(summary: dict, warnings: list) -> str:
    if summary.get('automatically_unsafe_count', 0):
        return 'Keep production integration blocked; at least one table geometry item is automatically unsafe.'
    if summary.get('requiring_human_approval_count', 0):
        return 'Use the local-only review pack for human approval before Phase 2U; production integration remains blocked.'
    if _table_geometry_visual_review_safe_for_phase_2u(summary, warnings):
        return 'All review items are approved or safe; Phase 2U may remain opt-in and guarded.'
    return 'Review pack is incomplete; keep the workflow report-only.'


def _copy_table_visual_decisions(decisions: dict) -> dict:
    decisions = decisions or {}
    return {
        'items': [
            dict(item) for item in decisions.get('items', []) or []
        ],
        'summary': dict(decisions.get('summary') or {}),
    }


def _table_visual_decisions_from_pack(pack: dict) -> dict:
    pack = pack or {}
    items = []
    for item in pack.get('review_items', []) or []:
        record = dict(item)
        record.setdefault('manual_decision', DECISION_NONE)
        record.setdefault('checked_decisions', [])
        record['row_column_cell_counts_preserved'] = (
            record.get('row_count_before') == record.get('row_count_after') and
            record.get('column_count_before') == record.get('column_count_after') and
            record.get('cell_count_before') == record.get('cell_count_after'))
        items.append(record)

    decision_counts = defaultdict(int)
    for item in items:
        decision_counts[item.get('manual_decision', DECISION_NONE)] += 1

    return {
        'items': items,
        'summary': {
            'review_item_count': len(items),
            'decision_counts': dict(sorted(decision_counts.items())),
        },
    }


def _table_geometry_visual_gate_disabled_summary(
        decisions: dict,
        expected_review_item_count: int) -> dict:
    parsed_count = len((decisions or {}).get('items', []) or [])
    return {
        'expected_review_item_count': expected_review_item_count,
        'parsed_review_item_count': parsed_count,
        'approve_count': 0,
        'reject_count': 0,
        'unsure_count': 0,
        'missing_decision_count': 0,
        'conflict_decision_count': 0,
        'row_column_cell_preservation_count': 0,
        'text_cell_signature_preservation_count': 0,
        'gate_status': 'blocked',
    }


def _table_geometry_visual_gate_summary(
        items: list,
        expected_review_item_count: int) -> dict:
    decision_counts = Counter(
        item.get('manual_decision', DECISION_NONE) for item in items or [])
    row_preserved = sum(
        1 for item in items or []
        if item.get('row_column_cell_counts_preserved') is True)
    text_preserved = sum(
        1 for item in items or []
        if item.get('text_cell_signature_preserved') is True)
    return {
        'expected_review_item_count': expected_review_item_count,
        'parsed_review_item_count': len(items or []),
        'approve_count': decision_counts.get('approve_safe_boundary_shift', 0),
        'reject_count': decision_counts.get('reject_unsafe_table_change', 0),
        'unsure_count': decision_counts.get('unsure', 0),
        'missing_decision_count': decision_counts.get(DECISION_NONE, 0),
        'conflict_decision_count': decision_counts.get(DECISION_CONFLICT, 0),
        'row_column_cell_preservation_count': row_preserved,
        'text_cell_signature_preservation_count': text_preserved,
        'affected_pages': sorted({
            item.get('page_number')
            for item in items or []
            if item.get('page_number') is not None
        }),
        'gate_status': 'pending',
    }


def _table_geometry_visual_gate_blocking_reasons(summary: dict) -> list:
    reasons = []
    expected = int(summary.get('expected_review_item_count') or 0)
    parsed = int(summary.get('parsed_review_item_count') or 0)
    if expected != 8:
        reasons.append({
            'type': 'unexpected_expected_review_item_count',
            'expected_required': 8,
            'observed': expected,
        })
    if parsed != expected:
        reasons.append({
            'type': 'parsed_review_item_count_mismatch',
            'expected': expected,
            'observed': parsed,
        })
    if summary.get('approve_count', 0) != expected:
        reasons.append({
            'type': 'not_all_items_approved',
            'expected': expected,
            'observed': summary.get('approve_count', 0),
        })
    for key, reason_type in (
            ('reject_count', 'rejected_items_present'),
            ('unsure_count', 'unsure_items_present'),
            ('missing_decision_count', 'missing_decisions_present'),
            ('conflict_decision_count', 'conflicting_decisions_present')):
        if summary.get(key, 0):
            reasons.append({
                'type': reason_type,
                'count': summary.get(key, 0),
            })
    if summary.get('row_column_cell_preservation_count', 0) != expected:
        reasons.append({
            'type': 'row_column_cell_counts_not_fully_preserved',
            'expected': expected,
            'observed': summary.get('row_column_cell_preservation_count', 0),
        })
    if summary.get('text_cell_signature_preservation_count', 0) != expected:
        reasons.append({
            'type': 'text_cell_signatures_not_fully_preserved',
            'expected': expected,
            'observed': summary.get('text_cell_signature_preservation_count', 0),
        })
    return reasons


def _table_geometry_visual_gate_recommendation(gate_status: str, blocking_reasons: list) -> str:
    if gate_status == 'passed':
        return 'Visual approval gate passed; Phase 2V may remain internal, opt-in, and guarded.'
    reason_types = ', '.join(reason.get('type', '') for reason in blocking_reasons or [])
    return f'Visual approval gate blocked; resolve: {reason_types}.'


def _filtered_docx_disabled_summary(
        baseline_docx_path: str,
        filtered_docx_path: str,
        experiment_report: dict,
        gate_report: dict) -> dict:
    experiment_summary = (experiment_report or {}).get('summary') or {}
    return {
        'baseline_docx_path': baseline_docx_path or '',
        'filtered_docx_path': filtered_docx_path or '',
        'table_visual_approval_gate_status': _filtered_docx_gate_summary(gate_report).get('gate_status'),
        'baseline_raw_block_count': experiment_summary.get('baseline_raw_block_count', 0),
        'filtered_raw_block_count': experiment_summary.get('filtered_raw_block_count', 0),
        'removed_approved_header_footer_page_number_count': experiment_summary.get('removed_raw_block_count', 0),
        'body_region_removed_count': experiment_summary.get('body_region_removed_count', 0),
        'gate_status': 'blocked',
    }


def _filtered_docx_summary(
        experiment_report: dict,
        gate_report: dict,
        baseline_docx_metrics: dict,
        filtered_docx_metrics: dict,
        normal_conversion_check: dict) -> dict:
    experiment_summary = (experiment_report or {}).get('summary') or {}
    pollution = (experiment_report or {}).get('header_footer_pollution_reduction') or {}
    gate_status = _filtered_docx_gate_summary(gate_report).get('gate_status')
    return {
        'table_visual_approval_gate_status': gate_status,
        'baseline_raw_block_count': experiment_summary.get('baseline_raw_block_count', 0),
        'filtered_raw_block_count': experiment_summary.get('filtered_raw_block_count', 0),
        'removed_approved_header_footer_page_number_count': experiment_summary.get('removed_raw_block_count', 0),
        'baseline_parsed_text_block_count': experiment_summary.get('baseline_parsed_text_block_count', 0),
        'filtered_parsed_text_block_count': experiment_summary.get('filtered_parsed_text_block_count', 0),
        'baseline_body_text_block_count': experiment_summary.get('baseline_body_text_block_count', 0),
        'filtered_body_text_block_count': experiment_summary.get('filtered_body_text_block_count', 0),
        'baseline_table_count': experiment_summary.get('baseline_table_count', 0),
        'filtered_table_count': experiment_summary.get('filtered_table_count', 0),
        'baseline_image_count': experiment_summary.get('baseline_image_count', 0),
        'filtered_image_count': experiment_summary.get('filtered_image_count', 0),
        'baseline_section_count': experiment_summary.get('baseline_section_count', 0),
        'filtered_section_count': experiment_summary.get('filtered_section_count', 0),
        'body_region_removed_count': experiment_summary.get('body_region_removed_count', 0),
        'rejected_unsure_layout_placeholder_removed_count': experiment_summary.get(
            'rejected_unsure_layout_placeholder_removed_count', 0),
        'parsed_text_block_delta': pollution.get('parsed_text_block_delta', 0),
        'body_text_block_delta': pollution.get('body_text_block_delta', 0),
        'baseline_docx_paragraph_count': baseline_docx_metrics.get('paragraph_count', 0),
        'filtered_docx_paragraph_count': filtered_docx_metrics.get('paragraph_count', 0),
        'baseline_docx_table_count': baseline_docx_metrics.get('table_count', 0),
        'filtered_docx_table_count': filtered_docx_metrics.get('table_count', 0),
        'normal_conversion_still_works': bool(normal_conversion_check.get('passed', False)),
        'state_restored_or_reloaded': bool(normal_conversion_check.get('state_restored_or_reloaded', False)),
    }


def _filtered_docx_gate_summary(gate_report: dict) -> dict:
    gate_report = gate_report or {}
    summary = gate_report.get('summary') or {}
    return {
        'gate_status': gate_report.get('gate_status') or summary.get('gate_status') or '',
        'approve_count': summary.get('approve_count', 0),
        'reject_count': summary.get('reject_count', 0),
        'unsure_count': summary.get('unsure_count', 0),
        'missing_decision_count': summary.get('missing_decision_count', 0),
        'expected_review_item_count': summary.get('expected_review_item_count', 0),
        'parsed_review_item_count': summary.get('parsed_review_item_count', 0),
    }


def _filtered_docx_files_report(
        baseline_docx_path: str,
        filtered_docx_path: str,
        baseline_docx_metrics: dict,
        filtered_docx_metrics: dict) -> dict:
    baseline_status = _filtered_docx_file_status(
        baseline_docx_path,
        baseline_docx_metrics)
    filtered_status = _filtered_docx_file_status(
        filtered_docx_path,
        filtered_docx_metrics)
    return {
        'baseline': baseline_status,
        'filtered': filtered_status,
    }


def _filtered_docx_file_status(path: str, metrics: dict) -> dict:
    path = path or ''
    exists = os.path.exists(path) if path else False
    size = int(metrics.get('size_bytes') or (os.path.getsize(path) if exists else 0))
    return {
        'path': path,
        'local_only_path': _is_local_report_path(path),
        'exists': bool(metrics.get('exists', exists)),
        'size_bytes': size,
        'empty': size <= 0,
        'paragraph_count': int(metrics.get('paragraph_count') or 0),
        'table_count': int(metrics.get('table_count') or 0),
    }


def _is_local_report_path(path: str) -> bool:
    normalized = normalize_text(path).replace('\\', '/')
    return normalized.startswith('local_reports/')


def _filtered_docx_warnings(
        summary: dict,
        docx_files: dict,
        gate_report: dict,
        normal_conversion_check: dict) -> list:
    warnings = []
    gate_summary = _filtered_docx_gate_summary(gate_report)
    if gate_summary.get('gate_status') != 'passed':
        warnings.append({
            'type': 'table_visual_approval_gate_not_passed',
            'gate_status': gate_summary.get('gate_status'),
        })
    for label in ('baseline', 'filtered'):
        status = docx_files.get(label, {})
        if not status.get('local_only_path'):
            warnings.append({
                'type': f'{label}_docx_path_not_local_only',
                'path': status.get('path'),
            })
        if not status.get('exists'):
            warnings.append({
                'type': f'{label}_docx_missing',
                'path': status.get('path'),
            })
        elif status.get('empty'):
            warnings.append({
                'type': f'{label}_docx_empty',
                'path': status.get('path'),
            })
    if summary.get('body_region_removed_count', 0):
        warnings.append({
            'type': 'body_region_removed_during_filtered_docx_experiment',
            'count': summary.get('body_region_removed_count'),
        })
    if summary.get('rejected_unsure_layout_placeholder_removed_count', 0):
        warnings.append({
            'type': 'blocked_or_placeholder_removed_during_filtered_docx_experiment',
            'count': summary.get('rejected_unsure_layout_placeholder_removed_count'),
        })
    if summary.get('body_text_block_delta', 0):
        warnings.append({
            'type': 'body_text_block_count_changed',
            'delta': summary.get('body_text_block_delta'),
        })
    if summary.get('baseline_image_count') != summary.get('filtered_image_count'):
        warnings.append({
            'type': 'image_count_changed_unexpectedly',
            'baseline': summary.get('baseline_image_count'),
            'filtered': summary.get('filtered_image_count'),
        })
    if summary.get('baseline_section_count') != summary.get('filtered_section_count'):
        warnings.append({
            'type': 'section_count_changed_unexpectedly',
            'baseline': summary.get('baseline_section_count'),
            'filtered': summary.get('filtered_section_count'),
        })
    if (
            summary.get('baseline_table_count') != summary.get('filtered_table_count') and
            gate_summary.get('gate_status') != 'passed'):
        warnings.append({
            'type': 'table_count_changed_without_visual_approval',
            'baseline': summary.get('baseline_table_count'),
            'filtered': summary.get('filtered_table_count'),
        })
    if not normal_conversion_check.get('passed', False):
        warnings.append({
            'type': 'normal_conversion_check_failed',
            'message': normal_conversion_check.get('message', ''),
        })
    if not normal_conversion_check.get('state_restored_or_reloaded', False):
        warnings.append({
            'type': 'state_restore_or_reload_not_confirmed',
        })
    return warnings


def _filtered_docx_safe_for_phase_2w(summary: dict, warnings: list) -> bool:
    blocking_types = {
        'table_visual_approval_gate_not_passed',
        'baseline_docx_path_not_local_only',
        'filtered_docx_path_not_local_only',
        'baseline_docx_missing',
        'filtered_docx_missing',
        'baseline_docx_empty',
        'filtered_docx_empty',
        'body_region_removed_during_filtered_docx_experiment',
        'blocked_or_placeholder_removed_during_filtered_docx_experiment',
        'body_text_block_count_changed',
        'image_count_changed_unexpectedly',
        'section_count_changed_unexpectedly',
        'table_count_changed_without_visual_approval',
        'normal_conversion_check_failed',
        'state_restore_or_reload_not_confirmed',
    }
    warning_types = {warning.get('type') for warning in warnings or []}
    return (
        summary.get('table_visual_approval_gate_status') == 'passed' and
        summary.get('normal_conversion_still_works') and
        summary.get('state_restored_or_reloaded') and
        not warning_types.intersection(blocking_types))


def _filtered_docx_recommendation(summary: dict, warnings: list) -> str:
    if _filtered_docx_safe_for_phase_2w(summary, warnings):
        if warnings:
            return 'Filtered DOCX generation completed with non-blocking warnings; Phase 2W can remain internal and guarded.'
        return 'Filtered DOCX generation comparison passed guarded checks; Phase 2W can remain internal and guarded.'
    return 'Keep production integration blocked; resolve filtered DOCX generation warnings first.'


def _normalize_removed_strings(removed_strings: list) -> list:
    seen = set()
    removed = []
    for item in removed_strings or []:
        text = normalize_text(item.get('text', '') if isinstance(item, dict) else item)
        if not text or text in seen:
            continue
        seen.add(text)
        removed.append(text)
    return removed


def _inspect_docx_openxml(path: str, removed_strings: list) -> dict:
    status = _docx_path_status(path)
    result = {
        'path': path or '',
        'exists': status['exists'],
        'size_bytes': status['size_bytes'],
        'empty': status['empty'],
        'readable': False,
        'body_paragraph_count': 0,
        'table_count': 0,
        'section_count': 0,
        'header_part_count': 0,
        'footer_part_count': 0,
        'body_paragraphs': [],
        'table_cells': [],
        'header_footer_parts': [],
        'residual_locations_by_text': {},
        'warnings': [],
    }
    if not status['exists']:
        result['warnings'].append({'type': 'docx_missing', 'path': path or ''})
        return result
    if status['empty']:
        result['warnings'].append({'type': 'docx_empty', 'path': path or ''})
        return result

    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if 'word/document.xml' not in names:
                result['warnings'].append({'type': 'document_xml_missing'})
                return result
            document_root = ET.fromstring(archive.read('word/document.xml'))
            document_summary = _docx_document_xml_summary(document_root)
            result.update(document_summary)
            result['header_footer_parts'] = _docx_header_footer_part_summaries(archive)
            result['header_part_count'] = sum(
                1 for part in result['header_footer_parts']
                if part.get('location_type') == 'header_part')
            result['footer_part_count'] = sum(
                1 for part in result['header_footer_parts']
                if part.get('location_type') == 'footer_part')
            result['residual_locations_by_text'] = _docx_residual_locations(result, removed_strings)
            result['readable'] = True
    except Exception as exc:
        result['warnings'].append({
            'type': 'docx_read_failed',
            'message': f'{exc.__class__.__name__}: {exc}',
        })
    return result


def _docx_path_status(path: str) -> dict:
    exists = bool(path and os.path.exists(path))
    size = os.path.getsize(path) if exists else 0
    return {
        'exists': exists,
        'size_bytes': size,
        'empty': size <= 0,
    }


def _docx_document_xml_summary(root) -> dict:
    body = root.find(f'.//{_WORD_XML_NS}body')
    direct_paragraphs = []
    table_cells = []
    table_count = 0
    section_count = 0
    if body is not None:
        direct_paragraphs = [
            _docx_location_record('body_paragraph', 'word/document.xml', index, _docx_element_text(child))
            for index, child in enumerate(list(body))
            if child.tag == f'{_WORD_XML_NS}p'
        ]
        tables = body.findall(f'.//{_WORD_XML_NS}tbl')
        table_count = len(tables)
        table_cells = [
            _docx_location_record('table_cell', 'word/document.xml', index, _docx_element_text(cell))
            for index, cell in enumerate(body.findall(f'.//{_WORD_XML_NS}tc'))
        ]
        section_count = len(body.findall(f'.//{_WORD_XML_NS}sectPr')) or 1

    return {
        'body_paragraph_count': len(direct_paragraphs),
        'table_count': table_count,
        'section_count': section_count,
        'body_paragraphs': direct_paragraphs,
        'table_cells': table_cells,
    }


def _docx_header_footer_part_summaries(archive) -> list:
    parts = []
    for name in sorted(archive.namelist()):
        if not (
                name.startswith('word/header') and name.endswith('.xml') or
                name.startswith('word/footer') and name.endswith('.xml')):
            continue
        try:
            root = ET.fromstring(archive.read(name))
            text = _docx_element_text(root)
        except Exception:
            text = ''
        location_type = 'header_part' if name.startswith('word/header') else 'footer_part'
        parts.append(_docx_location_record(location_type, name, len(parts), text))
    return parts


def _docx_location_record(location_type: str, part: str, index: int, text: str) -> dict:
    text = normalize_text(text)
    return {
        'location_type': location_type,
        'part': part,
        'index': index,
        'text_preview': _short_text_preview(text),
        'text': text,
    }


def _docx_element_text(element) -> str:
    return normalize_text(''.join(
        node.text or ''
        for node in element.iter(f'{_WORD_XML_NS}t')
    ))


def _short_text_preview(text: str, max_length: int = 80) -> str:
    text = normalize_text(text)
    if len(text) <= max_length:
        return text
    return text[:max_length-3].rstrip() + '...'


def _docx_residual_locations(docx_summary: dict, removed_strings: list) -> dict:
    locations_by_text = {}
    searchable = (
        docx_summary.get('body_paragraphs', []) +
        docx_summary.get('table_cells', []) +
        docx_summary.get('header_footer_parts', []))
    for removed in removed_strings or []:
        locations = []
        for location in searchable:
            if removed and removed in location.get('text', ''):
                public_location = dict(location)
                public_location.pop('text', None)
                locations.append(public_location)
        if locations:
            locations_by_text[removed] = locations
    return locations_by_text


def _filtered_docx_residual_disabled_summary(
        baseline: dict,
        filtered: dict,
        removed_strings: list) -> dict:
    return {
        'removed_string_count': len(removed_strings or []),
        'baseline_body_paragraph_count': baseline.get('body_paragraph_count', 0),
        'filtered_body_paragraph_count': filtered.get('body_paragraph_count', 0),
        'baseline_table_count': baseline.get('table_count', 0),
        'filtered_table_count': filtered.get('table_count', 0),
        'residual_removed_string_count': 0,
        'true_residual_header_footer_pollution_count': 0,
        'legitimate_body_table_duplicate_count': 0,
        'body_text_loss_warning_count': 0,
        'table_text_loss_warning_count': 0,
        'classification': 'disabled',
    }


def _filtered_docx_residual_items(baseline: dict, filtered: dict, removed_strings: list) -> list:
    residuals = []
    baseline_locations = baseline.get('residual_locations_by_text', {}) or {}
    filtered_locations = filtered.get('residual_locations_by_text', {}) or {}
    for removed in removed_strings or []:
        locations = filtered_locations.get(removed, [])
        if not locations:
            continue
        baseline_item_locations = baseline_locations.get(removed, [])
        classification = _classify_filtered_docx_residual(locations, baseline_item_locations)
        residuals.append({
            'text_preview': _short_text_preview(removed),
            'text_length': len(removed),
            'baseline_location_count': len(baseline_item_locations),
            'filtered_location_count': len(locations),
            'locations': locations,
            'location_counts': dict(sorted(Counter(
                item.get('location_type', '') for item in locations).items())),
            'classification': classification,
            'reason': _filtered_docx_residual_reason(classification),
        })
    return residuals


def _classify_filtered_docx_residual(locations: list, baseline_locations: list) -> str:
    location_types = Counter(item.get('location_type', '') for item in locations or [])
    if location_types.get('header_part') or location_types.get('footer_part'):
        return 'docx_header_footer_part_content'
    if location_types.get('body_paragraph', 0) > 1:
        return 'true_residual_header_footer_pollution'
    if location_types.get('table_cell') and not location_types.get('body_paragraph'):
        return 'legitimate_body_or_table_content'
    if location_types.get('body_paragraph'):
        baseline_body_count = sum(
            1 for item in baseline_locations or []
            if item.get('location_type') == 'body_paragraph')
        if baseline_body_count > location_types.get('body_paragraph', 0):
            return 'legitimate_body_duplicate'
        return 'needs_human_review'
    return 'insufficient_evidence'


def _filtered_docx_residual_reason(classification: str) -> str:
    if classification == 'docx_header_footer_part_content':
        return 'Residual appears in DOCX header/footer XML parts rather than body content.'
    if classification == 'true_residual_header_footer_pollution':
        return 'Residual appears repeatedly in filtered DOCX body paragraphs.'
    if classification == 'legitimate_body_or_table_content':
        return 'Residual appears only in table/cell content that remains in the filtered DOCX.'
    if classification == 'legitimate_body_duplicate':
        return 'Residual still appears once in body while baseline had more body occurrences.'
    if classification == 'needs_human_review':
        return 'Residual appears in body content, but location evidence is not enough to mark it safe.'
    return 'Residual location evidence is insufficient.'


def _filtered_docx_residual_summary(
        baseline: dict,
        filtered: dict,
        removed_strings: list,
        residuals: list) -> dict:
    classification_counts = Counter(item.get('classification', '') for item in residuals or [])
    location_counts = Counter()
    for item in residuals or []:
        location_counts.update(item.get('location_counts') or {})
    body_loss_warning = int(
        baseline.get('body_paragraph_count', 0) > 0 and
        filtered.get('body_paragraph_count', 0) == 0)
    table_loss_warning = int(
        baseline.get('table_count', 0) > 0 and
        filtered.get('table_count', 0) == 0)
    legitimate_body_table = (
        classification_counts.get('legitimate_body_duplicate', 0) +
        classification_counts.get('legitimate_body_or_table_content', 0))
    return {
        'removed_string_count': len(removed_strings or []),
        'baseline_body_paragraph_count': baseline.get('body_paragraph_count', 0),
        'filtered_body_paragraph_count': filtered.get('body_paragraph_count', 0),
        'paragraph_delta': filtered.get('body_paragraph_count', 0) - baseline.get('body_paragraph_count', 0),
        'baseline_table_count': baseline.get('table_count', 0),
        'filtered_table_count': filtered.get('table_count', 0),
        'table_delta': filtered.get('table_count', 0) - baseline.get('table_count', 0),
        'baseline_section_count': baseline.get('section_count', 0),
        'filtered_section_count': filtered.get('section_count', 0),
        'header_part_count': filtered.get('header_part_count', 0),
        'footer_part_count': filtered.get('footer_part_count', 0),
        'residual_removed_string_count': len(residuals or []),
        'residual_locations_by_part': dict(sorted(location_counts.items())),
        'true_residual_header_footer_pollution_count': classification_counts.get(
            'true_residual_header_footer_pollution', 0),
        'legitimate_body_table_duplicate_count': legitimate_body_table,
        'legitimate_body_duplicate_count': classification_counts.get('legitimate_body_duplicate', 0),
        'legitimate_body_or_table_content_count': classification_counts.get(
            'legitimate_body_or_table_content', 0),
        'docx_header_footer_part_content_count': classification_counts.get(
            'docx_header_footer_part_content', 0),
        'needs_human_review_count': classification_counts.get('needs_human_review', 0),
        'insufficient_evidence_count': classification_counts.get('insufficient_evidence', 0),
        'body_text_loss_warning_count': body_loss_warning,
        'table_text_loss_warning_count': table_loss_warning,
        'expected_header_footer_removal_confirmed': not classification_counts.get(
            'true_residual_header_footer_pollution', 0),
        'suspicious_residual_count': (
            classification_counts.get('true_residual_header_footer_pollution', 0) +
            classification_counts.get('needs_human_review', 0) +
            classification_counts.get('insufficient_evidence', 0)),
        'classification_counts': dict(sorted(classification_counts.items())),
        'classification': 'unsafe' if classification_counts.get(
            'true_residual_header_footer_pollution', 0) else (
                'review' if (
                    classification_counts.get('needs_human_review', 0) or
                    classification_counts.get('insufficient_evidence', 0)) else 'safe'),
    }


def _filtered_docx_residual_warnings(
        baseline: dict,
        filtered: dict,
        summary: dict,
        residuals: list) -> list:
    warnings = []
    for label, docx in (('baseline', baseline), ('filtered', filtered)):
        for warning in docx.get('warnings', []) or []:
            item = dict(warning)
            item['scope'] = label
            warnings.append(item)
    if summary.get('true_residual_header_footer_pollution_count', 0):
        warnings.append({
            'type': 'true_residual_header_footer_pollution',
            'count': summary.get('true_residual_header_footer_pollution_count'),
        })
    if summary.get('needs_human_review_count', 0):
        warnings.append({
            'type': 'residual_needs_human_review',
            'count': summary.get('needs_human_review_count'),
        })
    if summary.get('insufficient_evidence_count', 0):
        warnings.append({
            'type': 'residual_insufficient_evidence',
            'count': summary.get('insufficient_evidence_count'),
        })
    if summary.get('body_text_loss_warning_count', 0):
        warnings.append({
            'type': 'body_text_loss_warning',
            'count': summary.get('body_text_loss_warning_count'),
        })
    if summary.get('table_text_loss_warning_count', 0):
        warnings.append({
            'type': 'table_text_loss_warning',
            'count': summary.get('table_text_loss_warning_count'),
        })
    return warnings


def _filtered_docx_residual_safe_for_phase_2x(summary: dict, warnings: list) -> bool:
    blocking_types = {
        'docx_missing',
        'docx_empty',
        'docx_read_failed',
        'document_xml_missing',
        'true_residual_header_footer_pollution',
        'residual_needs_human_review',
        'residual_insufficient_evidence',
        'body_text_loss_warning',
        'table_text_loss_warning',
    }
    warning_types = {warning.get('type') for warning in warnings or []}
    return not warning_types.intersection(blocking_types)


def _filtered_docx_residual_recommendation(summary: dict, warnings: list) -> str:
    if _filtered_docx_residual_safe_for_phase_2x(summary, warnings):
        return 'DOCX residual structure inspection found no blocking residual pollution; Phase 2X can remain internal and guarded.'
    return 'Keep production integration blocked until DOCX residual structure warnings are resolved.'


def _reviewed_filtering_readiness_evidence(
        header_footer_review_report: dict,
        raw_object_mapping_report: dict,
        filtered_parse_experiment_report: dict,
        table_visual_approval_gate_report: dict,
        body_table_geometry_delta_safety_report: dict,
        filtered_docx_comparison_report: dict,
        docx_residual_structure_report: dict,
        verification_status: dict,
        evidence_overrides: dict) -> dict:
    header_report = header_footer_review_report or {}
    header_summary = header_report.get('summary') or {}
    mapping_summary = (raw_object_mapping_report or {}).get('summary') or {}
    parse_report = filtered_parse_experiment_report or {}
    parse_summary = parse_report.get('summary') or {}
    gate_summary = (table_visual_approval_gate_report or {}).get('summary') or {}
    table_geometry_summary = (
        body_table_geometry_delta_safety_report or {}).get('summary') or {}
    docx_report = filtered_docx_comparison_report or {}
    docx_summary = docx_report.get('summary') or {}
    docx_files = docx_report.get('docx_files') or {}
    residual_report = docx_residual_structure_report or {}
    residual_summary = residual_report.get('summary') or {}
    verification = dict(verification_status or {})

    expected_removed_count = _first_present(
        mapping_summary.get('expected_would_remove_count'),
        parse_summary.get('removed_raw_block_count'),
        docx_summary.get('removed_approved_header_footer_page_number_count'),
        header_summary.get('would_remove_block_count'))
    actual_removed_count = _first_present(
        parse_summary.get('removed_raw_block_count'),
        docx_summary.get('removed_approved_header_footer_page_number_count'),
        header_summary.get('removed_block_count'),
        mapping_summary.get('mapped_raw_object_count'))

    baseline_body_blocks = _first_present(
        parse_summary.get('baseline_body_text_block_count'),
        docx_summary.get('baseline_body_text_block_count'))
    filtered_body_blocks = _first_present(
        parse_summary.get('filtered_body_text_block_count'),
        docx_summary.get('filtered_body_text_block_count'))
    baseline_images = _first_present(
        parse_summary.get('baseline_image_count'),
        docx_summary.get('baseline_image_count'))
    filtered_images = _first_present(
        parse_summary.get('filtered_image_count'),
        docx_summary.get('filtered_image_count'))
    baseline_sections = _first_present(
        parse_summary.get('baseline_section_count'),
        docx_summary.get('baseline_section_count'))
    filtered_sections = _first_present(
        parse_summary.get('filtered_section_count'),
        docx_summary.get('filtered_section_count'))

    evidence = {
        'header_footer_review_approval_passed': _readiness_bool(_first_present(
            header_report.get('approved_candidate_count', None),
            header_summary.get('approved_candidate_count', None),
            mapping_summary.get('approved_candidate_count', None))) or False,
        'approved_candidate_count': _readiness_int(_first_present(
            header_report.get('approved_candidate_count', None),
            header_summary.get('approved_candidate_count', None),
            mapping_summary.get('approved_candidate_count', 0))),
        'blocked_candidate_count': _readiness_int(_first_present(
            header_report.get('blocked_candidate_count', None),
            header_summary.get('blocked_candidate_count', None),
            mapping_summary.get('blocked_candidate_count', 0))),
        'table_visual_approval_gate_passed': (
            (table_visual_approval_gate_report or {}).get('gate_status') == 'passed' or
            gate_summary.get('gate_status') == 'passed'),
        'table_visual_approval_gate_status': (
            (table_visual_approval_gate_report or {}).get('gate_status') or
            gate_summary.get('gate_status') or ''),
        'table_visual_expected_review_item_count': _readiness_int(
            gate_summary.get('expected_review_item_count', 0)),
        'table_visual_parsed_review_item_count': _readiness_int(
            gate_summary.get('parsed_review_item_count', 0)),
        'table_visual_approve_count': _readiness_int(gate_summary.get('approve_count', 0)),
        'table_visual_reject_count': _readiness_int(gate_summary.get('reject_count', 0)),
        'table_visual_unsure_count': _readiness_int(gate_summary.get('unsure_count', 0)),
        'table_visual_missing_decision_count': _readiness_int(
            gate_summary.get('missing_decision_count', 0)),
        'expected_removed_count': _readiness_int(expected_removed_count),
        'actual_removed_count': _readiness_int(actual_removed_count),
        'expected_removal_count_matches_actual': (
            expected_removed_count is not None and
            actual_removed_count is not None and
            _readiness_int(expected_removed_count) == _readiness_int(actual_removed_count) and
            _readiness_int(actual_removed_count) > 0),
        'body_region_removed_count': _readiness_int(_first_present(
            parse_summary.get('body_region_removed_count'),
            docx_summary.get('body_region_removed_count'),
            mapping_summary.get('body_region_matched_for_removal_count'),
            0)),
        'rejected_unsure_layout_placeholder_removed_count': _readiness_int(_first_present(
            parse_summary.get('rejected_unsure_layout_placeholder_removed_count'),
            docx_summary.get('rejected_unsure_layout_placeholder_removed_count'),
            mapping_summary.get(
                'rejected_unsure_layout_placeholder_matched_for_removal_count'),
            0)),
        'raw_mapping_exact_match_count': _readiness_int(
            mapping_summary.get('exact_match_count', 0)),
        'raw_mapping_fuzzy_match_count': _readiness_int(
            mapping_summary.get('fuzzy_match_count', 0)),
        'raw_mapping_ambiguous_match_count': _readiness_int(
            mapping_summary.get('ambiguous_match_count', 0)),
        'raw_mapping_missing_match_count': _readiness_int(
            mapping_summary.get('missing_match_count', 0)),
        'raw_mapping_unsafe_match_count': _readiness_int(
            mapping_summary.get('unsafe_match_count', 0)),
        'raw_mapping_all_expected_blocks_mapped_once': bool(
            mapping_summary.get('all_expected_blocks_mapped_once', False)),
        'baseline_body_text_block_count': _readiness_int(baseline_body_blocks),
        'filtered_body_text_block_count': _readiness_int(filtered_body_blocks),
        'body_textblock_count_preserved': (
            baseline_body_blocks is not None and
            filtered_body_blocks is not None and
            _readiness_int(baseline_body_blocks) == _readiness_int(filtered_body_blocks)),
        'baseline_image_count': _readiness_int(baseline_images),
        'filtered_image_count': _readiness_int(filtered_images),
        'image_count_preserved': (
            baseline_images is not None and
            filtered_images is not None and
            _readiness_int(baseline_images) == _readiness_int(filtered_images)),
        'baseline_section_count': _readiness_int(baseline_sections),
        'filtered_section_count': _readiness_int(filtered_sections),
        'section_count_preserved': (
            baseline_sections is not None and
            filtered_sections is not None and
            _readiness_int(baseline_sections) == _readiness_int(filtered_sections)),
        'known_table_delta_approved': _known_table_delta_approved(
            docx_summary,
            parse_summary,
            gate_summary,
            table_geometry_summary),
        'unexpected_parse_warning_count': _unexpected_parse_warning_count(
            parse_report.get('safety_warnings', []) or [],
            _known_table_delta_approved(
                docx_summary,
                parse_summary,
                gate_summary,
                table_geometry_summary)),
        'baseline_docx_exists_non_empty': _docx_file_ready(
            (docx_files.get('baseline') or {})),
        'filtered_docx_exists_non_empty': _docx_file_ready(
            (docx_files.get('filtered') or {})),
        'normal_conversion_after_experiment_passed': bool(
            docx_summary.get('normal_conversion_still_works', False)),
        'docx_state_restored_or_reloaded': bool(
            docx_summary.get('state_restored_or_reloaded', False)),
        'true_residual_header_footer_pollution_count': _readiness_int(
            residual_summary.get('true_residual_header_footer_pollution_count', 0)),
        'body_text_loss_warning_count': _readiness_int(
            residual_summary.get('body_text_loss_warning_count', 0)),
        'table_text_loss_warning_count': _readiness_int(
            residual_summary.get('table_text_loss_warning_count', 0)),
        'docx_residual_classification': residual_summary.get('classification', ''),
        'docx_residual_safe': _docx_residual_safe_for_readiness(
            residual_summary,
            residual_report.get('safety_warnings', []) or []),
        'layout_analyzer_tests_passed': bool(verification.get(
            'layout_analyzer_tests_passed', False)),
        'py_compile_passed': bool(verification.get('py_compile_passed', False)),
        'unittest_passed': bool(verification.get('unittest_passed', False)),
        'conversion_tests_passed': bool(verification.get(
            'conversion_tests_passed', False)),
        'git_diff_check_passed': bool(verification.get('git_diff_check_passed', False)),
        'local_artifacts_ignored': bool(verification.get('local_artifacts_ignored', False)),
        'local_sample_dependency': bool(verification.get(
            'local_sample_dependency',
            True)),
        'committed_synthetic_fixture_available': bool(verification.get(
            'committed_synthetic_fixture_available',
            False)),
        'committed_end_to_end_regression_fixture_available': bool(verification.get(
            'committed_end_to_end_regression_fixture_available',
            False)),
        'production_default_integration_enabled': bool(verification.get(
            'production_default_integration_enabled',
            False)),
        'public_cli_enabled': bool(verification.get('public_cli_enabled', False)),
    }
    evidence['test_status_all_passed'] = all(
        evidence.get(key) for key in (
            'layout_analyzer_tests_passed',
            'py_compile_passed',
            'unittest_passed',
            'conversion_tests_passed',
            'git_diff_check_passed',
            'local_artifacts_ignored',
        ))

    for key, value in (evidence_overrides or {}).items():
        evidence[key] = value
    evidence['test_status_all_passed'] = all(
        evidence.get(key) for key in (
            'layout_analyzer_tests_passed',
            'py_compile_passed',
            'unittest_passed',
            'conversion_tests_passed',
            'git_diff_check_passed',
            'local_artifacts_ignored',
        ))
    return evidence


def _reviewed_filtering_readiness_blocking_reasons(evidence: dict) -> list:
    reasons = []
    _add_readiness_reason(
        reasons,
        evidence.get('header_footer_review_approval_passed'),
        'header_footer_review_approval_missing',
        'Header/footer review approvals are missing or empty.')
    _add_readiness_reason(
        reasons,
        evidence.get('table_visual_approval_gate_passed'),
        'table_visual_approval_gate_not_passed',
        'Table visual approval gate has not passed.',
        status=evidence.get('table_visual_approval_gate_status'))
    _add_readiness_reason(
        reasons,
        evidence.get('expected_removal_count_matches_actual'),
        'reviewed_removal_count_mismatch',
        'Expected removal count does not match actual reviewed removal count.',
        expected=evidence.get('expected_removed_count'),
        observed=evidence.get('actual_removed_count'))
    for key, reason_type, message in (
            ('body_region_removed_count',
             'body_region_removed',
             'Reviewed filtering would remove body-region content.'),
            ('rejected_unsure_layout_placeholder_removed_count',
             'blocked_or_placeholder_removed',
             'Rejected, unsure, or layout-placeholder content would be removed.'),
            ('raw_mapping_ambiguous_match_count',
             'raw_mapping_ambiguous_matches',
             'Raw-object mapping has ambiguous matches.'),
            ('raw_mapping_missing_match_count',
             'raw_mapping_missing_matches',
             'Raw-object mapping has missing matches.'),
            ('raw_mapping_unsafe_match_count',
             'raw_mapping_unsafe_matches',
             'Raw-object mapping has unsafe matches.')):
        if _readiness_int(evidence.get(key, 0)):
            reasons.append({
                'type': reason_type,
                'message': message,
                'count': _readiness_int(evidence.get(key, 0)),
            })

    _add_readiness_reason(
        reasons,
        evidence.get('raw_mapping_all_expected_blocks_mapped_once'),
        'raw_mapping_not_one_to_one',
        'Not every reviewed removal maps to exactly one raw-page object.')
    _add_readiness_reason(
        reasons,
        evidence.get('body_textblock_count_preserved'),
        'body_textblock_count_changed',
        'Filtered parse changed body TextBlock count.',
        baseline=evidence.get('baseline_body_text_block_count'),
        filtered=evidence.get('filtered_body_text_block_count'))
    _add_readiness_reason(
        reasons,
        evidence.get('image_count_preserved'),
        'image_count_changed',
        'Filtered parse changed image count.',
        baseline=evidence.get('baseline_image_count'),
        filtered=evidence.get('filtered_image_count'))
    _add_readiness_reason(
        reasons,
        evidence.get('section_count_preserved'),
        'section_count_changed',
        'Filtered parse changed section count.',
        baseline=evidence.get('baseline_section_count'),
        filtered=evidence.get('filtered_section_count'))
    _add_readiness_reason(
        reasons,
        evidence.get('known_table_delta_approved'),
        'known_table_delta_not_approved',
        'Known table-count delta is not approved or structurally explained.')
    if _readiness_int(evidence.get('unexpected_parse_warning_count', 0)):
        reasons.append({
            'type': 'unexpected_parse_warnings_present',
            'count': _readiness_int(evidence.get('unexpected_parse_warning_count', 0)),
        })
    _add_readiness_reason(
        reasons,
        evidence.get('baseline_docx_exists_non_empty'),
        'baseline_docx_missing_or_empty',
        'Baseline DOCX is missing or empty.')
    _add_readiness_reason(
        reasons,
        evidence.get('filtered_docx_exists_non_empty'),
        'filtered_docx_missing_or_empty',
        'Filtered DOCX is missing or empty.')
    _add_readiness_reason(
        reasons,
        evidence.get('normal_conversion_after_experiment_passed'),
        'normal_conversion_after_experiment_failed',
        'Normal conversion check after the experiment did not pass.')
    _add_readiness_reason(
        reasons,
        evidence.get('docx_state_restored_or_reloaded'),
        'docx_experiment_state_not_restored',
        'Converter/page state was not confirmed restored or reloaded.')
    _add_readiness_reason(
        reasons,
        evidence.get('docx_residual_safe'),
        'docx_residual_not_safe',
        'DOCX residual structure report is not safe.',
        classification=evidence.get('docx_residual_classification'))
    for key, reason_type, message in (
            ('true_residual_header_footer_pollution_count',
             'true_residual_header_footer_pollution_present',
             'Filtered DOCX still contains true header/footer pollution.'),
            ('body_text_loss_warning_count',
             'body_text_loss_warnings_present',
             'Filtered DOCX has body text loss warnings.'),
            ('table_text_loss_warning_count',
             'table_text_loss_warnings_present',
             'Filtered DOCX has table text loss warnings.')):
        if _readiness_int(evidence.get(key, 0)):
            reasons.append({
                'type': reason_type,
                'message': message,
                'count': _readiness_int(evidence.get(key, 0)),
            })

    for key, reason_type in (
            ('layout_analyzer_tests_passed', 'layout_analyzer_tests_not_passed'),
            ('py_compile_passed', 'py_compile_not_passed'),
            ('unittest_passed', 'unittest_not_passed'),
            ('conversion_tests_passed', 'conversion_tests_not_passed'),
            ('git_diff_check_passed', 'git_diff_check_not_passed'),
            ('local_artifacts_ignored', 'local_artifacts_not_confirmed_ignored')):
        _add_readiness_reason(
            reasons,
            evidence.get(key),
            reason_type,
            f'{key} is not confirmed.')
    return reasons


def _reviewed_filtering_non_blocking_risks(evidence: dict) -> list:
    risks = []
    if evidence.get('local_sample_dependency', True):
        risks.append({
            'type': 'local_sample_dependency',
            'message': 'Readiness evidence still depends on ignored local sample artifacts.',
        })
    if not evidence.get('committed_synthetic_fixture_available', False):
        risks.append({
            'type': 'committed_synthetic_fixture_missing',
            'message': 'Synthetic fixtures are planned but not yet committed.',
        })
    if not evidence.get('committed_end_to_end_regression_fixture_available', False):
        risks.append({
            'type': 'committed_end_to_end_regression_fixture_missing',
            'message': 'No committed end-to-end regression fixture exists yet.',
        })
    if not evidence.get('production_default_integration_enabled', False):
        risks.append({
            'type': 'production_default_integration_still_disabled',
            'message': 'This is expected; default production integration remains blocked.',
        })
    if not evidence.get('public_cli_enabled', False):
        risks.append({
            'type': 'public_cli_still_disabled',
            'message': 'This is expected; no public CLI behavior is exposed yet.',
        })
    return risks


def _reviewed_filtering_fixture_coverage() -> list:
    return [
        {
            'fixture': 'repeated_header_footer_page_numbers',
            'purpose': 'Covers all-page repeated headers, footers, and page numbers.',
        },
        {
            'fixture': 'first_page_different_header',
            'purpose': 'Covers title-page/header exceptions.',
        },
        {
            'fixture': 'odd_even_headers',
            'purpose': 'Covers alternating section/page header text.',
        },
        {
            'fixture': 'footer_close_to_body_text',
            'purpose': 'Covers narrow body/footer separation risk.',
        },
        {
            'fixture': 'body_table_near_footer',
            'purpose': 'Covers body table preservation near bottom artifacts.',
        },
        {
            'fixture': 'callout_textbox_table_like_content',
            'purpose': 'Covers non-table layout boxes that can look table-like.',
        },
        {
            'fixture': 'paragraph_crossing_page_boundary',
            'purpose': 'Covers cross-page paragraph continuation evidence.',
        },
        {
            'fixture': 'hyphenated_cross_page_continuation',
            'purpose': 'Covers hyphenated line/page-break continuation.',
        },
        {
            'fixture': 'list_items_and_headings',
            'purpose': 'Covers list/heading boundaries that must not over-merge.',
        },
        {
            'fixture': 'no_header_no_footer_negative_control',
            'purpose': 'Covers documents where no exclusion should occur.',
        },
    ]


def _reviewed_filtering_readiness_recommendation(
        readiness_status: str,
        blocking_reasons: list,
        non_blocking_risks: list) -> str:
    if readiness_status == 'ready_for_internal_opt_in_integration_experiment':
        return (
            'Ready for the next internal opt-in integration experiment only; '
            'production default integration remains blocked until synthetic '
            'fixtures and committed regressions exist.')
    reason_types = ', '.join(reason.get('type', '') for reason in blocking_reasons or [])
    return f'Keep production integration blocked; resolve readiness blockers: {reason_types}.'


def _add_readiness_reason(
        reasons: list,
        condition,
        reason_type: str,
        message: str,
        **details):
    if condition:
        return
    reason = {
        'type': reason_type,
        'message': message,
    }
    reason.update({key: value for key, value in details.items() if value is not None})
    reasons.append(reason)


def _first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _readiness_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _readiness_bool(value) -> bool:
    if isinstance(value, str):
        return normalize_text(value).lower() in {'true', 'yes', 'passed'}
    return bool(value)


def _known_table_delta_approved(
        docx_summary: dict,
        parse_summary: dict,
        gate_summary: dict,
        table_geometry_summary: dict) -> bool:
    baseline_table_count = _first_present(
        parse_summary.get('baseline_table_count'),
        docx_summary.get('baseline_table_count'))
    filtered_table_count = _first_present(
        parse_summary.get('filtered_table_count'),
        docx_summary.get('filtered_table_count'))
    if (
            baseline_table_count is not None and
            filtered_table_count is not None and
            _readiness_int(baseline_table_count) == _readiness_int(filtered_table_count)):
        return True

    gate_passed = gate_summary.get('gate_status') == 'passed'
    row_col_cell_preserved = (
        _readiness_int(table_geometry_summary.get('changed_row_column_cell_count', 0)) == 0 and
        _readiness_int(table_geometry_summary.get(
            'possible_body_table_structure_change_count', 0)) == 0 and
        _readiness_int(table_geometry_summary.get('possible_cell_loss_count', 0)) == 0)
    text_preserved = (
        _readiness_int(table_geometry_summary.get('text_cell_signature_changed_count', 0)) == 0)
    if table_geometry_summary:
        return gate_passed and row_col_cell_preserved and text_preserved
    return gate_passed


def _unexpected_parse_warning_count(warnings: list, known_table_delta_approved: bool) -> int:
    unexpected = []
    for warning in warnings or []:
        warning_type = warning.get('type') if isinstance(warning, dict) else str(warning)
        if known_table_delta_approved and warning_type == 'table_count_changed':
            continue
        unexpected.append(warning)
    return len(unexpected)


def _docx_file_ready(status: dict) -> bool:
    return bool(status.get('exists')) and not bool(status.get('empty'))


def _docx_residual_safe_for_readiness(summary: dict, warnings: list) -> bool:
    return (
        summary.get('classification') == 'safe' and
        not _readiness_int(summary.get('true_residual_header_footer_pollution_count', 0)) and
        not _readiness_int(summary.get('body_text_loss_warning_count', 0)) and
        not _readiness_int(summary.get('table_text_loss_warning_count', 0)) and
        _filtered_docx_residual_safe_for_phase_2x(summary, warnings))


def _corpus_validation_empty_summary() -> dict:
    return {
        'sample_count': 0,
        'samples_analyzed_successfully': 0,
        'samples_failed_analysis': 0,
        'samples_skipped_or_partially_analyzed': 0,
        'samples_with_likely_valid_header_footer_candidates': 0,
        'samples_with_suspicious_candidates': 0,
        'samples_needing_manual_review': 0,
        'samples_too_large_for_full_pipeline': 0,
        'recommended_for_phase_2y1_manual_review': [],
    }


def _corpus_sample_summary(sample: dict, large_page_threshold: int) -> dict:
    sample = sample or {}
    layout_report = sample.get('layout_analysis_report') or {}
    page_count = _readiness_int(_first_present(
        sample.get('page_count'),
        layout_report.get('page_count'),
        0))
    pages_analyzed = _readiness_int(_first_present(
        sample.get('pages_analyzed'),
        layout_report.get('page_count'),
        0))
    parsing_succeeded = bool(sample.get('parsing_succeeded', False))
    analysis_succeeded = bool(sample.get('analysis_succeeded', False))
    is_large = page_count > int(large_page_threshold or 0)
    analysis_mode = sample.get('analysis_mode') or (
        'analysis_only_bounded_subset' if is_large else 'analysis_only')

    layout_summary = _corpus_layout_analysis_summary(layout_report)
    dry_run_summary = _corpus_dry_run_filtering_summary(layout_report)
    review_pack_summary = {
        'review_pack_generated': bool(sample.get('review_pack_generated', False)),
        'review_pack_path': sample.get('review_pack_path', ''),
        'auto_approved_decisions': False,
        'manual_decisions_consumed': False,
    }
    warnings = _corpus_sample_warnings(
        sample,
        parsing_succeeded,
        analysis_succeeded,
        is_large,
        pages_analyzed,
        page_count,
        layout_summary,
        dry_run_summary)

    recommendation = _corpus_sample_recommendation(
        parsing_succeeded,
        analysis_succeeded,
        is_large,
        dry_run_summary,
        warnings)
    return {
        'sample_name': sample.get('sample_name') or os.path.basename(sample.get('file_path', '')),
        'file_path': sample.get('file_path', ''),
        'basic_file_summary': {
            'file_name': sample.get('file_name') or os.path.basename(sample.get('file_path', '')),
            'file_size_bytes': _readiness_int(sample.get('file_size_bytes', 0)),
            'page_count': page_count,
            'pages_analyzed': pages_analyzed,
            'parsing_succeeded': parsing_succeeded,
            'analysis_succeeded': analysis_succeeded,
            'runtime_seconds': round(float(sample.get('runtime_seconds') or 0.0), 3),
            'analysis_mode': analysis_mode,
            'large_sample': is_large,
            'partial_or_bounded': bool(sample.get('partial_or_bounded', False)) or pages_analyzed < page_count,
        },
        'layout_analysis_summary': layout_summary,
        'dry_run_filtering_summary': dry_run_summary,
        'review_pack_summary': review_pack_summary,
        'warnings': warnings,
        'recommendation': recommendation,
    }


def _corpus_layout_analysis_summary(layout_report: dict) -> dict:
    layout_report = layout_report or {}
    pages = layout_report.get('pages', []) or []
    repeated = layout_report.get('repeated_text_candidates', []) or []
    region_counts = Counter()
    for page in pages:
        region_counts.update(page.get('region_counts') or {})
    confidence_counts = Counter(
        candidate.get('confidence_label', '') or 'unlabeled'
        for candidate in repeated)
    return {
        'total_block_count': sum(page.get('text_block_count', 0) for page in pages),
        'top_block_count': region_counts.get(REGION_TOP, 0),
        'body_block_count': region_counts.get(REGION_BODY, 0),
        'bottom_block_count': region_counts.get(REGION_BOTTOM, 0),
        'repeated_candidate_count': len(repeated),
        'strong_candidate_count': confidence_counts.get('strong', 0),
        'cautious_candidate_count': confidence_counts.get('cautious', 0),
        'placeholder_candidate_count': confidence_counts.get('placeholder', 0),
        'confidence_label_counts': dict(sorted(confidence_counts.items())),
    }


def _corpus_dry_run_filtering_summary(layout_report: dict) -> dict:
    dry_run = (layout_report or {}).get('header_footer_exclusion_dry_run') or {}
    summary = dry_run.get('summary') or {}
    candidates = dry_run.get('candidates', []) or []
    action_counts = Counter(summary.get('action_counts') or {})
    role_counts = Counter(summary.get('role_counts') or {})
    would_exclude = [
        candidate for candidate in candidates
        if candidate.get('action') == ACTION_WOULD_EXCLUDE
    ]
    suspicious_body = [
        candidate for candidate in candidates
        if (
            candidate.get('region') == REGION_BODY or
            REGION_BODY in (candidate.get('regions') or []) or
            'body_region_repetition' in (candidate.get('negative_signals') or []))
    ]
    support_counts = [
        {
            'candidate_id': candidate.get('candidate_id', ''),
            'proposed_role': candidate.get('proposed_role', ''),
            'action': candidate.get('action', ''),
            'support_count': _readiness_int(candidate.get('support_count', 0)),
            'page_count': _readiness_int(candidate.get('page_count', 0)),
        }
        for candidate in candidates
    ]
    return {
        'candidate_count': len(candidates),
        'would_exclude_candidate_count': action_counts.get(
            ACTION_WOULD_EXCLUDE,
            len(would_exclude)),
        'review_candidate_count': action_counts.get(ACTION_REVIEW, 0),
        'keep_candidate_count': action_counts.get(ACTION_KEEP, 0),
        'would_remove_block_count': sum(
            _readiness_int(candidate.get('support_count', 0))
            for candidate in would_exclude),
        'candidate_support_counts': support_counts,
        'role_counts': dict(sorted(role_counts.items())),
        'header_candidate_count': role_counts.get(ROLE_HEADER, 0),
        'footer_candidate_count': role_counts.get(ROLE_FOOTER, 0),
        'page_number_candidate_count': role_counts.get(ROLE_PAGE_NUMBER, 0),
        'layout_placeholder_candidate_count': role_counts.get(ROLE_LAYOUT_PLACEHOLDER, 0),
        'review_only_candidate_count': role_counts.get(ROLE_REVIEW_ONLY, 0),
        'body_region_removed_count': 0,
        'suspicious_body_region_candidate_count': len(suspicious_body),
        'warnings': _corpus_dry_run_warnings(candidates, suspicious_body),
    }


def _corpus_dry_run_warnings(candidates: list, suspicious_body: list) -> list:
    warnings = []
    if not candidates:
        warnings.append({
            'type': 'no_repeated_candidates',
            'message': 'No repeated header/footer candidates were detected.',
        })
    if suspicious_body:
        warnings.append({
            'type': 'suspicious_body_region_candidates',
            'count': len(suspicious_body),
        })
    return warnings


def _corpus_sample_warnings(
        sample: dict,
        parsing_succeeded: bool,
        analysis_succeeded: bool,
        is_large: bool,
        pages_analyzed: int,
        page_count: int,
        layout_summary: dict,
        dry_run_summary: dict) -> list:
    warnings = []
    if not parsing_succeeded:
        warnings.append({
            'type': 'parsing_failed',
            'message': sample.get('error', ''),
        })
    if parsing_succeeded and not analysis_succeeded:
        warnings.append({
            'type': 'analysis_failed',
            'message': sample.get('error', ''),
        })
    if is_large and not sample.get('full_pipeline_allowed', False):
        warnings.append({
            'type': 'large_sample_analysis_only',
            'page_count': page_count,
        })
    if pages_analyzed and page_count and pages_analyzed < page_count:
        warnings.append({
            'type': 'partial_or_bounded_analysis',
            'pages_analyzed': pages_analyzed,
            'page_count': page_count,
        })
    if analysis_succeeded and not layout_summary.get('repeated_candidate_count', 0):
        warnings.append({
            'type': 'no_repeated_candidates',
        })
    if dry_run_summary.get('suspicious_body_region_candidate_count', 0):
        warnings.append({
            'type': 'suspicious_body_region_candidates',
            'count': dry_run_summary.get('suspicious_body_region_candidate_count'),
        })
    return warnings


def _corpus_sample_recommendation(
        parsing_succeeded: bool,
        analysis_succeeded: bool,
        is_large: bool,
        dry_run_summary: dict,
        warnings: list) -> dict:
    warning_types = {warning.get('type') for warning in warnings or []}
    if not parsing_succeeded or not analysis_succeeded:
        return {
            'label': 'analysis_failed',
            'reason': 'Parsing or layout analysis failed; inspect the sample before deeper review.',
        }
    if dry_run_summary.get('would_exclude_candidate_count', 0):
        label = 'manual_review_recommended'
        if is_large:
            label = 'manual_review_recommended_bounded_large_sample'
        return {
            'label': label,
            'reason': 'Dry-run candidates exist, but no exclusion is approved without manual review.',
        }
    if 'suspicious_body_region_candidates' in warning_types:
        return {
            'label': 'needs_manual_review',
            'reason': 'Body-region repeated candidates need review before any filtering experiment.',
        }
    return {
        'label': 'analysis_only_no_deeper_review_yet',
        'reason': 'No would-exclude candidates were found in this analysis pass.',
    }


def _corpus_validation_summary(samples: list) -> dict:
    recommendations = {
        sample.get('sample_name')
        for sample in samples or []
        if (sample.get('recommendation') or {}).get('label') in {
            'manual_review_recommended',
            'manual_review_recommended_bounded_large_sample',
            'needs_manual_review',
        }
    }
    return {
        'sample_count': len(samples or []),
        'samples_analyzed_successfully': sum(
            1 for sample in samples or []
            if sample.get('basic_file_summary', {}).get('analysis_succeeded')),
        'samples_failed_analysis': sum(
            1 for sample in samples or []
            if not sample.get('basic_file_summary', {}).get('analysis_succeeded')),
        'samples_skipped_or_partially_analyzed': sum(
            1 for sample in samples or []
            if sample.get('basic_file_summary', {}).get('partial_or_bounded')),
        'samples_with_likely_valid_header_footer_candidates': sum(
            1 for sample in samples or []
            if sample.get('dry_run_filtering_summary', {}).get(
                'would_exclude_candidate_count', 0)),
        'samples_with_suspicious_candidates': sum(
            1 for sample in samples or []
            if sample.get('dry_run_filtering_summary', {}).get(
                'suspicious_body_region_candidate_count', 0)),
        'samples_needing_manual_review': len(recommendations),
        'samples_too_large_for_full_pipeline': sum(
            1 for sample in samples or []
            if sample.get('basic_file_summary', {}).get('large_sample')),
        'recommended_for_phase_2y1_manual_review': sorted(recommendations),
    }


def _corpus_validation_warnings(samples: list) -> list:
    warnings = []
    for sample in samples or []:
        for warning in sample.get('warnings', []) or []:
            item = dict(warning)
            item['sample_name'] = sample.get('sample_name')
            warnings.append(item)
    return warnings


def _corpus_validation_recommendation(summary: dict, warnings: list) -> str:
    if not summary.get('samples_analyzed_successfully', 0):
        return 'No sample was analyzed successfully; do not proceed to deeper review.'
    if summary.get('samples_failed_analysis', 0):
        return 'Some samples failed analysis; inspect failures before selecting Phase 2Y1 manual review targets.'
    if summary.get('recommended_for_phase_2y1_manual_review'):
        return 'Proceed only to local Phase 2Y1 manual review for the recommended samples; do not enable production integration.'
    return 'Corpus analysis completed, but no sample has clear reviewed-filtering candidates yet.'


def _corpus_manual_review_disabled_summary(sample: dict) -> dict:
    return {
        'sample_name': sample.get('sample_name', '') if sample else '',
        'candidate_count': 0,
        'would_exclude_candidate_count': 0,
        'would_remove_block_count': 0,
        'review_only_candidate_count': 0,
        'cautious_candidate_count': 0,
        'placeholder_candidate_count': 0,
        'ready_for_human_approval': False,
        'recommended_next_action': 'disabled',
        'auto_approved_decision_count': 0,
    }


def _corpus_manual_review_items(layout_report: dict) -> list:
    dry_run = (layout_report or {}).get('header_footer_exclusion_dry_run') or {}
    repeated_by_fingerprint = {
        item.get('fingerprint', ''): item
        for item in (layout_report or {}).get('repeated_text_candidates', []) or []
    }
    return [
        _corpus_manual_review_item(candidate, repeated_by_fingerprint)
        for candidate in dry_run.get('candidates', []) or []
    ]


def _corpus_manual_review_item(candidate: dict, repeated_by_fingerprint: dict) -> dict:
    repeated = repeated_by_fingerprint.get(candidate.get('fingerprint', ''), {})
    action = candidate.get('action', '')
    proposed_role = candidate.get('proposed_role', '')
    support_count = _readiness_int(candidate.get('support_count', 0))
    confidence_label = candidate.get('confidence_label') or repeated.get('confidence_label', '')
    text = repeated.get('text') or _first_instance_text(repeated) or ''
    return {
        'candidate_id': candidate.get('candidate_id', ''),
        'fingerprint': candidate.get('fingerprint', ''),
        'proposed_role': proposed_role,
        'action': action,
        'region': candidate.get('region', ''),
        'regions': list(candidate.get('regions', []) or []),
        'affected_pages': list(candidate.get('affected_pages', []) or []),
        'affected_page_numbers': [
            _human_page_number(page_index)
            for page_index in candidate.get('affected_pages', []) or []
        ],
        'support_count': support_count,
        'page_count': _readiness_int(candidate.get('page_count', 0)),
        'confidence_label': confidence_label,
        'semantic_confidence': round(float(candidate.get(
            'semantic_confidence',
            repeated.get('semantic_confidence', 0.0)) or 0.0), 3),
        'would_remove_count': support_count if action == ACTION_WOULD_EXCLUDE else 0,
        'short_preview': _short_text_preview(text),
        'positive_signals': list(candidate.get('positive_signals', []) or []),
        'negative_signals': list(candidate.get('negative_signals', []) or []),
        'reason': candidate.get('reason', ''),
        'suggested_review_recommendation': _corpus_manual_review_recommendation(
            candidate,
            confidence_label),
        'manual_decision_fields': {
            'approve_exclude': False,
            'reject_exclude': False,
            'unsure': False,
            'reviewer_notes': '',
        },
        'auto_approved': False,
    }


def _first_instance_text(repeated: dict) -> str:
    instances = repeated.get('instances', []) or []
    if not instances:
        return ''
    return normalize_text(instances[0].get('text', ''))


def _corpus_manual_review_recommendation(candidate: dict, confidence_label: str) -> str:
    if candidate.get('action') == ACTION_WOULD_EXCLUDE:
        return 'manual_review_required'
    if candidate.get('proposed_role') == ROLE_LAYOUT_PLACEHOLDER:
        return 'layout_placeholder_review_only'
    if confidence_label == 'cautious':
        return 'cautious_review_only'
    if candidate.get('action') == ACTION_REVIEW:
        return 'needs_visual_review'
    return 'keep_or_skip'


def _corpus_manual_review_pack_summary(
        sample: dict,
        items: list,
        missing_inputs: list) -> dict:
    page_count = _readiness_int(sample.get('page_count', 0))
    pages_analyzed = _readiness_int(_first_present(
        sample.get('pages_analyzed'),
        page_count))
    bounded = bool(sample.get('partial_or_bounded', False)) or (
        page_count and pages_analyzed < page_count)
    warning_types = [
        warning.get('type')
        for warning in sample.get('warnings', []) or []
        if isinstance(warning, dict)
    ]
    would_exclude_count = sum(
        1 for item in items or []
        if item.get('action') == ACTION_WOULD_EXCLUDE)
    summary = {
        'sample_name': sample.get('sample_name') or sample.get('file_name', ''),
        'file_path': sample.get('file_path', ''),
        'page_count': page_count,
        'pages_analyzed': pages_analyzed,
        'analyzed_pages': list(sample.get('analyzed_pages', []) or []),
        'analyzed_page_numbers': list(sample.get('analyzed_page_numbers', []) or []),
        'analysis_mode': sample.get('analysis_mode', ''),
        'bounded_analysis_only': bounded,
        'candidate_count': len(items or []),
        'would_exclude_candidate_count': would_exclude_count,
        'would_remove_block_count': sum(
            _readiness_int(item.get('would_remove_count', 0))
            for item in items or []),
        'review_only_candidate_count': sum(
            1 for item in items or []
            if (
                item.get('action') == ACTION_REVIEW or
                item.get('proposed_role') == ROLE_REVIEW_ONLY)),
        'cautious_candidate_count': sum(
            1 for item in items or []
            if item.get('confidence_label') == 'cautious'),
        'placeholder_candidate_count': sum(
            1 for item in items or []
            if (
                item.get('confidence_label') == 'placeholder' or
                item.get('proposed_role') == ROLE_LAYOUT_PLACEHOLDER)),
        'auto_approved_decision_count': sum(
            1 for item in items or []
            if item.get('auto_approved')),
        'manual_approval_required': bool(items),
        'ready_for_human_approval': bool(items) and not missing_inputs,
        'source_warning_types': warning_types,
        'missing_inputs': list(missing_inputs or []),
    }
    summary['recommended_next_action'] = _corpus_manual_review_next_action(summary)
    return summary


def _corpus_manual_review_next_action(summary: dict) -> str:
    if summary.get('missing_inputs'):
        return 'needs_corpus_report'
    if not summary.get('candidate_count', 0):
        return 'skip_no_candidates'
    if summary.get('bounded_analysis_only'):
        return 'analysis_only_large_sample'
    if summary.get('would_exclude_candidate_count', 0):
        return 'manual_approve_then_full_local_pipeline'
    return 'needs_visual_review'


def _corpus_manual_review_pack_warnings(summary: dict, missing_inputs: list) -> list:
    warnings = []
    for missing in missing_inputs or []:
        warnings.append({
            'type': 'missing_input',
            'input': missing,
        })
    if summary.get('bounded_analysis_only'):
        warnings.append({
            'type': 'bounded_large_sample_review',
            'pages_analyzed': summary.get('pages_analyzed'),
            'page_count': summary.get('page_count'),
        })
    if summary.get('auto_approved_decision_count', 0):
        warnings.append({
            'type': 'auto_approval_present',
            'count': summary.get('auto_approved_decision_count'),
        })
    if not summary.get('candidate_count', 0) and not missing_inputs:
        warnings.append({
            'type': 'no_candidates',
        })
    return warnings


def _corpus_manual_review_pack_recommendation(summary: dict, warnings: list) -> str:
    if summary.get('missing_inputs'):
        return 'Manual review pack is incomplete; regenerate corpus analysis first.'
    if summary.get('bounded_analysis_only'):
        return 'Manual review can proceed on the bounded large-sample subset only.'
    if summary.get('would_exclude_candidate_count', 0):
        return 'Ready for human approval review; do not apply filtering until decisions are explicit.'
    if summary.get('candidate_count', 0):
        return 'Candidates require visual/manual review, but none should be auto-approved.'
    return 'No candidates need manual review for this sample.'


def _corpus_manual_review_summary_empty() -> dict:
    return {
        'selected_sample_count': 0,
        'review_packs_ready_count': 0,
        'missing_review_pack_count': 0,
        'total_candidate_count': 0,
        'total_would_exclude_candidate_count': 0,
        'total_would_remove_block_count': 0,
        'manual_approval_required_count': 0,
        'auto_approved_decision_count': 0,
        'recommended_next_actions': {},
    }


def _corpus_manual_review_sample_row(pack: dict) -> dict:
    if not pack or not isinstance(pack, dict):
        return {
            'sample_name': '',
            'ready_for_human_approval': False,
            'candidate_count': 0,
            'would_exclude_candidate_count': 0,
            'would_remove_block_count': 0,
            'review_only_candidate_count': 0,
            'cautious_candidate_count': 0,
            'placeholder_candidate_count': 0,
            'bounded_analysis_only': False,
            'recommended_next_action': 'needs_corpus_report',
            'warnings': [{'type': 'missing_corpus_manual_review_pack'}],
        }
    summary = pack.get('summary') or {}
    warnings = [dict(warning) for warning in pack.get('warnings', []) or []]
    if not pack.get('enabled', False):
        warnings.append({'type': 'manual_review_pack_disabled'})
    return {
        'sample_name': summary.get('sample_name', pack.get('sample_name', '')),
        'ready_for_human_approval': bool(summary.get('ready_for_human_approval', False)),
        'candidate_count': _readiness_int(summary.get('candidate_count', 0)),
        'would_exclude_candidate_count': _readiness_int(
            summary.get('would_exclude_candidate_count', 0)),
        'would_remove_block_count': _readiness_int(
            summary.get('would_remove_block_count', 0)),
        'review_only_candidate_count': _readiness_int(
            summary.get('review_only_candidate_count', 0)),
        'cautious_candidate_count': _readiness_int(
            summary.get('cautious_candidate_count', 0)),
        'placeholder_candidate_count': _readiness_int(
            summary.get('placeholder_candidate_count', 0)),
        'bounded_analysis_only': bool(summary.get('bounded_analysis_only', False)),
        'manual_approval_required': bool(summary.get('manual_approval_required', False)),
        'auto_approved_decision_count': _readiness_int(
            summary.get('auto_approved_decision_count', 0)),
        'recommended_next_action': summary.get('recommended_next_action', ''),
        'warnings': warnings,
    }


def _corpus_manual_review_summary(samples: list) -> dict:
    action_counts = Counter(
        sample.get('recommended_next_action', '')
        for sample in samples or [])
    return {
        'selected_sample_count': len(samples or []),
        'review_packs_ready_count': sum(
            1 for sample in samples or []
            if sample.get('ready_for_human_approval')),
        'missing_review_pack_count': sum(
            1 for sample in samples or []
            if sample.get('recommended_next_action') == 'needs_corpus_report'),
        'total_candidate_count': sum(
            sample.get('candidate_count', 0)
            for sample in samples or []),
        'total_would_exclude_candidate_count': sum(
            sample.get('would_exclude_candidate_count', 0)
            for sample in samples or []),
        'total_would_remove_block_count': sum(
            sample.get('would_remove_block_count', 0)
            for sample in samples or []),
        'manual_approval_required_count': sum(
            1 for sample in samples or []
            if sample.get('manual_approval_required')),
        'auto_approved_decision_count': sum(
            sample.get('auto_approved_decision_count', 0)
            for sample in samples or []),
        'recommended_next_actions': dict(sorted(action_counts.items())),
    }


def _corpus_manual_review_summary_warnings(samples: list) -> list:
    warnings = []
    for sample in samples or []:
        for warning in sample.get('warnings', []) or []:
            item = dict(warning)
            item['sample_name'] = sample.get('sample_name', '')
            warnings.append(item)
    if any(sample.get('auto_approved_decision_count', 0) for sample in samples or []):
        warnings.append({
            'type': 'auto_approval_present',
        })
    return warnings


def _corpus_manual_review_summary_recommendation(summary: dict, warnings: list) -> str:
    warning_types = {warning.get('type') for warning in warnings or []}
    if 'missing_corpus_manual_review_pack' in warning_types:
        return 'Some review packs are missing; regenerate local corpus review packs before Phase 2Y2.'
    if summary.get('auto_approved_decision_count', 0):
        return 'Auto-approved decisions are present; discard and regenerate packs without approvals.'
    if summary.get('review_packs_ready_count', 0):
        return 'Manual review packs are ready; human approval is required before any Phase 2Y2 filtering experiment.'
    return 'No selected sample is ready for manual approval.'


def _corpus_approval_disabled_summary(
        sample_name: str,
        bounded_analysis_only: bool,
        full_docx_validation_allowed: bool) -> dict:
    return {
        'sample_name': sample_name,
        'candidate_count': 0,
        'explicit_decision_count': 0,
        'approve_count': 0,
        'reject_count': 0,
        'unsure_count': 0,
        'missing_decision_count': 0,
        'conflict_decision_count': 0,
        'explicit_decisions_complete': False,
        'eligible_approved_candidate_count': 0,
        'blocked_candidate_count': 0,
        'reviewed_removed_block_count': 0,
        'body_region_removed_count': 0,
        'rejected_removed_count': 0,
        'unsure_removed_count': 0,
        'layout_placeholder_removed_count': 0,
        'raw_would_exclude_without_approval_removed_count': 0,
        'unsafe_removed_count': 0,
        'bounded_analysis_only': bool(bounded_analysis_only),
        'full_docx_validation_allowed': bool(full_docx_validation_allowed),
        'full_docx_validation_blocked': bool(
            bounded_analysis_only and not full_docx_validation_allowed),
    }


def _corpus_approval_candidate_rows(
        dry_run_report: dict,
        review_decisions,
        filtering_report: dict) -> list:
    candidates = _dry_run_candidates(dry_run_report)
    decision_map = _review_decision_map(review_decisions)
    approved_fingerprints = set(filtering_report.get('approved_fingerprints', []) or [])
    blocked_by_fingerprint = {
        item.get('fingerprint'): item
        for item in filtering_report.get('blocked_candidates', []) or []
        if item.get('fingerprint')
    }
    return [
        _corpus_approval_candidate_row(
            candidate,
            decision_map,
            approved_fingerprints,
            blocked_by_fingerprint)
        for candidate in candidates or []
    ]


def _corpus_approval_candidate_row(
        candidate: dict,
        decision_map: dict,
        approved_fingerprints: set,
        blocked_by_fingerprint: dict) -> dict:
    decision = (
        decision_map.get(candidate.get('fingerprint')) or
        decision_map.get(candidate.get('candidate_id')) or
        DECISION_NONE)
    blocked = blocked_by_fingerprint.get(candidate.get('fingerprint'), {})
    eligible = candidate.get('fingerprint') in approved_fingerprints
    return {
        'candidate_id': candidate.get('candidate_id', ''),
        'fingerprint': candidate.get('fingerprint', ''),
        'proposed_role': candidate.get('proposed_role', ''),
        'action': candidate.get('action', ''),
        'region': candidate.get('region', ''),
        'regions': list(candidate.get('regions', []) or []),
        'manual_decision': decision,
        'eligible_for_reviewed_filtering': bool(eligible),
        'blocked_reason': '' if eligible else blocked.get('reason', 'missing_review_decision'),
        'would_remove_count': (
            _readiness_int(candidate.get('support_count', 0))
            if candidate.get('action') == ACTION_WOULD_EXCLUDE else 0),
        'affected_pages': list(candidate.get('affected_pages', []) or []),
        'support_count': _readiness_int(candidate.get('support_count', 0)),
    }


def _corpus_approval_summary(
        sample_name: str,
        bounded_analysis_only: bool,
        full_docx_validation_allowed: bool,
        candidates: list,
        filtering_report: dict) -> dict:
    decision_counts = Counter(
        candidate.get('manual_decision', DECISION_NONE)
        for candidate in candidates or [])
    removed_blocks = _corpus_removed_blocks(filtering_report)
    missing_count = decision_counts.get(DECISION_NONE, 0)
    conflict_count = decision_counts.get(DECISION_CONFLICT, 0)
    rejected_removed_count = _corpus_removed_decision_count(
        removed_blocks,
        DECISION_REJECT_EXCLUDE)
    unsure_removed_count = _corpus_removed_decision_count(
        removed_blocks,
        DECISION_UNSURE)
    body_removed_count = _corpus_removed_region_count(removed_blocks, REGION_BODY)
    layout_removed_count = _corpus_removed_layout_placeholder_count(removed_blocks)
    raw_without_approval_count = _corpus_unapproved_raw_would_exclude_removed_count(
        removed_blocks,
        candidates)
    unsafe_removed_count = (
        body_removed_count +
        rejected_removed_count +
        unsure_removed_count +
        layout_removed_count +
        raw_without_approval_count)
    filtering_summary = filtering_report.get('summary', {}) or {}
    return {
        'sample_name': sample_name,
        'candidate_count': len(candidates or []),
        'explicit_decision_count': sum(
            1 for candidate in candidates or []
            if candidate.get('manual_decision') not in {DECISION_NONE, ''}),
        'approve_count': decision_counts.get(DECISION_APPROVE_EXCLUDE, 0),
        'reject_count': decision_counts.get(DECISION_REJECT_EXCLUDE, 0),
        'unsure_count': decision_counts.get(DECISION_UNSURE, 0),
        'missing_decision_count': missing_count,
        'conflict_decision_count': conflict_count,
        'explicit_decisions_complete': missing_count == 0 and conflict_count == 0,
        'eligible_approved_candidate_count': _readiness_int(
            filtering_report.get('approved_candidate_count', 0)),
        'blocked_candidate_count': _readiness_int(
            filtering_report.get('blocked_candidate_count', 0)),
        'reviewed_would_remove_block_count': _readiness_int(
            filtering_summary.get('would_remove_block_count', 0)),
        'reviewed_removed_block_count': _readiness_int(
            filtering_summary.get('removed_block_count', 0)),
        'reviewed_kept_block_count': _readiness_int(
            filtering_summary.get('kept_block_count', 0)),
        'body_region_removed_count': body_removed_count,
        'rejected_removed_count': rejected_removed_count,
        'unsure_removed_count': unsure_removed_count,
        'layout_placeholder_removed_count': layout_removed_count,
        'raw_would_exclude_without_approval_removed_count': raw_without_approval_count,
        'unsafe_removed_count': unsafe_removed_count,
        'bounded_analysis_only': bool(bounded_analysis_only),
        'full_docx_validation_allowed': bool(full_docx_validation_allowed),
        'full_docx_validation_blocked': bool(
            bounded_analysis_only and not full_docx_validation_allowed),
    }


def _corpus_removed_blocks(filtering_report: dict) -> list:
    return [
        dict(block)
        for page in (filtering_report or {}).get('pages', []) or []
        for block in page.get('removed_blocks', []) or []
    ]


def _corpus_removed_region_count(removed_blocks: list, region: str) -> int:
    return sum(1 for block in removed_blocks or [] if block.get('region') == region)


def _corpus_removed_decision_count(removed_blocks: list, decision: str) -> int:
    return sum(
        1 for block in removed_blocks or []
        if block.get('manual_decision') == decision)


def _corpus_removed_layout_placeholder_count(removed_blocks: list) -> int:
    return sum(
        1 for block in removed_blocks or []
        if block.get('proposed_role') == ROLE_LAYOUT_PLACEHOLDER)


def _corpus_unapproved_raw_would_exclude_removed_count(
        removed_blocks: list,
        candidates: list) -> int:
    candidate_by_fingerprint = {
        candidate.get('fingerprint'): candidate
        for candidate in candidates or []
        if candidate.get('fingerprint')
    }
    count = 0
    for block in removed_blocks or []:
        candidate = candidate_by_fingerprint.get(block.get('fingerprint'), {})
        if (
                candidate.get('action') == ACTION_WOULD_EXCLUDE and
                candidate.get('manual_decision') != DECISION_APPROVE_EXCLUDE):
            count += 1
    return count


def _corpus_approval_warnings(summary: dict) -> list:
    warnings = []
    if summary.get('missing_decision_count', 0):
        warnings.append({
            'type': 'missing_review_decisions',
            'count': summary.get('missing_decision_count'),
        })
    if summary.get('conflict_decision_count', 0):
        warnings.append({
            'type': 'conflicting_review_decisions',
            'count': summary.get('conflict_decision_count'),
        })
    if summary.get('unsure_count', 0):
        warnings.append({
            'type': 'unsure_candidates_present',
            'count': summary.get('unsure_count'),
            'message': 'Unsure candidates are blocked and need visual review.',
        })
    if summary.get('body_region_removed_count', 0):
        warnings.append({
            'type': 'body_region_removed',
            'count': summary.get('body_region_removed_count'),
        })
    if summary.get('rejected_removed_count', 0):
        warnings.append({
            'type': 'rejected_candidate_removed',
            'count': summary.get('rejected_removed_count'),
        })
    if summary.get('unsure_removed_count', 0):
        warnings.append({
            'type': 'unsure_candidate_removed',
            'count': summary.get('unsure_removed_count'),
        })
    if summary.get('layout_placeholder_removed_count', 0):
        warnings.append({
            'type': 'layout_placeholder_removed',
            'count': summary.get('layout_placeholder_removed_count'),
        })
    if summary.get('raw_would_exclude_without_approval_removed_count', 0):
        warnings.append({
            'type': 'raw_would_exclude_without_approval_removed',
            'count': summary.get('raw_would_exclude_without_approval_removed_count'),
        })
    if summary.get('full_docx_validation_blocked', False):
        warnings.append({
            'type': 'bounded_large_sample_full_docx_blocked',
            'message': 'Large sample remains bounded-subset only.',
        })
    if not summary.get('eligible_approved_candidate_count', 0):
        warnings.append({
            'type': 'no_eligible_approved_candidates',
        })
    return warnings


def _corpus_approval_recommendation(summary: dict, warnings: list) -> str:
    warning_types = {warning.get('type') for warning in warnings or []}
    if 'missing_review_decisions' in warning_types:
        return 'Phase 2Y2 is blocked until every candidate has exactly one manual decision.'
    if 'conflicting_review_decisions' in warning_types:
        return 'Phase 2Y2 is blocked until conflicting manual decisions are resolved.'
    unsafe_types = {
        'body_region_removed',
        'rejected_candidate_removed',
        'unsure_candidate_removed',
        'layout_placeholder_removed',
        'raw_would_exclude_without_approval_removed',
    }
    if warning_types.intersection(unsafe_types):
        return 'Approved-only validation is unsafe; do not continue deeper validation for this sample.'
    if summary.get('full_docx_validation_blocked', False):
        return 'Approved-only bounded validation may proceed; full large-document DOCX validation remains blocked.'
    if summary.get('eligible_approved_candidate_count', 0):
        if summary.get('unsure_count', 0):
            return 'Approved candidates may be validated locally; unsure candidates remain blocked for visual review.'
        return 'Approved candidates may proceed through local-only validation.'
    return 'No eligible approved candidates are available for local validation.'


def _corpus_approval_summary_empty() -> dict:
    return {
        'sample_count': 0,
        'samples_validated_count': 0,
        'samples_with_missing_decisions': 0,
        'samples_with_unsure_decisions': 0,
        'samples_bounded_only': 0,
        'total_candidate_count': 0,
        'total_approve_count': 0,
        'total_reject_count': 0,
        'total_unsure_count': 0,
        'total_missing_decision_count': 0,
        'total_eligible_approved_candidate_count': 0,
        'total_removed_block_count': 0,
        'total_body_region_removed_count': 0,
        'full_large_document_validation_skipped_count': 0,
    }


def _corpus_approval_summary_row(report: dict) -> dict:
    if not report or not isinstance(report, dict):
        return {
            'sample_name': '',
            'enabled': False,
            'candidate_count': 0,
            'approve_count': 0,
            'reject_count': 0,
            'unsure_count': 0,
            'missing_decision_count': 0,
            'eligible_approved_candidate_count': 0,
            'reviewed_removed_block_count': 0,
            'body_region_removed_count': 0,
            'bounded_analysis_only': False,
            'full_docx_validation_blocked': False,
            'warnings': [{'type': 'missing_corpus_approval_validation_report'}],
            'safe_to_run_approved_only_validation': False,
        }

    summary = report.get('summary') or {}
    return {
        'sample_name': summary.get('sample_name', report.get('sample_name', '')),
        'enabled': bool(report.get('enabled', False)),
        'candidate_count': _readiness_int(summary.get('candidate_count', 0)),
        'approve_count': _readiness_int(summary.get('approve_count', 0)),
        'reject_count': _readiness_int(summary.get('reject_count', 0)),
        'unsure_count': _readiness_int(summary.get('unsure_count', 0)),
        'missing_decision_count': _readiness_int(
            summary.get('missing_decision_count', 0)),
        'eligible_approved_candidate_count': _readiness_int(
            summary.get('eligible_approved_candidate_count', 0)),
        'reviewed_removed_block_count': _readiness_int(
            summary.get('reviewed_removed_block_count', 0)),
        'body_region_removed_count': _readiness_int(
            summary.get('body_region_removed_count', 0)),
        'bounded_analysis_only': bool(summary.get('bounded_analysis_only', False)),
        'full_docx_validation_blocked': bool(
            summary.get('full_docx_validation_blocked', False)),
        'warnings': [dict(warning) for warning in report.get('warnings', []) or []],
        'safe_to_run_approved_only_validation': bool(
            (report.get('recommendation') or {}).get(
                'safe_to_run_approved_only_validation', False)),
    }


def _corpus_approval_validation_summary(samples: list) -> dict:
    return {
        'sample_count': len(samples or []),
        'samples_validated_count': sum(
            1 for sample in samples or []
            if sample.get('safe_to_run_approved_only_validation')),
        'samples_with_missing_decisions': sum(
            1 for sample in samples or []
            if sample.get('missing_decision_count', 0)),
        'samples_with_unsure_decisions': sum(
            1 for sample in samples or []
            if sample.get('unsure_count', 0)),
        'samples_bounded_only': sum(
            1 for sample in samples or []
            if sample.get('bounded_analysis_only')),
        'total_candidate_count': sum(
            sample.get('candidate_count', 0)
            for sample in samples or []),
        'total_approve_count': sum(
            sample.get('approve_count', 0)
            for sample in samples or []),
        'total_reject_count': sum(
            sample.get('reject_count', 0)
            for sample in samples or []),
        'total_unsure_count': sum(
            sample.get('unsure_count', 0)
            for sample in samples or []),
        'total_missing_decision_count': sum(
            sample.get('missing_decision_count', 0)
            for sample in samples or []),
        'total_eligible_approved_candidate_count': sum(
            sample.get('eligible_approved_candidate_count', 0)
            for sample in samples or []),
        'total_removed_block_count': sum(
            sample.get('reviewed_removed_block_count', 0)
            for sample in samples or []),
        'total_body_region_removed_count': sum(
            sample.get('body_region_removed_count', 0)
            for sample in samples or []),
        'full_large_document_validation_skipped_count': sum(
            1 for sample in samples or []
            if sample.get('full_docx_validation_blocked')),
    }


def _corpus_approval_summary_warnings(samples: list) -> list:
    warnings = []
    for sample in samples or []:
        if not sample.get('enabled', False):
            warnings.append({
                'type': 'approval_validation_report_disabled',
                'sample_name': sample.get('sample_name', ''),
            })
        for warning in sample.get('warnings', []) or []:
            item = dict(warning)
            item['sample_name'] = sample.get('sample_name', '')
            warnings.append(item)
    return warnings


def _corpus_approval_summary_recommendation(summary: dict, warnings: list) -> str:
    warning_types = {warning.get('type') for warning in warnings or []}
    if 'missing_review_decisions' in warning_types:
        return 'Some samples still have missing review decisions; keep Phase 2Y2 blocked for those samples.'
    unsafe_types = {
        'body_region_removed',
        'rejected_candidate_removed',
        'unsure_candidate_removed',
        'layout_placeholder_removed',
        'raw_would_exclude_without_approval_removed',
    }
    if warning_types.intersection(unsafe_types):
        return 'At least one sample has unsafe approved-filtering behavior; do not proceed to integration.'
    if summary.get('samples_validated_count', 0):
        return 'Local approved-only validation completed; next work should use committed synthetic fixtures before integration.'
    return 'No sample has eligible approved candidates for deeper validation.'


def _raw_object_page_fingerprint(raw_object_pages: list) -> list:
    fingerprint = []
    for page in raw_object_pages or []:
        page_index = page.get('page_index')
        page_items = []
        for raw_object in page.get('raw_objects', []) or []:
            page_items.append((
                raw_object.get('raw_object_id'),
                raw_object.get('fingerprint'),
                raw_object.get('region'),
                tuple(_json_bbox(raw_object.get('bbox'))),
            ))
        fingerprint.append((page_index, tuple(page_items)))
    return fingerprint


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
