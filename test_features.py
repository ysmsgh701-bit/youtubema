"""전체 기능 검증 테스트"""
import sys, os, json, yaml, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []

def check(name, fn):
    try:
        fn()
        results.append((PASS, name, ""))
        print(f"  {PASS} {name}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL} {name}")
        print(f"         -> {str(e)[:120]}")

print("=" * 58)
print("  기능 검증 테스트")
print("=" * 58)

# ── 1. 트랙 프로파일 ──────────────────────────────
print("\n[1] 트랙 프로파일 로딩")

def test_finance_profile():
    with open("config/finance_profile.yaml", encoding="utf-8") as f:
        p = yaml.safe_load(f)
    assert p["track"] == "finance"
    assert "style" in p and "script_system_prompt" in p and "meta_prompt" in p

def test_tft_profile():
    with open("config/tft_profile.yaml", encoding="utf-8") as f:
        p = yaml.safe_load(f)
    assert p["track"] == "tft"
    assert p["style"]["layout"] == "gaming"

check("finance_profile.yaml 로딩", test_finance_profile)
check("tft_profile.yaml 로딩", test_tft_profile)

# ── 2. 자막 생성 (faster-whisper) ─────────────────
print("\n[2] 자막 생성 (faster-whisper)")

def test_whisper_import():
    from faster_whisper import WhisperModel
    assert WhisperModel is not None

def test_srt_to_text():
    from scripts.transcribe import srt_to_text
    srt = "1\n00:00:00,000 --> 00:00:05,000\n안녕하세요\n\n2\n00:00:05,000 --> 00:00:10,000\n테스트입니다\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False, encoding="utf-8") as f:
        f.write(srt); tmp = f.name
    text = srt_to_text(tmp)
    os.unlink(tmp)
    assert "안녕하세요" in text and "테스트" in text

def test_srt_time_format():
    from scripts.transcribe import _fmt_time
    assert _fmt_time(3661.5) == "01:01:01,500"
    assert _fmt_time(0.0) == "00:00:00,000"

check("faster_whisper import", test_whisper_import)
check("srt_to_text() 파싱", test_srt_to_text)
check("타임스탬프 포맷 변환", test_srt_time_format)

# ── 3. 메타데이터 생성 ────────────────────────────
print("\n[3] 메타데이터 생성 (Gemini)")

def test_meta_fallback():
    from scripts.generate_meta import generate_meta
    with open("config/finance_profile.yaml", encoding="utf-8") as f:
        p = yaml.safe_load(f)
    meta = generate_meta("", p, api_key=None)
    assert "titles" in meta and "description" in meta and "tags" in meta

def test_meta_with_api():
    api_key = os.environ.get("GEMINI_API_KEY")
    assert api_key, "GEMINI_API_KEY not set"
    from scripts.generate_meta import generate_meta
    with open("config/finance_profile.yaml", encoding="utf-8") as f:
        p = yaml.safe_load(f)
    meta = generate_meta("AI로 결산 보고서 만들기", p, api_key=api_key)
    assert len(meta.get("titles", [])) >= 1
    assert len(meta.get("description", "")) > 10

check("메타 fallback (API 없을 때)", test_meta_fallback)
check("메타 생성 with Gemini API", test_meta_with_api)

# ── 4. 썸네일 생성 ────────────────────────────────
print("\n[4] 썸네일 생성 (PIL)")

def test_thumb_finance():
    from scripts.generate_thumb import generate_thumbnail
    with open("config/finance_profile.yaml", encoding="utf-8") as f:
        p = yaml.safe_load(f)
    out = "output/test_check_finance.jpg"
    generate_thumbnail("결산 보고서 3분 완성", p, out)
    assert os.path.exists(out) and os.path.getsize(out) > 1000
    os.unlink(out)

def test_thumb_tft():
    from scripts.generate_thumb import generate_thumbnail
    with open("config/tft_profile.yaml", encoding="utf-8") as f:
        p = yaml.safe_load(f)
    out = "output/test_check_tft.jpg"
    generate_thumbnail("1등 굳혔는데 역전 당함", p, out)
    assert os.path.exists(out) and os.path.getsize(out) > 1000
    os.unlink(out)

def test_thumb_wrap():
    from scripts.generate_thumb import _wrap_text
    lines = _wrap_text("엑셀 피벗 대신 ChatGPT 써서 보고서 만드는 법", max_chars=14)
    assert 1 <= len(lines) <= 3

check("finance 썸네일 생성", test_thumb_finance)
check("tft 썸네일 생성", test_thumb_tft)
check("긴 제목 줄바꿈 처리", test_thumb_wrap)

