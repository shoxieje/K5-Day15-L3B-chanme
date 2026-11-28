"""Web server cho Be The Agent (chanme) — chỉ dùng thư viện chuẩn Python 3.10+.

Hỗ trợ 3 cách đưa bài lab vào:
  1. Chọn bài lab mẫu có sẵn (deploy/sample_labs/) để chạy thử ngay
  2. Dán link GitHub repository công khai (tải archive zip trực tiếp)
  3. Tải lên file .zip hoặc chọn thư mục bài lab từ máy người dùng

Mỗi request chọn một chế độ (allowlist, thiếu ⇒ before_lab):
  - before_lab "Chuẩn bị lab": luồng cũ, answer(<đường dẫn>) → "Trang đóng vai: output/<x>.html"
  - after_lab  "Hiểu bài đã làm": chỉ nhận .md ở gốc repo, answer("@learning-v1 {json}")
    → "Trang học lại: output/learning-<12hex>-<8hex>.html" (xem docs/design/learning-html-contract.md)

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

try:  # module của luồng after_lab; thiếu thì web vẫn chạy (không đăng ký manifest)
    from root_markdown import register_ingest_manifest  # noqa: E402
except ImportError:  # pragma: no cover - phụ thuộc tiến độ module khác
    def register_ingest_manifest(repo_path: str, manifest: dict) -> None:  # type: ignore[misc]
        return None

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

# Chế độ theo từng request (không có trạng thái mode toàn cục).
MODE_BEFORE = "before_lab"
MODE_AFTER = "after_lab"
MODE_LABELS = {MODE_BEFORE: "Chuẩn bị lab", MODE_AFTER: "Hiểu bài đã làm"}
DEFAULT_MODE = MODE_BEFORE

# Giới hạn thu nhận Markdown gốc cho after_lab (contract §3).
LEARNING_MAX_FILE_BYTES = 512 * 1024      # 512 KiB/tệp
LEARNING_MAX_TOTAL_BYTES = 2 * 1024 * 1024  # 2 MiB tổng
LEARNING_PAGE_RE = re.compile(r"^learning-[0-9a-f]{12}-[0-9a-f]{8}\.html$")
OUTPUT_PAGE_RE = re.compile(r"^output/([A-Za-z0-9_-]+\.html)$")
LEARNING_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
)
RESULT_MARKERS = {MODE_BEFORE: "Trang đóng vai: ", MODE_AFTER: "Trang học lại: "}
EXCLUDE_REASON_LABELS = {
    "over_limit": "vượt 512 KiB/tệp",
    "over_total_limit": "vượt tổng 2 MiB",
    "collision": "trùng tên khi bỏ qua hoa/thường",
    "symlink": "là liên kết tượng trưng (symlink)",
    "not_regular": "không phải tệp thường hoặc tên không an toàn",
}
_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_UNSAFE_NAME_CHARS = set('<>:"|?*') | {chr(c) for c in range(32)}

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


def _parse_mode(values: list[str] | None) -> str:
    """Allowlist mode theo request. Thiếu field ⇒ before_lab (request cũ giữ nghĩa); giá trị lạ ⇒ ValueError (400)."""
    if not values:
        return DEFAULT_MODE
    value = (values[0] or "").strip()
    if value not in MODE_LABELS:
        raise ValueError("Chế độ không hợp lệ. Chỉ nhận “Chuẩn bị lab” hoặc “Hiểu bài đã làm”.")
    return value


def _archive_entry_parts(raw: str) -> tuple[str, ...]:
    """Tách đường dẫn entry thành các thành phần; ValueError nếu tuyệt đối, ổ đĩa, UNC/backslash đầu, `..` hoặc `:`."""
    shown = (raw or "")[:120]
    if "\x00" in (raw or ""):
        raise ValueError(f"Tệp nén có đường dẫn chứa ký tự rỗng, đã từ chối toàn bộ: {shown!r}")
    if raw.startswith(("/", "\\")):
        raise ValueError(f"Tệp nén có đường dẫn tuyệt đối hoặc UNC, đã từ chối toàn bộ để an toàn: {shown}")
    if _DRIVE_RE.match(raw):
        raise ValueError(f"Tệp nén có đường dẫn kèm ổ đĩa (vd C:), đã từ chối toàn bộ để an toàn: {shown}")
    parts = tuple(p for p in raw.replace("\\", "/").split("/") if p and p != ".")
    for part in parts:
        if part == "..":
            raise ValueError(f"Tệp nén có đường dẫn chứa “..” (zip-slip), đã từ chối toàn bộ để an toàn: {shown}")
        if ":" in part:
            raise ValueError(f"Tệp nén có tên chứa “:” (ổ đĩa/luồng dữ liệu ẩn), đã từ chối toàn bộ để an toàn: {shown}")
    return parts


_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


def _is_safe_root_name(name: str) -> bool:
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        return False
    if any(ch in _UNSAFE_NAME_CHARS for ch in name) or name[-1] in (" ", "."):
        return False
    return name.split(".", 1)[0].upper() not in _WIN_RESERVED


def _is_root_markdown_name(name: str) -> bool:
    return name.lower().endswith(".md") and not name.startswith(".")


def _select_root_markdown(candidates: list[dict], dest_root: Path) -> tuple[list[dict], list[dict]]:
    """Ghi các Markdown gốc hợp lệ vào dest_root; mọi file .md bị loại đều có lý do (không lặng lẽ bỏ).

    candidate = {"name", "size", "kind": "file"|"symlink"|"other", "read": callable(limit) -> bytes}
    """
    accepted: list[dict] = []
    excluded: list[dict] = []
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for cand in candidates:
        groups[cand["name"].casefold()].append(cand)
    singles = []
    for members in groups.values():
        if len(members) > 1:
            excluded.extend({"name": m["name"], "reason": "collision"} for m in members)
        else:
            singles.append(members[0])

    dest_resolved = dest_root.resolve()
    total = 0
    total_exceeded = False
    for cand in sorted(singles, key=lambda c: c["name"]):
        name = cand["name"]
        if cand["kind"] == "symlink":
            excluded.append({"name": name, "reason": "symlink"})
            continue
        if cand["kind"] != "file" or not _is_safe_root_name(name):
            excluded.append({"name": name, "reason": "not_regular"})
            continue
        if cand["size"] > LEARNING_MAX_FILE_BYTES:
            excluded.append({"name": name, "reason": "over_limit"})
            continue
        if total_exceeded or len(accepted) >= MAX_FILES or total + cand["size"] > LEARNING_MAX_TOTAL_BYTES:
            total_exceeded = True
            excluded.append({"name": name, "reason": "over_total_limit"})
            continue
        data = cand["read"](LEARNING_MAX_FILE_BYTES + 1)
        if len(data) > LEARNING_MAX_FILE_BYTES:  # kích thước khai báo trong zip có thể sai
            excluded.append({"name": name, "reason": "over_limit"})
            continue
        if total + len(data) > LEARNING_MAX_TOTAL_BYTES:
            total_exceeded = True
            excluded.append({"name": name, "reason": "over_total_limit"})
            continue
        if total + len(data) > MAX_EXTRACT_BYTES:
            raise ValueError("Dung lượng bài lab sau giải nén vượt quá giới hạn 30 MB.")
        target = (dest_root / name).resolve()
        if target.parent != dest_resolved:
            excluded.append({"name": name, "reason": "not_regular"})
            continue
        target.write_bytes(data)
        total += len(data)
        accepted.append({"name": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    excluded.sort(key=lambda e: (e["name"], e["reason"]))
    return accepted, excluded


def _ingest_zip_after_lab(raw_bytes: bytes, dest_root: Path, channel: str = "zip") -> dict:
    """after_lab: kiểm mọi đường dẫn trước khi giải nén, bỏ đúng một lớp thư mục bọc, chỉ lấy .md ở gốc repo.

    Trả manifest {"channel", "wrapper_stripped", "accepted", "excluded", "out_of_scope_count"}.
    """
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("Tệp .zip vượt quá giới hạn 20 MB.")
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError("Tệp .zip không hợp lệ hoặc bị hỏng.") from exc

    with zf:
        entries = []
        for info in zf.infolist():
            parts = _archive_entry_parts(info.filename)  # từ chối toàn bộ archive nếu có path nguy hiểm
            if not parts:
                continue
            unix_type = (info.external_attr >> 16) & 0o170000
            entries.append((info, parts, info.is_dir() or unix_type == 0o040000, unix_type))
        files = [e for e in entries if not e[2]]
        if not files:
            raise ValueError("Tệp .zip trống, không có tệp nào.")

        top_dirs = {parts[0] for _, parts, _, _ in entries}
        strip_top = len(top_dirs) == 1 and all(len(parts) > 1 for _, parts, _, _ in files)

        out_of_scope = 0
        candidates = []
        for info, parts, _, unix_type in files:
            rel = parts[1:] if strip_top else parts
            if len(rel) != 1 or not _is_root_markdown_name(rel[0]):
                out_of_scope += 1
                continue
            kind = "symlink" if unix_type == 0o120000 else ("file" if unix_type in (0, 0o100000) else "other")

            def _read(limit: int, _info=info) -> bytes:
                try:
                    with zf.open(_info) as fh:
                        return fh.read(limit)
                except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
                    raise ValueError(f"Không đọc được tệp trong .zip (hỏng hoặc bị mã hóa): {_info.filename[:120]}") from exc

            candidates.append({"name": rel[0], "size": info.file_size, "kind": kind, "read": _read})

        accepted, excluded = _select_root_markdown(candidates, dest_root)

    return {
        "channel": channel,
        "wrapper_stripped": strip_top,
        "accepted": accepted,
        "excluded": excluded,
        "out_of_scope_count": out_of_scope,
    }


def _ingest_folder_upload(
    mode: str, items: list[tuple[str, bytes]], raw_root: str, lab_dir: Path
) -> tuple[int, dict | None]:
    """Ghi các tệp từ folder picker vào lab_dir theo mode. Trả (số tệp đã ghi, manifest hoặc None cho before_lab).

    before_lab: đúng quy tắc cũ (`_is_allowed_relpath`). after_lab: bỏ thành phần đầu chỉ khi bằng lab_name gửi lên,
    sau đó bắt buộc còn đúng một thành phần là tệp .md (không áp SKIP_FILES).
    """
    if mode == MODE_AFTER:
        candidates = []
        out_of_scope = 0
        for rel, data in items:
            parts = _archive_entry_parts(rel)
            if len(parts) > 1 and parts[0] == raw_root:
                parts = parts[1:]
            if len(parts) != 1 or not _is_root_markdown_name(parts[0]):
                out_of_scope += 1
                continue
            candidates.append({
                "name": parts[0], "size": len(data), "kind": "file",
                "read": lambda limit, _d=data: _d[:limit],
            })
        accepted, excluded = _select_root_markdown(candidates, lab_dir)
        manifest = {
            "channel": "folder",
            "wrapper_stripped": False,
            "accepted": accepted,
            "excluded": excluded,
            "out_of_scope_count": out_of_scope,
        }
        return len(accepted), manifest

    dest_resolved = lab_dir.resolve()
    written = 0
    total_bytes = 0
    for rel, data in items:
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
    return written, None


def _no_root_markdown_error(manifest: dict) -> ValueError:
    msg = (
        "Không tìm thấy tệp Markdown (.md) hợp lệ nào nằm trực tiếp ở thư mục gốc repo. "
        "Chế độ “Hiểu bài đã làm” chỉ đọc các tệp .md ở cấp gốc (không đọc thư mục con, không cần README hay .py)."
    )
    excluded = manifest.get("excluded") or []
    if excluded:
        shown = "; ".join(
            f"{e['name']} ({EXCLUDE_REASON_LABELS.get(e['reason'], e['reason'])})" for e in excluded[:10]
        )
        msg += f" Các tệp .md bị loại: {shown}."
    return ValueError(msg)


def _download_github_zip(url: str, mode: str = DEFAULT_MODE) -> tuple[bytes, str, str]:
    """Tải archive ZIP từ GitHub repo công khai. Trả về (zip_bytes, lab_name, subdir)."""
    m = GITHUB_URL_RE.fullmatch(url.strip())
    if not m:
        raise ValueError("Link GitHub chưa đúng dạng https://github.com/<owner>/<repo>")
    owner, repo, tree_part = m.group(1), m.group(2), m.group(3)
    if mode == MODE_AFTER and (tree_part or "/tree/" in url):
        raise ValueError(
            "Chế độ Hiểu bài đã làm chỉ nhận link gốc repo, chưa hỗ trợ thư mục con "
            "(hãy dùng dạng https://github.com/owner/repo, không có /tree/...)."
        )
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
        is_learning = bool(LEARNING_PAGE_RE.fullmatch(p.name))
        pages.append({
            "name": p.stem,
            "filename": p.name,
            "kind_label": "Trang học lại" if is_learning else "Trang đóng vai",
            "is_learning": is_learning,
            "download_url": f"/download/{urllib.parse.quote(p.name)}" if is_learning else "",
            "url": f"/output/{urllib.parse.quote(p.name)}",
            "mtime": stat.st_mtime,
            "mtime_str": time.strftime("%d/%m/%Y %H:%M", time.localtime(stat.st_mtime)),
        })
    pages.sort(key=lambda item: item["mtime"], reverse=True)
    return pages[:20]


class JobCancelled(Exception):
    """Job bị hủy khi còn chờ lượt; answer() chưa được gọi."""


def _agent_input(lab_dir: Path, mode: str) -> str:
    """Input cho answer(): before_lab giữ đường dẫn thuần; after_lab dùng prefix @learning-v1 + json.dumps."""
    if mode == MODE_AFTER:
        return "@learning-v1 " + json.dumps({"repo_path": str(lab_dir)}, ensure_ascii=False)
    return str(lab_dir)


def _parse_result_page(text: str, mode: str) -> str:
    """Lấy URL trang từ dòng marker theo mode; chỉ nhận output/<tên an toàn>.html (after_lab: learning-*.html)."""
    marker = RESULT_MARKERS.get(mode, RESULT_MARKERS[MODE_BEFORE])
    if marker not in text:
        return ""
    tail = text.rsplit(marker, 1)[1].strip()
    page_rel = tail.splitlines()[0].strip() if tail else ""
    m = OUTPUT_PAGE_RE.fullmatch(page_rel)
    if not m:
        return ""
    name = m.group(1)
    if mode == MODE_AFTER and not LEARNING_PAGE_RE.fullmatch(name):
        return ""
    return "/output/" + urllib.parse.quote(name)


def _run_agent(
    lab_dir: Path,
    display_name: str,
    case_id: str,
    mode: str = DEFAULT_MODE,
    on_acquired=None,
) -> tuple[str, str, dict]:
    """Chạy answer() tuần tự (an toàn cho tracing._case) và trả (markdown, page_url, summary).

    on_acquired: gọi ngay sau khi lấy được _AGENT_LOCK; trả False ⇒ JobCancelled, không gọi answer().
    """
    if mode not in MODE_LABELS:
        raise ValueError("Chế độ không hợp lệ.")
    agent_input = _agent_input(lab_dir, mode)
    with _AGENT_LOCK:
        if on_acquired is not None and on_acquired() is False:
            raise JobCancelled()
        t0 = time.perf_counter()  # thời gian chạy, không tính thời gian chờ lượt
        tracing.begin(case_id)
        try:
            raw = answer(agent_input)["output"]
        finally:
            summary, _ = tracing.end()
    summary["elapsed_s"] = round(time.perf_counter() - t0, 1)
    # Ẩn đường dẫn thư mục tạm trên server khỏi markdown hiển thị cho người dùng (cả dạng JSON-escape / POSIX)
    cleaned = raw
    lab_str = str(lab_dir)
    variants = {lab_str, json.dumps(lab_str, ensure_ascii=False)[1:-1], lab_dir.as_posix()}
    for variant in sorted((v for v in variants if v), key=len, reverse=True):
        cleaned = cleaned.replace(variant, display_name)
    page_url = _parse_result_page(cleaned, mode)
    return cleaned, page_url, summary


def _start_job(
    lab_dir: Path,
    display_name: str,
    case_id: str,
    cleanup_dir: Path | None = None,
    mode: str = DEFAULT_MODE,
    ingest: dict | None = None,
) -> str:
    """Tạo job chạy nền để trả HTTP 303 ngay lập tức (tránh lỗi Cloudflare 524 khi AI mất >100s)."""
    if mode not in MODE_LABELS:
        raise ValueError("Chế độ không hợp lệ.")
    job_id = secrets.token_urlsafe(12)
    job = {
        "id": job_id,
        "mode": mode,
        "status": "queued",
        "cancel_requested": False,
        "display_name": display_name,
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "markdown": "",
        "page_url": "",
        "download_url": "",
        "summary": {},
        "ingest": _ingest_summary(ingest),
        "error": "",
        "_cleanup_dir": cleanup_dir,
    }
    with _JOBS_LOCK:
        _JOBS[job_id] = job
        if len(_JOBS) > MAX_JOB_HISTORY:
            oldest = sorted(_JOBS.items(), key=lambda kv: kv[1]["created_at"])[: len(_JOBS) - MAX_JOB_HISTORY]
            for old_id, _ in oldest:
                if _JOBS[old_id]["status"] in ("done", "error", "cancelled"):
                    _JOBS.pop(old_id, None)

    def _on_acquired() -> bool:
        # Chỉ chuyển sang running khi đã thật sự có lượt (giữ _AGENT_LOCK); kiểm cờ hủy cùng khóa job.
        with _JOBS_LOCK:
            if job["cancel_requested"]:
                return False
            job["status"] = "running"
            job["started_at"] = time.time()
            return True

    def _worker() -> None:
        try:
            md, page_url, summary = _run_agent(lab_dir, display_name, case_id, mode, on_acquired=_on_acquired)
            download_url = ""
            if mode == MODE_AFTER and page_url:
                download_url = "/download/" + page_url.rsplit("/", 1)[1]
            with _JOBS_LOCK:
                job["status"] = "done"
                job["markdown"] = md
                job["page_url"] = page_url
                job["download_url"] = download_url
                job["summary"] = summary
                job["finished_at"] = time.time()
        except JobCancelled:
            with _JOBS_LOCK:
                job["status"] = "cancelled"
                job["finished_at"] = job["finished_at"] or time.time()
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


def _cancel_job(job_id: str) -> str:
    """Hủy job khi còn queued. Trả "cancelled", "not_found" hoặc "not_cancellable"."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return "not_found"
        if job["status"] != "queued" or job["cancel_requested"]:
            return "not_cancellable"
        job["cancel_requested"] = True
        job["status"] = "cancelled"
        job["finished_at"] = time.time()
        cleanup_dir = job.get("_cleanup_dir")
    # Worker chưa gọi answer (chưa qua _on_acquired) nên có thể dọn thư mục tạm ngay.
    if cleanup_dir is not None:
        shutil.rmtree(cleanup_dir, ignore_errors=True)
    return "cancelled"


