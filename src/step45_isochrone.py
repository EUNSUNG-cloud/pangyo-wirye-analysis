"""
단계 4-5: 다익스트라 + 등시간권 폴리곤 생성
  - 판교역(신분당선) / 남위례역(서울8호선) 각각
  - 30분/60분 도달역 집합 계산
  - 800m 도보 버퍼 합집합 → GeoJSON 저장 (4326)
"""
import os, pickle, numpy as np, pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
import json, warnings
warnings.filterwarnings("ignore")

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
PROC = os.path.join(BASE, "data", "processed")
DOCS = os.path.join(BASE, "docs", "data")
os.makedirs(DOCS, exist_ok=True)

# ── 로드 ─────────────────────────────────────────────────────────
with open(os.path.join(PROC, "network_active.pkl"), "rb") as f:
    net = pickle.load(f)

nodes  = net["nodes"]    # active nodes
links  = net["links"]    # active links
found  = net["found"]    # {"pangyo": id, "namwirye": id}

# 전체 노드 수 (원본 id 기반 CSR 행렬 크기)
N = int(nodes["id"].max()) + 1

# ── 그래프 빌드 (directed, 초 단위) ──────────────────────────────
u    = links["fromNode"].to_numpy(dtype=np.int32)
v    = links["toNode"].to_numpy(dtype=np.int32)
ftFT = links["timeFT"].to_numpy(dtype=np.float32)
ftTF = links["timeTF"].to_numpy(dtype=np.float32)

# 양방향 엣지를 하나의 directed graph로 표현
src  = np.concatenate([u, v])
dst  = np.concatenate([v, u])
cost = np.concatenate([ftFT, ftTF])

A = csr_matrix((cost, (src, dst)), shape=(N, N))

print("=== 그래프 ===")
print(f"  노드 수(행렬 크기): {N}")
print(f"  엣지 수(방향 포함): {len(src)}")
print(f"  active nodes: {len(nodes)}")

# ── 다익스트라 실행 ───────────────────────────────────────────────
print("\n=== Dijkstra ===")
results = {}
THRESHOLDS_SEC = [30*60, 60*60]   # 1800s, 3600s

for label, src_id in found.items():
    dist = dijkstra(A, indices=src_id, directed=True)
    results[label] = dist

    for thr in THRESHOLDS_SEC:
        reachable = nodes[dist[nodes["id"]] <= thr]
        print(f"  [{label}] {thr//60}분 이내 도달역: {len(reachable):3d}개")

# ── 도달역 좌표 확인 ─────────────────────────────────────────────
print("\n=== 30분 도달역 (샘플 5개) ===")
for label in found:
    dist = results[label]
    r30 = nodes[dist[nodes["id"]] <= 1800].copy()
    r30["min"] = (dist[r30["id"]] / 60).round(1)
    print(f"  [{label}]")
    print(r30[["id","linenm","statnm","min"]].head(5).to_string(index=False))

# ── 등시간권 폴리곤 생성 (EPSG:5179 → 버퍼 → 합집합 → 4326 저장) ─
BUFFER_M = 800   # 도보권 반경 (m)

print(f"\n=== 등시간권 폴리곤 (버퍼 {BUFFER_M}m) ===")

label_names = {"pangyo": "pangyo", "namwirye": "namwirye"}
THRS_LABEL  = {1800: "30min", 3600: "60min"}

features = []
for label, dist in results.items():
    for thr, thr_label in THRS_LABEL.items():
        reach = nodes[dist[nodes["id"]] <= thr].copy()
        pts   = [Point(row["x_5179"], row["y_5179"]) for _, row in reach.iterrows()]
        gdf_pts = gpd.GeoDataFrame(geometry=pts, crs=5179)
        poly_5179 = unary_union(gdf_pts.buffer(BUFFER_M))
        poly_4326 = gpd.GeoSeries([poly_5179], crs=5179).to_crs(4326).iloc[0]
        area_km2  = poly_5179.area / 1e6

        features.append({
            "type": "Feature",
            "properties": {
                "station": label,
                "threshold": thr_label,
                "threshold_min": thr // 60,
                "n_stations": len(reach),
                "area_km2": round(area_km2, 2),
            },
            "geometry": poly_4326.__geo_interface__,
        })
        print(f"  [{label}] {thr_label}: {len(reach)}역, "
              f"면적={area_km2:.1f}km2")

        # 개별 파일도 저장 (분석 단계에서 편리하게 쓰기 위해)
        fname = f"isochrone_{label}_{thr_label}.geojson"
        gpd.GeoDataFrame(
            [{"station": label, "threshold": thr_label}],
            geometry=[poly_4326], crs=4326
        ).to_file(os.path.join(DOCS, fname), driver="GeoJSON")

# 4개를 하나의 FeatureCollection으로도 저장
fc = {"type": "FeatureCollection", "features": features}
out = os.path.join(DOCS, "isochrones.geojson")
with open(out, "w", encoding="utf-8") as f:
    json.dump(fc, f, ensure_ascii=False)
print(f"\n  저장: docs/data/isochrones.geojson (폴리곤 {len(features)}개)")

# 분석용 pickle (5179) 저장
with open(os.path.join(PROC, "dijkstra_results.pkl"), "wb") as f:
    pickle.dump({"results": results, "found": found, "nodes": nodes}, f)
print("  저장: data/processed/dijkstra_results.pkl")
