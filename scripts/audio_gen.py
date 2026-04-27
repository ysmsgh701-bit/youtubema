import os
import json
from gtts import gTTS

def generate_audio_from_script(script_path, output_base_dir):
    with open(script_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    audio_dir = os.path.join(output_base_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    print(f"[Audio] '{data['language']}' 음성 생성 시작...")
    
    for i, scene in enumerate(data['scenes']):
        text = scene['narration']
        # 일본어(ja) 타겟으로 음성 생성
        tts = gTTS(text=text, lang='ja')
        audio_path = os.path.join(audio_dir, f"scene_{i+1}.mp3")
        tts.save(audio_path)
        print(f" - Scene {i+1} 오디오 저장 완료: {audio_path}")
        
    return audio_dir

if __name__ == "__main__":
    # 샘플 대본 기반 실행
    script_file = "output/sample_script.json"
    output_dir = "output/20260427_1853"
    generate_audio_from_script(script_file, output_dir)
