"""
도보 보정 등시간권 분석
- export.geojson: 로마(lon~12.5E, lat~41.9N) 좌표 → 한국 미해당, 사용 불가
- 대체: 직선거리 x 1.2 우회계수 / 도보속도 4.5 km/h (=75 m/min)
- 업무지구 중심 -> 최가 역 도보시간을 30/60분 예산에서 선공제
"""
import os, json, pickle, math
import numpy as np, pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.strtree import STRtree
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from pyproj import Transformer
import warnings
warnings.filterwarnings("ignore")

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
NET  = os.path.join(BASE, "data", "raw", "subway", "network")
PROC = os.path.join(BASE, "data", "processed")
DOCS = os.path.join(BASE, "docs", "data")

# ── 상수 ─────────────────────────────────────────────────────────
WALK_SPEED_MPS  = 4500 / 3600   # 4.5 km/h -> m/s = 1.25
DETOUR_FACTOR   = 1.2            # 직선 -> 실경로 보정계수 (도심)
BUFFER_M        = 800

# 업무지구 중심 (WGS84)
CENTERS_WGS = {
    "pangyo":  (127.108, 37.402),   # 판교TV 중심
    "wirye":   (127.145, 37.475),   # 위례 업무 중심
}

# WGS84 -> EPSG:5179
tf = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
CENTERS_5179 = {k: tf.transform(*v) for k, v in CENTERS_WGS.items()}
print("업무지구 중심 (EPSG:5179):")
for k, (x, y) in CENTERS_5179.items():
    print(f"  {k}: x={x:.0f}, y={y:.0f}")

# ── 헬퍼 함수들 ──────────────────────────────────────────────────

def straight_dist(x1, y1, x2, y2):
    return math.sqrt((x1-x2)**2 + (y1-y2)**2)

def walk_time_sec(dist_m):
    """직선거리 -> 실경로 환산 -> 도보 소요초"""
    return dist_m * DETOUR_FACTOR / WALK_SPEED_MPS

def filter_network(cutoff: str):
    def eff(row):
        eb = row["effective_begin"]
        if pd.notna(eb) and str(eb).strip() not in ("", "nan"):
            return str(eb).strip()
        return str(row["begin"]).strip()
    n = nodes_all.copy()
    n["eff_begin"] = n.apply(eff, axis=1)
    an = n[n["eff_begin"] <= cutoff].copy()
    aid = set(an["id"])
    al = links_all[
        (links_all["begin"].astype(str) <= cutoff) &
        links_all["fromNode"].isin(aid) &
        links_all["toNode"].isin(aid)
    ].copy()
    return an, al

def build_dijkstra(active_nodes, active_links, src_id):
    N = int(nodes_all["id"].max()) + 1
    u  = active_links["fromNode"].to_numpy(np.int32)
    v  = active_links["toNode"].to_numpy(np.int32)
    ft = active_links["timeFT"].to_numpy(np.float32)
    tf_ = active_links["timeTF"].to_numpy(np.float32)
    A = csr_matrix(
        (np.concatenate([ft, tf_]),
         (np.concatenate([u,v]), np.concatenate([v,u]))),
        shape=(N, N)
    )
    return dijkstra(A, indices=int(src_id), directed=True)

def make_poly(active_nodes, dist_arr, thr_sec):
    reach = active_nodes[dist_arr[active_nodes["id"]] <= thr_sec]
    if len(reach) == 0:
        return None
    pts = [Point(r["x_5179"], r["y_5179"]) for _, r in reach.iterrows()]
    return unary_union([p.buffer(BUFFER_M) for p in pts])

def weighted_census(oa, poly):
    if poly is None or poly.is_empty:
        return {"pop": 0, "emp": 0, "biz": 0}
    minx, miny, maxx, maxy = poly.bounds
    cands = oa.cx[minx:maxx, miny:maxy].copy()
    if len(cands) == 0:
        return {"pop": 0, "emp": 0, "biz": 0}
    tree = STRtree(cands.geometry.values)
    idxs = tree.query(poly)
    cands = cands.iloc[idxs].copy()
    cands["ai"] = cands.geometry.intersection(poly).area
    cands = cands[cands["ai"] > 0].copy()
    cands["r"] = (cands["ai"] / cands["area_total"]).clip(0, 1)
    return {
        "pop": float((cands["pop_tot"] * cands["r"]).sum()),
        "emp": float((cands["emp_tot"] * cands["r"]).sum()),
        "biz": float((cands["biz_tot"] * cands["r"]).sum()),
    }

