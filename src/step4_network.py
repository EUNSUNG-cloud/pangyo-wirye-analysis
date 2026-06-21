"""
단계 4-1~3: 지하철 네트워크 구축 + 핵심역 확인
"""
import os, pandas as pd, numpy as np, pickle
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
NET  = os.path.join(BASE, "data", "raw", "subway", "network")
PROC = os.path.join(BASE, "data", "processed")
os.makedirs(PROC, exist_ok=True)

CUTOFF = "2026-06-21"

# ── 1. nodes / links 로드 ─────────────────────────────────────────
nodes = pd.read_csv(os.path.join(NET, "nodes.tsv"), sep="\t", encoding="utf-8")
links = pd.read_csv(os.path.join(NET, "links.tsv"), sep="\t", encoding="utf-8")

print("=== RAW ===")
print(f"  nodes: {len(nodes)}  links: {len(links)}")
print(f"  links kind: {links['kind'].value_counts().to_dict()}")

# ── 2. 날짜 필터 (effective_begin이 NaN이면 begin 사용) ──────────
def eff(row):
    eb = row["effective_begin"]
    if pd.notna(eb) and str(eb).strip() not in ("", "nan"):
        return str(eb).strip()
    return str(row["begin"]).strip()

nodes["eff_begin"] = nodes.apply(eff, axis=1)
active_nodes = nodes[nodes["eff_begin"] <= CUTOFF].copy()
active_ids   = set(active_nodes["id"])

active_links = links[
    (links["begin"].astype(str) <= CUTOFF) &
    links["fromNode"].isin(active_ids) &
    links["toNode"].isin(active_ids)
].copy()

print(f"\n=== ACTIVE NETWORK ({CUTOFF}) ===")
print(f"  nodes: {len(active_nodes)} / {len(nodes)}")
print(f"  links: {len(active_links)} / {len(links)}")
print(f"  kind: {active_links['kind'].value_counts().to_dict()}")
print(f"  lines: {active_nodes['linenm'].nunique()}")
print(f"  begin range: {active_nodes['eff_begin'].min()} ~ {active_nodes['eff_begin'].max()}")

# ── 3. 핵심역 확인 ───────────────────────────────────────────────
KEY_STATIONS = {
    "pangyo":   ("판교", "신분당선"),
    "namwirye": ("남위례", "서울8호선"),
}

print("\n=== KEY STATIONS ===")
found = {}
for label, (stnm, linenm) in KEY_STATIONS.items():
    hit = active_nodes[
        (active_nodes["statnm"] == stnm) &
        (active_nodes["linenm"] == linenm)
    ]
    if len(hit) == 1:
        r = hit.iloc[0]
        found[label] = int(r["id"])
        print(f"  [{label}] FOUND id={r['id']} linenm={r['linenm']} statnm={r['statnm']}"
              f" x={r['x_5179']:.0f} y={r['y_5179']:.0f}"
              f" lat={r['lat']:.5f} lng={r['lng']:.5f}")
    elif len(hit) == 0:
        cand = active_nodes[
            active_nodes["statnm"].str.contains(stnm[:2], na=False) |
            active_nodes["linenm"].str.contains(linenm[:3], na=False)
        ][["id","linenm","statnm","eff_begin"]].drop_duplicates()
        print(f"  [{label}] NOT FOUND. candidates:\n{cand.to_string(index=False)}")
    else:
        print(f"  [{label}] MULTIPLE ({len(hit)}):\n{hit[['id','linenm','statnm']].to_string()}")

if len(found) < 2:
    print("\nSTOP: could not find all key stations.")
else:
    print(f"\n  pangyo id={found['pangyo']}, namwirye id={found['namwirye']}")
    with open(os.path.join(PROC, "network_active.pkl"), "wb") as f:
        pickle.dump({"nodes": active_nodes, "links": active_links, "found": found}, f)
    print("  saved: data/processed/network_active.pkl")
