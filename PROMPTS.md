# 단계별 개발 프롬프트

> `PRD.md`를 기준으로 AI 관상 웹앱을 4단계로 개발하기 위한 프롬프트입니다.
> 각 단계의 프롬프트를 순서대로 복사해 Claude Code에 붙여넣으세요.
> 단계마다 결과를 확인한 뒤 다음 단계로 넘어갑니다.

---

## 1단계: 기본 뼈대 작성

```
PRD.md를 읽고, AI 관상 웹앱의 기본 뼈대를 만들어줘.

[만들 파일]
1. app.py
   - Streamlit 단일 페이지 앱
   - 페이지 설정(st.set_page_config): 제목 "AI 관상가", 아이콘, layout="centered"
   - 앱 제목, 짧은 소개 문구, 면책 문구("재미로 보는 관상이며 과학적 근거가 없습니다") 표시
   - 함수 구조만 먼저 잡기 (본문은 TODO 또는 최소 구현):
     - get_api_key(): st.secrets["OPENAI_API_KEY"] 먼저 확인 → 없으면 .env/환경변수에서 읽기
     - get_model(): 같은 방식으로 OPENAI_MODEL 읽기, 기본값 "gpt-4o"
     - preprocess_image(uploaded_file) -> str : 이미지 → base64 data URL (TODO)
     - analyze_face(data_url) -> str : OpenAI 호출 (TODO)
     - main(): 화면 구성
   - API 키가 없으면 st.error로 안내하고 st.stop()
   - st.secrets 접근 시 secrets.toml이 없어도 에러 나지 않도록 try/except 처리

2. requirements.txt
   - streamlit, openai, python-dotenv, Pillow (최소 버전 명시)

3. .env.example
   - OPENAI_API_KEY=your-api-key-here
   - OPENAI_MODEL=gpt-4o

4. .gitignore
   - .env, .streamlit/secrets.toml, __pycache__/, *.pyc, .venv/, venv/, .DS_Store

5. README.md
   - 프로젝트 소개, 로컬 실행 방법(가상환경, pip install, .env 작성, streamlit run app.py)
   - Streamlit Cloud 배포 방법(Secrets 설정 예시 포함)

[조건]
- API 키를 코드에 절대 하드코딩하지 마.
- 이 단계에서는 OpenAI 호출을 실제로 구현하지 않아도 돼.
- 작성 후 `python -m py_compile app.py`로 문법 오류가 없는지 확인해줘.
```

---

## 2단계: 주요 기능 추가

