"""AI 관상가 - 얼굴 사진을 업로드하면 OpenAI 비전 모델이 관상을 풀이해 주는 Streamlit 앱."""

import base64
import hashlib
import html
import io
import os

import openai
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageOps, UnidentifiedImageError

load_dotenv()

DEFAULT_MODEL = "gpt-5.4-mini"
DISCLAIMER = "※ 본 결과는 재미로 보는 관상이며 과학적 근거가 없습니다."
PRIVACY_NOTICE = "🔒 업로드한 사진은 저장되지 않으며 분석에만 사용됩니다."

ALLOWED_TYPES = ["jpg", "jpeg", "png", "webp"]
MAX_FILE_MB = 10
MAX_SIDE_PX = 1024
JPEG_QUALITY = 85
MAX_OUTPUT_TOKENS = 2500
TEMPERATURE = 0.7
NO_FACE_TAG = "[NO_FACE]"

SYSTEM_PROMPT = f"""당신은 수십 년 경력의 전통 동양 관상가입니다.
이 서비스는 사용자가 재미로 관상을 보기 위해 직접 사진을 올리는 오락용 서비스입니다.
사진 속 얼굴을 보고, 관찰 가능한 특징(이목구비의 형태, 비율, 표정, 전체적인 인상)에 근거해
전통 관상학 관점으로 재미있고 따뜻하게 풀이합니다.
이것은 신원 확인이 아니라 눈에 보이는 얼굴 생김새에 대한 관상학적 해석이므로, 얼굴이 보이면 반드시 풀이합니다.

[반드시 지킬 규칙]
- 사진 속 인물이 누구인지 식별하거나 추측하지 않습니다. 실존 인물의 이름을 언급하지 않습니다.
- 인물이 유명인처럼 보이더라도 신원과 상관없이 얼굴 생김새만으로 풀이합니다.
  옷, 유니폼, 등번호, 로고, 배경 같은 신원 단서는 언급하지 않습니다.
- 각 부위 풀이는 이 사진에서 실제로 보이는 구체적인 특징(예: 웃는 입매, 수염, 안경, 눈꼬리 방향,
  이마를 드러낸 머리 모양)을 먼저 짚은 뒤 해석합니다. 어느 얼굴에나 해당될 상투적인 문장은 피합니다.
  안경·수염 등이 있으면 그것이 가리는 부위는 보이는 범위에서만 풀이합니다.
- 인종, 민족, 국적, 종교, 성적 지향, 정치 성향, 질병·장애 등 민감한 속성을 추정하거나 언급하지 않습니다.
- 외모를 비하하거나 조롱하지 않습니다. 약점으로 보일 수 있는 부분도 긍정적인 조언으로 표현합니다.
- 건강운은 일반적인 생활 습관 조언 수준으로만 말하고, 의학적 진단처럼 들리는 표현은 쓰지 않습니다.
- 사진에서 보이지 않는 부위는 "사진에서 잘 보이지 않습니다"라고 짧게 쓰고 넘어갑니다.

[분석할 수 없는 경우 - 이 경우에만 해당]
사진에 사람 얼굴이 아예 없거나, 두 명 이상의 얼굴이 함께 있거나, 얼굴이 너무 작거나 가려져
이목구비를 알아볼 수 없을 때만 분석하지 말고 "{NO_FACE_TAG}"로 시작하는 한두 문장의 한국어 안내만 답하세요.
얼굴 한 명이 알아볼 수 있게 보이면 이 안내를 쓰지 말고 반드시 아래 형식으로 풀이하세요.
예: "{NO_FACE_TAG} 사진에서 얼굴을 찾기 어렵습니다. 정면 얼굴이 잘 보이는 사진을 올려주세요."

[출력 형식] 한국어 마크다운, 아래 구조를 그대로 따릅니다.
## 🪞 첫인상
(한 줄 요약)

## 👁️ 부위별 관상
### 이마 (초년운·지혜)
### 눈썹 (형제운·성격)
### 눈 (마음·대인관계)
### 코 (재물운·중년운)
### 입·입술 (말년운·언변)
### 귀 (복·건강운)
### 얼굴형·턱 (의지·말년운)
(각 부위마다 2~3문장)

## 🍀 운세
### 재물운
### 애정운
### 직업운
### 건강운
(각 2~3문장)

## 📜 종합 평가와 조언
(3~5문장)

## 🐾 닮은 동물상
(동물 하나와 이유 한 문장)

---
마지막 줄: _재미로 보는 관상이며 과학적 근거는 없습니다._
"""

