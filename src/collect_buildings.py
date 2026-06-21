"""
건축HUB API 건축물대장 수집
  - getBrTitleInfo    (표제부): 동별 주용도·면적 등
  - getBrRecapTitleInfo (총괄표제부): 집합건물 전체 요약
대상: 판교(삼평동 41135-10900) / 위례(창곡동 41131-10600, 장지동 11710-11400)
인증키: 환경변수 BLD_SERVICE_KEY (코드 미포함)
"""
import os, time, json, requests, pandas as pd

BASE_URL = "https://apis.data.go.kr/1613000/BldRgstHubService"
KEY = os.environ.get("BLD_SERVICE_KEY", "")
if not KEY:
    raise EnvironmentError(
        "BLD_SERVICE_KEY 환경변수가 설정되지 않았습니다.\n"
        "PowerShell: $env:BLD_SERVICE_KEY='인증키'\n"
        "CMD:        set BLD_SERVICE_KEY=인증키"
    )

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
OUT  = os.path.join(BASE, "data", "processed", "buildings")
os.makedirs(OUT, exist_ok=True)

# ── 대상 법정동 ───────────────────────────────────────────────────
# sigunguCd: PNU 시도(2)+시군구(3), bjdongCd: 법정동(3)+리(2)
TARGETS = [
    {"label": "판교_삼평동", "area": "pangyo",
     "sigunguCd": "41135", "bjdongCd": "10900"},
    {"label": "위례_창곡동", "area": "wirye",
     "sigunguCd": "41131", "bjdongCd": "10600"},
    {"label": "위례_장지동", "area": "wirye",
     "sigunguCd": "11710", "bjdongCd": "11400"},
]

NUM_ROWS = 100    # 공공데이터포털 API 실제 페이지 최대
SLEEP    = 0.4    # 요청 간 대기(초)


# ── 페이지 단위 요청 함수 ─────────────────────────────────────────
def fetch_page(operation: str, sigunguCd: str, bjdongCd: str,
               page: int) -> dict:
    params = {
        "serviceKey": KEY,
        "sigunguCd":  sigunguCd,
        "bjdongCd":   bjdongCd,
        "numOfRows":  NUM_ROWS,
        "pageNo":     page,
        "_type":      "json",
    }
    url = f"{BASE_URL}/{operation}"
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def safe_items(body: dict) -> list:
    """response body의 items.item 을 항상 list로 반환"""
    items = body.get("items") or {}
    item  = items.get("item") if items else None
    if item is None:
        return []
    return item if isinstance(item, list) else [item]

def fetch_all(operation: str, sigunguCd: str, bjdongCd: str,
              label: str) -> list:
    """전체 페이지 반복 수집"""
    page = 1
    all_records = []
    while True:
        try:
            data = fetch_page(operation, sigunguCd, bjdongCd, page)
        except Exception as e:
            print(f"    [WARN] {label} p{page} 오류: {e}")
            break

        body = data.get("response", {}).get("body", {})
        rc   = data.get("response", {}).get("header", {}).get("resultCode", "??")
        if rc != "00":
            msg = data.get("response", {}).get("header", {}).get("resultMsg", "")
            print(f"    [ERR] resultCode={rc}: {msg}")
            break

        total    = int(body.get("totalCount", 0))
        records  = safe_items(body)
        all_records.extend(records)

        if page == 1:
            print(f"    totalCount={total:,}, numOfRows={NUM_ROWS}")

        if len(all_records) >= total:
            break
        if len(records) == 0:
            break
        page += 1
        time.sleep(SLEEP)

    return all_records


# ── 수집 실행 ─────────────────────────────────────────────────────
summary = {}

for t in TARGETS:
    label      = t["label"]
    sigunguCd  = t["sigunguCd"]
    bjdongCd   = t["bjdongCd"]
    print(f"\n=== {label} ({sigunguCd}-{bjdongCd}) ===")

    # 표제부
    print(f"  [getBrTitleInfo]")
    title = fetch_all("getBrTitleInfo", sigunguCd, bjdongCd, label)
    print(f"    수집: {len(title):,}건")

    # 총괄표제부
    print(f"  [getBrRecapTitleInfo]")
    recap = fetch_all("getBrRecapTitleInfo", sigunguCd, bjdongCd, label)
    print(f"    수집: {len(recap):,}건")

    # 저장
    for tag, recs in [("title", title), ("recap", recap)]:
        path = os.path.join(OUT, f"{label}_{tag}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(recs, f, ensure_ascii=False)

    # 주용도 분포
    if title:
        df = pd.DataFrame(title)
        purp_col = next((c for c in df.columns if "mainPurpsCdNm" in c
                         or "mainpurpscdnm" in c.lower()), None)
        if purp_col:
            print(f"\n    주용도 분포 ({purp_col}):")
            dist = df[purp_col].fillna("미상").value_counts()
            for v, cnt in dist.items():
                print(f"      {v:<24} {cnt:5,}건")
        else:
            print(f"    컬럼 목록: {list(df.columns)[:15]}")

    # 요약
    summary[label] = {
        "sigunguCd":  sigunguCd,
        "bjdongCd":   bjdongCd,
        "title_cnt":  len(title),
        "recap_cnt":  len(recap),
    }
    time.sleep(SLEEP)

# ── 최종 요약 ─────────────────────────────────────────────────────
print("\n" + "="*50)
print("수집 완료 요약")
print("="*50)
for label, s in summary.items():
    print(f"  {label}: 표제부={s['title_cnt']:,}, 총괄표제부={s['recap_cnt']:,}")

# 요약 저장
with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(f"\n저장 위치: data/processed/buildings/")