```
PRD.md의 5장(기능 요구사항)과 7장(기술 구조)에 맞게 app.py에 핵심 기능을 구현해줘.

[구현할 기능]
F1. 이미지 업로드
   - st.file_uploader, 허용 확장자: jpg, jpeg, png, webp
   - 10MB 넘으면 경고 표시 후 중단

F2. 이미지 미리보기
   - 업로드한 이미지를 화면에 표시

F3. 이미지 전처리 (preprocess_image)
   - Pillow로 열고 EXIF 회전 보정(ImageOps.exif_transpose)
   - RGBA/P 모드 등은 RGB로 변환
   - 긴 변이 1024px보다 크면 비율 유지하며 축소
   - JPEG로 메모리(BytesIO)에 저장 → base64 data URL 반환
   - 디스크에 파일 저장하지 않기
   - 이미지가 깨졌거나 열 수 없으면 사용자 친화적 에러 표시

F4. 관상 분석 (analyze_face)
   - openai 패키지의 OpenAI 클라이언트 사용
   - system 프롬프트: PRD 7.5 내용을 반영
     - 수십 년 경력의 전통 동양 관상가 역할
     - 관찰 가능한 얼굴 특징(형태, 비율, 인상)에 근거한 관상학 해석
     - 신원 식별 금지, 인종·민족·종교·성적 지향·질병 등 민감 속성 추정 금지
     - 외모 비하 금지, 단점도 긍정적인 조언으로 표현
     - 얼굴이 없거나 여러 명이거나 식별이 어려우면 정해진 키워드(예: "[NO_FACE]")로 시작하는 안내만 반환
   - 출력 형식: PRD 5.2 구조의 한국어 마크다운
     1) 첫인상 한 줄 요약
     2) 부위별 풀이(이마, 눈썹, 눈, 코, 입·입술, 귀(보이는 경우), 얼굴형·턱)
     3) 재물운 / 애정운 / 직업운 / 건강운
     4) 종합 평가 및 조언
     5) 닮은 동물상
     6) 마지막 줄에 재미용 면책 문구
   - user 메시지에 텍스트 지시 + image_url(data URL) 함께 전달
   - 출력 토큰 상한 설정(예: 1500), temperature 적당히(0.7 정도)

F5. 결과 표시
   - "관상 보기" 버튼 클릭 시 st.spinner와 함께 분석
   - 결과는 st.markdown으로 출력
   - 결과를 st.session_state에 저장해 같은 이미지로 다시 그릴 때 API를 재호출하지 않기
   - 새 이미지를 올리면 이전 결과 초기화

F6. 얼굴 미검출 처리
   - 응답이 "[NO_FACE]"로 시작하면 st.warning으로 안내

F7. 에러 처리
   - openai.AuthenticationError → "API 키가 올바르지 않습니다"
   - openai.RateLimitError → "요청이 많습니다. 잠시 후 다시 시도해주세요"
   - openai.APIConnectionError → "네트워크 연결을 확인해주세요"
   - openai.BadRequestError → 모델/이미지 문제 안내
   - 그 밖의 예외 → 일반 오류 메시지 (상세 내용은 API 키가 노출되지 않게 처리)
   - 모델이 분석을 거부한 응답(빈 응답 등)도 안내 메시지로 처리

F8. 면책 및 개인정보 문구
   - "업로드한 사진은 저장되지 않으며 분석에만 사용됩니다" 안내 추가

[조건]
- 같은 버튼을 빠르게 여러 번 눌러도 중복 호출되지 않도록 처리해줘.
- 구현 후 `python -m py_compile app.py`로 확인하고, `streamlit run app.py`로 실행해서 에러 없이 뜨는지 확인해줘.
- 바뀐 내용을 요약해줘.
```

---

## 3단계: UI 디자인

```
기능은 그대로 두고 app.py의 UI를 "동양 관상가" 콘셉트로 보기 좋게 다듬어줘.

[디자인 방향]
- 콘셉트: 전통적이고 신비로운 동양 관상 분위기 (한지 느낌의 배경, 먹색·주홍색·금색 포인트)
- 한국어 웹폰트 적용 (예: Google Fonts의 Noto Serif KR 또는 Gowun Batang)
- st.markdown(unsafe_allow_html=True)로 커스텀 CSS 적용
- .streamlit/config.toml에 테마 색상(primaryColor, backgroundColor 등) 설정

[화면 구성]
1. 헤더: 큰 제목 "AI 관상가", 부제 "사진 한 장으로 보는 당신의 관상"
2. 업로드 영역: 카드 형태, 사진 촬영 팁(정면, 밝은 조명, 얼굴 한 명, 모자·선글라스 X) 표시
3. 미리보기: 이미지를 적당한 크기로 가운데 정렬
4. "관상 보기" 버튼: 강조 색상, 넓은 버튼(use_container_width)
5. 결과 영역:
   - 첫인상 요약을 강조 카드로 표시
   - 부위별 풀이와 운세를 st.tabs 또는 st.expander로 보기 좋게 정리
     (모델 출력 형식을 섹션 단위로 파싱하기 어렵다면, 프롬프트에서 섹션 구분자를 정해 파싱해줘)
   - 결과 텍스트 다운로드 버튼(st.download_button, .txt 또는 .md)
   - "다른 사진으로 다시 보기" 버튼
6. 푸터: 면책 문구, 개인정보 안내

[조건]
- 모바일(좁은 화면)에서도 깨지지 않게 해줘.
- 다크 모드에서도 글자가 잘 보이게 해줘.
- CSS로 Streamlit 내부 클래스에 지나치게 의존하지 말고, 가능하면 직접 만든 클래스에 스타일을 입혀줘.
- 기존 기능(F1~F8)이 깨지지 않았는지 다시 실행해서 확인해줘.
```