def _ingest_summary(manifest: dict | None) -> dict:
    """Tóm tắt manifest để hiển thị trên trang job (chỉ tên tệp + lý do, không nội dung)."""
    if not manifest:
        return {}
    return {
        "channel": manifest.get("channel", ""),
        "accepted": [a["name"] for a in manifest.get("accepted", [])],
        "excluded": [(e["name"], e["reason"]) for e in manifest.get("excluded", [])],
        "out_of_scope_count": int(manifest.get("out_of_scope_count", 0)),
    }


def _register_and_start(
    lab_dir: Path,
    display_name: str,
    case_id: str,
    manifest: dict,
    cleanup_dir: Path | None = None,
) -> str:
    """after_lab: đăng ký manifest với đúng repo_path sẽ truyền trong JSON, rồi tạo job."""
    register_ingest_manifest(str(lab_dir), manifest)
    return _start_job(lab_dir, display_name, case_id, cleanup_dir=cleanup_dir, mode=MODE_AFTER, ingest=manifest)


def _render_ingest_block(ingest: dict) -> str:
    if not ingest:
        return ""
    accepted = ingest.get("accepted") or []
    excluded = ingest.get("excluded") or []
    items = "".join(f"<li><code>{html.escape(n)}</code></li>" for n in accepted)
    excl = "".join(
        f"<li><code>{html.escape(n)}</code> — {html.escape(EXCLUDE_REASON_LABELS.get(r, r))}</li>" for n, r in excluded
    )
    block = (
        '<details class="ingest"><summary>'
        f'Đã nhận {len(accepted)} tệp Markdown ở gốc repo · loại {len(excluded)} · '
        f'{int(ingest.get("out_of_scope_count", 0))} tệp khác ngoài phạm vi</summary>'
        f'<ul>{items}</ul>'
    )
    if excl:
        block += f'<p class="hint">Tệp .md bị loại (có lý do):</p><ul>{excl}</ul>'
    return block + "</details>"


