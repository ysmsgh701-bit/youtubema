"""
YouTube 자동 업로드 모듈 v2
다채널 인증, 쇼츠 자동 해시태그, 썸네일 A/B 등록을 지원합니다.
"""
import os
import json
import sys
import pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CLIENT_SECRETS_FILE, YOUTUBE_SCOPES, CHANNELS

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request


# ──────────────────────────────────────────────
# 인증
# ──────────────────────────────────────────────

def get_authenticated_service(channel_id=None):
    """
    OAuth 2.0 인증을 통해 YouTube API 서비스 객체를 반환합니다.
    채널별로 별도의 토큰 파일을 관리합니다.
    
    Args:
        channel_id: 채널 식별자 (None이면 기본 인증)
    """
    token_file = f"token_{channel_id}.pickle" if channel_id else "token.pickle"

    credentials = None

    # 저장된 토큰 로드
    if os.path.exists(token_file):
        with open(token_file, "rb") as f:
            credentials = pickle.load(f)

    # 토큰이 만료되었거나 없는 경우
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print(f"[Auth] 토큰 갱신 중... ({channel_id or 'default'})")
            credentials.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"[오류] '{CLIENT_SECRETS_FILE}' 파일이 존재하지 않습니다.")
                print("Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 생성하세요.")
                return None

            print(f"[Auth] 새 인증 진행 중... ({channel_id or 'default'})")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, YOUTUBE_SCOPES
            )
            credentials = flow.run_local_server(port=0)

        # 토큰 저장
        with open(token_file, "wb") as f:
            pickle.dump(credentials, f)
        print(f"[Auth] 토큰 저장 완료: {token_file}")

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
    return youtube


# ──────────────────────────────────────────────
# 업로드
# ──────────────────────────────────────────────

def upload_video(
    youtube,
    video_file,
    title,
    description,
    tags,
    thumbnail_files=None,
    video_format="longform",
    category_id="27",
    privacy="private",
    lang_code=None,
):
    """
    영상을 업로드하고 썸네일을 등록합니다.
    
    Args:
        youtube: YouTube API 서비스 객체
        video_file: 영상 파일 경로
        title: 영상 제목
        description: 영상 설명
        tags: 태그 리스트
        thumbnail_files: 썸네일 파일 경로 리스트 (A/B 테스트용 최대 2개)
        video_format: "shorts" 또는 "longform"
        category_id: YouTube 카테고리 ID
        privacy: "private", "unlisted", "public"
        lang_code: 언어 코드
    """
    if not os.path.exists(video_file):
        print(f"[오류] 영상 파일 없음: {video_file}")
        return None

    # 쇼츠 자동 처리
    if video_format == "shorts":
        if "#Shorts" not in title:
            title = f"{title} #Shorts"
        description = f"{description}\n\n#Shorts"

    # 채널별 태그 추가
    if lang_code and lang_code in CHANNELS:
        tags = list(set(tags + CHANNELS[lang_code]["tags_base"]))
        description += f"\n\n{CHANNELS[lang_code]['description_suffix']}"

    print(f"\n[Upload] '{title}' 업로드 준비 중...")
    print(f"  포맷: {video_format} | 공개상태: {privacy}")

    # 메타데이터
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    # 영상 업로드
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media,
    )

    response = request.execute()
    video_id = response.get("id")
    print(f"[OK] 업로드 완료 Video ID: {video_id}")
    print(f"  URL: https://youtu.be/{video_id}")

    # 썸네일 등록 (A/B 테스트용)
    if thumbnail_files:
        for i, thumb_path in enumerate(thumbnail_files):
            if thumb_path and os.path.exists(thumb_path):
                variant = chr(65 + i)  # A, B, C...
                try:
                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(thumb_path),
                    ).execute()
                    print(f"  ✓ 썸네일 {variant} 등록 완료: {thumb_path}")
                except Exception as e:
                    print(f"  ! 썸네일 {variant} 등록 실패: {e}")

    return {
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "title": title,
        "format": video_format,
        "privacy": privacy,
    }


def upload_batch(youtube, upload_items):
    """
    여러 영상을 일괄 업로드합니다.
    
    Args:
        youtube: YouTube API 서비스 객체
        upload_items: [{"video_file": ..., "title": ..., ...}] 리스트
    
    Returns:
        업로드 결과 리스트
    """
    results = []
    total = len(upload_items)

    for idx, item in enumerate(upload_items, 1):
        print(f"\n{'─'*50}")
        print(f"[Batch] {idx}/{total} 업로드 중...")

        result = upload_video(youtube, **item)
        if result:
            results.append(result)

    print(f"\n{'='*50}")
    print(f"[Batch 완료] {len(results)}/{total} 업로드 성공")
    for r in results:
        print(f"  • {r['title']} → {r['url']}")

    return results


if __name__ == "__main__":
    # 테스트 — 기존 영상 업로드
    video_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "output", "20260427_1853", "final_video_prototype.mp4"
    )

    youtube_service = get_authenticated_service()
    if youtube_service and os.path.exists(video_path):
        upload_video(
            youtube_service,
            video_file=video_path,
            title="[Test] 인플레이션 방어 배당주 시바견 애니메이션",
            description="AI가 100% 자동 생성한 트렌디한 애니메이션 영상입니다.",
            tags=["주식", "경제", "배당주"],
            video_format="longform",
            privacy="private",
        )
    else:
        print("[오류] YouTube 서비스 인증 실패 또는 영상 파일 없음")
