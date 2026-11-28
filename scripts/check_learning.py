"""Kiểm nghiệm thu luồng after_lab (learning-v1). Chỉ thư viện chuẩn (+ websocket-client nếu chạy --browser).

  python scripts/check_learning.py unit                         bộ kiểm tests/learning (model giả/kịch bản)
  python scripts/check_learning.py parity <repo> [<repo>...]     cùng root qua local / ZIP / folder upload → cùng manifest+hash;
                                                                 before_lab vẫn lọc MISSION_ANSWERS/INSTRUCTOR_GUIDE
  python scripts/check_learning.py html <file.html> [--repo <repo>]   kiểm tĩnh: CSP, không primitive mạng, JSON nhúng,
                                                                 không lộ tên/MSSV/email/URL deploy của repo
  python scripts/check_learning.py browser <file.html> [--shots <dir>]  Chrome headless qua CDP: lỗi JS, request mạng,
                                                                 thao tác bàn phím/chuột trên các tương tác

Không in nội dung nguồn; chỉ in số lượng, hash rút gọn và kết quả kiểm. Thư mục tạm được xóa sau khi kiểm.
"""
import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "codebase"))
os.environ.setdefault("MODEL_PROVIDER", "fake")      # parity/html không gọi model

FORBIDDEN = [r"fetch\(", r"XMLHttpRequest", r"WebSocket", r"sendBeacon", r"importScripts", r"\bimport\(", r"<link ",
             r"@import", r'src="http', r'href="http', r"url\(http", r"serviceWorker", r"\beval\(", r"new Function",
             r"\.innerHTML", r"insertAdjacentHTML", r"document\.write", r"<iframe", r"<form"]


def ok(flag, msg):
    print(("  ✔ " if flag else "  ✘ ") + msg)
    return bool(flag)


# ------------------------------------------------------------------ unit
def cmd_unit():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests" / "learning"), top_level_dir=str(ROOT))
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    return res.wasSuccessful()


# ------------------------------------------------------------------ parity
def _root_files(repo):
    """(root .md, vài file ở thư mục con / file khác) — chỉ để dựng archive thử, không in nội dung."""
    md, other = [], []
    for e in sorted(os.scandir(repo), key=lambda e: e.name):
        if e.is_file() and e.name.lower().endswith(".md"):
            md.append(e.path)
        elif e.is_dir() and not e.name.startswith("."):
            for r, _, fs in os.walk(e.path):
                other += [os.path.join(r, f) for f in fs[:2] if f.lower().endswith((".md", ".py", ".txt"))]
                if len(other) > 6:
                    break
    return md, other[:6]


