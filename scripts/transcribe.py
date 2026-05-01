"""
Whisper 자막 생성 모듈
faster-whisper로 영상/음성 파일에서 SRT 자막을 생성합니다.

독립 실행:
    python scripts/transcribe.py recording.mp4
    python scripts/transcribe.py recording.mp4 -o output/subtitles.srt -l ko
"""
import os
import argparse


def transcribe_to_srt(
    video_path: str,
    output_path: str = None,
    language: str = "ko",
    model_size: str = "large-v3",
) -> str:
    """
    영상 파일에서 SRT 자막 파일을 생성합니다.

    Args:
        video_path: 영상/음성 파일 경로
        output_path: 출력 SRT 경로 (None이면 video_path와 같은 위치에 자동 생성)
        language: 언어 코드 (ko, en, ja ...)
        model_size: Whisper 모델 크기 (large-v3 권장, 빠른 테스트는 small)

    Returns:
        생성된 SRT 파일 경로
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "faster-whisper가 설치되지 않았습니다.\n"
            "  pip install faster-whisper"
        )

    if not output_path:
        base = os.path.splitext(video_path)[0]
        output_path = f"{base}.srt"

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    print(f"[Transcribe] 모델 로드 중: {model_size} (첫 실행 시 다운로드 ~3GB)")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"[Transcribe] 자막 생성 중: {os.path.basename(video_path)}")
    segments, info = model.transcribe(video_path, language=language, beam_size=5)

    print(
        f"[Transcribe] 감지 언어: {info.language} "
        f"(신뢰도: {info.language_probability:.1%})"
    )

    srt_lines = []
    count = 0
    for seg in segments:
        count += 1
        start = _fmt_time(seg.start)
        end = _fmt_time(seg.end)
        text = seg.text.strip()
        srt_lines.append(f"{count}\n{start} --> {end}\n{text}\n")

    srt_content = "\n".join(srt_lines)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    print(f"[Transcribe] 완료: {count}개 세그먼트 → {output_path}")
    return output_path


def srt_to_text(srt_path: str) -> str:
    """SRT 파일에서 타임스탬프·인덱스를 제거하고 순수 텍스트만 반환합니다."""
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = []
    for block in content.strip().split("\n\n"):
        parts = block.strip().split("\n")
        if len(parts) >= 3:
            lines.extend(parts[2:])

    return " ".join(lines)


def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Whisper 자막 생성")
    parser.add_argument("video", help="영상/음성 파일 경로")
    parser.add_argument("-o", "--output", default=None, help="출력 SRT 파일 경로")
    parser.add_argument("-l", "--language", default="ko", help="언어 코드 (기본: ko)")
    parser.add_argument(
        "-m", "--model", default="large-v3",
        help="Whisper 모델 크기 (large-v3 권장, 빠른 테스트: small)"
    )
    args = parser.parse_args()

    transcribe_to_srt(args.video, args.output, args.language, args.model)
