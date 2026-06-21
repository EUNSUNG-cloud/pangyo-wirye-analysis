"""bbox 안 필지의 실제 법정동 코드 진단"""
import os, geopandas as gpd, pandas as pd
import warnings; warnings.filterwarnings("ignore")

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
RAW  = os.path.join(BASE, "data", "raw")

LAT_MIN, LAT_MAX = 37.460, 37.482
LON_MIN, LON_MAX = 127.138, 127.156

for shp_name, shp in [
    ("수정구", os.path.join(RAW,"lsmd_sujeong","LSMD_CONT_LDREG_41131_202606.shp")),
    ("송파구", os.path.join(RAW,"lsmd_songpa", "LSMD_CONT_LDREG_11710_202606.shp")),
]:
    g = gpd.read_file(shp).to_crs(5179)
    cent_4326 = gpd.GeoSeries(g.geometry.centroid, crs=5179).to_crs(4326)
    mask = ((cent_4326.y >= LAT_MIN) & (cent_4326.y <= LAT_MAX) &
            (cent_4326.x >= LON_MIN) & (cent_4326.x <= LON_MAX))
    sub = g[mask].copy()
    sub["dong_cd"] = sub["PNU"].str[:10]

    print(f"\n=== {shp_name} bbox 내 필지 {len(sub)}개 ===")
    print("  PNU 앞10자리(법정동) 분포:")
    print(sub["dong_cd"].value_counts().head(15).to_string())

    print("  JIBUN 샘플 (필지 중심 위경도 포함):")
    sub2 = sub.copy()
    sub2["lat"] = cent_4326.y[mask].values
    sub2["lon"] = cent_4326.x[mask].values
    for _, r in sub2.head(5).iterrows():
        print(f"    PNU={r['PNU']}  JIBUN={r['JIBUN']}  {r['lat']:.4f}N,{r['lon']:.4f}E")
