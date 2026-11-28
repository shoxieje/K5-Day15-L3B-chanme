"""Khung giao diện chung cho 3 trang của mỗi lab (đóng vai · slide · tóm tắt).
Không gọi model, không tác động ra ngoài. Chỉ dựng chuỗi HTML."""
import html
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PART_LABEL = {
    "muc_tieu": "Mục tiêu",
    "agent_thay": "Bạn đang thấy",
    "cong_cu": "Công cụ",
    "lua_chon": "Lựa chọn",
    "buoc_dung": "Bước đúng",
    "loi_de_mac": "Lỗi dễ mắc",
}

# (khóa, nhãn, hậu tố file)
KINDS = [("roleplay", "Đóng vai", ""), ("slides", "Slide", "-slides"), ("summary", "Tóm tắt", "-summary")]

CSS = """
:root{color-scheme:light;--bg:#ffffff;--fg:#1c1917;--muted:#78716c;--line:#e7e5e4;--accent:#2563eb;--soft:#f5f5f4;--warn:#b45309}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:24px 16px 64px}
.top{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
.top .wrap{display:flex;align-items:center;gap:16px;padding-top:12px;padding-bottom:12px;flex-wrap:wrap}
.brand{font-weight:600;font-size:14px;letter-spacing:.01em;margin-right:auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}
.tabs{display:flex;gap:4px}
.tabs a{font-size:14px;color:var(--muted);text-decoration:none;padding:4px 10px;border-radius:6px}
.tabs a:hover{color:var(--fg);background:var(--soft)}
.tabs a[aria-current]{color:var(--fg);background:var(--soft);font-weight:600}
h1{font-size:28px;line-height:1.25;margin:8px 0 4px;letter-spacing:-.01em}
h2{font-size:20px;margin:40px 0 8px;letter-spacing:-.005em}
h3{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:24px 0 6px;font-weight:600}
p{margin:6px 0}
.note{color:var(--muted);font-size:14px}
.src{color:var(--muted);font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap;cursor:help}
ul{padding-left:20px}
a{color:var(--accent)}
button{font:inherit;color:inherit}
@media print{.top{display:none}body{background:#fff;color:#000}}
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def safe_name(lab_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", lab_name).strip("-") or "lab"


def out_path(lab_name: str, kind: str) -> str:
    """Đường dẫn tuyệt đối của file output cho một loại trang."""
    suffix = dict((k, s) for k, _, s in KINDS)[kind]
    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    return os.path.join(ROOT, "output", safe_name(lab_name) + suffix + ".html")


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def src(item: dict) -> str:
    """Nhãn nguồn file:dòng, hover hiện trích dẫn nguyên văn."""
    return '<span class="src" title="%s">%s</span>' % (esc(item.get("quote", "")), esc(item.get("source", "")))


def by_part(task: dict) -> dict:
    out = {}
    for it in task.get("items", []):
        out.setdefault(it.get("part"), []).append(it)
    return out


def page(lab_name: str, kind: str, body: str, extra_css: str = "", script: str = "") -> str:
    """Bọc body trong khung chung: thanh trên có tên lab + 3 tab (đóng vai · slide · tóm tắt)."""
    base = safe_name(lab_name)
    tabs = "".join(
        '<a href="%s%s.html"%s>%s</a>' % (base, suf, ' aria-current="page"' if k == kind else "", label)
        for k, label, suf in KINDS
    )
    return (
        '<!doctype html><html lang="vi"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>%s · %s</title><style>%s%s</style></head><body>"
        '<header class="top"><div class="wrap"><span class="brand">Be The Agent · %s</span><nav class="tabs">%s</nav></div></header>'
        "%s%s</body></html>"
        % (esc(lab_name), dict((k, l) for k, l, _ in KINDS)[kind], CSS, extra_css, esc(lab_name), tabs, body,
           ("<script>%s</script>" % script) if script else "")
    )
