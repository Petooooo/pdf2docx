# PDF-to-DOCX 고품질 변환 설계 초안

## 설계 목표

PDF의 시각적 layout을 최대한 보존하되, DOCX 결과물이 편집 가능한 문서 구조를 갖도록 한다. 특히 header/footer/body 분리, 반복 header/footer detection, page break로 끊긴 paragraph continuation 복원, table/image/section/style 보존을 함께 다룬다.

## 기본 원칙

- 기존 pipeline을 보존하면서 document-level analysis를 단계적으로 추가한다.
- Phase 1은 full converter가 아니라 내부 layout analysis와 debug report를 우선 만든다.
- 새 heuristic은 confidence score와 근거 signal을 함께 남긴다.
- header/footer 제거, paragraph merge, page break suppression은 모두 되돌릴 수 있는 annotation 기반으로 시작한다.
- 기존 table/image/shape/DOCX XML helper를 넓게 refactor하지 않는다.

## 전체 변환 Pipeline 제안

현재 pipeline을 다음처럼 확장하는 방향이 자연스럽다.

```text
PDF input
  -> PyMuPDF extraction
  -> RawPage cleanup
  -> document-level layout analysis
       - page region inference
       - repeated header/footer candidate detection
       - body region estimation
  -> page-level parse
       - section/column detection
       - table/image detection
       - paragraph grouping
  -> cross-page semantic analysis
       - paragraph continuation candidates
       - page break policy
  -> DOCX generation
       - body paragraphs/tables/images
       - section/header/footer where confidence is high
       - debug metadata/report when requested
```

현재 `Pages._parse_document()`가 비어 있으므로, header/footer와 body region 후보 분석을 넣을 1차 hook으로 적합하다. 다만 paragraph continuation은 `Page.parse()` 이후 `TextBlock`이 만들어져야 판단하기 쉬우므로 별도 post-page-parse hook이 필요할 가능성이 높다.

## PDF Page Model

기존 `Page`, `RawPage`, `BasePage`를 유지하되 분석용 model 또는 dict를 별도로 둔다.

필수 필드:

- `page_index`
- `width`, `height`, `rotation`
- `raw_lines`: cleanup 이후의 `Line` 단위 정보
- `raw_shapes`, `raw_images`
- `candidate_regions`
  - `header_band`
  - `body_region`
  - `footer_band`
- `classified_elements`
  - `header_candidates`
  - `body_candidates`
  - `footer_candidates`
  - `repeated_elements`
- `page_margin`
- `confidence`
- `signals`

초기에는 `Page.store()` 구조를 바로 바꾸기보다 debug JSON 전용 구조로 시작하는 것이 안전하다.

## Text Block Model

기존 `TextBlock`은 DOCX 생성까지 직접 연결되어 있으므로, 분석용 wrapper를 두는 편이 안전하다.

분석용 text block 필드:

- `page_index`
- `bbox`
- `text`
- `normalized_text`
- `line_count`
- `first_line_bbox`, `last_line_bbox`
- `font_family_stats`
- `font_size_stats`
- `style_flags`
- `alignment_features`
- `left_boundary`, `right_boundary`
- `region_label`: `header`, `body`, `footer`, `unknown`
- `repeat_key`
- `is_page_number_candidate`
- `confidence`

## Line Model

기존 `Line`/`TextSpan` 정보를 요약해 paragraph와 header/footer signal 계산에 사용한다.

필수 signal:

- bbox와 baseline 위치
- raw text와 normalized text
- span별 font family, size, bold/italic flag, color
- line height와 row gap
- left/right boundary
- tab stop 또는 indentation 후보
- image span 포함 여부
- text direction
- source parent id 또는 source block 순서

## Paragraph Reconstruction Model

### Page 내부 paragraph

기존 로직:

- `Blocks._join_lines_vertically()`가 line spacing과 vertical distance로 `TextBlock`을 만든다.
- `Lines.split_vertically_by_text()`가 punctuation과 free space로 paragraph split을 수행한다.

개선 방향:

- 기존 결과를 유지하되, 각 split/merge 판단에 score와 signal을 남긴다.
- list, heading, caption, table-adjacent text를 별도 후보로 표시한다.
- paragraph split 여부를 단일 threshold가 아니라 여러 signal의 weighted score로 판단한다.

### Page 간 paragraph continuation

cross-page merge 후보는 `previous_page.last_body_text_block`과 `next_page.first_body_text_block` 사이 edge로 표현한다.

추천 score signal:

- 이전 block이 page body region의 하단 가까이에 있는가.
- 다음 block이 page body region의 상단 가까이에 있는가.
- 이전 block이 footer region이 아닌가.
- 다음 block이 header region이 아닌가.
- 이전 block text가 sentence-ending punctuation으로 끝나지 않는가.
- 이전 line 끝에 hyphenation이 있는가.
- hyphen 뒤 다음 page 첫 글자가 lower-case 또는 같은 단어 continuation처럼 보이는가.
- font family, font size, bold/italic, color가 유사한가.
- line spacing과 row gap이 유사한가.
- left/right boundary가 유사한가.
- paragraph indentation이 continuation과 호환되는가.
- 다음 page first line indentation이 새 paragraph 시작처럼 과도하게 들여쓰기되어 있지 않은가.
- 두 block 사이에 table/image/heading/page number barrier가 없는가.

