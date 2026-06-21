"""PNU 불일치 심층 진단 - 미매칭 필지가 LSMD 전체 파일에 있는지 확인"""
import os, json, geopandas as gpd, pandas as pd
import warnings; warnings.filterwarnings("ignore")

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
RAW  = os.path.join(BASE, "data", "raw")
BLD  = os.path.join(BASE, "data", "processed", "buildings")

SAN_MAP = {"0":"1","1":"2","2":"0"}

def build_pnu(row):
    sg  = str(row.get("sigunguCd","")).zfill(5)
    bj  = str(row.get("bjdongCd","")).zfill(5)
    san = SAN_MAP.get(str(row.get("platGbCd","0")).strip(), "1")
    bun = str(row.get("bun","0")).strip().zfill(4)
    ji  = str(row.get("ji","0")).strip().zfill(4)
    return sg + bj + san + bun + ji

# 건축물대장 PNU 집합
with open(os.path.join(BLD,"판교_삼평동_title.json"), encoding="utf-8") as f:
    bld = json.load(f)
df = pd.DataFrame(bld)
df["pnu19"] = df.apply(build_pnu, axis=1)
bld_pnus = set(df["pnu19"])

# LSMD 전체 분당구 로드
shp = os.path.join(RAW,"lsmd_bundang","LSMD_CONT_LDREG_41135_202606.shp")
full = gpd.read_file(shp)
full_pnus = set(full["PNU"].astype(str))

# 교집합
matched    = bld_pnus & full_pnus
unmatched  = bld_pnus - full_pnus
print(f"=== 판교 PNU 전체파일 대조 ===")
print(f"  건축물대장 고유PNU: {len(bld_pnus)}")
print(f"  LSMD 전체(분당구) PNU: {len(full_pnus)}")
print(f"  매칭: {len(matched)} / {len(bld_pnus)}  ({len(matched)/len(bld_pnus)*100:.1f}%)")
print(f"  미매칭 건축물PNU: {len(unmatched)}")

# 미매칭 PNU의 앞 10자 분포
print(f"\n  미매칭 PNU 앞10자 분포 (동코드):")
from collections import Counter
pre10 = Counter(p[:10] for p in unmatched)
for k,v in pre10.most_common(10):
    print(f"    {k}: {v}개")

# 미매칭 PNU 상세 샘플
print(f"\n  미매칭 PNU 샘플 5개:")
for p in sorted(unmatched)[:5]:
    row = df[df["pnu19"]==p].iloc[0]
    print(f"    {p}  platPlc={row.get('platPlc','?')}"
          f"  platGbCd={row.get('platGbCd','?')}"
          f"  bun={row.get('bun','?')}  ji={row.get('ji','?')}")

# LSMD에서 해당 동코드 PNU 앞10자 분포
print(f"\n  LSMD 전체에서 삼평동 관련 PNU 앞10자:")
full["pre10"] = full["PNU"].str[:10]
samp_dong = full[full["pre10"].str.startswith("411351090")]
print(f"  4113510900x 필지: {len(samp_dong)}")
# san여부 분포
samp_dong = samp_dong.copy()
samp_dong["san"] = samp_dong["PNU"].str[10]
print(f"  산여부 분포: {samp_dong['san'].value_counts().to_dict()}")

# 미매칭 PNU에서 bun이 낮은 필지 - 혹시 다른 동코드로 등록?
print(f"\n  미매칭 건물 platPlc 샘플:")
unmatch_df = df[df["pnu19"].isin(unmatched)]
for _, r in unmatch_df.head(10).iterrows():
    print(f"    platPlc={r.get('platPlc','?')}  pnu={r['pnu19']}")
