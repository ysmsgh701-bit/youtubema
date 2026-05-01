"""
썸네일 생성 모듈 (트랙별 PIL 템플릿)
- finance 트랙: 다크 네이비 + 골드 라인, 전문직 느낌
- tft 트랙: 딥 퍼플 + 네온, 게이밍 느낌

독립 실행:
    python scripts/generate_thumb.py "엑셀 대신 AI 쓰는 법" config/finance_profile.yaml
    python scripts/generate_thumb.py "1등각 무너짐 ㅋㅋ" config/tft_profile.yaml -o out.jpg
"""
import os
import argparse

import yaml

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

THUMB_W, THUMB_H = 1280, 720

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgunbd.ttf",   # 맑은 고딕 Bold
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/gulim.ttc",
]


def _load_font(size: int):
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            pass
    return ImageFont.load_default()


def _wrap_text(text: str, max_chars: int = 13) -> list:
    """긴 제목을 최대 3줄로 나눕니다."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]


def generate_thumbnail(title: str, profile: dict, output_path: str) -> str:
    """
    트랙 프로파일 스타일로 썸네일을 생성합니다.

    Args:
        title: 썸네일에 표시할 텍스트
        profile: config/*.yaml 로드 결과 dict
        output_path: 저장 경로 (.jpg 권장)

    Returns:
        저장된 파일 경로
    """
    if not HAS_PILLOW:
        raise ImportError("Pillow가 설치되지 않았습니다.\n  pip install pillow")

    style = profile.get("style", {})
    layout = style.get("layout", "professional")
    colors = style.get("colors", {})

    primary = tuple(colors.get("primary", [15, 25, 60]))
    secondary = tuple(colors.get("secondary", [255, 200, 50]))
    text_color = tuple(colors.get("text", [255, 255, 255]))
    accent = tuple(colors.get("accent", [50, 200, 100]))

    img = Image.new("RGB", (THUMB_W, THUMB_H), primary)
    draw = ImageDraw.Draw(img)

    if layout == "gaming":
        _draw_gaming_bg(draw, img, primary, secondary, accent)
    else:
        _draw_professional_bg(draw, img, primary, secondary, accent)

    # 제목 텍스트 (중앙 배치)
    font_size = style.get("font_size_title", 72)
    font = _load_font(font_size)
    lines = _wrap_text(title, max_chars=14)
    line_h = font_size + 12
    total_h = len(lines) * line_h
    y = (THUMB_H - total_h) // 2

    for line in lines:
        # 드롭 섀도우
        draw.text((82, y + 4), line, font=font, fill=(0, 0, 0))
        draw.text((80, y), line, font=font, fill=text_color)
        y += line_h

    # 채널명 워터마크 (좌하단)
    channel_name = profile.get("name", "")
    wm_font = _load_font(30)
    draw.text((40, THUMB_H - 55), channel_name, font=wm_font, fill=secondary)

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    img.save(output_path, "JPEG", quality=95)
    print(f"[Thumb] 생성 완료: {output_path}")
    return output_path


def _draw_professional_bg(draw, img, primary, secondary, accent):
    """재무 트랙: 다크 네이비 그라데이션 + 골드 테두리 + 차트 데코."""
    w, h = img.size

    for y in range(h):
        ratio = y / h
        r = min(255, int(primary[0] + ratio * 25))
        g = min(255, int(primary[1] + ratio * 25))
        b = min(255, int(primary[2] + ratio * 15))
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # 좌측 골드 세로 강조선
    draw.rectangle([0, 0, 8, h], fill=secondary)
    # 상단 골드 수평선
    draw.rectangle([0, 0, w, 5], fill=secondary)

    # 우측 하단: 상승 차트 라인 데코
    pts = [
        (w - 380, h - 70), (w - 290, h - 155),
        (w - 200, h - 95), (w - 100, h - 215), (w - 20, h - 170),
    ]
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=accent, width=3)
    for px, py in pts:
        draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=accent)


def _draw_gaming_bg(draw, img, primary, secondary, accent):
    """TFT 트랙: 딥 퍼플 그라데이션 + 네온 하이라이트 + 다이아몬드 패턴."""
    w, h = img.size

    for y in range(h):
        ratio = y / h
        r = min(255, int(primary[0] + ratio * 20))
        g = min(255, int(primary[1] + ratio * 8))
        b = min(255, int(primary[2] + ratio * 50))
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # 희미한 다이아몬드 격자 패턴
    for gx in range(0, w, 110):
        for gy in range(0, h, 110):
            pts = [
                (gx, gy - 28), (gx + 28, gy),
                (gx, gy + 28), (gx - 28, gy),
            ]
            draw.polygon(pts, outline=(
                secondary[0], secondary[1], secondary[2]
            ))

    # 하단 네온 라인
    draw.rectangle([0, h - 7, w, h], fill=secondary)
    # 대각선 강조 (좌상단 → 우하단)
    draw.line([(0, 0), (w, h)], fill=(secondary[0], secondary[1], secondary[2]), width=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="트랙별 썸네일 생성")
    parser.add_argument("title", help="썸네일 제목 텍스트")
    parser.add_argument("profile", help="트랙 프로파일 YAML 경로")
    parser.add_argument("-o", "--output", default="thumbnail.jpg", help="출력 파일 경로")
    args = parser.parse_args()

    with open(args.profile, "r", encoding="utf-8") as f:
        prof = yaml.safe_load(f)

    generate_thumbnail(args.title, prof, args.output)
