"""
메타데이터 생성 모듈
Gemini API로 YouTube 제목 후보 3개 / 설명 / 태그를 생성합니다.

독립 실행:
    python scripts/generate_meta.py subtitles.srt config/finance_profile.yaml
"""
import os
import json
import argparse

import yaml


def generate_meta(srt_text: str, profile: dict, api_key: str = None) -> dict:
    """
    자막 텍스트와 트랙 프로파일을 기반으로 YouTube 메타데이터를 생성합니다.

    Args:
        srt_text: SRT에서 추출한 순수 텍스트
        profile: 트랙 프로파일 dict (config/*.yaml 로드 결과)
        api_key: Gemini API 키 (None이면 환경변수 GEMINI_API_KEY 사용)

    Returns:
        {"titles": [...3개...], "description": "...", "tags": [...]}
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[Meta] GEMINI_API_KEY 없음 - 기본 메타데이터 사용")
        return _fallback_meta(profile)

    try:
        from google import genai as gai
        client = gai.Client(api_key=api_key)
    except ImportError:
        print("[Meta] google-genai 미설치 - 기본 메타데이터 사용")
        return _fallback_meta(profile)

    track_name = profile.get("name", "")
    meta_prompt = profile.get("meta_prompt", "")
    tags_base = profile.get("tags_base", [])

    prompt = f"""당신은 YouTube SEO 전문가입니다.
채널: {track_name}
{meta_prompt}

아래 영상 자막을 읽고 최적화된 YouTube 메타데이터를 생성하세요.

자막 내용:
{srt_text[:3000]}

요구사항:
- titles: 클릭율 높은 제목 후보 3개 (각 40자 이내, 한국어)
- description: 영상 설명 (300자 내외, 핵심 내용 + 관련 해시태그 3~5개 포함)
- tags: 관련 태그 15개 (한국어/영어 혼합)

반드시 유효한 JSON만 반환하세요 (마크다운 코드블록 없이):
{{
  "titles": ["제목1", "제목2", "제목3"],
  "description": "설명...",
  "tags": ["태그1", "태그2"]
}}"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        raw = response.text.strip()

        if "```" in raw:
            for part in raw.split("```"):
                p = part.strip().lstrip("json").strip()
                if p.startswith("{"):
                    raw = p
                    break

        meta = json.loads(raw)
        meta["tags"] = list(set(meta.get("tags", []) + tags_base))
        return meta

    except Exception as e:
        print(f"[Meta] Gemini 호출 실패 - 기본 메타데이터 사용")
        return _fallback_meta(profile)


def _fallback_meta(profile: dict) -> dict:
    name = profile.get("name", "영상")
    return {
        "titles": [f"[{name}] 영상"],
        "description": f"{name} 채널 영상입니다.",
        "tags": profile.get("tags_base", []),
    }


def load_profile(profile_path: str) -> dict:
    with open(profile_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube 메타데이터 생성")
    parser.add_argument("srt", help="SRT 파일 경로")
    parser.add_argument("profile", help="트랙 프로파일 YAML 경로")
    parser.add_argument("-o", "--output", default=None, help="출력 JSON 파일 경로")
    args = parser.parse_args()

    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.transcribe import srt_to_text

    text = srt_to_text(args.srt)
    profile = load_profile(args.profile)

    print("[Meta] 메타데이터 생성 중...")
    meta = generate_meta(text, profile)

    output_path = args.output or os.path.splitext(args.srt)[0] + "_meta.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[Meta] 완료: {output_path}")
    print(f"  제목 후보:")
    for i, t in enumerate(meta.get("titles", []), 1):
        print(f"    {i}. {t}")
