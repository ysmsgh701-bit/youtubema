"""
대본 번역/현지화 모듈
원본 대본(JSON)을 각 언어별로 번역하고, 쇼츠용 축약 대본도 자동 생성합니다.
"""
import os
import json
import copy
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CHANNELS, CHARACTER_PROMPT


def translate_script(script_data, target_lang, api_key=None):
    """
    원본 대본을 target_lang으로 번역합니다.
    
    Args:
        script_data: 원본 대본 dict
        target_lang: 대상 언어 코드 (ko, ja, zh-TW, en)
        api_key: Gemini API 키 (없으면 간단한 복사본 생성)
    
    Returns:
        번역된 대본 dict
    """
    channel = CHANNELS.get(target_lang)
    if not channel:
        raise ValueError(f"지원하지 않는 언어: {target_lang}")

    translated = copy.deepcopy(script_data)
    translated["language"] = channel["name"]
    translated["lang_code"] = target_lang
    translated["target_market"] = channel["name"]

    # Gemini API가 있으면 실제 번역 수행
    if api_key:
        try:
            from google import genai as gai
            client = gai.Client(api_key=api_key)

            narrations = [s["narration"] for s in translated["scenes"]]
            batch_prompt = (
                f"Translate each of the following {len(narrations)} narration lines to {channel['name']}. "
                f"Keep them natural, conversational, and culturally appropriate. "
                f"Return ONLY a JSON array of translated strings in the same order, no extra text:\n"
                + json.dumps(narrations, ensure_ascii=False)
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash", contents=batch_prompt
            )
            raw = response.text.strip().replace("```json", "").replace("```", "").strip()
            translated_narrations = json.loads(raw)

            for i, scene in enumerate(translated["scenes"]):
                scene["narration"] = translated_narrations[i] if i < len(translated_narrations) else scene["narration"]
                if CHARACTER_PROMPT not in scene.get("image_prompt", ""):
                    scene["image_prompt"] = f"{CHARACTER_PROMPT}, {scene.get('image_prompt', '')}"

            # 썸네일 텍스트 번역
            if "thumbnail_plan" in translated:
                thumb_prompt = (
                    f"Translate this YouTube thumbnail text to {channel['name']}. "
                    f"Make it catchy and short (max 10 characters). "
                    f"Only return the translated text.\n\n"
                    f"Original: {translated['thumbnail_plan'].get('text_overlay', '')}"
                )
                r2 = client.models.generate_content(model="gemini-2.5-flash", contents=thumb_prompt)
                translated["thumbnail_plan"]["text_overlay"] = r2.text.strip()

            print(f"  [{target_lang}] Gemini 번역 완료")
        except Exception as e:
            print(f"  ! [{target_lang}] Gemini 번역 실패, 원본 유지: {e}")
    else:
        print(f"  [{target_lang}] API 키 미제공 — 원본 대본 복사")

    return translated


