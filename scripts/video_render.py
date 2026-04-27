"""
영상 렌더링 모듈 v2
쇼츠(세로 9:16) / 롱폼(가로 16:9) 이중 포맷 렌더링을 지원합니다.
Ken Burns 효과, 크로스페이드 트랜지션, BGM 합성 기능을 포함합니다.
"""
import os
import json
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import VIDEO_FORMATS, TRANSITION_DURATION, KEN_BURNS_ZOOM, BGM_VOLUME, BGM_DIR

from moviepy import (
    ImageClip, AudioFileClip, concatenate_videoclips,
    TextClip, CompositeVideoClip, CompositeAudioClip,
    vfx
)


def resize_image_for_format(img_clip, video_format):
    """
    이미지를 영상 포맷에 맞게 리사이즈합니다.
    - 쇼츠: 세로 1080x1920 (center crop)
    - 롱폼: 가로 1920x1080 (fit)
    """
    fmt = VIDEO_FORMATS[video_format]
    target_w, target_h = fmt["width"], fmt["height"]
    
    # 이미지를 타겟 크기에 맞게 resize (비율 유지, 빈 공간 없이)
    img_w, img_h = img_clip.size
    scale_w = target_w / img_w
    scale_h = target_h / img_h
    scale = max(scale_w, scale_h)  # 빈 공간 없이 채우기
    
    resized = img_clip.resized((int(img_w * scale), int(img_h * scale)))
    
    # 중앙 크롭
    rw, rh = resized.size
    x_center = rw / 2
    y_center = rh / 2
    x1 = int(x_center - target_w / 2)
    y1 = int(y_center - target_h / 2)
    
    cropped = resized.cropped(x1=x1, y1=y1, width=target_w, height=target_h)
    return cropped


def apply_ken_burns(clip, zoom_factor=None, direction="in"):
    """
    정적 이미지에 Ken Burns (줌인/줌아웃) 효과를 적용합니다.
    
    Args:
        clip: ImageClip
        zoom_factor: 줌 배율 (None이면 config 기본값)
        direction: "in" (줌인) 또는 "out" (줌아웃)
    """
    if zoom_factor is None:
        zoom_factor = KEN_BURNS_ZOOM
    
    if zoom_factor <= 1.0:
        return clip  # 줌 없음
    
    duration = clip.duration
    w, h = clip.size
    
    def make_frame_func(get_frame):
        def new_get_frame(t):
            if direction == "in":
                progress = t / duration
            else:
                progress = 1 - (t / duration)
            
            current_zoom = 1.0 + (zoom_factor - 1.0) * progress
            frame = get_frame(t)
            
            # PIL을 사용한 줌 효과 (moviepy 내부에서 처리)
            return frame
        return new_get_frame
    
    # 간단한 줌 — resize + crop 방식
    # 시작 크기를 zoom_factor만큼 키운 후, 점진적으로 crop 영역 이동
    enlarged = clip.resized(zoom_factor)
    ew, eh = enlarged.size
    
    def position_func(t):
        if direction == "in":
            progress = t / duration if duration > 0 else 0
        else:
            progress = 1 - (t / duration) if duration > 0 else 0
        
        offset_x = (ew - w) * progress / 2
        offset_y = (eh - h) * progress / 2
        return (-offset_x, -offset_y)
    
    # CompositeVideoClip으로 줌 효과 구현
    moving = enlarged.with_position(position_func)
    result = CompositeVideoClip([moving], size=(w, h)).with_duration(duration)
    
    return result


