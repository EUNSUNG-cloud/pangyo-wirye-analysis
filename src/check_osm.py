import json, os

path = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트\export.geojson"
size_mb = os.path.getsize(path) / 1e6
with open(path, encoding="utf-8") as f:
    fc = json.load(f)

feats = fc["features"]
print(f"size: {size_mb:.1f}MB, features: {len(feats)}")

# geometry type distribution
types = {}
for ft in feats:
    t = ft["geometry"]["type"]
    types[t] = types.get(t, 0) + 1
print(f"geometry types: {types}")

# highway tag distribution (first 3000 line features)
hwy = {}
for ft in feats[:3000]:
    if ft["geometry"]["type"] == "LineString":
        hw = ft.get("properties", {}).get("highway", "none")
        hwy[hw] = hwy.get(hw, 0) + 1
print(f"highway tags (first 3000): {dict(sorted(hwy.items(), key=lambda x: -x[1])[:15])}")

# sample line feature
for ft in feats:
    if ft["geometry"]["type"] == "LineString":
        props = ft.get("properties", {})
        print(f"\nsample line props keys: {list(props.keys())[:15]}")
        print(f"sample line props: {dict(list(props.items())[:8])}")
        coords = ft["geometry"]["coordinates"]
        print(f"sample coords (first 3): {coords[:3]}")
        break
