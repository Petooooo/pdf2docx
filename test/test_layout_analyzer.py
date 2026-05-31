import json
import unittest
from importlib import util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / 'pdf2docx' / 'page' / 'LayoutAnalyzer.py'
SPEC = util.spec_from_file_location('LayoutAnalyzer', MODULE_PATH)
LayoutAnalyzer = util.module_from_spec(SPEC)
# Load the pure helper directly so these tests do not need PyMuPDF.
SPEC.loader.exec_module(LayoutAnalyzer)

PAGE_NUMBER_PLACEHOLDER = LayoutAnalyzer.PAGE_NUMBER_PLACEHOLDER
REGION_BODY = LayoutAnalyzer.REGION_BODY
REGION_BOTTOM = LayoutAnalyzer.REGION_BOTTOM
REGION_TOP = LayoutAnalyzer.REGION_TOP
IMAGE_PLACEHOLDER = LayoutAnalyzer.IMAGE_PLACEHOLDER
ACTION_KEEP = LayoutAnalyzer.ACTION_KEEP
ACTION_REVIEW = LayoutAnalyzer.ACTION_REVIEW
ACTION_WOULD_EXCLUDE = LayoutAnalyzer.ACTION_WOULD_EXCLUDE
ROLE_FOOTER = LayoutAnalyzer.ROLE_FOOTER
ROLE_HEADER = LayoutAnalyzer.ROLE_HEADER
ROLE_KEEP_BODY = LayoutAnalyzer.ROLE_KEEP_BODY
ROLE_LAYOUT_PLACEHOLDER = LayoutAnalyzer.ROLE_LAYOUT_PLACEHOLDER
ROLE_PAGE_NUMBER = LayoutAnalyzer.ROLE_PAGE_NUMBER
classify_y_band = LayoutAnalyzer.classify_y_band
find_repeated_text_candidates = LayoutAnalyzer.find_repeated_text_candidates
build_header_footer_exclusion_dry_run = LayoutAnalyzer.build_header_footer_exclusion_dry_run
build_body_filtering_diff_report = LayoutAnalyzer.build_body_filtering_diff_report
build_document_parse_filtering_hook_report = LayoutAnalyzer.build_document_parse_filtering_hook_report
build_document_parse_raw_object_mapping_report = LayoutAnalyzer.build_document_parse_raw_object_mapping_report
build_document_parse_filtering_simulation_report = LayoutAnalyzer.build_document_parse_filtering_simulation_report
build_filter_insertion_point_analysis_report = LayoutAnalyzer.build_filter_insertion_point_analysis_report
build_indentation_rule_comparison_report = LayoutAnalyzer.build_indentation_rule_comparison_report
build_paragraph_integrity_report = LayoutAnalyzer.build_paragraph_integrity_report
build_paragraph_mismatch_analysis_report = LayoutAnalyzer.build_paragraph_mismatch_analysis_report
build_paragraph_production_comparison_report = LayoutAnalyzer.build_paragraph_production_comparison_report
build_paragraph_reconstruction_validation_report = LayoutAnalyzer.build_paragraph_reconstruction_validation_report
build_reviewed_header_footer_filter_report = LayoutAnalyzer.build_reviewed_header_footer_filter_report
build_layout_analysis_report = LayoutAnalyzer.build_layout_analysis_report
find_paragraph_continuation_candidates = LayoutAnalyzer.find_paragraph_continuation_candidates
make_text_fingerprint = LayoutAnalyzer.make_text_fingerprint
normalize_page_number = LayoutAnalyzer.normalize_page_number
normalize_text = LayoutAnalyzer.normalize_text
parse_exclusion_review_markdown = LayoutAnalyzer.parse_exclusion_review_markdown
text_block_records = LayoutAnalyzer.text_block_records

try:
    from pdf2docx.page.Pages import Pages
except Exception:
    Pages = None


