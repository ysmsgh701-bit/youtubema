# Skill: Trend Scraper
미국 경제/건강 매체 및 트렌드 분석 스킬입니다.

## 상세 로직
1. `search_web` 또는 직접 크롤링을 통해 오늘의 주요 헤드라인을 수집합니다.
2. 수집된 데이터 중 조회수 잠재력이 높은 상위 3개 주제를 선별합니다.
3. 선별된 주제의 핵심 요약본을 Creative Scriptwriter에게 전달합니다.

---

# Skill: Gemini Scripting
Gemini 3.1 Pro를 이용한 대본 기획 및 프롬프트 생성 스킬입니다.

## 상세 로직
1. 선정된 주제를 기반으로 3~5분 분량의 유튜브 대본을 작성합니다.
2. 각 장면(Scene)별로 나레이션 텍스트와 대응하는 이미지 프롬프트를 페어로 구성합니다.
3. **Character Consistency**: 모든 프롬프트에 "Shiba Inu animation character, consistent style, vibrant colors"와 같은 키워드를 강제로 삽입합니다.

---

# Skill: Image & Thumbnail Generation
Nano Banana 2(Gemini 3 Flash Image)를 활용한 이미지 생성 스킬입니다.

## 상세 로직
1. 각 장면의 프롬프트를 API에 전송하여 16:9 이미지들을 생성합니다.
2. 썸네일 생성을 위해 라이벌 채널의 썸네일 구조를 분석하고, 스타일 트랜스퍼를 적용하여 고퀄리티 결과물을 뽑아냅니다.
3. 생성된 모든 이미지는 `assets/images/` 폴더에 타임스탬프와 함께 저장됩니다.

---

# Skill: Video Rendering & Uploading
MoviePy 및 YouTube API를 활용한 최종 공정 스킬입니다.

## 상세 로직
1. 생성된 이미지들과 음성 파일을 결합하여 동영상을 생성합니다.
2. 텍스트 데이터에 맞춰 가독성 좋은 자막(Subtitle)을 오버레이합니다.
3. 렌더링이 완료된 최종 영상(.mp4)을 YouTube Data API v3를 통해 목표 채널에 업로드 또는 예약합니다.
