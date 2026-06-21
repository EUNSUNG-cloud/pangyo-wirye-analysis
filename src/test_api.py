"""
건축HUB API 연결 테스트 — 판교 삼평동 표제부 1건만 조회
"""
import os, requests, json

KEY = os.environ.get("BLD_SERVICE_KEY", "")
if not KEY:
    raise EnvironmentError("BLD_SERVICE_KEY 환경변수 미설정")

url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
params = {
    "serviceKey": KEY,
    "sigunguCd":  "41135",   # 분당구
    "bjdongCd":   "10900",   # 삼평동
    "numOfRows":  3,
    "pageNo":     1,
    "_type":      "json",
}

r = requests.get(url, params=params, timeout=15)
print(f"HTTP {r.status_code}")
try:
    data = r.json()
    header = data["response"]["header"]
    print(f"resultCode: {header['resultCode']}")
    print(f"resultMsg:  {header['resultMsg']}")
    body = data["response"]["body"]
    print(f"totalCount: {body.get('totalCount')}")
    items = body.get("items", {})
    item  = items.get("item") if items else None
    if item:
        first = item[0] if isinstance(item, list) else item
        print("\n첫 번째 건 컬럼:")
        for k, v in first.items():
            print(f"  {k}: {v}")
    else:
        print("items 없음 (데이터 0건 또는 bjdongCd 불일치)")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:800])
except Exception as e:
    print(f"파싱 오류: {e}")
    print(r.text[:500])
