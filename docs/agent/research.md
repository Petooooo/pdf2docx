# PDF-to-DOCX 고품질 변환 기능 초기 조사

## 범위와 전제

- 이 문서는 구현 전 조사 결과만 기록한다.
- production 소스, 의존성, 패키징, 테스트 코드는 수정하지 않았다.
- 저장소 내 프로젝트별 `AGENTS.md`는 발견되지 않았고, 전역 `~/.codex/AGENTS.md` 지침을 따랐다.
- 사용자의 핵심 목표는 단순 텍스트 추출이 아니라, header/footer/body 분리와 page break로 끊긴 문단 복원까지 포함한 편집 가능한 DOCX 생성이다.

## 프로젝트 개요

- 프로젝트 유형: Python 패키지 및 CLI 라이브러리.
- 주 언어: Python.
- 패키징/빌드: `setup.py`, `requirements.txt`, `Makefile`.
- 패키지 매니저: pip 기반. `pyproject.toml`, lock file, Poetry/uv 설정은 없다.
- 공개 API:
  - `pdf2docx.Converter`
  - `pdf2docx.parse`
- CLI entry point:
  - `setup.py`의 `console_scripts`: `pdf2docx=pdf2docx.main:main`
  - CLI 구현은 `fire.Fire(PDF2DOCX)` 기반이다.
- Python 버전:
  - `setup.py`는 `python_requires=">=3.10"`이다.
  - README badge에는 `>=3.6`으로 표시되어 있어 문서와 패키징 정보가 불일치한다.
- 저장소 상태:
  - 현재 브랜치: `master`
  - 작업 시작 시 git status는 clean이었다.

## 저장소 구조 요약

```text
.
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── docs/
│   ├── api/
│   ├── quickstart*.rst
│   ├── techdoc.rst
│   └── ...
├── pdf2docx/
│   ├── common/
│   ├── font/
│   ├── gui/
│   ├── image/
│   ├── layout/
│   ├── page/
│   ├── shape/
│   ├── table/
│   ├── text/
│   ├── converter.py
│   └── main.py
├── test/
│   ├── samples/
│   ├── Makefile
│   └── test.py
├── requirements.txt
├── setup.py
└── Makefile
```

## 관련 파일과 디렉터리

- `pdf2docx/converter.py`
  - 전체 변환 흐름의 중심 클래스 `Converter`.
  - `convert() -> parse() -> make_docx()` 흐름을 제공한다.
  - 기본 설정값에 layout, table, image, paragraph 관련 threshold가 모여 있다.
- `pdf2docx/main.py`
  - CLI wrapper.
  - `convert`, `debug`, `table`, `gui` 명령을 노출한다.
- `pdf2docx/page/`
  - PDF page 추출, document/page-level 분석, page layout 저장/복원 담당.
  - `Pages._parse_document()`는 header/footer 분석 자리지만 현재 `TODO`이며 빈 문자열만 반환한다.
- `pdf2docx/layout/`
  - section, column, block 흐름 layout 분석.
  - table detection 이후 paragraph grouping과 spacing 계산이 이어진다.
- `pdf2docx/text/`
  - `Line`, `Lines`, `TextBlock`, `TextSpan`, `Char` 모델.
  - 현재 paragraph reconstruction은 주로 column 내부 line grouping 기준이다.
- `pdf2docx/table/`
  - lattice table과 stream table 구조 분석 및 DOCX table 생성.
- `pdf2docx/image/`
  - raster image, vector graphic clipping, floating/inline image 처리.
- `pdf2docx/shape/`
  - drawing path, stroke, fill, hyperlink, table border, underline, highlight 후보 처리.
- `pdf2docx/font/Fonts.py`
  - embedded font 분석과 line height 보정.
- `pdf2docx/common/docx.py`
  - `python-docx`가 직접 지원하지 않는 section, table, hyperlink, floating image XML 조작.
- `test/test.py`
  - 변환, table extraction, 일부 image issue regression, visual similarity 기반 품질 테스트.
