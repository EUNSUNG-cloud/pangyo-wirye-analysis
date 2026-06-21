"""
단계 1-3: 집계구 경계 + 인구·종사자·사업체 CSV 조인 및 검증
출력: data/processed/oa_joined.gpkg  (EPSG:5179)
      docs/data/oa_joined.geojson    (EPSG:4326, 시각화용)
"""
import os, geopandas as gpd, pandas as pd, warnings
warnings.filterwarnings("ignore")

BASE   = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
RAW    = os.path.join(BASE, "data", "raw")
PROC   = os.path.join(BASE, "data", "processed")
DOCS   = os.path.join(BASE, "docs", "data")
CENSUS = os.path.join(RAW, "census")
os.makedirs(PROC, exist_ok=True)
os.makedirs(DOCS, exist_ok=True)

# ── 1. 집계구 경계 합치기 ────────────────────────────────────────
print("=== 1. 집계구 경계 로드 ===")
oa11 = gpd.read_file(os.path.join(RAW, "bnd_oa_11_2025_2Q", "bnd_oa_11_2025_2Q.shp"))
oa31 = gpd.read_file(os.path.join(RAW, "bnd_oa_31_2025_2Q", "bnd_oa_31_2025_2Q.shp"))
oa11["sido"] = "서울"
oa31["sido"] = "경기"
oa = pd.concat([oa11, oa31], ignore_index=True)
oa = gpd.GeoDataFrame(oa, crs=5179)
oa["TOT_OA_CD"] = oa["TOT_OA_CD"].astype(str).str.zfill(14)
print(f"  서울 {len(oa11):,}개 + 경기 {len(oa31):,}개 = 합계 {len(oa):,}개")
print(f"  CRS: {oa.crs.to_epsg()}")


# ── 2. CSV 로드 헬퍼 ─────────────────────────────────────────────
def load_csv(path):
    df = pd.read_csv(path, header=None, names=["year","code","var","val"],
                     encoding="utf-8")
    df["code"] = df["code"].astype(str).str.zfill(14)
    return df

print("\n=== 2. CSV 로드 ===")

# 인구 (to_in_001 = 총인구)
pop = pd.concat([
    load_csv(os.path.join(CENSUS, "11_2024년_인구총괄(총인구).csv")),
    load_csv(os.path.join(CENSUS, "31_2024년_인구총괄(총인구).csv")),
], ignore_index=True)
pop_total = pop[pop["var"] == "to_in_001"][["code","val"]].copy()
pop_total.columns = ["TOT_OA_CD", "pop_tot"]
pop_total["pop_tot"] = pd.to_numeric(pop_total["pop_tot"], errors="coerce")
print(f"  인구 총인구 행수: {len(pop_total):,}  |  합계: {pop_total['pop_tot'].sum():,.0f}")

# 사업체 (to_fa_010)
biz = pd.concat([
    load_csv(os.path.join(CENSUS, "11_2023년_산업분류별(10차_대분류)_총괄사업체수.csv")),
    load_csv(os.path.join(CENSUS, "31_2023년_산업분류별(10차_대분류)_총괄사업체수.csv")),
], ignore_index=True)
biz = biz[["code","val"]].copy()
biz.columns = ["TOT_OA_CD", "biz_tot"]
biz["biz_tot"] = pd.to_numeric(biz["biz_tot"], errors="coerce")
print(f"  사업체 행수: {len(biz):,}  |  합계: {biz['biz_tot'].sum():,.0f}")

# 종사자 (to_em_020)
emp = pd.concat([
    load_csv(os.path.join(CENSUS, "11_2023년_산업분류별(10차_대분류)_총괄종사자수.csv")),
    load_csv(os.path.join(CENSUS, "31_2023년_산업분류별(10차_대분류)_총괄종사자수.csv")),
], ignore_index=True)
emp = emp[["code","val"]].copy()
emp.columns = ["TOT_OA_CD", "emp_tot"]
emp["emp_tot"] = pd.to_numeric(emp["emp_tot"], errors="coerce")
print(f"  종사자 행수: {len(emp):,}  |  합계: {emp['emp_tot'].sum():,.0f}")


# ── 3. 경계에 조인 ───────────────────────────────────────────────
print("\n=== 3. 조인 ===")
oa = oa.merge(pop_total, on="TOT_OA_CD", how="left")
oa = oa.merge(biz,       on="TOT_OA_CD", how="left")
oa = oa.merge(emp,       on="TOT_OA_CD", how="left")

# 검증
total = len(oa)
no_pop = oa["pop_tot"].isna().sum()
no_biz = oa["biz_tot"].isna().sum()
no_emp = oa["emp_tot"].isna().sum()

print(f"  전체 집계구: {total:,}")
print(f"  인구 미매칭: {no_pop:,}  ({no_pop/total*100:.1f}%)")
print(f"  사업체 미매칭: {no_biz:,}  ({no_biz/total*100:.1f}%)")
print(f"  종사자 미매칭: {no_emp:,}  ({no_emp/total*100:.1f}%)")
print(f"  조인 후 인구 합계:  {oa['pop_tot'].sum():,.0f}")
print(f"  조인 후 사업체 합계: {oa['biz_tot'].sum():,.0f}")
print(f"  조인 후 종사자 합계: {oa['emp_tot'].sum():,.0f}")

# NaN → 0 처리 (마스킹된 N/A 셀은 이미 to_numeric에서 NaN)
oa["pop_tot"] = oa["pop_tot"].fillna(0).astype(int)
oa["biz_tot"] = oa["biz_tot"].fillna(0).astype(int)
oa["emp_tot"] = oa["emp_tot"].fillna(0).astype(int)

# 샘플 출력
print("\n  샘플 5행:")
sample_cols = ["TOT_OA_CD","ADM_CD","sido","pop_tot","biz_tot","emp_tot"]
print(oa[sample_cols].head(5).to_string(index=False))

# 값이 0인 집계구 (마스킹·무인구 포함 가능성)
zero_pop = (oa["pop_tot"] == 0).sum()
zero_emp = (oa["emp_tot"] == 0).sum()
print(f"\n  인구=0 집계구: {zero_pop:,}  (무인구 지역 + 마스킹 포함)")
print(f"  종사자=0 집계구: {zero_emp:,}")


# ── 4. 저장 ─────────────────────────────────────────────────────
print("\n=== 4. 저장 ===")
# GeoPackage (5179, 분석용)
oa.to_file(os.path.join(PROC, "oa_joined.gpkg"), driver="GPKG", layer="oa")
print(f"  저장: data/processed/oa_joined.gpkg")

# GeoJSON (4326, 웹용) — 용량 줄이기 위해 geometry 단순화
oa_wgs = oa.to_crs(4326)
oa_wgs.to_file(os.path.join(DOCS, "oa_joined.geojson"), driver="GeoJSON")
print(f"  저장: docs/data/oa_joined.geojson")
print("완료.")
