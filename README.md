# 판교테크노밸리 vs 위례신도시 업무지구 비교 분석 시스템

> **연구 질문**: 왜 판교테크노밸리(제1판교)는 업무지구로 성공했고,  
> 위례신도시 업무·상업용지는 자족 업무지구로 실패했는가?

가천대학교 스마트시티 기말 프로젝트 (2026)  
공공데이터 기반 토지이용·교통망·인구사회 정량 비교 → GitHub Pages 정적 웹 시스템

**라이브 데모**: `docs/` 폴더를 GitHub Pages 루트로 설정하면 즉시 배포됩니다.  
로컬 실행: `python -m http.server 8080 --directory docs` → http://localhost:8080

---

## 시스템 구성 (4개 필수 기능)

| 기능 | 설명 |
|------|------|
| **비교 지도** | 판교TV·위례 구역계 오버레이, 필지 주용도별 색상, 구역 토글 |
| **등시간권 레이어** | 판교역·남위례역 기준 30분/60분 폴리곤, 도달 인구·종사자 팝업 |
| **통계 패널** | 토지이용·교통·인구사회 3탭 비교표 + 파이/선/막대 차트 |
| **필지 클릭 팝업** | 주용도·연면적·용적률 속성 표시 (76% PNU 매칭 기준) |

---

## 데이터 출처 및 기준월

### 공간 경계

| 데이터 | 출처 | 기준 | 좌표계 |
|--------|------|------|--------|
| 집계구 경계 (서울·경기) | SGIS `bnd_oa_11/31_2025_2Q.zip` | **2025년 2분기** | EPSG:5179 |
| 행정경계 (시도·시군구·동) | SGIS `bnd_all_00_2025_2Q.zip` | **2025년 2분기** | EPSG:5179 |
| 연속지적도 분당구 | 국토정보플랫폼 `LSMD_CONT_LDREG_41135_202606.shp` | **2026년 6월** | EPSG:5186 |
| 연속지적도 수정구 | 국토정보플랫폼 `LSMD_CONT_LDREG_41131_202606.shp` | **2026년 6월** | EPSG:5186 |
| 연속지적도 송파구 | 국토정보플랫폼 `LSMD_CONT_LDREG_11710_202606.shp` | **2026년 6월** | EPSG:5186 |

### 통계 데이터

| 데이터 | 출처 | 기준 | 비고 |
|--------|------|------|------|
| 집계구 총인구·성연령 | SGIS 소지역통계 | **2024년** | `to_in_001` (총인구) |
| 집계구 사업체·종사자 | SGIS 소지역통계 | **2023년** | `to_fa_010`, `to_em_020` |
| 건축물대장 표제부 | 공공데이터포털 건축HUB API | **2026년 6월 수집** | `getBrTitleInfo` |
| 건축물대장 총괄표제부 | 공공데이터포털 건축HUB API | **2026년 6월 수집** | `getBrRecapTitleInfo` |

### 교통 네트워크

| 데이터 | 출처 | 기준 | 비고 |
|--------|------|------|------|
| 수도권 지하철 네트워크 | 제공 데이터 `subway_network.zip` | **2026-05-05 export** | nodes 817개, links 999개 (유효 네트워크) |
| 도보 경로 | OSM `export.geojson` | — | ⚠️ 로마 좌표로 판명, 미사용 → 직선거리 × 1.2 대체 |

---

## 구역계 정의

### 판교TV (삼평동)
- **법정동**: 성남시 분당구 삼평동 (PNU 앞 10자리 `4113510900`)
- **LSMD 필지**: 421개 (platGbCd=1 임야번지 → PNU 매칭률 76%)
- **구역 면적**: 214.0 ha | **중심**: 37.402N, 127.106E

### 위례 업무지구 (창곡동)
- **법정동**: 성남시 수정구 창곡동 (`4113110600`) + 서울 송파구 장지동 (`1171011400`)
- **지리 필터**: 위도 37.455–37.485N, 경도 127.130–127.175E (거여동 북측·천마산 클러스터 제외)
- **구역 면적**: 55.9 ha | **중심**: 37.462N, 127.165E

> **PNU 매칭 한계**: 연속지적도(LSMD)는 개발 전 임야번지를 유지하고, 건축물대장은 분필 후 대지번지를 사용하여 동일 필지라도 PNU가 불일치할 수 있습니다. 실질 매칭률 76% 기준으로 분석하였으며, 공지율은 건물수/필지수 비율로 보정하였습니다.

---

## 핵심 분석 수치

| 지표 | 판교TV | 위례 업무지구 |
|------|--------|-------------|
| 구역 면적 | 214.0 ha | 55.9 ha |
| 평균 용적률 | **151 %** | 29 % |
| 공지율 (보정) | **~0 %** | 31 % |
| 업무시설 연면적 | **1,990,847 m²** | 2,066 m² |
| 업무+연구 연면적 | **2,906,617 m²** | 106,929 m² |
| LUM 엔트로피 | 0.39 (업무 집중) | 0.83 (혼합) |
| 구역내 종사자 | **93,188 명** | 1,414 명 |
| 구역내 상주인구 | 5,378 명 | 3,768 명 |
| **직주비** | **17.33** | **0.38** |
| 도보보정 30분 종사자 (2016) | 455,027 명 | 107,795 명 |
| 도보보정 30분 종사자 (2026) | 529,572 명 | 168,012 명 |

