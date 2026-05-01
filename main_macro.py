"""
YouTube 자동화 파이프라인 v2 — 메인 오케스트레이터
다채널 병렬 처리, 쇼츠/롱폼 이중 포맷, 썸네일 A/B 생성을 통합 관리합니다.

사용법:
    python main_macro.py                           # 전체 파이프라인 (ko, ja)
    python main_macro.py --langs ko                # 한국어만
    python main_macro.py --langs ko,ja,en           # 한국어+일본어+영어
    python main_macro.py --formats shorts           # 쇼츠만
    python main_macro.py --dry-run                  # 업로드 없이 렌더링만
"""
import os
import sys
import json
import asyncio
import argparse
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 프로젝트 루트를 PATH에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# .env 자동 로드
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

from config import (
    CHANNELS, VIDEO_FORMATS, OUTPUT_DIR, BGM_DIR,
    CHARACTER_PROMPT, PROJECT_ROOT
)
from scripts.script_translator import generate_all_translations
from scripts.audio_gen import generate_audio_from_script
from scripts.video_render import render_video
from scripts.thumbnail_gen import generate_thumbnails
from scripts.youtube_upload import get_authenticated_service, upload_video
from scripts.news_fetcher import select_topic_interactive
from scripts.topic_tracker import check_duplicate, record_topic, update_uploads, print_history


