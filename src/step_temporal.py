"""
시점별 등시간권 비교: 2016-01-01 (위례 입주 초기) vs 2026-06-21 (현재)
"""
import os, json, pickle
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
os.makedirs(DOCS, exist_ok=True)

# ── 0. 원본 전체 nodes / links 로드 ─────────────────────────────
nodes_all = pd.read_csv(os.path.join(NET, "nodes.tsv"), sep="\t", encoding="utf-8")
links_all = pd.read_csv(os.path.join(NET, "links.tsv"), sep="\t", encoding="utf-8")

# 위례 업무 중심 좌표 (WGS84 → EPSG:5179)
WIRYE_CENTER_WGS = (127.145, 37.475)   # lng, lat
tf = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
WIRYE_CENTER_5179 = tf.transform(*WIRYE_CENTER_WGS)   # (x, y)
print(f"위례 업무 중심 5179: x={WIRYE_CENTER_5179[0]:.0f}, y={WIRYE_CENTER_5179[1]:.0f}")


# ────────────────────────────────────────────────────────────────
# 1. 임의 시점 유효 네트워크 필터 함수
# ────────────────────────────────────────────────────────────────
def filter_network(cutoff: str):
    """cutoff(YYYY-MM-DD) 이하 begin/effective_begin 인 노드·링크만 반환"""
    def eff_date(row):
        eb = row["effective_begin"]
        if pd.notna(eb) and str(eb).strip() not in ("", "nan"):
            return str(eb).strip()
        return str(row["begin"]).strip()

    n = nodes_all.copy()
    n["eff_begin"] = n.apply(eff_date, axis=1)
    an = n[n["eff_begin"] <= cutoff].copy()
    aid = set(an["id"])

    al = links_all[
        (links_all["begin"].astype(str) <= cutoff) &
        links_all["fromNode"].isin(aid) &
        links_all["toNode"].isin(aid)
    ].copy()
    return an, al


# ────────────────────────────────────────────────────────────────
# 2. 그래프 빌드 + Dijkstra 함수
# ────────────────────────────────────────────────────────────────
def build_graph(active_nodes, active_links):
    N  = int(nodes_all["id"].max()) + 1
    u  = active_links["fromNode"].to_numpy(dtype=np.int32)
    v  = active_links["toNode"].to_numpy(dtype=np.int32)
    ft = active_links["timeFT"].to_numpy(dtype=np.float32)
    tf_ = active_links["timeTF"].to_numpy(dtype=np.float32)
    src  = np.concatenate([u, v])
    dst  = np.concatenate([v, u])
    cost = np.concatenate([ft, tf_])
    A    = csr_matrix((cost, (src, dst)), shape=(N, N))
    return A

def run_dijkstra(active_nodes, active_links, src_id):
    A    = build_graph(active_nodes, active_links)
    dist = dijkstra(A, indices=int(src_id), directed=True)
    return dist


# ────────────────────────────────────────────────────────────────
# 3. 가장 가까운 활성 역 탐색 함수
# ────────────────────────────────────────────────────────────────
def nearest_active_station(active_nodes, cx, cy, top_n=5):
    """(cx, cy) 5179 좌표에 가장 가까운 활성 역 top_n 반환"""
    an = active_nodes.copy()
    an["dist_m"] = np.sqrt((an["x_5179"] - cx)**2 + (an["y_5179"] - cy)**2)
    return an.nsmallest(top_n, "dist_m")[
        ["id","linenm","statnm","eff_begin","dist_m","x_5179","y_5179","lat","lng"]
    ]


# ────────────────────────────────────────────────────────────────
# 4. 폴리곤 빌드 + 면적비례 집계구 조인 함수
# ────────────────────────────────────────────────────────────────
BUFFER_M = 800

def make_poly(active_nodes, dist_arr, thr_sec):
    reach = active_nodes[dist_arr[active_nodes["id"]] <= thr_sec]
    if len(reach) == 0:
        return None
    pts = [Point(r["x_5179"], r["y_5179"]) for _, r in reach.iterrows()]
    return unary_union([p.buffer(BUFFER_M) for p in pts])

