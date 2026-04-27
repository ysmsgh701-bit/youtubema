"""
토픽 중복 방지 및 히스토리 관리 모듈
output/topic_history.json에 사용한 토픽을 기록하고
새 토픽 선택 시 유사 토픽이 있으면 경고합니다.
"""
import os
import json
from datetime import date

HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "output", "topic_history.json"
)


def _load():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"topics": []}


def _save(data):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _similarity(a, b):
    """간단한 단어 겹침 기반 유사도 (0~1)"""
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words or not b_words:
        return 0.0
    overlap = len(a_words & b_words)
    return overlap / max(len(a_words), len(b_words))


def check_duplicate(topic, threshold=0.5):
    """
    이미 사용한 토픽과 유사도를 검사합니다.

    Returns:
        list of (entry, similarity) tuples above threshold, sorted by similarity desc
    """
    data = _load()
    matches = []
    for entry in data["topics"]:
        sim = _similarity(topic, entry["topic"])
        if sim >= threshold:
            matches.append((entry, sim))
    return sorted(matches, key=lambda x: x[1], reverse=True)


def record_topic(topic, run_id, upload_urls=None):
    """토픽을 히스토리에 기록합니다."""
    data = _load()
    data["topics"].append({
        "topic": topic,
        "date": str(date.today()),
        "run_id": run_id,
        "uploads": upload_urls or [],
    })
    _save(data)


def update_uploads(run_id, upload_urls):
    """기존 기록에 업로드 URL을 추가합니다."""
    data = _load()
    for entry in data["topics"]:
        if entry["run_id"] == run_id:
            entry["uploads"] = list(set(entry.get("uploads", []) + upload_urls))
            break
    _save(data)


def print_history(last_n=10):
    """최근 N개 토픽 히스토리를 출력합니다."""
    data = _load()
    topics = data["topics"][-last_n:]
    if not topics:
        print("  (히스토리 없음)")
        return
    print(f"\n{'='*65}")
    print(f"  최근 업로드 토픽 히스토리 (최근 {len(topics)}개)")
    print(f"{'='*65}")
    for i, e in enumerate(reversed(topics), 1):
        uploads = ", ".join(e.get("uploads", [])) or "없음"
        print(f"  {i:2d}. [{e['date']}] {e['topic']}")
        print(f"       run: {e['run_id']}  |  URL: {uploads}")
    print(f"{'='*65}\n")
