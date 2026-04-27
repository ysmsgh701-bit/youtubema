import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload

# 인증 정보 파일 경로 (사용자가 직접 세팅해야 함)
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_authenticated_service():
    """OAuth 2.0 인증을 통해 YouTube API 서비스 객체를 반환합니다."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"[오류] '{CLIENT_SECRETS_FILE}' 파일이 존재하지 않습니다.")
        print("Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 생성하고 다운로드 받아주세요.")
        return None

    # 인증 과정 (최초 1회 브라우저 창이 열림)
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_local_server(port=0)
    
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
    return youtube

def upload_video(youtube, video_file, thumbnail_file, title, description, tags, category_id="27"):
    """영상을 업로드하고 썸네일을 지정합니다."""
    print(f"\n[Upload] '{title}' 영상 업로드 준비 중...")
    
    # 1. 영상 메타데이터 설정
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": "private", # 초기 설정: 비공개 (안전성 확보 후 public 전환)
            "selfDeclaredMadeForKids": False
        }
    }

    # 2. 영상 업로드 요청
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media
    )
    
    response = request.execute()
    video_id = response.get("id")
    print(f"[성공] 영상 업로드 완료! (Video ID: {video_id})")
    
    # 3. 썸네일 업로드
    if thumbnail_file and os.path.exists(thumbnail_file):
        print("[Upload] 썸네일 등록 중...")
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_file)
            ).execute()
            print("[성공] 썸네일 등록 완료!")
        except Exception as e:
            print(f"[오류] 썸네일 등록 실패: {e}")

if __name__ == "__main__":
    # 이전 단계에서 생성된 자산 경로
    video_path = "output/20260427_1853/final_video_prototype.mp4"
    # 실제 워크스페이스에 생성된 썸네일 이미지가 있다면 해당 경로로 수정 필요
    thumbnail_path = "" 
    
    # 업로드 메타데이터
    video_title = "[Test] 인플레이션 방어 배당주 시바견 애니메이션"
    video_desc = "AI가 100% 자동 생성한 트렌디한 애니메이션 영상입니다.\n\n#인플레이션 #배당주 #주식투자"
    video_tags = ["주식", "경제", "배당주", "인플레이션", "애니메이션"]
    
    youtube_service = get_authenticated_service()
    if youtube_service:
        if os.path.exists(video_path):
            upload_video(youtube_service, video_path, thumbnail_path, video_title, video_desc, video_tags)
        else:
            print(f"[오류] 업로드할 영상 파일이 없습니다: {video_path}")