def cmd_parity(repos):
    import root_markdown as R
    import web_server as W
    good = True
    for repo in repos:
        repo = os.path.abspath(repo)
        print("== %s" % R.RepoRef(repo).label)
        local = R.read_root_markdown(R.RepoRef(repo))
        want = {m["name"]: m["sha256"] for m in local.manifest}
        good &= ok(all(m["read_status"] == "read" for m in local.manifest), "local: %d/%d file đọc được"
                   % (sum(m["read_status"] == "read" for m in local.manifest), len(local.manifest)))
        md, other = _root_files(repo)
        wrapper = "repo-wrapper"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for p in md + other:
                zf.write(p, wrapper + "/" + os.path.relpath(p, repo).replace(os.sep, "/"))
        tmps = []
        try:
            # ZIP after_lab
            t = Path(tempfile.mkdtemp(prefix="parity-zip-")); tmps.append(t)
            (t / "lab").mkdir()
            man = W._ingest_zip_after_lab(buf.getvalue(), t / "lab", channel="zip")
            R.register_ingest_manifest(str(t / "lab"), man)
            z = R.read_root_markdown(R.RepoRef(str(t / "lab")))
            good &= ok({m["name"]: m["sha256"] for m in z.manifest} == want and z.snapshot_id == local.snapshot_id,
                       "ZIP: cùng %d file, cùng hash, cùng snapshot %s" % (len(want), z.snapshot_id[:12]))
            good &= ok(not any(i["code"] == "ingest_mismatch" for i in z.issues), "ZIP: manifest tiếp nhận khớp reader")
            # Folder upload after_lab
            t2 = Path(tempfile.mkdtemp(prefix="parity-folder-")); tmps.append(t2)
            items = [(os.path.basename(repo) + "/" + os.path.relpath(p, repo).replace(os.sep, "/"), open(p, "rb").read())
                     for p in md + other]
            (t2 / "lab").mkdir()
            n, man2 = W._ingest_folder_upload("after_lab", items, os.path.basename(repo), t2 / "lab")
            R.register_ingest_manifest(str(t2 / "lab"), man2)
            f = R.read_root_markdown(R.RepoRef(str(t2 / "lab")))
            good &= ok({m["name"]: m["sha256"] for m in f.manifest} == want and f.snapshot_id == local.snapshot_id,
                       "Folder upload: cùng %d file, cùng hash, cùng snapshot" % n)
            # before_lab giữ bộ lọc cũ
            t3 = Path(tempfile.mkdtemp(prefix="parity-before-")); tmps.append(t3)
            W._safe_extract_zip(buf.getvalue(), t3)
            kept = {p.name.upper() for p in t3.iterdir()}
            special = {"MISSION_ANSWERS.MD", "INSTRUCTOR_GUIDE.MD"} & {n.upper() for n in want}
            if special:
                good &= ok(not (special & kept), "before_lab ZIP vẫn lọc %s" % ", ".join(sorted(special)))
                good &= ok(special <= {n.upper() for n in {m["name"] for m in z.manifest}}, "after_lab giữ %s"
                           % ", ".join(sorted(special)))
        finally:
            for t in tmps:
                shutil.rmtree(t, ignore_errors=True)
    return good


# ------------------------------------------------------------------ html tĩnh
def _embedded(html):
    m = re.search(r'<script type="application/json" id="learning-data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else None


def cmd_html(path, repo=None):
    import root_markdown as R
    html = open(path, encoding="utf-8").read()
    good = ok(html.lstrip().lower().startswith("<!doctype html>"), "doctype")
    import html as _h
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]*)"', html)
    good &= ok(csp and "default-src 'none'" in _h.unescape(csp.group(1)), "CSP default-src 'none'")
    bad = [p for p in FORBIDDEN if re.search(p, html)]
    good &= ok(not bad, "không primitive mạng/HTML động" + ((": " + ", ".join(bad)) if bad else ""))
    good &= ok(len(re.findall(r'href="(?!#)', html)) == 0, "chỉ có link #mục nội bộ")
    data = _embedded(html)
    good &= ok(data is not None, "JSON nhúng đọc được")
    if data:
        model = data.get("model", data)
        v = model.get("validation", {})
        print("    content_state=%s · review=%s · coverage=%s" % (v.get("content_state"), v.get("review_state"),
                                                                 v.get("coverage_summary")))
        txt = json.dumps(model, ensure_ascii=False)
        good &= ok("verified_pass" not in txt and '"status": "verified"' not in txt, "không có trạng thái verified")
    good &= ok(not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}", html.replace("noreply@", "")),
               "không có email")
    good &= ok(not R.MSSV_RE.search(html), "không có MSSV")
    good &= ok(not R.DEPLOY_URL_RE.search(html), "không có URL deploy cá nhân")
    if repo:
        snap = R.read_root_markdown(R.RepoRef(repo))
        folded = R._fold(html)
        leaks = [n for n in snap._names if n in folded]
        good &= ok(not leaks, "không lộ %d tên/tài khoản suy ra từ repo (đếm lộ: %d)" % (len(snap._names), len(leaks)))
        good &= ok(os.path.basename(os.path.abspath(repo)) not in html, "không lộ tên thư mục repo")
    return good


# ------------------------------------------------------------------ trình duyệt (CDP)
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "/usr/bin/google-chrome", "/usr/bin/chromium"]