- `test/samples/`
  - text/table/image/section 관련 PDF 샘플 다수.

## 현재 변환 흐름

현재 핵심 pipeline은 다음 순서다.

1. `Converter.convert()`
   - `default_settings`를 구성하고, 단일 프로세스 또는 multi-processing 경로를 선택한다.

2. `Converter.load_pages()`
   - `fitz.Document` 인증을 처리한다.
   - 전체 페이지 수만큼 `Page(id=i, skip_parsing=True)`를 만들고, 변환 대상 page만 `skip_parsing=False`로 바꾼다.

3. `Converter.parse_document()`
   - `Pages.parse(fitz_doc, **settings)`를 호출한다.

4. `Pages.parse()`
   - `Fonts.extract(fitz_doc)`로 font family와 line height 정보를 수집한다.
   - 각 대상 page에 대해 `RawPageFactory.create(..., backend='PyMuPDF')`로 `RawPageFitz`를 만든다.
   - `RawPageFitz.extract_raw_dict()`에서 PyMuPDF 기반 raw layout을 추출한다.
   - `RawPage.clean_up()`에서 text block을 line 단위로 풀고, invalid/overlap/floating image/shape를 정리한다.
   - `RawPage.process_font()`로 `TextSpan` font와 line height를 보정한다.
   - `Pages._parse_document(raw_pages)`를 호출하지만 현재 header/footer 분석은 구현되어 있지 않다.
   - 각 page별로 `RawPage.calculate_margin()`과 `RawPage.parse_section()`을 수행한다.

5. `Converter.parse_pages()`
   - 각 `Page.parse()`를 호출한다.
   - `Page.parse()`는 `Sections.parse()`로 이어지고, 결국 `Layout.parse()`가 column/cell 단위로 table과 paragraph를 분석한다.

6. `Layout.parse()`
   - `_parse_table()`:
     - `TablesConstructor.lattice_tables()`
     - `TablesConstructor.stream_tables()`
   - `_parse_paragraph()`:
     - `Blocks.parse_block()`로 line을 `TextBlock`으로 묶는다.
     - `Blocks.parse_text_format()`로 underline/highlight/hyperlink 등 text style을 적용한다.
     - `Blocks.parse_spacing()`으로 paragraph spacing, indent, alignment, line spacing을 계산한다.
   - table cell 내부 layout도 재귀적으로 parse한다.

7. `Converter.make_docx()`
   - `python-docx.Document()`를 만들고 parsed page를 순회한다.
   - `Page.make_docx()`는 page마다 새 section 또는 첫 section을 만들고 page size/margin을 설정한다.
   - `Sections -> Section -> Column -> Blocks` 순서로 paragraph/table/image를 DOCX로 만든다.

## PDF/DOCX/Layout 관련 기존 의존성

| 의존성 | 사용 위치 | 역할 |
| --- | --- | --- |
| `PyMuPDF>=1.26.7` | `converter.py`, `RawPageFitz.py`, image/shape/font/test | PDF open, text rawdict, text trace, images, drawings, links, pixmap, fonts |
| `python-docx>=0.8.10` | `converter.py`, `common/docx.py`, text/table/layout/page | DOCX 문서, paragraph, run, table, section 생성 |
| `fonttools>=4.24.0` | `font/Fonts.py` | embedded font family와 line height ratio 추출 |
| `numpy>=1.17.2` | image/test/algorithm | image array, visual similarity 계산 |
| `opencv-python-headless>=4.5` | image/algorithm/test | vector graphic contour detection, image rotation, SSIM-style comparison |
| `fire>=0.3.0` | `main.py` | CLI command binding |
| `lxml` | `common/docx.py`에서 python-docx 내부 의존으로 사용 | OpenXML 직접 조작 |

테스트용으로는 CI에서 `pytest`, `pytest-cov`를 설치한다. `docx2pdf`는 Windows 경로에서 동적으로 설치되며, Linux/macOS 품질 검증에는 외부 `libreoffice` 실행 파일이 필요하다.

## 이미 존재하는 기능

