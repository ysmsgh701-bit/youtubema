"""
블로그 글 -> 유튜브 대본 변환 모듈
Gemini API로 블로그 원문을 트랙에 맞는 유튜브 촬영 대본으로 변환합니다.

독립 실행:
    python scripts/generate_script.py blog.txt config/finance_profile.yaml
    python scripts/generate_script.py blog.txt config/tft_profile.yaml -o output/scripts/
"""
import os
import sys
import argparse
from datetime import datetime

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_script(blog_content: str, profile: dict, api_key: str = None) -> str:
    """
    블로그 원문을 트랙 프로파일에 맞는 유튜브 촬영 대본으로 변환합니다.

    Args:
        blog_content: 블로그 원문 텍스트
        profile: 트랙 프로파일 dict
        api_key: Gemini API 키

    Returns:
        마크다운 형식의 촬영 대본 문자열
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[Script] GEMINI_API_KEY 없음 - 기본 템플릿 사용")
        return _fallback_script(blog_content, profile)

    try:
        from google import genai as gai
        client = gai.Client(api_key=api_key)
    except ImportError:
        print("[Script] google-genai 미설치 - 기본 템플릿 사용")
        return _fallback_script(blog_content, profile)

    system_prompt = profile.get("script_system_prompt", "")
    track_name = profile.get("name", "")

    prompt = f"""{system_prompt}

아래는 내가 쓴 블로그 글입니다. 이 글의 핵심 내용을 유지하면서 유튜브 촬영 대본으로 변환해 주세요.

[블로그 원문]
{blog_content}

[변환 규칙]
- 블로그 특유의 글쓰기 표현(문어체, 긴 설명)을 구어체 나레이션으로 바꿔주세요
- 화면에 보여줄 내용은 [화면] 태그로 명시해주세요
- 각 섹션에 예상 소요 시간을 표시해주세요
- 유튜브 시청자가 이탈하지 않도록 훅을 강화해주세요
- 마지막에 구독/좋아요 CTA를 추가해주세요

[출력 형식]
# [영상 제목]

## 🎬 훅 (0:00~0:30)
[화면] 화면 구성 설명
나레이션: ...

## 📌 본론 1 - 소제목 (0:30~2:00)
[화면] ...
나레이션: ...

## ✅ 마무리 + CTA (~마지막 30초)
나레이션: 오늘 영상이 도움이 됐다면 구독과 좋아요 부탁드립니다!"""

    print(f"[Script] 블로그 -> 대본 변환 중... (트랙: {track_name}, {len(blog_content)}자)")
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"[Script] Gemini 호출 실패: {e}")
        return _fallback_script(blog_content, profile)


def _fallback_script(blog_content: str, profile: dict) -> str:
    name = profile.get("name", "채널")
    # 블로그 첫 줄을 제목으로 추출
    first_line = next((l.strip().lstrip("#").strip() for l in blog_content.splitlines() if l.strip()), "블로그 글")
    title = first_line[:40]
    return f"""# {title}

## 🎬 훅 (0:00~0:30)
[화면] 제목 슬라이드
나레이션: 안녕하세요, {name}입니다. 오늘은 블로그에서 반응이 좋았던 내용을 영상으로 정리해봤습니다.

## 📌 본론 (0:30~5:00)
[화면] 실제 화면 시연
나레이션: (블로그 내용을 바탕으로 구어체로 설명)

## ✅ 마무리 + CTA
나레이션: 오늘 내용이 도움이 됐다면 구독과 좋아요 부탁드립니다!

---
[원문 요약]
{blog_content[:300]}...
"""


def _extract_title(blog_content: str) -> str:
    """블로그 원문에서 제목을 추출합니다."""
    for line in blog_content.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:40]
    return "blog_script"


def save_script(script_text: str, output_dir: str, title: str = "") -> str:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c for c in title if c.isalnum() or c in " _-")[:30].strip() or "script"
    filename = f"{timestamp}_{safe}.md"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(script_text)
    print(f"[Script] 대본 저장: {path}")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="블로그 -> 유튜브 대본 변환")
    parser.add_argument("blog_file", help="블로그 원문 텍스트 파일 경로")
    parser.add_argument("profile", help="트랙 프로파일 YAML 경로")
    parser.add_argument(
        "-o", "--output-dir", default="output/scripts",
        help="저장 디렉토리 (기본: output/scripts)"
    )
    args = parser.parse_args()

    with open(args.blog_file, "r", encoding="utf-8") as f:
        blog = f.read()

    with open(args.profile, "r", encoding="utf-8") as f:
        prof = yaml.safe_load(f)

    script = generate_script(blog, prof)
    title = _extract_title(blog)
    path = save_script(script, args.output_dir, title)

    print("\n--- 대본 미리보기 (앞 600자) ---")
    print(script[:600])
    print(f"\n전체 대본: {path}")
