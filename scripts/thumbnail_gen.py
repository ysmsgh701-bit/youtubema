"""
썸네일 A/B 생성 모듈
각 영상에 대해 2종류의 썸네일을 자동 생성합니다.
- Variant A: 감정 대비형 (Before/After 분할)
- Variant B: 임팩트형 (큰 텍스트 + 강렬한 단일 이미지)
YouTube Studio 네이티브 A/B 테스트("Test and compare")에 등록하여 활용합니다.
"""
import os
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import THUMBNAIL, CHARACTER_PROMPT, CHANNELS

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    print("[Warning] Pillow가 설치되지 않았습니다. pip install pillow")


def generate_thumbnail_prompts(script_data, variant="A"):
    """
    대본 데이터로부터 썸네일 이미지 생성 프롬프트를 만듭니다.
    
    Args:
        script_data: 대본 dict
        variant: "A" (감정 대비형) 또는 "B" (임팩트형)
    
    Returns:
        이미지 생성용 프롬프트 문자열
    """
    title = script_data.get("project_title", "Video")

    if variant == "A":
        # Variant A: 감정 대비 (슬픈 vs 행복한 시바견)
        prompt = (
            f"YouTube thumbnail design, split screen composition, "
            f"LEFT SIDE: {CHARACTER_PROMPT}, looking sad and worried, "
            f"holding an empty wallet, dark gloomy background, "
            f"RIGHT SIDE: {CHARACTER_PROMPT}, looking happy and rich, "
            f"surrounded by golden coins and green upward arrows, bright sunny background, "
            f"bold dramatic contrast, ultra high quality, 1280x720, "
            f"no text overlay, clean thumbnail design"
        )
    else:
        # Variant B: 임팩트형 (단일 강렬 이미지)
        prompt = (
            f"YouTube thumbnail design, single powerful composition, "
            f"{CHARACTER_PROMPT}, standing confidently, "
            f"holding a glowing golden chart showing exponential growth, "
            f"dynamic fire and sparkle effects in background, "
            f"dramatic lighting, ultra vibrant colors, 1280x720, "
            f"cinematic quality, no text overlay"
        )

    return prompt


def add_text_overlay(image_path, text, output_path, lang="ko", style="bold"):
    """
    이미지에 텍스트 오버레이를 추가합니다.
    
    Args:
        image_path: 원본 이미지 경로
        text: 오버레이할 텍스트
        output_path: 저장 경로
        lang: 언어 코드 (폰트 선택용)
        style: 스타일 ("bold" 또는 "subtle")
    """
    if not HAS_PILLOW:
        print("  ! Pillow 미설치 — 텍스트 오버레이 생략")
        return

    img = Image.open(image_path).convert("RGBA")
    img = img.resize((THUMBNAIL["width"], THUMBNAIL["height"]), Image.LANCZOS)

    # 텍스트 오버레이 레이어
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 폰트 설정 (시스템 폰트 fallback)
    font_size = 72 if style == "bold" else 48
    try:
        channel_cfg = CHANNELS.get(lang, CHANNELS["en"])
        font = ImageFont.truetype(channel_cfg["font"], font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    # 텍스트 위치 계산 (하단 1/3)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (img.width - text_w) // 2
    y = int(img.height * 0.65)

    # 반투명 배경 바
    padding = 20
    bar_rect = [0, y - padding, img.width, y + text_h + padding * 2]
    draw.rectangle(bar_rect, fill=(0, 0, 0, 160))

    # 텍스트 (흰색 + 아웃라인)
    outline_color = (255, 50, 50) if style == "bold" else (0, 0, 0)
    for dx in [-3, 0, 3]:
        for dy in [-3, 0, 3]:
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text((x, y), text, font=font, fill=(255, 255, 255))

    # 합성 및 저장
    result = Image.alpha_composite(img, overlay).convert("RGB")
    result.save(output_path, quality=95)
    print(f"  ✓ 썸네일 저장: {output_path}")


def generate_thumbnails(script_data, output_dir, lang="ko", base_images=None):
    """
    A/B 두 종류의 썸네일을 생성합니다.
    
    Args:
        script_data: 대본 dict
        output_dir: 출력 디렉토리
        lang: 언어 코드
        base_images: {"A": path, "B": path} 기본 이미지 (없으면 프롬프트만 반환)
    
    Returns:
        {"A": path, "B": path, "prompts": {"A": str, "B": str}}
    """
    os.makedirs(output_dir, exist_ok=True)

    text_overlay = ""
    if "thumbnail_plan" in script_data:
        text_overlay = script_data["thumbnail_plan"].get("text_overlay", "")

    results = {"prompts": {}}

    for variant in ["A", "B"]:
        prompt = generate_thumbnail_prompts(script_data, variant)
        results["prompts"][variant] = prompt

        if base_images and variant in base_images and os.path.exists(base_images[variant]):
            output_path = os.path.join(output_dir, f"thumbnail_{variant}.jpg")
            style = "bold" if variant == "A" else "subtle"
            add_text_overlay(base_images[variant], text_overlay, output_path, lang, style)
            results[variant] = output_path
        else:
            # 이미지가 없으면 프롬프트만 기록
            prompt_file = os.path.join(output_dir, f"thumbnail_{variant}_prompt.txt")
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(prompt)
            results[variant] = prompt_file

    print(f"  ✓ [{lang}] 썸네일 A/B 생성 완료: {output_dir}")
    return results


if __name__ == "__main__":
    # 테스트
    sample_script = {
        "project_title": "Test_Thumbnail",
        "thumbnail_plan": {
            "text_overlay": "인플레에 이기는 법!",
        }
    }
    out = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "test_thumbnails")
    result = generate_thumbnails(sample_script, out, lang="ko")
    print("\n[결과]", json.dumps(result, indent=2, ensure_ascii=False))
