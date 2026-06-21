"""
건축물대장 주용도 분포 분석 및 저장
"""
import os, json, pandas as pd

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
BLD  = os.path.join(BASE, "data", "processed", "buildings")
DOCS = os.path.join(BASE, "docs", "data")

TARGETS = [
    {"label": "판교_삼평동", "area": "pangyo"},
    {"label": "위례_창곡동", "area": "wirye"},
    {"label": "위례_장지동", "area": "wirye"},
]

# ── 로드 및 DataFrame 변환 ─────────────────────────────────────
dfs = {}
for t in TARGETS:
    lb = t["label"]
    with open(os.path.join(BLD, f"{lb}_title.json"), encoding="utf-8") as f:
        recs = json.load(f)
    df = pd.DataFrame(recs)
    df["area"] = t["area"]
    df["label"] = lb
    dfs[lb] = df
    print(f"{lb}: {len(df)}건, 컬럼수={len(df.columns)}")

# 위례 두 동 합산
wirye = pd.concat([dfs["위례_창곡동"], dfs["위례_장지동"]], ignore_index=True)
wirye_label = "위례(창곡+장지)"

# ── 주용도 분포 ───────────────────────────────────────────────
print("\n" + "="*60)
print("주용도 분포 비교 (mainPurpsCdNm)")
print("="*60)

for df, label in [(dfs["판교_삼평동"], "판교 삼평동"), (wirye, "위례(창곡+장지)")]:
    total = len(df)
    dist = df["mainPurpsCdNm"].fillna("미상").value_counts()
    print(f"\n[{label}] 총 {total}건")
    print(f"  {'주용도':<28} {'건수':>6}  {'비율':>6}")
    print(f"  {'-'*42}")
    for nm, cnt in dist.items():
        print(f"  {str(nm):<28} {cnt:>6}  {cnt/total*100:>5.1f}%")

# ── 업무·연구 특화 비교 ───────────────────────────────────────
print("\n" + "="*60)
print("업무·연구 시설 집중 비교")
print("="*60)

OFFICE_KEYS = ["업무시설"]
RESEARCH_KEYS = ["교육연구시설"]
RESI_KEYS = ["공동주택", "단독주택"]
RETAIL_KEYS = ["제1종근린생활시설", "제2종근린생활시설", "판매시설", "판매.영업.처리시설"]

def count_keys(df, keys):
    mask = df["mainPurpsCdNm"].isin(keys)
    return mask.sum(), mask.sum() / len(df) * 100

rows_out = []
for df, label in [(dfs["판교_삼평동"], "판교 삼평동"), (wirye, "위례(창곡+장지)")]:
    total = len(df)
    o_cnt, o_pct = count_keys(df, OFFICE_KEYS)
    r_cnt, r_pct = count_keys(df, RESEARCH_KEYS)
    rs_cnt, rs_pct = count_keys(df, RESI_KEYS)
    rt_cnt, rt_pct = count_keys(df, RETAIL_KEYS)
    print(f"\n[{label}] 총 {total}건")
    print(f"  업무시설:          {o_cnt:>5}건  ({o_pct:>5.1f}%)")
    print(f"  교육연구시설:      {r_cnt:>5}건  ({r_pct:>5.1f}%)")
    print(f"  주거(공동+단독):   {rs_cnt:>5}건  ({rs_pct:>5.1f}%)")
    print(f"  근린·판매:         {rt_cnt:>5}건  ({rt_pct:>5.1f}%)")
    rows_out.append({
        "지역": label, "전체": total,
        "업무시설_건": o_cnt, "업무시설_%": round(o_pct,1),
        "교육연구_건": r_cnt, "교육연구_%": round(r_pct,1),
        "주거_건": rs_cnt, "주거_%": round(rs_pct,1),
        "근린판매_건": rt_cnt, "근린판매_%": round(rt_pct,1),
    })

# ── 연면적 기준 ───────────────────────────────────────────────
print("\n" + "="*60)
print("업무시설 연면적 비교 (totArea 기준, m²)")
print("="*60)

for df, label in [(dfs["판교_삼평동"], "판교 삼평동"), (wirye, "위례(창곡+장지)")]:
    df2 = df.copy()
    df2["totArea"] = pd.to_numeric(df2["totArea"], errors="coerce").fillna(0)
    office = df2[df2["mainPurpsCdNm"] == "업무시설"]
    if len(office) > 0:
        print(f"\n[{label}] 업무시설 {len(office)}건")
        print(f"  연면적 합계:  {office['totArea'].sum():>12,.0f} m²")
        print(f"  평균 연면적:  {office['totArea'].mean():>12,.0f} m²")
        print(f"  최대 연면적:  {office['totArea'].max():>12,.0f} m²")
    else:
        print(f"\n[{label}] 업무시설 0건")

# ── 저장 ─────────────────────────────────────────────────────
summary = {
    "by_area": rows_out,
    "pangyo_dist": dfs["판교_삼평동"]["mainPurpsCdNm"].fillna("미상").value_counts().to_dict(),
    "wirye_changok_dist": dfs["위례_창곡동"]["mainPurpsCdNm"].fillna("미상").value_counts().to_dict(),
    "wirye_jangji_dist":  dfs["위례_장지동"]["mainPurpsCdNm"].fillna("미상").value_counts().to_dict(),
}
def to_py(obj):
    if isinstance(obj, dict):
        return {k: to_py(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_py(v) for v in obj]
    if hasattr(obj, "item"):   # numpy/pandas scalar
        return obj.item()
    return obj

with open(os.path.join(DOCS, "buildings_summary.json"), "w", encoding="utf-8") as f:
    json.dump(to_py(summary), f, ensure_ascii=False, indent=2)
print(f"\n저장: docs/data/buildings_summary.json")
