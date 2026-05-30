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

_SPACE_RE = re.compile(r'\s+')
_PAGE_NUMBER_RE_LIST = (
    re.compile(r'^(?:page|p\.?)\s*\d+$', re.IGNORECASE),
    re.compile(r'^(?:page|p\.?)\s*\d+\s*(?:/|of)\s*\d+$', re.IGNORECASE),
    re.compile(r'^\d+\s*(?:/|of)\s*\d+$', re.IGNORECASE),
    re.compile(r'^-?\s*\d+\s*-?$'),
)


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
        candidates.append({
            'fingerprint': key,
            'text': group[0]['normalized_text'],
            'pages': pages_seen,
            'count': len(group),
            'regions': regions_seen,
            'instances': group,
        })

    candidates.sort(key=lambda item: (-len(item['pages']), item['fingerprint']))
    return candidates


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