class YouTubeAutomationPipelineV2:
    """다채널, 이중 포맷 YouTube 자동화 파이프라인"""

    def __init__(self, languages=None, formats=None, dry_run=False, api_key=None, run_dir=None):
        self.timestamp = (
            os.path.basename(run_dir)
            if run_dir else
            datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        self.run_dir = run_dir or os.path.join(OUTPUT_DIR, self.timestamp)
        self.languages = languages  # None = 체크포인트에서 로드 또는 기본값 적용
        self.formats = formats      # None = 체크포인트에서 로드 또는 기본값 적용
        self.dry_run = dry_run
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

        os.makedirs(self.run_dir, exist_ok=True)
        self.results = {}

        print(f"{'='*60}")
        print(f"  YouTube 자동화 파이프라인 v2")
        print(f"  실행 ID: {self.timestamp}")
        print(f"  언어: {', '.join(self.languages) if self.languages else '(체크포인트에서 로드)'}")
        print(f"  포맷: {', '.join(self.formats) if self.formats else '(체크포인트에서 로드)'}")
        print(f"  Dry Run: {self.dry_run}")
        print(f"{'='*60}\n")

    # ─────────────────────────────────────
    # Phase 1: 트렌드 소싱
    # ─────────────────────────────────────
    def phase_1_trend_sourcing(self, auto_pick=None):
        """미국/유럽/일본 Google News RSS에서 뉴스를 수집하고 토픽을 선택합니다."""
        while True:
            topic = select_topic_interactive(auto_pick=auto_pick)

            # 중복 체크
            dupes = check_duplicate(topic, threshold=0.45)
            if dupes:
                print(f"\n  [주의] 유사한 토픽이 이미 사용된 적 있습니다:")
                for entry, sim in dupes[:3]:
                    urls = ", ".join(entry.get("uploads", [])) or "URL없음"
                    print(f"    - [{entry['date']}] {entry['topic']}  (유사도 {sim:.0%})")
                    print(f"      {urls}")

                if auto_pick is not None:
                    print("  (배치 모드) 중복에도 불구하고 진행합니다.")
                    break

                try:
                    answer = input("\n  계속 진행하시겠습니까? (y=진행 / n=다시 선택): ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    answer = "y"

                if answer == "y":
                    break
                else:
                    auto_pick = None  # 다시 대화형 선택
                    continue
            else:
                break

        print(f"  선정 토픽: {topic}")
        return topic

    # ─────────────────────────────────────
    # Phase 2: 대본 생성 + 번역
    # ─────────────────────────────────────
    def phase_2_script_generation(self, topic):
        """대본 생성 및 다국어 번역"""
        print("\n[Phase 2] 📝 대본 생성 + 다국어 번역 중...")

        # API 키가 있으면 항상 토픽 기반으로 새 대본 생성
        source_script = self._create_default_script(topic)

        # 다국어 번역 + 쇼츠 축약
        script_results = generate_all_translations(
            source_script, self.run_dir,
            languages=self.languages,
            api_key=self.api_key,
        )

        print(f"\n  {len(script_results)}개 언어 대본 생성 완료")
        return script_results

    def _preview_and_confirm(self, script_results, auto_pick=None):
        """
        생성된 대본의 첫 3장면을 출력하고 진행 여부를 확인합니다.
        auto_pick 모드에서는 자동으로 진행합니다.
        """
        # 첫 번째 언어의 롱폼 대본 미리보기
        first_lang = next(iter(script_results))
        longform_path = script_results[first_lang].get("longform")
        if not longform_path or not os.path.exists(longform_path):
            return True

        with open(longform_path, "r", encoding="utf-8") as f:
            script = json.load(f)

        scenes = script.get("scenes", [])
        title = script.get("project_title", "")
        total = len(scenes)

        print(f"\n{'='*65}")
        print(f"  대본 미리보기 — {title}  ({total}장면, 약 {total*20//60}분 {total*20%60}초 예상)")
        print(f"{'='*65}")
        for scene in scenes[:3]:
            no = scene.get("scene_no", "?")
            narr = scene.get("narration", "")
            print(f"  [장면 {no}] {narr}")
            print()
        if total > 3:
            print(f"  ... 외 {total - 3}장면")
        print(f"{'='*65}")

        if auto_pick is not None:
            print("  (배치 모드) 자동 진행합니다.")
            return True

        try:
            answer = input("\n  이 대본으로 렌더링을 진행하시겠습니까? (y=진행 / n=중단): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            answer = "y"

        return answer != "n"

    def _create_default_script(self, topic):
        """Gemini API로 5분 분량(15~18장면) 대본을 생성합니다. API 없으면 기본 템플릿 사용."""
        if self.api_key:
            path = self._generate_script_with_gemini(topic)
            if path:
                return path

        # Fallback: 기본 3장면 템플릿
        script = {
            "project_title": topic.replace(" ", "_")[:30],
            "target_market": "Global",
            "language": "Korean",
            "lang_code": "ko",
            "main_character": "Shiba Investor (Cute, Wearing a Small Blue Tie)",
            "vibe": "Trendy Animation, Educational yet Energetic",
            "scenes": [
                {
                    "scene_no": 1,
                    "narration": f"안녕하세요! 오늘은 '{topic}'에 대해 알아봅니다. 꼭 끝까지 봐주세요!",
                    "image_prompt": f"{CHARACTER_PROMPT}, greeting viewers warmly, waving hand enthusiastically",
                    "visual_description": "시바견이 시청자에게 인사하는 모습",
                },
                {
                    "scene_no": 2,
                    "narration": "전문가들은 이 상황을 어떻게 분석하고 있을까요? 지금 바로 핵심을 짚어드립니다.",
                    "image_prompt": f"{CHARACTER_PROMPT}, pointing at a large news headline on a screen, serious expression",
                    "visual_description": "시바견이 뉴스 화면을 가리키며 설명하는 모습",
                },
                {
                    "scene_no": 3,
                    "narration": "오늘 내용이 도움이 됐다면 구독과 좋아요 부탁드립니다! 다음 영상에서 또 만나요!",
                    "image_prompt": f"{CHARACTER_PROMPT}, waving goodbye, subscribe button and like button floating nearby",
                    "visual_description": "시바견이 구독/좋아요 버튼 옆에서 손을 흔드는 모습",
                },
            ],
            "thumbnail_plan": {
                "text_overlay": "지금 꼭 봐야 할 경제 뉴스",
                "image_prompt": f"{CHARACTER_PROMPT}, ultra close-up, shocked expression, money and charts exploding around",
            },
        }

        path = os.path.join(self.run_dir, "source_script.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)
        return path

    def _generate_script_with_gemini(self, topic):
        """Gemini로 25~28장면, 약 10분 분량 롱폼 대본을 생성합니다."""
        try:
            from google import genai as gai
            client = gai.Client(api_key=self.api_key)

            prompt = f"""
You are a professional YouTube script writer for a Korean investment education channel.
Write a complete script for a ~10 minute YouTube video (horizontal 16:9) about this topic:
"{topic}"

Character: Cute Shiba Inu anime character wearing a small blue tie (friendly financial expert)
Style: Energetic, educational, conversational Korean. Natural spoken-word pacing.

STRICT Requirements:
- EXACTLY 25 to 28 scenes
- Each narration: 60~80 Korean words (~20~25 seconds of speech at a natural pace)
  → Total target: ~600~700 seconds = ~10 minutes
- Scene 1: Powerful 3-second hook question or shocking statistic
- Scenes 2~5: Context — why this matters right now
- Scenes 6~20: Main educational content split into numbered steps or key points
- Scenes 21~25: Real-world examples, data, or case study
- Scenes 26~28: Summary + strong call-to-action (subscribe, like, comment)
- image_prompt: vivid English description for AI image generation, ALWAYS include "{CHARACTER_PROMPT}"
- visual_description: one-line Korean description

Return ONLY valid JSON, no markdown, no explanation:
{{
  "project_title": "short_title_underscored_max30chars",
  "target_market": "Global",
  "language": "Korean",
  "lang_code": "ko",
  "main_character": "Shiba Investor (Cute, Wearing a Small Blue Tie)",
  "vibe": "Trendy Animation, Educational yet Energetic",
  "scenes": [
    {{
      "scene_no": 1,
      "narration": "Korean narration 60~80 words...",
      "image_prompt": "English image prompt always starting with the character description...",
      "visual_description": "한 줄 장면 설명..."
    }}
  ],
  "thumbnail_plan": {{
    "text_overlay": "강렬한 텍스트 10자 이내",
    "image_prompt": "English thumbnail image prompt..."
  }}
}}
"""
            print("  Gemini로 10분 대본 생성 중... (25~28장면, 잠시 기다려주세요)")
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            raw = response.text.strip()

            # JSON 블록 추출
            if "```" in raw:
                parts = raw.split("```")
                for part in parts:
                    p = part.strip()
                    if p.startswith("json"):
                        p = p[4:]
                    p = p.strip()
                    if p.startswith("{"):
                        raw = p
                        break

            script = json.loads(raw.strip())
            scene_count = len(script.get("scenes", []))
            total_words = sum(len(s.get("narration", "").split()) for s in script.get("scenes", []))
            print(f"  Gemini 대본 생성 완료: {scene_count}장면, 총 {total_words}단어")

            path = os.path.join(self.run_dir, "source_script.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(script, f, ensure_ascii=False, indent=2)
            return path

        except Exception as e:
            print(f"  Gemini 대본 생성 실패, 기본 템플릿 사용: {e}")
            return None

    # ─────────────────────────────────────
    # Phase 3: 에셋 생성 (이미지 + 음성)
    # ─────────────────────────────────────
    def phase_3_asset_generation(self, script_results):
        """이미지 + 음성 에셋 생성"""
        print("\n[Phase 3] 🎨 에셋 생성 중 (이미지 + 음성)...")

        for lang, paths in script_results.items():
            for fmt, script_path in paths.items():
                if fmt not in self.formats:
                    continue

                print(f"\n  [{lang}/{fmt}] 에셋 생성...")
                assets_dir = os.path.join(self.run_dir, lang, fmt)
                os.makedirs(os.path.join(assets_dir, "images"), exist_ok=True)
                os.makedirs(os.path.join(assets_dir, "audio"), exist_ok=True)

                # 음성 생성
                generate_audio_from_script(script_path, assets_dir, lang_code=lang)

                # 이미지 생성 (TODO: Gemini Image API 연동)
                # 현재는 기존 이미지 복사 또는 placeholder
                self._generate_or_copy_images(script_path, assets_dir)

        print("\n  ✓ 에셋 생성 완료")

    def _generate_or_copy_images(self, script_path, assets_dir):
        """이미지 생성: Pollinations.ai → Gemini API → Pillow 자동 생성 순서로 시도"""
        with open(script_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        fmt = data.get("format", "longform")
        is_shorts = fmt == "shorts"

        for i, scene in enumerate(data["scenes"]):
            target = os.path.join(assets_dir, "images", f"scene_{i+1}.png")

            if os.path.exists(target):
                continue

            prompt = scene.get("image_prompt", "")

            # 1순위: Pollinations.ai (무료, 키 불필요)
            if self._pollinations_generate_image(prompt, target, vertical=is_shorts):
                print(f"    Pollinations 이미지 생성: scene_{i+1}.png")
                continue

            # 2순위: Gemini 이미지 생성 API (유료 플랜 전용)
            if self.api_key:
                if self._gemini_generate_image(prompt, target):
                    print(f"    Gemini 이미지 생성: scene_{i+1}.png")
                    continue

            # 3순위: Pillow로 장면별 배경 이미지 자동 생성
            self._make_scene_image(scene, i, target, vertical=is_shorts)
            print(f"    배경 이미지 생성: scene_{i+1}.png")

    def _pollinations_generate_image(self, prompt, output_path, vertical=False):
        """Pollinations.ai로 이미지를 생성합니다. 무료, API 키 불필요. 성공 시 True 반환."""
        import urllib.parse
        try:
            import requests
        except ImportError:
            return False
        try:
            w, h = (1080, 1920) if vertical else (1920, 1080)
            encoded = urllib.parse.quote(prompt[:400])
            url = (
                f"https://image.pollinations.ai/prompt/{encoded}"
                f"?width={w}&height={h}&nologo=true&model=flux"
            )
            r = requests.get(url, timeout=60)
            if r.status_code == 200 and r.content:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                return True
        except Exception:
            pass
        return False

    def _gemini_generate_image(self, prompt, output_path):
        """Gemini API로 장면 이미지를 생성합니다. 성공 시 True 반환."""
        try:
            from google import genai as gai
            from google.genai import types as gtypes
            client = gai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=f"Create an animation-style scene image: {prompt}",
                config=gtypes.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
            for cand in response.candidates:
                for part in cand.content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        with open(output_path, "wb") as f:
                            f.write(part.inline_data.data)
                        return True
        except Exception:
            pass
        return False

    def _make_scene_image(self, scene, index, output_path, vertical=False):
        """Pillow로 장면 번호·설명이 담긴 배경 이미지를 생성합니다."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            w, h = (1080, 1920) if vertical else (1920, 1080)
            img = Image.new("RGB", (w, h))
            draw = ImageDraw.Draw(img)

            # 장면 번호에 따라 다른 색조 (16가지 색상 순환)
            palettes = [
                (10, 20, 60), (20, 10, 60), (10, 40, 50), (40, 10, 50),
                (60, 20, 10), (50, 40, 10), (10, 60, 30), (30, 10, 60),
                (15, 30, 55), (55, 15, 30), (30, 55, 15), (40, 20, 55),
                (20, 55, 40), (55, 40, 20), (10, 50, 45), (45, 10, 50),
            ]
            base_r, base_g, base_b = palettes[index % len(palettes)]

            for y in range(h):
                ratio = y / h
                r = int(base_r + ratio * 30)
                g = int(base_g + ratio * 30)
                b = int(base_b + ratio * 30)
                draw.line([(0, y), (w, y)], fill=(r, g, b))

            # 장면 번호 (한글 지원 폰트 우선)
            def _load_font(size):
                for path in ["C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/gulim.ttc", "arial.ttf"]:
                    try:
                        return ImageFont.truetype(path, size)
                    except (OSError, IOError):
                        pass
                return ImageFont.load_default()

            font_large = _load_font(120)
            font_small = _load_font(40)

            scene_no = scene.get("scene_no", index + 1)
            draw.text((80, 80), f"Scene {scene_no}", font=font_large, fill=(255, 255, 255, 180))

            # 장면 설명 (줄바꿈 처리)
            desc = scene.get("visual_description", scene.get("narration", ""))[:80]
            draw.text((80, h - 120), desc, font=font_small, fill=(200, 200, 200))

            img.save(output_path)
        except Exception as e:
            # Pillow 없으면 빈 검정 이미지
            try:
                from PIL import Image
                Image.new("RGB", (1080, 1920) if vertical else (1920, 1080), (10, 10, 40)).save(output_path)
            except Exception:
                pass

    # ─────────────────────────────────────
    # Phase 4: 렌더링 (병렬)
    # ─────────────────────────────────────
    def phase_4_rendering(self, script_results):
        """쇼츠 + 롱폼 영상 렌더링"""
        print("\n[Phase 4] 🎬 영상 렌더링 중...")

        render_results = {}
        bgm_path = self._find_bgm()

        for lang, paths in script_results.items():
            render_results[lang] = {}

            for fmt, script_path in paths.items():
                if fmt not in self.formats:
                    continue

                assets_dir = os.path.join(self.run_dir, lang, fmt)
                output_path = os.path.join(self.run_dir, lang, fmt, f"final_{fmt}.mp4")

                result = render_video(
                    script_path, assets_dir, output_path,
                    video_format=fmt,
                    bgm_path=bgm_path,
                )

                if result:
                    render_results[lang][fmt] = result

        self.results["renders"] = render_results
        return render_results

    def _find_bgm(self):
        """BGM 폴더에서 사용 가능한 BGM 검색"""
        if os.path.exists(BGM_DIR):
            for f in os.listdir(BGM_DIR):
                if f.endswith((".mp3", ".wav", ".ogg")):
                    return os.path.join(BGM_DIR, f)
        return None

    # ─────────────────────────────────────
    # Phase 5: 썸네일 생성
    # ─────────────────────────────────────
    def phase_5_thumbnails(self, script_results):
        """A/B 썸네일 생성"""
        print("\n[Phase 5] 🖼️ 썸네일 A/B 생성 중...")

        thumb_results = {}

        for lang, paths in script_results.items():
            # 롱폼 대본 기반으로 썸네일 생성
            script_path = paths.get("longform", paths.get("shorts"))
            if not script_path:
                continue

            with open(script_path, "r", encoding="utf-8") as f:
                script_data = json.load(f)

            thumb_dir = os.path.join(self.run_dir, lang, "thumbnails")
            result = generate_thumbnails(script_data, thumb_dir, lang=lang, api_key=self.api_key)
            thumb_results[lang] = result

        self.results["thumbnails"] = thumb_results
        return thumb_results

    # ─────────────────────────────────────
    # Phase 6: 업로드
    # ─────────────────────────────────────
    def phase_6_upload(self, render_results, thumb_results):
        """YouTube 업로드"""
        if self.dry_run:
            print("\n[Phase 6] ⏭️ Dry Run 모드 — 업로드 생략")
            return {}

        print("\n[Phase 6] 🚀 YouTube 업로드 중...")

        youtube = get_authenticated_service()
        if not youtube:
            print("  ! 인증 실패 — 업로드 중단")
            return {}

        upload_results = {}

        for lang, formats in render_results.items():
            upload_results[lang] = {}
            channel = CHANNELS.get(lang, {})

            for fmt, render_info in formats.items():
                video_file = render_info["path"]
                if not os.path.exists(video_file):
                    continue

                # 제목 생성
                title = f"[{channel.get('name', lang)}] 배당주 투자 전략"
                if fmt == "shorts":
                    title = f"배당주 투자 꿀팁 #Shorts"

                # 썸네일 파일
                thumb_files = []
                if lang in thumb_results:
                    for variant in ["A", "B"]:
                        path = thumb_results[lang].get(variant, "")
                        if path and os.path.exists(path) and path.endswith((".jpg", ".png")):
                            thumb_files.append(path)

                result = upload_video(
                    youtube,
                    video_file=video_file,
                    title=title,
                    description=f"AI가 자동 생성한 {channel.get('name', '')} 애니메이션 영상입니다.",
                    tags=channel.get("tags_base", []),
                    thumbnail_files=thumb_files,
                    video_format=fmt,
                    privacy="private",
                    lang_code=lang,
                )

                if result:
                    upload_results[lang][fmt] = result

        self.results["uploads"] = upload_results
        return upload_results

    # ─────────────────────────────────────
    # 체크포인트 저장/로드
    # ─────────────────────────────────────
    def save_checkpoint(self, topic, script_results):
        """Phase 2 완료 후 체크포인트 저장 — Phase 3-6 재개 시 사용"""
        checkpoint = {
            "timestamp": self.timestamp,
            "run_dir": self.run_dir,
            "languages": self.languages,
            "formats": self.formats,
            "topic": topic,
            "script_results": script_results,
        }
        path = os.path.join(self.run_dir, "checkpoint.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        return path

    def load_checkpoint(self):
        """저장된 체크포인트 로드"""
        path = os.path.join(self.run_dir, "checkpoint.json")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"체크포인트 파일 없음: {path}\n"
                f"  먼저 Phase 1-2를 실행하세요: python main_macro.py --phase 1-2"
            )
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ─────────────────────────────────────
    # 단계별 파이프라인 실행
    # ─────────────────────────────────────
    def run_phases(self, start_phase=1, end_phase=6, auto_pick=None):
        """지정된 Phase 범위만 실행합니다."""
        start_time = time.time()
        topic = None
        script_results = None

        try:
            # Phase 3+ 시작 시 체크포인트에서 복원
            if start_phase >= 3:
                ck = self.load_checkpoint()
                topic = ck["topic"]
                script_results = ck["script_results"]
                # CLI에서 langs/formats를 지정하지 않았으면 체크포인트 값 사용
                if self.languages is None:
                    self.languages = ck["languages"]
                if self.formats is None:
                    self.formats = ck["formats"]
                print(f"  📂 체크포인트 로드: {self.run_dir}")
                print(f"  토픽: {topic}")

            # None이면 기본값 적용 (Phase 1-2 신규 실행)
            if self.languages is None:
                self.languages = ["ko", "ja"]
            if self.formats is None:
                self.formats = ["longform", "shorts"]

            if start_phase <= 1 <= end_phase:
                topic = self.phase_1_trend_sourcing(auto_pick=auto_pick)

            if start_phase <= 2 <= end_phase:
                if topic is None:
                    ck = self.load_checkpoint()
                    topic = ck["topic"]
                script_results = self.phase_2_script_generation(topic)
                ck_path = self.save_checkpoint(topic, script_results)
                print(f"\n  체크포인트 저장: {ck_path}")

                # 대본 미리보기 + 진행 여부 확인
                if not self._preview_and_confirm(script_results, auto_pick=auto_pick):
                    print("\n  중단됩니다. 대본을 수정 후 다시 실행하세요.")
                    print(f"    python main_macro.py --phase 3-6 --run-dir {self.timestamp}")
                    return

                # 토픽 히스토리 기록
                record_topic(topic, self.timestamp)

            # Phase 2까지만 실행하고 종료 — 검토 안내 출력
            if end_phase <= 2:
                self._print_review_instructions(script_results)
                return

            if start_phase <= 3 <= end_phase:
                self.phase_3_asset_generation(script_results)

            if start_phase <= 4 <= end_phase:
                render_results = self.phase_4_rendering(script_results)
            else:
                render_results = self.results.get("renders", {})

            if start_phase <= 5 <= end_phase:
                thumb_results = self.phase_5_thumbnails(script_results)
            else:
                thumb_results = self.results.get("thumbnails", {})

            if start_phase <= 6 <= end_phase:
                self.phase_6_upload(render_results, thumb_results)

        except Exception as e:
            print(f"\n[오류] 파이프라인 실행 중 에러: {e}")
            import traceback
            traceback.print_exc()
            return

        elapsed = time.time() - start_time
        self._print_summary(elapsed)

        # 업로드 URL을 히스토리에 저장
        uploads = self.results.get("uploads", {})
        urls = [
            info.get("url")
            for formats in uploads.values()
            for info in formats.values()
            if info.get("url")
        ]
        if urls and topic:
            update_uploads(self.timestamp, urls)
            print(f"  히스토리 업데이트: {len(urls)}개 URL 기록됨")

        summary_path = os.path.join(self.run_dir, "pipeline_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n실행 결과 저장: {summary_path}")

    def _print_review_instructions(self, script_results):
        """Phase 2 완료 후 검토 안내 메시지 출력"""
        run_id = os.path.basename(self.run_dir)
        extra = ""
        if self.dry_run:
            extra += " --dry-run"

        print(f"\n{'='*60}")
        print(f"  ✅ Phase 1-2 완료 — 대본을 검토하세요")
        print(f"  📁 실행 ID: {run_id}")
        print(f"\n  생성된 대본 파일:")
        for lang, paths in script_results.items():
            for fmt, path in paths.items():
                print(f"    [{lang}/{fmt}] {path}")
        print(f"\n  ▶ 검토 완료 후 이어서 실행:")
        print(f"    python main_macro.py --phase 3-6 --run-dir {run_id}{extra}")
        print(f"{'='*60}")

    def _print_summary(self, elapsed):
        """실행 결과 요약 출력"""
        print(f"\n{'='*60}")
        print(f"  ✅ 파이프라인 실행 완료!")
        print(f"  소요 시간: {elapsed:.1f}초 ({elapsed/60:.1f}분)")
        print(f"  출력 디렉토리: {self.run_dir}")
        print(f"{'='*60}")

        # 렌더링 결과
        renders = self.results.get("renders", {})
        if renders:
            print("\n  📹 렌더링 결과:")
            for lang, formats in renders.items():
                for fmt, info in formats.items():
                    print(f"    • [{lang}/{fmt}] {info.get('duration', 0):.1f}초 → {info.get('path', '')}")

        # 업로드 결과
        uploads = self.results.get("uploads", {})
        if uploads:
            print("\n  🚀 업로드 결과:")
            for lang, formats in uploads.items():
                for fmt, info in formats.items():
                    print(f"    • [{lang}/{fmt}] {info.get('url', 'N/A')}")


# ─────────────────────────────────────
# CLI
# ─────────────────────────────────────
def _parse_phase(phase_str):
    """'1-2' → (1, 2), '3-6' → (3, 6), '1' → (1, 1)"""
    if "-" in phase_str:
        parts = phase_str.split("-", 1)
        return int(parts[0]), int(parts[1])
    n = int(phase_str)
    return n, n


def main():
    parser = argparse.ArgumentParser(
        description="YouTube 자동화 파이프라인 v2.5",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 대본까지만 생성하고 검토 (기본 권장)
  python main_macro.py --phase 1-2

  # 검토 후 이어서 렌더링 + 업로드
  python main_macro.py --phase 3-6 --run-dir 20260427_153000

  # 전체 파이프라인 (검토 없이 자동)
  python main_macro.py --phase 1-6

  # 특정 언어 + 포맷만
  python main_macro.py --phase 1-2 --langs ko,en --formats shorts
        """,
    )
    parser.add_argument(
        "--phase", type=str, default="1-6",
        help="실행할 Phase 범위 (예: 1-2, 3-6, 1-6). 기본값: 1-6",
    )
    parser.add_argument(
        "--run-dir", type=str, default=None,
        help="이어서 실행할 run ID 또는 경로 (--phase 3-6 시 필요)",
    )
    parser.add_argument(
        "--langs", type=str, default=None,
        help="처리할 언어 (쉼표 구분, 예: ko,ja,en) 또는 'auto' (요일별 분할). "
             "Phase 3+ 재개 시 생략하면 체크포인트 값 사용",
    )
    parser.add_argument(
        "--formats", type=str, default=None,
        help="영상 포맷 (쉼표 구분, 예: longform,shorts). "
             "Phase 3+ 재개 시 생략하면 체크포인트 값 사용",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="업로드 없이 렌더링만 실행",
    )
    parser.add_argument(
        "--api-key", type=str, default=None,
        help="Gemini API 키 (번역/대본 생성/썸네일 생성용)",
    )
    parser.add_argument(
        "--pick", type=int, default=None,
        help="뉴스 번호 자동 선택 (배치 모드용). 생략 시 대화형 선택",
    )

    args = parser.parse_args()
    start_phase, end_phase = _parse_phase(args.phase)

    # --run-dir: 타임스탬프 문자열이면 OUTPUT_DIR 아래에서 탐색
    run_dir = None
    if args.run_dir:
        candidate = args.run_dir
        if not os.path.isabs(candidate):
            candidate = os.path.join(OUTPUT_DIR, candidate)
        if not os.path.exists(candidate):
            print(f"[오류] run-dir 경로를 찾을 수 없습니다: {candidate}")
            sys.exit(1)
        run_dir = candidate
    elif start_phase >= 3:
        print("[오류] Phase 3 이상 시작 시 --run-dir 을 지정해야 합니다.")
        print("  예: python main_macro.py --phase 3-6 --run-dir 20260427_153000")
        sys.exit(1)

    # 언어 결정
    if args.langs is None:
        languages = None  # Phase 3+에서 체크포인트로부터 로드
    elif args.langs.lower() == "auto":
        weekday = datetime.today().weekday()
        if weekday in [0, 2, 4]:
            languages = ["ko", "en"]
            print(f"[스케줄링] 월/수/금 세트 선택: {languages}")
        elif weekday in [1, 3, 5]:
            languages = ["ja", "zh-TW"]
            print(f"[스케줄링] 화/목/토 세트 선택: {languages}")
        else:
            languages = ["ko", "ja"]
            print(f"[스케줄링] 일요일 세트 선택: {languages}")
    else:
        languages = [l.strip() for l in args.langs.split(",")]

    # 포맷 결정
    formats = (
        [f.strip() for f in args.formats.split(",")]
        if args.formats else None
    )

    pipeline = YouTubeAutomationPipelineV2(
        languages=languages,
        formats=formats,
        dry_run=args.dry_run,
        api_key=args.api_key,
        run_dir=run_dir,
    )
    pipeline.run_phases(start_phase, end_phase, auto_pick=args.pick)


if __name__ == "__main__":
    main()