USER_PROMPT = "이 사진 속 인물의 관상을 정해진 형식에 맞춰 풀이해 주세요."


class AnalysisError(Exception):
    """사용자에게 그대로 보여줄 수 있는 메시지를 담은 예외."""


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
def _get_config(key: str) -> str | None:
    """st.secrets를 먼저 확인하고, 없으면 환경변수(.env)에서 값을 읽는다."""
    try:
        value = st.secrets.get(key)
        if value:
            return str(value)
    except Exception:
        # 로컬에 .streamlit/secrets.toml이 없으면 예외가 발생할 수 있음
        pass
    return os.getenv(key) or None


def get_api_key() -> str | None:
    return _get_config("OPENAI_API_KEY")


def get_model() -> str:
    return _get_config("OPENAI_MODEL") or DEFAULT_MODEL


@st.cache_resource(show_spinner=False)
def get_client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key, timeout=60, max_retries=1)


# ---------------------------------------------------------------------------
# 이미지 처리
# ---------------------------------------------------------------------------
def preprocess_image(uploaded_file) -> str:
    """업로드된 이미지를 메모리에서 리사이즈하고 base64 JPEG data URL로 변환한다."""
    try:
        image = Image.open(io.BytesIO(uploaded_file.getvalue()))
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise AnalysisError(
            "이미지를 열 수 없습니다. 손상되지 않은 JPG, PNG, WEBP 파일을 올려주세요."
        ) from exc

    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        # 투명 배경은 흰색으로 채운다
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    image.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


# ---------------------------------------------------------------------------
# OpenAI 분석
# ---------------------------------------------------------------------------
def _request(client: OpenAI, model: str, data_url: str, use_temperature: bool):
    params = dict(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                ],
            },
        ],
        max_completion_tokens=MAX_OUTPUT_TOKENS,
    )
    if use_temperature:
        params["temperature"] = TEMPERATURE
    return client.chat.completions.create(**params)


def analyze_face(data_url: str) -> str:
    """OpenAI 비전 모델로 관상 분석 결과(마크다운)를 받아온다."""
    api_key = get_api_key()
    if not api_key:
        raise AnalysisError("OpenAI API 키가 설정되지 않았습니다.")
    client = get_client(api_key)
    model = get_model()

    try:
        try:
            response = _request(client, model, data_url, use_temperature=True)
        except openai.BadRequestError as exc:
            # 일부 모델은 temperature 조정을 지원하지 않으므로 빼고 한 번 더 시도
            if "temperature" not in str(exc):
                raise
            response = _request(client, model, data_url, use_temperature=False)
    except openai.AuthenticationError as exc:
        raise AnalysisError("API 키가 올바르지 않습니다. 설정을 확인해 주세요.") from exc
    except openai.RateLimitError as exc:
        raise AnalysisError(
            "요청이 많거나 사용 한도를 초과했습니다. 잠시 후 다시 시도해 주세요."
        ) from exc
    except openai.APIConnectionError as exc:
        raise AnalysisError("AI 서버에 연결하지 못했습니다. 네트워크를 확인해 주세요.") from exc
    except openai.NotFoundError as exc:
        raise AnalysisError(
            f"모델 '{model}'을(를) 사용할 수 없습니다. OPENAI_MODEL 설정을 확인해 주세요."
        ) from exc
    except openai.BadRequestError as exc:
        raise AnalysisError(
            "요청을 처리하지 못했습니다. 다른 사진을 사용하거나, "
            "이미지 입력을 지원하는 모델인지 확인해 주세요."
        ) from exc
    except openai.APIError as exc:
        raise AnalysisError("AI 서버에서 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.") from exc

    message = response.choices[0].message if response.choices else None
    content = (message.content or "").strip() if message else ""
    is_no_face = content.startswith(NO_FACE_TAG)
    # 형식(## 섹션)을 따르지 않은 짧은 답변은 모델의 거절 문구로 본다
    if not content or (not is_no_face and content.count("## ") < 3):
        raise AnalysisError(
            "AI가 이 사진의 분석을 거절했습니다. 정면 얼굴이 잘 보이는 다른 사진으로 시도해 주세요."
        )
    return content


