# -*- coding: utf-8 -*-

'''Collection of :py:class:`~pdf2docx.page.Page` instances.'''

import copy
import logging

from .LayoutAnalyzer import (
    build_document_parse_copied_raw_page_filtering_apply_report,
    build_document_parse_filtering_hook_report,
    build_document_parse_filtered_parse_experiment_report,
    build_document_parse_guarded_raw_page_apply_restore_report,
    build_document_parse_raw_object_mapping_report,
    build_layout_analysis_report,
    classify_y_band,
    reviewed_raw_object_removal_plan,
    REGION_BODY,
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
        self._document_parse_raw_object_mapping_report = None
        self._document_parse_copied_raw_filtering_apply_report = None
        self._document_parse_guarded_raw_apply_restore_report = None
        self._document_parse_filtered_parse_experiment_report = None


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
        self._document_parse_raw_object_mapping_report = None
        self._document_parse_copied_raw_filtering_apply_report = None
        self._document_parse_guarded_raw_apply_restore_report = None
        self._document_parse_filtered_parse_experiment_report = None

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

        if settings.get('_document_parse_raw_object_mapping_enabled'):
            if layout_analysis_report is None:
                layout_analysis_report = Pages._build_layout_analysis_report(
                    pages, raw_pages, **settings)
            self._run_document_parse_raw_object_mapping_validation(
                layout_analysis_report,
                pages,
                raw_pages,
                **settings)

        if settings.get('_document_parse_copied_raw_filtering_enabled'):
            if layout_analysis_report is None:
                layout_analysis_report = Pages._build_layout_analysis_report(
                    pages, raw_pages, **settings)
            self._run_document_parse_copied_raw_filtering_apply(
                layout_analysis_report,
                pages,
                raw_pages,
                **settings)

        if settings.get('_document_parse_guarded_raw_apply_restore_enabled'):
            if layout_analysis_report is None:
                layout_analysis_report = Pages._build_layout_analysis_report(
                    pages, raw_pages, **settings)
            self._run_document_parse_guarded_raw_apply_restore(
                layout_analysis_report,
                pages,
                raw_pages,
                **settings)

        if settings.get('_document_parse_filtered_parse_experiment_enabled'):
            if layout_analysis_report is None:
                layout_analysis_report = Pages._build_layout_analysis_report(
                    pages, raw_pages, **settings)
            self._run_document_parse_filtered_parse_experiment(
                layout_analysis_report,
                pages,
                raw_pages,
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


    def _run_document_parse_raw_object_mapping_validation(
            self,
            layout_analysis_report:dict,
            pages:list,
            raw_pages:list,
            **settings):
        '''Validate summary-to-raw-object mapping without mutating raw pages.'''
        if not settings.get('_document_parse_raw_object_mapping_enabled'):
            self._document_parse_raw_object_mapping_report = None
            return None

        self._document_parse_raw_object_mapping_report = Pages._build_document_parse_raw_object_mapping_report(
            layout_analysis_report,
            pages,
            raw_pages,
            **settings)
        return self._document_parse_raw_object_mapping_report


    def _run_document_parse_copied_raw_filtering_apply(
            self,
            layout_analysis_report:dict,
            pages:list,
            raw_pages:list,
            **settings):
        '''Apply reviewed filtering to copied raw-page records only.'''
        if not settings.get('_document_parse_copied_raw_filtering_enabled'):
            self._document_parse_copied_raw_filtering_apply_report = None
            return None

        self._document_parse_copied_raw_filtering_apply_report = Pages._build_document_parse_copied_raw_filtering_apply_report(
            layout_analysis_report,
            pages,
            raw_pages,
            raw_object_mapping_report=self._document_parse_raw_object_mapping_report,
            **settings)
        return self._document_parse_copied_raw_filtering_apply_report


    def _run_document_parse_guarded_raw_apply_restore(
            self,
            layout_analysis_report:dict,
            pages:list,
            raw_pages:list,
            **settings):
        '''Apply reviewed filtering to raw pages and restore before returning.'''
        if not settings.get('_document_parse_guarded_raw_apply_restore_enabled'):
            self._document_parse_guarded_raw_apply_restore_report = None
            return None

        self._document_parse_guarded_raw_apply_restore_report = Pages._build_document_parse_guarded_raw_apply_restore_report(
            layout_analysis_report,
            pages,
            raw_pages,
            raw_object_mapping_report=self._document_parse_raw_object_mapping_report,
            copied_apply_report=self._document_parse_copied_raw_filtering_apply_report,
            **settings)
        return self._document_parse_guarded_raw_apply_restore_report


    def _run_document_parse_filtered_parse_experiment(
            self,
            layout_analysis_report:dict,
            pages:list,
            raw_pages:list,
            **settings):
        '''Run a filtered parse experiment and restore raw pages before returning.'''
        if not settings.get('_document_parse_filtered_parse_experiment_enabled'):
            self._document_parse_filtered_parse_experiment_report = None
            return None

        self._document_parse_filtered_parse_experiment_report = Pages._build_document_parse_filtered_parse_experiment_report(
            layout_analysis_report,
            pages,
            raw_pages,
            raw_object_mapping_report=self._document_parse_raw_object_mapping_report,
            copied_apply_report=self._document_parse_copied_raw_filtering_apply_report,
            guarded_apply_restore_report=self._document_parse_guarded_raw_apply_restore_report,
            **settings)
        return self._document_parse_filtered_parse_experiment_report


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
    def _build_document_parse_raw_object_mapping_report(
            layout_analysis_report:dict,
            pages:list,
            raw_pages:list,
            **settings):
        layout_analysis_report = layout_analysis_report or {}
        raw_object_pages = Pages._raw_object_mapping_pages(pages, raw_pages)
        return build_document_parse_raw_object_mapping_report(
            layout_analysis_report.get('pages', []),
            raw_object_pages,
            settings.get('_document_parse_mapping_dry_run_report') or
            layout_analysis_report.get('header_footer_exclusion_dry_run', {}),
            settings.get('_document_parse_filtering_review_decisions'),
            enabled=bool(settings.get('_document_parse_raw_object_mapping_enabled')),
            expected_would_remove_count=settings.get(
                '_document_parse_mapping_expected_would_remove_count'))


    @staticmethod
    def _build_document_parse_copied_raw_filtering_apply_report(
            layout_analysis_report:dict,
            pages:list,
            raw_pages:list,
            raw_object_mapping_report:dict=None,
            **settings):
        layout_analysis_report = layout_analysis_report or {}
        raw_object_pages = Pages._raw_object_mapping_pages(pages, raw_pages)
        return build_document_parse_copied_raw_page_filtering_apply_report(
            layout_analysis_report.get('pages', []),
            raw_object_pages,
            settings.get('_document_parse_mapping_dry_run_report') or
            layout_analysis_report.get('header_footer_exclusion_dry_run', {}),
            settings.get('_document_parse_filtering_review_decisions'),
            raw_object_mapping_report=raw_object_mapping_report,
            enabled=bool(settings.get('_document_parse_copied_raw_filtering_enabled')),
            expected_mapping_count=settings.get(
                '_document_parse_copied_raw_filtering_expected_mapping_count'))


    @staticmethod
    def _build_document_parse_guarded_raw_apply_restore_report(
            layout_analysis_report:dict,
            pages:list,
            raw_pages:list,
            raw_object_mapping_report:dict=None,
            copied_apply_report:dict=None,
            **settings):
        layout_analysis_report = layout_analysis_report or {}
        raw_object_pages_before = Pages._raw_object_mapping_pages(pages, raw_pages)
        mapping_report = raw_object_mapping_report or build_document_parse_raw_object_mapping_report(
            layout_analysis_report.get('pages', []),
            raw_object_pages_before,
            settings.get('_document_parse_mapping_dry_run_report') or
            layout_analysis_report.get('header_footer_exclusion_dry_run', {}),
            settings.get('_document_parse_filtering_review_decisions'),
            enabled=True,
            expected_would_remove_count=settings.get(
                '_document_parse_guarded_raw_apply_restore_expected_mapping_count'))
        copied_apply_report = copied_apply_report or build_document_parse_copied_raw_page_filtering_apply_report(
            layout_analysis_report.get('pages', []),
            raw_object_pages_before,
            settings.get('_document_parse_mapping_dry_run_report') or
            layout_analysis_report.get('header_footer_exclusion_dry_run', {}),
            settings.get('_document_parse_filtering_review_decisions'),
            raw_object_mapping_report=mapping_report,
            enabled=True,
            expected_mapping_count=settings.get(
                '_document_parse_guarded_raw_apply_restore_expected_mapping_count'))

        snapshot = Pages._snapshot_raw_page_blocks(raw_pages)
        snapshot_created = True
        restore_completed = False
        removed_by_page = []
        apply_skipped_reason = ''
        try:
            if mapping_report.get('safety_warnings'):
                apply_skipped_reason = 'mapping_report_has_safety_warnings'
                raw_object_pages_during = raw_object_pages_before
            else:
                removed_by_page = Pages._apply_guarded_raw_page_filter(
                    pages,
                    raw_pages,
                    reviewed_raw_object_removal_plan(mapping_report))
                raw_object_pages_during = Pages._raw_object_mapping_pages(pages, raw_pages)
        finally:
            Pages._restore_raw_page_blocks(snapshot)
            restore_completed = True

        raw_object_pages_after = Pages._raw_object_mapping_pages(pages, raw_pages)
        return build_document_parse_guarded_raw_page_apply_restore_report(
            raw_object_pages_before,
            raw_object_pages_during,
            raw_object_pages_after,
            removed_by_page,
            raw_object_mapping_report=mapping_report,
            copied_apply_report=copied_apply_report,
            enabled=bool(settings.get('_document_parse_guarded_raw_apply_restore_enabled')),
            snapshot_created=snapshot_created,
            restore_completed=restore_completed,
            expected_mapping_count=settings.get(
                '_document_parse_guarded_raw_apply_restore_expected_mapping_count'),
            apply_skipped_reason=apply_skipped_reason)


    @staticmethod
    def _build_document_parse_filtered_parse_experiment_report(
            layout_analysis_report:dict,
            pages:list,
            raw_pages:list,
            raw_object_mapping_report:dict=None,
            copied_apply_report:dict=None,
            guarded_apply_restore_report:dict=None,
            **settings):
        layout_analysis_report = layout_analysis_report or {}
        raw_object_pages_before = Pages._raw_object_mapping_pages(pages, raw_pages)
        mapping_report = raw_object_mapping_report or build_document_parse_raw_object_mapping_report(
            layout_analysis_report.get('pages', []),
            raw_object_pages_before,
            settings.get('_document_parse_mapping_dry_run_report') or
            layout_analysis_report.get('header_footer_exclusion_dry_run', {}),
            settings.get('_document_parse_filtering_review_decisions'),
            enabled=True,
            expected_would_remove_count=settings.get(
                '_document_parse_filtered_parse_expected_mapping_count'))
        copied_apply_report = copied_apply_report or build_document_parse_copied_raw_page_filtering_apply_report(
            layout_analysis_report.get('pages', []),
            raw_object_pages_before,
            settings.get('_document_parse_mapping_dry_run_report') or
            layout_analysis_report.get('header_footer_exclusion_dry_run', {}),
            settings.get('_document_parse_filtering_review_decisions'),
            raw_object_mapping_report=mapping_report,
            enabled=True,
            expected_mapping_count=settings.get(
                '_document_parse_filtered_parse_expected_mapping_count'))

        baseline_metrics = Pages._collect_filtered_parse_experiment_metrics(
            pages,
            raw_pages,
            **settings)
        snapshot = Pages._snapshot_raw_page_blocks(raw_pages)
        restore_completed = False
        removed_by_page = []
        apply_skipped_reason = ''
        try:
            if mapping_report.get('safety_warnings'):
                apply_skipped_reason = 'mapping_report_has_safety_warnings'
                raw_object_pages_filtered = raw_object_pages_before
                filtered_metrics = baseline_metrics
            else:
                removed_by_page = Pages._apply_guarded_raw_page_filter(
                    pages,
                    raw_pages,
                    reviewed_raw_object_removal_plan(mapping_report))
                raw_object_pages_filtered = Pages._raw_object_mapping_pages(pages, raw_pages)
                filtered_metrics = Pages._collect_filtered_parse_experiment_metrics(
                    pages,
                    raw_pages,
                    **settings)
        finally:
            Pages._restore_raw_page_blocks(snapshot)
            restore_completed = True

        raw_object_pages_after = Pages._raw_object_mapping_pages(pages, raw_pages)
        restore_fingerprint_match = raw_object_pages_before == raw_object_pages_after
        return build_document_parse_filtered_parse_experiment_report(
            raw_object_pages_before,
            raw_object_pages_filtered,
            raw_object_pages_after,
            removed_by_page,
            baseline_metrics,
            filtered_metrics,
            raw_object_mapping_report=mapping_report,
            copied_apply_report=copied_apply_report,
            guarded_apply_restore_report=guarded_apply_restore_report,
            enabled=bool(settings.get('_document_parse_filtered_parse_experiment_enabled')),
            restore_completed=restore_completed,
            restore_fingerprint_match=restore_fingerprint_match,
            expected_mapping_count=settings.get(
                '_document_parse_filtered_parse_expected_mapping_count'),
            apply_skipped_reason=apply_skipped_reason)


    @staticmethod
    def _build_layout_analysis_report(pages:list, raw_pages:list, **settings):
        analysis_pages = Pages._layout_analysis_pages(pages, raw_pages)
        return build_layout_analysis_report(
            analysis_pages,
            min_pages=settings.get('layout_analysis_min_pages', 2),
            top_ratio=settings.get('layout_analysis_top_ratio', 0.15),
            bottom_ratio=settings.get('layout_analysis_bottom_ratio', 0.15))


    @staticmethod
    def _collect_filtered_parse_experiment_metrics(
            pages:list,
            raw_pages:list,
            **settings):
        '''Collect parse metrics from temporary downstream parse copies.'''
        raw_object_pages = Pages._raw_object_mapping_pages(pages, raw_pages)
        page_reports = []
        warnings = []
        parse_available = False

        for page, raw_page, raw_object_page in zip(pages, raw_pages, raw_object_pages):
            page_report = Pages._filtered_parse_raw_page_metrics(raw_object_page)
            parsed_metrics = Pages._filtered_parse_page_metrics(
                raw_page,
                page_index=page.id,
                **settings)
            page_report.update(parsed_metrics)
            if parsed_metrics.get('parse_metrics_available'):
                parse_available = True
            for warning in parsed_metrics.get('warnings', []) or []:
                warning = dict(warning)
                warning.setdefault('page_index', page.id)
                warning.setdefault('page_number', page.id + 1)
                warnings.append(warning)
            page_reports.append(page_report)

        return {
            'parse_metrics_available': parse_available,
            'raw_block_count': sum(page.get('raw_block_count', 0) for page in page_reports),
            'body_raw_block_count': sum(page.get('body_raw_block_count', 0) for page in page_reports),
            'parsed_text_block_count': sum(page.get('parsed_text_block_count', 0) for page in page_reports),
            'body_text_block_count': sum(page.get('body_text_block_count', 0) for page in page_reports),
            'paragraph_like_text_block_count': sum(
                page.get('paragraph_like_text_block_count', 0)
                for page in page_reports),
            'table_count': sum(page.get('table_count', 0) for page in page_reports),
            'image_count': sum(page.get('image_count', 0) for page in page_reports),
            'section_count': sum(page.get('section_count', 0) for page in page_reports),
            'tables': [
                table
                for page in page_reports
                for table in page.get('tables', []) or []
            ],
            'pages': page_reports,
            'warnings': warnings,
        }


    @staticmethod
    def _filtered_parse_raw_page_metrics(raw_object_page:dict):
        raw_objects = raw_object_page.get('raw_objects', []) or []
        return {
            'page_index': raw_object_page.get('page_index'),
            'page_number': raw_object_page.get('page_number', raw_object_page.get('page_index', 0) + 1),
            'raw_block_count': len(raw_objects),
            'body_raw_block_count': sum(
                1 for raw_object in raw_objects
                if (
                    raw_object.get('region') or
                    classify_y_band(
                        Pages._json_bbox(raw_object.get('bbox')),
                        raw_object_page.get('height', raw_object_page.get('page_height', 0)) or 1)
                ) == REGION_BODY),
        }


    @staticmethod
    def _filtered_parse_page_metrics(raw_page, page_index:int=None, **settings):
        metrics = {
            'parse_metrics_available': False,
            'parsed_text_block_count': 0,
            'body_text_block_count': 0,
            'paragraph_like_text_block_count': 0,
            'table_count': 0,
            'image_count': 0,
            'section_count': 0,
            'tables': [],
            'warnings': [],
        }
        if not hasattr(raw_page, 'calculate_margin') or not hasattr(raw_page, 'parse_section'):
            metrics['warnings'].append({
                'type': 'parse_adapter_unavailable',
                'message': 'Raw-page object does not expose calculate_margin/parse_section.',
            })
            return metrics

        original_blocks = getattr(raw_page, 'blocks', None)
        original_shapes = getattr(raw_page, 'shapes', None)
        had_margin = hasattr(raw_page, 'margin')
        original_margin = getattr(raw_page, 'margin', None)
        try:
            raw_page.blocks = Pages._copy_element_collection(original_blocks, raw_page)
            if original_shapes is not None:
                raw_page.shapes = Pages._copy_element_collection(original_shapes, raw_page)
            margin = raw_page.calculate_margin(**settings)
            raw_page.margin = margin
            sections = raw_page.parse_section(**settings) or []
            for section in sections:
                section.parse(**settings)
            metrics.update(Pages._parsed_sections_metrics(
                sections,
                raw_page.height,
                page_index=page_index))
            metrics['parse_metrics_available'] = True
        except Exception as exc:
            metrics['warnings'].append({
                'type': 'parse_metrics_failed',
                'message': f'{exc.__class__.__name__}: {exc}',
            })
        finally:
            raw_page.blocks = original_blocks
            if original_shapes is not None:
                raw_page.shapes = original_shapes
            if had_margin:
                raw_page.margin = original_margin
        return metrics


    @staticmethod
    def _copy_element_collection(collection, parent):
        if collection is None:
            return []

        try:
            copied = collection.__class__(parent=parent)
        except TypeError:
            copied = collection.__class__()
            if hasattr(copied, '_parent'):
                copied._parent = parent

        copied_instances = []
        for instance in collection:
            if hasattr(instance, 'copy'):
                copied_instance = instance.copy()
            else:
                copied_instance = copy.deepcopy(instance)
            if hasattr(copied_instance, 'parent'):
                copied_instance.parent = parent
            copied_instances.append(copied_instance)

        if hasattr(copied, '_instances'):
            copied._instances = copied_instances
        elif isinstance(copied, list):
            copied[:] = copied_instances
        else:
            copied = copied_instances

        if hasattr(copied, '_floating_image_blocks') and hasattr(collection, 'floating_image_blocks'):
            copied._floating_image_blocks = [
                item.copy() if hasattr(item, 'copy') else copy.deepcopy(item)
                for item in collection.floating_image_blocks
            ]
        return copied


    @staticmethod
    def _parsed_sections_metrics(sections:list, page_height:float, page_index:int=None):
        metrics = {
            'parsed_text_block_count': 0,
            'body_text_block_count': 0,
            'paragraph_like_text_block_count': 0,
            'table_count': 0,
            'image_count': 0,
            'section_count': len(sections or []),
            'tables': [],
        }
        for block in Pages._walk_parsed_blocks(sections):
            if getattr(block, 'is_table_block', False):
                metrics['table_count'] += 1
                metrics['tables'].append(Pages._parsed_table_record(
                    block,
                    page_height,
                    page_index=page_index,
                    table_index=len(metrics['tables'])))
                continue
            if getattr(block, 'is_image_block', False):
                metrics['image_count'] += 1
            if getattr(block, 'is_text_image_block', False):
                metrics['parsed_text_block_count'] += 1
                metrics['paragraph_like_text_block_count'] += 1
                if classify_y_band(Pages._json_bbox(getattr(block, 'bbox', None)), page_height) == REGION_BODY:
                    metrics['body_text_block_count'] += 1
        return metrics


    @staticmethod
    def _parsed_table_record(table, page_height:float, page_index:int=None, table_index:int=0):
        rows = list(table)
        cells = [
            cell
            for row in rows
            for cell in row
        ]
        bbox = Pages._json_bbox(getattr(table, 'bbox', None))
        return {
            'table_id': f'page-{page_index}-table-{table_index}',
            'page_index': page_index,
            'page_number': page_index + 1 if page_index is not None else None,
            'table_index': table_index,
            'bbox': bbox,
            'region': classify_y_band(bbox, page_height) if page_height else '',
            'row_count': getattr(table, 'num_rows', len(rows)),
            'column_count': getattr(table, 'num_cols', 0),
            'cell_count': len(cells),
            'non_empty_cell_count': sum(1 for cell in cells if bool(cell)),
            'table_type': (
                'stream' if getattr(table, 'is_stream_table_block', False) else
                'lattice' if getattr(table, 'is_lattice_table_block', False) else
                ''),
            'cell_summaries': Pages._table_cell_summaries(rows),
            'cell_text_signature': Pages._table_cell_text_signature(rows),
            'cell_bbox_signature': Pages._table_cell_bbox_signature(rows),
            'text_preview': Pages._table_text_preview(table),
        }


    @staticmethod
    def _table_cell_summaries(rows:list):
        cells = []
        for row_index, row in enumerate(rows or []):
            for column_index, cell in enumerate(row):
                if not cell:
                    cells.append({
                        'row_index': row_index,
                        'column_index': column_index,
                        'bbox': [0.0, 0.0, 0.0, 0.0],
                        'text_preview': '',
                        'empty': True,
                    })
                    continue
                cells.append({
                    'row_index': row_index,
                    'column_index': column_index,
                    'bbox': Pages._json_bbox(getattr(cell, 'bbox', None)),
                    'text_preview': Pages._normalize_table_text(getattr(cell, 'text', '')),
                    'empty': False,
                })
        return cells


    @staticmethod
    def _table_cell_text_signature(rows:list):
        return [
            cell.get('text_preview', '')
            for cell in Pages._table_cell_summaries(rows)
        ]


    @staticmethod
    def _table_cell_bbox_signature(rows:list):
        return [
            cell.get('bbox', [0.0, 0.0, 0.0, 0.0])
            for cell in Pages._table_cell_summaries(rows)
        ]


    @staticmethod
    def _table_text_preview(table, max_length:int=80):
        try:
            rows = table.text
        except Exception:
            return ''

        parts = []
        for row in rows or []:
            if isinstance(row, (list, tuple)):
                parts.extend(str(item or '') for item in row)
            else:
                parts.append(str(row or ''))
        text = ' '.join(part.strip() for part in parts if part and part.strip())
        text = ' '.join(text.split())
        if len(text) <= max_length:
            return text
        return text[:max_length-3].rstrip() + '...'


    @staticmethod
    def _normalize_table_text(text, max_length:int=80):
        if text is None:
            return ''
        if isinstance(text, list):
            text = ' '.join(str(item or '') for item in text)
        text = ' '.join(str(text).split())
        if len(text) <= max_length:
            return text
        return text[:max_length-3].rstrip() + '...'


    @staticmethod
    def _walk_parsed_blocks(sections:list):
        for section in sections or []:
            for column in section:
                for block in column.blocks:
                    yield block
                    if getattr(block, 'is_table_block', False):
                        for nested in Pages._walk_table_blocks(block):
                            yield nested


    @staticmethod
    def _walk_table_blocks(table_block):
        try:
            rows = list(table_block)
        except TypeError:
            return
        for row in rows:
            for cell in row:
                for block in cell.blocks:
                    yield block
                    if getattr(block, 'is_table_block', False):
                        for nested in Pages._walk_table_blocks(block):
                            yield nested


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
    def _raw_object_mapping_pages(pages:list, raw_pages:list):
        raw_object_pages = []
        for page, raw_page in zip(pages, raw_pages):
            raw_object_pages.append({
                'page_index': page.id,
                'width': raw_page.width,
                'height': raw_page.height,
                'raw_objects': [
                    Pages._raw_object_mapping_block(page.id, index, block)
                    for index, block in enumerate(raw_page.blocks)
                ],
            })
        return raw_object_pages


    @staticmethod
    def _raw_object_mapping_block(page_index:int, object_index:int, block):
        return {
            'raw_object_id': f'page-{page_index}-raw-block-{object_index}',
            'object_index': object_index,
            'block_index': object_index,
            'object_type': block.__class__.__name__,
            'text': getattr(block, 'text', ''),
            'bbox': Pages._json_bbox(getattr(block, 'bbox', None)),
            'style': Pages._layout_analysis_style(block),
        }


    @staticmethod
    def _snapshot_raw_page_blocks(raw_pages:list):
        return [
            {
                'raw_page': raw_page,
                'blocks': list(raw_page.blocks),
            }
            for raw_page in raw_pages or []
        ]


    @staticmethod
    def _restore_raw_page_blocks(snapshot:list):
        for item in snapshot or []:
            Pages._reset_raw_page_blocks(
                item.get('raw_page'),
                item.get('blocks', []))


    @staticmethod
    def _apply_guarded_raw_page_filter(pages:list, raw_pages:list, removal_plan:list):
        remove_by_key = {
            (item.get('page_index'), item.get('raw_object_id')): item
            for item in removal_plan or []
        }
        removed_by_page = []
        for page, raw_page in zip(pages or [], raw_pages or []):
            kept_blocks = []
            removed_objects = []
            for index, block in enumerate(raw_page.blocks):
                raw_object = Pages._raw_object_mapping_block(page.id, index, block)
                plan_item = remove_by_key.get((page.id, raw_object.get('raw_object_id')))
                if plan_item:
                    raw_object.update({
                        'candidate_id': plan_item.get('candidate_id', ''),
                        'proposed_role': plan_item.get('proposed_role', ''),
                        'fingerprint': plan_item.get('fingerprint', ''),
                        'region': plan_item.get('region', ''),
                        'mapping_status': plan_item.get('mapping_status', ''),
                        'removal_reason': 'guarded_apply_restore_experiment',
                    })
                    removed_objects.append(raw_object)
                    continue
                kept_blocks.append(block)

            Pages._reset_raw_page_blocks(raw_page, kept_blocks)
            removed_by_page.append({
                'page_index': page.id,
                'page_number': page.id + 1,
                'removed_count': len(removed_objects),
                'objects': removed_objects,
            })

        return removed_by_page


    @staticmethod
    def _reset_raw_page_blocks(raw_page, blocks:list):
        if hasattr(raw_page.blocks, '_instances'):
            # Preserve exact object identity/count; reset() may skip falsey bbox objects.
            raw_page.blocks._instances = list(blocks)
        elif isinstance(raw_page.blocks, list):
            raw_page.blocks[:] = list(blocks)
        else:
            raw_page.blocks = list(blocks)


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
