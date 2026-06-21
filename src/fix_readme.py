"""Fix corrupted UTF-8 bytes in README.md (5 positions with U+FFFD replacement chars)"""
import os

BASE = r"C:\Users\User\OneDrive\바탕 화면\스시론 기말 프로젝트"
path = os.path.join(BASE, "README.md")

with open(path, "rb") as f:
    data = f.read()

print(f"Before: {data.count(b'\\xef\\xbf\\xbd')} replacement chars")

# 업??지구로 → 업무지구로  (무 U+BB34 = \xeb\xac\xb4)
data = data.replace(
    b"\xec\x97\x85\xef\xbf\xbd\xef\xbf\xbd\xec\xa7\x80\xea\xb5\xac\xeb\xa1\x9c",
    b"\xec\x97\x85\xeb\xac\xb4\xec\xa7\x80\xea\xb5\xac\xeb\xa1\x9c")

# 대학?? → 대학교  (교 U+AD50 = \xea\xb5\x90)
data = data.replace(
    b"\xeb\x8c\x80\xed\x95\x99\xef\xbf\xbd\xef\xbf\xbd\x20",
    b"\xeb\x8c\x80\xed\x95\x99\xea\xb5\x90\x20")

# 교_???평동_title → 교_삼평동_title  (삼 U+C0BC = \xec\x82\xbc)
data = data.replace(
    b"\xea\xb5\x90_\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xed\x8f\x89\xeb\x8f\x99_title",
    b"\xea\xb5\x90_\xec\x82\xbc\xed\x8f\x89\xeb\x8f\x99_title")

# ── ???례_창곡동 → ── 위례_창곡동  (위 U+C704 = \xec\x9c\x84)
data = data.replace(
    b"\xe2\x94\x80\x20\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xeb\xa1\x80_\xec\xb0\xbd",
    b"\xe2\x94\x80\x20\xec\x9c\x84\xeb\xa1\x80_\xec\xb0\xbd")

# 10700`), ???파구 → 10700`), 송파구  (송 U+C1A1 = \xec\x86\xa1)
data = data.replace(
    b"10700`), \xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xed\x8c\x8c\xea\xb5\xac",
    b"10700`), \xec\x86\xa1\xed\x8c\x8c\xea\xb5\xac")

with open(path, "wb") as f:
    f.write(data)

remaining = data.count(b"\xef\xbf\xbd")
print(f"After:  {remaining} replacement chars")
if remaining == 0:
    print("README.md 인코딩 수정 완료")
else:
    # Show remaining positions
    pos = 0
    while True:
        idx = data.find(b"\xef\xbf\xbd", pos)
        if idx == -1:
            break
        ctx = data[max(0, idx-15):idx+15]
        print(f"  remaining pos={idx}: {ctx}")
        pos = idx + 1