### PDF text/layout extraction

- `RawPageFitz._preprocess_text()`가 `page.get_text('rawdict', ...)`로 text block, line, span, char 좌표를 가져온다.
- `page.get_texttrace()`로 hidden text를 걸러내려는 로직이 있다.
- text direction, rotation matrix, bbox 연산은 `Element`, `Line`, `Collection` 계층에서 처리한다.

### Image extraction

- `ImagesExtractor.extract_images()`는 `page.get_images()`, `page.get_image_rects()`, pixmap 복구, CMYK/RGB 변환, per-image rotation 일부를 처리한다.
- vector graphic은 `Paths.to_shapes_and_images()`와 OpenCV contour detection으로 bitmap clipping한다.
- floating image 후보는 `Blocks._identify_floating_images()`에서 line connectivity로 분리한다.

### Table detection

- lattice table:
  - explicit stroke/fill shape 기반.
  - `TablesConstructor.lattice_tables()`, `TableStructure`.
- stream table:
  - text layout과 implicit border 기반.
  - `TablesConstructor.stream_tables()`.
- table cell 내부 text/table/shapes도 layout parse 대상이다.

### Paragraph reconstruction

- page/column/cell 내부에서만 수행된다.
- `Blocks._join_lines_vertically()`는 인접 line 간 vertical distance, common spacing, image line 여부를 기준으로 `TextBlock`을 만든다.
- `Lines.split_vertically_by_text()`는 sentence-ending punctuation과 line end free space, new paragraph free space를 기준으로 block을 나눈다.
- `Lines.adjust_last_word()`는 같은 `TextBlock` 내부 line 사이에서 영문 단어 공백 삽입과 optional hyphen deletion을 처리한다.
- page를 넘어가는 paragraph continuation은 현재 처리하지 않는다.

### Header/footer

- `Page` 모델에 `header`, `footer` 필드가 있고 `store()/restore()`에도 포함된다.
- `Converter` docstring과 `Pages.parse()` 주석에는 document-level header/footer 분석이 언급되어 있다.
- 실제 구현은 `Pages._parse_document()`의 `TODO` 상태이며, 현재 header/footer content를 body에서 제거하거나 DOCX header/footer로 만드는 흐름은 없다.

### OCR

- `default_settings`에 `ocr` 옵션이 있다.
- `ocr == 1`은 `SystemExit("OCR feature is planned but not implemented yet.")`를 발생시킨다.
- `ocr == 2`는 OCR 처리된 PDF에서 hidden/displayed text 처리 방식을 바꾸는 용도에 가깝다.
- 내장 OCR pipeline은 없다.

### DOCX generation

- `python-docx` 기반으로 paragraph, run, table, section을 만든다.
- `common/docx.py`에서 OpenXML을 직접 조작해 columns, hyperlinks, floating image, cell borders/shading 등을 설정한다.
- 현재는 page마다 `WD_SECTION.NEW_PAGE`를 만들기 때문에 PDF page 단위가 DOCX 구조에 강하게 남는다.

## 테스트와 검증 도구

### 기존 테스트

- `test/test.py::TestConversion`
  - table extraction.
  - multi-page convert.
  - rotated/non-RGB image regression.
  - output DOCX 파일 존재 및 크기 확인.
- `test/test.py::test_one`
  - sample별 PDF -> DOCX -> PDF 재변환 후 visual similarity 비교.
  - multi-page sample은 대부분 skip.
  - Word 또는 LibreOffice가 필요하다.

### 샘플 fixture

- `test/samples/demo-text*.pdf`
- `test/samples/demo-table*.pdf`
- `test/samples/demo-image*.pdf`
- `test/samples/demo-section*.pdf`
- issue regression: `demo-issue-340.pdf`, `demo-issue-346.pdf`
- 현재 header/footer 반복, page break paragraph continuation을 명시적으로 검증하는 fixture는 보이지 않는다.

### 발견된 검증 명령

```bash
python setup.py develop
pytest -v ./test/test.py::TestConversion
pytest -v ./test/test.py::TestConversion --cov=./pdf2docx --cov-report=xml
make test
```