# ── 5. 대본 생성 ──────────────────────────────────
print("\n[5] 대본 생성 (Gemini)")

def test_script_fallback():
    from scripts.generate_script import generate_script
    with open("config/tft_profile.yaml", encoding="utf-8") as f:
        p = yaml.safe_load(f)
    text = generate_script("테스트 주제", p, api_key=None)
    assert len(text) > 20 and "테스트 주제" in text

def test_script_with_api():
    api_key = os.environ.get("GEMINI_API_KEY")
    assert api_key
    from scripts.generate_script import generate_script
    with open("config/finance_profile.yaml", encoding="utf-8") as f:
        p = yaml.safe_load(f)
    text = generate_script("AI로 경비처리 자동화하기", p, api_key=api_key)
    assert len(text) > 100

def test_script_save():
    from scripts.generate_script import save_script
    tmp_dir = "output/_test_scripts_tmp"
    path = save_script("# 테스트 대본\n내용", tmp_dir, "테스트 주제")
    assert os.path.exists(path)
    shutil.rmtree(tmp_dir)

check("대본 fallback (API 없을 때)", test_script_fallback)
check("대본 생성 with Gemini API", test_script_with_api)
check("대본 파일 저장", test_script_save)

# ── 6. 업로드 모듈 ────────────────────────────────
print("\n[6] 업로드 모듈 (OAuth 제외)")

def test_upload_import():
    from scripts.upload_captions import upload_with_captions, _upload_captions
    assert upload_with_captions is not None

def test_youtube_upload_import():
    from scripts.youtube_upload import get_authenticated_service, upload_video
    assert upload_video is not None

check("upload_captions.py import", test_upload_import)
check("youtube_upload.py 기존 모듈 연결", test_youtube_upload_import)

# ── 7. pipeline.py ────────────────────────────────
print("\n[7] pipeline.py 오케스트레이터")

def test_pipeline_import():
    import pipeline
    assert hasattr(pipeline, "run_pipeline")
    assert hasattr(pipeline, "load_profile")
    assert hasattr(pipeline, "VALID_TRACKS")

def test_pipeline_invalid_track():
    import pipeline
    try:
        pipeline.load_profile("invalid_track")
        assert False, "예외 발생해야 함"
    except FileNotFoundError:
        pass

def test_pipeline_missing_video():
    import pipeline
    try:
        pipeline.run_pipeline("없는파일.mp4", "finance")
        assert False
    except FileNotFoundError:
        pass

check("pipeline.py import 및 함수 존재", test_pipeline_import)
check("잘못된 트랙명 예외 처리", test_pipeline_invalid_track)
check("존재하지 않는 영상 예외 처리", test_pipeline_missing_video)

# ── 8. watch_folder.py ────────────────────────────
print("\n[8] watch_folder.py 폴더 감시")

def test_watch_import():
    import watch_folder
    assert hasattr(watch_folder, "VideoDropHandler")
    assert hasattr(watch_folder, "TRACKS")

def test_watch_track_detection():
    from watch_folder import VideoDropHandler
    handler = VideoDropHandler(dry_run=True)
    assert handler._detect_track("/some/inbox/finance/video.mp4") == "finance"
    assert handler._detect_track("/some/inbox/tft/clip.mkv") == "tft"
    assert handler._detect_track("/some/other/video.mp4") is None

def test_watch_ext_filter():
    from watch_folder import VIDEO_EXTENSIONS
    assert ".mp4" in VIDEO_EXTENSIONS
    assert ".mov" in VIDEO_EXTENSIONS
    assert ".txt" not in VIDEO_EXTENSIONS

def test_inbox_dirs():
    assert os.path.isdir("inbox/finance"), "inbox/finance 없음"
    assert os.path.isdir("inbox/tft"), "inbox/tft 없음"

check("watch_folder.py import", test_watch_import)
check("트랙 자동 감지 (finance/tft)", test_watch_track_detection)
check("영상 확장자 필터", test_watch_ext_filter)
check("inbox 폴더 존재", test_inbox_dirs)

# ── 결과 요약 ─────────────────────────────────────
passed = sum(1 for r in results if r[0] == PASS)
failed = [r for r in results if r[0] == FAIL]
total = len(results)

print()
print("=" * 58)
print(f"  결과: {passed}/{total} 통과  |  실패: {len(failed)}개")
print("=" * 58)
if failed:
    print("\n  실패 항목:")
    for r in failed:
        print(f"    x {r[1]}")
        print(f"      {r[2][:100]}")
