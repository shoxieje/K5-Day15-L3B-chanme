"""Web server cho Be The Agent (chanme) — chỉ dùng thư viện chuẩn Python 3.10+.

Hỗ trợ 3 cách đưa bài lab vào:
  1. Chọn bài lab mẫu có sẵn (deploy/sample_labs/) để chạy thử ngay
  2. Dán link GitHub repository công khai (tải archive zip trực tiếp)
  3. Tải lên file .zip hoặc chọn thư mục bài lab từ máy người dùng

Chạy cục bộ hoặc trên VPS sau Cloudflare Tunnel:
  python codebase/web_server.py --host 127.0.0.1 --port 8795
"""
import argparse
import collections
import hashlib
import hmac
import html
import io
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CODEBASE_DIR = Path(__file__).resolve().parent
ROOT = CODEBASE_DIR.parent
if str(CODEBASE_DIR) not in sys.path:
    sys.path.insert(0, str(CODEBASE_DIR))

import tracing  # noqa: E402
from agent import answer  # noqa: E402
from ai import MODEL_NAME, MODEL_PROVIDER  # noqa: E402
from tools import SKIP_DIRS, SKIP_FILES, TEXT_EXT  # noqa: E402

OUTPUT_DIR = (ROOT / "output").resolve()
SAMPLES_DIR = Path(os.environ.get("SAMPLES_DIR") or (ROOT / "deploy" / "sample_labs")).resolve()
WEB_SECRET = (os.environ.get("WEB_SECRET") or secrets.token_hex(32)).encode("utf-8")
CHANME_HOST = (os.environ.get("CHANME_HOST") or "").strip()

MAX_UPLOAD_BYTES = 20 * 1024 * 1024       # 20 MB
MAX_EXTRACT_BYTES = 30 * 1024 * 1024      # 30 MB
MAX_FILES = 1000
CSRF_TTL_S = 12 * 3600
RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX") or "12")
RATE_LIMIT_WINDOW_S = int(os.environ.get("RATE_LIMIT_WINDOW_S") or "600")

GITHUB_URL_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:/tree/([A-Za-z0-9_./-]+))?/?$"
)
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_-]+")

_AGENT_LOCK = threading.Lock()
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: dict[str, collections.deque[float]] = collections.defaultdict(collections.deque)
_JOBS_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}
MAX_JOB_HISTORY = 100


