"""
경제 뉴스 수집 모듈
Google News RSS에서 미국/유럽/일본 최신 경제 뉴스를 수집하고
터미널에서 토픽을 선택합니다.
"""
import sys
import xml.etree.ElementTree as ET

import requests

FEEDS = {
    "미국 (US)": (
        "https://news.google.com/rss/search"
        "?q=economy+stocks+finance&hl=en-US&gl=US&ceid=US:en"
    ),
    "유럽 (EU)": (
        "https://news.google.com/rss/search"
        "?q=economy+europe+finance&hl=en-GB&gl=GB&ceid=GB:en"
    ),
    "일본 (JP)": (
        "https://news.google.com/rss/search"
        "?q=economy+japan+finance&hl=ja&gl=JP&ceid=JP:ja"
    ),
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_news(region_key, n=6, timeout=10):
    """Google News RSS에서 뉴스를 가져옵니다."""
    url = FEEDS[region_key]
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")[:n]
        return [
            {
                "region": region_key,
                "title": (item.findtext("title") or "").strip(),
                "link": item.findtext("link") or "",
                "date": item.findtext("pubDate") or "",
            }
            for item in items
            if item.findtext("title")
        ]
    except Exception as e:
        print(f"  [경고] {region_key} 뉴스 수집 실패: {e}")
        return []


def fetch_all_news(per_region=5):
    """미국/유럽/일본 뉴스를 모두 수집합니다."""
    all_items = []
    for region in FEEDS:
        print(f"  {region} 뉴스 수집 중...", end=" ", flush=True)
        items = fetch_news(region, n=per_region)
        all_items.extend(items)
        print(f"{len(items)}건")
    return all_items


def select_topic_interactive(auto_pick=None):
    """
    뉴스 목록을 출력하고 사용자가 토픽을 선택합니다.

    Args:
        auto_pick: 숫자면 자동 선택 (배치 모드용), None이면 대화형

    Returns:
        선택된 토픽 문자열
    """
    print("\n[Phase 1] 최신 경제 뉴스 수집 중...")
    all_items = fetch_all_news(per_region=5)

    if not all_items:
        fallback = "글로벌 경제 최신 트렌드 2026"
        print(f"  뉴스 수집 실패 — 기본 토픽 사용: {fallback}")
        return fallback

    print(f"\n{'='*70}")
    print(f"  오늘의 경제 뉴스")
    print(f"{'='*70}")
    for i, item in enumerate(all_items, 1):
        print(f"  {i:2d}. [{item['region']}] {item['title']}")
    print(f"{'='*70}")

    # 자동 선택 모드
    if auto_pick is not None:
        idx = int(auto_pick)
        if 1 <= idx <= len(all_items):
            selected = all_items[idx - 1]["title"]
            print(f"\n  자동 선택 #{idx}: {selected}")
            return selected

    # 대화형 선택
    while True:
        try:
            choice = input(
                f"\n  번호 선택 (1~{len(all_items)}) 또는 직접 토픽 입력: "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  기본 토픽 사용")
            return "글로벌 경제 최신 트렌드 2026"

        if choice.isdigit() and 1 <= int(choice) <= len(all_items):
            selected = all_items[int(choice) - 1]["title"]
            print(f"\n  선택된 토픽: {selected}")
            return selected
        elif choice:
            print(f"\n  직접 입력된 토픽: {choice}")
            return choice
        else:
            print(f"  1~{len(all_items)} 사이 숫자 또는 텍스트를 입력하세요.")


if __name__ == "__main__":
    topic = select_topic_interactive()
    print(f"\n최종 토픽: {topic}")
