# -*- coding: utf-8 -*-

'''Small pure helpers for document-level layout analysis.

This module intentionally does not integrate with the converter pipeline yet.
It works with simplified page dictionaries so tests and debug tools can build
header/footer analysis incrementally without changing conversion output.
'''

import re
from collections import defaultdict


PAGE_NUMBER_PLACEHOLDER = '<PAGE_NUMBER>'
REGION_TOP = 'top'
REGION_BODY = 'body'
REGION_BOTTOM = 'bottom'
DEFAULT_TOP_RATIO = 0.15
DEFAULT_BOTTOM_RATIO = 0.15
DEFAULT_NEAR_BODY_EDGE_RATIO = 0.12
STRONG_SENTENCE_END_PUNC = '.．。?？!！'

_SPACE_RE = re.compile(r'\s+')
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

            records.append({
                'page_index': page_index,
                'block_index': block_index,
                'text': text,
                'normalized_text': fingerprint['text'],
                'bbox': bbox,
                'region': region,
                'style': normalize_style_key(style),
                'fingerprint': fingerprint['key'],
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
        candidates.append({
            'fingerprint': key,
            'text': group[0]['normalized_text'],
            'pages': pages_seen,
            'count': len(group),
            'regions': regions_seen,
            'confidence': confidence,
            'signals': {
                'support_pages': support,
                'total_pages': total_pages,
                'instance_count': len(group),
                'regions': regions_seen,
            },
            'instances': group,
        })

    candidates.sort(key=lambda item: (-len(item['pages']), item['fingerprint']))
    return candidates


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
    continuations = find_paragraph_continuation_candidates(
        page_summaries,
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
        'paragraph_continuation_candidates': continuations,
        'signals': {
            'text_block_count': len(records),
            'repeated_text_candidate_count': len(repeated),
            'paragraph_continuation_candidate_count': len(continuations),
        },
    }


def find_paragraph_continuation_candidates(
        page_summaries: list,
        top_ratio: float = DEFAULT_TOP_RATIO,
        bottom_ratio: float = DEFAULT_BOTTOM_RATIO,
        near_edge_ratio: float = DEFAULT_NEAR_BODY_EDGE_RATIO) -> list:
    '''Score adjacent-page paragraph continuation candidates.'''
    candidates = []
    page_summaries = page_summaries or []
    for index, previous_page in enumerate(page_summaries[:-1]):
        next_page = page_summaries[index+1]
        previous_block = _last_body_block(previous_page)
        next_block = _first_body_block(next_page)
        candidates.append(score_paragraph_continuation(
            previous_page,
            next_page,
            previous_block,
            next_block,
            top_ratio=top_ratio,
            bottom_ratio=bottom_ratio,
            near_edge_ratio=near_edge_ratio))
    return candidates


def score_paragraph_continuation(
        previous_page: dict,
        next_page: dict,
        previous_block: dict = None,
        next_block: dict = None,
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


def _last_body_block(page_summary: dict):
    body_blocks = _body_blocks(page_summary)
    if not body_blocks:
        return None
    return sorted(body_blocks, key=lambda block: (block['bbox'][3], block['block_index']))[-1]


def _first_body_block(page_summary: dict):
    body_blocks = _body_blocks(page_summary)
    if not body_blocks:
        return None
    return sorted(body_blocks, key=lambda block: (block['bbox'][1], block['block_index']))[0]


def _body_blocks(page_summary: dict) -> list:
    blocks = page_summary.get('text_blocks', []) or []
    return [
        block for block in blocks
        if block.get('region') == REGION_BODY and normalize_text(block.get('text'))
    ]


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
