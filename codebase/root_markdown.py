"""Reader Markdown cấp gốc cho luồng after_lab — hợp đồng learning-v1 §2–§3.

    RepoRef(path)              tham chiếu repo; repr không lộ đường dẫn (tracing ghi input của @tool)
    read_root_markdown(ref)    @tool · input RepoRef · output RootSnapshot (manifest + dòng ĐÃ CHE). Không tác động ra ngoài.
    make_chunks(snapshot)      chia đoạn theo dòng, giữ số dòng gốc, đoạn ngữ cảnh lặp được đánh dấu context-only
    register_ingest_manifest   web ghi manifest tiếp nhận (ZIP/thư mục/GitHub) để reader đối chiếu, theo từng đường dẫn
    verify_unchanged(ref, s)   băm lại sau khi xử lý; file đổi trong lúc chạy → issue file_changed

Chỉ đọc file .md trực tiếp ở root (không đệ quy, không theo symlink/reparse point, không mở liên kết, không chạy lệnh).
Raw bytes chỉ dùng để băm, không ra khỏi hàm. Bí mật/PII được che theo đoạn trong dòng, số dòng giữ nguyên.
"""
import hashlib
import os
import re
import stat
import threading
import unicodedata

from tracing import tool

MAX_TOTAL_BYTES = 2 * 1024 * 1024      # giới hạn kỹ thuật MVP (hợp đồng §3), không phải số đo
MAX_FILE_BYTES = 512 * 1024
CHUNK_CHARS = 16_000
REPARSE_POINT = 0x400                  # FILE_ATTRIBUTE_REPARSE_POINT (Windows)

MASK_SECRET = "[đã che: bí mật]"
MASK_PII = "[đã che: thông tin cá nhân]"
MASK_URL = "[đã che: URL cá nhân]"

# ---------------------------------------------------------------- che bí mật / PII
SECRET_RES = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bgsk_[A-Za-z0-9]{20,}|\bxox[abprs]-[A-Za-z0-9-]{10,}|\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/:@'\"`]*:[^\s/@'\"`]+@"),          # mật khẩu trong URL
]
ASSIGN_SECRET_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:API[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE[_-]?KEY)[A-Z0-9_]*)"
    r"(\s*[:=]\s*[\"']?)([^\s\"'`<>$]{8,})")
