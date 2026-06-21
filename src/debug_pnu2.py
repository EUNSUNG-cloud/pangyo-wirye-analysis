"""PNU 상세 진단 — platGbCd 분포 + 대지 파셀 여부 + platPlc 파싱"""
import os, json, re, geopandas as gpd, pandas as pd
import warnings; warnings.filterwarnings("ignore")

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
RAW  = os.path.join(BASE, "data", "raw")
BLD  = os.path.join(BASE, "data", "processed", "buildings")

CHECKS = [
    ("pangyo", "lsmd_bundang", "LSMD_CONT_LDREG_41135_202606.shp",
     ["4113510900"], "판교_삼평동_title.json"),
    ("wirye_sj", "lsmd_sujeong", "LSMD_CONT_LDREG_41131_202606.shp",
     ["4113110600"], "위례_창곡동_title.json"),
    ("wirye_sp", "lsmd_songpa",  "LSMD_CONT_LDREG_11710_202606.shp",
     ["1171011400"], "위례_장지동_title.json"),
]

for area, folder, fname, codes, bld_fname in CHECKS:
    shp = os.path.join(RAW, folder, fname)
    gdf = gpd.read_file(shp)
    mask = gdf["PNU"].str[:10].isin(codes)
    sub  = gdf[mask].copy()

    # platGbCd 분포 (PNU[10])
    sub["platGb"] = sub["PNU"].str[10]
    print(f"\n=== {area} - LSMD ({len(sub)}parcels) ===")
    print(f"  platGbCd 분포: {sub['platGb'].value_counts().to_dict()}")

    # 0(대지) 파셀 존재하면 샘플
    dae = sub[sub["platGb"] == "0"]
    if len(dae):
        print(f"  대지(0) 파셀 {len(dae)}개 샘플:")
        for _, r in dae.head(3).iterrows():
            print(f"    PNU={r['PNU']}  JIBUN={r['JIBUN']}")
    else:
        print(f"  대지(0) 파셀 없음. 임야(1) JIBUN 샘플:")
        for _, r in sub.head(3).iterrows():
            print(f"    PNU={r['PNU']}  JIBUN={r['JIBUN']}")

    # 건축물 platPlc 파싱 → 본번/부번 추출
    with open(os.path.join(BLD, bld_fname), encoding="utf-8") as f:
        bld = json.load(f)
    df = pd.DataFrame(bld)

    # platPlc 예시
    print(f"\n  건축물 platPlc 샘플:")
    for v in df["platPlc"].dropna().head(5):
        print(f"    {v}")

    # platPlc에서 본번-부번 파싱
    def parse_lot(plc):
        m = re.search(r"(\d+)(?:-(\d+))?번지?", str(plc))
        if m:
            return int(m.group(1)), int(m.group(2) or 0)
        return None, None

    df[["plc_bun","plc_ji"]] = df["platPlc"].apply(
        lambda x: pd.Series(parse_lot(x)))
    # bun 숫자 비교
    df["api_bun"] = pd.to_numeric(df["bun"], errors="coerce")
    sub["jibun_bun"] = sub["JIBUN"].str.extract(r"(\d+)")[0].astype(float)

    bld_buns  = set(df["api_bun"].dropna().astype(int))
    lsmd_buns = set(sub["jibun_bun"].dropna().astype(int))
    overlap   = bld_buns & lsmd_buns
    print(f"\n  건축물 본번 범위: {min(bld_buns)}~{max(bld_buns)}  ({len(bld_buns)}개)")
    print(f"  LSMD 본번 범위:  {min(lsmd_buns)}~{max(lsmd_buns)}  ({len(lsmd_buns)}개)")
    print(f"  교집합 본번: {len(overlap)}개  {sorted(overlap)[:10]}")