def weighted_census(oa, poly):
    if poly is None or poly.is_empty:
        return {"pop": 0, "emp": 0, "biz": 0, "n_tract": 0}
    minx, miny, maxx, maxy = poly.bounds
    cands = oa.cx[minx:maxx, miny:maxy].copy()
    if len(cands) == 0:
        return {"pop": 0, "emp": 0, "biz": 0, "n_tract": 0}
    tree  = STRtree(cands.geometry.values)
    idxs  = tree.query(poly)
    cands = cands.iloc[idxs].copy()
    cands["area_inter"] = cands.geometry.intersection(poly).area
    cands = cands[cands["area_inter"] > 0].copy()
    cands["ratio"] = (cands["area_inter"] / cands["area_total"]).clip(0, 1)
    return {
        "pop":     float((cands["pop_tot"] * cands["ratio"]).sum()),
        "emp":     float((cands["emp_tot"] * cands["ratio"]).sum()),
        "biz":     float((cands["biz_tot"] * cands["ratio"]).sum()),
        "n_tract": len(cands),
    }


# ────────────────────────────────────────────────────────────────
# 5. 집계구 로드
# ────────────────────────────────────────────────────────────────
print("\n집계구 로드 중...")
oa = gpd.read_file(os.path.join(PROC, "oa_joined.gpkg"), layer="oa").to_crs(5179)
oa["area_total"] = oa.geometry.area
print(f"  {len(oa):,}개 로드 완료")


# ────────────────────────────────────────────────────────────────
# 6. 두 시점 분석
# ────────────────────────────────────────────────────────────────
CUTOFFS = {
    "2016-01-01": "2016-01-01",
    "2026-06-21": "2026-06-21",
}

# 판교역 (신분당선, 2011-10-28 개통 → 두 시점 모두 존재)
PANGYO_STATNM = "판교"
PANGYO_LINENM = "신분당선"
# 남위례역 (서울8호선, 2021-03-27 개통 → 2026만 존재, 2016엔 대체역 사용)
WIRYE_STATNM  = "남위례"
WIRYE_LINENM  = "서울8호선"

all_rows = []
station_info = {}    # {cutoff: {"pangyo": {...}, "wirye": {...}}}
nearby_info  = {}    # 800m 반경 역 목록