PLACEHOLDER_RE = re.compile(r"(?i)^(?:your|<|\$|xxx|\*+|example|changeme|placeholder|\.\.\.)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
MSSV_RE = re.compile(r"\b\d[A-Z]\d{9}\b|\b2A2\d{8}\b")
PHONE_RE = re.compile(r"(?<![\d.,])(?:\+84|0)(?:[\s.-]?\d){9}(?![\d.,])")
GITHUB_ACCT_RE = re.compile(r"(?i)(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:/[^\s)\]>`'\"]*)?")
DEPLOY_URL_RE = re.compile(
    r"(?i)\bhttps?://[^\s)\]>`'\"]*?(?:railway\.app|onrender\.com|\.run\.app|vercel\.app|herokuapp\.com|fly\.dev|"
    r"ngrok(?:-free)?\.(?:app|io|dev)|trycloudflare\.com|netlify\.app|pages\.dev|azurewebsites\.net|amazonaws\.com|"
    r"hf\.space|streamlit\.app)[^\s)\]>`'\"]*")
LABEL_RE = re.compile(r"(?i)(\*{0,2}(?:họ\s*(?:và\s*)?tên|mssv|mã\s*(?:số\s*)?(?:sinh\s*viên|sv|học\s*viên)|student\s*id|"
                      r"full\s*name|email|e-mail|số\s*điện\s*thoại|sđt|phone)\*{0,2}\s*[:：]\s*\*{0,2})")
NAME_CELL_RE = re.compile(r"^[A-ZÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+){1,5}$")
CAMEL_NAME_RE = re.compile(r"^(?:[A-Z][a-z]+){2,5}$")


def _fold(s):
    """Bỏ dấu + chữ thường, giữ nguyên độ dài (mỗi ký tự → một ký tự) để ánh xạ vị trí."""
    out = []
    for ch in s:
        if ch in "đĐ":
            out.append("d")
            continue
        base = unicodedata.normalize("NFD", ch)[0]
        out.append(base.lower() if len(base.lower()) == 1 else ch)
    return "".join(out)


def harvest_names(all_lines, folder_name="", extra=()):
    """Tên người suy ra từ dòng có MSSV/email (ô bảng trông như họ tên) và dòng nhãn 'Họ tên:'. Chỉ giữ trong bộ nhớ."""
    names = set()
    for line in all_lines:
        has_id = bool(MSSV_RE.search(line) or EMAIL_RE.search(line))
        if has_id and "|" in line:
            for cell in line.strip().strip("|").split("|"):
                cell = re.sub(r"[*_`]", "", cell).strip()
                if NAME_CELL_RE.match(cell) and len(cell) <= 60:
                    names.add(cell)
        m = re.search(r"(?i)(?:họ\s*(?:và\s*)?tên|full\s*name|người\s*làm)\*{0,2}\s*[:：]\s*\*{0,2}\s*([^\n—|*,;(]+)", line)
        if m:
            cand = m.group(1).strip()
            if NAME_CELL_RE.match(cand):
                names.add(cand)
    for seg in re.split(r"[-_ .]+", folder_name or ""):
        if CAMEL_NAME_RE.match(seg) and len(seg) >= 8:
            names.add(" ".join(re.findall(r"[A-Z][a-z]+", seg)))
    variants = set()
    for x in extra:                                       # ô cột định danh (GitHub handle, tên…)
        x = re.sub(r"[*_`@\[\]()]", "", x).strip()
        if len(x) >= 4 and not re.fullmatch(r"[\d\W]+", x):
            variants.add(x)
    for n in names:
        words = n.split()
        variants.add(n)
        variants.add("".join(words))                      # dạng viết liền (vd NguyenVanThu)
        if len(words) >= 3:
            variants.add(" ".join(words[-2:]))
            variants.add("".join(words[-2:]))
    return sorted((_fold(v) for v in variants if len(v) >= 6), key=len, reverse=True)


PII_HEADER_RE = re.compile(r"(?i)^\s*\**\s*(?:họ\s*(?:và\s*)?tên|tên|họ tên thành viên|thành viên|name|full\s*name|mssv|"
                           r"mã\s*(?:số\s*)?(?:sv|sinh\s*viên|học\s*viên)|student\s*id|email|e-mail|github|git\s*hub|"
                           r"username|user|tài\s*khoản|account|sđt|số\s*điện\s*thoại|phone)\s*\**\s*$")


def _cells(line):
    """Vị trí (start, end) nội dung từng ô của một dòng bảng Markdown."""
    out, i = [], line.find("|")
    if i < 0:
        return out
    while True:
        j = line.find("|", i + 1)
        if j < 0:
            break
        out.append((i + 1, j))
        i = j
    return out


def table_pii_cells(lines):
    """{số dòng: [(start, end)]} ô thuộc cột định danh (header Họ tên/MSSV/Email/GitHub…) trong bảng Markdown."""
    out, cols = {}, None
    for no, line in enumerate(lines, 1):
        if not TABLE_LINE_RE.match(line):
            cols = None
            continue
        cells = _cells(line)
        nxt = lines[no] if no < len(lines) else ""
        if cols is None and re.match(r"^\s*\|?\s*:?-{2,}", nxt):
            cols = {k for k, (a, b) in enumerate(cells) if PII_HEADER_RE.match(line[a:b])}
            continue
        if cols and not re.match(r"^\s*\|?\s*:?-{2,}", line):
            spans = [(a, b) for k, (a, b) in enumerate(cells) if k in cols and line[a:b].strip()]
            if spans:
                out[no] = spans
    return out


TABLE_LINE_RE = re.compile(r"^\s*\|")


def redact_line(line, folded_names=(), cell_spans=()):
    """→ (dòng đã che, tập loại đã che). Che theo đoạn; chuỗi che bắt đầu bằng '[đã che'."""
    spans = [(a, b, MASK_PII, "pii") for a, b in cell_spans]   # (start, end, mask, kind)
    for rx in SECRET_RES:
        spans += [(m.start(), m.end(), MASK_SECRET, "secret") for m in rx.finditer(line)]
    for m in ASSIGN_SECRET_RE.finditer(line):
        val = m.group(3)
        if not PLACEHOLDER_RE.match(val):
            spans.append((m.start(3), m.end(3), MASK_SECRET, "secret"))
    spans += [(m.start(), m.end(), MASK_URL, "url") for m in DEPLOY_URL_RE.finditer(line)]
    spans += [(m.start(), m.end(), MASK_URL, "url") for m in GITHUB_ACCT_RE.finditer(line)]
    spans += [(m.start(), m.end(), MASK_PII, "pii") for rx in (EMAIL_RE, MSSV_RE, PHONE_RE) for m in rx.finditer(line)]
    for m in LABEL_RE.finditer(line):
        end = len(line)
        stop = re.search(r"\s[—–|]\s|\s{2,}|\|", line[m.end():])
        if stop:
            end = m.end() + stop.start()
        if line[m.end():end].strip():
            spans.append((m.end(), end, MASK_PII, "pii"))
    if folded_names:
        fl = _fold(line)
        for n in folded_names:
            start = 0
            while True:
                i = fl.find(n, start)
                if i < 0:
                    break
                before = fl[i - 1] if i else " "
                after = fl[i + len(n)] if i + len(n) < len(fl) else " "
                if not before.isalnum() and not after.isalnum():
                    spans.append((i, i + len(n), MASK_PII, "pii"))
                start = i + len(n)
    if not spans:
        return line, set()
    spans.sort()
    merged = []
    for s, e, mask, kind in spans:
        if merged and s <= merged[-1][1]:
            ps, pe, pm, pk = merged[-1]
            merged[-1] = (ps, max(pe, e), MASK_SECRET if "secret" in (pk, kind) else pm, pk if pk == "secret" else kind)
        else:
            merged.append((s, e, mask, kind))
    out, pos, kinds = [], 0, set()
    for s, e, mask, kind in merged:
        out.append(line[pos:s])
        out.append(mask)
        kinds.add(kind)
        pos = e
    out.append(line[pos:])
    return "".join(out), kinds


def redact_text(text, folded_names=()):
    return redact_line(text, folded_names)[0]


# ---------------------------------------------------------------- tham chiếu và handoff ingestion
class RepoRef:
    """Đường dẫn repo, repr chỉ là nhãn băm (không lộ đường dẫn/tên học viên trong trace)."""

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.label = "repo#" + hashlib.sha256(self.path.encode("utf-8", "replace")).hexdigest()[:8]

    def __repr__(self):
        return "RepoRef(%s)" % self.label


_INGEST = {}
_INGEST_LOCK = threading.Lock()


def _key(path):
    return os.path.normcase(os.path.abspath(path))


def register_ingest_manifest(repo_path, manifest):
    """Web gọi trước khi chạy job after_lab (ZIP/thư mục/GitHub). Dữ liệu theo đường dẫn, không phải trạng thái mode."""
    with _INGEST_LOCK:
        _INGEST[_key(repo_path)] = manifest


def _pop_ingest(path):
    with _INGEST_LOCK:
        return _INGEST.pop(_key(path), None)


# ---------------------------------------------------------------- snapshot
class RootSnapshot:
    """Snapshot bất biến trong phiên. lines = dòng ĐÃ CHE; không giữ raw bytes."""

    def __init__(self):
        self.snapshot_id = ""
        self.revision = None
        self.display_label = "Repo bài lab"
        self.manifest = []             # đúng shape source_manifest
        self.lines = {}                # source_id → [dòng đã che]
        self.issues = []               # issue objects {id, code, severity, message, scope_ids}
        self.out_of_scope_count = 0
        self.root_exists = False
        self._names = []               # tên đã gập dấu, chỉ để che (không xuất)
        self._hashes = {}              # source_id → sha256 lúc đọc
        self._real = {}                # source_id → tên file thật trên đĩa

    def name_of(self, sid):
        return next((m["name"] for m in self.manifest if m["source_id"] == sid), sid)

    def add_issue(self, code, severity, message, scope_ids=()):
        iid = "iss-%d" % (len(self.issues) + 1)
        self.issues.append({"id": iid, "code": code, "severity": severity, "message": message,
                            "scope_ids": list(scope_ids)})
        return iid

    def redact(self, text):
        return redact_text(text, self._names)

    def __repr__(self):
        return "RootSnapshot(%s, files=%d, lines=%d, issues=%d)" % (
            self.snapshot_id[:12], len(self.manifest), sum(len(v) for v in self.lines.values()), len(self.issues))


def _git_revision(root):
    """Commit của CHÍNH root (đọc .git/HEAD, không chạy git, không lấy repo cha)."""
    gdir = os.path.join(root, ".git")
    try:
        if os.path.isfile(gdir):
            with open(gdir, encoding="utf-8") as f:
                m = re.match(r"gitdir:\s*(.+)", f.read().strip())
            if not m:
                return None
            gdir = os.path.join(root, m.group(1)) if not os.path.isabs(m.group(1)) else m.group(1)
        if not os.path.isdir(gdir):
            return None
        head = open(os.path.join(gdir, "HEAD"), encoding="utf-8").read().strip()
        if re.fullmatch(r"[0-9a-f]{40}", head):
            return head
        m = re.match(r"ref:\s*(refs/[\w./-]+)$", head)
        if not m:
            return None
        ref_file = os.path.join(gdir, *m.group(1).split("/"))
        if os.path.isfile(ref_file):
            sha = open(ref_file, encoding="utf-8").read().strip()
            return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None
        packed = os.path.join(gdir, "packed-refs")
        if os.path.isfile(packed):
            for line in open(packed, encoding="utf-8"):
                parts = line.strip().split(" ")
                if len(parts) == 2 and parts[1] == m.group(1) and re.fullmatch(r"[0-9a-f]{40}", parts[0]):
                    return parts[0]
    except (OSError, UnicodeDecodeError):
        return None
    return None


def _is_link(entry):
    try:
        if entry.is_symlink():
            return True
        st = entry.stat(follow_symlinks=False)
        return bool(getattr(st, "st_file_attributes", 0) & REPARSE_POINT)
    except OSError:
        return True


def _display_name(name, names):
    """Tên file hiển thị: che MSSV/email/tên nếu có trong tên file."""
    shown = redact_text(name, names)
    return shown if shown == name else re.sub(r"\[đã che[^\]]*\]", "an-danh", shown)


@tool
def read_root_markdown(ref: RepoRef) -> RootSnapshot:
    """read_root_markdown · input: RepoRef (thư mục repo được chỉ định là root)
    output: RootSnapshot {snapshot_id, manifest, lines đã che, issues}. Chỉ .md trực tiếp ở root, không đệ quy,
    không theo symlink, UTF-8/UTF-8-BOM nghiêm ngặt, che bí mật/PII trước khi trả. Không tác động ra ngoài."""
    snap = RootSnapshot()
    root = ref.path
    ingest = _pop_ingest(root)
    if not os.path.isdir(root):
        snap.add_issue("read_failed", "error", "Không tìm thấy thư mục repo được chỉ định.")
        snap.snapshot_id = hashlib.sha256(b"").hexdigest()
        return snap
    snap.root_exists = True
    snap.revision = _git_revision(root)
    try:
        entries = sorted(os.scandir(root), key=lambda e: e.name)
    except OSError:
        snap.add_issue("read_failed", "error", "Không liệt kê được thư mục repo.")
        snap.snapshot_id = hashlib.sha256(b"").hexdigest()
        return snap

    md, other = [], 0
    for e in entries:
        if e.name.lower().endswith(".md") and not e.name.startswith("."):   # cùng quy tắc với web ingestion
            md.append(e)
        elif e.name not in (".git",):
            other += 1
    snap.out_of_scope_count = other + (ingest or {}).get("out_of_scope_count", 0)

    lower_count = {}
    for e in md:
        lower_count[e.name.lower()] = lower_count.get(e.name.lower(), 0) + 1

    raw_texts = {}                      # source_id → text (chưa che) — chỉ sống trong hàm này
    total = 0
    for idx, e in enumerate(md, 1):
        sid = "s%d" % idx
        item = {"source_id": sid, "name": e.name, "sha256": None, "line_count": None, "read_status": "read",
                "processed_ranges": [], "redacted_ranges": [], "issues": []}
        snap.manifest.append(item)
        snap._real[sid] = e.name

        def fail(status, code, msg, sev="error"):
            item["read_status"] = status
            item["issues"].append(snap.add_issue(code, sev, msg, [sid]))

        if _is_link(e):
            fail("excluded", "symlink", "%s là symlink/reparse point: không đọc theo." % e.name)
            continue
        if not e.is_file(follow_symlinks=False):
            fail("excluded", "not_regular", "%s không phải file thường." % e.name)
            continue
        if lower_count[e.name.lower()] > 1:
            fail("excluded", "collision", "%s trùng tên khác hoa/thường với file khác: không đọc để tránh nhầm." % e.name)
            continue
        try:
            size = e.stat(follow_symlinks=False).st_size
            with open(e.path, "rb") as f:
                raw = f.read(MAX_FILE_BYTES + 1)
        except OSError:
            fail("unreadable", "read_failed", "Không mở được %s." % e.name)
            continue
        if size > MAX_FILE_BYTES or len(raw) > MAX_FILE_BYTES:
            fail("over_limit", "over_limit", "%s vượt giới hạn %d KiB/file: chưa đọc." % (e.name, MAX_FILE_BYTES // 1024))
            continue
        if total + len(raw) > MAX_TOTAL_BYTES:
            fail("over_limit", "over_total_limit", "Tổng Markdown vượt %d MiB: %s chưa đọc." % (MAX_TOTAL_BYTES // 2**20, e.name))
            continue
        total += len(raw)
        item["sha256"] = hashlib.sha256(raw).hexdigest()
        snap._hashes[sid] = item["sha256"]
        body = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            fail("unreadable", "decode_error", "%s không phải UTF-8 hợp lệ: không đọc bằng ký tự thay thế." % e.name)
            continue
        lines = text.splitlines()
        item["line_count"] = len(lines)
        if not lines:
            item["read_status"] = "empty"
            continue
        raw_texts[sid] = lines

    # Đối chiếu manifest tiếp nhận (web): file đã nhận phải có mặt, cùng hash; file bị loại có lý do
    if ingest:
        by_name = {m["name"]: m for m in snap.manifest}
        for acc in ingest.get("accepted") or []:
            m = by_name.get(acc.get("name"))
            if not m:
                snap.add_issue("ingest_mismatch", "error", "File đã tiếp nhận %s không thấy khi đọc." % acc.get("name"))
            elif m["sha256"] and acc.get("sha256") and m["sha256"] != acc["sha256"]:
                m["issues"].append(snap.add_issue("ingest_mismatch", "error",
                                                  "%s khác hash lúc tiếp nhận." % m["name"], [m["source_id"]]))
        reasons = {"over_limit": "over_limit", "over_total_limit": "over_limit"}
        for exc in ingest.get("excluded") or []:
            name = str(exc.get("name") or "?")
            if name in by_name:
                continue
            sid = "s%d" % (len(snap.manifest) + 1)
            reason = str(exc.get("reason") or "excluded")
            item = {"source_id": sid, "name": name, "sha256": None, "line_count": None,
                    "read_status": reasons.get(reason, "excluded"), "processed_ranges": [], "redacted_ranges": [],
                    "issues": []}
            item["issues"].append(snap.add_issue(reason, "error", "%s bị loại khi tiếp nhận (%s)." % (name, reason), [sid]))
            snap.manifest.append(item)
            by_name[name] = item

    # Che: gom tên người từ toàn bộ dòng trước, rồi che từng dòng (giữ số dòng)
    cells_by = {sid: table_pii_cells(lines) for sid, lines in raw_texts.items()}
    cell_vals = [raw_texts[sid][no - 1][a:b] for sid, cm in cells_by.items() for no, sp in cm.items() for a, b in sp]
    snap._names = harvest_names([l for ls in raw_texts.values() for l in ls], os.path.basename(root), cell_vals)
    for m in snap.manifest:
        m["name"] = _display_name(m["name"], snap._names)
    for sid, lines in raw_texts.items():
        out, red, kinds = [], [], set()
        cells = cells_by[sid]
        for no, line in enumerate(lines, 1):
            new, k = redact_line(line, snap._names, cells.get(no, ()))
            if k:
                red.append(no)
                kinds |= k
            out.append(new)
        snap.lines[sid] = out
        item = next(m for m in snap.manifest if m["source_id"] == sid)
        item["redacted_ranges"] = _to_ranges(red)
        if red:
            item["issues"].append(snap.add_issue("redacted", "info", "Đã che %d dòng (loại: %s) trong %s; vị trí dòng giữ nguyên."
                                                 % (len(red), ", ".join(sorted(kinds)), item["name"]), [sid]))
    del raw_texts

    if not any(m["read_status"] == "read" for m in snap.manifest):
        snap.add_issue("no_markdown", "error", "Không có file Markdown cấp gốc đọc được.")
    if snap.out_of_scope_count:
        snap.add_issue("out_of_scope", "info", "%d mục khác (thư mục con, code, CSV, ảnh…) nằm ngoài phạm vi root-Markdown: "
                       "không đọc." % snap.out_of_scope_count)
    h = hashlib.sha256()
    for m in sorted(snap.manifest, key=lambda m: m["name"]):
        h.update(("%s\t%s\n" % (m["name"], m["sha256"] or "-")).encode("utf-8"))
    snap.snapshot_id = h.hexdigest()
    snap.display_label = _label(snap)
    return snap


def _label(snap):
    for m in sorted(snap.manifest, key=lambda m: (not m["name"].lower().startswith("readme"), m["name"])):
        for line in snap.lines.get(m["source_id"], [])[:40]:
            mm = re.match(r"^#\s+(.+)", line)
            if mm and "[đã che" not in mm.group(1):
                label = re.sub(r"[`*_]", "", mm.group(1)).strip()
                return label[:90] or "Repo bài lab"
    return "Repo bài lab"


def _to_ranges(nums):
    out = []
    for n in nums:
        if out and n == out[-1]["end_line"] + 1:
            out[-1]["end_line"] = n
        else:
            out.append({"start_line": n, "end_line": n})
    return out


def verify_unchanged(ref, snap):
    """Băm lại các file đã đọc; khác → issue file_changed (không đọc lại nội dung mới để hợp thức nguồn cũ)."""
    changed = []
    for m in snap.manifest:
        sid = m["source_id"]
        if sid not in snap._hashes:
            continue
        try:
            with open(os.path.join(ref.path, snap._real[sid]), "rb") as f:
                now = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            now = None
        if now != snap._hashes[sid]:
            changed.append(m)
    for m in changed:
        m["issues"].append(snap.add_issue("file_changed", "error", "%s đã thay đổi trong lúc xử lý; trang dùng bản đã đọc."
                                          % m["name"], [m["source_id"]]))
    return changed


# ---------------------------------------------------------------- chia đoạn
HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
TABLE_RE = re.compile(r"^\s*\|")


def _fmt(no, text):
    return "%d: %s\n" % (no, text)


def make_chunks(snap, chunk_chars=CHUNK_CHARS):
    """→ (chunks, ledger). chunk = {chunk_id, source_id, name, start_line, end_line, context: [(no, text)], body: [(no, text)]}.
    ledger = [{source_id,start_line,end_line,status,issue_ids}] (pending/failed). Dòng dài hơn chunk_chars → failed + issue."""
    chunks, ledger = [], []
    for m in snap.manifest:
        sid = m["source_id"]
        lines = snap.lines.get(sid)
        if m["read_status"] != "read" or not lines:
            continue
        n = len(lines)
        # trạng thái ngữ cảnh từng dòng: heading trail, fence mở, header bảng
        trail, fence_open, table_hdr = [], None, None
        ctx_at = []
        for no, line in enumerate(lines, 1):
            ctx_at.append((list(trail), fence_open, table_hdr))
            if fence_open is None and HEADING_RE.match(line):
                lvl = len(HEADING_RE.match(line).group(1))
                trail = [t for t in trail if t[2] < lvl] + [(no, line, lvl)]
            if FENCE_RE.match(line):
                fence_open = None if fence_open else (no, line)
            if TABLE_RE.match(line):
                if table_hdr is None and no < n and re.match(r"^\s*\|?\s*:?-{2,}", lines[no]):
                    table_hdr = [(no, line), (no + 1, lines[no])]
            else:
                table_hdr = None
        start = 1
        while start <= n:
            if len(_fmt(start, lines[start - 1])) > chunk_chars:
                iid = snap.add_issue("line_over_limit", "error", "%s dòng %d dài hơn giới hạn đoạn %d ký tự: không gửi model, "
                                     "không tính đã xử lý." % (m["name"], start, chunk_chars), [sid])
                m["issues"].append(iid)
                ledger.append({"source_id": sid, "start_line": start, "end_line": start, "status": "failed",
                               "issue_ids": [iid]})
                start += 1
                continue
            trail0, fence0, table0 = ctx_at[start - 1]
            context = [(no, t) for no, t, _ in trail0 if no < start]
            if fence0 and fence0[0] < start:
                context.append(fence0)
            if table0 and table0[0][0] < start:
                context += [x for x in table0 if x[0] < start]
            budget = chunk_chars - sum(len(_fmt(no, t)) for no, t in context) - 200
            size, end, best = 0, start - 1, None
            while end < n:
                add = len(_fmt(end + 1, lines[end]))
                if size + add > budget and end >= start:
                    break
                size += add
                end += 1
                nxt = lines[end] if end < n else ""
                in_struct = ctx_at[end][1] if end < n else None
                if (not nxt.strip() or HEADING_RE.match(nxt)) and in_struct is None and end - start > 5:
                    best = end
            if end < n and best and best >= start + (end - start) // 2:
                end = best
            body = [(no, lines[no - 1]) for no in range(start, end + 1)]
            chunks.append({"chunk_id": "k%d" % (len(chunks) + 1), "source_id": sid, "name": m["name"],
                           "start_line": start, "end_line": end, "context": context, "body": body})
            ledger.append({"source_id": sid, "start_line": start, "end_line": end, "status": "pending", "issue_ids": []})
            start = end + 1
    return chunks, ledger


def chunk_text(chunk, total_lines):
    out = ["### FILE %s (source_id %s) — dòng %d-%d trên %d" % (chunk["name"], chunk["source_id"], chunk["start_line"],
                                                              chunk["end_line"], total_lines)]
    if chunk["context"]:
        out.append("[NGỮ CẢNH LẶP — chỉ để hiểu, đã được xử lý ở đoạn khác]")
        out += ["~%d: %s" % (no, t) for no, t in chunk["context"]]
        out.append("[HẾT NGỮ CẢNH]")
    out += ["%d: %s" % (no, t) for no, t in chunk["body"]]
    return "\n".join(out)
