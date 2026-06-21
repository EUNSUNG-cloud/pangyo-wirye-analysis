"""필지 GeoJSON 내보내기 (EPSG:4326, 속성 포함)"""
import os, geopandas as gpd, pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
PROC = os.path.join(BASE, "data", "processed")
DOCS = os.path.join(BASE, "docs", "data")

for area in ["pangyo","wirye"]:
    gdf = gpd.read_file(os.path.join(PROC, f"{area}_parcels.gpkg"))
    gdf["totArea_sum"] = pd.to_numeric(gdf.get("totArea_sum",0), errors="coerce").fillna(0)
    gdf["area_m2"]     = pd.to_numeric(gdf.get("area_m2",1),    errors="coerce").replace(0,np.nan)
    gdf["far_pct"]     = (gdf["totArea_sum"] / gdf["area_m2"] * 100).fillna(0).round(0).clip(0,2000).astype(int)
    gdf["mainPurps"]   = gdf["mainPurps"].fillna("정보없음")
    gdf["totArea_sum"] = gdf["totArea_sum"].round(0).astype(int)
    gdf["area_m2"]     = gdf["area_m2"].fillna(0).round(0).astype(int)

    out = gdf[["PNU","JIBUN","purp_class","mainPurps",
               "totArea_sum","area_m2","far_pct","geometry"]].copy()
    out.geometry = out.geometry.simplify(5, preserve_topology=True)
    path = os.path.join(DOCS, f"{area}_parcels.geojson")
    out.to_crs(4326).to_file(path, driver="GeoJSON")

    size_kb = os.path.getsize(path) / 1024
    print(f"{area}: {len(out)}필지, {size_kb:.0f}KB → {path}")
