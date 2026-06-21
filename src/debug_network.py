import os, pandas as pd

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
NET  = os.path.join(BASE, "data", "raw", "subway", "network")

nodes = pd.read_csv(os.path.join(NET, "nodes.tsv"), sep="\t", encoding="utf-8")
links = pd.read_csv(os.path.join(NET, "links.tsv"), sep="\t", encoding="utf-8")

# begin 컬럼 실제 값 확인
print("=== nodes begin 분포 (상위 10) ===")
print(nodes["begin"].value_counts().head(10).to_string())
print(f"\nbegin dtype: {nodes['begin'].dtype}")
print(f"effective_begin 샘플: {nodes['effective_begin'].head(10).tolist()}")
print(f"effective_begin 비어있는 비율: {(nodes['effective_begin'].astype(str).str.strip() == '').mean():.2%}")

print("\n=== begin 범위 ===")
print(f"  min: {nodes['begin'].min()}")
print(f"  max: {nodes['begin'].max()}")

# 날짜가 float/NaN인지 확인
print(f"\nnodes begin 타입 샘플: {nodes['begin'].head(5).tolist()}")
print(f"links begin 타입 샘플: {links['begin'].head(5).tolist()}")

# 노선명 확인 - 판교/남위례 관련
print("\n=== 신분당선 관련 역 ===")
print(nodes[nodes["linenm"].astype(str).str.contains("신분당|분당", na=False)][["id","linenm","statnm","begin"]].to_string())

print("\n=== 8호선 관련 역 ===")
print(nodes[nodes["linenm"].astype(str).str.contains("8호|8号", na=False)][["id","linenm","statnm","begin"]].head(10).to_string())

print("\n=== '판교' 포함 역 ===")
print(nodes[nodes["statnm"].astype(str).str.contains("판교", na=False)][["id","linenm","statnm","begin"]].to_string())

print("\n=== '위례' 포함 역 ===")
print(nodes[nodes["statnm"].astype(str).str.contains("위례", na=False)][["id","linenm","statnm","begin"]].to_string())
