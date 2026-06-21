"""
구역계 v5: 동코드 PNU 정확 매칭 + 지역별 bbox 필터
  - 판교: 삼평동(4113510900) 전체 (동코드가 곧 테크노밸리)
  - 위례: 창곡동(4113110600) + 장지동(1171011400)
      bbox [37.455~37.500N, 127.130~127.175E] 로 위례신도시 구간만
      → 거여동/위례동 북측(위도>37.500) 및 중원구(동코드 이미 제외) 자동 제외
  - bun/ji cross-dong fallback 완전 제거
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

tf_fw = Transformer.from_crs("EPSG:4326","EPSG:5179", always_xy=True)
tf_bw = Transformer.from_crs("EPSG:5179","EPSG:4326", always_xy=True)

def build_pnu(row):
    sg  = str(row.get("sigunguCd","")).zfill(5)
    bj  = str(row.get("bjdongCd","")).zfill(5)
    san = SAN_MAP.get(str(row.get("platGbCd","0")).strip(), "1")
    bun = str(row.get("bun","0")).strip().zfill(4)
    ji  = str(row.get("ji","0")).strip().zfill(4)
    return sg + bj + san + bun + ji

# 위례 bbox (WGS84) → 5179 변환
W_SW = tf_fw.transform(127.130, 37.455)   # (x_min, y_min)
W_NE = tf_fw.transform(127.175, 37.485)   # (x_max, y_max) — 북단 37.485로 제한
print(f"위례 bbox 5179: SW={W_SW[0]:.0f},{W_SW[1]:.0f}  NE={W_NE[0]:.0f},{W_NE[1]:.0f}")

# ── 1. 건축물대장 ─────────────────────────────────────────────────
print("\n=== 1. 건축물대장 로드 ===")
BLD_FILES = {
    "pangyo": ["판교_삼평동_title.json"],
    "wirye":  ["위례_창곡동_title.json","위례_장지동_title.json"],
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
    print(f"  {area}: {len(bld)}건 → 유니크PNU {len(agg)}개  샘플: {bld['pnu19'].iloc[0]}")

# ── 2. LSMD 로드 + 동코드 필터 + bbox/범위 필터 ─────────────────
print("\n=== 2. LSMD 로드 + 공간 필터 ===")
LSMD_CFG = {
    "pangyo": [(os.path.join(RAW,"lsmd_bundang","LSMD_CONT_LDREG_41135_202606.shp"),
                ["4113510900"])],   # 삼평동 전체
    "wirye":  [(os.path.join(RAW,"lsmd_sujeong","LSMD_CONT_LDREG_41131_202606.shp"),
                ["4113110600"]),    # 창곡동 (수정구, 중원구 자동 제외)
               (os.path.join(RAW,"lsmd_songpa","LSMD_CONT_LDREG_11710_202606.shp"),
                ["1171011400"])],   # 장지동 (북측 bbox로 제외)
}

gdfs = {}
for area, cfg in LSMD_CFG.items():
    parts = []
    for shp, codes in cfg:
        g = gpd.read_file(shp).to_crs(5179)
        g = g[g["PNU"].str[:10].isin(codes)].copy()
        parts.append(g)
    gdf = pd.concat(parts, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, crs=5179)
    n_before = len(gdf)

    # bbox 필터 (위례만 적용, 판교는 삼평동=테크노밸리 전체)
    if area == "wirye":
        cx = gdf.geometry.centroid.x
        cy = gdf.geometry.centroid.y
        mask = ((cx >= W_SW[0]) & (cx <= W_NE[0]) &
                (cy >= W_SW[1]) & (cy <= W_NE[1]))
        gdf = gdf[mask].copy()
        print(f"  [wirye] 동코드필터={n_before} → bbox필터={len(gdf)}")
    else:
        print(f"  [pangyo] 삼평동 전체={n_before}")

    gdf["area_m2"] = gdf.geometry.area
    gdf["PNU"]     = gdf["PNU"].astype(str)

    # PNU 19자리 정확 조인
    agg = bld_by_area[area]
    gdf = gdf.merge(agg, left_on="PNU", right_on="pnu19", how="left")
    matched = gdf["mainPurps"].notna().sum()

    gdf["purp_class"] = "empty"
    gdf.loc[gdf["mainPurps"].isin(RESI),     "purp_class"] = "residential"
    gdf.loc[gdf["mainPurps"].isin(NON_RESI), "purp_class"] = "non_resi"
    n_nr = (gdf.purp_class=="non_resi").sum()
    n_rs = (gdf.purp_class=="residential").sum()
    n_em = (gdf.purp_class=="empty").sum()

    print(f"    PNU매칭={matched}({matched/len(gdf)*100:.0f}%)"
          f"  비주거={n_nr}  주거={n_rs}  빈={n_em}")

    # 필지 중심 WGS84 출력 (확인용)
    sample = gdf.iloc[:5]
    sx = sample.geometry.centroid.x.values
    sy = sample.geometry.centroid.y.values
    for i in range(min(3,len(sample))):
        lon, lat = tf_bw.transform(sx[i], sy[i])
        pclass = sample.iloc[i]["purp_class"]
        purp   = str(sample.iloc[i]["mainPurps"])[:10] if pd.notna(sample.iloc[i]["mainPurps"]) else "empty"
        print(f"      샘플 {i}: {lat:.4f}N,{lon:.4f}E [{pclass}/{purp}]")

    gdfs[area] = gdf

# ── 3. 구역계 dissolve ─────────────────────────────────────────
print("\n=== 3. 구역계 ===")
BUFFER_M = 60
MIN_AREA = 5000
boundaries = {}

for area, gdf in gdfs.items():
    non_resi = gdf[gdf["purp_class"]=="non_resi"]
    empty    = gdf[gdf["purp_class"]=="empty"]
    print(f"\n  [{area}] 비주거={len(non_resi)}개({non_resi.area_m2.sum()/1e4:.1f}ha)"
          f"  빈={len(empty)}개")

    if len(non_resi) == 0:
        main_poly = unary_union(gdf.geometry.values)
        print(f"    비주거 없음 → 전체 dissolve")
    else:
        nr_buf  = unary_union(non_resi.geometry.values).buffer(BUFFER_M)
        inc_emp = empty[empty.geometry.intersects(nr_buf)]
        merged  = unary_union(
            gpd.GeoDataFrame(pd.concat([non_resi,inc_emp],ignore_index=True),crs=5179).geometry.values)
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
    area_ha = main_poly.area/1e4
    off_a   = float(within[within["mainPurps"]=="업무시설"]["totArea_sum"].sum())
    vac_rt  = n_em/max(n_tot,1)*100
    emp_rt  = n_nr/max(n_tot,1)*100

    c     = main_poly.centroid
    clon, clat = tf_bw.transform(c.x, c.y)

    # 구역계 바운드 출력
    b = main_poly.bounds
    blon1,blat1 = tf_bw.transform(b[0],b[1])
    blon2,blat2 = tf_bw.transform(b[2],b[3])

    print(f"    구역: {area_ha:.1f}ha  필지={n_tot}(비주거={n_nr} 주거={n_rs} 빈={n_em})")
    print(f"    중심: {clat:.4f}N, {clon:.4f}E")
    print(f"    bbox: {blat1:.4f}~{blat2:.4f}N / {blon1:.4f}~{blon2:.4f}E")
    print(f"    공지율={vac_rt:.1f}%  비주거율={emp_rt:.1f}%  업무연면적={off_a:,.0f}m2")

    zone_gdf = gpd.GeoDataFrame(geometry=[main_poly], crs=5179)
    zone_gdf.to_file(os.path.join(PROC,f"{area}_zone.gpkg"), driver="GPKG")
    zone_gdf.to_crs(4326).to_file(os.path.join(DOCS,f"{area}.geojson"), driver="GeoJSON")
    within[["PNU","JIBUN","purp_class","mainPurps","totArea_sum","area_m2","geometry"]
           ].to_file(os.path.join(PROC,f"{area}_parcels.gpkg"), driver="GPKG")

    boundaries[area] = dict(
        area_ha=round(area_ha,1), n_parcel=n_tot,
        n_non_resi=n_nr, n_resi=n_rs, n_empty=n_em,
        non_resi_pct=round(emp_rt,1),
        empty_rate=round(vac_rt,1),
        office_area_m2=round(off_a),
        center_lat=round(clat,4), center_lon=round(clon,4),
    )

print("\n=== 비교표 ===")
for area,b in boundaries.items():
    print(f"  {area}: {b['area_ha']}ha, {b['n_parcel']}필지,"
          f" 비주거{b['n_non_resi']}(빈{b['n_empty']}/{b['empty_rate']}%),"
          f" 업무연면적={b['office_area_m2']:,}m2, 중심={b['center_lat']}N,{b['center_lon']}E")

with open(os.path.join(PROC,"boundaries.pkl"),"wb") as f:
    pickle.dump({"gdfs":gdfs,"boundaries":boundaries}, f)
print("  boundaries.pkl 저장")