def nearest_stations(active_nodes, cx, cy, top_n=10):
    an = active_nodes.copy()
    an["dist_m"] = np.sqrt((an["x_5179"]-cx)**2 + (an["y_5179"]-cy)**2)
    return an.nsmallest(top_n, "dist_m")

# ── 데이터 로드 ───────────────────────────────────────────────────
print("\n데이터 로드...")
nodes_all = pd.read_csv(os.path.join(NET, "nodes.tsv"), sep="\t", encoding="utf-8")
links_all = pd.read_csv(os.path.join(NET, "links.tsv"), sep="\t", encoding="utf-8")

oa = gpd.read_file(os.path.join(PROC, "oa_joined.gpkg"), layer="oa").to_crs(5179)
oa["area_total"] = oa.geometry.area
print(f"  집계구 {len(oa):,}개")

# 이전 역기준 결과 재사용
prev_path = os.path.join(DOCS, "temporal_comparison.json")
with open(prev_path, encoding="utf-8") as f:
    prev = json.load(f)
prev_table = {
    (r["cutoff"], r["area"], r["threshold"]): r
    for r in prev["comparison_table"]
}

# ────────────────────────────────────────────────────────────────
# 분석: 두 시점 x 두 지역 x 두 예산
# ────────────────────────────────────────────────────────────────
CUTOFFS = ["2016-01-01", "2026-06-21"]
BUDGETS = [30, 60]

# 핵심역 정의
KEY_STATIONS = {
    "2016-01-01": {
        "pangyo":  ("판교", "신분당선"),
        "wirye":   None,   # 대체역 자동 탐색
    },
    "2026-06-21": {
        "pangyo":  ("판교", "신분당선"),
        "wirye":   ("남위례", "서울8호선"),
    },
}

rows = []          # 최종 비교표
nearby_rows = []   # 도보권 역 목록

for cutoff in CUTOFFS:
    print(f"\n{'='*60}")
    print(f"시점: {cutoff}")
    an, al = filter_network(cutoff)
    print(f"  nodes={len(an)}, links={len(al)}")

    for area_key in ["pangyo", "wirye"]:
        cx, cy = CENTERS_5179[area_key]

        # ── 가장 가까운 역 확정 ──────────────────────────────────
        spec = KEY_STATIONS[cutoff][area_key]
        if spec is not None:
            stnm, linenm = spec
            hit = an[(an["statnm"] == stnm) & (an["linenm"] == linenm)]
            if len(hit) == 1:
                srow = hit.iloc[0]
                src_id = int(srow["id"])
                sx, sy = srow["x_5179"], srow["y_5179"]
                station_label = f"{linenm} {stnm}"
            else:
                print(f"  [{area_key}] 지정역 미발견: {spec}")
                continue
        else:
            # 위례 2016: 가장 가까운 역 자동 선택
            nr = nearest_stations(an, cx, cy, top_n=1)
            srow = nr.iloc[0]
            src_id = int(srow["id"])
            sx, sy = srow["x_5179"], srow["y_5179"]
            station_label = f"{srow['linenm']} {srow['statnm']} (대체)"

        # ── 도보 거리/시간 계산 ───────────────────────────────────
        walk_dist_straight = straight_dist(cx, cy, sx, sy)
        walk_dist_route    = walk_dist_straight * DETOUR_FACTOR
        walk_sec           = walk_dist_route / WALK_SPEED_MPS
        walk_min           = walk_sec / 60

        print(f"  [{area_key}] 핵심역={station_label}")
        print(f"    직선={walk_dist_straight:.0f}m, 경로추정={walk_dist_route:.0f}m"
              f", 도보={walk_min:.1f}min")

        # ── Dijkstra (핵심역 출발) ───────────────────────────────
        dist_arr = build_dijkstra(an, al, src_id)

        # ── 각 예산 처리 ──────────────────────────────────────────
        for budget_min in BUDGETS:
            budget_sec      = budget_min * 60
            remaining_sec   = budget_sec - walk_sec
            remaining_min   = remaining_sec / 60

            # 역기준 (기존)
            prev_r = prev_table.get((cutoff, area_key, budget_min), {})
            emp_station = prev_r.get("emp", 0)
            pop_station = prev_r.get("pop", 0)

            if remaining_sec <= 0:
                # 예산이 도보로 모두 소진 -> 지하철 도달 불가
                emp_walk = 0
                pop_walk = 0
                n_st_walk = 0
                area_km2_walk = 0.0
                print(f"    {budget_min}min -> 도보시간({walk_min:.1f}min) > 예산 -> 도달역 없음")
            else:
                poly_walk = make_poly(an, dist_arr, remaining_sec)
                res_walk  = weighted_census(oa, poly_walk)
                n_st_walk = int((dist_arr[an["id"]] <= remaining_sec).sum())
                area_km2_walk = round(poly_walk.area/1e6, 1) if poly_walk else 0
                emp_walk = round(res_walk["emp"])
                pop_walk = round(res_walk["pop"])
                print(f"    {budget_min}min -> 잔여={remaining_min:.1f}min"
                      f", stations={n_st_walk}, emp={emp_walk:,.0f}"
                      f" (역기준 emp={emp_station:,.0f}"
                      f", 비율={emp_walk/emp_station*100:.1f}% )" if emp_station else
                      f"    {budget_min}min -> 잔여={remaining_min:.1f}min"
                      f", stations={n_st_walk}, emp={emp_walk:,.0f}")

            rows.append({
                "cutoff":          cutoff,
                "area":            area_key,
                "budget_min":      budget_min,
                "station_label":   station_label,
                "walk_dist_m":     round(walk_dist_straight),
                "walk_route_m":    round(walk_dist_route),
                "walk_min":        round(walk_min, 1),
                "remaining_min":   round(max(remaining_min, 0), 1),
                "n_stations_walk": n_st_walk,
                "area_km2_walk":   area_km2_walk,
                "emp_station":     int(emp_station),
                "emp_walk":        int(emp_walk),
                "pop_station":     int(pop_station),
                "pop_walk":        int(pop_walk),
            })

        # ── 도보권(800m, 1km) 내 역 목록 ─────────────────────────
        nr_all = nearest_stations(an, cx, cy, top_n=30)
        for radius in [800, 1000]:
            nr_in = nr_all[nr_all["dist_m"] <= radius]
            nearby_rows.append({
                "cutoff":   cutoff,
                "area":     area_key,
                "radius_m": radius,
                "n_stations": len(nr_in),
                "stations": [
                    {"linenm": r["linenm"], "statnm": r["statnm"],
                     "dist_m": round(r["dist_m"]), "since": r["eff_begin"]}
                    for _, r in nr_in.iterrows()
                ],
            })