품질 비교까지 실행하려면 추가로 다음 환경이 필요하다.

```bash
pytest -sv ./test/test.py::test_one
```

이 경로는 DOCX를 다시 PDF로 렌더링해야 하므로 Windows에서는 Word/docx2pdf, Linux/macOS에서는 LibreOffice가 필요하다.

## 현재 아키텍처 제약

- `Converter.default_settings`가 많은 layout heuristic threshold를 한 곳에서 관리한다.
- `Pages.parse()`가 document-level 분석, raw page cleanup, margin/section parsing을 한 메서드에서 순차 실행한다.
- `Pages._parse_document()`는 header/footer를 넣을 자연스러운 hook이지만 아직 비어 있다.
- `RawPage.clean_up()` 이후 margin과 section이 계산되므로, header/footer 제거 또는 분류 시점이 margin 계산 결과에 영향을 준다.
- `Page.make_docx()`가 page마다 section/page break를 만들기 때문에 cross-page paragraph merge는 DOCX 생성 구조와 충돌한다.
- `Blocks.parse_block()`과 `Lines.split_vertically_by_text()`는 column 내부 line grouping에 최적화되어 있고, document-level context를 알지 못한다.
- table detection은 text block이 paragraph로 묶이기 전 line/table 후보를 많이 재배치한다. header/footer 제거를 잘못 넣으면 table parsing 품질에 영향을 줄 수 있다.
- `common/docx.py`는 python-docx 내부 XML에 의존한다. 작은 변경도 Word/LibreOffice rendering 차이를 만들 수 있다.
- multi-processing 경로는 page parse 결과를 JSON으로 serialize/deserialize한다. 새 분석 결과는 store/restore 호환성을 고려해야 한다.

## 수정 시 조심해야 할 경계

- 공개 API와 CLI:
  - `Converter.convert`, `Converter.extract_tables`, `PDF2DOCX.convert/debug/table`, `parse`.
- low-level coordinate model:
  - `Element.ROTATION_MATRIX`, `Element.update_bbox`, row/column grouping.
- table parsing:
  - `TablesConstructor`, `TableStructure`, `Border`, `Cell` 계층.
- image/vector extraction:
  - `ImagesExtractor`, `Paths`, `ImageBlock`, `ImageSpan`.
- DOCX XML helper:
  - `common/docx.py`.
- test fixture와 CI workflow:
  - existing sample conversion 품질이 쉽게 흔들릴 수 있다.
- dependency/package files:
  - 사용자가 명시적으로 금지했으므로 현재 단계에서 변경 금지.

## 주요 unknown과 위험

- 반복 header/footer detection을 평가할 ground truth fixture가 없다.
- current visual similarity 테스트는 semantic quality를 보장하지 않는다.
- header/footer를 제거하면 margin/section/table detection 결과가 달라질 수 있다.
- page number, chapter title, running head처럼 반복되지만 의미가 있는 요소를 어떻게 DOCX header/footer에 매핑할지 정책이 필요하다.
- 첫 페이지, 홀짝 페이지, section별 header/footer 예외가 흔하다.
- page마다 section을 만드는 현재 DOCX 생성 방식은 cross-page paragraph continuation과 자연스럽게 맞지 않는다.
- paragraph continuation을 aggressive하게 적용하면 서로 다른 paragraph가 합쳐지는 품질 사고가 난다.
- continuation을 conservative하게 적용하면 split paragraph가 계속 남는다.
- OCR은 사실상 미구현이다. scanned PDF까지 포함하려면 별도 큰 설계와 의존성 검토가 필요하다.
- bullet/list detection은 `common/share.py::is_list_item()`이 즉시 `False`를 반환하므로 현재 사실상 비활성화되어 있다.
- PyMuPDF 버전 gate와 실제 `requirements.txt`의 `PyMuPDF>=1.26.7` 조합은 현재 코드에서 허용되지만, upstream API 변화에 민감할 수 있다.