merge를 막는 signal:

- 이전 block이 heading, caption, list item, table cell, footer 후보인 경우.
- 다음 block이 heading, list start, chapter title, header 후보인 경우.
- font size/style이 크게 다른 경우.
- left/right boundary가 column 또는 margin 단위로 달라진 경우.
- 이전 block이 문장 종료 punctuation으로 끝나고 마지막 줄에 충분한 right-side free space가 있는 경우.
- 다음 block 첫 줄이 강한 first-line indent를 가진 경우.
- page break가 section break, orientation/page size change, column count change와 함께 발생한 경우.

초기 정책은 conservative해야 한다. score가 충분히 높을 때만 continuation으로 표시하고, 실제 DOCX paragraph merge는 나중 phase에서 적용한다.

## Header Detection Strategy

header candidate는 page top band와 body region 밖 요소에서 시작한다.

주요 signal:

- 여러 page에서 반복되는 text.
- 반복되는 y-coordinate band.
- 반복되는 font family, font size, style.
- page number, date, document title, chapter title pattern.
- normal body margin 밖 또는 body top보다 위에 위치.
- adjacent pages 사이의 text/position/style similarity.
- odd/even page에서 서로 다른 running header pattern.
- first-page exception.
- section boundary 이후 바뀌는 running header.

추천 절차:

1. page별 top candidate band를 만든다.
   - 단순히 page height의 상위 10-15%만 보지 말고, actual body text y-distribution의 상단 quantile도 함께 본다.
2. line/block text를 normalize한다.
   - whitespace normalize.
   - page number를 placeholder로 치환.
   - 날짜/숫자 token을 선택적으로 placeholder화.
3. `(normalized_text, y_band, style_key)` fingerprint를 만든다.
4. 전체 page, adjacent pages, odd/even pages, section-like ranges별로 cluster를 만든다.
5. cluster support, position stability, style stability, body distance로 confidence를 계산한다.
6. high-confidence header는 body parse에서 제외하거나 별도 annotation으로 표시한다.

## Footer Detection Strategy

footer는 header와 유사하되 page bottom band와 page number signal의 비중이 더 높다.

주요 signal:

- 반복 text 또는 반복 page number pattern.
- 반복 y-coordinate band.
- page bottom에 가까운 위치.
- body bottom보다 아래에 위치.
- font/style 안정성.
- adjacent/odd/even similarity.
- first-page/section-specific exception.

주의점:

- footnote는 footer와 다르다. footnote는 body semantic content일 수 있으므로 단순 bottom 위치만으로 제거하면 안 된다.
- table이 page 하단까지 내려가는 경우 footer와 충돌할 수 있다.
- page number만 있는 footer는 text normalization 후 반복 cluster로 잡아야 한다.

## Repeated Element Detection

반복 요소 detection은 header/footer에 한정하지 말고 공통 utility로 둔다.

입력:

- page index
- normalized text
- bbox
- y band
- style key
- element type: text/image/shape

cluster 기준:

- exact normalized text match.
- page number placeholder match.
- fuzzy text similarity.
- y-coordinate band overlap.
- x-boundary similarity.
- style similarity.
- page range support.

출력:

- `repeat_group_id`
- `support_pages`
- `pattern_type`: `running_header`, `running_footer`, `page_number`, `logo`, `unknown_repeat`
- `confidence`
- `exceptions`

반복 logo/image도 header/footer의 일부일 수 있으므로 image bbox와 page band 반복성도 추적한다.

## Page Margin/Body Region Detection

현재 `RawPage.calculate_margin()`은 cleanup된 blocks와 shapes의 bbox를 기준으로 margin을 계산한다. header/footer가 body에 섞여 있으면 margin이 왜곡될 수 있다.

제안:

- Phase 1에서는 기존 margin을 바꾸지 않고 별도 `estimated_body_region`만 debug output으로 낸다.
- body region 추정은 다음 정보를 조합한다.
  - header/footer high-confidence element 제외 후 text bbox quantile.
  - repeated top/bottom band 제외.
  - left/right text boundary의 mode 또는 quantile.
  - table/image bbox가 body 영역을 확장하는지 여부.
- 이후 phase에서만 `calculate_margin()` 입력 또는 결과에 반영한다.

## Reading Order Reconstruction

현재 reading order는 `Collection.sort_in_reading_order_plus()`, row/column grouping, section/column detection에 의존한다.

개선 방향:

- region order: header -> body -> footer를 명확히 분리한다.
- body 내부는 section/column/table 흐름을 유지한다.
- header/footer로 분류된 element가 body table/paragraph 후보에 들어가지 않도록 한다.
- multi-column page에서는 column boundary 변화와 cross-page continuation 판단을 분리한다.
- rotated/vertical text는 현재 지원 범위를 유지하되, continuation merge에서는 기본적으로 제외하는 것이 안전하다.

## Table Handling Strategy

초기에는 기존 table parser를 유지한다.

추가해야 할 정책:

