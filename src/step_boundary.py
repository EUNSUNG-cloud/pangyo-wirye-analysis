"""
구역계 v6: CRS 정확 처리 + WGS84 위경도 bbox 필터
  - LSMD 5186→5179 변환 후 중심을 4326으로 변환해 위경도로 비교
  - 위례 bbox [37.460~37.482N, 127.138~127.156E] (트랜짓몰·위례중앙·비즈밸리)
    → 양지동·은행동(위도~37.44) 자동 제외
"""
import os, json, pickle, warnings
import numpy as np, pandas as pd
import geopandas as gpd
from shapely.ops import unary_union
from pyproj import Transformer
warnings.filterwarnings("ignore")

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
RAW  = os.path.join(BASE, "data", "raw")
BLD  = os.path.join(BASE, "data", "processed", "buildings")
PROC = os.path.join(BASE, "data", "processed")
DOCS = os.path.join(BASE, "docs", "data")

NON_RESI = {"업무시설","교육연구시설","판매시설","판매.영업.처리시설",
            "제1종근린생활시설","제2종근린생활시설","문화및집회시설",
            "의료시설","숙박시설","위락시설","창고시설","운수시설","자동차관련시설"}
RESI     = {"공동주택","단독주택"}
SAN_MAP  = {"0":"1","1":"2","2":"0"}

def build_pnu(row):
    sg  = str(row.get("sigunguCd","")).zfill(5)
    bj  = str(row.get("bjdongCd","")).zfill(5)
    san = SAN_MAP.get(str(row.get("platGbCd","0")).strip(), "1")
    bun = str(row.get("bun","0")).strip().zfill(4)
    ji  = str(row.get("ji","0")).strip().zfill(4)
    return sg + bj + san + bun + ji

# ── 1. 건축물대장 ─────────────────────────────────────────────────
print("=== 1. 건축물대장 로드 ===")
BLD_FILES = {
    "pangyo": ["판교_삼평동_title.json"],
    "wirye":  ["위례_창곡동_title.json","위례_복정동_title.json","위례_송파_title.json"],
}
bld_by_area = {}
for area, fnames in BLD_FILES.items():
    parts = []
    for fn in fnames:
        with open(os.path.join(BLD, fn), encoding="utf-8") as f:
            recs = json.load(f)
        parts.append(pd.DataFrame(recs))
    bld = pd.concat(parts, ignore_index=True)
    bld["totArea"] = pd.to_numeric(bld.get("totArea",0), errors="coerce").fillna(0)
    bld["pnu19"]   = bld.apply(build_pnu, axis=1)
    agg = (bld.sort_values("totArea",ascending=False)
              .groupby("pnu19")
              .agg(mainPurps=("mainPurpsCdNm","first"),
                   totArea_sum=("totArea","sum"),
                   bld_cnt=("pnu19","count"))
              .reset_index())
    bld_by_area[area] = agg
    print(f"  {area}: {len(bld)}건 → 유니크PNU {len(agg)}개")

# ── 2. LSMD 로드 + CRS 변환 + WGS84 bbox 필터 ─────────────────
print("\n=== 2. LSMD 로드 + WGS84 위경도 bbox 필터 ===")

# 판교: 삼평동 동코드 필터만
# 위례: 수정구+송파구 전체 로드 후 WGS84 bbox로 필터 (중원구 등 자동 제외)
LSMD_CFG = {
    "pangyo": {
        "files": [(os.path.join(RAW,"lsmd_bundang","LSMD_CONT_LDREG_41135_202606.shp"),
                   ["4113510900"])],
        "bbox_wgs84": None,   # 동코드 필터만
    },
    "wirye": {
        "files": [(os.path.join(RAW,"lsmd_sujeong","LSMD_CONT_LDREG_41131_202606.shp"), None),
                  (os.path.join(RAW,"lsmd_songpa", "LSMD_CONT_LDREG_11710_202606.shp"), None)],
        # 위례신도시 핵심 (트랜짓몰·위례중앙광장·비즈밸리)
        # 양지동·은행동(위도~37.44) → lat_min=37.460으로 자동 제외
        "bbox_wgs84": (37.460, 37.482, 127.138, 127.156),  # lat_min, lat_max, lon_min, lon_max
    },
}

gdfs = {}
for area, cfg in LSMD_CFG.items():
    parts = []
    for shp, codes in cfg["files"]:
        g = gpd.read_file(shp)
        print(f"  {os.path.basename(shp)} 원본 CRS: {g.crs.to_epsg()}")
        g = g.to_crs(5179)   # 5186 → 5179 (또는 5179는 그대로)
        if codes:
            g = g[g["PNU"].str[:10].isin(codes)].copy()
        parts.append(g)

    gdf = pd.concat(parts, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, crs=5179)
    n_before = len(gdf)

    bbox = cfg["bbox_wgs84"]
    if bbox is not None:
        lat_min, lat_max, lon_min, lon_max = bbox

        # ★ CRS 정확 처리: 5179 중심 → 4326(위경도)로 변환 후 비교 ★
        centroids_5179 = gpd.GeoSeries(gdf.geometry.centroid, crs=5179)
        centroids_4326 = centroids_5179.to_crs(4326)
        clat = centroids_4326.y   # 위도
        clon = centroids_4326.x   # 경도

        mask = ((clat >= lat_min) & (clat <= lat_max) &
                (clon >= lon_min) & (clon <= lon_max))
        gdf = gdf[mask].copy()

        # 필터 결과 위경도 범위 출력 (검증)
        print(f"  [{area}] 로드={n_before} → bbox필터={len(gdf)}")
        if len(gdf):
            print(f"    위경도 범위: lat {clat[mask].min():.4f}~{clat[mask].max():.4f}N"
                  f"  lon {clon[mask].min():.4f}~{clon[mask].max():.4f}E")
    else:
        print(f"  [{area}] 동코드 필터={n_before}")

    gdf["area_m2"] = gdf.geometry.area
    gdf["PNU"]     = gdf["PNU"].astype(str)

    # PNU 정확 조인
    agg = bld_by_area[area]
    gdf = gdf.merge(agg, left_on="PNU", right_on="pnu19", how="left")
    matched = gdf["mainPurps"].notna().sum()

    gdf["purp_class"] = "empty"
    gdf.loc[gdf["mainPurps"].isin(RESI),     "purp_class"] = "residential"
    gdf.loc[gdf["mainPurps"].isin(NON_RESI), "purp_class"] = "non_resi"

    n_nr = (gdf.purp_class=="non_resi").sum()
    n_rs = (gdf.purp_class=="residential").sum()
    n_em = (gdf.purp_class=="empty").sum()
    print(f"    PNU매칭={matched}({matched/max(len(gdf),1)*100:.0f}%)"
          f"  비주거={n_nr}  주거={n_rs}  빈={n_em}")

    gdfs[area] = gdf

