"""Đếm bằng chứng từ data pre-class BTC cấp. Chạy: python evidence/count.py <đường dẫn tới data/preclass>
Không chép data vào repo; script chỉ in số đã tổng hợp."""
import csv, json, os, sys
from collections import defaultdict

D = sys.argv[1] if len(sys.argv) > 1 else "data/preclass"
rd = lambda f: csv.DictReader(open(os.path.join(D, f), encoding="utf-8-sig"))

# 1. Mini lab: ai mở, ai bấm bỏ qua
opened = defaultdict(set); done = {}
for e in rd("events.csv"):
    if e["type"] not in ("lab_opened", "lab_completed"):
        continue
    d = json.loads(e["data"] or "{}"); k = (e["hv"], d.get("lab_key"))
    if e["type"] == "lab_opened":
        opened[e["hv"]].add(d.get("lab_key"))
    else:
        done[k] = d
skipped = [k for k, d in done.items() if str(d.get("skipped")).lower() == "true"]
print("Học viên có mở mini lab: %d" % len(opened))
partial = [k for k, d in done.items() if d.get("steps") and d.get("steps_done") is not None and d["steps_done"] < d["steps"]]
print("Lần xong mini lab có steps_done < steps: %d/%d" % (len(partial), len(done)))
print("Lần xong mini lab bị bấm bỏ qua: %d/%d (%.0f%%)" % (len(skipped), len(done), 100 * len(skipped) / len(done)))
sk_hv = {k[0] for k in skipped} & set(opened)
print("Học viên bỏ qua ≥1 mini lab: %d/%d (%.0f%%)" % (len(sk_hv), len(opened), 100 * len(sk_hv) / len(opened)))

# 2. Làm bước thực hành nhưng chưa từng tự giải thích
A = list(rd("answers.csv"))
th = {a["hv"] for a in A if a["nguon"] == "thuc_hanh"}
gt = {a["hv"] for a in A if a["nguon"] == "giai_thich"}
print("Học viên làm bước thực hành có tự giải thích ít nhất 1 lần: %d/%d (%.0f%%)" % (len(th & gt), len(th), 100 * len(th & gt) / len(th)))