# ────────────────────────────────────────────────────────────────
# 최종 비교표
# ────────────────────────────────────────────────────────────────
df = pd.DataFrame(rows)

print("\n" + "="*72)
print("  [도달 종사자 비교표] 역기준 vs 도보보정")
print("="*72)
cols = ["cutoff","area","budget_min","walk_min","remaining_min",
        "emp_station","emp_walk"]
print(df[cols].to_string(index=False))

print("\n  [종사자 격차: 판교 - 위례]")
print(f"  {'':20s}  {'30min':>12s}  {'60min':>12s}")
for cutoff in CUTOFFS:
    for col in ["emp_station","emp_walk"]:
        label = "역기준" if col=="emp_station" else "도보보정"
        pg = df.query("cutoff==@cutoff and area=='pangyo' and budget_min==30")[col].values
        wr = df.query("cutoff==@cutoff and area=='wirye'  and budget_min==30")[col].values
        pg60 = df.query("cutoff==@cutoff and area=='pangyo' and budget_min==60")[col].values
        wr60 = df.query("cutoff==@cutoff and area=='wirye'  and budget_min==60")[col].values
        if len(pg) and len(wr):
            g30 = pg[0]-wr[0]; g60 = pg60[0]-wr60[0]
            print(f"  {cutoff} {label:6s}  {g30:>+12,.0f}  {g60:>+12,.0f}")

print("\n  [도보권 내 역 수] 업무지구 중심 기준")
nr_df = pd.DataFrame([
    {"cutoff":r["cutoff"],"area":r["area"],"radius_m":r["radius_m"],"n":r["n_stations"]}
    for r in nearby_rows
])
print(nr_df.pivot_table(index=["area","cutoff"], columns="radius_m", values="n").to_string())

# ── 저장 ─────────────────────────────────────────────────────────
out = {
    "note": (
        "walk_dist: straight-line, walk_route: x1.2 detour, "
        "walk_speed: 4.5km/h. export.geojson unusable (Rome coords)."
    ),
    "walk_correction_table": rows,
    "nearby_stations": nearby_rows,
}
with open(os.path.join(DOCS, "walk_corrected.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\n저장: docs/data/walk_corrected.json")