def create_subtitle_clip(text, duration, video_format, font_name="Arial"):
    """
    포맷에 맞는 자막 클립을 생성합니다.
    """
    fmt = VIDEO_FORMATS[video_format]
    target_w = fmt["width"]
    font_size = fmt["subtitle_font_size"]
    y_ratio = fmt["subtitle_y_ratio"]
    
    # Windows 환경 폰트 폴백 설정
    font_path = font_name
    if os.name == 'nt':
        # 흔히 쓰이는 폰트 파일 매핑
        font_map = {
            "NanumGothic": "C:/Windows/Fonts/malgun.ttf", # 나눔고딕이 없을 경우 맑은 고딕
            "NotoSansJP": "C:/Windows/Fonts/msgothic.ttc",
            "NotoSansTC": "C:/Windows/Fonts/msjh.ttc",
            "Arial": "C:/Windows/Fonts/arial.ttf"
        }
        font_path = font_map.get(font_name, "C:/Windows/Fonts/arial.ttf")

    try:
        txt_clip = TextClip(
            text=text,
            font=font_path,
            font_size=font_size,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(int(target_w * 0.85), None),
        ).with_duration(duration)
        
        txt_clip = txt_clip.with_position(("center", y_ratio))
        return txt_clip
    except Exception as e:
        print(f"  ! 자막 생성 오류: {e}")
        return None


def render_video(script_path, assets_dir, output_path, video_format="longform", bgm_path=None):
    """
    대본 + 에셋을 조합하여 영상을 렌더링합니다.
    
    Args:
        script_path: 대본 JSON 경로
        assets_dir: 이미지/오디오 에셋 디렉토리
        output_path: 출력 MP4 경로
        video_format: "shorts" 또는 "longform"
        bgm_path: 배경음악 파일 경로 (선택)
    """
    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    fmt = VIDEO_FORMATS[video_format]
    lang = data.get("language", "Unknown")
    lang_code = data.get("lang_code", "en")

    print(f"\n{'='*60}")
    print(f"[Render] {lang} / {video_format} ({fmt['aspect_ratio']}) 렌더링 시작")
    print(f"  해상도: {fmt['width']}x{fmt['height']} @ {fmt['fps']}fps")
    print(f"{'='*60}")

    clips = []
    total_duration = 0.0

    for i, scene in enumerate(data["scenes"]):
        img_path = os.path.join(assets_dir, "images", f"scene_{i+1}.png")
        audio_path = os.path.join(assets_dir, "audio", f"scene_{i+1}.mp3")

        if not os.path.exists(img_path) or not os.path.exists(audio_path):
            print(f"  ! Scene {i+1} 자산 누락 (Skip)")
            continue

        # 오디오
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration

        # 쇼츠 길이 제한 체크
        if fmt["max_duration"] and (total_duration + duration) > fmt["max_duration"]:
            remaining = fmt["max_duration"] - total_duration
            if remaining <= 1:
                print(f"  ! 쇼츠 시간 초과 — Scene {i+1} 이후 생략")
                break
            audio_clip = audio_clip.subclipped(0, remaining)
            duration = remaining
            print(f"  ⚠ Scene {i+1} 잘림: {duration:.2f}초 (쇼츠 제한)")

        total_duration += duration
        print(f"  ▸ Scene {i+1} | 언어: {lang} | 길이: {duration:.2f}초")

        # 이미지 → 포맷 맞춤 리사이즈
        img_clip = ImageClip(img_path).with_duration(duration)
        img_clip = resize_image_for_format(img_clip, video_format)

        # Ken Burns 효과 (짝수: 줌인, 홀수: 줌아웃)
        direction = "in" if i % 2 == 0 else "out"
        img_clip = apply_ken_burns(img_clip, direction=direction)

        # 자막
        subtitle = create_subtitle_clip(
            scene["narration"], duration, video_format
        )

        if subtitle:
            video_scene = CompositeVideoClip(
                [img_clip, subtitle],
                size=(fmt["width"], fmt["height"])
            )
        else:
            video_scene = img_clip

        video_scene = video_scene.with_duration(duration).with_audio(audio_clip)
        clips.append(video_scene)

    if not clips:
        print("[오류] 합성할 클립이 없습니다.")
        return None

    # 장면 연결 (크로스페이드 트랜지션)
    print(f"\n[Info] 장면 연결 중 (트랜지션: {TRANSITION_DURATION}초 크로스페이드)...")
    
    if len(clips) > 1 and TRANSITION_DURATION > 0:
        # 크로스페이드를 위해 padding 추가
        transition_clips = [clips[0]]
        for clip in clips[1:]:
            transition_clips.append(
                clip.with_effects([vfx.CrossFadeIn(TRANSITION_DURATION)])
            )
        final_video = concatenate_videoclips(transition_clips, method="compose", padding=-TRANSITION_DURATION)
    else:
        final_video = concatenate_videoclips(clips, method="compose")

    # BGM 합성 (있으면)
    if bgm_path and os.path.exists(bgm_path):
        print(f"  ♬ BGM 합성: {bgm_path}")
        bgm = AudioFileClip(bgm_path)
        
        # BGM을 영상 길이에 맞게 루프
        if bgm.duration < final_video.duration:
            loops = math.ceil(final_video.duration / bgm.duration)
            bgm_clips = [bgm] * loops
            bgm = concatenate_videoclips(bgm_clips)  # audio concat
        
        bgm = bgm.subclipped(0, final_video.duration)
        bgm = bgm.with_volume_scaled(BGM_VOLUME)
        
        mixed_audio = CompositeAudioClip([final_video.audio, bgm])
        final_video = final_video.with_audio(mixed_audio)

    # 출력
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    actual_duration = final_video.duration
    print(f"\n[Info] 최종 영상 길이: {actual_duration:.2f}초")
    print(f"[Info] 렌더링 시작 → {output_path}")

    final_video.write_videofile(
        output_path,
        fps=fmt["fps"],
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
    )

    print(f"\n[✓ 완료] {video_format} 영상 생성: {output_path}")
    print(f"  해상도: {fmt['width']}x{fmt['height']} | 길이: {actual_duration:.2f}초")
    
    return {
        "path": output_path,
        "format": video_format,
        "duration": actual_duration,
        "resolution": f"{fmt['width']}x{fmt['height']}",
        "language": lang,
    }


