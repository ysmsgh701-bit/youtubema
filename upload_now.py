"""
즉시 업로드 스크립트 — 기존 MP4를 YouTube에 바로 올립니다.

사용법:
    # 업로드할 영상 목록만 확인
    python upload_now.py --list

    # 특정 영상 업로드 (비공개)
    python upload_now.py --video output/20260427_200205/ko/longform/final_longform.mp4

    # 제목/공개범위 지정
    python upload_now.py --video <경로> --title "배당주 투자 전략" --privacy public

    # 최신 run 영상 전체 업로드 (비공개)
    python upload_now.py --latest
"""
import os
import sys
import glob
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import OUTPUT_DIR
from scripts.youtube_upload import get_authenticated_service, upload_video


def find_mp4s():
    """output 디렉토리에서 모든 MP4 파일을 최신 순으로 반환"""
    pattern = os.path.join(OUTPUT_DIR, "**", "*.mp4")
    files = glob.glob(pattern, recursive=True)
    return sorted(files, key=os.path.getmtime, reverse=True)


def find_latest_run_mp4s():
    """가장 최신 run 디렉토리의 MP4 파일만 반환"""
    run_dirs = sorted(
        [d for d in os.listdir(OUTPUT_DIR)
         if os.path.isdir(os.path.join(OUTPUT_DIR, d)) and d[0].isdigit()],
        reverse=True,
    )
    if not run_dirs:
        return []
    latest = os.path.join(OUTPUT_DIR, run_dirs[0])
    pattern = os.path.join(latest, "**", "*.mp4")
    return sorted(glob.glob(pattern, recursive=True), key=os.path.getmtime, reverse=True)


def guess_format(path):
    if "shorts" in path.lower():
        return "shorts"
    return "longform"


def guess_lang(path):
    for lang in ["ko", "ja", "zh-TW", "en"]:
        if f"/{lang}/" in path.replace("\\", "/") or f"\\{lang}\\" in path:
            return lang
    return None


def main():
    parser = argparse.ArgumentParser(description="YouTube 즉시 업로드")
    parser.add_argument("--list", action="store_true", help="업로드 가능한 MP4 목록 출력")
    parser.add_argument("--video", type=str, help="업로드할 영상 파일 경로")
    parser.add_argument("--latest", action="store_true", help="최신 run 영상 전체 업로드")
    parser.add_argument("--title", type=str, default=None, help="영상 제목")
    parser.add_argument(
        "--privacy", type=str, default="private",
        choices=["private", "unlisted", "public"],
        help="공개 범위 (기본: private)",
    )
    args = parser.parse_args()

    # 목록만 출력
    if args.list:
        mp4s = find_mp4s()
        if not mp4s:
            print("업로드 가능한 MP4가 없습니다.")
            return
        print(f"\n업로드 가능한 영상 ({len(mp4s)}개):")
        for i, p in enumerate(mp4s, 1):
            size_mb = os.path.getsize(p) / 1024 / 1024
            print(f"  {i:2d}. [{guess_format(p):8s}] {p}  ({size_mb:.1f} MB)")
        print(f"\n업로드 예시:")
        print(f"  python upload_now.py --video \"{mp4s[0]}\"")
        return

    # 업로드할 파일 목록 결정
    if args.latest:
        targets = find_latest_run_mp4s()
        if not targets:
            print("[오류] 최신 run에서 MP4를 찾을 수 없습니다.")
            sys.exit(1)
        print(f"최신 run 영상 {len(targets)}개를 업로드합니다:")
        for p in targets:
            print(f"  • {p}")
    elif args.video:
        if not os.path.exists(args.video):
            print(f"[오류] 파일 없음: {args.video}")
            sys.exit(1)
        targets = [args.video]
    else:
        parser.print_help()
        return

    # YouTube 인증
    print("\nYouTube 인증 중...")
    youtube = get_authenticated_service()
    if not youtube:
        print("[오류] 인증 실패. client_secrets.json을 확인하세요.")
        sys.exit(1)
    print("인증 완료\n")

    # 업로드
    results = []
    for video_path in targets:
        fmt = guess_format(video_path)
        lang = guess_lang(video_path)

        title = args.title
        if not title:
            base = os.path.splitext(os.path.basename(video_path))[0]
            title = f"[테스트] 배당주 투자 전략 애니메이션 ({base})"

        description = "AI가 자동 생성한 시바견 애니메이션 투자 영상입니다."
        tags = ["주식", "경제", "배당주", "애니메이션", "시바견"]

        result = upload_video(
            youtube,
            video_file=video_path,
            title=title,
            description=description,
            tags=tags,
            video_format=fmt,
            privacy=args.privacy,
            lang_code=lang,
        )
        if result:
            results.append(result)

    # 결과 요약
    print(f"\n{'='*60}")
    print(f"  업로드 완료: {len(results)}/{len(targets)}개 성공")
    for r in results:
        print(f"  • {r['title']}")
        print(f"    {r['url']}  ({r['privacy']})")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