class TestLayoutAnalyzer(unittest.TestCase):

    def test_normalize_text_collapses_whitespace(self):
        self.assertEqual(normalize_text('  Annual\n   Report\t2026  '), 'Annual Report 2026')
        self.assertEqual(normalize_text(None), '')

    def test_normalize_page_number_replaces_simple_page_number(self):
        for text in ['1', 'Page 2', 'p. 3', '4 / 10', 'Page 5 of 12', '- 6 -']:
            with self.subTest(text=text):
                self.assertEqual(normalize_page_number(text), PAGE_NUMBER_PLACEHOLDER)

    def test_normalize_page_number_keeps_non_page_number_text(self):
        self.assertEqual(normalize_page_number('Chapter 3'), 'Chapter 3')
        self.assertEqual(normalize_page_number('Section 1 Introduction'), 'Section 1 Introduction')

    def test_make_text_fingerprint_uses_normalized_page_number_and_band(self):
        fingerprint = make_text_fingerprint(' Page 7 ', y_band='Bottom')

        self.assertEqual(fingerprint, {
            'text': PAGE_NUMBER_PLACEHOLDER.lower(),
            'y_band': 'bottom',
            'style': '',
            'key': f'{PAGE_NUMBER_PLACEHOLDER.lower()}||bottom',
        })

    def test_classify_y_band_uses_page_height_ratios(self):
        self.assertEqual(classify_y_band([0, 10, 100, 30], page_height=1000), REGION_TOP)
        self.assertEqual(classify_y_band([0, 300, 100, 330], page_height=1000), REGION_BODY)
        self.assertEqual(classify_y_band([0, 950, 100, 980], page_height=1000), REGION_BOTTOM)

    def test_classify_y_band_rejects_invalid_ratios(self):
        with self.assertRaises(ValueError):
            classify_y_band([0, 10, 100, 30], page_height=1000, top_ratio=0.6, bottom_ratio=0.4)

    def test_text_block_records_are_json_serializable(self):
        records = text_block_records([
            {
                'page_index': 0,
                'height': 1000,
                'blocks': [
                    {'text': 'Annual Report', 'bbox': (50, 20, 300, 40), 'font': 'Arial', 'size': 10.0},
                    {'text': 'Body text', 'bbox': (50, 300, 500, 330)},
                ],
            },
        ])

        self.assertEqual(records[0]['region'], REGION_TOP)
        self.assertEqual(records[0]['bbox'], [50.0, 20.0, 300.0, 40.0])
        json.dumps(records)

    def test_find_repeated_text_candidates_clusters_top_and_bottom_text_only_by_default(self):
        pages = [
            {
                'page_index': 0,
                'height': 1000,
                'blocks': [
                    {'text': 'Annual Report', 'bbox': [50, 20, 300, 40]},
                    {'text': 'Repeated body line', 'bbox': [50, 300, 500, 330]},
                    {'text': 'Page 1', 'bbox': [260, 960, 310, 980]},
                ],
            },
            {
                'page_index': 1,
                'height': 1000,
                'blocks': [
                    {'text': 'Annual Report', 'bbox': [50, 22, 300, 42]},
                    {'text': 'Repeated body line', 'bbox': [50, 310, 500, 340]},
                    {'text': 'Page 2', 'bbox': [260, 960, 310, 980]},
                ],
            },
            {
                'page_index': 2,
                'height': 1000,
                'blocks': [
                    {'text': 'Annual Report', 'bbox': [50, 19, 300, 39]},
                    {'text': 'Repeated body line', 'bbox': [50, 320, 500, 350]},
                    {'text': 'Page 3', 'bbox': [260, 960, 310, 980]},
                ],
            },
        ]

        candidates = find_repeated_text_candidates(pages)
        by_text = {candidate['text']: candidate for candidate in candidates}

        self.assertIn('annual report', by_text)
        self.assertIn(PAGE_NUMBER_PLACEHOLDER.lower(), by_text)
        self.assertNotIn('repeated body line', by_text)
        self.assertEqual(by_text['annual report']['pages'], [0, 1, 2])
        self.assertEqual(by_text['annual report']['confidence'], 1.0)
        self.assertEqual(by_text['annual report']['signals']['support_pages'], 3)
        self.assertEqual(by_text[PAGE_NUMBER_PLACEHOLDER.lower()]['regions'], [REGION_BOTTOM])
        json.dumps(candidates)

    def test_build_layout_analysis_report_contains_page_summary_and_candidates(self):
        pages = [
            {
                'page_index': 0,
                'width': 600,
                'height': 1000,
                'blocks': [
                    {'text': 'Annual Report', 'bbox': [50, 20, 300, 40]},
                    {'text': 'First body paragraph', 'bbox': [50, 300, 500, 330]},
                    {'text': 'Page 1', 'bbox': [260, 960, 310, 980]},
                ],
            },
            {
                'page_index': 1,
                'width': 600,
                'height': 1000,
                'blocks': [
                    {'text': 'Annual Report', 'bbox': [50, 20, 300, 40]},
                    {'text': 'Second body paragraph', 'bbox': [50, 300, 500, 330]},
                    {'text': 'Page 2', 'bbox': [260, 960, 310, 980]},
                ],
            },
        ]

        report = build_layout_analysis_report(pages)
        by_text = {candidate['text']: candidate for candidate in report['repeated_text_candidates']}

        self.assertEqual(report['page_count'], 2)
        self.assertEqual(report['pages'][0]['region_counts'][REGION_TOP], 1)
        self.assertEqual(report['pages'][0]['region_counts'][REGION_BODY], 1)
        self.assertEqual(report['pages'][0]['region_counts'][REGION_BOTTOM], 1)
        self.assertIn('First body paragraph', report['pages'][0]['text'])
        self.assertIn('annual report', by_text)
        self.assertIn(PAGE_NUMBER_PLACEHOLDER.lower(), by_text)
        self.assertEqual(report['signals']['repeated_text_candidate_count'], 2)
        self.assertIn('paragraph_continuation_candidates', report)
        json.dumps(report)

    def test_paragraph_continuation_candidate_when_text_runs_across_pages(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('This paragraph starts on one page and continues', 50, 805, 520, 835),
            ]),
            _page(1, [
                _block('with the same sentence on the next page.', 50, 170, 520, 200),
            ]),
        ])
        candidate = report['paragraph_continuation_candidates'][0]

        self.assertEqual(candidate['label'], 'candidate')
        self.assertGreaterEqual(candidate['score'], 0.65)
        self.assertIn('previous_text_open_ended', candidate['positive_signals'])
        self.assertIn('previous_near_body_bottom', candidate['positive_signals'])
        self.assertIn('next_near_body_top', candidate['positive_signals'])

    def test_paragraph_continuation_unlikely_after_sentence_end(self):
        candidates = find_paragraph_continuation_candidates(build_layout_analysis_report([
            _page(0, [
                _block('This paragraph clearly ends here.', 50, 805, 520, 835),
            ]),
            _page(1, [
                _block('A new paragraph starts on the next page.', 50, 170, 520, 200),
            ]),
        ])['pages'])
        candidate = candidates[0]

        self.assertEqual(candidate['label'], 'unlikely')
        self.assertIn('previous_strong_sentence_end', candidate['negative_signals'])

    def test_paragraph_continuation_hyphenated_split_is_strong_candidate(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('The policy applies to inter-', 50, 805, 520, 835),
            ]),
            _page(1, [
                _block('national transactions recorded later', 50, 170, 520, 200),
            ]),
        ])
        candidate = report['paragraph_continuation_candidates'][0]

        self.assertEqual(candidate['label'], 'candidate')
        self.assertIn('previous_hyphenated_word', candidate['positive_signals'])
        self.assertIn('Hyphenated page break', candidate['reason'])

    def test_paragraph_continuation_unlikely_when_next_block_looks_like_heading(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('The preceding discussion continues without punctuation', 50, 805, 520, 835),
            ]),
            _page(1, [
                _block('CHAPTER TWO', 50, 170, 250, 200),
            ]),
        ])
        candidate = report['paragraph_continuation_candidates'][0]

        self.assertEqual(candidate['label'], 'unlikely')
        self.assertIn('next_looks_like_heading', candidate['negative_signals'])

    def test_paragraph_continuation_unlikely_for_footer_to_header_only(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Page 1', 270, 955, 330, 980),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 45),
            ]),
        ])
        candidate = report['paragraph_continuation_candidates'][0]

        self.assertEqual(candidate['label'], 'unlikely')
        self.assertEqual(candidate['previous_text_preview'], '')
        self.assertEqual(candidate['next_text_preview'], '')
        self.assertIn('no_previous_body_block', candidate['negative_signals'])
        self.assertIn('no_next_body_block', candidate['negative_signals'])

    def test_short_text_does_not_become_strong_continuation_evidence(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Note', 50, 805, 520, 835),
            ]),
            _page(1, [
                _block('x', 50, 170, 520, 200),
            ]),
        ])
        candidate = report['paragraph_continuation_candidates'][0]

        self.assertEqual(candidate['label'], 'unlikely')
        self.assertIn('previous_short_text', candidate['negative_signals'])
        self.assertIn('next_short_text', candidate['negative_signals'])
        self.assertIn('too short', candidate['reason'])

    def test_page_number_placeholder_is_not_normal_body_continuation_text(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Page 1', 50, 805, 520, 835),
            ]),
            _page(1, [
                _block('continued body text with matching layout', 50, 170, 520, 200),
            ]),
        ])
        candidate = report['paragraph_continuation_candidates'][0]

        self.assertEqual(candidate['label'], 'unlikely')
        self.assertIn('previous_placeholder_text', candidate['negative_signals'])
        self.assertIn('placeholder-like', candidate['reason'])

    def test_image_placeholder_is_reported_but_not_strong_semantic_repeated_text(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block(IMAGE_PLACEHOLDER, 50, 20, 120, 40),
                _block('Body paragraph one.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block(IMAGE_PLACEHOLDER, 50, 20, 120, 40),
                _block('Body paragraph two.', 50, 300, 520, 330),
            ]),
            _page(2, [
                _block(IMAGE_PLACEHOLDER, 50, 20, 120, 40),
                _block('Body paragraph three.', 50, 300, 520, 330),
            ]),
        ])
        by_text = {candidate['text']: candidate for candidate in report['repeated_text_candidates']}
        candidate = by_text[IMAGE_PLACEHOLDER.lower()]

        self.assertEqual(candidate['confidence'], 1.0)
        self.assertLess(candidate['semantic_confidence'], candidate['confidence'])
        self.assertEqual(candidate['confidence_label'], 'placeholder')
        self.assertEqual(candidate['signals']['text_quality']['placeholder_kind'], 'image')

    def test_two_page_repeated_cluster_is_more_cautious_than_all_page_header(self):
        pages = [
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Boundary Note', 50, 955, 300, 980),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Boundary Note', 50, 955, 300, 980),
            ]),
            _page(2, [
                _block('Annual Report', 50, 20, 300, 40),
            ]),
            _page(3, [
                _block('Annual Report', 50, 20, 300, 40),
            ]),
        ]
        report = build_layout_analysis_report(pages)
        by_text = {candidate['text']: candidate for candidate in report['repeated_text_candidates']}

        self.assertGreater(
            by_text['annual report']['semantic_confidence'],
            by_text['boundary note']['semantic_confidence'])
        self.assertEqual(by_text['annual report']['confidence_label'], 'strong')
        self.assertEqual(by_text['boundary note']['confidence_label'], 'cautious')
        self.assertEqual(by_text['boundary note']['signals']['support_level'], 'low')

    def test_continuation_avoids_likely_repeated_header_footer_blocks(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Running Footer', 50, 960, 300, 980),
                _block('The paragraph continues across pages', 50, 805, 520, 835),
                _block('Running Footer', 50, 830, 300, 850),
            ]),
            _page(1, [
                _block('Running Footer', 50, 20, 300, 40),
                _block('Running Footer', 50, 170, 300, 190),
                _block('on the next page with matching text', 50, 205, 520, 235),
                _block('Running Footer', 50, 960, 300, 980),
            ]),
            _page(2, [
                _block('Running Footer', 50, 20, 300, 40),
                _block('Another body paragraph.', 50, 300, 520, 330),
                _block('Running Footer', 50, 960, 300, 980),
            ]),
        ])
        candidate = report['paragraph_continuation_candidates'][0]

        self.assertEqual(
            candidate['previous_text_preview'],
            'The paragraph continues across pages')
        self.assertEqual(
            candidate['next_text_preview'],
            'on the next page with matching text')

    def test_dry_run_marks_strong_all_page_top_text_as_header_candidate(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body one.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body two.', 50, 300, 520, 330),
            ]),
            _page(2, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body three.', 50, 300, 520, 330),
            ]),
        ])
        dry_run = _dry_run_by_fingerprint(report)
        candidate = dry_run['annual report||top']

        self.assertEqual(candidate['action'], ACTION_WOULD_EXCLUDE)
        self.assertEqual(candidate['proposed_role'], ROLE_HEADER)
        self.assertIn('top_region', candidate['positive_signals'])

    def test_dry_run_marks_strong_all_page_bottom_text_as_footer_candidate(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Body one.', 50, 300, 520, 330),
                _block('Confidential Footer', 50, 960, 300, 980),
            ]),
            _page(1, [
                _block('Body two.', 50, 300, 520, 330),
                _block('Confidential Footer', 50, 960, 300, 980),
            ]),
            _page(2, [
                _block('Body three.', 50, 300, 520, 330),
                _block('Confidential Footer', 50, 960, 300, 980),
            ]),
        ])
        dry_run = _dry_run_by_fingerprint(report)
        candidate = dry_run['confidential footer||bottom']

        self.assertEqual(candidate['action'], ACTION_WOULD_EXCLUDE)
        self.assertEqual(candidate['proposed_role'], ROLE_FOOTER)
        self.assertIn('bottom_region', candidate['positive_signals'])

    def test_dry_run_marks_page_number_placeholder_as_page_number_candidate(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Body one.', 50, 300, 520, 330),
                _block('Page 1', 270, 960, 330, 980),
            ]),
            _page(1, [
                _block('Body two.', 50, 300, 520, 330),
                _block('Page 2', 270, 960, 330, 980),
            ]),
            _page(2, [
                _block('Body three.', 50, 300, 520, 330),
                _block('Page 3', 270, 960, 330, 980),
            ]),
        ])
        dry_run = _dry_run_by_fingerprint(report)
        candidate = dry_run[f'{PAGE_NUMBER_PLACEHOLDER.lower()}||bottom']

        self.assertEqual(candidate['action'], ACTION_WOULD_EXCLUDE)
        self.assertEqual(candidate['proposed_role'], ROLE_PAGE_NUMBER)
        self.assertNotEqual(candidate['proposed_role'], ROLE_KEEP_BODY)
        self.assertIn('page_number_placeholder', candidate['positive_signals'])

    def test_dry_run_marks_image_placeholder_as_review_layout_signal(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block(IMAGE_PLACEHOLDER, 50, 20, 120, 40),
                _block('Body one.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block(IMAGE_PLACEHOLDER, 50, 20, 120, 40),
                _block('Body two.', 50, 300, 520, 330),
            ]),
            _page(2, [
                _block(IMAGE_PLACEHOLDER, 50, 20, 120, 40),
                _block('Body three.', 50, 300, 520, 330),
            ]),
        ])
        dry_run = _dry_run_by_fingerprint(report)
        candidate = dry_run[f'{IMAGE_PLACEHOLDER.lower()}||top']

        self.assertEqual(candidate['action'], ACTION_REVIEW)
        self.assertEqual(candidate['proposed_role'], ROLE_LAYOUT_PLACEHOLDER)
        self.assertIn('placeholder_not_semantic_text', candidate['negative_signals'])

    def test_dry_run_keeps_two_page_cautious_cluster_out_of_automatic_exclusion(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Boundary Note', 50, 960, 300, 980),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Boundary Note', 50, 960, 300, 980),
            ]),
            _page(2, [
                _block('Annual Report', 50, 20, 300, 40),
            ]),
            _page(3, [
                _block('Annual Report', 50, 20, 300, 40),
            ]),
        ])
        dry_run = _dry_run_by_fingerprint(report)
        candidate = dry_run['boundary note||bottom']

        self.assertEqual(candidate['action'], ACTION_REVIEW)
        self.assertNotEqual(candidate['action'], ACTION_WOULD_EXCLUDE)
        self.assertIn('low_support', candidate['negative_signals'])

    def test_dry_run_keeps_body_region_repetition_as_body_content(self):
        pages = [
            _page(0, [
                _block('Repeated Body Line', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block('Repeated Body Line', 50, 310, 520, 340),
            ]),
            _page(2, [
                _block('Repeated Body Line', 50, 320, 520, 350),
            ]),
        ]
        repeated = find_repeated_text_candidates(pages, regions=(REGION_BODY,))
        dry_run = build_header_footer_exclusion_dry_run(repeated, page_count=3)
        candidate = dry_run['candidates'][0]

        self.assertEqual(candidate['action'], ACTION_KEEP)
        self.assertEqual(candidate['proposed_role'], ROLE_KEEP_BODY)
        self.assertIn('body_region_repetition', candidate['negative_signals'])

    def test_dry_run_does_not_mutate_input_blocks(self):
        pages = [
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body one.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body two.', 50, 300, 520, 330),
            ]),
        ]
        before = json.loads(json.dumps(pages))

        build_layout_analysis_report(pages)

        self.assertEqual(pages, before)

    def test_parse_exclusion_review_markdown_counts_manual_decisions(self):
        decisions = parse_exclusion_review_markdown('\n'.join([
            '### repeated-1 | header | would_exclude',
            '- fingerprint: `annual report||top`',
            '- human_decision: approve_exclude: [x]    reject_exclude: [ ]    unsure: [ ]',
            '### repeated-2 | review_only | review',
            '- fingerprint: `body note||bottom`',
            '- human_decision: approve_exclude: [ ]    reject_exclude: [X]    unsure: [ ]',
            '### repeated-3 | layout_placeholder | review',
            '- fingerprint: `<image>||top`',
            '- human_decision: approve_exclude: [ ]    reject_exclude: [ ]    unsure: [x]',
        ]))

        self.assertEqual(decisions['summary']['decision_counts'], {
            'approve_exclude': 1,
            'reject_exclude': 1,
            'unsure': 1,
        })
        self.assertEqual(decisions['decisions'][0]['fingerprint'], 'annual report||top')

    def test_reviewed_filter_removes_approved_candidate_only_when_opted_in(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph one.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph two.', 50, 300, 520, 330),
            ]),
            _page(2, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph three.', 50, 300, 520, 330),
            ]),
        ])
        decisions = parse_exclusion_review_markdown(_review_markdown(
            'repeated-1',
            'annual report||top',
            'header',
            'would_exclude',
            'approve_exclude'))

        disabled = build_reviewed_header_footer_filter_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions)
        dry_run = build_reviewed_header_footer_filter_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True)
        applied = build_reviewed_header_footer_filter_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True,
            apply=True)

        self.assertFalse(disabled['enabled'])
        self.assertEqual(disabled['summary']['removed_block_count'], 0)
        self.assertEqual(disabled['summary']['would_remove_block_count'], 0)
        self.assertEqual(dry_run['summary']['would_remove_block_count'], 3)
        self.assertEqual(dry_run['summary']['removed_block_count'], 0)
        self.assertEqual(applied['summary']['removed_block_count'], 3)
        self.assertEqual(applied['summary']['kept_block_count'], 3)
        self.assertNotIn('Annual Report', applied['filtered_pages'][0]['text'])

    def test_reviewed_filter_does_not_remove_rejected_or_unsure_candidates(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Confidential Footer', 50, 960, 300, 980),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Confidential Footer', 50, 960, 300, 980),
            ]),
            _page(2, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Confidential Footer', 50, 960, 300, 980),
            ]),
        ])
        decisions = parse_exclusion_review_markdown('\n'.join([
            _review_markdown(
                'repeated-1',
                'annual report||top',
                'header',
                'would_exclude',
                'reject_exclude'),
            _review_markdown(
                'repeated-2',
                'confidential footer||bottom',
                'footer',
                'would_exclude',
                'unsure'),
        ]))

        applied = build_reviewed_header_footer_filter_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True,
            apply=True)

        self.assertEqual(applied['approved_candidate_count'], 0)
        self.assertEqual(applied['summary']['removed_block_count'], 0)
        self.assertEqual(applied['summary']['kept_block_count'], 6)

    def test_reviewed_filter_does_not_consume_raw_would_exclude_without_approval(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
            ]),
            _page(2, [
                _block('Annual Report', 50, 20, 300, 40),
            ]),
        ])

        applied = build_reviewed_header_footer_filter_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            review_decisions=[],
            enabled=True,
            apply=True)

        self.assertEqual(applied['approved_candidate_count'], 0)
        self.assertEqual(applied['summary']['removed_block_count'], 0)
        self.assertEqual(applied['summary']['kept_block_count'], 3)

    def test_reviewed_filter_does_not_remove_layout_placeholder_even_if_approved(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block(IMAGE_PLACEHOLDER, 50, 20, 120, 40),
                _block('Body paragraph one.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block(IMAGE_PLACEHOLDER, 50, 20, 120, 40),
                _block('Body paragraph two.', 50, 300, 520, 330),
            ]),
            _page(2, [
                _block(IMAGE_PLACEHOLDER, 50, 20, 120, 40),
                _block('Body paragraph three.', 50, 300, 520, 330),
            ]),
        ])
        decisions = parse_exclusion_review_markdown(_review_markdown(
            'repeated-1',
            f'{IMAGE_PLACEHOLDER.lower()}||top',
            'layout_placeholder',
            'review',
            'approve_exclude'))

        applied = build_reviewed_header_footer_filter_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True,
            apply=True)

        self.assertEqual(applied['approved_candidate_count'], 0)
        self.assertEqual(applied['summary']['removed_block_count'], 0)
        self.assertIn(
            'dry_run_action_not_would_exclude',
            {item['reason'] for item in applied['blocked_candidates']})

    def test_reviewed_filter_default_does_not_mutate_page_summaries(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('More body text.', 50, 300, 520, 330),
            ]),
        ])
        before = json.loads(json.dumps(report['pages']))
        decisions = parse_exclusion_review_markdown(_review_markdown(
            'repeated-1',
            'annual report||top',
            'header',
            'would_exclude',
            'approve_exclude'))

        build_reviewed_header_footer_filter_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions)

        self.assertEqual(report['pages'], before)

    def test_reviewed_filter_report_includes_removed_and_kept_counts(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Page 1', 270, 960, 330, 980),
                _block('Body paragraph one.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block('Page 2', 270, 960, 330, 980),
                _block('Body paragraph two.', 50, 300, 520, 330),
            ]),
        ])
        decisions = parse_exclusion_review_markdown(_review_markdown(
            'repeated-1',
            f'{PAGE_NUMBER_PLACEHOLDER.lower()}||bottom',
            'page_number',
            'would_exclude',
            'approve_exclude'))

        applied = build_reviewed_header_footer_filter_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True,
            apply=True)

        self.assertEqual(applied['summary']['original_block_count'], 4)
        self.assertEqual(applied['summary']['would_remove_block_count'], 2)
        self.assertEqual(applied['summary']['removed_block_count'], 2)
        self.assertEqual(applied['summary']['kept_block_count'], 2)

    def test_body_filtering_diff_report_includes_removed_and_kept_counts(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph one.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph two.', 50, 300, 520, 330),
            ]),
            _page(2, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph three.', 50, 300, 520, 330),
            ]),
        ])
        decisions = parse_exclusion_review_markdown(_review_markdown(
            'repeated-1',
            'annual report||top',
            'header',
            'would_exclude',
            'approve_exclude'))

        diff = build_body_filtering_diff_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True)

        self.assertEqual(diff['summary']['original_block_count'], 6)
        self.assertEqual(diff['summary']['would_remove_block_count'], 3)
        self.assertEqual(diff['summary']['kept_block_count'], 3)
        self.assertEqual(
            sum(page['removed_count'] for page in diff['removed_blocks_by_page']),
            3)

    def test_body_filtering_diff_groups_removed_blocks_by_approved_candidate(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Confidential Footer', 50, 960, 300, 980),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Confidential Footer', 50, 960, 300, 980),
            ]),
            _page(2, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Confidential Footer', 50, 960, 300, 980),
            ]),
        ])
        decisions = parse_exclusion_review_markdown('\n'.join([
            _review_markdown(
                'repeated-1',
                'annual report||top',
                'header',
                'would_exclude',
                'approve_exclude'),
            _review_markdown(
                'repeated-2',
                'confidential footer||bottom',
                'footer',
                'would_exclude',
                'approve_exclude'),
        ]))

        diff = build_body_filtering_diff_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True)
        grouped = {
            item['fingerprint']: item
            for item in diff['removed_blocks_by_candidate']
        }

        self.assertEqual(grouped['annual report||top']['removed_count'], 3)
        self.assertEqual(grouped['confidential footer||bottom']['removed_count'], 3)

    def test_body_filtering_diff_keeps_rejected_unsure_and_placeholders(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Confidential Footer', 50, 960, 300, 980),
                _block(IMAGE_PLACEHOLDER, 50, 60, 120, 80),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Confidential Footer', 50, 960, 300, 980),
                _block(IMAGE_PLACEHOLDER, 50, 60, 120, 80),
            ]),
            _page(2, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Confidential Footer', 50, 960, 300, 980),
                _block(IMAGE_PLACEHOLDER, 50, 60, 120, 80),
            ]),
        ])
        decisions = parse_exclusion_review_markdown('\n'.join([
            _review_markdown(
                'repeated-1',
                'annual report||top',
                'header',
                'would_exclude',
                'reject_exclude'),
            _review_markdown(
                'repeated-2',
                'confidential footer||bottom',
                'footer',
                'would_exclude',
                'unsure'),
            _review_markdown(
                'repeated-3',
                f'{IMAGE_PLACEHOLDER.lower()}||top',
                'layout_placeholder',
                'review',
                'approve_exclude'),
        ]))

        diff = build_body_filtering_diff_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True)

        self.assertEqual(diff['summary']['would_remove_block_count'], 0)
        self.assertEqual(diff['summary']['kept_block_count'], 9)
        self.assertEqual(diff['safety']['warnings'], [])

    def test_body_filtering_diff_report_does_not_mutate_input(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('More body text.', 50, 300, 520, 330),
            ]),
        ])
        before = json.loads(json.dumps(report['pages']))
        decisions = parse_exclusion_review_markdown(_review_markdown(
            'repeated-1',
            'annual report||top',
            'header',
            'would_exclude',
            'approve_exclude'))

        build_body_filtering_diff_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True)

        self.assertEqual(report['pages'], before)

    def test_body_filtering_diff_warns_when_unapproved_candidate_would_be_removed(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
            ]),
        ])
        decisions = parse_exclusion_review_markdown(_review_markdown(
            'repeated-1',
            'annual report||top',
            'header',
            'would_exclude',
            'reject_exclude'))
        unsafe_filter_report = {
            'approved_fingerprints': [],
            'approved_candidate_count': 0,
            'blocked_candidate_count': 1,
            'blocked_candidates': [{
                'candidate_id': 'repeated-1',
                'fingerprint': 'annual report||top',
                'proposed_role': 'header',
                'action': 'would_exclude',
                'manual_decision': 'reject_exclude',
            }],
            'pages': [{
                'page_index': 0,
                'removed_blocks': [{
                    'block_index': 0,
                    'fingerprint': 'annual report||top',
                    'candidate_id': 'repeated-1',
                    'proposed_role': 'header',
                    'manual_decision': 'reject_exclude',
                    'explicit_approval': False,
                    'removal_reason': 'unsafe test removal',
                }],
            }],
        }

        diff = build_body_filtering_diff_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True,
            filtering_report=unsafe_filter_report)

        self.assertIn('Unapproved candidates would be removed.', diff['safety']['warnings'])
        self.assertIn('Rejected candidates would be removed.', diff['safety']['warnings'])
        self.assertEqual(diff['safety']['unapproved_removed_candidate_count'], 1)
        self.assertEqual(diff['safety']['rejected_removed_candidate_count'], 1)

    def test_body_filtering_diff_disabled_mode_removes_zero_blocks(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph one.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph two.', 50, 300, 520, 330),
            ]),
        ])
        decisions = parse_exclusion_review_markdown(_review_markdown(
            'repeated-1',
            'annual report||top',
            'header',
            'would_exclude',
            'approve_exclude'))

        diff = build_body_filtering_diff_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions)

        self.assertFalse(diff['enabled'])
        self.assertEqual(diff['summary']['would_remove_block_count'], 0)
        self.assertEqual(diff['summary']['kept_block_count'], 4)

    def test_paragraph_integrity_report_has_no_body_loss_for_top_bottom_removal(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph first line', 50, 300, 520, 330),
                _block('Body paragraph second line', 50, 335, 520, 365),
                _block('Page 1', 270, 960, 330, 980),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph continues', 50, 300, 520, 330),
                _block('Body paragraph finishes', 50, 335, 520, 365),
                _block('Page 2', 270, 960, 330, 980),
            ]),
        ])
        decisions = parse_exclusion_review_markdown('\n'.join([
            _review_markdown(
                'repeated-1',
                f'{PAGE_NUMBER_PLACEHOLDER.lower()}||bottom',
                'page_number',
                'would_exclude',
                'approve_exclude'),
            _review_markdown(
                'repeated-2',
                'annual report||top',
                'header',
                'would_exclude',
                'approve_exclude'),
        ]))
        diff = build_body_filtering_diff_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True)

        integrity = build_paragraph_integrity_report(
            report['pages'],
            diff,
            enabled=True)

        self.assertEqual(integrity['summary']['removed_block_count'], 4)
        self.assertEqual(integrity['summary']['body_region_removed_count'], 0)
        self.assertEqual(integrity['summary']['top_bottom_removed_count'], 4)
        self.assertEqual(integrity['suspicious_body_loss_warnings'], [])
        self.assertEqual(integrity['suspicious_paragraph_gap_warnings'], [])
        self.assertTrue(integrity['summary']['line_level_body_blocks_available'])

    def test_paragraph_integrity_warns_if_body_region_block_is_removed(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Body paragraph first line', 50, 300, 520, 330),
                _block('Body paragraph removed line', 50, 335, 520, 365),
                _block('Body paragraph final line', 50, 370, 520, 400),
            ]),
        ])
        diff = _unsafe_diff_report_for_removed_blocks(
            report['pages'],
            [(0, 1)])

        integrity = build_paragraph_integrity_report(
            report['pages'],
            diff,
            enabled=True)

        self.assertEqual(integrity['summary']['body_region_removed_count'], 1)
        self.assertIn(
            'body_region_removed',
            {warning['type'] for warning in integrity['suspicious_body_loss_warnings']})
        self.assertIn(
            'body_flow_gap',
            {warning['type'] for warning in integrity['suspicious_paragraph_gap_warnings']})

    def test_paragraph_integrity_warns_on_high_page_body_loss(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Body paragraph first line', 50, 300, 520, 330),
                _block('Body paragraph second line', 50, 335, 520, 365),
                _block('Body paragraph third line', 50, 370, 520, 400),
            ]),
        ])
        diff = _unsafe_diff_report_for_removed_blocks(
            report['pages'],
            [(0, 0), (0, 1)])

        integrity = build_paragraph_integrity_report(
            report['pages'],
            diff,
            enabled=True,
            high_body_loss_ratio=0.5)

        self.assertIn(
            'high_body_loss_ratio',
            {warning['type'] for warning in integrity['suspicious_body_loss_warnings']})

    def test_paragraph_integrity_keeps_line_level_body_blocks_available(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body line one', 50, 300, 520, 330),
                _block('Body line two', 50, 335, 520, 365),
                _block('Body line three', 50, 370, 520, 400),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body line four', 50, 300, 520, 330),
            ]),
        ])
        decisions = parse_exclusion_review_markdown(_review_markdown(
            'repeated-1',
            'annual report||top',
            'header',
            'would_exclude',
            'approve_exclude'))
        diff = build_body_filtering_diff_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True)

        integrity = build_paragraph_integrity_report(
            report['pages'],
            diff,
            enabled=True)
        kept_body_blocks = [
            block
            for page in integrity['filtered_pages']
            for block in page['text_blocks']
            if block['region'] == REGION_BODY
        ]

        self.assertEqual(len(kept_body_blocks), 4)
        self.assertTrue(integrity['summary']['line_level_body_blocks_available'])

    def test_paragraph_integrity_report_does_not_mutate_input(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('More body text.', 50, 300, 520, 330),
            ]),
        ])
        before = json.loads(json.dumps(report['pages']))
        decisions = parse_exclusion_review_markdown(_review_markdown(
            'repeated-1',
            'annual report||top',
            'header',
            'would_exclude',
            'approve_exclude'))
        diff = build_body_filtering_diff_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True)

        build_paragraph_integrity_report(
            report['pages'],
            diff,
            enabled=True)

        self.assertEqual(report['pages'], before)

    def test_paragraph_integrity_disabled_mode_keeps_original_summaries(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body paragraph.', 50, 300, 520, 330),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('More body text.', 50, 300, 520, 330),
            ]),
        ])
        decisions = parse_exclusion_review_markdown(_review_markdown(
            'repeated-1',
            'annual report||top',
            'header',
            'would_exclude',
            'approve_exclude'))
        diff = build_body_filtering_diff_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True)

        integrity = build_paragraph_integrity_report(
            report['pages'],
            diff)

        self.assertFalse(integrity['enabled'])
        self.assertEqual(integrity['summary']['removed_block_count'], 0)
        self.assertEqual(integrity['summary']['filtered_block_count'], 4)
        self.assertEqual(integrity['filtered_pages'], report['pages'])

    def test_paragraph_reconstruction_groups_consistent_body_lines(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('This visual line starts a paragraph', 50, 300, 520, 320),
                _block('and this visual line continues it', 50, 326, 520, 346),
                _block('before the same paragraph finishes.', 50, 352, 520, 372),
                _block('Page 1', 270, 960, 330, 980),
            ]),
            _page(1, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Another body paragraph.', 50, 300, 520, 320),
                _block('Page 2', 270, 960, 330, 980),
            ]),
        ])
        decisions = parse_exclusion_review_markdown('\n'.join([
            _review_markdown(
                'repeated-1',
                'annual report||top',
                'header',
                'would_exclude',
                'approve_exclude'),
            _review_markdown(
                'repeated-2',
                f'{PAGE_NUMBER_PLACEHOLDER.lower()}||bottom',
                'page_number',
                'would_exclude',
                'approve_exclude'),
        ]))
        diff = build_body_filtering_diff_report(
            report['pages'],
            report['header_footer_exclusion_dry_run'],
            decisions,
            enabled=True)
        integrity = build_paragraph_integrity_report(
            report['pages'],
            diff,
            enabled=True)

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            paragraph_integrity_report=integrity,
            enabled=True)

        self.assertEqual(
            validation['summary']['body_block_count_before_filtering'], 4)
        self.assertEqual(
            validation['summary']['body_block_count_after_filtering'], 4)
        self.assertEqual(validation['pages'][0]['estimated_paragraph_group_count'], 1)
        self.assertEqual(
            validation['pages'][0]['estimated_paragraph_groups'][0]['block_count'], 3)
        self.assertEqual(validation['summary']['warning_count'], 0)

    def test_paragraph_reconstruction_groups_same_row_fragments_as_one_line(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Click on', 50, 300, 110, 320),
                _block('Header', 116, 300, 170, 320, style={'font': 'Arial', 'size': 11.0}),
                _block('and then choose Edit.', 50, 326, 520, 346),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        group = validation['pages'][0]['estimated_paragraph_groups'][0]
        self.assertEqual(validation['pages'][0]['estimated_paragraph_group_count'], 1)
        self.assertEqual(group['line_count'], 2)
        self.assertEqual(group['block_count'], 3)

    def test_paragraph_reconstruction_detects_hard_break_signals(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('First paragraph line one', 50, 300, 520, 320),
                _block('First paragraph line two.', 50, 326, 250, 346),
                _block('Indented new paragraph starts', 80, 352, 520, 372),
                _block(
                    'Different style paragraph starts',
                    80, 378, 520, 398,
                    style={'font': 'Arial', 'size': 12.0}),
                _block(
                    'Large gap paragraph starts',
                    80, 520, 520, 540,
                    style={'font': 'Arial', 'size': 12.0}),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        groups = validation['pages'][0]['estimated_paragraph_groups']
        break_reasons = [
            reason
            for group in groups
            for reason in group['break_before_reasons']
        ]
        self.assertEqual(validation['pages'][0]['estimated_paragraph_group_count'], 4)
        self.assertIn('indentation_change', break_reasons)
        self.assertIn('style_change', break_reasons)
        self.assertIn('large_vertical_gap', break_reasons)
        self.assertIn('split_boundaries', validation['pages'][0])
        boundary_reasons = [
            reason
            for boundary in validation['pages'][0]['split_boundaries']
            for reason in boundary['reasons']
        ]
        self.assertIn('indentation_change', boundary_reasons)
        self.assertIn('sentence_end_with_trailing_space', boundary_reasons)

    def test_paragraph_reconstruction_ignores_weak_indentation_change(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('This visual line continues without punctuation', 50, 300, 520, 320),
                _block('and this indented line is still continuation text', 80, 326, 520, 346),
                _block('with one more aligned continuation line.', 80, 352, 520, 372),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        page = validation['pages'][0]
        self.assertEqual(page['estimated_paragraph_group_count'], 1)
        self.assertEqual(
            page['ignored_split_boundaries'][0]['ignored_reasons'],
            ['weak_indentation_change'])
        self.assertEqual(
            validation['summary']['ignored_split_reason_counts'],
            {'weak_indentation_change': 1})

    def test_paragraph_reconstruction_indentation_with_free_space_can_split(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('A short complete sentence.', 50, 300, 250, 320),
                _block('Indented new paragraph starts after free space', 90, 326, 520, 346),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        split_reasons = validation['pages'][0]['split_boundaries'][0]['reasons']
        self.assertEqual(validation['pages'][0]['estimated_paragraph_group_count'], 2)
        self.assertIn('indentation_change', split_reasons)
        self.assertIn('sentence_end_with_trailing_space', split_reasons)

    def test_paragraph_reconstruction_heading_like_indentation_still_splits(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Overview', 50, 300, 170, 320),
                _block('Indented body starts below the heading.', 85, 326, 520, 346),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        split_reasons = validation['pages'][0]['split_boundaries'][0]['reasons']
        self.assertEqual(validation['pages'][0]['estimated_paragraph_group_count'], 2)
        self.assertIn('previous_heading_like', split_reasons)
        self.assertIn('indentation_change', split_reasons)

    def test_paragraph_reconstruction_list_indentation_still_splits(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Introductory prose before a list', 50, 300, 520, 320),
                _block('- Indented list item', 80, 326, 420, 346),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        split_reasons = validation['pages'][0]['split_boundaries'][0]['reasons']
        self.assertEqual(validation['pages'][0]['estimated_paragraph_group_count'], 2)
        self.assertIn('list_marker', split_reasons)
        self.assertIn('indentation_change', split_reasons)

    def test_paragraph_reconstruction_weak_indent_relaxation_reduces_group_count(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('A continuing instruction line without a period', 50, 300, 520, 320),
                _block('wrapped continuation line with indentation', 80, 326, 520, 346),
                _block('another wrapped continuation line', 80, 352, 520, 372),
                _block('final wrapped continuation line.', 80, 378, 520, 398),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        self.assertEqual(validation['pages'][0]['estimated_paragraph_group_count'], 1)
        self.assertEqual(
            validation['diagnostics']['ignored_split_reason_counts'],
            {'weak_indentation_change': 1})

    def test_paragraph_reconstruction_sentence_end_does_not_force_every_line_split(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('This complete sentence fills the line.', 50, 300, 550, 320),
                _block('The next visual line can still belong with it', 50, 326, 550, 346),
                _block('Short sentence.', 50, 352, 250, 372),
                _block('A new paragraph starts after visible free space', 50, 378, 550, 398),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        self.assertEqual(validation['pages'][0]['estimated_paragraph_group_count'], 2)
        split_reasons = [
            reason
            for boundary in validation['pages'][0]['split_boundaries']
            for reason in boundary['reasons']
        ]
        self.assertIn('sentence_end_with_trailing_space', split_reasons)

    def test_paragraph_reconstruction_splits_heading_like_short_lines(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Overview', 50, 300, 180, 320),
                _block('This body paragraph starts below the heading', 50, 326, 550, 346),
                _block('and continues on a second visual line.', 50, 352, 550, 372),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        self.assertEqual(validation['pages'][0]['estimated_paragraph_group_count'], 2)
        split_reasons = [
            reason
            for boundary in validation['pages'][0]['split_boundaries']
            for reason in boundary['reasons']
        ]
        self.assertIn('previous_heading_like', split_reasons)

    def test_paragraph_reconstruction_keeps_list_items_separate_from_prose(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Introductory prose before a list.', 50, 300, 550, 320),
                _block('- First list item', 70, 326, 400, 346),
                _block('Closing prose after the list item', 50, 352, 550, 372),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        self.assertEqual(validation['pages'][0]['estimated_paragraph_group_count'], 3)
        split_reasons = [
            reason
            for boundary in validation['pages'][0]['split_boundaries']
            for reason in boundary['reasons']
        ]
        self.assertIn('list_marker', split_reasons)
        self.assertIn('previous_list_item', split_reasons)

    def test_paragraph_reconstruction_hyphenated_line_ending_is_continuation_signal(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('This line ends with a hyphen-', 50, 300, 350, 320),
                _block('ated word despite indentation change.', 80, 326, 550, 346),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        self.assertEqual(validation['pages'][0]['estimated_paragraph_group_count'], 1)
        self.assertEqual(validation['pages'][0]['split_boundaries'], [])

    def test_paragraph_reconstruction_warns_on_excessive_one_line_fragments(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Small bit one', 50, 300, 520, 320),
                _block('Small bit two', 50, 380, 520, 400),
                _block('Small bit three', 50, 460, 520, 480),
                _block('Small bit four', 50, 540, 520, 560),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        self.assertEqual(
            validation['summary']['suspicious_single_line_paragraph_count'], 4)
        self.assertEqual(
            validation['summary']['suspicious_short_fragment_count'], 4)
        self.assertIn(
            'excessive_one_line_fragmentation',
            {warning['type'] for warning in validation['warnings']})
        self.assertGreater(
            validation['diagnostics']['one_line_group_ratio'],
            0.0)
        self.assertEqual(
            validation['diagnostics']['pages_with_worst_fragmentation'][0]['page_number'],
            1)
        self.assertIn('1', validation['diagnostics']['groups_by_line_count'])

    def test_paragraph_reconstruction_reports_cross_page_continuation_without_merge(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('This paragraph starts on one page and continues', 50, 805, 520, 835),
            ]),
            _page(1, [
                _block('with the same sentence on the next page.', 50, 170, 520, 200),
            ]),
        ])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        self.assertEqual(
            validation['summary']['possible_cross_page_continuation_count'], 1)
        self.assertEqual(
            validation['summary']['estimated_paragraph_group_count'], 2)
        self.assertIn(
            'possible_cross_page_continuation',
            {warning['type'] for warning in validation['warnings']})

    def test_paragraph_reconstruction_report_does_not_mutate_input(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Body line one', 50, 300, 520, 320),
                _block('Body line two.', 50, 326, 520, 346),
            ]),
        ])
        before = json.loads(json.dumps(report['pages']))

        build_paragraph_reconstruction_validation_report(
            report['pages'],
            enabled=True)

        self.assertEqual(report['pages'], before)

    def test_paragraph_reconstruction_disabled_mode_keeps_original_summaries(self):
        report = build_layout_analysis_report([
            _page(0, [
                _block('Annual Report', 50, 20, 300, 40),
                _block('Body line one', 50, 300, 520, 320),
                _block('Body line two.', 50, 326, 520, 346),
            ]),
        ])
        diff = _unsafe_diff_report_for_removed_blocks(
            report['pages'],
            [(0, 1)])

        validation = build_paragraph_reconstruction_validation_report(
            report['pages'],
            body_filtering_diff_report=diff)

        self.assertFalse(validation['enabled'])
        self.assertEqual(
            validation['summary']['body_block_count_before_filtering'], 2)
        self.assertEqual(
            validation['summary']['body_block_count_after_filtering'], 2)
        self.assertEqual(
            validation['summary']['estimated_paragraph_group_count'], 0)
        self.assertEqual(validation['filtered_pages'], report['pages'])

    def test_paragraph_production_comparison_includes_estimator_metrics(self):
        estimator = build_paragraph_reconstruction_validation_report(
            build_layout_analysis_report([
                _page(0, [
                    _block('Body line one', 50, 300, 520, 320),
                    _block('Body line two.', 50, 326, 520, 346),
                ]),
            ])['pages'],
            enabled=True)

        comparison = build_paragraph_production_comparison_report(
            estimator,
            production_pages=[],
            enabled=True)

        self.assertTrue(comparison['estimator']['available'])
        self.assertEqual(comparison['estimator']['paragraph_group_count'], 1)
        self.assertFalse(comparison['production_observed']['available'])
        self.assertEqual(
            comparison['warnings'][0]['type'],
            'production_metrics_unavailable')

    def test_paragraph_production_comparison_includes_production_metrics(self):
        estimator = build_paragraph_reconstruction_validation_report(
            build_layout_analysis_report([
                _page(0, [
                    _block('Body line one', 50, 300, 520, 320),
                    _block('Body line two.', 50, 326, 520, 346),
                    _block('Second paragraph.', 50, 420, 300, 440),
                ]),
            ])['pages'],
            enabled=True)
        production_pages = [
            _production_page(0, [
                _production_text_block(
                    ['Body line one', 'Body line two.'],
                    [50, 300, 520, 346]),
                _production_text_block(
                    ['Second paragraph.'],
                    [50, 420, 300, 440]),
            ]),
        ]

        comparison = build_paragraph_production_comparison_report(
            estimator,
            production_pages=production_pages,
            enabled=True)

        self.assertTrue(comparison['production_observed']['available'])
        self.assertEqual(comparison['production_observed']['paragraph_group_count'], 2)
        self.assertEqual(comparison['production_observed']['total_body_line_count'], 3)
        self.assertIn('average_lines_per_group', comparison['production_observed'])

    def test_paragraph_production_comparison_computes_mismatch_ratio(self):
        estimator = build_paragraph_reconstruction_validation_report(
            build_layout_analysis_report([
                _page(0, [
                    _block('One.', 50, 300, 200, 320),
                    _block('Two.', 50, 380, 200, 400),
                    _block('Three.', 50, 460, 200, 480),
                ]),
            ])['pages'],
            enabled=True)
        production_pages = [
            _production_page(0, [
                _production_text_block(
                    ['One.', 'Two.', 'Three.'],
                    [50, 300, 200, 480]),
            ]),
        ]

        comparison = build_paragraph_production_comparison_report(
            estimator,
            production_pages=production_pages,
            enabled=True)

        self.assertEqual(comparison['mismatch']['estimator_group_count'], 3)
        self.assertEqual(comparison['mismatch']['production_group_count'], 1)
        self.assertEqual(comparison['mismatch']['group_count_delta_ratio'], 2.0)
        self.assertEqual(
            comparison['warnings'][0]['type'],
            'high_group_count_mismatch')

    def test_paragraph_production_comparison_does_not_mutate_inputs(self):
        estimator = build_paragraph_reconstruction_validation_report(
            build_layout_analysis_report([
                _page(0, [
                    _block('Body line one', 50, 300, 520, 320),
                    _block('Body line two.', 50, 326, 520, 346),
                ]),
            ])['pages'],
            enabled=True)
        production_pages = [
            _production_page(0, [
                _production_text_block(
                    ['Body line one', 'Body line two.'],
                    [50, 300, 520, 346]),
            ]),
        ]
        before_estimator = json.loads(json.dumps(estimator))
        before_production = json.loads(json.dumps(production_pages))

        build_paragraph_production_comparison_report(
            estimator,
            production_pages=production_pages,
            enabled=True)

        self.assertEqual(estimator, before_estimator)
        self.assertEqual(production_pages, before_production)

    def test_paragraph_production_comparison_disabled_mode_is_clear(self):
        estimator = build_paragraph_reconstruction_validation_report(
            build_layout_analysis_report([
                _page(0, [
                    _block('Body line one', 50, 300, 520, 320),
                    _block('Body line two.', 50, 326, 520, 346),
                ]),
            ])['pages'],
            enabled=True)
        production_pages = [
            _production_page(0, [
                _production_text_block(
                    ['Body line one', 'Body line two.'],
                    [50, 300, 520, 346]),
            ]),
        ]

        comparison = build_paragraph_production_comparison_report(
            estimator,
            production_pages=production_pages)

        self.assertFalse(comparison['enabled'])
        self.assertFalse(comparison['production_observed']['available'])
        self.assertFalse(comparison['mismatch']['available'])

    def test_paragraph_mismatch_analysis_identifies_estimator_over_splitting(self):
        estimator = _estimator_report_for_mismatch([
            _estimator_page_for_mismatch(
                0,
                group_count=5,
                body_blocks=10,
                split_reasons=['indentation_change'] * 4),
        ])
        production_pages = [
            _production_page(0, [
                _production_text_block(['Line one', 'Line two', 'Line three'], [50, 300, 520, 360]),
            ]),
        ]

        analysis = build_paragraph_mismatch_analysis_report(
            estimator,
            production_pages=production_pages,
            enabled=True)

        self.assertEqual(
            analysis['summary']['dominant_mismatch_cause'],
            'estimator_over_split_by_indentation')
        self.assertEqual(
            analysis['pages'][0]['likely_cause'],
            'estimator_over_split_by_indentation')
        self.assertIn('indentation_change', analysis['pages'][0]['estimator_split_reason_counts'])

    def test_paragraph_mismatch_analysis_identifies_possible_production_over_merge(self):
        estimator = _estimator_report_for_mismatch([
            _estimator_page_for_mismatch(
                0,
                group_count=4,
                body_blocks=8,
                split_reasons=[]),
        ])
        production_pages = [
            _production_page(0, [
                _production_text_block(
                    ['Line one', 'Line two', 'Line three', 'Line four', 'Line five', 'Line six'],
                    [50, 300, 520, 460]),
            ]),
        ]

        analysis = build_paragraph_mismatch_analysis_report(
            estimator,
            production_pages=production_pages,
            enabled=True)

        self.assertEqual(
            analysis['pages'][0]['likely_cause'],
            'production_possible_over_merge')
        self.assertTrue(analysis['summary']['mostly_production_over_merging'])

    def test_paragraph_mismatch_analysis_lists_worst_pages(self):
        estimator = _estimator_report_for_mismatch([
            _estimator_page_for_mismatch(0, group_count=2, body_blocks=4, split_reasons=[]),
            _estimator_page_for_mismatch(1, group_count=8, body_blocks=16, split_reasons=['style_change'] * 7),
        ])
        production_pages = [
            _production_page(0, [
                _production_text_block(['One'], [50, 300, 520, 320]),
            ]),
            _production_page(1, [
                _production_text_block(['One', 'Two'], [50, 300, 520, 350]),
            ]),
        ]

        analysis = build_paragraph_mismatch_analysis_report(
            estimator,
            production_pages=production_pages,
            enabled=True)

        self.assertEqual(analysis['pages'][0]['page_number'], 2)
        self.assertEqual(analysis['pages'][0]['absolute_group_count_delta'], 7)
        self.assertEqual(
            analysis['pages'][0]['likely_cause'],
            'estimator_over_split_by_style_change')

    def test_paragraph_mismatch_analysis_handles_missing_production_metrics(self):
        estimator = _estimator_report_for_mismatch([
            _estimator_page_for_mismatch(0, group_count=2, body_blocks=4, split_reasons=[]),
        ])

        analysis = build_paragraph_mismatch_analysis_report(
            estimator,
            enabled=True)

        self.assertFalse(analysis['summary']['available'])
        self.assertEqual(
            analysis['warnings'][0]['type'],
            'production_metrics_unavailable')

    def test_paragraph_mismatch_analysis_does_not_mutate_inputs(self):
        estimator = _estimator_report_for_mismatch([
            _estimator_page_for_mismatch(
                0,
                group_count=3,
                body_blocks=6,
                split_reasons=['sentence_end_with_trailing_space'] * 2),
        ])
        production_pages = [
            _production_page(0, [
                _production_text_block(['One', 'Two'], [50, 300, 520, 350]),
            ]),
        ]
        before_estimator = json.loads(json.dumps(estimator))
        before_production = json.loads(json.dumps(production_pages))

        build_paragraph_mismatch_analysis_report(
            estimator,
            production_pages=production_pages,
            enabled=True)

        self.assertEqual(estimator, before_estimator)
        self.assertEqual(production_pages, before_production)

    def test_paragraph_mismatch_analysis_disabled_mode_is_clear(self):
        estimator = _estimator_report_for_mismatch([
            _estimator_page_for_mismatch(0, group_count=2, body_blocks=4, split_reasons=[]),
        ])
        production_pages = [
            _production_page(0, [
                _production_text_block(['One'], [50, 300, 520, 320]),
            ]),
        ]

        analysis = build_paragraph_mismatch_analysis_report(
            estimator,
            production_pages=production_pages)

        self.assertFalse(analysis['enabled'])
        self.assertFalse(analysis['summary']['available'])
        self.assertEqual(analysis['pages'], [])

    def test_indentation_rule_comparison_marks_small_indent_as_mergeable(self):
        report = _estimator_report_for_indentation([
            _indentation_boundary(
                page_index=0,
                left_delta=12.0,
                previous_sentence_end=False,
                width_similar=True,
                previous_width_ratio=0.95,
                previous_right_gap_ratio=0.02),
        ])

        comparison = build_indentation_rule_comparison_report(
            report,
            enabled=True)

        self.assertEqual(
            comparison['summary']['total_indentation_split_boundaries'], 1)
        self.assertEqual(
            comparison['boundaries'][0]['recommendation'],
            'estimator_should_merge')
        self.assertEqual(
            comparison['boundaries'][0]['production_like_expected_behavior'],
            'keep_together')

    def test_indentation_rule_comparison_marks_clear_new_paragraph_as_split(self):
        report = _estimator_report_for_indentation([
            _indentation_boundary(
                page_index=0,
                left_delta=40.0,
                previous_sentence_end=True,
                width_similar=False,
                previous_width_ratio=0.1,
                previous_right_gap_ratio=0.9),
        ])

        comparison = build_indentation_rule_comparison_report(
            report,
            enabled=True)

        self.assertEqual(
            comparison['boundaries'][0]['recommendation'],
            'estimator_should_split')
        self.assertEqual(
            comparison['summary']['estimator_should_split_count'], 1)

    def test_indentation_rule_comparison_keeps_heading_list_boundary_split(self):
        report = _estimator_report_for_indentation([
            _indentation_boundary(
                page_index=0,
                left_delta=35.0,
                previous_sentence_end=False,
                width_similar=True,
                previous_width_ratio=0.95,
                previous_right_gap_ratio=0.01,
                extra_reasons=['list_marker'],
                current_list_marker=True),
        ])

        comparison = build_indentation_rule_comparison_report(
            report,
            enabled=True)

        self.assertEqual(
            comparison['boundaries'][0]['production_like_expected_behavior'],
            'treat_as_heading_list_table_boundary')
        self.assertEqual(
            comparison['boundaries'][0]['recommendation'],
            'estimator_should_split')

    def test_indentation_rule_comparison_reports_missing_metadata(self):
        report = _estimator_report_for_indentation([
            _indentation_boundary(
                page_index=0,
                left_delta=0.0,
                previous_sentence_end=False,
                width_similar=False,
                previous_width_ratio=0.0,
                previous_right_gap_ratio=0.0,
                insufficient_metadata=True),
        ])

        comparison = build_indentation_rule_comparison_report(
            report,
            enabled=True)

        self.assertEqual(
            comparison['boundaries'][0]['recommendation'],
            'needs_more_metadata')
        self.assertEqual(
            comparison['summary']['needs_more_metadata_count'], 1)

    def test_indentation_rule_comparison_produces_summary_counts(self):
        report = _estimator_report_for_indentation([
            _indentation_boundary(0, left_delta=12.0, previous_sentence_end=False, width_similar=True),
            _indentation_boundary(0, left_delta=40.0, previous_sentence_end=True, previous_width_ratio=0.1, previous_right_gap_ratio=0.9),
            _indentation_boundary(1, left_delta=35.0, previous_sentence_end=False, extra_reasons=['heading_like'], current_heading_like=True),
        ])

        comparison = build_indentation_rule_comparison_report(
            report,
            enabled=True)

        self.assertEqual(
            comparison['summary']['total_indentation_split_boundaries'], 3)
        self.assertEqual(
            comparison['summary']['estimator_should_merge_count'], 1)
        self.assertEqual(
            comparison['summary']['estimator_should_split_count'], 2)
        self.assertEqual(comparison['pages'][0]['page_number'], 1)

    def test_indentation_rule_comparison_does_not_mutate_inputs(self):
        report = _estimator_report_for_indentation([
            _indentation_boundary(0, left_delta=12.0, previous_sentence_end=False, width_similar=True),
        ])
        before = json.loads(json.dumps(report))

        build_indentation_rule_comparison_report(
            report,
            enabled=True)

        self.assertEqual(report, before)

    def test_indentation_rule_comparison_disabled_mode_is_clear(self):
        report = _estimator_report_for_indentation([
            _indentation_boundary(0, left_delta=12.0, previous_sentence_end=False, width_similar=True),
        ])

        comparison = build_indentation_rule_comparison_report(report)

        self.assertFalse(comparison['enabled'])
        self.assertEqual(
            comparison['summary']['total_indentation_split_boundaries'], 0)
        self.assertEqual(comparison['boundaries'], [])

    def test_filter_insertion_analysis_includes_all_candidate_stages(self):
        analysis = build_filter_insertion_point_analysis_report(
            **_filter_insertion_reports(),
            enabled=True)

        candidate_ids = {
            point['candidate_id']
            for point in analysis['insertion_points']
        }
        self.assertEqual(analysis['summary']['evaluated_insertion_point_count'], 6)
        self.assertEqual(candidate_ids, {
            'raw_page_cleanup',
            'document_parse',
            'before_page_parse',
            'before_blocks_cleanup_or_grouping',
            'after_textblock_grouping',
            'docx_generation',
        })

    def test_filter_insertion_analysis_stage_fields_are_complete(self):
        analysis = build_filter_insertion_point_analysis_report(
            **_filter_insertion_reports(),
            enabled=True)

        for point in analysis['insertion_points']:
            self.assertIn(point['risk_level'], {'low', 'medium', 'high'})
            self.assertIn(point['implementation_complexity'], {'low', 'medium', 'high'})
            self.assertIn(point['recommendation'], {'preferred', 'possible', 'avoid'})
            self.assertIn('paragraph_grouping_impact', point)
            self.assertIn('table_detection_impact', point)
            self.assertIn('image_shape_extraction_impact', point)

    def test_filter_insertion_analysis_prefers_document_level_stage(self):
        analysis = build_filter_insertion_point_analysis_report(
            **_filter_insertion_reports(),
            enabled=True)

        by_id = _insertion_points_by_id(analysis)
        self.assertEqual(
            analysis['summary']['preferred_insertion_point'],
            'document_parse')
        self.assertEqual(by_id['document_parse']['recommendation'], 'preferred')
        self.assertEqual(by_id['document_parse']['risk_level'], 'low')

    def test_filter_insertion_analysis_marks_docx_stage_incomplete(self):
        analysis = build_filter_insertion_point_analysis_report(
            **_filter_insertion_reports(),
            enabled=True)

        docx_point = _insertion_points_by_id(analysis)['docx_generation']
        self.assertEqual(docx_point['recommendation'], 'avoid')
        self.assertEqual(docx_point['risk_level'], 'high')
        self.assertIn('Incomplete', docx_point['paragraph_grouping_impact'])

    def test_filter_insertion_analysis_marks_post_textblock_filtering_risky(self):
        analysis = build_filter_insertion_point_analysis_report(
            **_filter_insertion_reports(),
            enabled=True)

        point = _insertion_points_by_id(analysis)['after_textblock_grouping']
        self.assertEqual(point['recommendation'], 'avoid')
        self.assertEqual(point['risk_level'], 'high')
        self.assertTrue(any('merged' in signal for signal in point['negative_signals']))

    def test_filter_insertion_analysis_handles_missing_reports(self):
        analysis = build_filter_insertion_point_analysis_report(enabled=True)

        self.assertTrue(analysis['enabled'])
        self.assertIn(
            'layout_analysis_report',
            analysis['summary']['missing_inputs'])
        self.assertIn(
            'production_grouping_metrics_unavailable',
            {warning['type'] for warning in analysis['warnings']})

    def test_filter_insertion_analysis_does_not_mutate_inputs(self):
        reports = _filter_insertion_reports()
        before = json.loads(json.dumps(reports))

        build_filter_insertion_point_analysis_report(
            **reports,
            enabled=True)

        self.assertEqual(reports, before)

    def test_filter_insertion_analysis_disabled_mode_is_clear(self):
        analysis = build_filter_insertion_point_analysis_report(
            **_filter_insertion_reports())

        self.assertFalse(analysis['enabled'])
        self.assertEqual(analysis['insertion_points'], [])
        self.assertEqual(
            analysis['summary']['evaluated_insertion_point_count'],
            0)

    def test_document_parse_simulation_removes_only_approved_candidates(self):
        inputs = _document_parse_simulation_inputs()

        simulation = build_document_parse_filtering_simulation_report(
            **inputs,
            enabled=True,
            apply=True,
            expected_removed_count=2,
            expected_kept_count=4)

        self.assertEqual(simulation['insertion_point'], 'document_parse')
        self.assertEqual(simulation['summary']['would_remove_block_count'], 2)
        self.assertEqual(simulation['summary']['simulated_removed_count'], 2)
        self.assertEqual(simulation['removed_counts_by_role'], {
            ROLE_FOOTER: 1,
            ROLE_HEADER: 1,
        })

    def test_document_parse_simulation_keeps_rejected_unsure_and_placeholders(self):
        inputs = _document_parse_simulation_inputs()

        simulation = build_document_parse_filtering_simulation_report(
            **inputs,
            enabled=True,
            apply=True,
            expected_removed_count=2,
            expected_kept_count=4)
        kept_fingerprints = {
            block['fingerprint']
            for page in simulation['simulated_apply']['filtered_pages']
            for block in page['text_blocks']
        }

        self.assertIn('reject-header', kept_fingerprints)
        self.assertIn('unsure-footer', kept_fingerprints)
        self.assertIn('image-placeholder', kept_fingerprints)
        self.assertEqual(simulation['summary']['rejected_removed_count'], 0)
        self.assertEqual(simulation['summary']['unsure_removed_count'], 0)
        self.assertEqual(simulation['summary']['layout_placeholder_removed_count'], 0)

    def test_document_parse_simulation_preserves_body_region_blocks(self):
        inputs = _document_parse_simulation_inputs()

        simulation = build_document_parse_filtering_simulation_report(
            **inputs,
            enabled=True,
            apply=True,
            expected_removed_count=2,
            expected_kept_count=4)

        self.assertEqual(simulation['summary']['body_region_removed_count'], 0)
        self.assertTrue(
            simulation['downstream_availability']['body_region_blocks_preserved'])
        self.assertEqual(
            simulation['downstream_availability']['paragraph_grouping_body_block_count'],
            1)

    def test_document_parse_simulation_dry_run_removes_zero_blocks(self):
        inputs = _document_parse_simulation_inputs()

        simulation = build_document_parse_filtering_simulation_report(
            **inputs,
            enabled=True,
            apply=False,
            expected_removed_count=2,
            expected_kept_count=4)

        self.assertEqual(simulation['dry_run']['would_remove_block_count'], 2)
        self.assertEqual(simulation['dry_run']['removed_block_count'], 0)
        self.assertFalse(simulation['simulated_apply']['applied'])
        self.assertEqual(simulation['simulated_apply']['removed_block_count'], 0)
        self.assertEqual(simulation['summary']['simulated_kept_count'], 6)

    def test_document_parse_simulation_apply_uses_copied_data(self):
        inputs = _document_parse_simulation_inputs()
        before_pages = json.loads(json.dumps(inputs['page_summaries']))

        simulation = build_document_parse_filtering_simulation_report(
            **inputs,
            enabled=True,
            apply=True,
            expected_removed_count=2,
            expected_kept_count=4)

        self.assertEqual(inputs['page_summaries'], before_pages)
        self.assertIsNot(
            simulation['simulated_apply']['filtered_pages'][0],
            inputs['page_summaries'][0])
        self.assertEqual(
            len(simulation['simulated_apply']['filtered_pages'][0]['text_blocks']),
            4)

    def test_document_parse_simulation_counts_match_expected_reviewed_filtering(self):
        inputs = _document_parse_simulation_inputs()

        simulation = build_document_parse_filtering_simulation_report(
            **inputs,
            enabled=True,
            apply=True,
            expected_removed_count=2,
            expected_kept_count=4)

        checks = simulation['consistency_checks']
        self.assertTrue(checks['phase_2b_removed_match'])
        self.assertTrue(checks['phase_2b_kept_match'])
        self.assertTrue(checks['phase_2c_body_region_removed_match'])
        self.assertEqual(simulation['summary']['simulated_kept_count'], 4)

    def test_document_parse_simulation_reports_missing_review_decisions(self):
        inputs = _document_parse_simulation_inputs()
        inputs['review_decisions'] = {'decisions': [], 'summary': {'decision_counts': {}}}

        simulation = build_document_parse_filtering_simulation_report(
            **inputs,
            enabled=True,
            apply=True,
            expected_removed_count=0,
            expected_kept_count=6)

        warning_types = {warning['type'] for warning in simulation['safety_warnings']}
        self.assertIn('missing_review_decisions', warning_types)
        self.assertIn('no_approved_candidates', warning_types)
        self.assertEqual(simulation['summary']['would_remove_block_count'], 0)

    def test_document_parse_simulation_disabled_mode_is_clear(self):
        inputs = _document_parse_simulation_inputs()

        simulation = build_document_parse_filtering_simulation_report(**inputs)

        self.assertFalse(simulation['enabled'])
        self.assertFalse(simulation['applied'])
        self.assertEqual(simulation['summary']['would_remove_block_count'], 0)
        self.assertEqual(simulation['simulated_apply']['kept_block_count'], 6)

    def test_document_parse_hook_dry_run_reports_without_production_removal(self):
        inputs = _document_parse_simulation_inputs()

        hook = build_document_parse_filtering_hook_report(
            **inputs,
            enabled=True,
            apply=False,
            expected_removed_count=2,
            expected_kept_count=4)

        self.assertEqual(hook['hook_location'], 'Pages._parse_document()')
        self.assertEqual(hook['mode'], 'dry_run_report_only')
        self.assertEqual(hook['summary']['original_block_count'], 6)
        self.assertEqual(hook['summary']['would_remove_block_count'], 2)
        self.assertEqual(hook['summary']['simulated_removed_count'], 0)
        self.assertEqual(hook['summary']['production_removed_count'], 0)
        self.assertFalse(hook['summary']['production_objects_mutated'])
        self.assertFalse(hook['summary']['default_behavior_changed'])

    def test_document_parse_hook_uses_only_explicit_approval(self):
        inputs = _document_parse_simulation_inputs()

        hook = build_document_parse_filtering_hook_report(
            **inputs,
            enabled=True,
            apply=False,
            expected_removed_count=2,
            expected_kept_count=4)

        self.assertEqual(hook['summary']['approved_candidate_count'], 2)
        self.assertEqual(hook['summary']['blocked_candidate_count'], 3)
        self.assertEqual(hook['summary']['rejected_removed_count'], 0)
        self.assertEqual(hook['summary']['unsure_removed_count'], 0)
        self.assertEqual(hook['summary']['layout_placeholder_removed_count'], 0)

    def test_document_parse_hook_counts_match_simulation_helper(self):
        inputs = _document_parse_simulation_inputs()

        hook = build_document_parse_filtering_hook_report(
            **inputs,
            enabled=True,
            apply=False,
            expected_removed_count=2,
            expected_kept_count=4)
        simulation = build_document_parse_filtering_simulation_report(
            **inputs,
            enabled=True,
            apply=False,
            expected_removed_count=2,
            expected_kept_count=4)

        self.assertEqual(
            hook['summary']['would_remove_block_count'],
            simulation['summary']['would_remove_block_count'])
        self.assertEqual(
            hook['phase_2k_consistency']['would_remove_count_matches_phase_2k'],
            True)
        self.assertEqual(
            hook['phase_2k_consistency']['would_keep_count_matches_phase_2k'],
            True)

    def test_document_parse_hook_reports_missing_review_decisions(self):
        inputs = _document_parse_simulation_inputs()
        inputs['review_decisions'] = {'decisions': [], 'summary': {'decision_counts': {}}}

        hook = build_document_parse_filtering_hook_report(
            **inputs,
            enabled=True,
            apply=False,
            expected_removed_count=0,
            expected_kept_count=6)

        warning_types = {warning['type'] for warning in hook['safety_warnings']}
        self.assertIn('missing_review_decisions', warning_types)
        self.assertIn('no_approved_candidates', warning_types)
        self.assertFalse(hook['recommendation']['safe_to_attempt_phase_2m'])

    @unittest.skipIf(Pages is None, 'Pages import unavailable')
    def test_pages_parse_document_default_behavior_remains_unchanged(self):
        pages = Pages()

        self.assertEqual(Pages._parse_document([object()]), ('', ''))
        self.assertIsNone(pages._document_parse_filtering_hook_report)

    @unittest.skipIf(Pages is None, 'Pages import unavailable')
    def test_pages_document_parse_hook_stores_report_without_mutating_input(self):
        inputs = _document_parse_simulation_inputs()
        layout_report = _document_parse_hook_layout_report(inputs)
        before = json.loads(json.dumps(layout_report))
        pages = Pages()

        report = pages._run_document_parse_filtering_hook(
            layout_report,
            _document_parse_filtering_hook_enabled=True,
            _document_parse_filtering_review_decisions=inputs['review_decisions'],
            _document_parse_filtering_body_diff_report=inputs['body_filtering_diff_report'],
            _document_parse_filtering_paragraph_integrity_report=inputs['paragraph_integrity_report'],
            _document_parse_filtering_expected_removed_count=2,
            _document_parse_filtering_expected_kept_count=4)

        self.assertEqual(layout_report, before)
        self.assertIs(pages._document_parse_filtering_hook_report, report)
        self.assertEqual(report['summary']['would_remove_block_count'], 2)
        self.assertEqual(report['summary']['simulated_removed_count'], 0)

    @unittest.skipIf(Pages is None, 'Pages import unavailable')
    def test_pages_document_parse_hook_disabled_leaves_report_empty(self):
        inputs = _document_parse_simulation_inputs()
        layout_report = _document_parse_hook_layout_report(inputs)
        pages = Pages()

        report = pages._run_document_parse_filtering_hook(layout_report)

        self.assertIsNone(report)
        self.assertIsNone(pages._document_parse_filtering_hook_report)

    def test_raw_object_mapping_maps_approved_summary_to_one_raw_object(self):
        inputs = _document_parse_raw_mapping_inputs()

        mapping = build_document_parse_raw_object_mapping_report(
            **inputs,
            enabled=True,
            expected_would_remove_count=2)

        self.assertEqual(mapping['summary']['approved_candidate_count'], 2)
        self.assertEqual(mapping['summary']['expected_would_remove_count'], 2)
        self.assertEqual(mapping['summary']['mapped_raw_object_count'], 2)
        self.assertEqual(mapping['summary']['exact_match_count'], 2)
        self.assertEqual(mapping['summary']['ambiguous_match_count'], 0)
        self.assertEqual(mapping['summary']['missing_match_count'], 0)
        self.assertTrue(mapping['summary']['all_expected_blocks_mapped_once'])

    def test_raw_object_mapping_does_not_map_rejected_unsure_or_placeholder(self):
        inputs = _document_parse_raw_mapping_inputs()

        mapping = build_document_parse_raw_object_mapping_report(
            **inputs,
            enabled=True,
            expected_would_remove_count=2)
        mapped_fingerprints = {
            raw_object['fingerprint']
            for item in mapping['mappings']
            for raw_object in item['selected_raw_objects']
        }

        self.assertNotIn('reject-header', mapped_fingerprints)
        self.assertNotIn('unsure-footer', mapped_fingerprints)
        self.assertNotIn('image-placeholder', mapped_fingerprints)
        self.assertEqual(
            mapping['summary']['rejected_unsure_layout_placeholder_matched_for_removal_count'],
            0)

    def test_raw_object_mapping_does_not_map_body_region_for_removal(self):
        inputs = _document_parse_raw_mapping_inputs()
        inputs['raw_object_pages'][0]['raw_objects'].append(
            _raw_object(6, 'Approved Header', REGION_BODY))

        mapping = build_document_parse_raw_object_mapping_report(
            **inputs,
            enabled=True,
            expected_would_remove_count=2)

        self.assertEqual(mapping['summary']['mapped_raw_object_count'], 2)
        self.assertEqual(mapping['summary']['body_region_matched_for_removal_count'], 0)
        self.assertEqual(mapping['summary']['unsafe_match_count'], 0)

    def test_raw_object_mapping_warns_when_raw_object_is_missing(self):
        inputs = _document_parse_raw_mapping_inputs()
        inputs['raw_object_pages'][0]['raw_objects'] = [
            raw_object
            for raw_object in inputs['raw_object_pages'][0]['raw_objects']
            if raw_object['fingerprint'] != _summary_fingerprint('Approved Footer', REGION_BOTTOM)
        ]

        mapping = build_document_parse_raw_object_mapping_report(
            **inputs,
            enabled=True,
            expected_would_remove_count=2)

        warning_types = {warning['type'] for warning in mapping['safety_warnings']}
        self.assertEqual(mapping['summary']['missing_match_count'], 1)
        self.assertIn('missing_raw_object_match', warning_types)
        self.assertFalse(mapping['recommendation']['safe_to_attempt_phase_2n'])

    def test_raw_object_mapping_warns_when_raw_match_is_ambiguous(self):
        inputs = _document_parse_raw_mapping_inputs()
        inputs['raw_object_pages'][0]['raw_objects'].append(
            _raw_object(6, 'Approved Header', REGION_TOP))

        mapping = build_document_parse_raw_object_mapping_report(
            **inputs,
            enabled=True,
            expected_would_remove_count=2)

        warning_types = {warning['type'] for warning in mapping['safety_warnings']}
        self.assertEqual(mapping['summary']['ambiguous_match_count'], 1)
        self.assertIn('ambiguous_raw_object_match', warning_types)

    def test_raw_object_mapping_reports_fuzzy_match_separately(self):
        inputs = _document_parse_raw_mapping_inputs()
        inputs['raw_object_pages'][0]['raw_objects'][0]['bbox'] = [52.0, 22.0, 302.0, 42.0]

        mapping = build_document_parse_raw_object_mapping_report(
            **inputs,
            enabled=True,
            expected_would_remove_count=2)

        self.assertEqual(mapping['summary']['exact_match_count'], 1)
        self.assertEqual(mapping['summary']['fuzzy_match_count'], 1)
        self.assertEqual(mapping['summary']['mapped_raw_object_count'], 2)

    def test_raw_object_mapping_does_not_mutate_inputs(self):
        inputs = _document_parse_raw_mapping_inputs()
        before_pages = json.loads(json.dumps(inputs['page_summaries']))
        before_raw = json.loads(json.dumps(inputs['raw_object_pages']))

        build_document_parse_raw_object_mapping_report(
            **inputs,
            enabled=True,
            expected_would_remove_count=2)

        self.assertEqual(inputs['page_summaries'], before_pages)
        self.assertEqual(inputs['raw_object_pages'], before_raw)

    def test_raw_object_mapping_disabled_mode_is_clear(self):
        inputs = _document_parse_raw_mapping_inputs()

        mapping = build_document_parse_raw_object_mapping_report(**inputs)

        self.assertFalse(mapping['enabled'])
        self.assertEqual(mapping['summary']['mapped_raw_object_count'], 0)
        self.assertFalse(mapping['recommendation']['safe_to_attempt_phase_2n'])

    @unittest.skipIf(Pages is None, 'Pages import unavailable')
    def test_pages_raw_object_mapping_hook_stores_report_without_mutating_raw_pages(self):
        inputs = _document_parse_raw_mapping_inputs()
        layout_report = _document_parse_hook_layout_report(inputs)
        fake_pages = [_FakePage(0)]
        fake_raw_pages = [_FakeRawPage(inputs['raw_object_pages'][0]['raw_objects'])]
        before_raw_texts = [block.text for block in fake_raw_pages[0].blocks]
        pages = Pages()

        report = pages._run_document_parse_raw_object_mapping_validation(
            layout_report,
            fake_pages,
            fake_raw_pages,
            _document_parse_raw_object_mapping_enabled=True,
            _document_parse_filtering_review_decisions=inputs['review_decisions'],
            _document_parse_mapping_expected_would_remove_count=2)

        self.assertIs(pages._document_parse_raw_object_mapping_report, report)
        self.assertEqual(report['summary']['mapped_raw_object_count'], 2)
        self.assertEqual([block.text for block in fake_raw_pages[0].blocks], before_raw_texts)

    @unittest.skipIf(Pages is None, 'Pages import unavailable')
    def test_pages_raw_object_mapping_disabled_leaves_report_empty(self):
        inputs = _document_parse_raw_mapping_inputs()
        layout_report = _document_parse_hook_layout_report(inputs)
        pages = Pages()

        report = pages._run_document_parse_raw_object_mapping_validation(
            layout_report,
            [_FakePage(0)],
            [_FakeRawPage(inputs['raw_object_pages'][0]['raw_objects'])])

        self.assertIsNone(report)
        self.assertIsNone(pages._document_parse_raw_object_mapping_report)


def _page(page_index, blocks):
    return {
        'page_index': page_index,
        'width': 600,
        'height': 1000,
        'blocks': blocks,
    }


def _block(text, x0, y0, x1, y1, style=None):
    return {
        'text': text,
        'bbox': [x0, y0, x1, y1],
        'style': style or {'font': 'Times New Roman', 'size': 11.0},
    }


def _production_page(page_index, text_blocks):
    return {
        'id': page_index,
        'width': 600,
        'height': 1000,
        'sections': [
            {
                'columns': [
                    {
                        'blocks': text_blocks,
                    },
                ],
            },
        ],
    }


def _production_text_block(lines, bbox):
    return {
        'type': 0,
        'bbox': bbox,
        'lines': [
            {
                'spans': [
                    {
                        'text': line,
                    },
                ],
            }
            for line in lines
        ],
    }


def _estimator_report_for_mismatch(pages):
    group_count = sum(page['estimated_paragraph_group_count'] for page in pages)
    body_blocks = sum(page['body_block_count_after_filtering'] for page in pages)
    return {
        'enabled': True,
        'summary': {
            'estimated_paragraph_group_count': group_count,
            'body_block_count_after_filtering': body_blocks,
            'average_blocks_per_estimated_paragraph': (
                round(body_blocks / group_count, 3)
                if group_count else 0.0),
            'suspicious_single_line_paragraph_count': 0,
            'suspicious_short_fragment_count': 0,
            'one_line_group_ratio': 0.0,
            'short_fragment_ratio': 0.0,
        },
        'pages': pages,
        'diagnostics': {},
    }


def _estimator_page_for_mismatch(page_index, group_count, body_blocks, split_reasons):
    groups = [
        {
            'group_index': index,
            'line_count': 1,
            'block_count': 1,
            'break_before_reasons': split_reasons[index-1:index],
            'text_preview': f'Estimator group {index}',
        }
        for index in range(group_count)
    ]
    return {
        'page_index': page_index,
        'page_number': page_index + 1,
        'estimated_paragraph_group_count': group_count,
        'body_block_count_after_filtering': body_blocks,
        'average_blocks_per_estimated_paragraph': (
            round(body_blocks / group_count, 3)
            if group_count else 0.0),
        'suspicious_single_line_paragraph_count': 0,
        'suspicious_short_fragment_count': 0,
        'estimated_paragraph_groups': groups,
        'split_boundaries': [
            {
                'boundary_index': index,
                'reasons': [reason],
                'previous_text_preview': f'Previous {index}',
                'next_text_preview': f'Next {index}',
            }
            for index, reason in enumerate(split_reasons)
        ],
    }


def _estimator_report_for_indentation(boundaries):
    pages = {}
    for boundary in boundaries:
        page_index = boundary['page_index']
        pages.setdefault(page_index, {
            'page_index': page_index,
            'page_number': page_index + 1,
            'estimated_paragraph_group_count': 1,
            'body_block_count_after_filtering': 2,
            'average_blocks_per_estimated_paragraph': 2.0,
            'suspicious_single_line_paragraph_count': 0,
            'suspicious_short_fragment_count': 0,
            'estimated_paragraph_groups': [],
            'split_boundaries': [],
        })
        pages[page_index]['split_boundaries'].append(boundary)

    return {
        'enabled': True,
        'summary': {
            'estimated_paragraph_group_count': len(pages),
            'body_block_count_after_filtering': len(boundaries) * 2,
            'average_blocks_per_estimated_paragraph': 2.0,
            'suspicious_single_line_paragraph_count': 0,
            'suspicious_short_fragment_count': 0,
            'one_line_group_ratio': 0.0,
            'short_fragment_ratio': 0.0,
        },
        'pages': list(pages.values()),
        'diagnostics': {},
    }


def _indentation_boundary(
        page_index,
        left_delta=24.0,
        previous_sentence_end=False,
        width_similar=True,
        previous_width_ratio=0.95,
        previous_right_gap_ratio=0.02,
        extra_reasons=None,
        current_heading_like=False,
        current_list_marker=False,
        insufficient_metadata=False):
    reasons = ['indentation_change']
    reasons.extend(extra_reasons or [])
    return {
        'page_index': page_index,
        'page_number': page_index + 1,
        'boundary_index': 0,
        'previous_line_index': 0,
        'next_line_index': 1,
        'previous_block_indexes': [0],
        'next_block_indexes': [1],
        'previous_bbox': [50.0, 300.0, 520.0, 320.0],
        'next_bbox': [50.0 + left_delta, 326.0, 520.0, 346.0],
        'previous_left': 50.0,
        'previous_right': 520.0,
        'next_left': 50.0 + left_delta,
        'next_right': 520.0,
        'reasons': reasons,
        'signals': {
            'left_delta': left_delta,
            'right_delta': 0.0,
            'width_delta_ratio': 0.02 if width_similar else 0.4,
            'width_similar': width_similar,
            'previous_sentence_end': previous_sentence_end,
            'previous_hyphenated': False,
            'current_heading_like': current_heading_like,
            'current_list_marker': current_list_marker,
            'style_change': False,
            'significant_style_change': False,
            'previous_width_ratio': previous_width_ratio,
            'previous_right_gap_ratio': previous_right_gap_ratio,
            'gap_ratio': 0.3,
            'insufficient_metadata': insufficient_metadata,
        },
        'previous_text_preview': 'Previous visual line',
        'next_text_preview': 'Next visual line',
    }


def _filter_insertion_reports(body_region_removed_count=0):
    return {
        'layout_analysis_report': {
            'page_count': 2,
            'pages': [{}, {}],
            'header_footer_exclusion_dry_run': {
                'summary': {'candidate_count': 5},
                'candidates': [{} for _ in range(5)],
            },
        },
        'review_decisions': {
            'summary': {
                'approve_exclude': 2,
                'reject_exclude': 1,
                'unsure': 1,
            },
            'decisions': [],
        },
        'body_filtering_diff_report': {
            'summary': {
                'approved_candidate_count': 2,
                'blocked_candidate_count': 3,
                'would_remove_block_count': 8,
            },
        },
        'paragraph_integrity_report': {
            'summary': {
                'body_region_removed_count': body_region_removed_count,
                'suspicious_warning_count': 0,
            },
        },
        'paragraph_grouping_report': {
            'summary': {
                'estimated_paragraph_group_count': 79,
            },
        },
        'production_comparison_report': {
            'estimator': {
                'paragraph_group_count': 79,
            },
            'production_observed': {
                'available': True,
                'paragraph_group_count': 52,
            },
            'mismatch': {
                'absolute_group_count_delta': 27,
                'estimator_to_production_group_ratio': 1.519,
                'group_count_delta_ratio': 0.519,
            },
            'warnings': [],
        },
        'paragraph_mismatch_report': {
            'summary': {
                'dominant_mismatch_cause': 'estimator_over_split_by_indentation',
            },
            'warnings': [],
        },
        'indentation_rule_report': {
            'summary': {
                'total_indentation_split_boundaries': 22,
                'estimator_should_merge_count': 0,
                'estimator_should_split_count': 22,
            },
        },
    }


def _document_parse_simulation_inputs():
    page_summaries = [
        {
            'page_index': 0,
            'page_number': 1,
            'text_block_count': 6,
            'region_counts': {
                REGION_TOP: 3,
                REGION_BODY: 1,
                REGION_BOTTOM: 2,
            },
            'text_blocks': [
                _summary_block(0, 'approved-header', REGION_TOP, 'Approved Header'),
                _summary_block(1, 'body-text', REGION_BODY, 'Body paragraph'),
                _summary_block(2, 'approved-footer', REGION_BOTTOM, 'Approved Footer'),
                _summary_block(3, 'reject-header', REGION_TOP, 'Rejected Header'),
                _summary_block(4, 'unsure-footer', REGION_BOTTOM, 'Unsure Footer'),
                _summary_block(5, 'image-placeholder', REGION_TOP, IMAGE_PLACEHOLDER),
            ],
        },
    ]
    dry_run_report = {
        'summary': {'candidate_count': 5},
        'candidates': [
            _dry_run_candidate('c-approved-header', 'approved-header', ROLE_HEADER, ACTION_WOULD_EXCLUDE, [0], [REGION_TOP]),
            _dry_run_candidate('c-approved-footer', 'approved-footer', ROLE_FOOTER, ACTION_WOULD_EXCLUDE, [0], [REGION_BOTTOM]),
            _dry_run_candidate('c-reject-header', 'reject-header', ROLE_HEADER, ACTION_WOULD_EXCLUDE, [0], [REGION_TOP]),
            _dry_run_candidate('c-unsure-footer', 'unsure-footer', ROLE_FOOTER, ACTION_WOULD_EXCLUDE, [0], [REGION_BOTTOM]),
            _dry_run_candidate('c-image-placeholder', 'image-placeholder', ROLE_LAYOUT_PLACEHOLDER, ACTION_WOULD_EXCLUDE, [0], [REGION_TOP]),
        ],
    }
    review_decisions = {
        'decisions': [
            _review_decision('c-approved-header', 'approved-header', 'approve_exclude'),
            _review_decision('c-approved-footer', 'approved-footer', 'approve_exclude'),
            _review_decision('c-reject-header', 'reject-header', 'reject_exclude'),
            _review_decision('c-unsure-footer', 'unsure-footer', 'unsure'),
            _review_decision('c-image-placeholder', 'image-placeholder', 'approve_exclude'),
        ],
        'summary': {
            'decision_counts': {
                'approve_exclude': 3,
                'reject_exclude': 1,
                'unsure': 1,
            },
        },
    }
    return {
        'page_summaries': page_summaries,
        'dry_run_report': dry_run_report,
        'review_decisions': review_decisions,
        'body_filtering_diff_report': {
            'summary': {
                'would_remove_block_count': 2,
                'kept_block_count': 4,
            },
        },
        'paragraph_integrity_report': {
            'summary': {
                'body_region_removed_count': 0,
            },
        },
    }


def _document_parse_hook_layout_report(inputs):
    return {
        'pages': inputs['page_summaries'],
        'header_footer_exclusion_dry_run': inputs['dry_run_report'],
    }


def _document_parse_raw_mapping_inputs():
    page_summaries = [
        {
            'page_index': 0,
            'page_number': 1,
            'text_block_count': 6,
            'region_counts': {
                REGION_TOP: 3,
                REGION_BODY: 1,
                REGION_BOTTOM: 2,
            },
            'text_blocks': [
                _mapping_summary_block(
                    0,
                    _summary_fingerprint('Approved Header', REGION_TOP),
                    REGION_TOP,
                    'Approved Header'),
                _mapping_summary_block(
                    1,
                    _summary_fingerprint('Body paragraph', REGION_BODY),
                    REGION_BODY,
                    'Body paragraph'),
                _mapping_summary_block(
                    2,
                    _summary_fingerprint('Approved Footer', REGION_BOTTOM),
                    REGION_BOTTOM,
                    'Approved Footer'),
                _mapping_summary_block(
                    3,
                    _summary_fingerprint('Rejected Header', REGION_TOP),
                    REGION_TOP,
                    'Rejected Header'),
                _mapping_summary_block(
                    4,
                    _summary_fingerprint('Unsure Footer', REGION_BOTTOM),
                    REGION_BOTTOM,
                    'Unsure Footer'),
                _mapping_summary_block(
                    5,
                    _summary_fingerprint(IMAGE_PLACEHOLDER, REGION_TOP),
                    REGION_TOP,
                    IMAGE_PLACEHOLDER),
            ],
        },
    ]
    dry_run_report = {
        'summary': {'candidate_count': 5},
        'candidates': [
            _dry_run_candidate(
                'c-approved-header',
                _summary_fingerprint('Approved Header', REGION_TOP),
                ROLE_HEADER,
                ACTION_WOULD_EXCLUDE,
                [0],
                [REGION_TOP]),
            _dry_run_candidate(
                'c-approved-footer',
                _summary_fingerprint('Approved Footer', REGION_BOTTOM),
                ROLE_FOOTER,
                ACTION_WOULD_EXCLUDE,
                [0],
                [REGION_BOTTOM]),
            _dry_run_candidate(
                'c-reject-header',
                _summary_fingerprint('Rejected Header', REGION_TOP),
                ROLE_HEADER,
                ACTION_WOULD_EXCLUDE,
                [0],
                [REGION_TOP]),
            _dry_run_candidate(
                'c-unsure-footer',
                _summary_fingerprint('Unsure Footer', REGION_BOTTOM),
                ROLE_FOOTER,
                ACTION_WOULD_EXCLUDE,
                [0],
                [REGION_BOTTOM]),
            _dry_run_candidate(
                'c-image-placeholder',
                _summary_fingerprint(IMAGE_PLACEHOLDER, REGION_TOP),
                ROLE_LAYOUT_PLACEHOLDER,
                ACTION_WOULD_EXCLUDE,
                [0],
                [REGION_TOP]),
        ],
    }
    review_decisions = {
        'decisions': [
            _review_decision(
                'c-approved-header',
                _summary_fingerprint('Approved Header', REGION_TOP),
                'approve_exclude'),
            _review_decision(
                'c-approved-footer',
                _summary_fingerprint('Approved Footer', REGION_BOTTOM),
                'approve_exclude'),
            _review_decision(
                'c-reject-header',
                _summary_fingerprint('Rejected Header', REGION_TOP),
                'reject_exclude'),
            _review_decision(
                'c-unsure-footer',
                _summary_fingerprint('Unsure Footer', REGION_BOTTOM),
                'unsure'),
            _review_decision(
                'c-image-placeholder',
                _summary_fingerprint(IMAGE_PLACEHOLDER, REGION_TOP),
                'approve_exclude'),
        ],
        'summary': {
            'decision_counts': {
                'approve_exclude': 3,
                'reject_exclude': 1,
                'unsure': 1,
            },
        },
    }
    return {
        'page_summaries': page_summaries,
        'raw_object_pages': [{
            'page_index': 0,
            'page_number': 1,
            'width': 600,
            'height': 1000,
            'raw_objects': [
                _raw_object(0, 'Approved Header', REGION_TOP),
                _raw_object(1, 'Body paragraph', REGION_BODY),
                _raw_object(2, 'Approved Footer', REGION_BOTTOM),
                _raw_object(3, 'Rejected Header', REGION_TOP),
                _raw_object(4, 'Unsure Footer', REGION_BOTTOM),
                _raw_object(5, IMAGE_PLACEHOLDER, REGION_TOP),
            ],
        }],
        'dry_run_report': dry_run_report,
        'review_decisions': review_decisions,
    }


def _summary_fingerprint(text, region):
    return make_text_fingerprint(text, y_band=region)['key']


def _raw_object(block_index, text, region):
    bbox_by_region = {
        REGION_TOP: [50.0, 20.0, 300.0, 40.0],
        REGION_BODY: [50.0, 400.0, 520.0, 420.0],
        REGION_BOTTOM: [50.0, 960.0, 300.0, 980.0],
    }
    bbox = list(bbox_by_region[region])
    bbox[1] += block_index * 0.2
    bbox[3] += block_index * 0.2
    return {
        'raw_object_id': f'raw-{block_index}',
        'object_index': block_index,
        'block_index': block_index,
        'object_type': 'Line',
        'fingerprint': _summary_fingerprint(text, region),
        'region': region,
        'text': text,
        'bbox': bbox,
    }


def _mapping_summary_block(block_index, fingerprint, region, text):
    block = _raw_object(block_index, text, region)
    return {
        'block_index': block_index,
        'fingerprint': fingerprint,
        'normalized_text': normalize_page_number(text).lower(),
        'region': region,
        'text': text,
        'bbox': block['bbox'],
    }


class _FakePage:

    def __init__(self, page_id):
        self.id = page_id


class _FakeRawPage:

    def __init__(self, raw_objects):
        self.width = 600
        self.height = 1000
        self.blocks = [_FakeRawBlock(raw_object) for raw_object in raw_objects]


class _FakeRawBlock:

    def __init__(self, raw_object):
        self.text = raw_object['text']
        self.bbox = raw_object['bbox']
        self.spans = []


def _summary_block(block_index, fingerprint, region, text):
    return {
        'block_index': block_index,
        'fingerprint': fingerprint,
        'region': region,
        'text': text,
        'bbox': [50.0, 50.0 + block_index * 20.0, 520.0, 65.0 + block_index * 20.0],
    }


def _dry_run_candidate(candidate_id, fingerprint, role, action, pages, regions):
    return {
        'candidate_id': candidate_id,
        'fingerprint': fingerprint,
        'proposed_role': role,
        'action': action,
        'affected_pages': pages,
        'regions': regions,
    }


def _review_decision(candidate_id, fingerprint, manual_decision):
    return {
        'candidate_id': candidate_id,
        'fingerprint': fingerprint,
        'manual_decision': manual_decision,
    }


def _insertion_points_by_id(analysis):
    return {
        point['candidate_id']: point
        for point in analysis['insertion_points']
    }


def _dry_run_by_fingerprint(report):
    return {
        candidate['fingerprint']: candidate
        for candidate in report['header_footer_exclusion_dry_run']['candidates']
    }


def _review_markdown(candidate_id, fingerprint, role, action, decision):
    markers = {
        'approve_exclude': '[ ]',
        'reject_exclude': '[ ]',
        'unsure': '[ ]',
    }
    markers[decision] = '[x]'
    return '\n'.join([
        f'### {candidate_id} | {role} | {action}',
        f'- fingerprint: `{fingerprint}`',
        '- human_decision: '
        f'approve_exclude: {markers["approve_exclude"]}    '
        f'reject_exclude: {markers["reject_exclude"]}    '
        f'unsure: {markers["unsure"]}',
    ])


def _unsafe_diff_report_for_removed_blocks(pages, removed_keys):
    removed_by_page = []
    for page in pages:
        page_removed = []
        page_index = page['page_index']
        for block in page['text_blocks']:
            if (page_index, block['block_index']) in set(removed_keys):
                page_removed.append({
                    'page_index': page_index,
                    'page_number': page_index + 1,
                    'block_index': block['block_index'],
                    'candidate_id': 'unsafe-body',
                    'fingerprint': block['fingerprint'],
                    'proposed_role': 'header',
                    'manual_decision': 'reject_exclude',
                    'explicit_approval': False,
                    'region': block['region'],
                    'reason': 'unsafe synthetic removal',
                    'short_preview': block['text'],
                })
        removed_by_page.append({
            'page_index': page_index,
            'page_number': page_index + 1,
            'removed_count': len(page_removed),
            'blocks': page_removed,
        })

    return {
        'enabled': True,
        'summary': {
            'original_block_count': sum(len(page['text_blocks']) for page in pages),
        },
        'removed_blocks_by_page': removed_by_page,
        'kept_blocks_by_page': [],
        'removed_blocks_by_candidate': [],
        'retained_candidates': [],
        'safety': {'warnings': []},
    }


if __name__ == '__main__':
    unittest.main()
