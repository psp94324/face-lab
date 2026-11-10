# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AI 관상(face reading) web app: user uploads a face photo, an OpenAI vision model returns a Korean-language 관상 interpretation. Single-file Streamlit app (`app.py`), deployed via GitHub → Streamlit Community Cloud. UI, prompts and model output are all Korean; the user communicates in Korean.

- `PRD.md` — source of truth for requirements (feature IDs F1–F8, result structure §5.2, system-prompt rules §7.5).
- `PROMPTS.md` — the 4-stage build plan. All 4 stages are done; when asked for "N단계", follow that stage's scope.
- `.env` — real `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`). Never print it.
- `.streamlit/config.toml` — 10MB upload limit, light/dark theme colors, `toolbarMode = "minimal"` (hides Deploy button).
- `사진1~3.png` — sample photos of real public figures used for validation. Never name or identify the people in them.

## Commands

```bash
pip install -r requirements.txt
streamlit run app.py                                            # local dev (opens browser)
streamlit run app.py --server.headless true --server.port 8501  # for Playwright testing
python -m py_compile app.py                                     # syntax check
```

No test suite or linter. To exercise logic without the UI, import from `app` in a script run from the project root (Streamlit prints harmless "No runtime found" warnings). A file-like stub with `getvalue()` is enough for `preprocess_image`. Don't run these scripts with `python -I`, because the packages live in user site-packages. Call `load_dotenv(".env")` explicitly in stdin scripts, since `find_dotenv()` fails there.

To test the no-key or bad-key UI without touching `.env`, start a second server with `OPENAI_API_KEY="" ...` or `OPENAI_API_KEY="sk-invalid..." ...` on another port. `load_dotenv` doesn't override variables that are already set.

## Architecture (`app.py`)

**Request pipeline.** `preprocess_image` (EXIF transpose → flatten alpha onto white → RGB → thumbnail to 1024px → in-memory JPEG → base64 data URL) → `analyze_face` → `_request` (Chat Completions, `max_completion_tokens`, image as `image_url`). `_request` retries once without `temperature` if the model rejects it. All OpenAI exceptions are mapped to `AnalysisError`, whose message is shown to the user verbatim.

**Prompt and parser are coupled.** `SYSTEM_PROMPT` dictates the exact markdown layout: `## 🪞 첫인상`, `## 👁️ 부위별 관상` (with `###` per feature), `## 🍀 운세`, `## 📜 종합 평가와 조언`, `## 🐾 닮은 동물상`, then a disclaimer line. Two places depend on that layout:
- `analyze_face` treats any non-`[NO_FACE]` reply with fewer than 3 `## ` as a refusal and raises `AnalysisError`.
- `parse_sections` maps `##` headings to keys by substring (`첫인상`→summary, `부위`→parts, `운세`→fortune, `종합`→overall, `동물`→animal) and strips the trailing disclaimer. `render_result` turns these into the summary card and tabs. If parsing fails, it falls back to raw `st.markdown`.

If you change heading names in the prompt, update the `keys` map in `parse_sections`. The `[NO_FACE]` prefix (`NO_FACE_TAG`) is the contract for "no single usable face", and the UI shows the rest of that reply as a warning.

**Streamlit state flow.** The "관상 보기" button uses `on_click=_start_analysis` to set `session_state.analyzing = True`. A callback runs before the script, so the button is already rendered `disabled` on the run that performs the API call (this prevents double calls). The analysis block stores `result`/`error`, clears `analyzing` in `finally`, and calls `st.rerun()`. `image_key` (sha256 of the bytes) resets the result when a different file is uploaded. `_reset` bumps `uploader_nonce`, which is part of the uploader's `key`, to clear the uploader widget itself. The download button uses `on_click="ignore"` so it doesn't rerun.

**Styling.** Custom HTML blocks use the `gs-*` classes defined in `CSS`. Colors come from CSS variables with a `prefers-color-scheme: dark` override, which mirrors `[theme.light]`/`[theme.dark]` in config. Any model text injected into HTML must go through `_plain` (html.escape). Tab contents are plain `st.markdown`, with `###` converted to colored bold labels by `_compact_headings`.

## Model choice

Default is `gpt-5.4-mini` (`DEFAULT_MODEL`), which `OPENAI_MODEL` overrides. In testing on the sample photos:
- **gpt-4o:** refused most real faces, even with the revised prompt. Don't switch back to it.
- **gpt-4.1:** worked, but gave less differentiated readings.

Reasoning-style models count reasoning toward `max_completion_tokens`, which is why the cap is 2500. Output varies run to run (`TEMPERATURE = 0.7`), so the same photo can get a different animal type.

## Constraints

- Images must never be written to disk.
- The system prompt must forbid identification (including clues from clothing, jersey numbers and logos), inference of sensitive attributes and demeaning remarks. Every API call must keep an output-token cap.

## Open issues from the stage-4 review (not yet fixed, awaiting user decision)

1. A photo with two faces gets analyzed instead of returning `[NO_FACE]` (violates PRD F6).
2. Tiny files with huge pixel dimensions (e.g. 13000×13000 PNG, ~500KB) use ~1.3GB RAM in `preprocess_image`. Check `image.size` before decoding.
3. `사진1~3.png` are not in `.gitignore`.
4. `PRIVACY_NOTICE` says photos are only used for analysis, but they are sent to OpenAI.
5. `requirements.txt` says `streamlit>=1.36`, but the code uses newer APIs (`width="stretch"`, `on_click="ignore"`, theme.light/dark). The app was tested on 1.58.
6. No per-session request limit (cost exposure on public deploy).

## Playwright testing notes

- Screenshots must be saved under the project directory (e.g. `.playwright-mcp/`, which is gitignored), not the scratchpad.
- A screenshot taken right after `browser_wait_for` sometimes comes out blank while Streamlit re-renders. Wait ~2s and retake.
- For scripted runs, upload with `page.locator('input[type=file]').setInputFiles(path)`. Treat the page as idle once "살펴보는 중" text and `[data-testid="stStatusWidget"]` are gone.
- Killing test servers makes their background tasks report exit code 127. That's expected.
