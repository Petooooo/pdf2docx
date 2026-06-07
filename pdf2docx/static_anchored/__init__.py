# -*- coding: utf-8 -*-

"""Internal source-page anchored static header/footer helpers.

This package is intentionally not wired into the public CLI/API or default
``Converter.convert()`` behavior. It supports private/local visual fidelity
experiments where detected source-page header/footer/page-label artifacts are
preserved as static DOCX header/footer text instead of Word PAGE fields.
"""

from .analyzer import (
    build_static_anchored_plan,
    build_static_filtering_config,
    infer_zone_from_bbox,
    recommend_static_anchored_mode,
)
from .converter import convert_static_anchored_pdf
from .validator import validate_static_anchored_docx
from .writer import apply_static_anchored_plan

__all__ = [
    'apply_static_anchored_plan',
    'build_static_anchored_plan',
    'build_static_filtering_config',
    'convert_static_anchored_pdf',
    'infer_zone_from_bbox',
    'recommend_static_anchored_mode',
    'validate_static_anchored_docx',
]