INTERACT = r"""
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const out = {};
  const q = (s) => document.querySelector(s);
  const qa = (s) => [...document.querySelectorAll(s)];
  out.sections = qa('section.lesson').map(s => s.id);
  out.sectionErrors = qa('.section-error, [data-section-error]').length;
  const src = qa('button[aria-controls]').find(b => /\.md:\d/i.test(b.textContent));
  if (src) { src.focus(); src.click(); await sleep(50); out.sourceOpen = src.getAttribute('aria-expanded'); }
  const next = qa('button').find(b => /^(Tiếp|Bước sau|Sau)/.test(b.textContent.trim()));
  if (next) { next.click(); await sleep(50); next.click(); await sleep(50);
    out.traceCounter = (qa('[aria-live]').map(e => e.textContent).find(t => /Bước\s*\d+\s*\/\s*\d+/.test(t)) || '').slice(0, 80); }
  const radio = q('#decisions input[type=radio]');
  if (radio) {
    radio.click(); await sleep(30);
    const box = radio.closest('fieldset, .interaction, article, div').parentElement;
    const btn = qa('#decisions button').find(b => /Xem phản hồi/.test(b.textContent));
    out.feedbackDisabledBeforeReason = btn ? btn.disabled : null;
    const ta = q('#decisions textarea');
    if (ta) { ta.value = 'Vì nguồn ghi như vậy'; ta.dispatchEvent(new Event('input', {bubbles: true})); }
    await sleep(30);
    out.feedbackEnabledAfterReason = btn ? !btn.disabled : null;
    if (btn) { btn.click(); await sleep(50); }
    out.feedbackShown = qa('#decisions [aria-live]').some(e => e.textContent.trim().length > 10);
  }
  const tb = q('#teachback textarea');
  if (tb) {
    const done = qa('#teachback button').find(b => /Tôi đã trả lời xong/.test(b.textContent));
    out.teachDoneDisabledEmpty = done ? done.disabled : null;
    tb.value = 'Tôi giải thích bằng lời của mình'; tb.dispatchEvent(new Event('input', {bubbles: true})); await sleep(30);
    if (done) { done.click(); await sleep(50); }
    out.checklistVisible = qa('#teachback input[type=checkbox]').some(c => c.offsetParent !== null);
  }
  const pres = qa('button').find(b => /Chế độ trình bày/.test(b.textContent));
  if (pres) {
    pres.click(); await sleep(80);
    const counter = () => (qa('[aria-live], .slide-counter').map(e => e.textContent).find(t => /Thẻ\s*\d+\s*\/\s*\d+/.test(t)) || '');
    const before = counter();
    document.activeElement.blur && document.activeElement.blur();
    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
    await sleep(50);
    out.slideBefore = before.slice(0, 30); out.slideAfter = counter().slice(0, 30);
    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    await sleep(50);
    out.focusBackOnPresButton = document.activeElement === pres;
  }
  out.tabStops = qa('button, input, textarea, select, a[href]').filter(e => !e.disabled && e.tabIndex >= 0).length;
  out.scriptElementsFromData = qa('script').length;
  out.imgElements = qa('img').length;
  return out;
})()
"""