def _make_csrf_token() -> str:
    ts = str(int(time.time()))
    sig = hmac.new(WEB_SECRET, ts.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"


def _verify_csrf_token(token: str) -> bool:
    if not token or "." not in token:
        return False
    ts_str, sig = token.split(".", 1)
    if not ts_str.isdigit():
        return False
    age = int(time.time()) - int(ts_str)
    if age < -60 or age > CSRF_TTL_S:
        return False
    expected = hmac.new(WEB_SECRET, ts_str.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def _check_rate_limit(client_ip: str) -> tuple[bool, int]:
    now = time.monotonic()
    with _RATE_LOCK:
        q = _RATE_BUCKETS[client_ip]
        while q and now - q[0] > RATE_LIMIT_WINDOW_S:
            q.popleft()
        if len(q) >= RATE_LIMIT_MAX:
            retry_after = max(1, int(RATE_LIMIT_WINDOW_S - (now - q[0])))
            return False, retry_after
        q.append(now)
        return True, 0


def _sanitize_slug(name: str) -> str:
    cleaned = SAFE_NAME_RE.sub("-", (name or "").strip()).strip("-")
    return cleaned[:64] or "lab"


def _is_allowed_relpath(rel_parts: tuple[str, ...]) -> bool:
    if not rel_parts:
        return False
    for part in rel_parts[:-1]:
        if not part or part in (".", "..") or part.startswith(".") or part.lower() in SKIP_DIRS:
            return False
    fname = rel_parts[-1]
    if not fname or fname in (".", "..") or fname.startswith(".env") or fname.upper() in SKIP_FILES:
        return False
    return fname.lower().endswith(TEXT_EXT)


def _safe_extract_zip(raw_bytes: bytes, dest_root: Path) -> int:
    """Giải nén an toàn chỉ các file văn bản hợp lệ vào dest_root, bỏ thư mục bọc ngoài nếu có."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError("Tệp .zip không hợp lệ hoặc bị hỏng.") from exc

    with zf:
        infos = [info for info in zf.infolist() if not info.is_dir()]
        if not infos:
            raise ValueError("Tệp .zip trống, không có tệp nào.")

        # Kiểm tra nếu toàn bộ file nằm trong một thư mục gốc duy nhất (vd archive của GitHub)
        split_paths = []
        for info in infos:
            # Bỏ symlink (UNIX mode 0o120000)
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                continue
            norm = info.filename.replace("\\", "/").lstrip("/")
            parts = tuple(p for p in norm.split("/") if p)
            if not parts or any(p == ".." for p in parts):
                continue
            split_paths.append((info, parts))

        if not split_paths:
            raise ValueError("Không tìm thấy tệp hợp lệ nào trong tệp .zip.")

        top_dirs = {parts[0] for _, parts in split_paths if len(parts) > 1}
        strip_top = len(top_dirs) == 1 and all(len(parts) > 1 for _, parts in split_paths)

        total_bytes = 0
        written = 0
        dest_resolved = dest_root.resolve()
        for info, parts in split_paths:
            rel_parts = parts[1:] if strip_top else parts
            if not _is_allowed_relpath(rel_parts):
                continue
            if written >= MAX_FILES:
                break
            if info.file_size > 5 * 1024 * 1024:
                continue
            data = zf.read(info)
            total_bytes += len(data)
            if total_bytes > MAX_EXTRACT_BYTES:
                raise ValueError("Dung lượng bài lab sau giải nén vượt quá giới hạn 30 MB.")
            target = (dest_root / Path(*rel_parts)).resolve()
            if not str(target).startswith(str(dest_resolved) + os.sep):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            written += 1

        return written


def _download_github_zip(url: str) -> tuple[bytes, str, str]:
    """Tải archive ZIP từ GitHub repo công khai. Trả về (zip_bytes, lab_name, subdir)."""
    m = GITHUB_URL_RE.fullmatch(url.strip())
    if not m:
        raise ValueError("Link GitHub chưa đúng dạng https://github.com/<owner>/<repo>")
    owner, repo, tree_part = m.group(1), m.group(2), m.group(3)
    candidates: list[tuple[str, str]] = []
    if tree_part:
        segs = [s for s in tree_part.split("/") if s]
        branch = segs[0]
        subdir = "/".join(segs[1:])
        candidates.append((f"https://github.com/{owner}/{repo}/archive/refs/heads/{urllib.parse.quote(branch)}.zip", subdir))
        candidates.append((f"https://github.com/{owner}/{repo}/archive/HEAD.zip", tree_part))
    else:
        candidates.append((f"https://github.com/{owner}/{repo}/archive/HEAD.zip", ""))

    last_err = None
    for zip_url, subdir in candidates:
        req = urllib.request.Request(zip_url, headers={"User-Agent": "BeTheAgent-Chanme/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                final_host = (urllib.parse.urlsplit(resp.geturl()).hostname or "").lower()
                if final_host not in ("github.com", "codeload.github.com"):
                    raise ValueError("Đích chuyển hướng không thuộc GitHub.")
                buf = io.BytesIO()
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    buf.write(chunk)
                    if buf.tell() > MAX_UPLOAD_BYTES:
                        raise ValueError("Repository vượt quá giới hạn tải 20 MB.")
                lab_name = _sanitize_slug(f"{repo}-{subdir.replace('/', '-')}" if subdir else repo)
                return buf.getvalue(), lab_name, subdir
        except urllib.error.HTTPError as exc:
            last_err = f"GitHub trả HTTP {exc.code} (hãy chắc chắn repo đang ở chế độ Public)."
        except urllib.error.URLError as exc:
            last_err = f"Không tải được từ GitHub: {exc.reason}"
    raise ValueError(last_err or "Không tải được repository từ GitHub.")


def _parse_multipart(content_type: str, body: bytes) -> tuple[dict[str, list[str]], list[tuple[str, str, bytes]]]:
    """Parser multipart/form-data tối giản bằng stdlib (không phụ thuộc module cgi)."""
    m = re.search(r'boundary=(?:"([^"]+)"|([^;\s]+))', content_type, re.IGNORECASE)
    if not m:
        raise ValueError("Thiếu boundary trong multipart/form-data.")
    boundary = (m.group(1) or m.group(2)).encode("latin-1")
    delimiter = b"--" + boundary
    fields: dict[str, list[str]] = collections.defaultdict(list)
    files: list[tuple[str, str, bytes]] = []

    parts = body.split(delimiter)
    for part in parts[1:]:
        if part.startswith(b"--"):
            break
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        sep = part.find(b"\r\n\r\n")
        if sep < 0:
            continue
        raw_headers = part[:sep].decode("utf-8", errors="replace")
        payload = part[sep + 4:]
        disp = ""
        for line in raw_headers.splitlines():
            if line.lower().startswith("content-disposition:"):
                disp = line.split(":", 1)[1].strip()
                break
        name_m = re.search(r'name="([^"]*)"', disp)
        if not name_m:
            continue
        field_name = name_m.group(1)
        file_m = re.search(r'filename="([^"]*)"', disp)
        if file_m is not None:
            filename = file_m.group(1)
            if filename:
                files.append((field_name, filename, payload))
        else:
            fields[field_name].append(payload.decode("utf-8", errors="replace"))
    return fields, files


def _list_samples() -> list[dict]:
    items = []
    if not SAMPLES_DIR.is_dir():
        return items
    for child in sorted(SAMPLES_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        readme = next((child / n for n in ("README.md", "readme.md") if (child / n).is_file()), None)
        if not readme:
            continue
        title = child.name
        for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("#"):
                title = line.strip().lstrip("#").strip()
                break
        file_count = sum(1 for p in child.rglob("*") if p.is_file() and p.name.lower().endswith(TEXT_EXT))
        slug = _sanitize_slug(child.name)
        rendered_exists = (OUTPUT_DIR / f"{slug}.html").is_file()
        items.append({
            "id": child.name,
            "title": title,
            "file_count": file_count,
            "slug": slug,
            "rendered_url": f"/output/{urllib.parse.quote(slug)}.html" if rendered_exists else "",
        })
    return items


def _list_outputs() -> list[dict]:
    if not OUTPUT_DIR.is_dir():
        return []
    pages = []
    for p in OUTPUT_DIR.glob("*.html"):
        if not p.is_file():
            continue
        stat = p.stat()
        pages.append({
            "name": p.stem,
            "filename": p.name,
            "url": f"/output/{urllib.parse.quote(p.name)}",
            "mtime": stat.st_mtime,
            "mtime_str": time.strftime("%d/%m/%Y %H:%M", time.localtime(stat.st_mtime)),
        })
    pages.sort(key=lambda item: item["mtime"], reverse=True)
    return pages[:20]


def _run_agent(lab_dir: Path, display_name: str, case_id: str) -> tuple[str, str, dict]:
    """Chạy answer() tuần tự (an toàn cho tracing._case) và trả (markdown, page_url, summary)."""
    t0 = time.perf_counter()
    with _AGENT_LOCK:
        tracing.begin(case_id)
        try:
            raw = answer(str(lab_dir))["output"]
        finally:
            summary, _ = tracing.end()
    summary["elapsed_s"] = round(time.perf_counter() - t0, 1)
    # Ẩn đường dẫn thư mục tạm trên server khỏi tiêu đề markdown hiển thị cho người dùng
    cleaned = raw.replace(str(lab_dir), display_name)
    page_url = ""
    marker = "Trang đóng vai: "
    if marker in cleaned:
        page_rel = cleaned.rsplit(marker, 1)[1].strip()
        if page_rel.startswith("output/") and page_rel.endswith(".html"):
            page_url = "/" + urllib.parse.quote(page_rel, safe="/")
    return cleaned, page_url, summary


def _start_job(lab_dir: Path, display_name: str, case_id: str, cleanup_dir: Path | None = None) -> str:
    """Tạo job chạy nền để trả HTTP 303 ngay lập tức (tránh lỗi Cloudflare 524 khi AI mất >100s)."""
    job_id = secrets.token_urlsafe(12)
    job = {
        "id": job_id,
        "status": "queued",
        "display_name": display_name,
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "markdown": "",
        "page_url": "",
        "summary": {},
        "error": "",
    }
    with _JOBS_LOCK:
        _JOBS[job_id] = job
        if len(_JOBS) > MAX_JOB_HISTORY:
            oldest = sorted(_JOBS.items(), key=lambda kv: kv[1]["created_at"])[: len(_JOBS) - MAX_JOB_HISTORY]
            for old_id, _ in oldest:
                if _JOBS[old_id]["status"] in ("done", "error"):
                    _JOBS.pop(old_id, None)

    def _worker() -> None:
        try:
            with _JOBS_LOCK:
                job["status"] = "running"
                job["started_at"] = time.time()
            md, page_url, summary = _run_agent(lab_dir, display_name, case_id)
            with _JOBS_LOCK:
                job["status"] = "done"
                job["markdown"] = md
                job["page_url"] = page_url
                job["summary"] = summary
                job["finished_at"] = time.time()
        except Exception as exc:
            with _JOBS_LOCK:
                job["status"] = "error"
                job["error"] = str(exc)
                job["finished_at"] = time.time()
        finally:
            if cleanup_dir is not None:
                shutil.rmtree(cleanup_dir, ignore_errors=True)

    threading.Thread(target=_worker, daemon=True, name=f"chanme-job-{job_id[:6]}").start()
    return job_id


def _render_job_page(job: dict) -> str:
    status = job["status"]
    name = html.escape(job["display_name"])
    jid = html.escape(job["id"], quote=True)
    elapsed = round(time.time() - (job["started_at"] or job["created_at"]), 1)
    refresh_meta = '<meta http-equiv="refresh" content="4">' if status in ("queued", "running") else ""

    if status in ("queued", "running"):
        status_label = "Đang chờ lượt xử lý..." if status == "queued" else "Đang phân tích bài lab & kiểm trích dẫn bằng Gemini..."
        body_block = (
            '<section class="card" aria-live="polite">'
            f'<h2>{html.escape(status_label)}</h2>'
            f'<p class="hint">Bài lab: <strong>{name}</strong> · Đã chạy: <span id="elapsed">{elapsed}</span>s</p>'
            '<p class="hint">Hệ thống đang đọc đề, soạn tình huống đóng vai và tự kiểm tra mọi trích dẫn <code>file:dòng</code> (có thể mất 30–120 giây). Trang sẽ tự cập nhật ngay khi hoàn tất.</p>'
            '<progress aria-label="Đang xử lý bài lab" style="width:100%;height:14px;margin-top:12px"></progress>'
            '</section>'
            f'<script>'
            f'const started={job["created_at"]};'
            f'const el=document.getElementById("elapsed");'
            f'setInterval(()=>{{if(el)el.textContent=((Date.now()/1000)-started).toFixed(1);}},500);'
            f'async function poll(){{try{{const r=await fetch("/api/jobs/{jid}",{{cache:"no-store"}});'
            f'if(!r.ok)return;const d=await r.json();'
            f'if(d.status==="done"||d.status==="error"){{location.reload();return;}}}}catch(_e){{}}'
            f'setTimeout(poll,2500);}}setTimeout(poll,2000);'
            f'</script>'
        )
    elif status == "done":
        body_block = _build_result_card(job["markdown"], job["page_url"], job["summary"])
    else:
        body_block = (
            '<div class="alert alert-error" role="alert">'
            '<span role="img" aria-label="Lỗi">❌</span> '
            f'<span>Không tạo được trang cho <strong>{name}</strong>: {html.escape(job["error"])}</span></div>'
        )

    return f'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{refresh_meta}
<title>Be The Agent · {name}</title>
<style>
  :root {{ color-scheme: light; --bg:#f6f8fc; --surface:#fff; --ink:#18253b; --muted:#475569; --accent:#1d4ed8; --accent-hover:#1e40af; --danger-bg:#fef2f2; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif; line-height:1.6; margin:0; background:var(--bg); color:var(--ink); }}
  main {{ max-width:860px; margin:0 auto; padding:28px 16px 56px; }}
  .top-bar {{ display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:12px; margin-bottom:20px; }}
  .back-link {{ color:var(--accent); font-weight:600; text-decoration:none; min-height:44px; display:inline-flex; align-items:center; }}
  .back-link:hover,.back-link:focus-visible {{ text-decoration:underline; outline:3px solid var(--accent); outline-offset:2px; border-radius:6px; }}
  .card {{ background:var(--surface); border:1px solid #dbe3f0; border-radius:14px; padding:24px; margin-bottom:20px; box-shadow:0 1px 3px rgb(15 23 42 / .05); }}
  .hint,.stats {{ color:var(--muted); font-size:.95rem; }}
  .btn-primary {{ font:inherit; font-weight:600; min-height:48px; padding:.75rem 1.4rem; background:var(--accent); color:#fff; border:0; border-radius:8px; text-decoration:none; display:inline-flex; align-items:center; gap:8px; }}
  .btn-primary:hover {{ background:var(--accent-hover); }}
  .result-actions {{ display:flex; flex-wrap:wrap; gap:12px; margin:12px 0 18px; }}
  .alert {{ padding:14px 16px; border-radius:10px; display:flex; gap:8px; }}
  .alert-error {{ background:var(--danger-bg); border:1px solid #fecaca; color:#991b1b; }}
  pre {{ white-space:pre-wrap; overflow-wrap:anywhere; background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px; font-size:.9rem; max-height:540px; overflow:auto; }}
</style>
</head>
<body>
<main>
  <div class="top-bar">
    <a href="/" class="back-link">← Quay lại Be The Agent</a>
    <span class="hint">Bài lab: <strong>{name}</strong></span>
  </div>
  {body_block}
</main>
</body>
</html>'''


def _enhance_roleplay_html(raw_html: str) -> str:
    """Thêm thanh điều hướng quay lại trang chủ và CSS đọc dễ hơn mà giữ nguyên nội dung gốc."""
    nav = (
        '<div class="bta-bar">'
        '<a href="/" class="bta-back">← Quay lại Be The Agent</a>'
        '<span class="bta-badge">Bản nháp chờ trợ giảng duyệt</span>'
        '</div>'
    )
    extra_css = (
        "<style>"
        ":root{color-scheme:light}"
        "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.6;"
        "background:#f6f8fc;color:#18253b;max-width:860px;margin:0 auto;padding:20px 16px 48px}"
        ".bta-bar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;"
        "background:#ffffff;border:1px solid #d6deeb;border-radius:12px;padding:12px 16px;margin-bottom:20px}"
        ".bta-back{color:#1d4ed8;font-weight:600;text-decoration:none;min-height:44px;display:inline-flex;align-items:center}"
        ".bta-back:hover,.bta-back:focus-visible{text-decoration:underline;outline:3px solid #1d4ed8;outline-offset:2px;border-radius:6px}"
        ".bta-badge{font-size:.875rem;color:#475569;background:#eef2ff;padding:4px 10px;border-radius:999px}"
        "section{background:#ffffff;border:1px solid #dbe3f0;border-radius:14px;padding:20px 24px;margin:18px 0;"
        "box-shadow:0 1px 2px rgb(15 23 42 / .04)}"
        "section h2{margin-top:0;color:#0f172a;border-bottom:1px solid #e2e8f0;padding-bottom:8px}"
        "section h3{color:#1e3a8a;margin-top:18px;margin-bottom:8px;font-size:1.02rem}"
        "section ul{list-style:none;padding:0;display:grid;gap:10px}"
        "section li button{font:inherit;font-size:max(1rem,1em);min-height:48px;width:100%;text-align:left;"
        "padding:12px 14px;background:#f8fafc;color:#0f172a;border:1.5px solid #94a3b8;border-radius:10px;cursor:pointer}"
        "section li button:hover{background:#eff6ff;border-color:#2563eb}"
        "section li button:focus-visible{outline:3px solid #1d4ed8;outline-offset:2px}"
        ".reveal{margin-top:16px;padding:14px 16px;background:#f0fdf4;border-left:4px solid #16a34a;border-radius:8px}"
        ".src{color:#475569;font-size:.85em;background:#f1f5f9;padding:1px 6px;border-radius:4px;margin-left:4px}"
        "</style>"
    )
    if "<h1>" in raw_html:
        return raw_html.replace("<h1>", extra_css + nav + "<h1>", 1)
    return extra_css + nav + raw_html


def _render_home(
    *,
    active_tab: str = "sample",
    result_html: str = "",
    error_msg: str = "",
    github_url: str = "",
    selected_sample: str = "",
) -> str:
    token = _make_csrf_token()
    samples = _list_samples()
    outputs = _list_outputs()
    model_label = f"{MODEL_PROVIDER} · {MODEL_NAME}" if MODEL_PROVIDER != "fake" and MODEL_NAME else MODEL_PROVIDER
    is_fake = MODEL_PROVIDER == "fake"

    if not selected_sample and samples:
        selected_sample = samples[0]["id"]

    sample_radios = []
    for s in samples:
        checked = " checked" if s["id"] == selected_sample else ""
        preview_link = (
            f' · <a href="{s["rendered_url"]}" class="inline-link">Xem trang mẫu đã tạo →</a>'
            if s["rendered_url"] else ""
        )
        sid = html.escape(s["id"], quote=True)
        sample_radios.append(
            f'<div class="radio-row">'
            f'<input type="radio" id="sample-{sid}" name="sample" value="{sid}"{checked} required>'
            f'<label for="sample-{sid}"><strong>{html.escape(s["title"])}</strong>'
            f'<span class="meta"> ({s["file_count"]} tệp){preview_link}</span></label>'
            f'</div>'
        )
    samples_block = "\n".join(sample_radios) if sample_radios else '<p class="hint">Chưa có bài lab mẫu trên server.</p>'

    if outputs:
        out_items = "".join(
            f'<li><a href="{o["url"]}" class="output-link">'
            f'<span class="output-name">{html.escape(o["name"])}</span>'
            f'<span class="output-time">Cập nhật {html.escape(o["mtime_str"])}</span></a></li>'
            for o in outputs
        )
        outputs_section = (
            '<section class="card" aria-labelledby="recent-heading">'
            '<h2 id="recent-heading">Trang đóng vai đã tạo</h2>'
            '<p class="hint">Bấm để mở ngay trang đóng vai tương tác (mọi bản đều là bản nháp chờ trợ giảng duyệt).</p>'
            f'<ul class="output-list">{out_items}</ul></section>'
        )
    else:
        outputs_section = ""

    banner_html = ""
    if error_msg:
        banner_html = (
            '<div class="alert alert-error" role="alert">'
            '<span role="img" aria-label="Lỗi">❌</span> '
            f'<span>{html.escape(error_msg)}</span></div>'
        )

    tabs = [
        ("sample", "Bài lab mẫu"),
        ("github", "Link GitHub repo"),
        ("upload", "Tải .zip / thư mục"),
    ]
    if active_tab not in {t[0] for t in tabs}:
        active_tab = "sample"

    tab_buttons = []
    for tid, label in tabs:
        is_sel = tid == active_tab
        tab_buttons.append(
            f'<button type="button" role="tab" id="tab-{tid}" data-tab="{tid}" '
            f'aria-selected="{"true" if is_sel else "false"}" '
            f'tabindex="{"0" if is_sel else "-1"}">{html.escape(label)}</button>'
        )

    p_sample_hidden = "" if active_tab == "sample" else ' hidden="until-found"'
    p_github_hidden = "" if active_tab == "github" else ' hidden="until-found"'
    p_upload_hidden = "" if active_tab == "upload" else ' hidden="until-found"'

    return f'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Be The Agent · chanme</title>
<style>
  :root {{
    color-scheme: light;
    --bg: #f6f8fc;
    --surface: #ffffff;
    --ink: #18253b;
    --muted: #475569;
    --border: #cbd5e1;
    --accent: #1d4ed8;
    --accent-hover: #1e40af;
    --danger: #c62828;
    --danger-bg: #fef2f2;
    --ok: #15803d;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    line-height: 1.6;
    margin: 0;
    background: var(--bg);
    color: var(--ink);
  }}
  main {{
    max-width: 860px;
    margin: 0 auto;
    padding: 28px 16px 56px;
  }}
  header {{
    margin-block-end: 24px;
  }}
  h1 {{
    margin: 0 0 8px;
    font-size: clamp(1.6rem, 3vw, 2.1rem);
    letter-spacing: -0.02em;
  }}
  .subtitle {{
    margin: 0 0 12px;
    color: var(--muted);
    max-width: 68ch;
  }}
  .meta-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }}
  .pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.875rem;
    padding: 4px 12px;
    border-radius: 999px;
    background: #e0e7ff;
    color: #1e3a8a;
    font-weight: 600;
  }}
  .pill-warn {{
    background: #fef3c7;
    color: #92400e;
  }}
  .card {{
    background: var(--surface);
    border: 1px solid #dbe3f0;
    border-radius: 14px;
    padding: 24px;
    margin-block-end: 20px;
    box-shadow: 0 1px 3px rgb(15 23 42 / 0.05);
  }}
  .tabs-card {{
    padding: 0;
    overflow: hidden;
  }}
  [role="tablist"] {{
    display: flex;
    overflow-x: auto;
    border-block-end: 1px solid #dbe3f0;
    background: #f8fafc;
    scrollbar-width: none;
  }}
  [role="tablist"]::-webkit-scrollbar {{ display: none; }}
  [role="tab"] {{
    position: relative;
    flex: none;
    appearance: none;
    background: transparent;
    border: 0;
    font: inherit;
    font-size: max(1rem, 1em);
    font-weight: 600;
    color: var(--muted);
    padding: 14px 20px;
    min-height: 48px;
    cursor: pointer;
    white-space: nowrap;
  }}
  [role="tab"]:hover {{ color: var(--ink); }}
  [role="tab"]:focus-visible {{
    outline: 3px solid var(--accent);
    outline-offset: -3px;
  }}
  [role="tab"][aria-selected="true"] {{
    color: var(--accent);
  }}
  [role="tab"][aria-selected="true"]::after {{
    content: "";
    position: absolute;
    inset: auto 0 0;
    border-block-end: 3px solid var(--accent);
  }}
  /* Không đặt padding/border/margin lên chính phần tử tabpanel (hidden="until-found") */
  [role="tabpanel"] {{
    margin: 0;
    padding: 0;
    border: 0;
  }}
  .panel-body {{
    padding: 24px;
  }}
  .panel-body h2 {{
    margin: 0 0 8px;
    font-size: 1.15rem;
  }}
  .field {{
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 0.35rem;
    margin-block-end: 1.25rem;
  }}
  label {{
    font-weight: 600;
    display: inline-block;
  }}
  .hint {{
    margin: 0;
    color: var(--muted);
    font-size: 0.9rem;
  }}
  input[type="url"],
  input[type="text"],
  input[type="file"] {{
    font: inherit;
    font-size: max(1rem, 1em);
    padding: 0.7rem 0.85rem;
    min-height: 48px;
    width: 100%;
    border: 1.5px solid #767676;
    border-radius: 8px;
    background: #fff;
    color: var(--ink);
  }}
  input:focus-visible,
  button:focus-visible,
  a:focus-visible {{
    outline: 3px solid var(--accent);
    outline-offset: 2px;
  }}
  :is(input:user-invalid, input.user-invalid-fallback) {{
    border-color: var(--danger);
    background-color: var(--danger-bg);
  }}
  .error-msg {{
    display: none;
    color: var(--danger);
    font-size: 0.9rem;
    margin-top: 0.25rem;
  }}
  :is(input:user-invalid, input.user-invalid-fallback) + .error-msg {{
    display: block;
  }}
  fieldset {{
    border: 1px solid #dbe3f0;
    border-radius: 10px;
    padding: 14px 16px;
    margin: 0 0 1.25rem;
  }}
  legend {{
    font-weight: 700;
    padding: 0 6px;
  }}
  .radio-row {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 8px 0;
  }}
  .radio-row input[type="radio"] {{
    width: 20px;
    height: 20px;
    margin-top: 3px;
    accent-color: var(--accent);
    flex: none;
  }}
  .radio-row label {{
    font-weight: 400;
    cursor: pointer;
  }}
  .meta {{
    color: var(--muted);
    font-size: 0.9rem;
  }}
  .inline-link {{
    color: var(--accent);
    font-weight: 600;
  }}
  .btn-primary {{
    font: inherit;
    font-size: max(1rem, 1em);
    font-weight: 600;
    min-height: 48px;
    padding: 0.75rem 1.4rem;
    background: var(--accent);
    color: #ffffff;
    border: 0;
    border-radius: 8px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    text-decoration: none;
  }}
  .btn-primary:hover {{ background: var(--accent-hover); }}
  .btn-primary:disabled {{
    opacity: 0.7;
    cursor: wait;
  }}
  .btn-secondary {{
    font: inherit;
    font-size: max(1rem, 1em);
    font-weight: 600;
    min-height: 48px;
    padding: 0.65rem 1.1rem;
    background: #f1f5f9;
    color: var(--ink);
    border: 1.5px solid #94a3b8;
    border-radius: 8px;
    cursor: pointer;
  }}
  .btn-secondary:hover {{ background: #e2e8f0; }}
  .upload-grid {{
    display: grid;
    gap: 16px;
  }}
  .divider {{
    text-align: center;
    color: var(--muted);
    font-size: 0.875rem;
    font-weight: 600;
    margin: 4px 0;
  }}
  .status-line {{
    margin-top: 12px;
    font-size: 0.95rem;
    color: #1e40af;
    min-height: 1.4em;
  }}
  .alert {{
    padding: 14px 16px;
    border-radius: 10px;
    margin-block-end: 20px;
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }}
  .alert-error {{
    background: var(--danger-bg);
    border: 1px solid #fecaca;
    color: #991b1b;
  }}
  .result-actions {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    margin: 12px 0 18px;
  }}
  .stats {{
    font-size: 0.9rem;
    color: var(--muted);
    margin: 0 0 14px;
  }}
  pre {{
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    font-size: 0.9rem;
    max-height: 480px;
    overflow: auto;
  }}
  .output-list {{
    list-style: none;
    padding: 0;
    margin: 14px 0 0;
    display: grid;
    gap: 10px;
  }}
  .output-link {{
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    min-height: 48px;
    border: 1px solid #dbe3f0;
    border-radius: 10px;
    text-decoration: none;
    color: var(--ink);
    background: #f8fafc;
  }}
  .output-link:hover {{
    border-color: var(--accent);
    background: #eff6ff;
  }}
  .output-name {{ font-weight: 600; color: var(--accent); }}
  .output-time {{ font-size: 0.875rem; color: var(--muted); }}
  .visually-hidden:where(:not(:focus-within, :active)) {{
    position: absolute !important;
    clip-path: inset(50%) !important;
    overflow: hidden !important;
    width: 1px !important;
    height: 1px !important;
    margin: -1px !important;
    padding: 0 !important;
    border: 0 !important;
    white-space: nowrap !important;
  }}
</style>
</head>
<body>
<main>
  <header>
    <h1>Be The Agent · chanme</h1>
    <p class="subtitle">
      Đưa một bài lab vào → hệ thống chạy workflow kiểm nguồn cố định và tạo <strong>trang web đóng vai</strong> bằng tiếng Việt giúp học viên tự đóng vai AI trước giờ lab. Mọi kết quả đều là bản nháp chờ trợ giảng duyệt.
    </p>
    <div class="meta-row">
      <span class="pill{' pill-warn' if is_fake else ''}">Model: {html.escape(model_label)}{' (giả, không gọi API)' if is_fake else ''}</span>
      <span class="pill">Chỉ đọc · Kiểm trích dẫn file:dòng</span>
    </div>
  </header>

  {banner_html}

  <section class="card tabs-card" aria-label="Chọn nguồn bài lab">
    <div role="tablist" aria-label="Nguồn đầu vào bài lab">
      {"".join(tab_buttons)}
    </div>

    <div role="tabpanel" id="panel-sample" aria-labelledby="tab-sample"{p_sample_hidden}>
      <div class="panel-body">
        <form id="form-sample" method="POST" action="/generate-sample" aria-labelledby="sample-heading">
          <h2 id="sample-heading">Chạy thử trên bài lab mẫu</h2>
          <p class="hint" style="margin-bottom:14px">Chọn một bài lab mẫu để hệ thống đọc đề, sinh tình huống đóng vai bằng AI và kiểm tra từng trích dẫn `file:dòng`.</p>
          <input type="hidden" name="csrf_token" value="{token}">
          <fieldset>
            <legend>Danh sách bài lab mẫu</legend>
            {samples_block}
          </fieldset>
          <button type="submit" class="btn-primary">Tạo trang đóng vai từ lab mẫu</button>
          <div class="status-line" role="status" aria-live="polite"></div>
        </form>
      </div>
    </div>

    <div role="tabpanel" id="panel-github" aria-labelledby="tab-github"{p_github_hidden}>
      <div class="panel-body">
        <form id="form-github" method="POST" action="/generate-github" aria-labelledby="github-heading">
          <h2 id="github-heading">Tạo từ link GitHub repository công khai</h2>
          <input type="hidden" name="csrf_token" value="{token}">
          <div class="field">
            <label for="github-url">URL GitHub repository <span aria-hidden="true">*</span></label>
            <span id="gh-hint" class="hint">Ví dụ: https://github.com/owner/ten-bai-lab (hoặc kèm /tree/main/thu-muc-con). Repo cần ở chế độ Public.</span>
            <input
              type="url"
              id="github-url"
              name="github_url"
              required
              pattern="https://github\\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(/.*)?"
              autocomplete="url"
              autocorrect="off"
              autocapitalize="none"
              spellcheck="false"
              enterkeyhint="go"
              placeholder="https://github.com/owner/repo"
              aria-describedby="gh-hint"
              data-error="gh-error"
              value="{html.escape(github_url, quote=True)}"
            >
            <div id="gh-error" class="error-msg">
              <span role="img" aria-label="Lỗi">❌</span> Nhập đúng đường dẫn bắt đầu bằng https://github.com/owner/repo.
            </div>
          </div>
          <button type="submit" class="btn-primary">Tải repo &amp; tạo trang đóng vai</button>
          <div class="status-line" role="status" aria-live="polite"></div>
        </form>
      </div>
    </div>

    <div role="tabpanel" id="panel-upload" aria-labelledby="tab-upload"{p_upload_hidden}>
      <div class="panel-body">
        <form id="form-upload" method="POST" action="/generate-upload" enctype="multipart/form-data" aria-labelledby="upload-heading">
          <h2 id="upload-heading">Tải bài lab lên từ máy</h2>
          <p class="hint" style="margin-bottom:14px">Hệ thống chỉ đọc các tệp văn bản (<code>.md, .py, .json, .yaml, .txt, .ipynb</code>) và tự động bỏ qua <code>.env</code>, <code>.git</code>, <code>.venv</code>, <code>solution/</code>.</p>
          <input type="hidden" name="csrf_token" value="{token}">
          <div class="upload-grid">
            <div class="field">
              <label for="lab-zip">Cách 1: Tải lên tệp .zip của bài lab</label>
              <span id="zip-hint" class="hint">Tối đa 20 MB. Nén thư mục chứa README.md và mã nguồn bài lab.</span>
              <input type="file" id="lab-zip" name="archive" accept=".zip,application/zip" aria-describedby="zip-hint">
            </div>
            <div class="divider">— HOẶC —</div>
            <div class="field">
              <label for="lab-folder">Cách 2: Chọn trực tiếp thư mục bài lab trên máy</label>
              <span id="folder-hint" class="hint">Trình duyệt chỉ gửi các tệp văn bản hợp lệ, không tải lên .env hay thư mục nặng.</span>
              <input type="file" id="lab-folder" name="folder_files" webkitdirectory directory multiple aria-describedby="folder-hint">
              <span id="folder-summary" class="hint" role="status" aria-live="polite"></span>
            </div>
          </div>
          <button type="submit" class="btn-primary">Tải lên &amp; tạo trang đóng vai</button>
          <div class="status-line" role="status" aria-live="polite"></div>
        </form>
      </div>
    </div>
  </section>

  {result_html}
  {outputs_section}
</main>
<script>
(() => {{
  // 1. Accessible Tabs with roving tabindex, Arrow keys, and hidden="until-found" beforematch sync
  const tablist = document.querySelector('[role="tablist"]');
  const tabs = [...tablist.querySelectorAll('[role="tab"]')];
  const panels = tabs.map((t) => document.getElementById('panel-' + t.dataset.tab));

  const activateTab = (tab, moveFocus = false) => {{
    tabs.forEach((t, i) => {{
      const selected = t === tab;
      t.setAttribute('aria-selected', selected ? 'true' : 'false');
      t.tabIndex = selected ? 0 : -1;
      if (selected) {{
        panels[i].removeAttribute('hidden');
      }} else {{
        panels[i].hidden = 'until-found';
      }}
    }});
    tab.scrollIntoView({{ block: 'nearest', inline: 'nearest' }});
    if (moveFocus) tab.focus();
  }};

  tabs.forEach((tab) => {{
    tab.addEventListener('click', () => activateTab(tab, false));
  }});

  tablist.addEventListener('keydown', (e) => {{
    const idx = tabs.indexOf(document.activeElement);
    if (idx < 0) return;
    let next = idx;
    if (e.key === 'ArrowRight') next = (idx + 1) % tabs.length;
    else if (e.key === 'ArrowLeft') next = (idx - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = tabs.length - 1;
    else return;
    e.preventDefault();
    activateTab(tabs[next], true);
  }});

  panels.forEach((panel, i) => {{
    panel.addEventListener('beforematch', () => activateTab(tabs[i], false));
  }});

  // 2. Sync aria-invalid & aria-describedby with :user-invalid (with fallback)
  const linkError = (el, shown) => {{
    const errorId = el.dataset.error;
    if (!errorId) return;
    const ids = (el.getAttribute('aria-describedby') || '').split(/\\s+/).filter((id) => id && id !== errorId);
    if (shown) ids.push(errorId);
    if (ids.length) el.setAttribute('aria-describedby', ids.join(' '));
    else el.removeAttribute('aria-describedby');
  }};

  const announcer = document.createElement('div');
  announcer.setAttribute('aria-live', 'polite');
  announcer.className = 'visually-hidden';
  document.body.append(announcer);

  const supportsUserInvalid = CSS.supports('selector(:user-invalid)');
  const dirty = new WeakMap();
  const syncAria = (el, announce = false) => {{
    if (!el.matches?.('input[type="url"], input[type="text"]')) return;
    const invalid = supportsUserInvalid
      ? el.matches(':user-invalid')
      : Boolean(dirty.get(el)?.blurred && !el.validity.valid);
    if (!supportsUserInvalid && dirty.get(el)?.blurred) {{
      el.classList.toggle('user-invalid-fallback', invalid);
    }}
    el.setAttribute('aria-invalid', invalid ? 'true' : 'false');
    linkError(el, invalid);
    if (invalid && announce && el.dataset.error) {{
      const errNode = document.getElementById(el.dataset.error);
      if (errNode) {{
        announcer.textContent = '';
        setTimeout(() => {{ announcer.textContent = errNode.textContent.trim(); }}, 300);
      }}
    }}
  }};

  document.querySelectorAll('input[type="url"], input[type="text"]').forEach((el) => syncAria(el));
  document.addEventListener('blur', (e) => {{
    const st = dirty.get(e.target) || {{ interacted: false, blurred: false }};
    st.blurred = true;
    dirty.set(e.target, st);
    syncAria(e.target, true);
  }}, true);
  document.addEventListener('input', (e) => {{
    const st = dirty.get(e.target) || {{ interacted: false, blurred: false }};
    st.interacted = true;
    dirty.set(e.target, st);
    syncAria(e.target, false);
  }});
  document.addEventListener('invalid', (e) => {{
    dirty.set(e.target, {{ interacted: true, blurred: true }});
    syncAria(e.target, false);
  }}, true);

  // 3. Folder upload filtering & loading state on submit
  const ALLOWED_EXT = ['.md', '.py', '.json', '.yaml', '.yml', '.txt', '.ipynb'];
  const SKIP_DIRS = new Set(['.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache', 'solution', 'solutions', 'answers']);
  const SKIP_FILES = new Set(['MISSION_ANSWERS.MD', 'INSTRUCTOR_GUIDE.MD']);

  const folderInput = document.getElementById('lab-folder');
  const zipInput = document.getElementById('lab-zip');
  const folderSummary = document.getElementById('folder-summary');
  let filteredFolderFiles = [];

  const filterFolder = (fileList) => {{
    const kept = [];
    for (const f of fileList) {{
      const rel = (f.webkitRelativePath || f.name).replace(/\\\\/g, '/');
      const parts = rel.split('/').filter(Boolean);
      const dirs = parts.slice(0, -1);
      const fname = parts[parts.length - 1] || '';
      if (dirs.some((d) => d.startsWith('.') || SKIP_DIRS.has(d.toLowerCase()))) continue;
      if (fname.startsWith('.env') || SKIP_FILES.has(fname.toUpperCase())) continue;
      const lower = fname.toLowerCase();
      if (!ALLOWED_EXT.some((ext) => lower.endsWith(ext))) continue;
      if (f.size > 5 * 1024 * 1024) continue;
      kept.push({{ file: f, rel }});
    }}
    return kept;
  }};

  folderInput?.addEventListener('change', () => {{
    filteredFolderFiles = filterFolder(folderInput.files || []);
    if (folderInput.files?.length) {{
      zipInput.value = '';
      folderSummary.textContent = filteredFolderFiles.length
        ? `Đã chọn ${{filteredFolderFiles.length}} tệp văn bản hợp lệ (đã lọc bỏ .env/.git/thư mục hệ thống).`
        : 'Không tìm thấy tệp văn bản hợp lệ (.md, .py, .json, .yaml, .txt, .ipynb) trong thư mục này.';
    }} else {{
      folderSummary.textContent = '';
    }}
  }});

  zipInput?.addEventListener('change', () => {{
    if (zipInput.files?.length) {{
      folderInput.value = '';
      filteredFolderFiles = [];
      folderSummary.textContent = '';
    }}
  }});

  document.querySelectorAll('form').forEach((form) => {{
    form.addEventListener('submit', async (e) => {{
      const btn = form.querySelector('button[type="submit"]');
      const status = form.querySelector('.status-line');

      if (form.id === 'form-upload') {{
        const hasZip = Boolean(zipInput.files && zipInput.files.length > 0);
        const hasFolder = filteredFolderFiles.length > 0;
        if (!hasZip && !hasFolder) {{
          e.preventDefault();
          status.textContent = 'Vui lòng chọn tệp .zip hoặc thư mục bài lab hợp lệ trước khi gửi.';
          zipInput.focus();
          return;
        }}
        if (hasFolder && !hasZip) {{
          e.preventDefault();
          btn.disabled = true;
          btn.textContent = 'Đang phân tích bài lab bằng AI... (có thể mất 15–60 giây)';
          status.textContent = `Đang gửi ${{filteredFolderFiles.length}} tệp và gọi model kiểm nguồn...`;
          const fd = new FormData();
          fd.append('csrf_token', form.querySelector('input[name="csrf_token"]').value);
          const rootName = (filteredFolderFiles[0].rel.split('/')[0] || 'uploaded-lab');
          fd.append('lab_name', rootName);
          for (const item of filteredFolderFiles) {{
            fd.append('relpaths', item.rel);
            fd.append('files', item.file, item.file.name);
          }}
          try {{
            const resp = await fetch('/generate-upload', {{ method: 'POST', body: fd }});
            if (resp.redirected && resp.url) {{
              window.location.href = resp.url;
              return;
            }}
            const pageHtml = await resp.text();
            document.open();
            document.write(pageHtml);
            document.close();
          }} catch (err) {{
            btn.disabled = false;
            btn.textContent = 'Tải lên & tạo trang đóng vai';
            status.textContent = 'Lỗi kết nối khi gửi thư mục: ' + err.message;
          }}
          return;
        }}
      }}

      btn.disabled = true;
      btn.textContent = 'Đang phân tích bài lab bằng AI... (có thể mất 15–60 giây)';
      status.textContent = 'Đang đọc đề, soạn tình huống đóng vai và kiểm tra từng trích dẫn file:dòng...';
    }});
  }});
}})();
</script>
</body>
</html>'''


def _build_result_card(markdown: str, page_url: str, summary: dict) -> str:
    models = ", ".join(summary.get("models") or []) or MODEL_PROVIDER
    stats = (
        f"Model: {models} · Gọi model: {summary.get('model_calls', 0)} lần · "
        f"Công cụ: {summary.get('tool_calls', 0)} lần · "
        f"Token vào/ra: {summary.get('tokens_in', 0):,} / {summary.get('tokens_out', 0):,} · "
        f"Thời gian: {summary.get('elapsed_s', 0)}s"
    )
    action_btn = (
        f'<a href="{page_url}" class="btn-primary">Mở trang đóng vai tương tác →</a>'
        if page_url else ""
    )
    return (
        '<article class="card" aria-labelledby="result-heading">'
        '<h2 id="result-heading">Kết quả tạo bản nháp</h2>'
        f'<p class="stats">{html.escape(stats)}</p>'
        f'<div class="result-actions">{action_btn}</div>'
        f'<pre>{html.escape(markdown)}</pre>'
        '</article>'
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "BeTheAgent/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write("%s - %s\n" % (self._client_ip(), fmt % args))
        sys.stdout.flush()

    def _client_ip(self) -> str:
        cf_ip = (self.headers.get("CF-Connecting-IP") or "").strip()
        if cf_ip and self.client_address[0] in ("127.0.0.1", "::1"):
            return cf_ip
        return self.client_address[0]

    def _send_bytes(self, data: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, body: str, status: int = 200) -> None:
        self._send_bytes(body.encode("utf-8"), "text/html; charset=utf-8", status)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        self._send_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _read_body(self, limit: int) -> bytes:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length không hợp lệ.") from exc
        if size <= 0:
            raise ValueError("Dữ liệu gửi lên trống.")
        if size > limit:
            raise ValueError(f"Dữ liệu vượt quá giới hạn {limit // (1024 * 1024)} MB.")
        return self.rfile.read(size)

    def do_GET(self) -> None:
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        if path == "/health":
            self._send_json({
                "status": "ok",
                "model_provider": MODEL_PROVIDER,
                "model_name": MODEL_NAME,
                "samples": len(_list_samples()),
            })
            return
        if path == "/":
            self._send_html(_render_home())
            return
        if path.startswith("/job/"):
            job_id = path[len("/job/"):].strip("/")
            with _JOBS_LOCK:
                job = dict(_JOBS[job_id]) if job_id in _JOBS else None
            if not job:
                self.send_error(404)
                return
            self._send_html(_render_job_page(job))
            return
        if path.startswith("/api/jobs/"):
            job_id = path[len("/api/jobs/"):].strip("/")
            with _JOBS_LOCK:
                job = dict(_JOBS[job_id]) if job_id in _JOBS else None
            if not job:
                self._send_json({"error": "not_found"}, status=404)
                return
            self._send_json({
                "id": job["id"],
                "status": job["status"],
                "display_name": job["display_name"],
                "page_url": job["page_url"],
                "error": job["error"],
            })
            return
        if path.startswith("/output/"):
            target = (ROOT / path.lstrip("/")).resolve()
            if target.parent == OUTPUT_DIR and target.suffix == ".html" and target.is_file():
                raw = target.read_text(encoding="utf-8", errors="replace")
                self._send_html(_enhance_roleplay_html(raw))
                return
            self.send_error(404)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path not in ("/generate-sample", "/generate-github", "/generate-upload"):
            self.send_error(404)
            return

        allowed, retry_after = _check_rate_limit(self._client_ip())
        if not allowed:
            self._send_html(
                _render_home(
                    error_msg=f"Bạn đã gửi quá nhiều yêu cầu liên tiếp. Vui lòng thử lại sau {retry_after} giây."
                ),
                status=429,
            )
            return

        if path == "/generate-sample":
            self._handle_sample()
        elif path == "/generate-github":
            self._handle_github()
        elif path == "/generate-upload":
            self._handle_upload()

    def _handle_sample(self) -> None:
        try:
            body = self._read_body(32 * 1024)
            form = urllib.parse.parse_qs(body.decode("utf-8"))
            if not _verify_csrf_token(form.get("csrf_token", [""])[0]):
                self._send_html(_render_home(active_tab="sample", error_msg="Phiên biểu mẫu đã hết hạn, vui lòng tải lại trang."), status=403)
                return
            sample_id = form.get("sample", [""])[0].strip()
            sample_dir = (SAMPLES_DIR / sample_id).resolve()
            if not sample_id or sample_dir.parent != SAMPLES_DIR or not sample_dir.is_dir():
                raise ValueError("Bài lab mẫu không tồn tại.")
            job_id = _start_job(sample_dir, sample_id, f"sample:{sample_id}")
            self._redirect(f"/job/{job_id}")
        except Exception as exc:
            self._send_html(_render_home(active_tab="sample", error_msg=str(exc)), status=400)

    def _handle_github(self) -> None:
        gh_url = ""
        tmp_dir: Path | None = None
        try:
            body = self._read_body(32 * 1024)
            form = urllib.parse.parse_qs(body.decode("utf-8"))
            if not _verify_csrf_token(form.get("csrf_token", [""])[0]):
                self._send_html(_render_home(active_tab="github", error_msg="Phiên biểu mẫu đã hết hạn, vui lòng tải lại trang."), status=403)
                return
            gh_url = form.get("github_url", [""])[0].strip()
            zip_bytes, lab_name, subdir = _download_github_zip(gh_url)
            tmp_dir = Path(tempfile.mkdtemp(prefix="chanme-gh-"))
            base = tmp_dir / lab_name
            base.mkdir(parents=True, exist_ok=True)
            written = _safe_extract_zip(zip_bytes, base)
            if written == 0:
                raise ValueError("Không tìm thấy tệp văn bản bài lab hợp lệ trong repository này.")
            target_dir = base
            if subdir:
                candidate = (base / subdir).resolve()
                if str(candidate).startswith(str(base.resolve())) and candidate.is_dir():
                    target_dir = candidate
            job_id = _start_job(target_dir, lab_name, f"github:{lab_name}", cleanup_dir=tmp_dir)
            tmp_dir = None  # worker sẽ dọn dẹp sau khi chạy xong
            self._redirect(f"/job/{job_id}")
        except Exception as exc:
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            self._send_html(_render_home(active_tab="github", github_url=gh_url, error_msg=str(exc)), status=400)

    def _handle_upload(self) -> None:
        tmp_dir: Path | None = None
        try:
            ctype = self.headers.get("Content-Type") or ""
            if "multipart/form-data" not in ctype.lower():
                raise ValueError("Yêu cầu tải lên cần định dạng multipart/form-data.")
            body = self._read_body(MAX_UPLOAD_BYTES)
            fields, files = _parse_multipart(ctype, body)
            token = (fields.get("csrf_token") or [""])[0]
            if not _verify_csrf_token(token):
                self._send_html(_render_home(active_tab="upload", error_msg="Phiên biểu mẫu đã hết hạn, vui lòng tải lại trang."), status=403)
                return
            if not files:
                raise ValueError("Vui lòng chọn tệp .zip hoặc thư mục bài lab.")

            zip_entry = next(((fn, data) for field, fn, data in files if field == "archive" and data), None)
            tmp_dir = Path(tempfile.mkdtemp(prefix="chanme-up-"))
            if zip_entry:
                fname, data = zip_entry
                lab_name = _sanitize_slug(Path(fname).stem)
                lab_dir = tmp_dir / lab_name
                lab_dir.mkdir(parents=True, exist_ok=True)
                written = _safe_extract_zip(data, lab_dir)
            else:
                relpaths = fields.get("relpaths") or []
                uploaded = [(fn, data) for field, fn, data in files if field in ("files", "folder_files")]
                raw_root = (fields.get("lab_name") or ["uploaded-lab"])[0]
                lab_name = _sanitize_slug(raw_root)
                lab_dir = tmp_dir / lab_name
                lab_dir.mkdir(parents=True, exist_ok=True)
                dest_resolved = lab_dir.resolve()
                written = 0
                total_bytes = 0
                for idx, (fn, data) in enumerate(uploaded):
                    rel = relpaths[idx] if idx < len(relpaths) else fn
                    norm = rel.replace("\\", "/").lstrip("/")
                    parts = tuple(p for p in norm.split("/") if p)
                    if len(parts) > 1 and parts[0] == raw_root:
                        parts = parts[1:]
                    if not _is_allowed_relpath(parts):
                        continue
                    if written >= MAX_FILES:
                        break
                    total_bytes += len(data)
                    if total_bytes > MAX_EXTRACT_BYTES:
                        raise ValueError("Tổng dung lượng tệp tải lên vượt quá 30 MB.")
                    target = (lab_dir / Path(*parts)).resolve()
                    if not str(target).startswith(str(dest_resolved) + os.sep):
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    written += 1

            if written == 0:
                raise ValueError("Không có tệp văn bản bài lab hợp lệ (.md, .py, .json, .yaml, .txt, .ipynb).")
            job_id = _start_job(lab_dir, lab_name, f"upload:{lab_name}", cleanup_dir=tmp_dir)
            tmp_dir = None  # worker sẽ dọn dẹp sau khi chạy xong
            self._redirect(f"/job/{job_id}")
        except Exception as exc:
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            self._send_html(_render_home(active_tab="upload", error_msg=str(exc)), status=400)


def main() -> None:
    parser = argparse.ArgumentParser(description="Be The Agent web server")
    parser.add_argument("--host", default=os.environ.get("CHANME_BIND", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CHANME_PORT", "8795")))
    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"Be The Agent web server: http://{args.host}:{args.port} · model={MODEL_PROVIDER}/{MODEL_NAME or '-'}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
