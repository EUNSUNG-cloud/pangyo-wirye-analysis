"""PNU 포맷 진단 — LSMD vs 건축물대장"""
import os, json, geopandas as gpd, pandas as pd
import warnings; warnings.filterwarnings("ignore")

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
RAW  = os.path.join(BASE, "data", "raw")
BLD  = os.path.join(BASE, "data", "processed", "buildings")

# 1) LSMD PNU 실제 샘플 (삼평동)
gdf = gpd.read_file(os.path.join(RAW,"lsmd_bundang","LSMD_CONT_LDREG_41135_202606.shp"))
samp = gdf[gdf["PNU"].str[:10] == "4113510900"].head(10)
print("=== LSMD 삼평동 PNU 샘플 ===")
for _, r in samp.iterrows():
    print(f"  PNU={r['PNU']}  len={len(str(r['PNU']))}  JIBUN={r['JIBUN']}")

# 2) 건축물대장 재구성 PNU 샘플
with open(os.path.join(BLD, "판교_삼평동_title.json"), encoding="utf-8") as f:
    bld = json.load(f)
df = pd.DataFrame(bld)

def build_pnu(row):
    sg  = str(row.get("sigunguCd","")).zfill(5)
    bj  = str(row.get("bjdongCd","")).zfill(5)
    gb  = str(row.get("platGbCd","0"))
    bun = str(row.get("bun","0")).strip().zfill(4)
    ji  = str(row.get("ji","0")).strip().zfill(4)
    return sg + bj + gb + bun + ji

df["pnu19"] = df.apply(build_pnu, axis=1)
print("\n=== 건축물대장 재구성 PNU 샘플 ===")
for _, r in df.head(10).iterrows():
    raw_bun = r.get("bun",""), r.get("ji",""), r.get("platGbCd","")
    print(f"  PNU={r['pnu19']}  len={len(r['pnu19'])}  bun={raw_bun[0]}  ji={raw_bun[1]}  platGb={raw_bun[2]}")

# 3) 교집합 확인
lsmd_pnus = set(gdf[gdf["PNU"].str[:10]=="4113510900"]["PNU"].astype(str))
bld_pnus  = set(df["pnu19"])
common    = lsmd_pnus & bld_pnus
print(f"\n=== 교집합 ===")
print(f"  LSMD PNU 수: {len(lsmd_pnus)}")
print(f"  건축물 PNU 수: {len(bld_pnus)}")
print(f"  공통 PNU: {len(common)}")

# 4) 불일치 샘플 비교 (같은 지번을 찾아보기)
# LSMD JIBUN "30 번" → bun=30 에 해당하는 것 찾기
lsmd_30 = gdf[gdf["PNU"].str[:10]=="4113510900"][
    gdf["JIBUN"].str.strip().str.startswith("30")
]
if len(lsmd_30):
    print(f"\n=== LSMD 지번 '30...' 필지 ===")
    for _, r in lsmd_30.head(5).iterrows():
        print(f"  PNU={r['PNU']}  JIBUN={r['JIBUN']}")

bld_30 = df[df["bun"].astype(str).str.strip() == "0030"]
if len(bld_30):
    print(f"\n=== 건축물 bun='0030' ===")
    for _, r in bld_30.head(5).iterrows():
        print(f"  PNU={r['pnu19']}  bun={r['bun']}  ji={r['ji']}")
