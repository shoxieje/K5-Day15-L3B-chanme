"""Công cụ của bài toán — khớp bảng công cụ ở spec.md §4. Cả 3 công cụ là code thật, chỉ đọc / ghi file output, không gửi gì ra ngoài.

    read_lab       đường dẫn thư mục lab → các file chữ được phép đọc, đánh số dòng. Không tác động ra ngoài.
    check_sources  lesson (danh sách ý) + lab → ý đạt / ý trượt + lý do. Không tác động ra ngoài.
    render         lesson đã kiểm → trang web đóng vai (HTML) trong thư mục output/. Không gửi cho lớp (trợ giảng gửi tay).
"""
import html
import json
import os
import re

from tracing import tool, TOOLS  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABS_DIR = os.environ.get("LABS_DIR") or ROOT          # input "labs/<tên>" tính từ đây
TEXT_EXT = (".md", ".py", ".json", ".yaml", ".yml", ".txt", ".ipynb")
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "solution", "solutions", "answers"}
SKIP_FILES = {"MISSION_ANSWERS.MD", "INSTRUCTOR_GUIDE.MD"}                     # file bài làm của học viên
MAX_CHARS = 120_000                                     # giới hạn đọc một lượt; vượt thì ghi lại phần chưa đọc
KEY_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|AIza[0-9A-Za-z_\-]{20,}|ghp_[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,})")
SECTIONS = ("muc_tieu", "agent_thay", "cong_cu", "lua_chon", "buoc_dung", "loi_de_mac")


def _readme_first(path):
    name = os.path.basename(path).lower()
    return (0 if name.startswith("readme") else 1 if name.startswith("guide") else 2 if name.endswith(".py") else 3, path)


@tool
def read_lab(path: str) -> dict:
    """read_lab · input: đường dẫn thư mục lab · output: {"files": {rel_path: [dòng...]}, "skipped": [...], "truncated": [...], "is_lab": bool}
    Bỏ .env, thư mục môi trường ảo, solution / answers, file bài làm. Không tác động ra ngoài."""
    base = path if os.path.isabs(path) else os.path.join(LABS_DIR, path)
    out = {"files": {}, "skipped": [], "truncated": [], "is_lab": False}
    if not os.path.isdir(base):
        return out
    found = []
    for d, dirs, files in os.walk(base):
        dirs[:] = [x for x in dirs if x.lower() not in SKIP_DIRS and not x.startswith(".")]
        for f in files:
            p = os.path.join(d, f); rel = os.path.relpath(p, base).replace(os.sep, "/")
            if os.path.islink(p) or f.startswith(".env") or f.upper() in SKIP_FILES or not f.endswith(TEXT_EXT):
                out["skipped"].append(rel)
                continue
            found.append(p)
    used = 0
    for p in sorted(found, key=_readme_first):
        rel = os.path.relpath(p, base).replace(os.sep, "/")
        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if used + len(text) > MAX_CHARS:
            out["truncated"].append(rel)
            continue
        if KEY_RE.search(text):
            # Giữ số dòng nguồn và loại toàn bộ dòng có bí mật trước khi gọi API.
            text = "\n".join("" if KEY_RE.search(line) else line for line in text.splitlines())
        used += len(text)
        out["files"][rel] = text.splitlines()
    names = [k.lower() for k in out["files"]]
    out["is_lab"] = any(n.startswith("readme") for n in names) and any(n.endswith(".py") or re.fullmatch(r"(?:\d+-)?(?:guide|rubric|checkpoints)\.md", n) for n in names)
    return out


def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