def _render_job_page(job: dict) -> str:
    status = job["status"]
    mode = job.get("mode") or DEFAULT_MODE
    mode_label = html.escape(MODE_LABELS.get(mode, mode))
    name = html.escape(job["display_name"])
    jid = html.escape(job["id"], quote=True)
    elapsed = round(time.time() - (job["started_at"] or job["created_at"]), 1)
    refresh_meta = '<meta http-equiv="refresh" content="4">' if status in ("queued", "running") else ""
    ingest_block = _render_ingest_block(job.get("ingest") or {})

    if status in ("queued", "running"):
        if status == "queued":
            status_label = "Đang chờ lượt xử lý..."
        elif mode == MODE_AFTER:
            status_label = "Đang đọc Markdown ở gốc repo & dựng trang học lại..."
        else:
            status_label = "Đang phân tích bài lab & kiểm trích dẫn bằng Gemini..."
        if mode == MODE_AFTER:
            detail = (
                "Hệ thống đang đọc toàn bộ tệp Markdown ở gốc repo, đối chiếu nguồn <code>file:dòng</code> và dựng "
                "trang học lại (có thể mất vài phút). Trang sẽ tự cập nhật khi hoàn tất."
            )
        else:
            detail = (
                "Hệ thống đang đọc đề, soạn tình huống đóng vai và tự kiểm tra mọi trích dẫn <code>file:dòng</code> "
                "(có thể mất 30–120 giây). Trang sẽ tự cập nhật ngay khi hoàn tất."
            )
        if status == "queued":
            detail = (
                "Đang có bài khác được xử lý; job của bạn sẽ bắt đầu khi tới lượt. "
                "Bạn có thể hủy khi job còn đang chờ."
            )
        cancel_form = ""
        if status == "queued":
            cancel_form = (
                f'<form method="POST" action="/job/{jid}/cancel" class="cancel-form">'
                f'<input type="hidden" name="csrf_token" value="{_make_csrf_token()}">'
                '<button type="submit" class="btn-secondary">Hủy job đang chờ</button>'
                '</form>'
            )
        body_block = (
            '<section class="card" aria-live="polite">'
            f'<h2>{html.escape(status_label)}</h2>'
            f'<p class="hint">Bài lab: <strong>{name}</strong> · Chế độ: <strong>{mode_label}</strong> · '
            f'Trạng thái job: <code>{html.escape(status)}</code> · Đã qua: <span id="elapsed">{elapsed}</span>s</p>'
            f'<p class="hint">{detail}</p>'
            '<progress aria-label="Đang xử lý bài lab" style="width:100%;height:14px;margin-top:12px"></progress>'
            f'{cancel_form}'
            f'{ingest_block}'
            '</section>'
            f'<script>'
            f'const started={job["created_at"]};const initial="{html.escape(status)}";'
            f'const el=document.getElementById("elapsed");'
            f'setInterval(()=>{{if(el)el.textContent=((Date.now()/1000)-started).toFixed(1);}},500);'
            f'async function poll(){{try{{const r=await fetch("/api/jobs/{jid}",{{cache:"no-store"}});'
            f'if(!r.ok)return;const d=await r.json();'
            f'if(d.status!==initial){{location.reload();return;}}}}catch(_e){{}}'
            f'setTimeout(poll,2500);}}setTimeout(poll,2000);'
            f'</script>'
        )
    elif status == "done":
        body_block = _build_result_card(
            job["markdown"], job["page_url"], job["summary"],
            mode=mode, download_url=job.get("download_url", ""),
        ) + (f'<section class="card">{ingest_block}</section>' if ingest_block else "")
    elif status == "cancelled":
        body_block = (
            '<section class="card" role="status">'
            f'<h2>Đã hủy job</h2><p class="hint">Job cho <strong>{name}</strong> (chế độ {mode_label}) đã được hủy '
            'trước khi chạy; không gọi model và đã xóa tệp tạm.</p></section>'
        )
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
  .btn-primary:focus-visible,.btn-secondary:focus-visible {{ outline:3px solid var(--accent); outline-offset:2px; }}
  .btn-secondary {{ font:inherit; font-weight:600; min-height:48px; padding:.65rem 1.1rem; background:#f1f5f9; color:var(--ink); border:1.5px solid #94a3b8; border-radius:8px; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; }}
  .btn-secondary:hover {{ background:#e2e8f0; }}
  .cancel-form {{ margin-top:16px; }}
  .ingest {{ margin-top:16px; }}
  .ingest summary {{ cursor:pointer; font-weight:600; min-height:44px; display:flex; align-items:center; }}
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
    <span class="hint">Bài lab: <strong>{name}</strong> · Chế độ: <strong>{mode_label}</strong></span>
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


def _mode_fieldset(form_key: str, selected_mode: str) -> str:
    """Nhóm radio chọn chế độ cho từng form (fieldset/legend, mặc định before_lab)."""
    if selected_mode not in MODE_LABELS:
        selected_mode = DEFAULT_MODE
    hints = {
        MODE_BEFORE: "Đọc đề và tạo trang đóng vai trước giờ lab (giữ bộ lọc cũ, bỏ tệp bài làm).",
        MODE_AFTER: "Đọc mọi tệp .md ở gốc repo đã làm xong (kể cả MISSION_ANSWERS.md, INSTRUCTOR_GUIDE.md) và tạo trang học lại.",
    }
    rows = []
    for value, label in MODE_LABELS.items():
        rid = f"mode-{form_key}-{value}"
        checked = " checked" if value == selected_mode else ""
        rows.append(
            f'<div class="radio-row">'
            f'<input type="radio" id="{rid}" name="mode" value="{value}"{checked} aria-describedby="{rid}-hint">'
            f'<label for="{rid}"><strong>{html.escape(label)}</strong>'
            f'<span id="{rid}-hint" class="meta"> — {html.escape(hints[value])}</span></label>'
            f'</div>'
        )
    return (
        f'<fieldset class="mode-fieldset" data-mode-group="{form_key}">'
        '<legend>Mục đích sử dụng</legend>'
        + "".join(rows)
        + '</fieldset>'
    )


def _render_home(
    *,
    active_tab: str = "sample",
    result_html: str = "",
    error_msg: str = "",
    github_url: str = "",
    selected_sample: str = "",
    selected_mode: str = DEFAULT_MODE,
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
            f'<li class="output-item"><a href="{o["url"]}" class="output-link">'
            f'<span class="output-kind{" output-kind-learning" if o["is_learning"] else ""}">{html.escape(o["kind_label"])}</span>'
            f'<span class="output-name">{html.escape(o["name"])}</span>'
            f'<span class="output-time">Cập nhật {html.escape(o["mtime_str"])}</span></a>'
            + (
                f'<a href="{o["download_url"]}" class="output-download" download '
                f'aria-label="Tải HTML {html.escape(o["name"], quote=True)}">Tải HTML</a>'
                if o["download_url"] else ""
            )
            + '</li>'
            for o in outputs
        )
        outputs_section = (
            '<section class="card" aria-labelledby="recent-heading">'
            '<h2 id="recent-heading">Trang đã tạo</h2>'
            '<p class="hint">“Trang đóng vai” dùng trước giờ lab; “Trang học lại” giúp hiểu bài đã làm. '
            'Mọi bản đều là bản nháp chờ người duyệt.</p>'
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
  .output-item {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: stretch;
  }}
  .output-item .output-link {{ flex: 1 1 320px; }}
  .output-kind {{
    font-size: 0.8rem;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 999px;
    background: #e0e7ff;
    color: #1e3a8a;
  }}
  .output-kind-learning {{
    background: #dcfce7;
    color: #14532d;
  }}
  .output-download {{
    display: inline-flex;
    align-items: center;
    min-height: 48px;
    padding: 0 16px;
    border: 1.5px solid #94a3b8;
    border-radius: 10px;
    font-weight: 600;
    color: var(--ink);
    background: #f1f5f9;
    text-decoration: none;
  }}
  .output-download:hover {{ background: #e2e8f0; }}
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
      Đưa một bài lab vào và chọn chế độ: <strong>Chuẩn bị lab</strong> tạo trang web đóng vai giúp học viên tự đóng vai AI trước giờ lab; <strong>Hiểu bài đã làm</strong> đọc mọi tệp Markdown ở gốc repo đã hoàn thành và tạo trang học lại có dẫn nguồn. Mọi kết quả đều là bản nháp chờ người duyệt.
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
          {_mode_fieldset("sample", selected_mode)}
          <fieldset>
            <legend>Danh sách bài lab mẫu</legend>
            {samples_block}
          </fieldset>
          <button type="submit" class="btn-primary">Tạo trang từ lab mẫu</button>
          <div class="status-line" role="status" aria-live="polite"></div>
        </form>
      </div>
    </div>

    <div role="tabpanel" id="panel-github" aria-labelledby="tab-github"{p_github_hidden}>
      <div class="panel-body">
        <form id="form-github" method="POST" action="/generate-github" aria-labelledby="github-heading">
          <h2 id="github-heading">Tạo từ link GitHub repository công khai</h2>
          <input type="hidden" name="csrf_token" value="{token}">
          {_mode_fieldset("github", selected_mode)}
          <div class="field">
            <label for="github-url">URL GitHub repository <span aria-hidden="true">*</span></label>
            <span id="gh-hint" class="hint">Ví dụ: https://github.com/owner/ten-bai-lab (chế độ Chuẩn bị lab nhận thêm /tree/main/thu-muc-con; chế độ Hiểu bài đã làm chỉ nhận link gốc repo). Repo cần ở chế độ Public.</span>
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
          <button type="submit" class="btn-primary">Tải repo &amp; tạo trang</button>
          <div class="status-line" role="status" aria-live="polite"></div>
        </form>
      </div>
    </div>

    <div role="tabpanel" id="panel-upload" aria-labelledby="tab-upload"{p_upload_hidden}>
      <div class="panel-body">
        <form id="form-upload" method="POST" action="/generate-upload" enctype="multipart/form-data" aria-labelledby="upload-heading">
          <h2 id="upload-heading">Tải bài lab lên từ máy</h2>
          <p class="hint" style="margin-bottom:14px">Chuẩn bị lab: hệ thống chỉ đọc các tệp văn bản (<code>.md, .py, .json, .yaml, .txt, .ipynb</code>) và tự động bỏ qua <code>.env</code>, <code>.git</code>, <code>.venv</code>, <code>solution/</code>. Hiểu bài đã làm: chỉ lấy tệp <code>.md</code> nằm trực tiếp ở gốc (kể cả <code>MISSION_ANSWERS.md</code>, <code>INSTRUCTOR_GUIDE.md</code>), tối đa 512 KiB/tệp và 2 MiB tổng; tệp bị loại đều được báo lý do.</p>
          <input type="hidden" name="csrf_token" value="{token}">
          {_mode_fieldset("upload", selected_mode)}
          <div class="upload-grid">
            <div class="field">
              <label for="lab-zip">Cách 1: Tải lên tệp .zip của bài lab</label>
              <span id="zip-hint" class="hint">Tối đa 20 MB. Nén thư mục chứa README.md và mã nguồn bài lab.</span>
              <input type="file" id="lab-zip" name="archive" accept=".zip,application/zip" aria-describedby="zip-hint">
            </div>
            <div class="divider">— HOẶC —</div>
            <div class="field">
              <label for="lab-folder">Cách 2: Chọn trực tiếp thư mục bài lab trên máy</label>
              <span id="folder-hint" class="hint">Trình duyệt chỉ gửi các tệp hợp lệ theo chế độ đã chọn, không tải lên .env hay thư mục nặng.</span>
              <input type="file" id="lab-folder" name="folder_files" webkitdirectory directory multiple aria-describedby="folder-hint">
              <span id="folder-summary" class="hint" role="status" aria-live="polite"></span>
            </div>
          </div>
          <button type="submit" class="btn-primary">Tải lên &amp; tạo trang</button>
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
  const uploadForm = document.getElementById('form-upload');
  let filteredFolderFiles = [];

  const formMode = (form) => {{
    const checked = form?.querySelector('input[name="mode"]:checked');
    return checked ? checked.value : 'before_lab';
  }};

  // before_lab: đúng bộ lọc cũ.
  const filterFolderBefore = (fileList) => {{
    const kept = [];
    let skipped = 0;
    for (const f of fileList) {{
      const rel = (f.webkitRelativePath || f.name).replace(/\\\\/g, '/');
      const parts = rel.split('/').filter(Boolean);
      const dirs = parts.slice(0, -1);
      const fname = parts[parts.length - 1] || '';
      const lower = fname.toLowerCase();
      if (dirs.some((d) => d.startsWith('.') || SKIP_DIRS.has(d.toLowerCase()))
          || fname.startsWith('.env') || SKIP_FILES.has(fname.toUpperCase())
          || !ALLOWED_EXT.some((ext) => lower.endsWith(ext))
          || f.size > 5 * 1024 * 1024) {{
        skipped += 1;
        continue;
      }}
      kept.push({{ file: f, rel }});
    }}
    return {{ kept, skipped }};
  }};

  // after_lab: chỉ <thư-mục-đã-chọn>/<tên>.md (đúng 2 thành phần), không áp SKIP_FILES; server tự kiểm lại.
  const filterFolderAfter = (fileList) => {{
    const kept = [];
    let skipped = 0;
    for (const f of fileList) {{
      const rel = (f.webkitRelativePath || f.name).replace(/\\\\/g, '/');
      const parts = rel.split('/').filter(Boolean);
      const fname = parts[parts.length - 1] || '';
      if (parts.length === 2 && fname.toLowerCase().endsWith('.md') && !fname.startsWith('.')) {{
        kept.push({{ file: f, rel }});
      }} else {{
        skipped += 1;
      }}
    }}
    return {{ kept, skipped }};
  }};

  const refreshFolderSelection = () => {{
    const files = folderInput?.files || [];
    if (!files.length) {{
      filteredFolderFiles = [];
      folderSummary.textContent = '';
      return;
    }}
    const mode = formMode(uploadForm);
    const res = mode === 'after_lab' ? filterFolderAfter(files) : filterFolderBefore(files);
    filteredFolderFiles = res.kept;
    if (mode === 'after_lab') {{
      const names = res.kept.map((it) => it.rel.split('/').pop());
      folderSummary.textContent = res.kept.length
        ? `Hiểu bài đã làm: sẽ gửi ${{res.kept.length}} tệp Markdown ở gốc thư mục`
          + (names.length <= 20 ? ` (${{names.join(', ')}})` : '')
          + `; bỏ qua ${{res.skipped}} tệp khác (thư mục con hoặc không phải .md).`
        : `Không có tệp .md nào nằm trực tiếp ở gốc thư mục này (đã bỏ qua ${{res.skipped}} tệp khác).`;
    }} else {{
      folderSummary.textContent = res.kept.length
        ? `Đã chọn ${{res.kept.length}} tệp văn bản hợp lệ (đã lọc bỏ .env/.git/thư mục hệ thống).`
        : 'Không tìm thấy tệp văn bản hợp lệ (.md, .py, .json, .yaml, .txt, .ipynb) trong thư mục này.';
    }}
  }};

  folderInput?.addEventListener('change', () => {{
    if (folderInput.files?.length) zipInput.value = '';
    refreshFolderSelection();
  }});
  uploadForm?.querySelectorAll('input[name="mode"]').forEach((r) => r.addEventListener('change', refreshFolderSelection));

  zipInput?.addEventListener('change', () => {{
    if (zipInput.files?.length) {{
      folderInput.value = '';
      filteredFolderFiles = [];
      folderSummary.textContent = '';
    }}
  }});

  const busyText = (mode) => mode === 'after_lab'
    ? 'Đang gửi bài và xếp hàng tạo trang học lại...'
    : 'Đang đọc đề, soạn tình huống đóng vai và kiểm tra từng trích dẫn file:dòng...';

  document.querySelectorAll('form').forEach((form) => {{
    form.addEventListener('submit', async (e) => {{
      const btn = form.querySelector('button[type="submit"]');
      const status = form.querySelector('.status-line');
      const mode = formMode(form);

      if (form.id === 'form-upload') {{
        refreshFolderSelection();
        const hasZip = Boolean(zipInput.files && zipInput.files.length > 0);
        const hasFolder = filteredFolderFiles.length > 0;
        if (!hasZip && !hasFolder) {{
          e.preventDefault();
          status.textContent = mode === 'after_lab'
            ? 'Vui lòng chọn tệp .zip hoặc thư mục có tệp .md ở gốc trước khi gửi.'
            : 'Vui lòng chọn tệp .zip hoặc thư mục bài lab hợp lệ trước khi gửi.';
          zipInput.focus();
          return;
        }}
        if (hasFolder && !hasZip) {{
          e.preventDefault();
          const oldLabel = btn.textContent;
          btn.disabled = true;
          btn.textContent = 'Đang gửi bài lab...';
          status.textContent = `Đang gửi ${{filteredFolderFiles.length}} tệp...`;
          const fd = new FormData();
          fd.append('csrf_token', form.querySelector('input[name="csrf_token"]').value);
          fd.append('mode', mode);
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
            btn.textContent = oldLabel;
            status.textContent = 'Lỗi kết nối khi gửi thư mục: ' + err.message;
          }}
          return;
        }}
      }}

      btn.disabled = true;
      btn.textContent = 'Đang gửi bài lab...';
      status.textContent = busyText(mode);
    }});
  }});
}})();
</script>
</body>
</html>'''


def _build_result_card(
    markdown: str, page_url: str, summary: dict, mode: str = DEFAULT_MODE, download_url: str = ""
) -> str:
    models = ", ".join(summary.get("models") or []) or MODEL_PROVIDER
    stats = (
        f"Chế độ: {MODE_LABELS.get(mode, mode)} · "
        f"Model: {models} · Gọi model: {summary.get('model_calls', 0)} lần · "
        f"Công cụ: {summary.get('tool_calls', 0)} lần · "
        f"Token vào/ra: {summary.get('tokens_in', 0):,} / {summary.get('tokens_out', 0):,} · "
        f"Thời gian: {summary.get('elapsed_s', 0)}s"
    )
    if mode == MODE_AFTER:
        heading = "Kết quả tạo trang học lại"
        action_btn = ""
        if page_url:
            action_btn += f'<a href="{html.escape(page_url, quote=True)}" class="btn-primary">Mở trang học lại →</a>'
        if download_url:
            action_btn += (
                f'<a href="{html.escape(download_url, quote=True)}" class="btn-secondary" download>Tải HTML</a>'
            )
        note = (
            '<p class="hint">Job kỹ thuật đã chạy xong. Trạng thái nội dung (blocked / incomplete / draft_ready) '
            'hiển thị trong chính trang học lại; trang là bản nháp chờ người duyệt, không phải chứng nhận bài đạt.</p>'
        )
        if not page_url:
            note += '<p class="hint">Không nhận được đường dẫn trang học lại hợp lệ từ kết quả bên dưới.</p>'
    else:
        heading = "Kết quả tạo bản nháp"
        action_btn = ""
        note = ""
        if page_url:
            base = page_url[:-len(".html")]
            action_btn = (
                f'<a href="{html.escape(page_url, quote=True)}" class="btn-primary" target="_blank" rel="noopener">Đóng vai →</a>'
                f'<a href="{html.escape(base + "-slides.html", quote=True)}" class="btn-secondary" target="_blank" rel="noopener">Slide</a>'
                f'<a href="{html.escape(base + "-summary.html", quote=True)}" class="btn-secondary" target="_blank" rel="noopener">Tóm tắt</a>'
            )
            # Trang đóng vai tương tác hiện ngay trong kết quả, không bắt người dùng đọc markdown.
            note = (
                f'<iframe src="{html.escape(page_url, quote=True)}" title="Trang đóng vai" '
                'style="width:100%;height:78vh;border:1px solid #e7e5e4;border-radius:8px;background:#fff;margin:12px 0"></iframe>'
            )
    body_md = f'<pre>{html.escape(markdown)}</pre>'
    if mode != MODE_AFTER and page_url:
        body_md = f'<details><summary>Xem bản chữ (markdown)</summary>{body_md}</details>'
    return (
        '<article class="card" aria-labelledby="result-heading">'
        f'<h2 id="result-heading">{html.escape(heading)}</h2>'
        f'<p class="stats">{html.escape(stats)}</p>'
        f'<div class="result-actions">{action_btn}</div>'
        f'{note}'
        f'{body_md}'
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

    def _send_bytes(
        self, data: bytes, content_type: str, status: int = 200, extra_headers: dict[str, str] | None = None
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _output_file(self, name: str, learning_only: bool = False) -> Path | None:
        """Tệp .html nằm trực tiếp trong OUTPUT_DIR (resolve + chặn traversal); None nếu không hợp lệ."""
        if not name or "/" in name or "\\" in name or "\x00" in name or name in (".", ".."):
            return None
        if learning_only and not LEARNING_PAGE_RE.fullmatch(name):
            return None
        out_root = OUTPUT_DIR.resolve()
        candidate = out_root / name
        if candidate.is_symlink():
            return None
        target = candidate.resolve()
        if target.parent != out_root or target.suffix != ".html" or not target.is_file():
            return None
        return target

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
                "mode": job.get("mode", DEFAULT_MODE),
                "status": job["status"],
                "display_name": job["display_name"],
                "page_url": job["page_url"],
                "download_url": job.get("download_url", ""),
                "error": job["error"],
            })
            return
        if path.startswith("/output/"):
            name = path[len("/output/"):]
            target = self._output_file(name)
            if target is None:
                self.send_error(404)
                return
            if LEARNING_PAGE_RE.fullmatch(target.name):
                # learning-v1: trả nguyên bản bytes, không qua enhancer, kèm CSP chặt (contract §6).
                self._send_bytes(
                    target.read_bytes(), "text/html; charset=utf-8",
                    extra_headers={"Content-Security-Policy": LEARNING_CSP},
                )
                return
            raw = target.read_text(encoding="utf-8", errors="replace")
            # Trang 3-tab mới (codebase/ui.py) đã có giao diện riêng: gửi nguyên bản, không chèn CSS cũ.
            self._send_html(raw if '<header class="top">' in raw else _enhance_roleplay_html(raw))
            return
        if path.startswith("/download/"):
            name = path[len("/download/"):]
            target = self._output_file(name, learning_only=True)
            if target is None:
                self.send_error(404)
                return
            self._send_bytes(
                target.read_bytes(), "text/html; charset=utf-8",
                extra_headers={
                    "Content-Disposition": f'attachment; filename="{target.name}"',
                    "Content-Security-Policy": LEARNING_CSP,
                },
            )
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        cancel_m = re.fullmatch(r"/job/([A-Za-z0-9_-]{1,64})/cancel", path)
        if cancel_m:
            self._handle_cancel(cancel_m.group(1))
            return
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

    def _handle_cancel(self, job_id: str) -> None:
        try:
            body = self._read_body(8 * 1024)
            form = urllib.parse.parse_qs(body.decode("utf-8"))
        except Exception:
            form = {}
        if not _verify_csrf_token(form.get("csrf_token", [""])[0]):
            self._send_html(_render_home(error_msg="Phiên biểu mẫu đã hết hạn, vui lòng tải lại trang."), status=403)
            return
        result = _cancel_job(job_id)
        if result == "not_found":
            self.send_error(404)
            return
        if result == "not_cancellable":
            with _JOBS_LOCK:
                job = dict(_JOBS[job_id]) if job_id in _JOBS else None
            if not job:
                self.send_error(404)
                return
            self._send_html(_render_job_page(job), status=409)
            return
        self._redirect(f"/job/{job_id}")

    def _handle_sample(self) -> None:
        mode = DEFAULT_MODE
        try:
            body = self._read_body(32 * 1024)
            form = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True)
            if not _verify_csrf_token(form.get("csrf_token", [""])[0]):
                self._send_html(_render_home(active_tab="sample", error_msg="Phiên biểu mẫu đã hết hạn, vui lòng tải lại trang."), status=403)
                return
            mode = _parse_mode(form.get("mode"))
            sample_id = form.get("sample", [""])[0].strip()
            sample_dir = (SAMPLES_DIR / sample_id).resolve()
            if not sample_id or sample_dir.parent != SAMPLES_DIR or not sample_dir.is_dir():
                raise ValueError("Bài lab mẫu không tồn tại.")
            # after_lab trên lab mẫu: truyền thẳng thư mục, reader cục bộ tự liệt kê (không cần manifest).
            job_id = _start_job(sample_dir, sample_id, f"sample:{sample_id}", mode=mode)
            self._redirect(f"/job/{job_id}")
        except Exception as exc:
            self._send_html(
                _render_home(active_tab="sample", error_msg=str(exc), selected_mode=mode if mode in MODE_LABELS else DEFAULT_MODE),
                status=400,
            )

    def _handle_github(self) -> None:
        gh_url = ""
        mode = DEFAULT_MODE
        tmp_dir: Path | None = None
        try:
            body = self._read_body(32 * 1024)
            form = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True)
            if not _verify_csrf_token(form.get("csrf_token", [""])[0]):
                self._send_html(_render_home(active_tab="github", error_msg="Phiên biểu mẫu đã hết hạn, vui lòng tải lại trang."), status=403)
                return
            gh_url = form.get("github_url", [""])[0].strip()
            mode = _parse_mode(form.get("mode"))
            zip_bytes, lab_name, subdir = _download_github_zip(gh_url, mode)
            tmp_dir = Path(tempfile.mkdtemp(prefix="chanme-gh-"))
            base = tmp_dir / lab_name
            base.mkdir(parents=True, exist_ok=True)
            if mode == MODE_AFTER:
                manifest = _ingest_zip_after_lab(zip_bytes, base, channel="github")
                if not manifest["accepted"]:
                    raise _no_root_markdown_error(manifest)
                job_id = _register_and_start(base, lab_name, f"github:{lab_name}", manifest, cleanup_dir=tmp_dir)
            else:
                written = _safe_extract_zip(zip_bytes, base)
                if written == 0:
                    raise ValueError("Không tìm thấy tệp văn bản bài lab hợp lệ trong repository này.")
                target_dir = base
                if subdir:
                    candidate = (base / subdir).resolve()
                    if str(candidate).startswith(str(base.resolve())) and candidate.is_dir():
                        target_dir = candidate
                job_id = _start_job(target_dir, lab_name, f"github:{lab_name}", cleanup_dir=tmp_dir, mode=mode)
            tmp_dir = None  # worker sẽ dọn dẹp sau khi chạy xong
            self._redirect(f"/job/{job_id}")
        except Exception as exc:
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            self._send_html(
                _render_home(active_tab="github", github_url=gh_url, error_msg=str(exc), selected_mode=mode),
                status=400,
            )

    def _handle_upload(self) -> None:
        tmp_dir: Path | None = None
        mode = DEFAULT_MODE
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
            mode = _parse_mode(fields.get("mode"))
            if not files:
                raise ValueError("Vui lòng chọn tệp .zip hoặc thư mục bài lab.")

            zip_entry = next(((fn, data) for field, fn, data in files if field == "archive" and data), None)
            tmp_dir = Path(tempfile.mkdtemp(prefix="chanme-up-"))
            manifest: dict | None = None
            if zip_entry:
                fname, data = zip_entry
                lab_name = _sanitize_slug(Path(fname).stem)
                lab_dir = tmp_dir / lab_name
                lab_dir.mkdir(parents=True, exist_ok=True)
                if mode == MODE_AFTER:
                    manifest = _ingest_zip_after_lab(data, lab_dir, channel="zip")
                    written = len(manifest["accepted"])
                else:
                    written = _safe_extract_zip(data, lab_dir)
            else:
                relpaths = fields.get("relpaths") or []
                uploaded = [(fn, data) for field, fn, data in files if field in ("files", "folder_files")]
                items = [(relpaths[idx] if idx < len(relpaths) else fn, data) for idx, (fn, data) in enumerate(uploaded)]
                raw_root = (fields.get("lab_name") or ["uploaded-lab"])[0]
                lab_name = _sanitize_slug(raw_root)
                lab_dir = tmp_dir / lab_name
                lab_dir.mkdir(parents=True, exist_ok=True)
                written, manifest = _ingest_folder_upload(mode, items, raw_root, lab_dir)

            if mode == MODE_AFTER:
                if not written:
                    raise _no_root_markdown_error(manifest or {})
                job_id = _register_and_start(lab_dir, lab_name, f"upload:{lab_name}", manifest or {}, cleanup_dir=tmp_dir)
            else:
                if written == 0:
                    raise ValueError("Không có tệp văn bản bài lab hợp lệ (.md, .py, .json, .yaml, .txt, .ipynb).")
                job_id = _start_job(lab_dir, lab_name, f"upload:{lab_name}", cleanup_dir=tmp_dir, mode=mode)
            tmp_dir = None  # worker sẽ dọn dẹp sau khi chạy xong
            self._redirect(f"/job/{job_id}")
        except Exception as exc:
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            self._send_html(_render_home(active_tab="upload", error_msg=str(exc), selected_mode=mode), status=400)


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
