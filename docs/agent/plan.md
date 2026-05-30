# PDF-to-DOCX 고품질 변환 구현 계획

## Goal

PDF를 DOCX로 변환할 때 document structure와 layout을 더 잘 보존한다. 우선 header/footer/body 분리와 cross-page paragraph continuation 분석 기반을 만들고, 이후 실제 DOCX 생성에 단계적으로 연결한다.

## Non-goals

- 지금 단계에서 full PDF-to-DOCX converter를 새로 작성하지 않는다.
- 지금 단계에서 production source code를 수정하지 않는다.
- 지금 단계에서 의존성을 추가하지 않는다.
- OCR pipeline을 바로 구현하지 않는다.
- existing table/image/vector extraction을 넓게 refactor하지 않는다.
- visual-pixel reconstruction만 목표로 삼지 않는다.
- 기존 공개 API/CLI 동작을 급하게 바꾸지 않는다.

## Current Architecture Summary

현재 구조는 이미 PDF-to-DOCX 변환 pipeline을 갖고 있다.

```text
Converter.convert
  -> load_pages
  -> parse_document
       -> Pages.parse
          -> RawPageFitz extraction
          -> cleanup/font processing
          -> Pages._parse_document  # currently TODO
          -> margin/section parsing
  -> parse_pages
       -> Page.parse
          -> Layout.parse
             -> table detection
             -> paragraph grouping
             -> spacing/style parsing
  -> make_docx
       -> Page.make_docx
       -> Sections/Blocks/Table/Image/Text make_docx
```

기존 codebase는 line/block/table/image/shape coordinate 기반으로 layout을 재구성한다. 다만 document-level header/footer 분석과 cross-page paragraph continuation은 사실상 없다.

## Proposed Architecture

단계적으로 다음 분석 layer를 추가한다.

- Document-level layout analysis
  - `Pages._parse_document()` 주변에 header/footer/body region 후보 분석을 넣을 수 있다.
  - 초기에는 실제 body removal이 아니라 debug annotation/report만 생성한다.
- Repeated element clustering
  - text/image/shape의 normalized fingerprint, y-band, style을 기반으로 반복 요소를 찾는다.
- Body region inference
  - high-confidence repeated top/bottom candidates를 제외한 text bbox 분포로 body region을 추정한다.
- Paragraph continuation analysis
  - page parse 이후 last body text block과 next page first body text block 사이 continuation score를 계산한다.
- DOCX integration
  - 충분히 검증된 뒤 header/footer를 Word section header/footer로 이동하고, continuation paragraph는 하나의 DOCX paragraph로 생성한다.

## Files/Directories Likely To Change

구현 승인 후 변경 가능성이 높은 위치:

- `pdf2docx/page/Pages.py`
  - document-level analysis hook.
  - 현재 `Pages._parse_document()`가 TODO.
- `pdf2docx/page/Page.py`
  - header/footer/body annotation store/restore 확장 가능성.
- `pdf2docx/layout/Blocks.py`
  - body/header/footer 분류 결과를 paragraph grouping 입력에 반영하는 later phase.
- `pdf2docx/text/TextBlock.py`, `pdf2docx/text/Lines.py`
  - continuation signal과 paragraph split/merge 근거 기록 가능성.
- `pdf2docx/converter.py`
  - debug report 또는 feature flag 설정 추가 가능성.
- 새 module 후보:
  - `pdf2docx/page/LayoutAnalyzer.py`
  - 또는 `pdf2docx/layout/analysis.py`
  - 또는 `pdf2docx/semantic/` 계층.
- `test/test.py`
  - pure classifier unit tests, fixture-based regression tests.
- `test/samples/`
  - header/footer와 page-break paragraph fixture 추가 가능성.
- `docs/agent/`
  - 구현 로그와 검증 기록.

## Files/Directories That Should Not Be Changed Casually

- `setup.py`, `requirements.txt`
  - 의존성/패키징 변경은 별도 승인 필요.
- `pdf2docx/common/docx.py`
  - OpenXML helper는 영향 범위가 크므로 later phase에서만 좁게 수정.
- `pdf2docx/table/`
  - table parsing은 복잡하고 회귀 위험이 크므로 header/footer 제거가 table 입력에 미치는 영향부터 확인.
- `pdf2docx/image/`
  - image/color/rotation issue regression이 있으므로 초기 phase에서는 annotation만.
- `pdf2docx/shape/`
  - table/text style detection과 얽혀 있어 broad refactor 금지.
- `.github/workflows/`
  - CI 변경은 기능 구현과 분리.
- 기존 `test/samples/` 파일
  - 기존 fixture 수정 대신 새 fixture 추가가 안전하다.

## Minimal Phase 1 Scope

Phase 1은 아주 작고 안전하게 내부 layout analysis foundation만 만든다.

목표:

- PDF page를 기존 cleanup 이후 structured analysis object/debug dict로 요약한다.
- page별 top/body/bottom candidate region을 추정한다.
- 반복 header/footer 후보를 confidence와 signal로 표시한다.
- page 간 paragraph continuation 후보를 debug report에 표시한다.
- 실제 DOCX output은 바꾸지 않는다.
- 기존 conversion behavior는 유지한다.

권장 구현 단위:

1. 분석용 pure utility 추가
   - input: cleaned raw pages 또는 parsed page summary.
   - output: JSON-serializable analysis report.
   - production conversion에는 기본적으로 영향 없음.