---

## 분석 파이프라인

```
data/raw/                          ← 원본 데이터 (비공개, .gitignore)
│
├── 1. src/build_oa.py             집계구 경계 + 인구·종사자 조인
│       → data/processed/oa_joined.gpkg
│
├── 2. src/collect_buildings.py    건축HUB API 수집 (BLD_SERVICE_KEY 환경변수)
│       → data/processed/buildings/*.json
│
├── 3. src/step_boundary.py        구역계 정의 (PNU 조인 + 지리 필터)
│       → docs/data/pangyo.geojson, wirye.geojson
│       → docs/data/pangyo_parcels.geojson, wirye_parcels.geojson
│
├── 4. src/step45_isochrone.py     Dijkstra 등시간권 (scipy)
│       → docs/data/isochrones.geojson
│       → docs/data/accessibility_30_60.json
│       → docs/data/accessibility_curve.json
│
├── 5. src/step_temporal.py        2016/2026 시점 비교
│       → docs/data/temporal_comparison.json
│
├── 6. src/step_walk_corrected.py  도보 보정 등시간권
│       → docs/data/walk_corrected.json
│
├── 7. src/step_landuse.py         토지이용·직주비
│       → docs/data/landuse_metrics.json
│
└── 8. src/export_parcels.py       필지 GeoJSON (4326, 웹용)
        → docs/data/pangyo_parcels.geojson (198KB)
        → docs/data/wirye_parcels.geojson  (179KB)
```

### 좌표계 처리
- **분석**: 모든 공간 연산 EPSG:5179 (Korea 2000 Unified)
- **웹 표출**: EPSG:4326으로 변환하여 `docs/data/`에 저장
- **연속지적도**: 원본 EPSG:5186 → 분석 전 EPSG:5179 재투영

---

## 파일 구조

```
docs/                    ← GitHub Pages 루트
├── index.html           ← 메인 시스템 (Leaflet + Chart.js)
├── boundary_check.html  ← 구역계 확인 페이지
└── data/
    ├── pangyo.geojson          판교TV 구역계 폴리곤
    ├── wirye.geojson           위례 업무지구 구역계
    ├── pangyo_parcels.geojson  판교TV 필지 + 속성 (198KB)
    ├── wirye_parcels.geojson   위례 필지 + 속성  (179KB)
    ├── isochrones.geojson      30/60분 등시간권 4개 (2026 기준)
    ├── accessibility_30_60.json 역기준 도달 인구·종사자
    ├── accessibility_curve.json 5분 간격 누적 접근성 곡선
    ├── temporal_comparison.json 2016/2026 시점 비교
    ├── walk_corrected.json     도보 보정 분석 결과
    ├── landuse_metrics.json    토지이용·직주비 지표
    ├── buildings_summary.json  건축물 주용도 분포
    └── zone_summary.json       구역계 요약

src/                     ← 전처리 Python 스크립트
├── build_oa.py          집계구 조인
├── collect_buildings.py 건축HUB API 수집
├── step_boundary.py     구역계 정의 (v5)
├── step45_isochrone.py  Dijkstra 등시간권
├── step_temporal.py     시점 비교
├── step_walk_corrected.py 도보 보정
├── step_landuse.py      토지이용 지표
└── export_parcels.py    필지 GeoJSON 내보내기

data/                    ← .gitignore 제외 (대용량)
├── raw/                 원본 zip·shp·csv
└── processed/           중간 결과 gpkg·pkl
```

---

## 실행 환경

```bash
pip install geopandas shapely scipy pyproj pandas numpy requests
python -m http.server 8080 --directory docs
```

건축HUB API 키:
```bash
# Windows PowerShell
$env:BLD_SERVICE_KEY = "발급받은_인증키"
python src/collect_buildings.py
```

---

## 주요 한계 및 주의사항

1. **LSMD–건축물대장 PNU 불일치**: 임야번지(platGbCd=1) ↔ 대지번지(platGbCd=0) 이중 체계로 인해 매칭률 76% 수준. 공지율은 건물수/필지수 비율로 보정.
2. **위례 구역 한정**: 위도 37.455–37.485N 기준으로 창곡동(성남) 중심. 장지동(서울) 위례 구간의 상당 부분이 37.485N 이북에 위치해 본 분석에서 제외.
3. **OSM 도보망 미사용**: `export.geojson`이 로마 좌표(lon~12.5E)로 판명, 도보 거리는 직선 × 1.2 우회계수 적용.
4. **등시간권**: 역 기준 Dijkstra (timeFT/timeTF에 환승 대기 포함). 역까지 도보시간을 별도 공제한 도보보정 결과도 제공.
5. **집계구 통계**: 인구 2024년, 사업체·종사자 2023년으로 연도 차이 있음. 집계구 경계는 2025년 2분기 기준.
