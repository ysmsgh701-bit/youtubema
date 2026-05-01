"""
폴더 감시 → 파이프라인 자동 트리거
inbox/{track}/ 폴더에 영상 파일을 드롭하면 자동으로 pipeline.py를 실행합니다.

폴더 구조:
    inbox/
        finance/   ← 재무 트랙 영상 드롭
        tft/       ← TFT 트랙 영상 드롭

사용법:
    python watch_folder.py              # 일반 실행 (업로드 포함)
    python watch_folder.py --dry-run    # 업로드 없이 처리만
    python watch_folder.py --model small  # 빠른 테스트용 Whisper 모델
"""
import os
import sys
import time
import argparse
import threading
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("[오류] watchdog이 설치되지 않았습니다.")
    print("  pip install watchdog")
    sys.exit(1)

from pipeline import run_pipeline

_ROOT = os.path.dirname(os.path.abspath(__file__))
INBOX_DIR = os.path.join(_ROOT, "inbox")
TRACKS = ["finance", "tft"]
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


class VideoDropHandler(FileSystemEventHandler):
    def __init__(self, dry_run: bool = False, whisper_model: str = "large-v3"):
        self.dry_run = dry_run
        self.whisper_model = whisper_model
        self._processing: set = set()
        self._lock = threading.Lock()

    def on_created(self, event):
        if event.is_directory:
            return

        path = event.src_path
        if Path(path).suffix.lower() not in VIDEO_EXTENSIONS:
            return

        track = self._detect_track(path)
        if not track:
            print(f"[Watch] 트랙 미인식 파일 무시: {os.path.basename(path)}")
            return

        with self._lock:
            if path in self._processing:
                return
            self._processing.add(path)

        # 별도 스레드에서 파이프라인 실행 (감시 루프 블록 방지)
        thread = threading.Thread(
            target=self._process,
            args=(path, track),
            daemon=True,
        )
        thread.start()

    def _process(self, path: str, track: str):
        try:
            print(f"\n[Watch] 새 영상 감지: {os.path.basename(path)} → 트랙: {track}")
            self._wait_for_file(path)
            run_pipeline(
                path, track,
                dry_run=self.dry_run,
                whisper_model=self.whisper_model,
            )
        except Exception as e:
            print(f"[Watch] 파이프라인 오류: {e}")
        finally:
            with self._lock:
                self._processing.discard(path)

    def _detect_track(self, file_path: str):
        """파일 경로에서 트랙 이름을 추출합니다 (inbox/{track}/ 기준)."""
        parts = Path(file_path).parts
        for part in parts:
            if part.lower() in TRACKS:
                return part.lower()
        return None

    def _wait_for_file(self, path: str, timeout: int = 60):
        """파일 복사가 완료될 때까지 크기 안정을 기다립니다."""
        prev_size = -1
        waited = 0
        while waited < timeout:
            try:
                size = os.path.getsize(path)
                if size == prev_size and size > 0:
                    return
                prev_size = size
            except OSError:
                pass
            time.sleep(2)
            waited += 2
        print(f"[Watch] 파일 안정화 대기 타임아웃: {os.path.basename(path)}")


def main():
    parser = argparse.ArgumentParser(description="영상 드롭 폴더 감시 → 자동 파이프라인")
    parser.add_argument("--dry-run", action="store_true", help="업로드 없이 처리만")
    parser.add_argument(
        "--model", default="large-v3",
        help="Whisper 모델 크기 (기본: large-v3, 빠른 테스트: small)"
    )
    args = parser.parse_args()

    # inbox 폴더 자동 생성
    for track in TRACKS:
        os.makedirs(os.path.join(INBOX_DIR, track), exist_ok=True)

    print("[Watch] 폴더 감시 시작")
    print(f"  inbox 경로: {INBOX_DIR}")
    for track in TRACKS:
        print(f"    inbox/{track}/  ← {track} 트랙 영상 드롭")
    print(f"  Whisper 모델: {args.model}")
    print(f"  Dry Run: {args.dry_run}")
    print("  Ctrl+C로 종료\n")

    handler = VideoDropHandler(dry_run=args.dry_run, whisper_model=args.model)
    observer = Observer()
    observer.schedule(handler, INBOX_DIR, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Watch] 종료 중...")
        observer.stop()

    observer.join()
    print("[Watch] 종료 완료")


if __name__ == "__main__":
    main()
