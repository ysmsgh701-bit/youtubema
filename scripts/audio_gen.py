"""
다국어 음성(TTS) 생성 모듈
config.py 설정을 기반으로 언어를 동적으로 선택하여 음성을 합성합니다.
"""
import os
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CHANNELS

from gtts import gTTS


def generate_audio_from_script(script_path, output_base_dir, lang_code=None):
    """
    대본 JSON에서 각 장면(scene)의 나레이션을 음성 파일로 변환합니다.
    
    Args:
        script_path: 대본 JSON 파일 경로
        output_base_dir: 출력 기본 디렉토리
        lang_code: 언어 코드 (None이면 대본의 lang_code 필드 사용)
    
    Returns:
        생성된 오디오 파일 경로 리스트
    """
    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 언어 코드 결정 (우선순위: 인자 > 대본 > 기본값)
    if lang_code is None:
        lang_code = data.get("lang_code", "ja")

    channel = CHANNELS.get(lang_code)
    tts_lang = channel["tts_lang"] if channel else lang_code

    audio_dir = os.path.join(output_base_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    lang_name = channel["name"] if channel else lang_code
    print(f"[Audio] '{lang_name}' ({tts_lang}) 음성 생성 시작...")

    audio_paths = []
    for i, scene in enumerate(data["scenes"]):
        text = scene["narration"]
        
        try:
            tts = gTTS(text=text, lang=tts_lang)
            audio_path = os.path.join(audio_dir, f"scene_{i+1}.mp3")
            tts.save(audio_path)
            audio_paths.append(audio_path)
            print(f"  ✓ Scene {i+1} 오디오 저장: {audio_path}")
        except Exception as e:
            print(f"  ✗ Scene {i+1} 오디오 생성 실패: {e}")

    print(f"[Audio] 총 {len(audio_paths)}개 오디오 파일 생성 완료")
    return audio_paths


def generate_audio_batch(script_dir, languages=None):
    """
    여러 언어의 대본을 일괄 처리합니다.
    
    Args:
        script_dir: 언어별 대본이 있는 디렉토리 (lang/script_*.json 구조)
        languages: 처리할 언어 리스트
    
    Returns:
        {lang: {format: [audio_paths]}} 딕셔너리
    """
    if languages is None:
        languages = list(CHANNELS.keys())

    results = {}

    for lang in languages:
        lang_dir = os.path.join(script_dir, lang)
        if not os.path.exists(lang_dir):
            print(f"  ! [{lang}] 대본 디렉토리 없음, 건너뜀")
            continue

        results[lang] = {}

        for fmt in ["longform", "shorts"]:
            script_path = os.path.join(lang_dir, f"script_{fmt}.json")
            if not os.path.exists(script_path):
                continue

            output_dir = os.path.join(lang_dir, fmt)
            os.makedirs(output_dir, exist_ok=True)

            print(f"\n[Batch Audio] {lang}/{fmt} 처리 중...")
            paths = generate_audio_from_script(script_path, output_dir, lang_code=lang)
            results[lang][fmt] = paths

    return results


if __name__ == "__main__":
    # 단일 파일 테스트
    script_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "output", "sample_script.json"
    )
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "output", "test_audio"
    )

    if os.path.exists(script_file):
        generate_audio_from_script(script_file, output_dir, lang_code="ja")
    else:
        print(f"대본 파일 없음: {script_file}")