def render_dual_format(script_dir, lang, assets_base_dir, output_base_dir, bgm_path=None):
    """
    하나의 언어에 대해 쇼츠 + 롱폼 두 가지 포맷을 렌더링합니다.
    
    Args:
        script_dir: 대본 디렉토리 (lang/script_*.json)
        lang: 언어 코드
        assets_base_dir: 에셋 기본 디렉토리
        output_base_dir: 출력 기본 디렉토리
        bgm_path: BGM 경로
    
    Returns:
        {"shorts": result, "longform": result}
    """
    results = {}
    lang_dir = os.path.join(script_dir, lang)

    for fmt in ["longform", "shorts"]:
        script_path = os.path.join(lang_dir, f"script_{fmt}.json")
        if not os.path.exists(script_path):
            print(f"  ! [{lang}/{fmt}] 대본 없음, 건너뜀")
            continue

        assets_dir = os.path.join(lang_dir, fmt)
        output_path = os.path.join(output_base_dir, lang, fmt, f"final_{fmt}.mp4")

        result = render_video(script_path, assets_dir, output_path, video_format=fmt, bgm_path=bgm_path)
        if result:
            results[fmt] = result

    return results


if __name__ == "__main__":
    # 기존 호환 — 단일 파일 렌더링 테스트
    script_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "output", "sample_script.json"
    )
    assets_folder = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "output", "20260427_1853"
    )

    if os.path.exists(script_file):
        # 롱폼 테스트
        render_video(
            script_file, assets_folder,
            os.path.join(assets_folder, "final_longform.mp4"),
            video_format="longform"
        )
        # 쇼츠 테스트
        render_video(
            script_file, assets_folder,
            os.path.join(assets_folder, "final_shorts.mp4"),
            video_format="shorts"
        )
    else:
        print(f"대본 파일 없음: {script_file}")
