"""
YouTube 자동화 파이프라인 v2 — 중앙 설정 모듈
다채널, 이중 포맷(쇼츠/롱폼), 캐릭터 일관성 등 모든 설정을 관리합니다.
"""
import os

# ──────────────────────────────────────────────
# 프로젝트 루트
# ──────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
BGM_DIR = os.path.join(ASSETS_DIR, "bgm")

# ──────────────────────────────────────────────
# 채널별 설정 및 캐릭터 일관성(Seed)
# ──────────────────────────────────────────────
CHANNELS = {
    "ko": {
        "name": "Korean",
        "lang_code": "ko",
        "tts_lang": "ko",
        "font": "NanumGothic",
        "description_suffix": "#주식 #경제 #배당주 #애니메이션",
        "tags_base": ["주식", "경제", "배당주", "인플레이션", "애니메이션", "시바견"],
        "seed": 42001,
    },
    "ja": {
        "name": "Japanese",
        "lang_code": "ja",
        "tts_lang": "ja",
        "font": "NotoSansJP",
        "description_suffix": "#株式 #経済 #配当株 #アニメ",
        "tags_base": ["株式", "経済", "配当株", "インフレ", "アニメ", "柴犬"],
        "seed": 42002,
    },
    "zh-TW": {
        "name": "Traditional Chinese (Taiwan)",
        "lang_code": "zh-TW",
        "tts_lang": "zh-TW",
        "font": "NotoSansTC",
        "description_suffix": "#股票 #經濟 #配息 #動畫",
        "tags_base": ["股票", "經濟", "配息", "通膨", "動畫", "柴犬"],
        "seed": 42003,
    },
    "en": {
        "name": "English",
        "lang_code": "en",
        "tts_lang": "en",
        "font": "Arial",
        "description_suffix": "#stocks #economy #dividends #animation",
        "tags_base": ["stocks", "economy", "dividends", "inflation", "animation", "shiba"],
        "seed": 42004,
    },
}

# ──────────────────────────────────────────────
# 이미지 생성 공통 설정
# ──────────────────────────────────────────────
IMAGE_GENERATION = {
    "model": "gemini-2.0-flash", # 또는 연결할 이미지 생성 API 모델명
    "style_reference": "studio ghibli style, soft pastel colors, cel shading",
}

# ──────────────────────────────────────────────
# 영상 포맷 설정
# ──────────────────────────────────────────────
VIDEO_FORMATS = {
    "shorts": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "max_duration": 59,        # 쇼츠 59초 제한 (안전 마진)
        "aspect_ratio": "9:16",
        "subtitle_y_ratio": 0.75,  # 자막 Y 위치 비율
        "subtitle_font_size": 48,
    },
    "longform": {
        "width": 1920,
        "height": 1080,
        "fps": 24,
        "max_duration": None,      # 제한 없음
        "aspect_ratio": "16:9",
        "subtitle_y_ratio": 0.85,
        "subtitle_font_size": 40,
    },
}

# ──────────────────────────────────────────────
# 캐릭터 일관성 프롬프트
# ──────────────────────────────────────────────
CHARACTER_PROMPT = (
    "Shiba Inu cute anime character, wearing a small blue tie, "
    "expressive round eyes, fluffy golden fur, consistent character design, "
    "Ghibli inspired soft color palette, high resolution, "
    "animation cel shading style"
)

# ──────────────────────────────────────────────
# 트랜지션 / 이펙트 설정
# ──────────────────────────────────────────────
TRANSITION_DURATION = 0.5      # 장면 전환 크로스페이드 (초)
KEN_BURNS_ZOOM = 1.08          # Ken Burns 줌 배율 (1.0 = 없음)
BGM_VOLUME = 0.08              # BGM 볼륨 (나레이션 대비)

# ──────────────────────────────────────────────
# 썸네일 설정
# ──────────────────────────────────────────────
THUMBNAIL = {
    "width": 1280,
    "height": 720,
    "variants": 2,              # A/B 테스트용 2장 생성
}

# ──────────────────────────────────────────────
# API / 인증
# ──────────────────────────────────────────────
CLIENT_SECRETS_FILE = os.path.join(PROJECT_ROOT, "client_secrets.json")
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
                  "https://www.googleapis.com/auth/youtube"]