# ── 3. 구역계 dissolve ─────────────────────────────────────────
print("\n=== 3. 구역계 정의 ===")
BUFFER_M = 60
MIN_AREA = 5000
boundaries = {}
tf_bw = Transformer.from_crs(5179, 4326, always_xy=True)

for area, gdf in gdfs.items():
    non_resi = gdf[gdf["purp_class"]=="non_resi"]
    empty    = gdf[gdf["purp_class"]=="empty"]
    print(f"\n  [{area}] 비주거={len(non_resi)}({non_resi.area_m2.sum()/1e4:.1f}ha)"
          f"  빈={len(empty)}")

    if len(non_resi) == 0:
        print("    비주거 없음 → 전체 dissolve")
        main_poly = unary_union(gdf.geometry.values)
    else:
        nr_buf  = unary_union(non_resi.geometry.values).buffer(BUFFER_M)
        inc_emp = empty[empty.geometry.intersects(nr_buf)]
        merged  = unary_union(
            gpd.GeoDataFrame(pd.concat([non_resi,inc_emp],ignore_index=True),
                             crs=5179).geometry.values)
        polys = ([p for p in merged.geoms if p.area>=MIN_AREA]
                 if merged.geom_type=="MultiPolygon"
                 else ([merged] if merged.area>=MIN_AREA else [merged]))
        print(f"    버퍼흡수 빈={len(inc_emp)} → {len(polys)}군집")
        main_poly = unary_union(polys)

    within  = gdf[gdf.geometry.intersects(main_poly.buffer(-1))].copy()
    n_tot   = len(within)
    n_nr    = int((within.purp_class=="non_resi").sum())
    n_rs    = int((within.purp_class=="residential").sum())
    n_em    = int((within.purp_class=="empty").sum())
    area_ha = main_poly.area / 1e4
    off_a   = float(within[within["mainPurps"]=="업무시설"]["totArea_sum"].sum())
    vac_rt  = n_em / max(n_tot,1) * 100

    # 구역 중심 위경도
    c = main_poly.centroid
    clon, clat = tf_bw.transform(c.x, c.y)

    # 구역 bbox 위경도
    b = main_poly.bounds
    b1lon, b1lat = tf_bw.transform(b[0], b[1])
    b2lon, b2lat = tf_bw.transform(b[2], b[3])

    print(f"    구역: {area_ha:.1f}ha  필지={n_tot}"
          f" (비주거={n_nr} 주거={n_rs} 빈={n_em})")
    print(f"    중심: {clat:.4f}N, {clon:.4f}E")
    print(f"    bbox: {b1lat:.4f}~{b2lat:.4f}N / {b1lon:.4f}~{b2lon:.4f}E")
    print(f"    공지율={vac_rt:.1f}%  업무연면적={off_a:,.0f}m2")

    zone_gdf = gpd.GeoDataFrame(geometry=[main_poly], crs=5179)
    zone_gdf.to_file(os.path.join(PROC, f"{area}_zone.gpkg"), driver="GPKG")
    zone_gdf.to_crs(4326).to_file(os.path.join(DOCS, f"{area}.geojson"),
                                   driver="GeoJSON")
    within[["PNU","JIBUN","purp_class","mainPurps","totArea_sum","area_m2","geometry"]
           ].to_file(os.path.join(PROC, f"{area}_parcels.gpkg"), driver="GPKG")

    boundaries[area] = dict(
        area_ha=round(area_ha,1), n_parcel=n_tot,
        n_non_resi=n_nr, n_resi=n_rs, n_empty=n_em,
        empty_rate=round(vac_rt,1),
        office_area_m2=round(off_a),
        center_lat=round(clat,4), center_lon=round(clon,4),
    )

print("\n=== 비교표 ===")
for area, b in boundaries.items():
    print(f"  {area}: {b['area_ha']}ha, {b['n_parcel']}필지,"
          f" 비주거={b['n_non_resi']} 빈={b['n_empty']}({b['empty_rate']}%),"
          f" 업무연면적={b['office_area_m2']:,}m2,"
          f" 중심={b['center_lat']}N,{b['center_lon']}E")

with open(os.path.join(PROC,"boundaries.pkl"),"wb") as f:
    pickle.dump({"gdfs":gdfs,"boundaries":boundaries}, f)
print("  boundaries.pkl 저장")
