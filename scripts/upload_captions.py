"""
YouTube 업로드 모듈 (SRT 자막 포함)
기존 youtube_upload.py를 래핑하여 영상 + SRT 자막을 함께 업로드합니다.

독립 실행:
    python scripts/upload_captions.py video.mp4 meta.json config/finance_profile.yaml
    python scripts/upload_captions.py video.mp4 meta.json config/tft_profile.yaml \\
        --srt subtitles.srt --thumbnail thumbnail.jpg --privacy public
"""
import os
import sys
import json
import argparse

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.youtube_upload import get_authenticated_service, upload_video


def upload_with_captions(
    video_path: str,
    srt_path: str,
    meta: dict,
    profile: dict,
    thumbnail_path: str = None,
    privacy: str = "private",
) -> dict:
    """
    영상 + SRT 자막을 YouTube에 업로드합니다.

    Args:
        video_path: 업로드할 영상 파일 경로
        srt_path: SRT 자막 파일 경로 (None 가능)
        meta: generate_meta.py 결과 dict
        profile: 트랙 프로파일 dict
        thumbnail_path: 썸네일 파일 경로 (None 가능)
        privacy: "private" | "unlisted" | "public"

    Returns:
        {"video_id": ..., "url": ..., "title": ...}
    """
    youtube = get_authenticated_service()
    if not youtube:
        raise RuntimeError("YouTube OAuth 인증 실패 - client_secrets.json 확인 필요")

    title = (meta.get("titles") or [profile.get("name", "영상")])[0]
    description = meta.get("description", "")
    tags = meta.get("tags", [])

    result = upload_video(
        youtube,
        video_file=video_path,
        title=title,
        description=description,
        tags=tags,
        thumbnail_files=[thumbnail_path] if thumbnail_path and os.path.exists(thumbnail_path) else [],
        video_format="longform",
        privacy=privacy,
    )

    if result and srt_path and os.path.exists(srt_path):
        _upload_captions(youtube, result["video_id"], srt_path)

    return result


def _upload_captions(youtube, video_id: str, srt_path: str):
    """SRT 자막 파일을 해당 영상에 업로드합니다."""
    from googleapiclient.http import MediaFileUpload

    try:
        youtube.captions().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "language": "ko",
                    "name": "Korean",
                    "isDraft": False,
                }
            },
            media_body=MediaFileUpload(srt_path, mimetype="application/x-subrip"),
        ).execute()
        print(f"[Upload] 자막 업로드 완료: {os.path.basename(srt_path)}")
    except Exception as e:
        print(f"[Upload] 자막 업로드 실패 (영상 업로드는 완료됨): {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="YouTube 업로드 (영상 + SRT 자막)"
    )
    parser.add_argument("video", help="영상 파일 경로")
    parser.add_argument("meta", help="메타데이터 JSON 파일 경로")
    parser.add_argument("profile", help="트랙 프로파일 YAML 경로")
    parser.add_argument("--srt", default=None, help="SRT 자막 파일 경로")
    parser.add_argument("--thumbnail", default=None, help="썸네일 파일 경로")
    parser.add_argument(
        "--privacy", default="private",
        choices=["private", "unlisted", "public"],
        help="공개 설정 (기본: private)",
    )
    args = parser.parse_args()

    with open(args.meta, "r", encoding="utf-8") as f:
        meta_data = json.load(f)
    with open(args.profile, "r", encoding="utf-8") as f:
        profile_data = yaml.safe_load(f)

    result = upload_with_captions(
        args.video, args.srt, meta_data, profile_data,
        thumbnail_path=args.thumbnail,
        privacy=args.privacy,
    )

    if result:
        print(f"\n[OK] 업로드 완료: {result['url']}")