- header/footer 후보 line이 table detection 입력에 들어가 table로 오인되지 않게 한다.
- table 내부 text는 page-level paragraph continuation 대상에서 제외한다.
- page를 넘어가는 table continuation은 paragraph continuation과 별도 문제로 둔다.
- stream table detection은 footer page number 또는 two-column running header를 table로 오인할 수 있으므로 debug signal을 남긴다.
- later phase에서 repeated table header row detection은 별도 feature로 다룬다.

## Image Handling Strategy

현재 image extraction은 상당히 복잡하므로 초기 변경 범위에서 제외한다.

추가 설계:

- top/bottom band에 반복 출현하는 logo/image는 header/footer repeated element 후보로 표시한다.
- body image는 기존 inline/floating image 처리 유지.
- header/footer image를 실제 DOCX header/footer에 넣는 것은 later phase로 미룬다.
- image bbox가 body region을 강하게 차지하면 paragraph continuation merge를 막는 barrier로 사용한다.

## Section/Page-Break Handling Strategy

현재 `Page.make_docx()`는 page마다 새 DOCX section을 만든다. 이는 PDF와 비슷한 page break를 만들기 쉽지만, page break로 끊긴 paragraph를 하나의 DOCX paragraph로 복원하기 어렵다.

단계별 전략:

- Phase 1:
  - page break와 DOCX generation은 건드리지 않는다.
  - continuation candidate만 debug report에 남긴다.
- Later phase:
  - semantic mode를 별도 옵션으로 두고, continuation confidence가 높은 page boundary에서는 paragraph split을 억제한다.
  - page size/margin/column count가 바뀌는 boundary는 section break를 유지한다.
  - 단순 PDF pagination으로 인한 break는 Word가 자연스럽게 reflow하도록 처리한다.
  - visual fidelity mode와 semantic editability mode의 tradeoff를 명시한다.

## DOCX Generation Strategy

장기 목표:

- body content는 flow layout으로 생성한다.
- high-confidence header/footer는 Word section header/footer에 배치한다.
- paragraph continuation은 하나의 DOCX paragraph로 생성한다.
- table은 기존 `python-docx` table 생성 로직을 유지한다.
- image는 body/header/footer region에 따라 anchor 정책을 달리한다.

주의:

- `python-docx`는 header/footer, section, floating image 지원이 제한적이므로 `common/docx.py`의 XML helper 확장이 필요할 수 있다.
- 실제 DOCX header/footer 생성은 section break 정책과 같이 설계해야 한다.
- paragraph merge는 `TextBlock`을 직접 합치거나, DOCX generation 단계에서 continuation flag를 보고 같은 paragraph에 run을 이어 붙이는 방식 중 하나를 선택해야 한다.

## Style Mapping Strategy

기존 mapping:

- span font family, size, color.
- underline/highlight/hyperlink.
- paragraph alignment, indentation, spacing, line spacing.
- table border/shading/merge.

추가 mapping 제안:

- repeated header/footer style을 Word header/footer paragraph style로 분리.
- inferred heading/caption/list style은 confidence가 높을 때만 적용.
- paragraph continuation 시 이전 paragraph style을 유지하고, 다음 page 첫 line의 first-line indent는 merge 판단에만 사용한다.
- page/section margins은 body region 분석 결과를 직접 덮어쓰기 전에 debug로 비교한다.

## Quality Scoring/Validation Strategy

기존 visual similarity는 유지하되 semantic 평가를 추가해야 한다.

추천 metric:

- header/footer classification precision/recall.
- body text에 header/footer text가 섞이지 않았는지.
- paragraph continuation candidate accuracy.
- paragraph over-merge rate.
- paragraph over-split rate.
- reading order stability.
- table cell text preservation.
- image count/bbox approximation.
- DOCX XML structural sanity:
  - paragraph count.
  - header/footer part 존재 여부.
  - section break count.
  - table count.

Phase 1 debug JSON 예시:

```json
{
  "pages": [
    {
      "page_index": 0,
      "body_region": [72.0, 90.0, 540.0, 720.0],
      "header_candidates": [],
      "footer_candidates": [],
      "continuation_to_next": {
        "candidate": true,
        "confidence": 0.82,
        "signals": {
          "previous_near_bottom": true,
          "next_near_top": true,
          "punctuation_open": true,
          "font_match": true,
          "boundary_match": true
        }
      }
    }
  ]
}
```

## 제한과 Tradeoffs

- PDF에는 logical paragraph, header/footer semantic이 명시되지 않는 경우가 많아 heuristic이 필요하다.
- visual fidelity와 semantic editability는 자주 충돌한다.
- page마다 section을 만들면 visual fidelity는 좋아질 수 있지만 paragraph continuation에는 불리하다.
- header/footer를 너무 빨리 제거하면 table/section/margin 분석이 흔들릴 수 있다.
- repeated text가 항상 header/footer는 아니다. 반복되는 legal clause, table header, watermark, sidebar가 있을 수 있다.
- scanned PDF/OCR은 현재 별도 큰 범위다.
- first-page, odd/even, section-specific header/footer는 단순 global repeat만으로 부족하다.