@tool
def check_sources(lesson: dict, lab: dict) -> dict:
    """check_sources · input: lesson {"tasks": [...], "not_in_lab": [...]}, kết quả read_lab
    output: {"ok": [ý đạt], "failed": [{"item", "reason"}]}. Mỗi ý = {"task", "part", "text", "source": "file:a-b", "quote"}.
    Ý đạt khi: file có trong lab · khoảng dòng tồn tại · trích dẫn có nguyên văn trong khoảng dòng · không có chuỗi dạng key. Không tác động ra ngoài."""
    ok, failed = [], []
    tasks = lesson.get("tasks") if isinstance(lesson.get("tasks"), list) else []
    for task in tasks:
        if not isinstance(task, dict):
            failed.append({"item": {"raw": str(task)[:200]}, "reason": "sai cấu trúc: task phải là object"})
            continue
        if not isinstance(task.get("items"), list):
            task["items"] = []
        parts = {it.get("part") for it in task.get("items", []) if isinstance(it, dict)}
        missing = [s for s in SECTIONS if s not in parts]
        n_choice = sum(1 for it in task.get("items", []) if isinstance(it, dict) and it.get("part") == "lua_chon")
        if not 3 <= n_choice <= 4:
            missing.append("lua_chon cần 3–4 (đang %d)" % n_choice)
        if missing:
            failed.append({"item": {"task": task.get("name")}, "reason": "thiếu phần: " + ", ".join(missing)})
        for it in task.get("items", []):
            reason = None
            if not isinstance(it, dict) or not all(isinstance(it.get(k), str) for k in ("part", "text", "source", "quote")):
                failed.append({"item": it if isinstance(it, dict) else {"raw": str(it)[:200]},
                               "reason": "sai cấu trúc: part, text, source, quote phải là chuỗi"})
                continue
            m = re.fullmatch(r"(.+):(\d+)-(\d+)", it.get("source", ""))
            if KEY_RE.search(it.get("text", "") + it.get("quote", "")):
                reason = "có chuỗi dạng API key"
            elif (it.get("text", "") + "\n" + it.get("quote", "")).count("\n") >= 5:
                reason = "có khối code / trích dẫn ≥5 dòng (nghi chép lời giải)"
            elif not m:
                reason = "nguồn sai dạng file:dòng-dòng"
            elif m.group(1) not in lab["files"]:
                reason = "file %s không có trong lab (hoặc bị loại khi đọc)" % m.group(1)
            else:
                lines = lab["files"][m.group(1)]; a, b = int(m.group(2)), int(m.group(3))
                if not (1 <= a <= b <= len(lines)):
                    reason = "dòng %d-%d không có (file có %d dòng)" % (a, b, len(lines))
                elif not _norm(it.get("quote")) or _norm(it.get("quote")) not in _norm(" ".join(lines[a - 1:b])):
                    reason = "trích dẫn không khớp dòng %d-%d" % (a, b)
            (failed.append({"item": it, "reason": reason}) if reason else ok.append(it))
    return {"ok": ok, "failed": failed}


@tool
def render(lesson: dict, lab_name: str) -> str:
    """render · input: lesson đã kiểm, tên lab · output: đường dẫn file HTML trang đóng vai trong output/.
    Dựng từ khuôn, không gọi model, không gửi cho ai. Không tác động ra ngoài."""
    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", lab_name).strip("-") or "lab"
    out = os.path.join(ROOT, "output", safe + ".html")
    e = html.escape
    body = []
    for t in lesson.get("tasks", []):
        by = {}
        for it in t.get("items", []):
            by.setdefault(it["part"], []).append(it)
        src = lambda it: '<span class="src" title="%s">[%s]</span>' % (e(it.get("quote", "")), e(it["source"]))
        sec = lambda part: "".join("<p>%s %s</p>" % (e(it["text"]), src(it)) for it in by.get(part, []))
        choices = "".join('<li><button onclick="this.closest(\'section\').classList.add(\'shown\')">%s</button> %s</li>' % (e(it["text"]), src(it)) for it in by.get("lua_chon", []))
        body.append('<section><h2>%s</h2><h3>Mục tiêu</h3>%s<h3>Bạn là agent. Bạn đang thấy</h3>%s<h3>Công cụ bạn có</h3>%s'
                    '<h3>Bước tiếp theo bạn chọn?</h3><ul>%s</ul><div class="reveal"><h3>Bước đúng</h3>%s<h3>Lỗi dễ mắc</h3>%s</div></section>'
                    % (e(t.get("name", "")), sec("muc_tieu"), sec("agent_thay"), sec("cong_cu"), choices, sec("buoc_dung"), sec("loi_de_mac")))
    nil = "".join("<li>%s</li>" % e(x) for x in lesson.get("not_in_lab", []))
    page = ('<!doctype html><meta charset="utf-8"><title>Be The Agent · %s</title>'
            '<style>body{font-family:sans-serif;max-width:760px;margin:auto;padding:16px}.reveal{display:none}.shown .reveal{display:block}.src{color:#666;font-size:.85em}</style>'
            '<h1>Be The Agent · %s</h1><p><i>Bản nháp, chờ trợ giảng duyệt.</i></p>%s<h2>Không có trong bài</h2><ul>%s</ul>'
            % (e(lab_name), e(lab_name), "".join(body), nil))
    open(out, "w", encoding="utf-8").write(page)
    return os.path.relpath(out, ROOT).replace(os.sep, "/")
