"""
단계 3-4: 구역계 토지이용 지표 + 직주비
  - 공지율: (LSMD 필지 - 매칭 건물 필지) / LSMD 필지 (판교는 과대 보정 명시)
  - 용적률: 건물 연면적 / LSMD 필지 면적
  - 주용도 구성비 (연면적 기준)
  - LUM 엔트로피 (Shannon, 연면적 기준)
  - 직주비: 구역계 × 집계구 면적비례 조인
"""
import os, pickle, json, math
import numpy as np, pandas as pd
import geopandas as gpd
from shapely.strtree import STRtree
import warnings; warnings.filterwarnings("ignore")

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
PROC = os.path.join(BASE, "data", "processed")
DOCS = os.path.join(BASE, "docs", "data")

# ── 로드 ─────────────────────────────────────────────────────────
print("=== 데이터 로드 ===")
with open(os.path.join(PROC,"boundaries.pkl"),"rb") as f:
    data = pickle.load(f)
gdfs       = data["gdfs"]        # area -> GeoDataFrame (LSMD + 건물정보)
boundaries = data["boundaries"]  # area -> 요약dict

oa = gpd.read_file(os.path.join(PROC,"oa_joined.gpkg"), layer="oa").to_crs(5179)
oa["area_total"] = oa.geometry.area
print(f"  집계구 {len(oa):,}개")

# 구역계 폴리곤 로드 (5179)
zones = {}
for area in ["pangyo","wirye"]:
    gdf_zone = gpd.read_file(os.path.join(PROC,f"{area}_zone.gpkg")).to_crs(5179)
    zones[area] = gdf_zone.geometry.iloc[0]   # 단일 폴리곤 or MultiPolygon

# ── 헬퍼 ─────────────────────────────────────────────────────────
RESI_CATS  = {"공동주택","단독주택"}
OFFICE_CAT = "업무시설"
NON_RESI   = {"업무시설","교육연구시설","판매시설","판매.영업.처리시설",
              "제1종근린생활시설","제2종근린생활시설","문화및집회시설",
              "의료시설","숙박시설","위락시설","창고시설","운수시설","자동차관련시설"}

# 용도 -> 대분류
def cat5(purp):
    if purp in ("업무시설","교육연구시설"): return "업무·연구"
    if purp in ("제1종근린생활시설","제2종근린생활시설","판매시설","판매.영업.처리시설"):
        return "상업·근생"
    if purp in RESI_CATS: return "주거"
    if pd.isna(purp) or purp=="": return "공지"
    return "기타비주거"

def shannon(ser):
    """시리즈 합계 기반 Shannon entropy"""
    tot = ser.sum()
    if tot == 0: return 0.0
    ps = ser[ser>0] / tot
    return float(-(ps * np.log(ps)).sum())

# 면적비례 집계구 가중합산
def census_in_zone(oa_gdf, poly):
    minx,miny,maxx,maxy = poly.bounds
    cands = oa_gdf.cx[minx:maxx, miny:maxy].copy()
    if len(cands)==0: return {"pop":0,"emp":0,"biz":0}
    tree  = STRtree(cands.geometry.values)
    idxs  = tree.query(poly)
    cands = cands.iloc[idxs].copy()
    cands["ai"] = cands.geometry.intersection(poly).area
    cands = cands[cands["ai"]>0]
    cands["r"] = (cands["ai"]/cands["area_total"]).clip(0,1)
    return {"pop": float((cands["pop_tot"]*cands["r"]).sum()),
            "emp": float((cands["emp_tot"]*cands["r"]).sum()),
            "biz": float((cands["biz_tot"]*cands["r"]).sum())}

# ── 원본 건물 수 (전체 동 기준, 공지율 보정용) ───────────────────
BLD_CNT_TOTAL = {"pangyo": 423, "wirye": 3730}   # API 수집 결과
LSMD_TOTAL    = {"pangyo": 421, "wirye": 5405}

# ── 분석 루프 ─────────────────────────────────────────────────────
results = {}
print()