def create_shorts_script(script_data, max_scenes=2, api_key=None):
    """
    롱폼 대본에서 쇼츠용 축약 대본을 생성합니다.
    Gemini API를 사용하여 첫 장면을 강력한 3초 훅(Hook)으로 재작성합니다.
    
    Args:
        script_data: 원본 대본 dict
        max_scenes: 쇼츠에 포함할 최대 장면 수
        api_key: Gemini API 키
    
    Returns:
        쇼츠용 축약 대본 dict
    """
    shorts = copy.deepcopy(script_data)
    shorts["format"] = "shorts"
    lang_name = shorts.get("language", "Korean")

    if api_key:
        try:
            from google import genai as gai
            client = gai.Client(api_key=api_key)

            full_text = " ".join([s["narration"] for s in shorts["scenes"]])
            prompt = (
                f"Rewrite the following script into a YouTube Shorts script in {lang_name}. "
                f"TARGET: under 55 seconds total when read aloud at natural pace. "
                f"STRUCTURE: exactly 3 scenes.\n"
                f"  Scene 1 (Hook, ~5 sec): One shocking question or stat — grabs attention instantly.\n"
                f"  Scene 2 (Core, ~35 sec): The single most important insight from the original script.\n"
                f"  Scene 3 (CTA, ~10 sec): Subscribe + teaser for the full video.\n"
                f"Return ONLY a JSON array, no markdown:\n"
                f'[\n  {{"scene_no": 1, "narration": "...", "image_prompt": "...", "visual_description": "..."}},\n'
                f'  {{"scene_no": 2, "narration": "...", "image_prompt": "...", "visual_description": "..."}},\n'
                f'  {{"scene_no": 3, "narration": "...", "image_prompt": "...", "visual_description": "..."}}\n]\n\n'
                f"image_prompts MUST include: '{CHARACTER_PROMPT}'.\n"
                f"Original script:\n{full_text}"
            )
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            result_text = response.text.replace("```json", "").replace("```", "").strip()
            new_scenes = json.loads(result_text)
            shorts["scenes"] = new_scenes
            print(f"  [{shorts.get('lang_code')}] 쇼츠 대본 생성 완료 (3장면)")
            return shorts
        except Exception as e:
            print(f"  ! [{shorts.get('lang_code')}] 쇼츠 대본 API 재작성 실패, 기본 축약 사용: {e}")

    # API 오류 또는 미제공 시 기본 축약 로직
    scenes = shorts["scenes"]
    if len(scenes) > max_scenes:
        if max_scenes == 1:
            shorts["scenes"] = [scenes[0]]
        elif max_scenes == 2:
            shorts["scenes"] = [scenes[0], scenes[-1]]
        else:
            shorts["scenes"] = scenes[:max_scenes]

    print(f"  ✓ [{shorts.get('lang_code')}] 기본 쇼츠 대본 생성 ({len(shorts['scenes'])}개 장면)")
    return shorts


def generate_all_translations(source_script_path, output_dir, languages=None, api_key=None):
    """
    원본 대본을 모든 타겟 언어로 번역하고, 각각 롱폼/쇼츠 대본을 생성합니다.
    
    Args:
        source_script_path: 원본 대본 JSON 경로
        output_dir: 출력 디렉토리
        languages: 번역할 언어 리스트 (None이면 전체)
        api_key: Gemini API 키
    
    Returns:
        {lang: {"longform": path, "shorts": path}} 딕셔너리
    """
    with open(source_script_path, "r", encoding="utf-8") as f:
        source_data = json.load(f)

    if languages is None:
        languages = list(CHANNELS.keys())

    results = {}

    for lang in languages:
        print(f"\n[번역] {CHANNELS[lang]['name']} ({lang}) 처리 중...")
        lang_dir = os.path.join(output_dir, lang)
        os.makedirs(lang_dir, exist_ok=True)

        # 1) 롱폼 대본 (전체 번역)
        translated = translate_script(source_data, lang, api_key)
        translated["format"] = "longform"
        longform_path = os.path.join(lang_dir, "script_longform.json")
        with open(longform_path, "w", encoding="utf-8") as f:
            json.dump(translated, f, ensure_ascii=False, indent=2)

        # 2) 쇼츠 대본 (축약)
        shorts = create_shorts_script(translated, max_scenes=2, api_key=api_key)
        shorts_path = os.path.join(lang_dir, "script_shorts.json")
        with open(shorts_path, "w", encoding="utf-8") as f:
            json.dump(shorts, f, ensure_ascii=False, indent=2)

        results[lang] = {
            "longform": longform_path,
            "shorts": shorts_path,
        }
        print(f"  ✓ [{lang}] 대본 저장 완료: {lang_dir}")

    return results


if __name__ == "__main__":
    # 테스트 실행
    source = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "sample_script.json")
    out = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "test_translations")
    
    if os.path.exists(source):
        results = generate_all_translations(source, out, languages=["ko", "ja"])
        print("\n[결과]", json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(f"원본 대본 없음: {source}")
