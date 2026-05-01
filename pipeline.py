"""
YouTube 자동 후처리 파이프라인
촬영된 영상 파일을 받아 자막 → 메타데이터 → 썸네일 → 업로드를 순서대로 처리합니다.

사용법:
    python pipeline.py recording.mp4 --track finance
    python pipeline.py tft_session.mp4 --track tft
    python pipeline.py video.mp4 --track finance --dry-run
    python pipeline.py video.mp4 --track finance --privacy public --model small
"""
import os
import sys
import json
import shutil
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

import yaml

from scripts.transcribe import transcribe_to_srt, srt_to_text
from scripts.generate_meta import generate_meta
from scripts.generate_thumb import generate_thumbnail
from scripts.upload_captions import upload_with_captions

_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(_ROOT, "config")
OUTPUT_DIR = os.path.join(_ROOT, "output")
VALID_TRACKS = ["finance", "tft"]


def load_profile(track: str) -> dict:
    path = os.path.join(CONFIG_DIR, f"{track}_profile.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"프로파일 없음: {path}\n"
            f"  유효한 트랙: {VALID_TRACKS}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_pipeline(
    video_path: str,
    track: str,
    dry_run: bool = False,
    privacy: str = "private",
    whisper_model: str = "large-v3",
) -> dict:
    """
    메인 파이프라인: 영상 파일 → 자막 → 메타 → 썸네일 → 업로드.

    Args:
        video_path: 촬영된 영상 파일 경로
        track: "finance" 또는 "tft"
        dry_run: True이면 업로드 생략 (나머지 단계 정상 실행)
        privacy: YouTube 업로드 공개 설정
        whisper_model: faster-whisper 모델 크기

    Returns:
        단계별 결과 dict
    """
    print(f"\n{'='*60}")
    print(f"  YouTube 자동 후처리 파이프라인")
    print(f"  트랙  : {track}")
    print(f"  영상  : {os.path.basename(video_path)}")
    print(f"  모델  : {whisper_model}")
    print(f"  공개  : {privacy} {'(dry-run)' if dry_run else ''}")
    print(f"{'='*60}\n")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"영상 파일 없음: {video_path}")

    profile = load_profile(track)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(OUTPUT_DIR, track, timestamp)
    os.makedirs(run_dir, exist_ok=True)

    # 원본 영상 복사 (원본 보존)
    video_copy = os.path.join(run_dir, os.path.basename(video_path))
    shutil.copy2(video_path, video_copy)

    results = {
        "run_dir": run_dir,
        "track": track,
        "timestamp": timestamp,
        "video": video_copy,
    }

    # ── Step 1: 자막 생성 ──────────────────────────────
    print("[Step 1/4] 자막 생성 (faster-whisper)...")
    srt_path = os.path.join(run_dir, "subtitles.srt")
    transcribe_to_srt(video_copy, srt_path, language="ko", model_size=whisper_model)
    results["srt"] = srt_path

    # ── Step 2: 메타데이터 생성 ────────────────────────
    print("\n[Step 2/4] 메타데이터 생성 (Gemini)...")
    srt_text = srt_to_text(srt_path)
    meta = generate_meta(srt_text, profile)

    meta_path = os.path.join(run_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    results["meta"] = meta
    results["meta_path"] = meta_path

    print("  제목 후보:")
    for i, t in enumerate(meta.get("titles", []), 1):
        print(f"    {i}. {t}")

    # ── Step 3: 썸네일 생성 ────────────────────────────
    print("\n[Step 3/4] 썸네일 생성 (PIL)...")
    title_for_thumb = (meta.get("titles") or [profile.get("name", "")])[0]
    thumb_path = os.path.join(run_dir, "thumbnail.jpg")
    generate_thumbnail(title_for_thumb, profile, thumb_path)
    results["thumbnail"] = thumb_path

    # ── Step 4: 업로드 ─────────────────────────────────
    if dry_run:
        print("\n[Step 4/4] Dry Run - 업로드 생략")
        print(f"\n  출력 디렉토리: {run_dir}")
    else:
        print("\n[Step 4/4] YouTube 업로드...")
        upload_result = upload_with_captions(
            video_copy, srt_path, meta, profile,
            thumbnail_path=thumb_path,
            privacy=privacy,
        )
        results["upload"] = upload_result
        if upload_result:
            print(f"\n  업로드 완료: {upload_result.get('url', '')}")

    # 결과 저장
    summary_path = os.path.join(run_dir, "pipeline_result.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"  파이프라인 완료!")
    print(f"  출력: {run_dir}")
    print(f"{'='*60}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="YouTube 자동 후처리 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 재무 트랙 (비공개 업로드)
  python pipeline.py recording.mp4 --track finance

  # TFT 트랙 (업로드 없이 처리만)
  python pipeline.py tft_clip.mp4 --track tft --dry-run

  # 공개 업로드 + 빠른 모델 (테스트용)
  python pipeline.py video.mp4 --track finance --privacy public --model small
        """,
    )
    parser.add_argument("video", help="촬영된 영상 파일 경로")
    parser.add_argument(
        "--track", required=True, choices=VALID_TRACKS,
        help="트랙 선택: finance (재무AI) | tft (TFT플레이)"
    )
    parser.add_argument("--dry-run", action="store_true", help="업로드 없이 처리만 실행")
    parser.add_argument(
        "--privacy", default="private",
        choices=["private", "unlisted", "public"],
        help="YouTube 공개 설정 (기본: private)"
    )
    parser.add_argument(
        "--model", default="large-v3",
        help="Whisper 모델 크기 (기본: large-v3, 빠른 테스트: small)"
    )
    args = parser.parse_args()

    run_pipeline(args.video, args.track, args.dry_run, args.privacy, args.model)
