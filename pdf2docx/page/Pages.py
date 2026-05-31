# -*- coding: utf-8 -*-

'''Collection of :py:class:`~pdf2docx.page.Page` instances.'''

import logging

from .LayoutAnalyzer import (
    build_document_parse_filtering_hook_report,
    build_layout_analysis_report,
)
from .RawPageFactory import RawPageFactory
from ..common.Collection import BaseCollection
from ..font.Fonts import Fonts


class Pages(BaseCollection):
    '''A collection of ``Page``.'''

    def __init__(self, instances:list=None, parent=None):
        super().__init__(instances, parent)
        self._layout_analysis_report = None
        self._document_parse_filtering_hook_report = None


    @property
    def layout_analysis_report(self):
        return self._layout_analysis_report


    def restore_layout_analysis_report(self, report):
        self._layout_analysis_report = report or None

    def parse(self, fitz_doc, **settings):
        '''Analyze document structure, e.g. page section, header, footer.

        Args:
            fitz_doc (fitz.Document): ``PyMuPDF`` Document instance.
            settings (dict): Parsing parameters.
        '''
        self._layout_analysis_report = None
        self._document_parse_filtering_hook_report = None

        # ---------------------------------------------
        # 0. extract fonts properties, especially line height ratio
        # ---------------------------------------------
        fonts = Fonts.extract(fitz_doc)

        # ---------------------------------------------
        # 1. extract and then clean up raw page
        # ---------------------------------------------
        pages, raw_pages = [], []
        words_found = False
        for page in self:
            if page.skip_parsing: continue

            # init and extract data from PDF
            raw_page = RawPageFactory.create(page_engine=fitz_doc[page.id], backend='PyMuPDF')
            raw_page.restore(**settings)

            # check if any words are extracted since scanned pdf may be directed
            if not words_found and raw_page.raw_text.strip():
                words_found = True

            # process blocks and shapes based on bbox
            raw_page.clean_up(**settings)

            # process font properties
            raw_page.process_font(fonts)            

            # after this step, we can get some basic properties
            # NOTE: floating images are detected when cleaning up blocks, so collect them here
            page.width = raw_page.width
            page.height = raw_page.height
            page.float_images.reset().extend(raw_page.blocks.floating_image_blocks)

            raw_pages.append(raw_page)
            pages.append(page)

        # show message if no words found
        if not words_found:
            logging.warning('Words count: 0. It might be a scanned pdf, which is not supported yet.')

        
        # ---------------------------------------------
        # 2. parse structure in document/pages level
        # ---------------------------------------------
        # NOTE: blocks structure might be changed in this step, e.g. promote page header/footer,
        # so blocks structure based process, e.g. calculating margin, parse section should be 
        # run after this step.
        layout_analysis_report = None
        if settings.get('layout_analysis'):
            layout_analysis_report = self._layout_analysis_report = Pages._build_layout_analysis_report(
                pages, raw_pages, **settings)

        if settings.get('_document_parse_filtering_hook_enabled'):
            if layout_analysis_report is None:
                layout_analysis_report = Pages._build_layout_analysis_report(
                    pages, raw_pages, **settings)
            self._run_document_parse_filtering_hook(
                layout_analysis_report,
                **settings)

        header, footer = Pages._parse_document(raw_pages)


        # ---------------------------------------------
        # 3. parse structure in page level, e.g. page margin, section
        # ---------------------------------------------
        # parse sections
        for page, raw_page in zip(pages, raw_pages):
            # page margin
            margin = raw_page.calculate_margin(**settings)
            raw_page.margin = page.margin = margin

            # page section
            sections = raw_page.parse_section(**settings)
            page.sections.extend(sections)
    

    @staticmethod
    def _parse_document(raw_pages:list):
        '''Parse structure in document/pages level, e.g. header, footer'''
        # TODO
        return '', ''


    def _run_document_parse_filtering_hook(self, layout_analysis_report:dict, **settings):
        '''Run the internal document-parse dry-run hook without mutating pages.'''
        if not settings.get('_document_parse_filtering_hook_enabled'):
            self._document_parse_filtering_hook_report = None
            return None

        self._document_parse_filtering_hook_report = Pages._build_document_parse_filtering_hook_report(
            layout_analysis_report,
            **settings)
        return self._document_parse_filtering_hook_report


    @staticmethod
    def _build_document_parse_filtering_hook_report(
            layout_analysis_report:dict,
            **settings):
        layout_analysis_report = layout_analysis_report or {}
        return build_document_parse_filtering_hook_report(
            layout_analysis_report.get('pages', []),
            settings.get('_document_parse_filtering_dry_run_report') or
            layout_analysis_report.get('header_footer_exclusion_dry_run', {}),
            settings.get('_document_parse_filtering_review_decisions'),
            body_filtering_diff_report=settings.get(
                '_document_parse_filtering_body_diff_report'),
            paragraph_integrity_report=settings.get(
                '_document_parse_filtering_paragraph_integrity_report'),
            phase_2k_simulation_report=settings.get(
                '_document_parse_filtering_phase_2k_report'),
            enabled=bool(settings.get('_document_parse_filtering_hook_enabled')),
            apply=bool(settings.get('_document_parse_filtering_apply', False)),
            expected_removed_count=settings.get(
                '_document_parse_filtering_expected_removed_count',
                48),
            expected_kept_count=settings.get(
                '_document_parse_filtering_expected_kept_count',
                742),
            expected_body_region_removed_count=settings.get(
                '_document_parse_filtering_expected_body_region_removed_count',
                0))


    @staticmethod
    def _build_layout_analysis_report(pages:list, raw_pages:list, **settings):
        analysis_pages = Pages._layout_analysis_pages(pages, raw_pages)
        return build_layout_analysis_report(
            analysis_pages,
            min_pages=settings.get('layout_analysis_min_pages', 2),
            top_ratio=settings.get('layout_analysis_top_ratio', 0.15),
            bottom_ratio=settings.get('layout_analysis_bottom_ratio', 0.15))


    @staticmethod
    def _layout_analysis_pages(pages:list, raw_pages:list):
        analysis_pages = []
        for page, raw_page in zip(pages, raw_pages):
            analysis_pages.append({
                'page_index': page.id,
                'width': raw_page.width,
                'height': raw_page.height,
                'blocks': [
                    Pages._layout_analysis_block(block) for block in raw_page.blocks
                ],
            })
        return analysis_pages


    @staticmethod
    def _layout_analysis_block(block):
        return {
            'text': getattr(block, 'text', ''),
            'bbox': Pages._json_bbox(getattr(block, 'bbox', None)),
            'style': Pages._layout_analysis_style(block),
        }


    @staticmethod
    def _layout_analysis_style(block):
        spans = getattr(block, 'spans', [])
        for span in spans:
            font = getattr(span, 'font', '')
            size = getattr(span, 'size', '')
            flags = getattr(span, 'flags', '')
            if font or size or flags:
                return {
                    'font': font,
                    'size': size,
                    'flags': flags,
                }
        return {}


    @staticmethod
    def _json_bbox(bbox):
        if not bbox:
            return [0.0, 0.0, 0.0, 0.0]
        return [round(float(value), 2) for value in bbox[:4]]