for cutoff, label in CUTOFFS.items():
    print(f"\n{'='*55}")
    print(f"  시점: {cutoff}")
    print(f"{'='*55}")

    an, al = filter_network(cutoff)
    print(f"  활성 노드={len(an)}, 링크={len(al)}, 노선={an['linenm'].nunique()}")

    # ── 판교역 탐색 ────────────────────────────────────────────
    pg_hit = an[(an["statnm"] == PANGYO_STATNM) & (an["linenm"] == PANGYO_LINENM)]
    if len(pg_hit) == 1:
        pg = pg_hit.iloc[0]
        pg_id = int(pg["id"])
        pg_cx, pg_cy = pg["x_5179"], pg["y_5179"]
        print(f"  [판교] {pg['linenm']} {pg['statnm']} id={pg_id}"
              f" lat={pg['lat']:.4f} lng={pg['lng']:.4f}")
    else:
        print(f"  [판교] 미발견! (cutoff={cutoff})")
        continue

    # ── 위례 핵심역 탐색 ───────────────────────────────────────
    wr_hit = an[(an["statnm"] == WIRYE_STATNM) & (an["linenm"] == WIRYE_LINENM)]
    wx, wy = WIRYE_CENTER_5179
    if len(wr_hit) == 1:
        wr = wr_hit.iloc[0]
        wr_id = int(wr["id"])
        wr_cx, wr_cy = wr["x_5179"], wr["y_5179"]
        dist_to_center = np.sqrt((wr_cx - wx)**2 + (wr_cy - wy)**2)
        print(f"  [위례] {wr['linenm']} {wr['statnm']} id={wr_id}"
              f" lat={wr['lat']:.4f} lng={wr['lng']:.4f}"
              f" / 위례중심에서 {dist_to_center:.0f}m")
    else:
        # 대체역: 위례 중심에서 가장 가까운 활성 역
        nearest = nearest_active_station(an, wx, wy, top_n=5)
        print(f"  [위례] {WIRYE_STATNM}역 미개통. 가장 가까운 역 top5:")
        print(nearest[["id","linenm","statnm","eff_begin","dist_m"]].to_string(index=False))
        wr_row  = nearest.iloc[0]
        wr_id   = int(wr_row["id"])
        wr_cx, wr_cy = wr_row["x_5179"], wr_row["y_5179"]
        dist_to_center = float(wr_row["dist_m"])
        print(f"  -> 대체역 사용: {wr_row['linenm']} {wr_row['statnm']}"
              f" (위례 중심까지 {dist_to_center:.0f}m)")

    station_info[cutoff] = {
        "pangyo": {"id": pg_id, "x": pg_cx, "y": pg_cy,
                   "statnm": PANGYO_STATNM, "linenm": PANGYO_LINENM},
        "wirye":  {"id": wr_id, "x": wr_cx, "y": wr_cy,
                   "dist_to_center_m": round(dist_to_center)},
    }

    # ── Dijkstra ───────────────────────────────────────────────
    print(f"  Dijkstra 실행 중...")
    dist_pg = run_dijkstra(an, al, pg_id)
    dist_wr = run_dijkstra(an, al, wr_id)

    # ── 30/60분 집계 ───────────────────────────────────────────
    for tmin, tsec in [(30, 1800), (60, 3600)]:
        for area_label, dist_arr, cx, cy in [
            ("pangyo", dist_pg, pg_cx, pg_cy),
            ("wirye",  dist_wr, wr_cx, wr_cy),
        ]:
            n_st = int((dist_arr[an["id"]] <= tsec).sum())
            poly = make_poly(an, dist_arr, tsec)
            res  = weighted_census(oa, poly)
            area_km2 = round(poly.area / 1e6, 1) if poly else 0
            print(f"    [{area_label} {tmin}min] stations={n_st},"
                  f" area={area_km2}km2,"
                  f" pop={res['pop']:,.0f}, emp={res['emp']:,.0f}")
            all_rows.append({
                "cutoff":    cutoff,
                "area":      area_label,
                "threshold": tmin,
                "n_stations":n_st,
                "area_km2":  area_km2,
                "pop":       round(res["pop"]),
                "emp":       round(res["emp"]),
                "biz":       round(res["biz"]),
            })

    # ── 800m 반경 역 확인 ────────────────────────────────────────
    nearby_info[cutoff] = {}
    for area_label, cx, cy in [("pangyo", pg_cx, pg_cy),
                                 ("wirye",  wr_cx, wr_cy)]:
        nr = nearest_active_station(an, cx, cy, top_n=20)
        nr800 = nr[nr["dist_m"] <= 800][["linenm","statnm","eff_begin","dist_m"]]
        nearby_info[cutoff][area_label] = nr800.to_dict("records")
        print(f"  [{area_label}] 도보권(800m) 활성역: {len(nr800)}개")
        if len(nr800) > 0:
            print(nr800.to_string(index=False))


# ────────────────────────────────────────────────────────────────
# 7. 최종 비교표 출력
# ────────────────────────────────────────────────────────────────
df = pd.DataFrame(all_rows)

print("\n" + "="*70)
print("  최종 비교표: 도달 종사자(명) - 시점 x 지역 x 등시간권")
print("="*70)
pivot = df.pivot_table(
    index=["area","threshold"],
    columns="cutoff",
    values=["emp","pop","n_stations"],
    aggfunc="first"
)
print(pivot.to_string())

# emp만 간단 비교
print("\n  [종사자] 2016 vs 2026 (위례 결핍 크기)")
for tmin in [30, 60]:
    pg16 = df.query("area=='pangyo' and cutoff=='2016-01-01' and threshold==@tmin")["emp"].values[0]
    wr16 = df.query("area=='wirye'  and cutoff=='2016-01-01' and threshold==@tmin")["emp"].values[0]
    pg26 = df.query("area=='pangyo' and cutoff=='2026-06-21' and threshold==@tmin")["emp"].values[0]
    wr26 = df.query("area=='wirye'  and cutoff=='2026-06-21' and threshold==@tmin")["emp"].values[0]
    gap16 = pg16 - wr16
    gap26 = pg26 - wr26
    print(f"  {tmin}분 | 판교2016={pg16:>10,.0f}  위례2016={wr16:>10,.0f}  격차={gap16:>+10,.0f}")
    print(f"      | 판교2026={pg26:>10,.0f}  위례2026={wr26:>10,.0f}  격차={gap26:>+10,.0f}")


# ────────────────────────────────────────────────────────────────
# 8. 저장
# ────────────────────────────────────────────────────────────────
out = {
    "comparison_table": all_rows,
    "station_info":     station_info,
    "nearby_800m":      nearby_info,
}
with open(os.path.join(DOCS, "temporal_comparison.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\n저장: docs/data/temporal_comparison.json")
