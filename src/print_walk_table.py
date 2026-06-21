import json, os

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
with open(os.path.join(BASE, "docs", "data", "walk_corrected.json"), encoding="utf-8") as f:
    d = json.load(f)

rows = d["walk_correction_table"]

# ── 도보보정 절대값 표 ─────────────────────────────────────────
print("=" * 72)
print("도보 보정 도달 인구·종사자 (업무지구 중심 출발 기준)")
print(f"  도보속도 4.5 km/h, 우회계수 1.2 적용 / 단위: 명")
print("=" * 72)
hdr = f"{'시점':^12}{'지역':^8}{'예산':^6}{'도보(분)':^10}{'잔여(분)':^10}{'도달 인구':^14}{'도달 종사자':^14}"
print(hdr)
print("-" * 72)

order = [
    ("2016-01-01", "pangyo", 30),
    ("2016-01-01", "wirye",  30),
    ("2016-01-01", "pangyo", 60),
    ("2016-01-01", "wirye",  60),
    ("2026-06-21", "pangyo", 30),
    ("2026-06-21", "wirye",  30),
    ("2026-06-21", "pangyo", 60),
    ("2026-06-21", "wirye",  60),
]
idx = {(r["cutoff"], r["area"], r["budget_min"]): r for r in rows}

for key in order:
    r = idx[key]
    area_kr = "판교TV" if r["area"] == "pangyo" else "위례"
    print(
        f"  {r['cutoff']:^10}  {area_kr:^6}  {r['budget_min']:^4}분"
        f"  {r['walk_min']:^8.1f}  {r['remaining_min']:^8.1f}"
        f"  {r['pop_walk']:>12,.0f}  {r['emp_walk']:>12,.0f}"
    )
    if key[2] == 60 and key[0] != "2026-06-21":
        print("-" * 72)

print("=" * 72)

# ── 판교-위례 격차 ─────────────────────────────────────────────
print("\n판교 - 위례 도달 종사자 격차 (도보보정, 양수=판교 우위)")
print(f"{'':16}{'30분':>14}{'60분':>14}")
for cutoff in ["2016-01-01", "2026-06-21"]:
    pg30 = idx[(cutoff, "pangyo", 30)]["emp_walk"]
    wr30 = idx[(cutoff, "wirye",  30)]["emp_walk"]
    pg60 = idx[(cutoff, "pangyo", 60)]["emp_walk"]
    wr60 = idx[(cutoff, "wirye",  60)]["emp_walk"]
    print(f"  {cutoff}  {pg30-wr30:>+13,.0f}  {pg60-wr60:>+13,.0f}")
