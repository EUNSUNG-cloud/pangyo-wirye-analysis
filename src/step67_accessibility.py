"""
단계 6-7: 등시간권 × 집계구 공간결합 + 누적 접근성 곡선
  - 집계구 경계에 걸치는 경우 면적비례 배분
  - EPSG:5179 기준 분석
"""
import os, pickle, json, time
import numpy as np, pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.strtree import STRtree
import warnings
warnings.filterwarnings("ignore")

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
PROC = os.path.join(BASE, "data", "processed")
DOCS = os.path.join(BASE, "docs", "data")

# ── 로드 ─────────────────────────────────────────────────────────
print("=== 데이터 로드 ===")
with open(os.path.join(PROC, "dijkstra_results.pkl"), "rb") as f:
    dijk = pickle.load(f)
results = dijk["results"]   # {"pangyo": dist_arr, "namwirye": dist_arr}
nodes   = dijk["nodes"]

print("  dijkstra 로드 완료")
oa = gpd.read_file(os.path.join(PROC, "oa_joined.gpkg"), layer="oa")
oa = oa.to_crs(5179)
oa["area_total"] = oa.geometry.area
print(f"  집계구 {len(oa):,}개 로드 완료, CRS={oa.crs.to_epsg()}")


# ── 도달역 → 폴리곤 빌드 헬퍼 (5179) ───────────────────────────
BUFFER_M = 800

def make_poly_5179(dist_arr, thr_sec):
    """거리 배열에서 thr_sec 이내 도달 역들의 버퍼 합집합(5179) 반환"""
    reach = nodes[dist_arr[nodes["id"]] <= thr_sec]
    if len(reach) == 0:
        return None
    pts  = [Point(r["x_5179"], r["y_5179"]) for _, r in reach.iterrows()]
    return unary_union([p.buffer(BUFFER_M) for p in pts])


# ── 면적비례 조인 헬퍼 ────────────────────────────────────────────
def weighted_sum(oa_gdf, poly):
    """폴리곤과 겹치는 집계구를 면적비례 가중합산"""
    # 1) bbox 사전 필터
    minx, miny, maxx, maxy = poly.bounds
    candidates = oa_gdf.cx[minx:maxx, miny:maxy].copy()
    if len(candidates) == 0:
        return {"pop": 0.0, "biz": 0.0, "emp": 0.0, "n_tract": 0}

    # 2) STRtree 교차 필터
    tree  = STRtree(candidates.geometry.values)
    idxs  = tree.query(poly)              # 후보 인덱스
    cands = candidates.iloc[idxs].copy()
    if len(cands) == 0:
        return {"pop": 0.0, "biz": 0.0, "emp": 0.0, "n_tract": 0}

    # 3) 실제 교차 및 면적비 계산
    cands["area_inter"] = cands.geometry.intersection(poly).area
    cands = cands[cands["area_inter"] > 0]
    cands["ratio"] = cands["area_inter"] / cands["area_total"]
    cands["ratio"] = cands["ratio"].clip(0, 1)

    return {
        "pop": float((cands["pop_tot"] * cands["ratio"]).sum()),
        "biz": float((cands["biz_tot"] * cands["ratio"]).sum()),
        "emp": float((cands["emp_tot"] * cands["ratio"]).sum()),
        "n_tract": len(cands),
    }


# ── 6. 30/60분 도달 인구·종사자 비교표 ─────────────────────────
print("\n=== 단계 6: 30/60분 도달 인구·종사자 ===")
THRS = {30: 1800, 60: 3600}
table_rows = []

for label, dist in results.items():
    for tmin, tsec in THRS.items():
        t0   = time.time()
        poly = make_poly_5179(dist, tsec)
        res  = weighted_sum(oa, poly)
        n_st = int((dist[nodes["id"]] <= tsec).sum())
        elapsed = time.time() - t0
        row = {
            "station": label,
            "threshold_min": tmin,
            "n_stations": n_st,
            "area_km2": round(poly.area / 1e6, 1),
            **{k: round(v) for k, v in res.items() if k != "n_tract"},
            "n_tracts": res["n_tract"],
        }
        table_rows.append(row)
        print(f"  [{label} {tmin}min] stations={n_st}, "
              f"area={poly.area/1e6:.1f}km2, "
              f"pop={res['pop']:,.0f}, emp={res['emp']:,.0f}, "
              f"biz={res['biz']:,.0f}  ({elapsed:.1f}s)")

table = pd.DataFrame(table_rows)
print("\n  === 비교표 ===")
print(table.to_string(index=False))

# 저장
table.to_json(os.path.join(DOCS, "accessibility_30_60.json"),
              orient="records", force_ascii=False, indent=2)
print("\n  저장: docs/data/accessibility_30_60.json")


# ── 7. 누적 접근성 곡선 (5분 간격 0~60분) ───────────────────────
print("\n=== 단계 7: 누적 접근성 곡선 ===")
STEPS_MIN = list(range(0, 65, 5))   # 0,5,10,...,60

curve_data = {"pangyo": [], "namwirye": []}

for label, dist in results.items():
    print(f"  [{label}] 계산 중 (13 step)...")
    for tmin in STEPS_MIN:
        tsec = tmin * 60
        poly = make_poly_5179(dist, tsec)
        if poly is None or poly.is_empty:
            curve_data[label].append({
                "t_min": tmin, "pop": 0, "emp": 0, "biz": 0, "n_stations": 0
            })
            continue
        res  = weighted_sum(oa, poly)
        n_st = int((dist[nodes["id"]] <= tsec).sum())
        curve_data[label].append({
            "t_min": tmin,
            "pop":   round(res["pop"]),
            "emp":   round(res["emp"]),
            "biz":   round(res["biz"]),
            "n_stations": n_st,
        })
    last = curve_data[label][-1]
    print(f"    60min -> pop={last['pop']:,.0f}, emp={last['emp']:,.0f}")

out_curve = os.path.join(DOCS, "accessibility_curve.json")
with open(out_curve, "w", encoding="utf-8") as f:
    json.dump(curve_data, f, ensure_ascii=False, indent=2)
print(f"\n  저장: docs/data/accessibility_curve.json")
print("완료.")
