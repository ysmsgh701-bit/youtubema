"""
대본 생성 모듈 (촬영 전 단계)
Gemini API로 트랙별 시스템 프롬프트를 활용해 촬영 대본을 생성합니다.
생성된 대본은 .md 파일로 저장하여 OBS/화면 녹화 전에 참조합니다.

독립 실행:
    python scripts/generate_script.py "엑셀 대신 AI 쓰는 3가지 이유" config/finance_profile.yaml
    python scripts/generate_script.py "신조합 쓰면 OP인 이유" config/tft_profile.yaml -o output/scripts/
"""
import os
import sys
import argparse
from datetime import datetime

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_script(topic: str, profile: dict, api_key: str = None) -> str:
    """
    주제와 트랙 프로파일에 맞는 촬영 대본을 생성합니다.

    Args:
        topic: 영상 주제
        profile: 트랙 프로파일 dict
        api_key: Gemini API 키

    Returns:
        마크다운 형식의 대본 문자열
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[Script] GEMINI_API_KEY 없음 - 기본 템플릿 사용")
        return _fallback_script(topic, profile)

    try:
        from google import genai as gai
        client = gai.Client(api_key=api_key)
    except ImportError:
        print("[Script] google-genai 미설치 - 기본 템플릿 사용")
        return _fallback_script(topic, profile)

    system_prompt = profile.get("script_system_prompt", "")
    track_name = profile.get("name", "")

    prompt = f"""{system_prompt}

주제: {topic}

위 주제로 유튜브 촬영 대본을 마크다운 형식으로 작성하세요.
각 섹션에 예상 소요 시간을 표시하고, 화면에 보여줄 내용도 [화면] 태그로 명시하세요.

형식 예시:
# [제목]

## 🎬 훅 (0:00~0:30)
[화면] 화면 구성 설명
나레이션: ...

## 📌 본론 1 - 소제목 (0:30~2:00)
[화면] ...
나레이션: ...

## ✅ 마무리 + CTA (~마지막 30초)
나레이션: 오늘 영상이 도움이 됐다면 구독과 좋아요 부탁드립니다!"""

    print(f"[Script] '{topic}' 대본 생성 중... (트랙: {track_name})")
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"[Script] Gemini 호출 실패: {e}")
        return _fallback_script(topic, profile)


def _fallback_script(topic: str, profile: dict) -> str:
    name = profile.get("name", "채널")
    return f"""# {topic}

## 🎬 훅 (0:00~0:30)
[화면] 제목 슬라이드 또는 문제 상황 스크린샷
나레이션: 안녕하세요, {name}입니다. 오늘은 "{topic}"에 대해 다뤄볼게요.

## 📌 본론 (0:30~5:00)
[화면] 실제 화면 시연
나레이션: (내용 작성)

## ✅ 마무리 + CTA
나레이션: 오늘 내용이 도움이 됐다면 구독과 좋아요 부탁드립니다!
"""


def save_script(script_text: str, output_dir: str, topic: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c for c in topic if c.isalnum() or c in " _-")[:30].strip()
    filename = f"{timestamp}_{safe}.md"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(script_text)
    print(f"[Script] 대본 저장: {path}")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="트랙별 촬영 대본 생성")
    parser.add_argument("topic", help="영상 주제")
    parser.add_argument("profile", help="트랙 프로파일 YAML 경로")
    parser.add_argument(
        "-o", "--output-dir", default="output/scripts",
        help="저장 디렉토리 (기본: output/scripts)"
    )
    args = parser.parse_args()

    with open(args.profile, "r", encoding="utf-8") as f:
        prof = yaml.safe_load(f)

    script = generate_script(args.topic, prof)
    path = save_script(script, args.output_dir, args.topic)

    print("\n─── 대본 미리보기 (앞 600자) ───")
    print(script[:600])
    print(f"\n전체 대본: {path}")