def parse_sections(result: str) -> dict[str, str] | None:
    """'## 제목' 단위로 결과를 나눠 {키: 본문}으로 반환한다. 형식이 맞지 않으면 None."""
    keys = {"첫인상": "summary", "부위": "parts", "운세": "fortune", "종합": "overall", "동물": "animal"}
    sections: dict[str, str] = {}
    current = None
    lines: list[str] = []
    for line in result.splitlines():
        if line.startswith("## "):
            if current:
                sections[current] = "\n".join(lines).strip()
            current = next((v for k, v in keys.items() if k in line), None)
            lines = []
        elif current:
            lines.append(line)
    if current:
        sections[current] = "\n".join(lines).strip()

    # 마지막 섹션 뒤에 붙는 구분선과 면책 문구 제거 (화면 하단에 따로 표시)
    for key, body in sections.items():
        body = body.split("\n---")[0].strip()
        sections[key] = "\n".join(
            ln for ln in body.splitlines() if "재미로 보는 관상" not in ln
        ).strip()

    if not {"summary", "parts", "fortune"} <= sections.keys():
        return None
    return sections


# ---------------------------------------------------------------------------
# 화면
# ---------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=Noto+Serif+KR:wght@600;800&display=swap');

:root {
  --gs-paper: #fffdf7;
  --gs-ink: #2a2522;
  --gs-muted: #6f6458;
  --gs-red: #b23a2b;
  --gs-gold: #a8792a;
  --gs-line: #e4d8bf;
  --gs-soft: #f6eedb;
}
@media (prefers-color-scheme: dark) {
  :root {
    --gs-paper: #26201b;
    --gs-ink: #efe7d6;
    --gs-muted: #b9ad9a;
    --gs-red: #e2735f;
    --gs-gold: #d9ae5a;
    --gs-line: #42382e;
    --gs-soft: #2f2822;
  }
}

.gs-hero, .gs-card, .gs-summary, .gs-footer,
.gs-hero p, .gs-card li, .gs-summary p, .gs-summary div {
  font-family: 'Gowun Batang', serif !important;
}
.gs-summary p, .gs-summary div, .gs-card li { word-break: keep-all !important; }

.gs-hero { text-align: center; padding: 1.2rem 0 0.4rem; }
.gs-seal {
  display: inline-flex; align-items: center; justify-content: center;
  width: 64px; height: 64px; border-radius: 12px;
  background: var(--gs-red); color: #fff8ec;
  font-family: 'Noto Serif KR', serif; font-weight: 800; font-size: 1.5rem;
  transform: rotate(-4deg); box-shadow: 0 4px 14px rgba(178, 58, 43, 0.25);
}
.gs-title {
  font-family: 'Noto Serif KR', serif; font-weight: 800;
  font-size: clamp(2rem, 7vw, 2.8rem); color: var(--gs-ink);
  margin: 0.7rem 0 0.2rem; letter-spacing: -0.02em;
}
.gs-subtitle { color: var(--gs-muted); font-size: 1.05rem; margin: 0; }
.gs-rule {
  width: 120px; height: 2px; margin: 1rem auto 0;
  background: linear-gradient(90deg, transparent, var(--gs-gold), transparent);
}

