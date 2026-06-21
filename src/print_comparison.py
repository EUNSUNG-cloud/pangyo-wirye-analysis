"""판교TV vs 위례 비교표 출력"""
import json, pickle, os

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"

with open(os.path.join(BASE, "data", "processed", "boundaries.pkl"), "rb") as f:
    d = pickle.load(f)
b = d["boundaries"]

print("=== 구역계 중심좌표 ===")
for area, bd in b.items():
    print(f"  {area}: {bd['center_lat']}N, {bd['center_lon']}E"
          f"  ({bd['area_ha']}ha, {bd['n_parcel']}필지)")

with open(os.path.join(BASE, "docs", "data", "landuse_metrics.json"), encoding="utf-8") as f:
    m = json.load(f)

pg = m["pangyo"]
wr = m["wirye"]

print()
print("=" * 64)
print(f"  {'지표':<30}  {'판교TV':>14}  {'위례':>14}")
print("  " + "-" * 60)

rows = [
    ("area_ha",           "구역 면적 (ha)"),
    ("n_parcel_lsmd",     "LSMD 필지 수"),
    ("n_matched",         "건물 매칭 필지"),
    ("vac_pnu_pct",       "공지율 PNU기반 (%)"),
    ("vac_corr_pct",      "공지율 보정값 (%)"),
    ("tot_floor_m2",      "총 연면적 (m2)"),
    ("far_pct",           "평균 용적률 (%)"),
    ("lum_H",             "LUM 엔트로피 H"),
    ("lum_norm",          "LUM 정규화 (0-1)"),
    ("pop_in_zone",       "구역내 상주인구"),
    ("emp_in_zone",       "구역내 종사자"),
    ("biz_in_zone",       "구역내 사업체"),
    ("job_housing_ratio", "직주비 (종/인)"),
]
for key, lbl in rows:
    pv = pg[key]
    wv = wr[key]
    if isinstance(pv, float):
        print(f"  {lbl:<30}  {pv:>14.1f}  {wv:>14.1f}")
    else:
        print(f"  {lbl:<30}  {pv:>14,}  {wv:>14,}")

print()
print("  [주용도별 연면적 (m2)]")
cats = ["업무·연구", "상업·근생", "기타비주거"]
for cat in cats:
    pv = pg["cat_area_m2"].get(cat, 0)
    wv = wr["cat_area_m2"].get(cat, 0)
    print(f"  {cat:<30}  {pv:>14,}  {wv:>14,}")
