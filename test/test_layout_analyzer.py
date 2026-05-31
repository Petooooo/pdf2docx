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
build_reviewed_header_footer_filter_report = LayoutAnalyzer.build_reviewed_header_footer_filter_report
build_layout_analysis_report = LayoutAnalyzer.build_layout_analysis_report
find_paragraph_continuation_candidates = LayoutAnalyzer.find_paragraph_continuation_candidates
make_text_fingerprint = LayoutAnalyzer.make_text_fingerprint
normalize_page_number = LayoutAnalyzer.normalize_page_number
normalize_text = LayoutAnalyzer.normalize_text
parse_exclusion_review_markdown = LayoutAnalyzer.parse_exclusion_review_markdown
text_block_records = LayoutAnalyzer.text_block_records


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


if __name__ == '__main__':
    unittest.main()
