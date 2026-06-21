import pandas as pd
import os

base = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
census = os.path.join(base, "data", "raw", "census")

files = {
    "서울_총인구":     os.path.join(census, "11_2024년_인구총괄(총인구).csv"),
    "경기_총인구":     os.path.join(census, "31_2024년_인구총괄(총인구).csv"),
    "서울_총괄사업체": os.path.join(census, "11_2023년_산업분류별(10차_대분류)_총괄사업체수.csv"),
    "경기_총괄사업체": os.path.join(census, "31_2023년_산업분류별(10차_대분류)_총괄사업체수.csv"),
    "서울_총괄종사자": os.path.join(census, "11_2023년_산업분류별(10차_대분류)_총괄종사자수.csv"),
    "경기_총괄종사자": os.path.join(census, "31_2023년_산업분류별(10차_대분류)_총괄종사자수.csv"),
}

for name, path in files.items():
    df = pd.read_csv(path, header=None, names=["year", "code", "var", "val"],
                     encoding="utf-8")
    df["code"] = df["code"].astype(str).str.zfill(14)
    na_cnt = (df["val"].astype(str).str.strip().str.upper() == "N/A").sum()
    print(f"[{name}]")
    print(f"  행수={len(df)}, 고유코드={df['code'].nunique()}, 고유변수={df['var'].nunique()}")
    print(f"  변수목록: {sorted(df['var'].unique())}")
    print(f"  N/A 개수: {na_cnt}")
    print()
