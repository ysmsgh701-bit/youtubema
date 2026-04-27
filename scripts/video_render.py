import os
import json
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip

def render_video(script_path, assets_dir, output_path):
    with open(script_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    clips = []
    
    print("[Render] 영상 합성 시작...")
    
    for i, scene in enumerate(data['scenes']):
        img_path = os.path.join(assets_dir, "images", f"scene_{i+1}.png")
        audio_path = os.path.join(assets_dir, "audio", f"scene_{i+1}.mp3")
        
        if not os.path.exists(img_path) or not os.path.exists(audio_path):
            print(f" ! Warning: Scene {i+1} 자산 누락 (Skip)")
            continue
            
        # 오디오 클립 생성
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        # 이미지 클립 생성 (오디오 길이에 맞춤)
        img_clip = ImageClip(img_path).with_duration(duration)
        
        # 자막 추가 (간이 자막)
        try:
            # v2 스펙에 맞춘 텍스트 클립 (font 인자 필수)
            txt_clip = TextClip(text=scene['narration'], font="Arial", font_size=40, color='white', 
                               stroke_color='black', stroke_width=2,
                               method='caption', size=(img_clip.w*0.8, None)).with_duration(duration)
            txt_clip = txt_clip.with_position(('center', img_clip.h*0.8))
            video_scene = CompositeVideoClip([img_clip, txt_clip])
        except Exception as e:
            print(f" ! 자막 생성 오류 (ImageMagick 미설치 등): {e}")
            video_scene = img_clip
            
        video_scene = video_scene.with_audio(audio_clip)
        clips.append(video_scene)
    
    if clips:
        final_video = concatenate_videoclips(clips, method="compose")
        final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
        print(f"\n[성공] 최종 영상 생성 완료: {output_path}")
    else:
        print("[오류] 합성할 클립이 없습니다.")

if __name__ == "__main__":
    script_file = "output/sample_script.json"
    assets_folder = "output/20260427_1853"
    final_output = os.path.join(assets_folder, "final_video_prototype.mp4")
    
    render_video(script_file, assets_folder, final_output)