for area in ["pangyo","wirye"]:
    gdf   = gdfs[area]
    poly  = zones[area]
    b     = boundaries[area]
    label = "판교TV" if area=="pangyo" else "위례"

    print(f"=== {label} ===")

    # ── 구역 내 필지 ─────────────────────────────────────────────
    within = gdf[gdf.geometry.intersects(poly.buffer(-1))].copy()
    n_total = len(within)
    n_matched = within["mainPurps"].notna().sum()

    # ── 1. 공지율 ─────────────────────────────────────────────────
    # PNU 기반 (판교는 과대, 참고용)
    n_empty_pnu = (within["purp_class"]=="empty").sum()
    vac_pnu = n_empty_pnu / max(n_total,1) * 100

    # 보정 공지율: 전체 동 건물 수 / LSMD 필지 수 비율로 구역 내 보정
    occupancy_ratio = min(BLD_CNT_TOTAL[area] / LSMD_TOTAL[area], 1.0)
    vac_corrected   = (1 - occupancy_ratio) * 100
    print(f"  공지율(PNU기반): {vac_pnu:.1f}%  |  보정공지율: {vac_corrected:.1f}%"
          f"  {'[판교: lot 분할로 PNU 과대계상]' if area=='pangyo' else ''}")

    # ── 2. 용적률 (연면적/LSMD필지면적) ─────────────────────────
    matched = within[within["mainPurps"].notna()].copy()
    matched["totArea_sum"] = pd.to_numeric(
        matched.get("totArea_sum",0), errors="coerce").fillna(0)
    tot_floor   = matched["totArea_sum"].sum()
    tot_lot     = within["area_m2"].sum()
    far_avg     = tot_floor / max(tot_lot,1) * 100   # 백분율
    print(f"  연면적 합계: {tot_floor:,.0f}m2  대지면적: {tot_lot/1e4:.1f}ha"
          f"  용적률: {far_avg:.0f}%")

    # ── 3. 주용도 구성비 (연면적 기준) ───────────────────────────
    matched["cat5"] = matched["mainPurps"].apply(cat5)
    cat_area = matched.groupby("cat5")["totArea_sum"].sum().sort_values(ascending=False)
    total_floor_cat = cat_area.sum()
    print(f"  주용도 구성비 (연면적):")
    for cat,area_val in cat_area.items():
        print(f"    {cat}: {area_val:>12,.0f}m2  ({area_val/max(total_floor_cat,1)*100:.1f}%)")

    # ── 4. LUM 엔트로피 ───────────────────────────────────────────
    lum = shannon(cat_area)
    lum_norm = lum / math.log(max(len(cat_area),2))  # 0~1 정규화
    print(f"  LUM 엔트로피: H={lum:.3f}  정규화={lum_norm:.3f}")

    # ── 5. 직주비 (집계구 면적비례) ──────────────────────────────
    print(f"  직주비 계산 중...")
    census = census_in_zone(oa, poly)
    pop    = census["pop"]
    emp    = census["emp"]
    biz    = census["biz"]
    jjr    = emp / max(pop,1)
    print(f"  상주인구: {pop:,.0f}  종사자: {emp:,.0f}  직주비: {jjr:.2f}")

    results[area] = {
        "label":          label,
        "area_ha":        b["area_ha"],
        "n_parcel_lsmd":  n_total,
        "n_matched":      int(n_matched),
        "vac_pnu_pct":    round(vac_pnu,1),
        "vac_corr_pct":   round(vac_corrected,1),
        "tot_floor_m2":   round(tot_floor),
        "far_pct":        round(far_avg),
        "lum_H":          round(lum,3),
        "lum_norm":       round(lum_norm,3),
        "pop_in_zone":    round(pop),
        "emp_in_zone":    round(emp),
        "biz_in_zone":    round(biz),
        "job_housing_ratio": round(jjr,2),
        "cat_area_m2":    {k:round(float(v)) for k,v in cat_area.items()},
    }
    print()

# ── 최종 비교표 ───────────────────────────────────────────────────
print("=" * 62)
print(f"  {'지표':<28}  {'판교TV':>14}  {'위례':>14}")
print("  " + "-"*58)

metrics = [
    ("area_ha",            "구역 면적 (ha)"),
    ("n_parcel_lsmd",      "LSMD 필지 수"),
    ("n_matched",          "건물 매칭 필지"),
    ("vac_pnu_pct",        "공지율 PNU기반 (%)"),
    ("vac_corr_pct",       "공지율 보정값 (%)"),
    ("tot_floor_m2",       "총 연면적 (m2)"),
    ("far_pct",            "평균 용적률 (%)"),
    ("lum_H",              "LUM 엔트로피 H"),
    ("lum_norm",           "LUM 정규화 (0-1)"),
    ("pop_in_zone",        "구역내 상주인구"),
    ("emp_in_zone",        "구역내 종사자"),
    ("job_housing_ratio",  "직주비 (종/인)"),
]

for key, label in metrics:
    pg = results["pangyo"][key]
    wr = results["wirye"][key]
    if isinstance(pg, float):
        print(f"  {label:<28}  {pg:>14.1f}  {wr:>14.1f}")
    else:
        print(f"  {label:<28}  {pg:>14,}  {wr:>14,}")

# ── 저장 ─────────────────────────────────────────────────────────
def to_py(x):
    if isinstance(x,dict):  return {k:to_py(v) for k,v in x.items()}
    if isinstance(x,list):  return [to_py(v) for v in x]
    if hasattr(x,"item"):   return x.item()
    return x

with open(os.path.join(DOCS,"landuse_metrics.json"),"w",encoding="utf-8") as f:
    json.dump(to_py(results), f, ensure_ascii=False, indent=2)
print(f"\n  저장: docs/data/landuse_metrics.json")