def cmd_browser(path, shots=None):
    import websocket
    chrome = next((c for c in CHROME if os.path.exists(c)), None)
    if not chrome:
        print("  ! không tìm thấy Chrome/Edge — chưa kiểm trình duyệt")
        return False
    prof = tempfile.mkdtemp(prefix="cdp-prof-")
    port = 9400 + os.getpid() % 300
    proc = subprocess.Popen([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--remote-debugging-port=%d" % port,
                             "--user-data-dir=" + prof, "--window-size=1280,900", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    good = True
    try:
        for _ in range(80):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % port))
                break
            except Exception:
                time.sleep(0.2)
        tab = [t for t in tabs if t["type"] == "page"][0]
        ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=30)
        n, events = [0], []

        def call(method, **params):
            n[0] += 1
            ws.send(json.dumps({"id": n[0], "method": method, "params": params}))
            while True:
                m = json.loads(ws.recv())
                if m.get("id") == n[0]:
                    return m.get("result", m)
                events.append(m)

        for d in ("Runtime", "Page", "Log", "Network"):
            call(d + ".enable")
        url = Path(os.path.abspath(path)).as_uri()
        call("Page.navigate", url=url)
        time.sleep(2.0)
        r = call("Runtime.evaluate", expression=INTERACT, returnByValue=True, awaitPromise=True)
        res = r.get("result", {}).get("value") or {"exception": json.dumps(r.get("exceptionDetails", ""))[:300]}
        print("    " + json.dumps(res, ensure_ascii=False))
        if shots:
            os.makedirs(shots, exist_ok=True)
            call("Runtime.evaluate", expression="window.scrollTo(0,0)")
            for name, sel in (("top", None), ("workflow", "#workflow"), ("walkthrough", "#walkthrough"),
                              ("decisions", "#decisions"), ("evidence", "#evidence"), ("teachback", "#teachback"),
                              ("presentation", "#presentation")):
                if sel:
                    call("Runtime.evaluate", expression="document.querySelector('%s')?.scrollIntoView()" % sel)
                time.sleep(0.3)
                d = call("Page.captureScreenshot", format="png")
                open(os.path.join(shots, name + ".png"), "wb").write(base64.b64decode(d["data"]))
        call("Runtime.evaluate", expression="1")
        errs = [e for e in events if e.get("method") == "Runtime.exceptionThrown" or
                (e.get("method") == "Runtime.consoleAPICalled" and e["params"]["type"] == "error") or
                (e.get("method") == "Log.entryAdded" and e["params"]["entry"]["level"] == "error")]
        reqs = [e["params"]["request"]["url"] for e in events if e.get("method") == "Network.requestWillBeSent"]
        external = [u for u in reqs if not u.startswith(("file:", "data:", "blob:", "about:"))]
        good &= ok(not errs, "không lỗi JS/console (%d)" % len(errs))
        good &= ok(not external, "không request mạng ngoài (tổng request %d, ngoài %d)" % (len(reqs), len(external)))
        good &= ok(len(res.get("sections", [])) == 7 and not res.get("sectionErrors"), "đủ 7 mục, không mục lỗi")
        good &= ok(res.get("imgElements") == 0, "không phần tử <img> từ dữ liệu nguồn")
        for k, label in (("sourceOpen", "mở nguồn tại chỗ"), ("feedbackEnabledAfterReason", "phản hồi chỉ mở sau khi nhập lý do"),
                         ("checklistVisible", "checklist mở sau khi tự trả lời"), ("focusBackOnPresButton",
                                                                                  "Escape thoát trình bày, trả focus")):
            if k in res:
                good &= ok(res[k] in (True, "true"), label)
        if "feedbackDisabledBeforeReason" in res:
            good &= ok(res["feedbackDisabledBeforeReason"] is True, "nút phản hồi khóa khi chưa có lý do")
        if res.get("slideBefore") and not re.search(r"Thẻ\s*1\s*/\s*1(?!\d)", res["slideBefore"]):
            good &= ok(res["slideBefore"] != res["slideAfter"], "phím → chuyển thẻ (%s → %s)" % (res["slideBefore"],
                                                                                              res["slideAfter"]))
    finally:
        proc.kill()
        time.sleep(0.5)
        shutil.rmtree(prof, ignore_errors=True)
    return good


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "unit":
        return 0 if cmd_unit() else 1
    if cmd == "parity":
        return 0 if cmd_parity(rest) else 1
    if cmd == "html":
        repo = rest[rest.index("--repo") + 1] if "--repo" in rest else None
        return 0 if cmd_html(rest[0], repo) else 1
    if cmd == "browser":
        shots = rest[rest.index("--shots") + 1] if "--shots" in rest else None
        return 0 if cmd_browser(rest[0], shots) else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main(sys.argv[1:]))