.gs-card {
  background: var(--gs-paper); color: var(--gs-ink);
  border: 1px solid var(--gs-line); border-radius: 14px;
  padding: 1rem 1.2rem; margin: 0.8rem 0;
}
.gs-card-title {
  font-family: 'Noto Serif KR', serif; color: var(--gs-red);
  font-size: 1rem; margin: 0 0 0.5rem; padding: 0;
}
.gs-tips { margin: 0; padding-left: 1.1rem; color: var(--gs-ink); line-height: 1.7; }

.gs-summary {
  background: var(--gs-paper); color: var(--gs-ink);
  border: 1px solid var(--gs-line); border-left: 5px solid var(--gs-red);
  border-radius: 14px; padding: 1.2rem 1.4rem; margin: 1.2rem 0 1rem;
}
.gs-label {
  font-family: 'Noto Serif KR', serif; color: var(--gs-gold);
  font-size: 0.85rem; font-weight: 600; letter-spacing: 0.08em; margin: 0 0 0.4rem;
}
.gs-summary-text {
  font-family: 'Noto Serif KR', serif; font-size: clamp(1.1rem, 4.2vw, 1.35rem);
  line-height: 1.6; margin: 0; word-break: keep-all;
}
.gs-animal {
  margin-top: 0.9rem; padding: 0.6rem 0.9rem; border-radius: 10px;
  background: var(--gs-soft); color: var(--gs-ink); line-height: 1.6; word-break: keep-all;
}

.gs-footer {
  text-align: center; color: var(--gs-muted); font-size: 0.85rem;
  line-height: 1.7; margin-top: 2.5rem; padding-top: 1rem;
  border-top: 1px solid var(--gs-line);
}
</style>
"""

HERO_HTML = """
<div class="gs-hero">
  <div class="gs-seal">相</div>
  <div class="gs-title">AI 관상가</div>
  <p class="gs-subtitle">사진 한 장으로 보는 당신의 관상</p>
  <div class="gs-rule"></div>
</div>
"""

TIPS_HTML = """
<div class="gs-card">
  <div class="gs-card-title">📷 이렇게 찍으면 더 정확해요</div>
  <ul class="gs-tips">
    <li>정면을 바라보는 얼굴 한 명</li>
    <li>밝은 조명, 흔들리지 않은 사진</li>
    <li>모자·선글라스·마스크는 벗고</li>
  </ul>
</div>
"""

FOOTER_HTML = f"""
<div class="gs-footer">
  {DISCLAIMER}<br>
  {PRIVACY_NOTICE}