---

## 4단계: PRD 준수 여부 및 버그 검토 (Playwright 활용)

```
지금까지 만든 앱이 PRD.md에 맞게 개발됐는지, 문제나 버그가 있는지 자세히 검토해줘.
Playwright로 실제 브라우저에서 앱을 열어 테스트해줘.

[준비]
1. `streamlit run app.py --server.headless true --server.port 8501`을 백그라운드로 실행
2. 테스트용 이미지 준비 (scratchpad 디렉터리에 생성)
   - 정상 얼굴 사진 1장 (내가 제공하지 않으면 요청해줘)
   - 얼굴이 없는 이미지 (Pillow로 단색/풍경 이미지 생성)
   - 큰 이미지 (예: 4000x3000)
   - PNG 투명 배경 이미지 (RGBA)
   - 깨진 파일 (확장자만 .jpg인 텍스트 파일)

[1. PRD 요구사항 체크리스트]
PRD의 F1~F8, 6장(비기능 요구사항), 7장(구조/환경변수), 8장(배포)을 항목별로 확인하고
✅ 충족 / ⚠️ 부분 충족 / ❌ 미충족 으로 표로 정리해줘. 근거(코드 위치 file:line)도 함께.

[2. Playwright 브라우저 테스트]
- http://localhost:8501 접속 → 페이지 로딩, 제목, 면책 문구 확인 (스크린샷)
- 각 테스트 이미지 업로드 → 미리보기 확인
- "관상 보기" 클릭 → 스피너 표시 → 결과 출력 확인 (스크린샷)
- 얼굴 없는 이미지 → 경고 메시지 표시 확인
- 깨진 파일 → 사용자 친화적 에러 표시 확인
- 버튼 연속 클릭 시 중복 호출 여부 확인
- 새 이미지 업로드 시 이전 결과가 초기화되는지 확인
- 다운로드 버튼, "다시 보기" 버튼 동작 확인
- 브라우저 콘솔 에러 확인
- 화면 크기 375px(모바일) / 1280px(데스크톱)에서 레이아웃 스크린샷 비교
- 다크 모드(emulate media)에서 가독성 확인

[3. 에러 상황 테스트]
- 잘못된 API 키로 실행했을 때 안내 메시지 (실제 키를 덮어쓰지 말고 환경변수로만 바꿔서 별도 포트로 실행)
- API 키가 없을 때 안내 메시지

[4. 코드 리뷰]
- 보안: API 키 하드코딩/로그 출력 여부, .gitignore에 .env 포함 여부, 에러 메시지로 민감 정보가 노출되는지
- 개인정보: 이미지가 디스크에 저장되는지
- 비용: 이미지 리사이즈와 출력 토큰 제한이 실제로 적용되는지
- 윤리: 시스템 프롬프트에 민감 속성 추정 금지·비하 금지 규칙이 있는지
- 배포: requirements.txt가 Streamlit Cloud에서 설치 가능한지, st.secrets 처리가 맞는지
- 버그 가능성: session_state 처리, 예외 처리 누락, 엣지 케이스

[결과 보고 형식]
1. PRD 체크리스트 표
2. 발견된 문제 목록 (심각도: 높음/중간/낮음, 위치, 재현 방법, 수정 제안)
3. 스크린샷 경로
4. 총평

문제를 찾으면 바로 고치지 말고 먼저 목록으로 보여줘. 내가 확인한 뒤 수정을 요청할게.
테스트가 끝나면 백그라운드로 띄운 Streamlit 서버는 종료해줘.
```

---

## 사용 팁

- 각 단계가 끝날 때마다 `streamlit run app.py`로 직접 확인해보세요.
- 4단계에서 문제가 나오면 "높음 심각도 문제부터 수정해줘"처럼 이어서 요청하면 됩니다.
- 모든 단계가 끝나면 GitHub에 올리기 전에 `git status`로 `.env`가 목록에 없는지 꼭 확인하세요.
