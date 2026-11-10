# 🔮 AI 관상가

얼굴 사진을 업로드하면 OpenAI 이미지 분석 모델이 전통 관상학 관점으로 풀이해 주는 Streamlit 웹앱입니다.

> 본 결과는 재미로 보는 관상이며 과학적 근거가 없습니다. 업로드한 사진은 저장되지 않습니다.

## 로컬 실행

```bash
# 1. 가상환경 생성 및 활성화
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2. 패키지 설치
pip install -r requirements.txt

# 3. 환경변수 설정: .env.example을 복사해 .env를 만들고 API 키 입력
#    OPENAI_API_KEY=sk-...
#    OPENAI_MODEL=gpt-5.4-mini

# 4. 실행
streamlit run app.py
```

## Streamlit Community Cloud 배포

1. 이 저장소를 GitHub에 푸시합니다. (`.env`는 `.gitignore`에 포함되어 업로드되지 않습니다)
2. [share.streamlit.io](https://share.streamlit.io)에서 저장소를 연결하고 Main file path를 `app.py`로 지정합니다.
3. **Advanced settings → Secrets**에 아래 내용을 입력합니다.

   ```toml
   OPENAI_API_KEY = "sk-..."
   OPENAI_MODEL = "gpt-5.4-mini"
   ```

4. 배포 후 사진 업로드부터 결과 출력까지 정상 동작하는지 확인합니다.

API 키는 `st.secrets`에서 먼저 찾고, 없으면 `.env`(환경변수)에서 읽습니다.