</div>
"""


def _plain(text: str) -> str:
    """마크다운 강조 기호를 걷어내고 HTML에 안전하게 넣을 수 있게 만든다."""
    return html.escape(text.replace("**", "").replace("__", "").strip())


def _compact_headings(markdown: str) -> str:
    """탭 안의 '### 소제목'은 너무 크게 보이므로 굵은 글씨 + 색상 문단으로 바꾼다."""
    out = []
    for line in markdown.splitlines():
        if line.startswith("### "):
            out.append(f"\n**:red[{line[4:].strip()}]**  ")  # 끝 공백 2칸 = 줄바꿈
        else:
            out.append(line)
    return "\n".join(out)


def _start_analysis() -> None:
    st.session_state.analyzing = True


def _reset() -> None:
    """결과와 업로드를 모두 비우고 처음 화면으로 돌아간다."""
    st.session_state.uploader_nonce += 1
    st.session_state.image_key = None
    st.session_state.result = None
    st.session_state.error = None
    st.session_state.analyzing = False


def render_result(result: str) -> None:
    sections = parse_sections(result)
    if sections is None:
        # 형식이 예상과 다르면 원문을 그대로 보여준다
        st.markdown(result)
        return

    animal = sections.get("animal", "")
    animal_html = (
        f'<div class="gs-animal">🐾 <b>닮은 동물상</b> · {_plain(animal)}</div>' if animal else ""
    )
    st.markdown(
        f'<div class="gs-summary"><p class="gs-label">첫 인 상</p>'
        f'<p class="gs-summary-text">{_plain(sections["summary"])}</p>{animal_html}</div>',
        unsafe_allow_html=True,
    )

    tab_parts, tab_fortune, tab_overall = st.tabs(["👁️ 부위별 관상", "🍀 운세", "📜 종합 평가"])
    with tab_parts:
        st.markdown(_compact_headings(sections["parts"]))
    with tab_fortune:
        st.markdown(_compact_headings(sections["fortune"]))
    with tab_overall:
        st.markdown(sections.get("overall") or "종합 평가가 없습니다.")


def _footer() -> None:
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="AI 관상가", page_icon="🔮", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)

    st.session_state.setdefault("image_key", None)
    st.session_state.setdefault("result", None)
    st.session_state.setdefault("error", None)
    st.session_state.setdefault("analyzing", False)
    st.session_state.setdefault("uploader_nonce", 0)

    st.markdown(HERO_HTML, unsafe_allow_html=True)

    if not get_api_key():
        st.error(
            "OpenAI API 키가 설정되지 않았습니다. "
            "로컬에서는 `.env` 파일에, Streamlit Cloud에서는 Secrets에 "
            "`OPENAI_API_KEY`를 설정해 주세요."
        )
        _footer()
        st.stop()

    st.markdown(TIPS_HTML, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "얼굴 사진을 올려주세요 (JPG, PNG, WEBP · 최대 10MB)",
        type=ALLOWED_TYPES,
        key=f"uploader_{st.session_state.uploader_nonce}",
    )

    if uploaded is None:
        st.session_state.image_key = None
        st.session_state.result = None
        st.session_state.error = None
        st.session_state.analyzing = False
        _footer()
        return

    file_bytes = uploaded.getvalue()
    if len(file_bytes) > MAX_FILE_MB * 1024 * 1024:
        st.warning(f"파일이 너무 큽니다. {MAX_FILE_MB}MB 이하의 사진을 올려주세요.")
        _footer()
        return

    # 새 이미지가 올라오면 이전 결과 초기화
    image_key = hashlib.sha256(file_bytes).hexdigest()
    if st.session_state.image_key != image_key:
        st.session_state.image_key = image_key
        st.session_state.result = None
        st.session_state.error = None
        st.session_state.analyzing = False

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        try:
            st.image(file_bytes, caption="업로드한 사진", width="stretch")
        except Exception:
            st.error("이미지를 표시할 수 없습니다. 손상되지 않은 JPG, PNG, WEBP 파일을 올려주세요.")
            _footer()
            return

    result = st.session_state.result
    if result is None:
        st.button(
            "🔮 관상 보기",
            type="primary",
            on_click=_start_analysis,
            disabled=st.session_state.analyzing,
            width="stretch",
        )

    if st.session_state.analyzing:
        try:
            with st.spinner("관상가가 얼굴을 찬찬히 살펴보는 중입니다... (10초 정도 걸려요)"):
                data_url = preprocess_image(uploaded)
                st.session_state.result = analyze_face(data_url)
                st.session_state.error = None
        except AnalysisError as exc:
            st.session_state.error = str(exc)
        except Exception:
            st.session_state.error = "알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        finally:
            st.session_state.analyzing = False
        st.rerun()

    if st.session_state.error:
        st.error(st.session_state.error)

    if result:
        is_no_face = result.startswith(NO_FACE_TAG)
        if is_no_face:
            st.warning(result.removeprefix(NO_FACE_TAG).strip())
        else:
            render_result(result)

        col_dl, col_reset = st.columns(2)
        with col_dl:
            if not is_no_face:
                st.download_button(
                    "📥 결과 저장하기",
                    data=result.encode("utf-8"),
                    file_name="관상_결과.md",
                    mime="text/markdown",
                    on_click="ignore",
                    width="stretch",
                )
        with col_reset:
            st.button("🔄 다른 사진으로 다시 보기", on_click=_reset, width="stretch")

    _footer()


if __name__ == "__main__":
    main()