2. Text normalization/fingerprint 추가
   - whitespace normalize.
   - page number placeholder.
   - style key와 y-band key 계산.

3. Header/footer candidate classifier 추가
   - top/bottom band 후보 추출.
   - repeated element cluster 계산.
   - confidence와 signal 기록.

4. Body region estimator 추가
   - high-confidence repeated top/bottom 후보를 제외한 bbox quantile 기반.
   - 기존 `RawPage.calculate_margin()` 값은 변경하지 않음.

5. Paragraph continuation candidate 추가
   - page N last body text block과 page N+1 first body text block 비교.
   - punctuation, position, indentation, font/style, boundary, hyphenation, region label signal 기록.
   - 실제 paragraph merge는 하지 않음.

6. Debug JSON/report 출력
   - 기존 `debug_page`/`serialize`와 충돌하지 않게 별도 opt-in.
   - CLI 공개 여부는 최소화. 먼저 internal/test helper로 충분하다.

7. 작은 테스트 추가
   - 가능하면 pure function 중심 unit test.
   - 기존 PDF conversion output은 Phase 1에서 변경하지 않는다.

## Later Phases

### Phase 2: Header/Footer Integration

- high-confidence header/footer 후보를 `Page.header`, `Page.footer` 또는 별도 annotation에 반영.
- body parse 입력에서 header/footer 후보 제외를 opt-in으로 적용.
- existing sample regression 확인.

### Phase 3: DOCX Header/Footer Generation

- Word section header/footer에 high-confidence repeated content를 생성.
- first-page, odd/even, section-specific header/footer 정책 추가.
- header/footer image/logo 처리 검토.

### Phase 4: Cross-page Paragraph Merge

- continuation 후보가 high-confidence인 경우 실제 DOCX paragraph를 하나로 연결.
- page break/section break policy를 semantic mode로 분리.
- over-merge 방지 fixture 추가.

### Phase 5: Semantic Quality Evaluation

- visual similarity 외에 structural metrics 추가.
- generated DOCX XML inspection으로 paragraph/header/footer/table 구조 검증.
- header/footer와 paragraph continuation fixture 확장.

### Phase 6: Optional Advanced Features

- list detection 복구 또는 개선.
- repeated table header row detection.
- footnote/endnote 후보 분리.
- OCR은 별도 승인 후 독립 설계.

## Test Strategy

Phase 1:

- pure utility tests:
  - text normalization.
  - page number pattern placeholder.
  - repeated element clustering.
  - top/body/bottom region classification.
  - paragraph continuation scoring.
- fixture-light tests:
  - synthetic line/block objects 또는 minimal dict로 시작.
  - PDF rendering 없이 빠르게 실행 가능하게 한다.
- existing regression:
  - `pytest -v ./test/test.py::TestConversion`
  - Phase 1은 output 변경이 없어야 한다.

Later phases:

- fixture PDF 추가 후 end-to-end tests.
- DOCX XML inspection tests.
- visual similarity tests where LibreOffice/Word available.

## Sample Fixture Strategy

새 fixture는 작고 의도가 분명해야 한다.

- repeated header + page number footer + body paragraphs.
- first-page header exception.
- odd/even page header variation.
- paragraph continuing across page break without sentence-ending punctuation.
- paragraph ending at page bottom with punctuation, followed by unrelated next paragraph.
- hyphenated word split across page.
- footer-like footnote that should not be dropped.
- table near page bottom that should not be classified as footer.

가능하면 기존 의존성인 PyMuPDF로 test PDF를 생성해 새 dependency를 피한다. fixture 생성 script를 둘지는 별도 결정이 필요하다.

## Quality Evaluation Strategy

- Debug report review:
  - candidate region, confidence, signal이 사람이 읽기 쉬워야 한다.
- Structural assertions:
  - header/footer text가 body paragraph에 남지 않았는지.
  - continuation paragraph가 하나의 DOCX paragraph인지.
  - unrelated paragraphs가 merge되지 않았는지.
- Visual regression:
  - 기존 SSIM-style test를 유지하되 semantic 변경 후 기대치를 다시 검토한다.
- Manual review:
  - phase마다 대표 PDF를 DOCX로 열어 editing behavior를 확인한다.

## Risks

- header/footer 제거가 margin/section/table detection을 바꿀 수 있다.
- repeated text가 header/footer가 아니라 body 반복 문구일 수 있다.
- first-page, odd/even, section-specific header/footer를 단순 repeat logic으로 놓칠 수 있다.
- paragraph continuation merge가 잘못되면 semantic quality가 크게 나빠진다.
- 현재 page-per-section DOCX generation은 paragraph continuation과 구조적으로 충돌한다.
- visual fidelity와 editable semantic structure가 충돌할 수 있다.
- test 환경에서 Word/LibreOffice 유무에 따라 품질 검증 가능 범위가 달라진다.

## Rollback Strategy

- Phase 1은 opt-in debug analysis만 추가하여 기존 conversion output을 바꾸지 않는다.
- 새 설정값은 기본 off로 둔다.
- 기존 public API와 CLI behavior를 유지한다.
- 각 phase는 작은 commit 단위로 나누고, 실패 시 해당 phase commit만 되돌릴 수 있게 한다.
- high-risk integration 전후로 `Converter.serialize()` 또는 새 debug report를 비교해 layout 변화 범위를 확인한다.

## Approval Gate

이 문서 이후에는 사용자 승인 전 production source code, dependencies, broad refactor, commit, push를 진행하지 않는다.

