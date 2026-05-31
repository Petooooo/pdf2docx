# -*- coding: utf-8 -*-

'''Small pure helpers for document-level layout analysis.

This module intentionally does not integrate with the converter pipeline yet.
It works with simplified page dictionaries so tests and debug tools can build
header/footer analysis incrementally without changing conversion output.
'''

import re
from collections import defaultdict


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
