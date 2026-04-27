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

from config import (
    CHANNELS, VIDEO_FORMATS, OUTPUT_DIR, BGM_DIR,
    CHARACTER_PROMPT, PROJECT_ROOT
)
from scripts.script_translator import generate_all_translations
from scripts.audio_gen import generate_audio_from_script
from scripts.video_render import render_video
from scripts.thumbnail_gen import generate_thumbnails
from scripts.youtube_upload import get_authenticated_service, upload_video


class YouTubeAutomationPipelineV2:
    """다채널, 이중 포맷 YouTube 자동화 파이프라인"""

    def __init__(self, languages=None, formats=None, dry_run=False, api_key=None):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = os.path.join(OUTPUT_DIR, self.timestamp)
        self.languages = languages or ["ko", "ja"]
        self.formats = formats or ["longform", "shorts"]
        self.dry_run = dry_run
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

        os.makedirs(self.run_dir, exist_ok=True)
        self.results = {}

        print(f"{'='*60}")
        print(f"  YouTube 자동화 파이프라인 v2")
        print(f"  실행 ID: {self.timestamp}")
        print(f"  언어: {', '.join(self.languages)}")
        print(f"  포맷: {', '.join(self.formats)}")
        print(f"  Dry Run: {self.dry_run}")
        print(f"{'='*60}\n")

    # ─────────────────────────────────────
    # Phase 1: 트렌드 소싱
    # ─────────────────────────────────────
    def phase_1_trend_sourcing(self):
        """실시간 트렌드 소싱 (RSS/크롤링)"""
        print("\n[Phase 1] 📡 트렌드 소싱 중...")

        # TODO: 실제 구현 시 RSS 피드 또는 웹 크롤링
        topic = "인플레이션 방어 배당주 투자 전략 2026"
        print(f"  ✓ 선정 토픽: {topic}")
        return topic

    # ─────────────────────────────────────
    # Phase 2: 대본 생성 + 번역
    # ─────────────────────────────────────
    def phase_2_script_generation(self, topic):
        """대본 생성 및 다국어 번역"""
        print("\n[Phase 2] 📝 대본 생성 + 다국어 번역 중...")

        # 원본 대본 (기존 sample_script.json 활용 또는 Gemini 생성)
        source_script = os.path.join(PROJECT_ROOT, "output", "sample_script.json")

        if not os.path.exists(source_script):
            print("  ! 원본 대본 없음 — 기본 대본 생성")
            source_script = self._create_default_script(topic)

        # 다국어 번역 + 쇼츠 축약
        script_results = generate_all_translations(
            source_script, self.run_dir,
            languages=self.languages,
            api_key=self.api_key,
        )

        print(f"\n  ✓ {len(script_results)}개 언어 대본 생성 완료")
        return script_results

    def _create_default_script(self, topic):
        """기본 대본 템플릿 생성"""
        script = {
            "project_title": topic.replace(" ", "_")[:30],
            "target_market": "Global",
            "language": "Japanese",
            "lang_code": "ja",
            "main_character": "Shiba Investor (Cute, Wearing a Small Blue Tie)",
            "vibe": "Trendy Animation, Educational yet Energetic",
            "scenes": [
                {
                    "scene_no": 1,
                    "narration": "皆さん, こんにちは! 今日は最新の投資戦略をお伝えします!",
                    "image_prompt": f"{CHARACTER_PROMPT}, greeting the audience warmly, waving hand",
                    "visual_description": "시바견이 시청자에게 인사하는 모습",
                },
                {
                    "scene_no": 2,
                    "narration": "インフレに負けない配当株の選び方を解説します.",
                    "image_prompt": f"{CHARACTER_PROMPT}, pointing at a growing stock chart, excited expression",
                    "visual_description": "시바견이 주식 차트를 가리키며 설명하는 모습",
                },
                {
                    "scene_no": 3,
                    "narration": "ぜひチャンネル登録をお願いします! 次回もお楽しみに!",
                    "image_prompt": f"{CHARACTER_PROMPT}, waving goodbye, subscribe button floating nearby",
                    "visual_description": "시바견이 구독 버튼 옆에서 손을 흔드는 모습",
                },
            ],
            "thumbnail_plan": {
                "text_overlay": "配当株で勝つ!",
                "image_prompt": f"{CHARACTER_PROMPT}, ultra close-up, excited expression, golden coins raining",
            },
        }

        path = os.path.join(self.run_dir, "source_script.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)

        return path

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
        """이미지 생성 (API 연동 또는 기존 이미지 복사)"""
        with open(script_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        existing_images_dir = os.path.join(PROJECT_ROOT, "output", "20260427_1853", "images")

        for i, scene in enumerate(data["scenes"]):
            target = os.path.join(assets_dir, "images", f"scene_{i+1}.png")

            if os.path.exists(target):
                continue

            # 기존 이미지 복사 시도
            source = os.path.join(existing_images_dir, f"scene_{i+1}.png")
            if os.path.exists(source):
                import shutil
                shutil.copy2(source, target)
                print(f"    ✓ 이미지 복사: scene_{i+1}.png")
            else:
                # TODO: Gemini Image API로 실제 생성
                print(f"    ℹ 이미지 미생성 (API 연동 필요): scene_{i+1}.png")

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
            result = generate_thumbnails(script_data, thumb_dir, lang=lang)
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
    # 전체 파이프라인 실행
    # ─────────────────────────────────────
    def run_full_pipeline(self):
        """전체 파이프라인을 순차 실행합니다."""
        start_time = time.time()

        try:
            # Phase 1: 트렌드 소싱
            topic = self.phase_1_trend_sourcing()

            # Phase 2: 대본 생성 + 번역
            script_results = self.phase_2_script_generation(topic)

            # Phase 3: 에셋 생성
            self.phase_3_asset_generation(script_results)

            # Phase 4: 렌더링
            render_results = self.phase_4_rendering(script_results)

            # Phase 5: 썸네일 생성
            thumb_results = self.phase_5_thumbnails(script_results)

            # Phase 6: 업로드
            upload_results = self.phase_6_upload(render_results, thumb_results)

        except Exception as e:
            print(f"\n[오류] 파이프라인 실행 중 에러: {e}")
            import traceback
            traceback.print_exc()
            return

        # ─── 결과 요약 ───
        elapsed = time.time() - start_time
        self._print_summary(elapsed)

        # 결과 JSON 저장
        summary_path = os.path.join(self.run_dir, "pipeline_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n📋 실행 결과 저장: {summary_path}")

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
def main():
    parser = argparse.ArgumentParser(description="YouTube 자동화 파이프라인 v2")
    parser.add_argument(
        "--langs", type=str, default="ko,ja",
        help="처리할 언어 (쉼표 구분, 예: ko,ja,en)"
    )
    parser.add_argument(
        "--formats", type=str, default="longform,shorts",
        help="영상 포맷 (쉼표 구분, 예: longform,shorts)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="업로드 없이 렌더링만 실행"
    )
    parser.add_argument(
        "--api-key", type=str, default=None,
        help="Gemini API 키 (번역용)"
    )

    args = parser.parse_args()

    languages = [l.strip() for l in args.langs.split(",")]
    formats = [f.strip() for f in args.formats.split(",")]

    pipeline = YouTubeAutomationPipelineV2(
        languages=languages,
        formats=formats,
        dry_run=args.dry_run,
        api_key=args.api_key,
    )
    pipeline.run_full_pipeline()


if __name__ == "__main__":
    main()
