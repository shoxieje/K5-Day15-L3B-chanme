"""Renderer HTML học lại learning-v1 — docs/design/learning-html-contract.md §4–§6.

    build_learning_html(model, meta) -> str

Hàm thuần: không đọc/ghi file, không mạng, không gọi model. `model` là model learning-v1 đã qua validator
(codebase/learning_schema.py); `meta` = {generation_id, generated_at, model, prompt_version, template_version, fake}.

Kết quả là MỘT file HTML UTF-8 tự chứa: CSS/JS nội tuyến, không font/CDN/ảnh ngoài, không fetch. Dữ liệu chỉ được
nhúng trong <script type="application/json" id="learning-data"> với <, >, &, U+2028, U+2029 đã escape; JS dựng mọi
nội dung bằng createElement/textContent (không chèn chuỗi HTML từ dữ liệu). Python dựng sẵn bản tĩnh tối thiểu
(tiêu đề, trạng thái, bảy mục, ghi chú <noscript>) bằng html.escape để file vẫn đọc được khi tắt JavaScript.
"""
import html
import json

TEMPLATE_VERSION = "learning-html-1"

SECTIONS = (
    ("overview", "1. Bài của tôi giải quyết gì?"),
    ("workflow", "2. Toàn cảnh workflow"),
    ("walkthrough", "3. Hiểu từng bước"),
    ("decisions", "4. Quyết định quan trọng"),
    ("evidence", "5. Kết quả, bằng chứng và rubric"),
    ("teachback", "6. Thử giải thích lại"),
    ("presentation", "7. Luyện thuyết trình"),
)

# mục rỗng: (thiếu gì, cách bổ sung) — JS đọc lại từ data-empty-* nên chỉ có một nguồn chữ
EMPTY = {
    "overview": ("Chưa có yêu cầu hay mục tiêu học nào được trích từ Markdown.",
                 "Thêm đề bài/rubric dạng Markdown ở thư mục gốc của repo rồi sinh lại trang."),
    "workflow": ("Chưa có sơ đồ workflow có nguồn.",
                 "Bổ sung mô tả các bước/thứ tự làm bài trong Markdown cấp gốc rồi sinh lại."),
    "walkthrough": ("Chưa có bước nào để giải thích.",
                    "Cần workflow có nguồn (mục 2) trước; bổ sung mô tả từng bước trong Markdown rồi sinh lại."),
    "decisions": ("Chưa có quyết định nào được tài liệu nêu.",
                  "Ghi các phương án và lý do lựa chọn (ví dụ trong báo cáo) ở Markdown cấp gốc rồi sinh lại."),
    "evidence": ("Chưa có yêu cầu, nhận định hay bằng chứng nào.",
                 "Thêm báo cáo bài làm (Markdown cấp gốc) có kết quả và nguồn rồi sinh lại."),
    "teachback": ("Chưa có câu hỏi tự giải thích.",
                  "Cần mục tiêu học có nguồn (mục 1); sinh lại sau khi bổ sung đề/rubric."),
    "presentation": ("Chưa có thẻ trình bày.",
                     "Cần nhận định/bằng chứng có nguồn; bổ sung báo cáo bài làm rồi sinh lại."),
}

FAKE_TEXT = "CHẾ ĐỘ GIẢ — nội dung minh họa, không phải phân tích của model, không dùng làm bằng chứng"
STATE_TEXT = {
    "blocked": "Không dựng được bài học",
    "incomplete": "Bản nháp chưa đủ nguồn",
    "draft_ready": "Sẵn sàng để người duyệt xem — không có nghĩa bài đã hoàn thành hay bạn đã hiểu",
}
REVIEW_TEXT = "Chưa được người duyệt xem"
CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; "
       "base-uri 'none'; form-action 'none'")
SEV = {"info": "Thông tin", "warning": "Cảnh báo", "error": "Lỗi"}
READ_STATUS = {"read": "Đã đọc", "empty": "Rỗng", "unreadable": "Không đọc được", "excluded": "Bị loại",
               "over_limit": "Vượt giới hạn", "changed": "Đổi trong lúc đọc"}
CATEGORY = {"learning_goal": "Mục tiêu học", "deliverable": "Sản phẩm cần nộp", "constraint": "Ràng buộc",
            "assessment": "Tiêu chí đánh giá"}
GRAPH_KIND = {"learning_order": "Thứ tự học/làm theo đề", "system_flow": "Luồng hệ thống",
              "decision_process": "Quy trình quyết định"}


def _e(x):
    return html.escape("" if x is None else str(x), quote=True)


def _l(x):
    return x if isinstance(x, list) else []


def _d(x):
    return x if isinstance(x, dict) else {}


def json_for_script(data):
    """JSON an toàn để đặt trong <script type="application/json">: không thể đóng thẻ, không có U+2028/2029 thô."""
    s = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (s.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def _is_fake(model, meta):
    issues = _l(_d(model.get("validation")).get("issues"))
    return bool(meta.get("fake")) or any(_d(i).get("code") == "fake_model" for i in issues)


def _ranges(rs):
    out = []
    for r in _l(rs):
        r = _d(r)
        a, b = r.get("start_line"), r.get("end_line")
        out.append(str(a) if a == b else "%s–%s" % (a, b))
    return ", ".join(out) or "—"


def _coverage_text(cov):
    cov = _d(cov)
    return "Đã xử lý %s/%s file · %s/%s dòng · %s dòng đã che" % (
        cov.get("files_processed", "?"), cov.get("files_total", "?"), cov.get("lines_processed", "?"),
        cov.get("lines_total", "?"), cov.get("redacted_lines", "?"))


def _issues_html(issues):
    items = []
    for i in _l(issues):
        i = _d(i)
        scope = ", ".join(str(x) for x in _l(i.get("scope_ids")))
        items.append('<li><span class="chip sev-%s">%s</span> <code>%s</code> %s%s</li>' % (
            _e(i.get("severity") if i.get("severity") in SEV else "info"), _e(SEV.get(i.get("severity"), "Thông tin")),
            _e(i.get("code")), _e(i.get("message")), (" <span class=\"muted\">(phạm vi: %s)</span>" % _e(scope)) if scope else ""))
    return "<ul class=\"issues\">%s</ul>" % "".join(items) if items else "<p>Không có vấn đề nào được ghi.</p>"


def _status_html(model, meta):
    val = _d(model.get("validation"))
    state = val.get("content_state")
    snap = _d(model.get("repo_snapshot"))
    parts = []
    if _is_fake(model, meta):
        parts.append('<div class="banner banner-fake" role="alert"><strong>%s</strong></div>' % _e(FAKE_TEXT))
    if state == "incomplete":
        gaps = len(_l(model.get("gaps")))
        unresolved = sum(1 for c in _l(model.get("conflicts")) if _d(c).get("state") == "unresolved")
        unres_ids = ", ".join(str(x) for x in _l(_d(val.get("coverage_summary")).get("unresolved_issue_ids")))
        parts.append(
            '<div class="banner banner-incomplete" role="status"><p class="banner-title"><strong>%s</strong></p>'
            '<p>Các phần hợp lệ vẫn xem được. Những điểm chưa rõ:</p>%s<ul>'
            '<li>%d khoảng trống (gap) và %d mâu thuẫn chưa giải quyết — xem mục 5.</li>%s</ul></div>'
            % (_e(STATE_TEXT["incomplete"]), _issues_html(val.get("issues")), gaps, unresolved,
               ("<li>Vấn đề chưa xử lý: %s</li>" % _e(unres_ids)) if unres_ids else ""))
    elif state == "draft_ready":
        parts.append('<div class="banner banner-ready" role="status"><p class="banner-title"><strong>%s</strong></p>'
                     '<p>Khoảng trống nhỏ vẫn được hiện ở từng mục.</p></div>' % _e(STATE_TEXT["draft_ready"]))
    elif state == "blocked":
        parts.append('<div class="banner banner-blocked" role="alert"><p class="banner-title"><strong>%s</strong></p>'
                     '<p>Không có nguồn đọc được hoặc còn lỗi an toàn/cấu trúc chưa khắc phục, nên trang chỉ giải '
                     'thích lỗi, không có bài học.</p></div>' % _e(STATE_TEXT["blocked"]))
    else:
        parts.append('<div class="banner banner-incomplete" role="status"><p class="banner-title"><strong>'
                     'Trạng thái nội dung không rõ — coi như bản nháp chưa đủ nguồn</strong></p></div>')
    review_extra = " — cần người duyệt" if val.get("review_state") == "needs_review" else ""
    parts.append('<p class="review"><strong>Trạng thái duyệt: %s%s.</strong> Trang này không có nút đánh dấu đã '
                 'duyệt. Nhận xét/ghi chú do agent tạo là bản nháp, không phải điểm chính thức.</p>'
                 % (_e(REVIEW_TEXT), _e(review_extra)))
    sid = str(snap.get("snapshot_id") or "")
    parts.append(
        '<dl class="meta"><div><dt>Độ phủ nguồn</dt><dd>%s</dd></div><div><dt>Snapshot</dt><dd><code>%s</code></dd></div>'
        '<div><dt>Sinh lúc</dt><dd>%s</dd></div><div><dt>Model</dt><dd>%s</dd></div>'
        '<div><dt>Prompt</dt><dd>%s</dd></div><div><dt>Template</dt><dd>%s</dd></div>'
        '<div><dt>Mã lần sinh</dt><dd><code>%s</code></dd></div></dl>'
        % (_e(_coverage_text(val.get("coverage_summary"))), _e(sid[:12] or "—"), _e(meta.get("generated_at")),
           _e(meta.get("model")), _e(meta.get("prompt_version")),
           _e(meta.get("template_version") or TEMPLATE_VERSION), _e(meta.get("generation_id"))))
    return "\n".join(parts)


def _manifest_html(model):
    rows = []
    for m in _l(model.get("source_manifest")):
        m = _d(m)
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td><code>%s</code></td></tr>" % (
            _e(m.get("name")), _e(m.get("line_count") if m.get("line_count") is not None else "—"),
            _e(READ_STATUS.get(m.get("read_status"), m.get("read_status"))), _e(_ranges(m.get("processed_ranges"))),
            _e(_ranges(m.get("redacted_ranges"))), _e((m.get("sha256") or "—")[:12])))
    if not rows:
        return "<p>Không có file Markdown nào trong manifest.</p>"
    return ('<div class="tbl-wrap"><table><caption>Các file nguồn</caption><thead><tr><th scope="col">Tệp</th>'
            '<th scope="col">Số dòng</th><th scope="col">Trạng thái đọc</th><th scope="col">Dòng đã xử lý</th>'
            '<th scope="col">Dòng đã che</th><th scope="col">SHA256 (rút gọn)</th></tr></thead><tbody>%s</tbody>'
            '</table></div>' % "".join(rows))


def _fallback(sid, model):
    """Bản tĩnh tối thiểu cho mỗi mục (JS thay thế khi chạy)."""
    def empty():
        what, act = EMPTY[sid]
        return ('<div class="missing"><p><strong>Còn thiếu: </strong>%s</p><p><strong>Cách bổ sung: </strong>%s</p></div>'
                % (_e(what), _e(act)))

    reqs = _l(model.get("requirements"))
    graphs = _l(_d(model.get("workflow")).get("graphs"))
    inters = _l(model.get("interactions"))
    pres = _d(model.get("presentation"))
    if sid == "overview":
        if not reqs:
            return empty()
        return "<ul>%s</ul>" % "".join("<li>[%s] %s</li>" % (_e(CATEGORY.get(_d(q).get("category"), "?")),
                                                          _e(_d(q).get("text"))) for q in reqs)
    if sid == "workflow":
        if not graphs:
            return empty()
        return "".join("<p><strong>%s</strong> (%s)</p><ol>%s</ol>" % (
            _e(_d(g).get("label")), _e(GRAPH_KIND.get(_d(g).get("graph_kind"), "")),
            "".join("<li>%s</li>" % _e(_d(n).get("label")) for n in _l(_d(g).get("nodes")))) for g in graphs)
    if sid == "walkthrough":
        nodes = sum(len(_l(_d(g).get("nodes"))) for g in graphs)
        traces = [i for i in inters if _d(i).get("type") == "trace_flow"]
        if not nodes and not traces:
            return empty()
        return "<p>%d bước, %d bài theo dấu luồng.</p>" % (nodes, len(traces))
    if sid == "decisions":
        decs = _l(model.get("decisions"))
        ch = [i for i in inters if _d(i).get("type") == "choose_explain"]
        if not decs and not ch:
            return empty()
        return "<ul>%s</ul>" % "".join("<li>%s</li>" % _e(_d(d).get("question")) for d in decs)
    if sid == "evidence":
        n = [len(_l(model.get(k))) for k in ("claims", "evidence", "measurements", "gaps", "conflicts")]
        if not reqs and not n[0] and not n[1] and not n[2]:
            return empty() + _manifest_html(model)
        return ("<p>%d yêu cầu, %d nhận định, %d bằng chứng, %d số đo, %d khoảng trống, %d mâu thuẫn.</p>%s"
                % (len(reqs), n[0], n[1], n[2], n[3], n[4], _manifest_html(model)))
    if sid == "teachback":
        tb = [i for i in inters if _d(i).get("type") == "teach_back"]
        qs = _l(pres.get("questions"))
        if not tb and not qs:
            return empty()
        return "<ul>%s</ul>" % "".join(
            ["<li>%s</li>" % _e(_d(i).get("title")) for i in tb] + ["<li>%s</li>" % _e(_d(q).get("prompt")) for q in qs])
    if sid == "presentation":
        cards = _l(pres.get("cards"))
        if not cards:
            return empty()
        return "<ol>%s</ol>" % "".join("<li>%s</li>" % _e(_d(c).get("title")) for c in cards)
    return ""


def _head(title):
    return ('<!doctype html>\n<html lang="vi">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<meta http-equiv="Content-Security-Policy" content="%s">\n'
            '<meta name="referrer" content="no-referrer">\n<meta name="color-scheme" content="light">\n'
            '<title>%s</title>\n<style>\n%s\n</style>\n</head>\n' % (_e(CSP), _e(title), CSS))


def build_learning_html(model, meta):
    """Một tài liệu HTML hoàn chỉnh (str). Cùng template cho mọi model learning-v1."""
    model = _d(model)
    meta = dict(_d(meta))
    meta.setdefault("template_version", TEMPLATE_VERSION)
    label = str(_d(model.get("repo_snapshot")).get("display_label") or "Bài lab")
    title = label + " · Học lại bài lab"
    state = _d(model.get("validation")).get("content_state")
    data = json_for_script({"model": model, "meta": meta})
    head = _head(title)
    top = ('<header class="top" role="banner"><p class="eyebrow">Trang học lại sau bài lab · learning-v1</p>'
           '<h1>%s</h1>\n%s\n' % (_e(label), _status_html(model, meta)))
    if state == "blocked":
        val = _d(model.get("validation"))
        # trang blocked không mang nội dung bài học, kể cả trong dữ liệu nhúng
        data = json_for_script({"model": {k: model.get(k) for k in ("schema_version", "repo_snapshot",
                                                                     "source_manifest", "validation")},
                                "meta": meta})
        body = (
            '<body class="state-blocked">\n%s</header>\n<main id="main" class="blocked-page">'
            '<section class="lesson-blocked" aria-labelledby="h-blocked"><h2 id="h-blocked">Vì sao chưa có bài học</h2>'
            '<p>Trang này cố ý không hiển thị nội dung học (mục tiêu, workflow, quyết định, câu hỏi) vì nguồn chưa đủ '
            'an toàn hoặc chưa đọc được.</p><h3>Vấn đề được ghi</h3>%s<h3>Độ phủ nguồn</h3><p>%s</p>%s'
            '<h3>Cách khắc phục</h3><ul><li>Kiểm tra repo có ít nhất một file Markdown đọc được (UTF-8) ở thư mục '
            'gốc.</li><li>Sửa các lỗi cấu trúc/an toàn ở trên rồi sinh lại trang.</li></ul></section></main>\n'
            '<script type="application/json" id="learning-data">%s</script>\n</body>\n</html>\n'
            % (top, _issues_html(val.get("issues")), _e(_coverage_text(val.get("coverage_summary"))),
               _manifest_html(model), data))
        return head + body
    toc = "".join('<li><a href="#%s" data-target="%s"><span class="toc-text">%s</span>'
                  '<span class="toc-mark"></span></a></li>' % (sid, sid, _e(t)) for sid, t in SECTIONS)
    sections = "\n".join(
        '<section id="%s" class="lesson" data-section="%s" aria-labelledby="h-%s" data-empty-what="%s" '
        'data-empty-action="%s"><h2 id="h-%s" tabindex="-1">%s</h2><div class="sec-body">%s</div></section>'
        % (sid, sid, sid, _e(EMPTY[sid][0]), _e(EMPTY[sid][1]), sid, _e(t), _fallback(sid, model))
        for sid, t in SECTIONS)
    body = (
        '<body>\n<a class="skip" href="#main">Bỏ qua tới nội dung</a>\n%s'
        '<noscript><p class="banner banner-incomplete">JavaScript đang tắt: bạn chỉ xem được bản tóm tắt tĩnh. '
        'Trích dẫn nguồn, sơ đồ, câu hỏi tương tác và chế độ trình bày cần JavaScript (không cần mạng).</p></noscript>'
        '<div id="toolbar-slot" class="no-print"></div>\n</header>\n'
        '<div class="layout"><nav class="toc" aria-label="Mục lục"><p class="toc-title">Mục lục</p><ol>%s</ol>'
        '<p class="toc-progress"><progress id="toc-bar" max="7" value="0"></progress> '
        '<span id="toc-count">Đã xem 0/7 mục (chỉ trong phiên này)</span></p></nav>\n'
        '<main id="main" tabindex="-1">\n%s\n</main></div>\n'
        '<script type="application/json" id="learning-data">%s</script>\n<script>\n%s\n</script>\n</body>\n</html>\n'
        % (top, toc, sections, data, JS))
    return head + body


CSS = r"""
:root{--bg:#f6f6f3;--surface:#fff;--ink:#1b1b1b;--muted:#4a5160;--line:#cfd4dc;--accent:#1d4ed8;--focus:#b45309}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
[hidden]{display:none!important}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
a{color:var(--accent)}
code{font-family:ui-monospace,Consolas,monospace;font-size:.9em;background:#eef0f3;padding:0 4px;border-radius:4px;overflow-wrap:anywhere}
.skip{position:absolute;left:-9999px;top:0}
.skip:focus{left:16px;top:8px;background:#fff;padding:8px 12px;z-index:2000}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.muted{color:var(--muted)}
header.top{background:var(--surface);border-bottom:1px solid var(--line);padding:16px 24px}
header.top h1{margin:.1em 0 .4em;font-size:1.7rem;line-height:1.25}
.eyebrow{margin:0;color:var(--muted);font-size:.9rem}
.banner{border:1px solid var(--line);border-left:6px solid var(--muted);border-radius:8px;padding:10px 14px;margin:10px 0;background:#fff}
.banner p{margin:.3em 0}
.banner-title{font-size:1.1rem}
.banner-incomplete{border-left-color:#b45309;background:#fff8eb}
.banner-ready{border-left-color:#1d4ed8;background:#eef4ff}
.banner-blocked{border-left-color:#991b1b;background:#fff1f1}
.banner-fake{background:#7f1d1d;color:#fff;border:4px dashed #fff;outline:4px solid #7f1d1d;font-size:1.35rem;text-align:center;padding:16px}
.review{margin:8px 0}
dl.meta{display:flex;flex-wrap:wrap;gap:4px 20px;margin:8px 0 0;font-size:.9rem}
dl.meta div{display:flex;gap:6px}
dl.meta dt{color:var(--muted)}
dl.meta dd{margin:0}
ul.issues{padding-left:1.2em}
.toolbar{display:flex;flex-wrap:wrap;gap:10px 18px;margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}
.toolbar fieldset{border:1px solid var(--line);border-radius:8px;padding:6px 10px 8px;margin:0;display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center}
.toolbar legend{font-weight:600;font-size:.9rem;padding:0 4px}
.store-msg{flex-basis:100%;margin:0;font-size:.9rem}
.pending-import{flex-basis:100%;background:#fff8eb;border:1px solid #b45309;border-radius:6px;padding:8px}
button{font:inherit;font-size:.95rem;padding:5px 12px;border-radius:6px;border:1px solid #3b4252;background:#fff;color:#111;cursor:pointer}
button:hover:not([disabled]){background:#eef2f7}
button[disabled]{color:#5b6270;border-color:#9aa1ad;background:#f1f2f4;cursor:not-allowed}
button.primary{background:#1d4ed8;color:#fff;border-color:#1d4ed8}
button.primary:hover:not([disabled]){background:#1e40af}
input[type=file]{font-size:.9rem;max-width:100%}
label.inline{display:inline-flex;gap:6px;align-items:center}
.layout{display:grid;grid-template-columns:250px minmax(0,1fr);gap:24px;max-width:1320px;margin:0 auto;padding:16px 24px}
nav.toc{position:sticky;top:12px;align-self:start;max-height:calc(100vh - 24px);overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.toc-title{margin:0 0 6px;font-weight:700}
nav.toc ol{list-style:none;margin:0;padding:0}
nav.toc li a{display:flex;justify-content:space-between;gap:6px;padding:5px 6px;border-radius:6px;text-decoration:none;color:var(--ink)}
nav.toc li a:hover{background:#eef2f7}
nav.toc li a[aria-current]{background:#e3ebff;font-weight:700}
.toc-mark{color:#14532d;font-weight:700}
.toc-progress{font-size:.85rem;color:var(--muted);margin:10px 0 0}
.toc-progress progress{width:100%}
main{min-width:0}
main:focus{outline:none}
section.lesson,.lesson-blocked{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin-bottom:24px;scroll-margin-top:12px}
section.lesson>h2{margin:0 0 10px;font-size:1.4rem}
section.lesson>h2:focus{outline:none}
h3{font-size:1.15rem;margin:1.2em 0 .5em}
h4{font-size:1.02rem;margin:.2em 0 .4em}
.blocked-page{max-width:1000px;margin:16px auto;padding:0 16px}
.card{border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:10px 0;background:#fcfcfb}
.item{margin:6px 0;padding:6px 0;border-bottom:1px dashed #e1e4e8}
.item:last-child{border-bottom:none}
.item p{margin:.2em 0}
.item-text{font-weight:500}
ul.plain{list-style:none;padding-left:0;margin:.3em 0}
.chip{display:inline-block;padding:0 8px;border-radius:999px;font-size:.78rem;font-weight:700;border:1px solid #6b7280;margin:0 4px 2px 0;line-height:1.6;background:#f3f4f6;color:#1f2937;vertical-align:baseline;white-space:nowrap}
.ful-not_reported{background:#f3f4f6;color:#374151;border-style:dashed}
.ful-reported_complete{background:#dcfce7;color:#14532d;border-color:#15803d}
.ful-reported_partial{background:#fef3c7;color:#713f12;border-color:#a16207}
.ful-reported_not_done{background:#fee2e2;color:#7f1d1d;border-color:#b91c1c}
.ful-conflicting,.evs-conflicting{background:#f3e8ff;color:#581c87;border-color:#7e22ce}
.kind-required{background:#dbeafe;color:#1e3a8a;border-color:#1d4ed8}
.kind-reported{background:#ccfbf1;color:#134e4a;border-color:#0f766e}
.kind-document_observation{background:#f4f4f5;color:#3f3f46}
.kind-inference{background:#ede9fe;color:#4c1d95;border-color:#6d28d9;border-style:dotted}
.kind-hypothetical{background:#ffedd5;color:#7c2d12;border-color:#c2410c;border-style:dashed}
.evs-reported_in_markdown{background:#e0f2fe;color:#0c4a6e;border-color:#0369a1}
.evs-embedded_record_unverified{background:#fef9c3;color:#713f12;border-color:#a16207}
.evs-referenced_unread{background:#f1f5f9;color:#334155;border-style:dashed}
.evs-missing{background:#fee2e2;color:#7f1d1d;border-color:#b91c1c}
.chip-sim{background:#9a3412;color:#fff;border:2px solid #431407}
.chip-gap{background:#fff1f1;color:#991b1b;border-color:#b91c1c}
.chip-infer{background:#ede9fe;color:#4c1d95;border-style:dotted}
.nk-required_step{background:#dbeafe;color:#1e3a8a}
.nk-reported_step{background:#ccfbf1;color:#134e4a}
.nk-inferred_step{background:#ede9fe;color:#4c1d95;border-style:dotted}
.sev-error{background:#fee2e2;color:#7f1d1d}
.sev-warning{background:#fef3c7;color:#713f12}
.sev-info{background:#e0f2fe;color:#0c4a6e}
.chip-accept{background:#dcfce7;color:#14532d;border-color:#15803d}
.refs{margin:.25em 0}
.ref-row{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.ref-lead{font-size:.8rem;color:var(--muted)}
.refs-none{font-size:.8rem;color:var(--muted);font-style:italic}
button.ref-btn{font-family:ui-monospace,Consolas,monospace;font-size:.76rem;padding:0 6px;border-radius:4px;border:1px solid #64748b;background:#f8fafc;color:#1e293b;line-height:1.6}
button.ref-btn[aria-expanded=true]{background:#1e293b;color:#fff}
.ref-panel{border-left:4px solid #64748b;background:#f8fafc;margin:4px 0;padding:6px 10px;font-size:.92rem}
.ref-meta{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.ref-loc{font-family:ui-monospace,Consolas,monospace;font-size:.85rem}
.ref-quote{margin:4px 0 0;padding:0;white-space:pre-wrap;overflow-wrap:anywhere}
.missing{border:1px dashed #b45309;background:#fffaf0;border-radius:8px;padding:8px 12px;margin:8px 0}
.missing p{margin:.2em 0}
.gap{color:#7f1d1d}
.sec-error{border:2px solid #991b1b;background:#fff1f1;padding:8px 12px;border-radius:8px}
.tbl-wrap{overflow-x:auto;margin:8px 0}
table{border-collapse:collapse;width:100%;font-size:.92rem;background:#fff}
caption{text-align:left;font-weight:700;padding:4px 0}
th,td{border:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left}
th{background:#f1f3f6}
td .chip{white-space:normal}
.tbl-wrap table{min-width:820px}
td label.inline{align-items:flex-start;font-size:.88rem}
.svg-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:#fff;margin:8px 0}
.wf-svg{display:block;width:100%;height:auto}
.wf-node rect{fill:#eff6ff;stroke:#1e3a8a;stroke-width:1.5}
.wf-node.kind-reported_step rect{fill:#f0fdfa;stroke:#115e59}
.wf-node.kind-inferred_step rect{fill:#faf5ff;stroke:#6b21a8;stroke-dasharray:5 3}
.wf-node.has-gap rect{stroke:#b91c1c;stroke-width:2}
.wf-node.is-current rect{stroke:#b45309;stroke-width:4;fill:#fff7ed}
.wf-badge{font-size:11.5px;font-weight:700;fill:#1f2937;letter-spacing:.03em}
.wf-label{font-size:14.5px;fill:#111}
.wf-gap{font-size:11.5px;fill:#991b1b;font-weight:700}
.wf-edge{fill:none;stroke:#374151;stroke-width:1.6}
.wf-edge.inferred{stroke-dasharray:2 4;stroke-width:2}
.wf-fb{fill:none;stroke:#9a3412;stroke-width:1.6;stroke-dasharray:7 4}
.wf-arrow{fill:#374151}
.wf-arrow-fb{fill:#9a3412}
.wf-elabel{font-size:11px;fill:#4c1d95;font-style:italic}
.wf-fblabel{font-size:11px;fill:#9a3412;font-weight:600}
.token-g{transition:transform .45s ease}
.token-g rect{fill:#b45309}
.token-g text{fill:#fff;font-size:11px;font-weight:700}
.legend{font-size:.85rem;color:var(--muted);margin:.2em 0}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}
.step-counter{font-weight:700;margin:0}
.state-change{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:6px 0}
.state{border:1px solid var(--line);border-radius:6px;padding:2px 8px;background:#fff}
.token-chip{background:#b45309;color:#fff;border-color:#7c2d12}
.field{margin:8px 0}
.field label{display:block;font-weight:600;margin-bottom:3px}
textarea{width:100%;font:inherit;padding:6px 8px;border:1px solid #6b7280;border-radius:6px;background:#fff;color:#111}
fieldset.choices{border:1px solid var(--line);border-radius:8px;padding:8px 12px}
fieldset.choices legend{font-weight:600}
fieldset.choices label{display:block;padding:3px 0}
.answer{border-left:4px solid #15803d;background:#f3fbf5;padding:8px 12px;margin:8px 0;border-radius:0 8px 8px 0}
.hint{border-left-color:#a16207;background:#fffbeb}
.checklist li{margin:4px 0}
.tried{color:#14532d;font-weight:600;margin:4px 0}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.cols>div{border:1px solid var(--line);border-radius:6px;padding:6px 10px;background:#fff}
.slides{position:fixed;inset:0;background:#fff;z-index:1000;display:flex;flex-direction:column}
.slides-top{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;padding:10px 16px;border-bottom:1px solid var(--line);background:#f8fafc}
.slides-top h2{font-size:1.1rem;margin:0}
.slides-toc{display:flex;flex-wrap:wrap;gap:4px;list-style:none;margin:0;padding:0}
.slides-toc button[aria-current]{background:#1e293b;color:#fff}
.slides-stage{flex:1;overflow:auto;padding:24px 5vw;font-size:1.12rem}
.slides-stage h2{font-size:1.8rem;margin-top:0}
.slides-stage h2:focus{outline:none}
.slides-bottom{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;border-top:1px solid var(--line)}
.slides .private-note-wrap.slide-notes-off{display:none}
body.no-motion *,body.no-motion *::before{transition:none!important;animation:none!important;scroll-behavior:auto!important}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}html{scroll-behavior:auto}}
@media (max-width:759px){
 .layout{grid-template-columns:1fr;padding:12px 16px;gap:12px}
 nav.toc{position:static;max-height:none}
 header.top{padding:12px 16px}
 header.top h1{font-size:1.35rem}
 section.lesson{padding:12px}
 .cols{grid-template-columns:1fr}
 .slides-stage{padding:16px}
}
@media print{
 .no-print,.toolbar,nav.toc,.skip,.controls-print,.slides{display:none!important}
 body{background:#fff;font-size:11pt}
 .layout{display:block;padding:0}
 header.top{border:none;padding:0 0 8pt}
 body.js section.lesson{display:none}
 body.js section.lesson.is-current,body.js.print-all section.lesson{display:block}
 section.lesson{border:none;padding:0;break-inside:auto}
 body:not(.print-answers) .answer{display:none!important}
 body:not(.print-notes) .private-note-wrap{display:none!important}
 .svg-wrap,.tbl-wrap{overflow:visible;border:none}
 .chip{border:1px solid #000}
 .banner-fake{border:4pt solid #000}
}
"""

JS = r"""
(function () {
'use strict';
function dict() { return Object.create(null); }
function isObj(x) { return !!x && typeof x === 'object' && !Array.isArray(x); }
function obj(x) { return isObj(x) ? x : {}; }
function arr(x) { return Array.isArray(x) ? x : []; }
function str(x) { return typeof x === 'string' ? x : (x === null || x === undefined) ? '' : String(x); }
function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
function lab(t, k, fb) { return has(t, k) ? t[k] : (fb === undefined ? str(k) : fb); }
function cssKey(x) { x = str(x); return /^[a-z_]{1,40}$/.test(x) ? x : 'unknown'; }
function trunc(s, n) { s = str(s); return s.length > n ? s.slice(0, n - 1) + '…' : s; }

var D = {};
try { var de = document.getElementById('learning-data'); D = JSON.parse(de ? de.textContent : '{}') || {}; } catch (e) { D = {}; }
var M = obj(D.model), META = obj(D.meta);
var SNAP = str(obj(M.repo_snapshot).snapshot_id);
var TV = str(META.template_version) || 'learning-html-1';
var STORE_KEY = 'learning-v1:' + SNAP + ':' + TV;

var ROLE = {assignment: 'Đề bài', rule: 'Luật', rubric: 'Rubric', instruction: 'Hướng dẫn',
  student_submission: 'Bài làm tự báo cáo', instructor_example: 'Ví dụ/hướng dẫn giảng viên', background: 'Nền',
  unknown: 'Chưa rõ vai trò'};
var FUL = {not_reported: 'Chưa có nội dung bài làm', reported_complete: 'Bài làm tự báo cáo: xong',
  reported_partial: 'Tự báo cáo: một phần', reported_not_done: 'Tự báo cáo: chưa làm', conflicting: 'Mâu thuẫn'};
var KIND = {required: 'Đề yêu cầu', reported: 'Bài làm tự báo cáo', document_observation: 'Quan sát trong tài liệu',
  inference: 'Suy luận', hypothetical: 'Giả định minh họa'};
var EVS = {reported_in_markdown: 'Ghi trong Markdown, chưa xác minh',
  embedded_record_unverified: 'Bản ghi dán vào, chưa xác minh', referenced_unread: 'Nguồn được nhắc tới — chưa đọc',
  missing: 'Thiếu', conflicting: 'Mâu thuẫn'};
var ORIGIN = {lab_simulated: 'Dữ liệu giả lập của lab', student_reported_measurement: 'Số do học viên tự báo cáo',
  teaching_hypothetical: 'Ví dụ giả định để dạy', unknown: 'Chưa rõ xuất xứ', not_applicable: 'Không áp dụng'};
var CAT = {learning_goal: 'Mục tiêu học', deliverable: 'Sản phẩm cần nộp', constraint: 'Ràng buộc',
  assessment: 'Tiêu chí đánh giá'};
var APPL = {required: 'Bắt buộc', optional: 'Tùy chọn', conditional: 'Có điều kiện', unresolved: 'Chưa rõ áp dụng'};
var GKIND = {learning_order: 'Thứ tự học/làm theo đề', system_flow: 'Luồng hệ thống',
  decision_process: 'Quy trình quyết định'};
var NKIND = {required_step: 'theo đề', reported_step: 'bài làm ghi nhận', inferred_step: 'suy luận'};
var CSTATE = {unresolved: 'Chưa giải quyết — cần người học/TA xác nhận',
  resolved_by_source: 'Có nguồn chỉ dẫn ưu tiên', resolved_by_human: 'Có ghi chú giải quyết của người'};
var RSTATUS = {read: 'Đã đọc', empty: 'Rỗng', unreadable: 'Không đọc được', excluded: 'Bị loại',
  over_limit: 'Vượt giới hạn', changed: 'Đổi trong lúc đọc'};
var SEV = {info: 'Thông tin', warning: 'Cảnh báo', error: 'Lỗi'};
var SIM_TEXT = 'Số liệu giả lập (simulated)';

// ---------------------------------------------------------------- DOM helpers (chỉ textContent)
var BLOCKED_ATTR = /^(on|href$|src$|srcdoc$|action$|formaction$|xlink:href$|style$)/i;
var uidN = 0;
function uid(p) { uidN += 1; return 'lx-' + p + '-' + uidN; }
function append(n, kids) {
  if (kids === null || kids === undefined || kids === false) return;
  if (!Array.isArray(kids)) kids = [kids];
  kids.forEach(function (k) {
    if (k === null || k === undefined || k === false) return;
    if (Array.isArray(k)) append(n, k);
    else if (typeof k === 'string' || typeof k === 'number') n.appendChild(document.createTextNode(String(k)));
    else n.appendChild(k);
  });
}
function setAttrs(n, props) {
  Object.keys(props || {}).forEach(function (k) {
    var v = props[k];
    if (v === null || v === undefined || v === false) return;
    if (k === 'cls') n.setAttribute('class', v);
    else if (k === 'text') n.textContent = str(v);
    else if (k === 'on') Object.keys(v).forEach(function (ev) { n.addEventListener(ev, v[ev]); });
    else if (BLOCKED_ATTR.test(k)) throw new Error('thuộc tính bị chặn: ' + k);
    else if (v === true) n.setAttribute(k, '');
    else n.setAttribute(k, str(v));
  });
}
function el(tag, props, kids) { var n = document.createElement(tag); setAttrs(n, props); append(n, kids); return n; }
var SVGNS = 'http://www.w3.org/2000/svg';
function sv(tag, props, kids) { var n = document.createElementNS(SVGNS, tag); setAttrs(n, props); append(n, kids); return n; }
function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
function btn(text, props, onClick) {
  var p = props || {}; p.type = 'button';
  var b = el('button', p, text);
  if (onClick) b.addEventListener('click', onClick);
  return b;
}

// ---------------------------------------------------------------- index
var IX = {ref: dict(), src: dict(), req: dict(), claim: dict(), ev: dict(), gap: dict(), conf: dict(), ctx: dict(),
  meas: dict(), graph: dict(), node: dict(), nodeGraph: dict(), dec: dict(), card: dict(), q: dict(), it: dict()};
function put(map, o, key) { if (isObj(o) && typeof o[key || 'id'] === 'string') map[o[key || 'id']] = o; }
arr(M.source_manifest).forEach(function (o) { put(IX.src, o, 'source_id'); });
arr(M.source_refs).forEach(function (o) { put(IX.ref, o); });
arr(M.requirements).forEach(function (o) { put(IX.req, o); });
arr(M.claims).forEach(function (o) { put(IX.claim, o); });
arr(M.evidence).forEach(function (o) { put(IX.ev, o); });
arr(M.gaps).forEach(function (o) { put(IX.gap, o); });
arr(M.conflicts).forEach(function (o) { put(IX.conf, o); });
arr(M.contexts).forEach(function (o) { put(IX.ctx, o); });
arr(M.measurements).forEach(function (o) { put(IX.meas, o); });
arr(M.decisions).forEach(function (o) { put(IX.dec, o); });
arr(M.interactions).forEach(function (o) { put(IX.it, o); });
var GRAPHS = arr(obj(M.workflow).graphs).filter(isObj);
GRAPHS.forEach(function (g) {
  put(IX.graph, g);
  arr(g.nodes).forEach(function (n) { put(IX.node, n); if (isObj(n) && typeof n.id === 'string') IX.nodeGraph[n.id] = g; });
});
var PRES = obj(M.presentation);
var CARDS = arr(PRES.cards).filter(isObj), QUESTIONS = arr(PRES.questions).filter(isObj);
CARDS.forEach(function (o) { put(IX.card, o); });
QUESTIONS.forEach(function (o) { put(IX.q, o); });
var INTER = arr(M.interactions).filter(isObj);

function evSim(e) { return !!(e && e.simulation_label_required === true); }
function claimSim(c) {
  return !!(c && (c.simulation_label_required === true || arr(c.evidence_ids).some(function (x) { return evSim(IX.ev[x]); })));
}
function measSim(m) { return claimSim(IX.claim[m.claim_id]) || arr(m.evidence_ids).some(function (x) { return evSim(IX.ev[x]); }); }
var SIM_REFS = dict();
arr(M.claims).forEach(function (c) { if (claimSim(c)) arr(c.source_ref_ids).forEach(function (r) { SIM_REFS[r] = true; }); });
arr(M.evidence).forEach(function (e) { if (evSim(e)) arr(e.source_ref_ids).forEach(function (r) { SIM_REFS[r] = true; }); });
function refsSim(ids) { return arr(ids).some(function (r) { return SIM_REFS[r] === true; }); }

function ctxText(c) {
  c = obj(c);
  var parts = [c.artifact_label, c.part_label, c.checkpoint_label, c.environment, c.scope].filter(function (x) { return typeof x === 'string' && x; });
  return parts.length ? parts.join(' · ') : 'Ngữ cảnh chưa rõ';
}
function describeId(id) {
  if (IX.req[id]) return 'Yêu cầu: ' + str(IX.req[id].text);
  if (IX.claim[id]) return 'Nhận định: ' + str(IX.claim[id].text);
  if (IX.node[id]) return 'Bước: ' + str(IX.node[id].label);
  if (IX.graph[id]) return 'Sơ đồ: ' + str(IX.graph[id].label);
  if (IX.ev[id]) return 'Bằng chứng: ' + str(IX.ev[id].description);
  if (IX.dec[id]) return 'Quyết định: ' + str(IX.dec[id].question);
  if (IX.card[id]) return 'Thẻ trình bày: ' + str(IX.card[id].title);
  if (IX.q[id]) return 'Câu hỏi: ' + str(IX.q[id].prompt);
  if (IX.it[id]) return 'Tương tác: ' + str(IX.it[id].title);
  if (IX.src[id]) return 'Tệp: ' + str(IX.src[id].name);
  if (IX.ctx[id]) return 'Ngữ cảnh: ' + ctxText(IX.ctx[id]);
  if (IX.gap[id]) return 'Khoảng trống: ' + str(IX.gap[id].reason);
  if (IX.conf[id]) return 'Mâu thuẫn: ' + str(IX.conf[id].topic);
  if (IX.meas[id]) return 'Số đo: ' + str(IX.meas[id].value);
  return str(id);
}

// ---------------------------------------------------------------- components
function chip(text, cls) { return el('span', {cls: 'chip ' + (cls || '')}, text); }
function simChip() { return chip(SIM_TEXT, 'chip-sim'); }
function fulChip(f) { return chip(lab(FUL, f, 'Trạng thái chưa biết: ' + str(f)), 'ful-' + cssKey(f)); }
function kindChip(k) { return chip(lab(KIND, k), 'kind-' + cssKey(k)); }
function evChip(s) { return chip(lab(EVS, s), 'evs-' + cssKey(s)); }
function nodeKindChip(k) { return chip(lab(NKIND, k), 'nk-' + cssKey(k)); }
function inferChip() { return chip('suy luận', 'chip-infer'); }
function gapChip() { return chip('Còn thiếu', 'chip-gap'); }
function para(cls, kids) { return el('p', {cls: cls || null}, kids); }
function labelled(name, value) { return para('kv', [el('span', {cls: 'muted', text: name + ': '}), value]); }

function refName(r) {
  var s = IX.src[r.source_id];
  var name = s ? str(s.name) : str(r.source_id);
  var a = r.start_line, b = r.end_line;
  return name + ':' + a + (b !== undefined && b !== a ? '-' + b : '');
}
function refsBlock(ids, opts) {
  opts = opts || {};
  var list = arr(ids).filter(function (id) { return IX.ref[id]; });
  var wrap = el('div', {cls: 'refs'});
  if (!list.length) {
    if (opts.noneText !== false) append(wrap, el('span', {cls: 'refs-none', text: opts.noneText || 'Không có trích dẫn nguồn trực tiếp'}));
    return wrap;
  }
  var row = el('div', {cls: 'ref-row'}, el('span', {cls: 'ref-lead', text: opts.lead || 'Nguồn:'}));
  var panels = el('div', {cls: 'ref-panels'});
  list.forEach(function (id) {
    var r = IX.ref[id], pid = uid('ref'), name = refName(r), role = lab(ROLE, r.role, ROLE.unknown);
    var panel = el('div', {cls: 'ref-panel', id: pid, hidden: true, role: 'region', 'aria-label': 'Trích dẫn ' + name}, [
      el('div', {cls: 'ref-meta'}, [chip(role, 'role'), el('span', {cls: 'ref-loc', text: name})]),
      el('blockquote', {cls: 'ref-quote', text: str(r.quote)})]);
    var b = btn(name, {cls: 'ref-btn', 'aria-expanded': 'false', 'aria-controls': pid, 'aria-label': 'Trích dẫn ' + name + ' (' + role + ')'});
    b.addEventListener('click', function () {
      var open = b.getAttribute('aria-expanded') === 'true';
      b.setAttribute('aria-expanded', open ? 'false' : 'true');
      panel.hidden = open;
    });
    append(row, b);
    append(panels, panel);
  });
  append(wrap, row);
  append(wrap, panels);
  return wrap;
}
function missing(what, action) {
  return el('div', {cls: 'missing'}, [para(null, [el('strong', {text: 'Còn thiếu: '}), what]),
    action ? para(null, [el('strong', {text: 'Cách bổ sung: '}), action]) : null]);
}
function sectionEmpty(sec) {
  return missing(sec.getAttribute('data-empty-what') || 'Chưa có nội dung.', sec.getAttribute('data-empty-action') || '');
}
function gapView(id) {
  var g = IX.gap[id];
  if (!g) return null;
  return el('div', {cls: 'item gap'}, [para(null, [gapChip(), el('span', {text: str(g.reason)})]),
    g.requested_evidence ? labelled('Cần bổ sung', str(g.requested_evidence)) : null]);
}
function gapList(ids) {
  var gs = arr(ids).map(gapView).filter(Boolean);
  return gs.length ? el('div', {cls: 'gaps'}, gs) : null;
}
function contextLine(ids) {
  var cs = arr(ids).filter(function (x) { return IX.ctx[x]; });
  return cs.length ? labelled('Ngữ cảnh', cs.map(function (x) { return ctxText(IX.ctx[x]); }).join(' | ')) : null;
}
function claimView(c, compact) {
  if (!c) return null;
  var kids = [para('item-head', [kindChip(c.kind), claimSim(c) ? simChip() : null, el('span', {cls: 'item-text', text: str(c.text)})])];
  if (c.kind === 'hypothetical') kids.push(labelled('Giả định', str(c.assumption) || '(chưa ghi giả định)'));
  if (c.kind === 'inference') {
    var ps = arr(c.premise_ids).filter(function (p) { return IX.claim[p]; });
    kids.push(labelled('Suy luận từ', ps.length ? ps.map(function (p) { return '«' + str(IX.claim[p].text) + '»'; }).join('; ') : '(không có tiền đề)'));
  }
  if (!compact) {
    if (c.data_origin && c.data_origin !== 'not_applicable') kids.push(labelled('Xuất xứ dữ liệu', lab(ORIGIN, c.data_origin)));
    kids.push(contextLine(c.context_ids));
  }
  kids.push(refsBlock(c.source_ref_ids));
  return el('div', {cls: 'item claim'}, kids);
}
function evView(e, compact) {
  if (!e) return null;
  var kids = [para('item-head', [evChip(e.status), evSim(e) ? simChip() : null, el('span', {cls: 'item-text', text: str(e.description)})])];
  if (e.external_ref) kids.push(labelled('Tệp được nhắc tới (chưa đọc, không tự mở)', el('code', {text: str(e.external_ref)})));
  if (!compact) {
    if (e.data_origin && e.data_origin !== 'not_applicable') kids.push(labelled('Xuất xứ dữ liệu', lab(ORIGIN, e.data_origin)));
    if (e.limitation) kids.push(labelled('Giới hạn', str(e.limitation)));
    kids.push(contextLine(e.context_ids));
  }
  kids.push(refsBlock(e.source_ref_ids));
  return el('div', {cls: 'item evidence'}, kids);
}
function reqView(q, opts) {
  opts = opts || {};
  var kids = [para('item-head', [fulChip(q.fulfillment), opts.showCat ? chip(lab(CAT, q.category), 'cat') : null,
    chip(lab(APPL, q.applicability), 'appl'), el('span', {cls: 'item-text', text: str(q.text)})])];
  kids.push(refsBlock(q.source_ref_ids));
  if (q.condition) kids.push(labelled('Điều kiện', str(q.condition)));
  if (q.scope) kids.push(labelled('Phạm vi', str(q.scope)));
  arr(q.overrides).forEach(function (ov) {
    ov = obj(ov);
    kids.push(el('div', {cls: 'override'}, [labelled('Thay thế yêu cầu', describeId(ov.requirement_id)), refsBlock(ov.source_ref_ids)]));
  });
  if (!opts.noEvidence) {
    var evs = arr(q.evidence_ids).filter(function (x) { return IX.ev[x]; });
    if (evs.length) kids.push(el('div', {cls: 'sub'}, [el('p', {cls: 'muted', text: 'Bằng chứng liên kết:'}), evs.map(function (x) { return evView(IX.ev[x], true); })]));
  }
  arr(q.conflict_ids).forEach(function (x) { if (IX.conf[x]) kids.push(para('gap', [chip('Mâu thuẫn', 'ful-conflicting'), str(IX.conf[x].topic) + ' — xem mục 5'])); });
  kids.push(gapList(q.gap_ids));
  return el('div', {cls: 'item req'}, kids);
}
function goalsLine(ids) {
  var gs = arr(ids).filter(function (x) { return IX.req[x]; });
  return gs.length ? labelled('Gắn với mục tiêu', gs.map(function (x) { return str(IX.req[x].text); }).join(' | ')) : null;
}
function basisLine(it, traceStyle) {
  if (it.basis === 'hypothetical') return para(null, chip(traceStyle ? 'Ví dụ giả định — không phải replay code' : 'Ví dụ giả định', 'kind-hypothetical'));
  return null;
}
function nodeHasGap(n) {
  return arr(n.gap_ids).length > 0 || arr(n.requirement_ids).some(function (id) {
    return IX.req[id] && IX.req[id].fulfillment !== 'reported_complete';
  });
}

// ---------------------------------------------------------------- notes / storage
var NOTES = dict(), CHECKS = dict(), KNOWN = dict(), noteEls = dict(), noteCbs = dict();
var NOTE_MAX = 20000, NOTES_MAX = 1000, FILE_MAX = 1048576;
var storeOn = false, saveTimer = null, storeMsgEl = null, storeCb = null;
function noteArea(id, labelText, opts) {
  opts = opts || {};
  KNOWN[id] = true;
  var tid = uid('note');
  var ta = el('textarea', {id: tid, rows: opts.rows || 3, maxlength: NOTE_MAX});
  ta.value = NOTES[id] || '';
  ta.addEventListener('input', function () {
    NOTES[id] = ta.value;
    (noteEls[id] || []).forEach(function (t) { if (t !== ta && t.isConnected) t.value = ta.value; });
    runCbs(id);
    scheduleSave();
  });
  (noteEls[id] = noteEls[id] || []).push(ta);
  if (opts.onInput) (noteCbs[id] = noteCbs[id] || []).push(opts.onInput);
  var wrap = el('div', {cls: 'field private-note-wrap' + (opts.cls ? ' ' + opts.cls : '')}, [el('label', {'for': tid, text: labelText}), ta]);
  return {wrap: wrap, ta: ta};
}
function runCbs(id) { (noteCbs[id] || []).forEach(function (f) { try { f(NOTES[id] || ''); } catch (e) { /* bỏ qua */ } }); }
function applyNotes(notes) {
  Object.keys(notes).forEach(function (id) {
    if (!(id in KNOWN)) return;
    NOTES[id] = notes[id];
    (noteEls[id] || []).forEach(function (t) { if (t.isConnected) t.value = notes[id]; });
    runCbs(id);
  });
}
function storageMsg(text) { if (storeMsgEl) storeMsgEl.textContent = text; }
function payload(withChecks) {
  var notes = dict();
  Object.keys(NOTES).forEach(function (k) { if (NOTES[k]) notes[k] = NOTES[k]; });
  var o = {schema: 'learning-notes-1', snapshot_id: SNAP, notes: notes};
  if (withChecks) o.checks = CHECKS;
  return o;
}
function saveNow() {
  if (!storeOn) return;
  try { window.localStorage.setItem(STORE_KEY, JSON.stringify(payload(true))); }
  catch (e) {
    storeOn = false;
    if (storeCb) storeCb.checked = false;
    storageMsg('Không lưu được trên thiết bị này (trình duyệt chặn localStorage, thường gặp khi mở file://). Ghi chú chỉ giữ trong phiên này — hãy dùng “Xuất ghi chú (.json)”.');
  }
}
function scheduleSave() {
  if (!storeOn) return;
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(function () { saveTimer = null; saveNow(); }, 400);
}
function validateNotes(o) {
  function bad(m) { return {ok: false, err: m}; }
  if (!isObj(o)) return bad('Tệp không phải một object JSON.');
  if (o.schema !== 'learning-notes-1') return bad('Sai schema (cần "learning-notes-1").');
  if (typeof o.snapshot_id !== 'string' || !o.snapshot_id || o.snapshot_id.length > 200) return bad('Thiếu snapshot_id hợp lệ.');
  if (!isObj(o.notes)) return bad('Thiếu "notes" dạng object.');
  var keys = Object.keys(o.notes);
  if (keys.length > NOTES_MAX) return bad('Quá nhiều ghi chú (tối đa ' + NOTES_MAX + ').');
  var out = dict(), unknown = 0;
  for (var i = 0; i < keys.length; i++) {
    var k = keys[i], v = o.notes[k];
    if (typeof v !== 'string') return bad('Ghi chú "' + trunc(k, 40) + '" không phải chuỗi.');
    if (v.length > NOTE_MAX || k.length > 200) return bad('Ghi chú "' + trunc(k, 40) + '" quá dài.');
    if (!(k in KNOWN)) { unknown += 1; continue; }
    out[k] = v;
  }
  var checks = dict();
  if (isObj(o.checks)) Object.keys(o.checks).forEach(function (k) { if (o.checks[k] === true && k.length < 200) checks[k] = true; });
  return {ok: true, notes: out, unknown: unknown, snapshot_id: o.snapshot_id, checks: checks};
}
function loadStored() {
  var raw = null;
  try { raw = window.localStorage.getItem(STORE_KEY); } catch (e) { raw = null; }
  if (!raw) return;
  var v;
  try { v = validateNotes(JSON.parse(raw)); } catch (e) { v = {ok: false}; }
  if (!v.ok || v.snapshot_id !== SNAP) { storageMsg('Có dữ liệu đã lưu nhưng không hợp lệ cho bài này; đã bỏ qua.'); return; }
  applyNotes(v.notes);
  Object.keys(v.checks).forEach(function (k) { CHECKS[k] = true; });
  syncChecks();
  storeOn = true;
  if (storeCb) storeCb.checked = true;
  storageMsg('Đã nạp ghi chú đã lưu trên thiết bị này.');
}
var checkEls = dict();
function syncChecks() { Object.keys(checkEls).forEach(function (k) { checkEls[k].checked = CHECKS[k] === true; }); }
function selfCheck(key, text) {
  var id = uid('chk');
  var cb = el('input', {type: 'checkbox', id: id});
  cb.checked = CHECKS[key] === true;
  cb.addEventListener('change', function () { if (cb.checked) CHECKS[key] = true; else delete CHECKS[key]; scheduleSave(); });
  checkEls[key] = cb;
  return el('label', {cls: 'inline', 'for': id}, [cb, text || 'Điểm cần tự kiểm tra']);
}

// ---------------------------------------------------------------- toolbar
function checkbox(text, onChange) {
  var id = uid('opt');
  var cb = el('input', {type: 'checkbox', id: id});
  cb.addEventListener('change', function () { onChange(cb.checked, cb); });
  return {cb: cb, label: el('label', {cls: 'inline', 'for': id}, [cb, text])};
}
var printCurrentBtn = null;
function buildToolbar() {
  var slot = document.getElementById('toolbar-slot');
  if (!slot) return;
  var bar = el('div', {cls: 'toolbar', role: 'region', 'aria-label': 'Công cụ trang'});
  printCurrentBtn = btn('In mục đang xem', {}, function () { document.body.classList.remove('print-all'); window.print(); });
  var printAll = btn('In tất cả mục', {}, function () {
    document.body.classList.add('print-all');
    window.print();
    setTimeout(function () { document.body.classList.remove('print-all'); }, 500);
  });
  window.addEventListener('afterprint', function () { document.body.classList.remove('print-all'); });
  var pa = checkbox('In kèm đáp án đã mở', function (on) { document.body.classList.toggle('print-answers', on); });
  var pn = checkbox('In kèm ghi chú', function (on) { document.body.classList.toggle('print-notes', on); });
  append(bar, el('fieldset', {}, [el('legend', {text: 'In'}), printCurrentBtn, printAll, pa.label, pn.label]));
  var mo = checkbox('Tắt hiệu ứng', function (on) { document.body.classList.toggle('no-motion', on); });
  try { if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) { mo.cb.checked = true; document.body.classList.add('no-motion'); } } catch (e) { /* bỏ qua */ }
  append(bar, el('fieldset', {}, [el('legend', {text: 'Hiển thị'}), mo.label]));
  storeMsgEl = el('p', {cls: 'store-msg', 'aria-live': 'polite', text: 'Ghi chú và tiến độ mặc định chỉ giữ trong bộ nhớ của tab này; không có gì được gửi đi.'});
  var st = checkbox('Lưu ghi chú trên thiết bị này', function (on, cb) {
    if (!on) { storeOn = false; storageMsg('Đã tắt lưu trên thiết bị. Dữ liệu đã lưu trước đó vẫn còn cho tới khi bạn bấm “Xóa dữ liệu đã lưu”.'); return; }
    storeOn = true;
    saveNow();
    if (storeOn) storageMsg('Đang lưu ghi chú trong trình duyệt của thiết bị này (khóa riêng cho snapshot này).');
    else cb.checked = false;
  });
  storeCb = st.cb;
  var exp = btn('Xuất ghi chú (.json)', {}, exportNotes);
  var fileId = uid('file');
  var file = el('input', {type: 'file', id: fileId, accept: '.json,application/json'});
  file.addEventListener('change', function () { if (file.files && file.files[0]) readNotesFile(file.files[0]); file.value = ''; });
  var del = btn('Xóa dữ liệu đã lưu', {}, function () {
    try { window.localStorage.removeItem(STORE_KEY); storageMsg('Đã xóa dữ liệu đã lưu trên thiết bị này. Ghi chú trong tab vẫn còn tới khi bạn đóng trang.'); }
    catch (e) { storageMsg('Trình duyệt không cho truy cập localStorage — không có dữ liệu nào được lưu.'); }
    storeOn = false; storeCb.checked = false;
  });
  pendingBox = el('div', {cls: 'pending-import', hidden: true, role: 'alert'});
  append(bar, el('fieldset', {}, [el('legend', {text: 'Ghi chú của bạn'}), st.label, exp,
    el('label', {cls: 'inline', 'for': fileId, text: 'Nhập ghi chú (.json):'}), file, del, storeMsgEl, pendingBox]));
  append(slot, bar);
}
var pendingBox = null;
function exportNotes() {
  try {
    var blob = new Blob([JSON.stringify(payload(false), null, 2)], {type: 'application/json'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'learning-notes-' + (SNAP.replace(/[^A-Za-z0-9]/g, '').slice(0, 12) || 'bai') + '.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
    storageMsg('Đã tạo tệp ghi chú để tải về (không gửi đi đâu).');
  } catch (e) { storageMsg('Không tạo được tệp xuất: ' + str(e && e.message)); }
}
function readNotesFile(f) {
  if (f.size > FILE_MAX) { storageMsg('Tệp quá lớn (tối đa 1 MB).'); return; }
  var rd = new FileReader();
  rd.onload = function () {
    var v;
    try { v = validateNotes(JSON.parse(str(rd.result))); } catch (e) { v = {ok: false, err: 'Tệp không phải JSON hợp lệ.'}; }
    if (!v.ok) { storageMsg('Không nhập: ' + v.err); return; }
    var info = Object.keys(v.notes).length + ' ghi chú khớp bài này' + (v.unknown ? ', bỏ qua ' + v.unknown + ' ghi chú có ID lạ' : '');
    if (v.snapshot_id !== SNAP) {
      clear(pendingBox);
      append(pendingBox, [para(null, [el('strong', {text: 'Cảnh báo: '}), 'tệp ghi chú thuộc snapshot khác (' + trunc(v.snapshot_id, 16) + ') — có thể là phiên bản bài khác. Chưa áp dụng gì. (' + info + ')']),
        btn('Vẫn áp dụng ghi chú này', {}, function () { applyNotes(v.notes); scheduleSave(); pendingBox.hidden = true; storageMsg('Đã áp dụng ghi chú từ snapshot khác theo yêu cầu của bạn (' + info + ').'); }),
        ' ', btn('Hủy', {}, function () { pendingBox.hidden = true; storageMsg('Đã hủy nhập ghi chú.'); })]);
      pendingBox.hidden = false;
      return;
    }
    applyNotes(v.notes);
    scheduleSave();
    storageMsg('Đã nhập ' + info + '.');
  };
  rd.onerror = function () { storageMsg('Không đọc được tệp.'); };
  rd.readAsText(f);
}

// ---------------------------------------------------------------- workflow graph (SVG)
var GW = 190, GH = 92, GX = 60, GY = 26, PADX = 44, PADT = 40, PADB = 20;
function layoutGraph(g) {
  var nodes = arr(g.nodes).filter(function (n) { return isObj(n) && typeof n.id === 'string'; });
  var idx = dict();
  nodes.forEach(function (n, i) { idx[n.id] = i; });
  var deps = arr(g.dependency_edges).filter(function (e) { return isObj(e) && (e.from in idx) && (e.to in idx) && e.from !== e.to; });
  var fbs = arr(g.feedback_edges).filter(function (e) { return isObj(e) && (e.from in idx) && (e.to in idx); });
  var indeg = dict(), out = dict(), layer = dict();
  nodes.forEach(function (n) { indeg[n.id] = 0; out[n.id] = []; layer[n.id] = 0; });
  deps.forEach(function (e) { indeg[e.to] += 1; out[e.from].push(e.to); });
  var queue = nodes.filter(function (n) { return indeg[n.id] === 0; }).map(function (n) { return n.id; });
  while (queue.length) {
    var u = queue.shift();
    out[u].forEach(function (v) { layer[v] = Math.max(layer[v], layer[u] + 1); indeg[v] -= 1; if (indeg[v] === 0) queue.push(v); });
  }
  var cols = [];
  nodes.forEach(function (n) { var l = layer[n.id]; (cols[l] = cols[l] || []).push(n); });
  cols = cols.filter(Boolean);
  var order = [];
  cols.forEach(function (c) { c.forEach(function (n) { order.push(n); }); });
  return {nodes: nodes, deps: deps, fbs: fbs, cols: cols, order: order};
}
function wrapText(s, max, lines) {
  var words = str(s).split(/\s+/).filter(Boolean), out = [], cur = '';
  words.forEach(function (w) {
    while (w.length > max) { if (cur) { out.push(cur); cur = ''; } out.push(w.slice(0, max)); w = w.slice(max); }
    if (!cur) cur = w; else if ((cur + ' ' + w).length <= max) cur += ' ' + w; else { out.push(cur); cur = w; }
  });
  if (cur) out.push(cur);
  if (out.length > lines) { out = out.slice(0, lines); out[lines - 1] = trunc(out[lines - 1], max - 1) + '…'; }
  return out;
}
function buildGraph(g, opts) {
  opts = opts || {};
  var L = layoutGraph(g);
  var ncols = Math.max(1, L.cols.length), nrows = 1;
  L.cols.forEach(function (c) { nrows = Math.max(nrows, c.length); });
  var baseBottom = PADT + nrows * GH + (nrows - 1) * GY;
  var width = PADX * 2 + ncols * GW + (ncols - 1) * GX;
  var height = baseBottom + PADB + (L.fbs.length ? 18 + L.fbs.length * 30 : 0);
  var pos = dict();
  L.cols.forEach(function (col, ci) { col.forEach(function (n, ri) { pos[n.id] = {x: PADX + ci * (GW + GX), y: PADT + ri * (GH + GY)}; }); });
  var tid = uid('svgt'), mA = uid('arr'), mF = uid('arrf');
  var svg = sv('svg', {viewBox: '0 0 ' + width + ' ' + height, role: 'img', 'aria-labelledby': tid, cls: 'wf-svg', focusable: 'false'});
  svg.style.maxWidth = width + 'px';
  svg.style.minWidth = Math.min(width, 620) + 'px';
  append(svg, sv('title', {id: tid}, 'Sơ đồ ' + str(g.label) + ' (' + lab(GKIND, g.graph_kind) + '). Mô tả bằng chữ ở danh sách ngay dưới sơ đồ.'));
  append(svg, sv('defs', {}, [
    sv('marker', {id: mA, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto'}, sv('path', {d: 'M0,0 L10,5 L0,10 z', cls: 'wf-arrow'})),
    sv('marker', {id: mF, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto'}, sv('path', {d: 'M0,0 L10,5 L0,10 z', cls: 'wf-arrow-fb'}))]));
  var edgesG = sv('g', {}), nodesG = sv('g', {}), labelsG = sv('g', {});
  L.deps.forEach(function (e) {
    var a = pos[e.from], b = pos[e.to];
    var x1 = a.x + GW, y1 = a.y + GH / 2, x2 = b.x, y2 = b.y + GH / 2, dx = Math.max(24, (x2 - x1) / 2);
    var inferred = e.basis === 'inferred';
    var p = sv('path', {d: 'M' + x1 + ',' + y1 + ' C' + (x1 + dx) + ',' + y1 + ' ' + (x2 - dx) + ',' + y2 + ' ' + x2 + ',' + y2,
      cls: 'wf-edge' + (inferred ? ' inferred' : ''), 'marker-end': 'url(#' + mA + ')'});
    append(p, sv('title', {}, 'Phụ thuộc: ' + str(IX.node[e.from] && IX.node[e.from].label) + ' → ' + str(IX.node[e.to] && IX.node[e.to].label) + '. ' + str(e.reason) + (inferred ? ' (suy luận)' : '')));
    append(edgesG, p);
    if (inferred) append(labelsG, sv('text', {x: (x1 + x2) / 2, y: (y1 + y2) / 2 - 7, 'text-anchor': 'middle', cls: 'wf-elabel'}, 'suy luận'));
  });
  L.fbs.forEach(function (e, k) {
    var a = pos[e.from], b = pos[e.to];
    var sx = a.x + GW, sy = a.y + GH / 2 + 18, tx = b.x, ty = b.y + GH / 2 + 18;
    var gx1 = sx + 14 + k * 6, gx2 = tx - 14 - k * 6, yD = baseBottom + 18 + k * 30;
    var p = sv('path', {d: 'M' + sx + ',' + sy + ' H' + gx1 + ' V' + yD + ' H' + gx2 + ' V' + ty + ' H' + tx,
      cls: 'wf-fb', 'marker-end': 'url(#' + mF + ')'});
    append(p, sv('title', {}, 'Vòng phản hồi: khi ' + str(e.condition) + '; dừng khi ' + str(e.stop_condition)));
    append(edgesG, p);
    append(labelsG, sv('text', {x: Math.min(gx1, gx2) + 6, y: yD - 6, cls: 'wf-fblabel'},
      '↺ quay lại khi: ' + trunc(e.condition, 52) + (e.basis === 'inferred' ? ' (suy luận)' : '')));
  });
  var nodeEls = dict();
  L.nodes.forEach(function (n) {
    var p = pos[n.id], gap = nodeHasGap(n);
    var grp = sv('g', {cls: 'wf-node kind-' + cssKey(n.kind) + (gap ? ' has-gap' : ''), transform: 'translate(' + p.x + ',' + p.y + ')'});
    append(grp, sv('title', {}, str(n.label) + ' — ' + lab(NKIND, n.kind) + (gap ? ' — còn thiếu' : '')));
    append(grp, sv('rect', {width: GW, height: GH, rx: 8}));
    append(grp, sv('text', {x: 10, y: 17, cls: 'wf-badge'}, lab(NKIND, n.kind).toUpperCase()));
    wrapText(n.label, 21, gap ? 2 : 3).forEach(function (line, i) { append(grp, sv('text', {x: 10, y: 37 + i * 17, cls: 'wf-label'}, line)); });
    if (gap) append(grp, sv('text', {x: 10, y: GH - 9, cls: 'wf-gap'}, '⚠ còn thiếu'));
    append(nodesG, grp);
    nodeEls[n.id] = grp;
  });
  append(svg, edgesG); append(svg, nodesG); append(svg, labelsG);
  var token = null;
  if (opts.token) {
    var tl = trunc(opts.token, 26), tw = Math.min(180, 24 + tl.length * 6.6);
    token = sv('g', {cls: 'token-g', 'aria-hidden': 'true'}, [sv('rect', {x: -tw / 2, y: -11, width: tw, height: 22, rx: 11}),
      sv('text', {x: 0, y: 4, 'text-anchor': 'middle'}, '● ' + tl)]);
    token.style.transform = 'translate(-200px,-200px)';
    append(svg, token);
  }
  var wrap = el('div', {cls: 'svg-wrap', tabindex: '0', role: 'group', 'aria-label': 'Sơ đồ ' + str(g.label) + ' (cuộn ngang nếu rộng)'}, svg);
  return {wrap: wrap, layout: L, highlight: function (id) {
    Object.keys(nodeEls).forEach(function (k) { nodeEls[k].classList.toggle('is-current', k === id); });
    if (token && pos[id]) token.style.transform = 'translate(' + (pos[id].x + GW / 2) + 'px,' + (pos[id].y - 16) + 'px)';
  }};
}
function graphTextList(g, L) {
  var ol = el('ol', {cls: 'wf-text'});
  L.order.forEach(function (n) {
    var li = el('li', {}, [para(null, [el('strong', {text: str(n.label)}), ' ', nodeKindChip(n.kind), nodeHasGap(n) ? gapChip() : null])]);
    L.deps.filter(function (e) { return e.to === n.id; }).forEach(function (e) {
      append(li, el('div', {cls: 'edge'}, [para(null, ['Sau «' + str(IX.node[e.from].label) + '»: ' + str(e.reason) + ' ', e.basis === 'inferred' ? inferChip() : null]),
        refsBlock(e.source_ref_ids, {lead: 'Nguồn quan hệ:', noneText: e.basis === 'inferred' ? 'Quan hệ suy luận, không có trích dẫn trực tiếp' : null})]));
    });
    append(li, refsBlock(n.source_ref_ids, {lead: 'Nguồn bước:'}));
    append(ol, li);
  });
  var out = [el('h4', {text: 'Mô tả bằng chữ (tương đương sơ đồ)'}), ol];
  if (L.fbs.length) {
    out.push(el('h4', {text: 'Vòng phản hồi'}));
    out.push(el('ul', {}, L.fbs.map(function (e) {
      return el('li', {}, [para(null, ['Từ «' + str(IX.node[e.from].label) + '» quay lại «' + str(IX.node[e.to].label) + '» khi: ' + str(e.condition) + '. Dừng khi: ' + str(e.stop_condition) + '. ',
        e.basis === 'inferred' ? inferChip() : null]), refsBlock(e.source_ref_ids)]);
    })));
  }
  return out;
}

// ---------------------------------------------------------------- sections
function bOverview(body, sec) {
  var reqs = arr(M.requirements).filter(isObj);
  var goals = reqs.filter(function (q) { return q.category === 'learning_goal'; });
  var reported = arr(M.claims).filter(function (c) { return isObj(c) && c.kind === 'reported'; });
  if (!reqs.length) append(body, sectionEmpty(sec));
  append(body, para('muted', 'Bài: ' + str(obj(M.repo_snapshot).display_label)));
  var se = el('div', {cls: 'card selfexplain'});
  append(se, el('h3', {text: 'Tự diễn đạt trước'}));
  append(se, noteArea('#overview', 'Tự diễn đạt mục tiêu trước khi mở gợi ý', {rows: 3}).wrap);
  var gid = uid('goals');
  var goalsBox = el('div', {id: gid, hidden: true});
  append(goalsBox, el('h3', {text: 'Mục tiêu học theo đề'}));
  if (goals.length) goals.forEach(function (q) { append(goalsBox, reqView(q)); });
  else append(goalsBox, missing('Chưa có mục tiêu học có nguồn.', 'Bổ sung câu mục tiêu trong đề/README cấp gốc rồi sinh lại.'));
  var reveal = btn('Mở gợi ý: mục tiêu theo đề', {'aria-expanded': 'false', 'aria-controls': gid, cls: 'primary'}, function () {
    var open = reveal.getAttribute('aria-expanded') === 'true';
    reveal.setAttribute('aria-expanded', open ? 'false' : 'true');
    goalsBox.hidden = open;
    reveal.textContent = open ? 'Mở gợi ý: mục tiêu theo đề' : 'Ẩn mục tiêu theo đề';
  });
  append(se, el('div', {cls: 'controls'}, reveal));
  append(se, goalsBox);
  append(body, se);
  var ctxs = arr(M.contexts).filter(isObj);
  append(body, el('h3', {text: 'Ngữ cảnh trong bài'}));
  if (ctxs.length) append(body, el('ul', {cls: 'plain'}, ctxs.map(function (c) { return el('li', {cls: 'item'}, [para(null, ctxText(c)), refsBlock(c.source_ref_ids)]); })));
  else append(body, para('muted', 'Chưa có ngữ cảnh (sản phẩm, phần, môi trường) được ghi.'));
  ['deliverable', 'constraint', 'assessment'].forEach(function (cat) {
    var qs = reqs.filter(function (q) { return q.category === cat; });
    append(body, el('h3', {text: CAT[cat]}));
    if (qs.length) qs.forEach(function (q) { append(body, reqView(q)); });
    else append(body, para('muted', 'Không có mục nào thuộc loại này trong nguồn.'));
  });
  if (reported.length) {
    append(body, el('h3', {text: 'Bài làm được tài liệu ghi nhận'}));
    append(body, para('muted', 'Đây là điều bài làm tự ghi trong Markdown, chưa được xác minh bằng chạy code.'));
    reported.forEach(function (c) { append(body, claimView(c)); });
  } else {
    append(body, el('h3', {text: 'Yêu cầu — chưa có nội dung bài làm'}));
    append(body, missing('Markdown cấp gốc chưa có đoạn bài làm tự báo cáo.', 'Thêm báo cáo bài làm (ví dụ REPORT.md) ở thư mục gốc rồi sinh lại.'));
  }
}
function bWorkflow(body, sec) {
  if (!GRAPHS.length) { append(body, sectionEmpty(sec)); return; }
  append(body, para('legend', 'Mỗi sơ đồ độc lập, không nối với nhau. Nét liền: phụ thuộc có nguồn · nét chấm: quan hệ suy luận · nét gạch cam: vòng phản hồi · “⚠ còn thiếu”: bước có khoảng trống hoặc yêu cầu chưa được tự báo cáo là xong.'));
  GRAPHS.forEach(function (g) {
    var box = el('div', {cls: 'card graph'});
    append(box, el('h3', {}, [str(g.label) + ' ', chip(lab(GKIND, g.graph_kind), 'cat')]));
    append(box, contextLine(g.context_ids));
    if (!arr(g.nodes).length) { append(box, missing('Sơ đồ chưa có bước nào.', 'Bổ sung mô tả bước trong Markdown rồi sinh lại.')); append(body, box); return; }
    var G = buildGraph(g);
    append(box, G.wrap);
    append(box, graphTextList(g, G.layout));
    append(body, box);
  });
}
function bWalkthrough(body, sec) {
  var nodeCount = 0;
  GRAPHS.forEach(function (g) { nodeCount += arr(g.nodes).length; });
  var traces = INTER.filter(function (i) { return i.type === 'trace_flow'; });
  if (!nodeCount && !traces.length) { append(body, sectionEmpty(sec)); return; }
  GRAPHS.forEach(function (g) {
    var L = layoutGraph(g);
    if (!L.order.length) return;
    append(body, el('h3', {}, [str(g.label) + ' ', chip(lab(GKIND, g.graph_kind), 'cat')]));
    L.order.forEach(function (n) {
      var c = el('article', {cls: 'card node'});
      append(c, el('h4', {}, [str(n.label) + ' ', nodeKindChip(n.kind), nodeHasGap(n) ? gapChip() : null]));
      if (n.purpose) append(c, labelled('Mục đích', str(n.purpose)));
      append(c, labelled('Đầu vào', arr(n.inputs).length ? arr(n.inputs).map(str).join('; ') : '(tài liệu không ghi)'));
      append(c, labelled('Đầu ra', arr(n.outputs).length ? arr(n.outputs).map(str).join('; ') : '(tài liệu không ghi)'));
      arr(n.requirement_ids).forEach(function (q) { if (IX.req[q]) append(c, reqView(IX.req[q], {showCat: true, noEvidence: true})); });
      arr(n.claim_ids).forEach(function (x) { if (IX.claim[x]) append(c, claimView(IX.claim[x], true)); });
      append(c, gapList(n.gap_ids));
      append(c, refsBlock(n.source_ref_ids));
      append(body, c);
    });
  });
  append(body, el('h3', {text: 'Theo dấu từng bước'}));
  if (!traces.length) append(body, para('muted', 'Chưa có bài theo dấu luồng cho bài này.'));
  traces.forEach(function (it) { append(body, buildTrace(it)); });
}
function interHead(box, it, traceStyle) {
  append(box, el('h4', {text: str(it.title)}));
  append(box, basisLine(it, traceStyle));
  if (it.prompt) append(box, para(null, str(it.prompt)));
  append(box, goalsLine(it.learning_goal_ids));
  append(box, refsBlock(it.source_ref_ids));
  append(box, gapList(it.gap_ids));
}
function buildTrace(it) {
  var p = obj(it.payload), g = IX.graph[p.graph_id], steps = arr(p.steps).filter(isObj);
  var box = el('article', {cls: 'card interaction trace'});
  interHead(box, it, true);
  if (!g || !steps.length) { append(box, missing('Không có sơ đồ hoặc bước để theo dấu.', 'Cần trace_flow trỏ tới một sơ đồ có bước.')); return box; }
  var G = buildGraph(g, {token: str(p.token_label) || 'token'});
  append(box, G.wrap);
  var counter = el('p', {cls: 'step-counter'});
  var nodeLine = para(null, '');
  var before = el('span', {cls: 'state before'}), after = el('span', {cls: 'state after'});
  var expl = para(null, '');
  var live = el('div', {cls: 'sr-only', 'aria-live': 'polite'});
  var i = 0;
  var prev = btn('← Bước trước', {}, function () { if (i > 0) { i -= 1; show(true); } });
  var next = btn('Bước sau →', {cls: 'primary'}, function () { if (i < steps.length - 1) { i += 1; show(true); } });
  function show(announce) {
    var s = steps[i], n = IX.node[s.node_id];
    var nl = n ? str(n.label) : '(bước không có trong sơ đồ: ' + str(s.node_id) + ')';
    counter.textContent = 'Bước ' + (i + 1) + '/' + steps.length;
    clear(nodeLine); append(nodeLine, [chip('● ' + str(p.token_label), 'token-chip'), ' đang ở: ', el('strong', {text: nl})]);
    before.textContent = 'Trước: ' + str(s.before);
    after.textContent = 'Sau: ' + str(s.after);
    expl.textContent = str(s.explanation);
    prev.disabled = i === 0;
    next.disabled = i === steps.length - 1;
    G.highlight(s.node_id);
    if (announce) live.textContent = counter.textContent + ': ' + nl + '. Trước: ' + str(s.before) + '. Sau: ' + str(s.after) + '. ' + str(s.explanation);
  }
  append(box, el('div', {cls: 'step-panel'}, [counter, nodeLine, el('div', {cls: 'state-change'}, [before, ' → ', after]), expl, live]));
  append(box, el('div', {cls: 'controls'}, [prev, next]));
  if (it.feedback) append(box, labelled('Ghi nhớ', str(it.feedback)));
  append(box, el('h5', {cls: 'sr-only', text: 'Danh sách các bước'}));
  append(box, el('details', {}, [el('summary', {text: 'Xem toàn bộ các bước bằng chữ'}), el('ol', {}, steps.map(function (s) {
    var n = IX.node[s.node_id];
    return el('li', {text: (n ? str(n.label) : str(s.node_id)) + ': ' + str(s.before) + ' → ' + str(s.after) + '. ' + str(s.explanation)});
  }))]));
  show(false);
  return box;
}
function bDecisions(body, sec) {
  var decs = arr(M.decisions).filter(isObj);
  var chs = INTER.filter(function (i) { return i.type === 'choose_explain'; });
  var other = INTER.filter(function (i) { return ['trace_flow', 'choose_explain', 'teach_back'].indexOf(i.type) < 0; });
  if (!decs.length && !chs.length && !other.length) { append(body, sectionEmpty(sec)); return; }
  append(body, el('h3', {text: 'Quyết định trong bài'}));
  if (!decs.length) append(body, para('muted', 'Tài liệu chưa nêu quyết định nào.'));
  decs.forEach(function (d) {
    var c = el('article', {cls: 'card decision'});
    append(c, el('h4', {text: str(d.question)}));
    arr(d.requirement_ids).forEach(function (q) { if (IX.req[q]) append(c, labelled('Yêu cầu liên quan', str(IX.req[q].text))); });
    append(c, refsBlock(d.source_ref_ids));
    var opts = arr(d.options).filter(isObj);
    append(c, el('p', {cls: 'muted', text: 'Các phương án (không phải đáp án dùng để chấm):'}));
    append(c, el('ul', {cls: 'plain'}, opts.map(function (o) {
      return el('li', {cls: 'item'}, [para(null, [el('strong', {text: str(o.label)}), ' — ' + str(o.rationale)]), refsBlock(o.source_ref_ids)]);
    })));
    var rec = d.recorded_choice_id !== null && d.recorded_choice_id !== undefined ? opts.filter(function (o) { return o.id === d.recorded_choice_id; })[0] : null;
    if (rec) append(c, el('div', {cls: 'item'}, [para(null, [chip('Bài làm tự báo cáo', 'kind-reported'), 'Bài làm ghi nhận lựa chọn: ', el('strong', {text: str(rec.label)})]), refsBlock(d.recorded_choice_ref_ids)]));
    else append(c, para('muted', 'Bài làm chưa ghi nhận lựa chọn.'));
    append(c, gapList(d.gap_ids));
    append(body, c);
  });
  append(body, el('h3', {text: 'Chọn và giải thích'}));
  if (!chs.length) append(body, para('muted', 'Chưa có câu chọn-và-giải-thích có căn cứ cho bài này.'));
  chs.forEach(function (it) { append(body, buildChoose(it)); });
  if (other.length) {
    append(body, el('h3', {text: 'Tương tác khác'}));
    other.forEach(function (it) { append(body, buildUnsupported(it)); });
  }
}
function buildChoose(it) {
  var p = obj(it.payload), opts = arr(p.options).filter(isObj), accepted = arr(p.accepted_option_ids);
  var box = el('article', {cls: 'card interaction choose'});
  interHead(box, it, false);
  var name = uid('radio'), selected = null, radios = [];
  var fs = el('fieldset', {cls: 'choices'}, el('legend', {text: str(it.prompt) || 'Chọn một phương án'}));
  opts.forEach(function (o) {
    var id = uid('opt');
    var r = el('input', {type: 'radio', name: name, id: id, value: str(o.id)});
    r.addEventListener('change', function () { if (r.checked) { selected = o; update(); } });
    radios.push(r);
    append(fs, el('label', {'for': id}, [r, ' ' + str(o.label)]));
  });
  append(box, fs);
  var why = noteArea(it.id, (str(p.explanation_prompt) || 'Lý do') + ' — lý do (bắt buộc trước khi xem phản hồi)', {rows: 3, onInput: function () { update(); }});
  append(box, why.wrap);
  var hintId = uid('hint');
  var hint = el('p', {cls: 'muted', id: hintId, text: 'Chọn một phương án và viết lý do để mở phản hồi. Lý do của bạn không được chấm.'});
  var show = btn('Xem phản hồi', {cls: 'primary', disabled: true, 'aria-describedby': hintId}, reveal);
  var retry = btn('Thử lại', {hidden: true}, function () {
    radios.forEach(function (r) { r.checked = false; r.disabled = false; });
    selected = null; fbBox.hidden = true; clear(fbBox); retry.hidden = true; show.hidden = false; update();
    if (radios[0]) radios[0].focus();
  });
  append(box, el('div', {cls: 'controls'}, [show, retry]));
  append(box, hint);
  var live = el('div', {'aria-live': 'polite'});
  var fbBox = el('div', {cls: 'answer', hidden: true});
  append(live, fbBox);
  append(box, live);
  function update() { show.disabled = !(selected && (NOTES[it.id] || '').trim()); }
  function reveal() {
    if (!selected || !(NOTES[it.id] || '').trim()) return;
    clear(fbBox);
    var ok = accepted.indexOf(selected.id) >= 0;
    append(fbBox, [para(null, [el('strong', {text: 'Bạn chọn: ' + str(selected.label) + ' '}),
      ok ? chip('Thuộc phương án được nguồn chấp nhận', 'chip-accept') : chip('Không thuộc phương án được nguồn chấp nhận', 'ful-reported_not_done'),
      refsSim(selected.source_ref_ids) ? simChip() : null]),
      para(null, str(selected.feedback)), refsBlock(selected.source_ref_ids),
      el('p', {cls: 'muted', text: 'Các phương án được nguồn chấp nhận:'}),
      el('ul', {}, opts.map(function (o) {
        return el('li', {}, [str(o.label) + ' ', accepted.indexOf(o.id) >= 0 ? chip('✓ được nguồn chấp nhận', 'chip-accept') : null]);
      })),
      it.feedback ? labelled('Gợi ý chung', str(it.feedback)) : null,
      refsSim(it.source_ref_ids) ? para(null, simChip()) : null]);
    fbBox.hidden = false;
    radios.forEach(function (r) { r.disabled = true; });
    show.hidden = true; retry.hidden = false;
    retry.focus();
  }
  return box;
}
function buildUnsupported(it) {
  var box = el('article', {cls: 'card interaction unsupported'});
  interHead(box, it, false);
  append(box, para(null, [chip('Tương tác này chưa hỗ trợ trong bản MVP', 'evs-referenced_unread'), 'Loại: ', el('code', {text: str(it.type)})]));
  var p = obj(it.payload);
  if (it.type === 'order_dependencies') {
    var g = IX.graph[p.graph_id];
    append(box, labelled('Sơ đồ', g ? str(g.label) : str(p.graph_id)));
    append(box, labelled('Các bước', arr(p.node_ids).map(function (x) { return IX.node[x] ? str(IX.node[x].label) : str(x); }).join('; ') || '(không có)'));
    var edges = g ? arr(g.dependency_edges).filter(function (e) { return arr(p.edge_ids).indexOf(e.id) >= 0; }) : [];
    append(box, labelled('Phụ thuộc cần giữ', edges.map(function (e) { return str(IX.node[e.from] && IX.node[e.from].label) + ' → ' + str(IX.node[e.to] && IX.node[e.to].label); }).join('; ') || '(không có)'));
    append(box, para('muted', 'Bạn có thể tự sắp xếp các bước trên giấy: mọi thứ tự giữ đúng các phụ thuộc trên đều hợp lệ.'));
  } else {
    append(box, el('ul', {}, Object.keys(p).map(function (k) {
      var v; try { v = JSON.stringify(p[k]); } catch (e) { v = '?'; }
      return el('li', {}, [el('code', {text: k}), ': ' + trunc(v, 400)]);
    })));
  }
  if (it.feedback) append(box, labelled('Gợi ý', str(it.feedback)));
  return box;
}
function bEvidence(body, sec) {
  var reqs = arr(M.requirements).filter(isObj), claims = arr(M.claims).filter(isObj), evs = arr(M.evidence).filter(isObj);
  var meas = arr(M.measurements).filter(isObj), gaps = arr(M.gaps).filter(isObj), confs = arr(M.conflicts).filter(isObj);
  if (!reqs.length && !claims.length && !evs.length && !meas.length) append(body, sectionEmpty(sec));
  append(body, para('muted', 'Mọi trạng thái ở đây là điều tài liệu ghi lại. Trang này không chạy code và không chứng nhận kết quả.'));
  // requirement table
  append(body, el('h3', {text: 'Yêu cầu ↔ bằng chứng ↔ nhận định ↔ khoảng trống'}));
  if (reqs.length) {
    var tb = el('tbody');
    reqs.forEach(function (q) {
      var rc = claims.filter(function (c) { return arr(c.requirement_ids).indexOf(q.id) >= 0; });
      var qe = arr(q.evidence_ids).filter(function (x) { return IX.ev[x]; });
      append(tb, el('tr', {}, [
        el('td', {}, [para(null, [chip(lab(CAT, q.category), 'cat'), str(q.text)]), refsBlock(q.source_ref_ids)]),
        el('td', {}, fulChip(q.fulfillment)),
        el('td', {}, qe.length ? qe.map(function (x) { return evView(IX.ev[x], true); }) : el('span', {cls: 'muted', text: 'Chưa có'})),
        el('td', {}, rc.length ? rc.map(function (c) { return claimView(c, true); }) : el('span', {cls: 'muted', text: 'Chưa có'})),
        el('td', {}, [gapList(q.gap_ids), arr(q.conflict_ids).filter(function (x) { return IX.conf[x]; }).map(function (x) { return para('gap', [chip('Mâu thuẫn', 'ful-conflicting'), str(IX.conf[x].topic)]); }),
          (!arr(q.gap_ids).length && !arr(q.conflict_ids).length) ? el('span', {cls: 'muted', text: 'Không ghi'}) : null]),
        el('td', {}, selfCheck('req:' + q.id))]));
    });
    append(body, el('div', {cls: 'tbl-wrap'}, el('table', {}, [el('caption', {text: 'Mỗi dòng là một yêu cầu'}),
      el('thead', {}, el('tr', {}, ['Yêu cầu', 'Trạng thái tự báo cáo', 'Bằng chứng', 'Nhận định liên quan', 'Khoảng trống / mâu thuẫn', 'Tự kiểm tra'].map(function (h) { return el('th', {scope: 'col', text: h}); }))), tb])));
  } else append(body, para('muted', 'Chưa có yêu cầu nào.'));
  // claims by kind
  append(body, el('h3', {text: 'Nhận định theo loại'}));
  if (!claims.length) append(body, para('muted', 'Chưa có nhận định nào.'));
  ['required', 'reported', 'document_observation', 'inference', 'hypothetical'].forEach(function (k) {
    var cs = claims.filter(function (c) { return c.kind === k; });
    if (!cs.length) return;
    append(body, el('h4', {}, [kindChip(k), ' ' + cs.length + ' nhận định']));
    cs.forEach(function (c) { append(body, claimView(c)); });
  });
  // evidence by status
  append(body, el('h3', {text: 'Bằng chứng theo trạng thái'}));
  if (!evs.length) append(body, para('muted', 'Chưa có bằng chứng nào.'));
  ['reported_in_markdown', 'embedded_record_unverified', 'referenced_unread', 'missing', 'conflicting'].forEach(function (s) {
    var es = evs.filter(function (e) { return e.status === s; });
    if (!es.length) return;
    append(body, el('h4', {}, [evChip(s), ' ' + es.length + ' mục']));
    es.forEach(function (e) { append(body, evView(e)); });
  });
  // measurements
  append(body, el('h3', {text: 'Số đo được ghi'}));
  if (meas.length) {
    var mt = el('tbody');
    meas.forEach(function (m) {
      var c = IX.claim[m.claim_id];
      append(mt, el('tr', {}, [
        el('td', {}, [c ? para(null, [kindChip(c.kind), str(c.text)]) : el('span', {text: str(m.claim_id)}), measSim(m) ? simChip() : null]),
        el('td', {}, el('code', {text: str(m.value)})),
        el('td', {text: m.operator === null || m.operator === undefined ? '(không ghi)' : str(m.operator)}),
        el('td', {text: m.unit === null || m.unit === undefined ? '(không ghi đơn vị)' : str(m.unit)}),
        el('td', {text: m.method === null || m.method === undefined ? '(không ghi phương pháp)' : str(m.method)}),
        el('td', {text: IX.ctx[m.context_id] ? ctxText(IX.ctx[m.context_id]) : str(m.context_id)}),
        el('td', {}, [arr(m.evidence_ids).filter(function (x) { return IX.ev[x]; }).map(function (x) { return para(null, [evChip(IX.ev[x].status), evSim(IX.ev[x]) ? simChip() : null]); }),
          arr(m.conflict_ids).filter(function (x) { return IX.conf[x]; }).map(function (x) { return para('gap', [chip('Mâu thuẫn', 'ful-conflicting'), str(IX.conf[x].topic)]); })]),
        el('td', {}, refsBlock(m.source_ref_ids))]));
    });
    append(body, el('div', {cls: 'tbl-wrap'}, el('table', {}, [el('caption', {text: 'Giữ nguyên giá trị, đơn vị, toán tử như nguồn; không vẽ biểu đồ, không tự quy đổi'}),
      el('thead', {}, el('tr', {}, ['Nhận định', 'Giá trị', 'Toán tử', 'Đơn vị', 'Phương pháp', 'Ngữ cảnh', 'Trạng thái bằng chứng', 'Nguồn'].map(function (h) { return el('th', {scope: 'col', text: h}); }))), mt])));
  } else append(body, para('muted', 'Chưa có số đo nào được ghi.'));
  // conflicts
  append(body, el('h3', {text: 'Mâu thuẫn giữa các nguồn'}));
  if (!confs.length) append(body, para('muted', 'Không ghi nhận mâu thuẫn.'));
  confs.forEach(function (c) {
    var box = el('article', {cls: 'card conflict'});
    append(box, el('h4', {text: str(c.topic)}));
    append(box, para(null, [chip(lab(CSTATE, c.state), c.state === 'unresolved' ? 'ful-conflicting' : 'cat')]));
    function side(title, ids) {
      return el('div', {}, [el('p', {cls: 'muted', text: title}), arr(ids).filter(function (r) { return IX.ref[r]; }).map(function (r) {
        return el('blockquote', {cls: 'ref-quote', text: '«' + str(IX.ref[r].quote) + '» — ' + refName(IX.ref[r])});
      }), refsBlock(ids)]);
    }
    append(box, el('div', {cls: 'cols'}, [side('Một phía', c.left_ref_ids), side('Phía còn lại', c.right_ref_ids)]));
    append(box, labelled('Ảnh hưởng', str(c.impact)));
    if (arr(c.resolution_ref_ids).length) append(box, refsBlock(c.resolution_ref_ids, {lead: 'Nguồn giải quyết:'}));
    if (c.human_resolution_note) append(box, labelled('Ghi chú của người', str(c.human_resolution_note)));
    append(box, selfCheck('conf:' + c.id));
    append(body, box);
  });
  // gaps
  append(body, el('h3', {text: 'Khoảng trống cần bổ sung'}));
  if (!gaps.length) append(body, para('muted', 'Không ghi khoảng trống.'));
  gaps.forEach(function (g) {
    append(body, el('div', {cls: 'item gap'}, [para(null, [gapChip(), str(g.reason)]), labelled('Cần bổ sung', str(g.requested_evidence)),
      arr(g.scope_ids).length ? labelled('Liên quan', arr(g.scope_ids).map(describeId).join(' | ')) : null, selfCheck('gap:' + g.id)]));
  });
  // unread external refs
  append(body, el('h3', {text: 'Tệp được nhắc tới nhưng chưa đọc'}));
  var unread = evs.filter(function (e) { return e.status === 'referenced_unread' || e.external_ref; });
  if (unread.length) append(body, el('ul', {}, unread.map(function (e) { return el('li', {}, [el('code', {text: str(e.external_ref) || '(không ghi tên)'}), ' — ' + str(e.description)]); })));
  else append(body, para('muted', 'Không có.'));
  // manifest
  append(body, el('h3', {text: 'Các file nguồn đã đọc'}));
  var cov = obj(obj(M.validation).coverage_summary);
  append(body, para(null, 'Đã xử lý ' + str(cov.files_processed) + '/' + str(cov.files_total) + ' file · ' + str(cov.lines_processed) + '/' + str(cov.lines_total) + ' dòng · ' + str(cov.redacted_lines) + ' dòng đã che.'));
  var man = arr(M.source_manifest).filter(isObj);
  function rng(rs) { return arr(rs).map(function (r) { r = obj(r); return r.start_line === r.end_line ? str(r.start_line) : str(r.start_line) + '–' + str(r.end_line); }).join(', ') || '—'; }
  if (man.length) append(body, el('div', {cls: 'tbl-wrap'}, el('table', {}, [
    el('thead', {}, el('tr', {}, ['Tệp', 'Số dòng', 'Trạng thái đọc', 'Dòng đã xử lý', 'Dòng đã che', 'SHA256 (rút gọn)'].map(function (h) { return el('th', {scope: 'col', text: h}); }))),
    el('tbody', {}, man.map(function (m) {
      return el('tr', {}, [el('td', {text: str(m.name)}), el('td', {text: m.line_count === null || m.line_count === undefined ? '—' : str(m.line_count)}),
        el('td', {text: lab(RSTATUS, m.read_status)}), el('td', {text: rng(m.processed_ranges)}), el('td', {text: rng(m.redacted_ranges)}),
        el('td', {}, el('code', {text: str(m.sha256).slice(0, 12) || '—'}))]);
    }))])));
  else append(body, para('muted', 'Không có file trong manifest.'));
  // validation issues
  append(body, el('h3', {text: 'Vấn đề do bước kiểm tra ghi lại'}));
  var issues = arr(obj(M.validation).issues).filter(isObj);
  if (issues.length) append(body, el('ul', {}, issues.map(function (i) {
    return el('li', {}, [chip(lab(SEV, i.severity), 'sev-' + cssKey(i.severity)), el('code', {text: str(i.code)}), ' ' + str(i.message),
      arr(i.scope_ids).length ? el('span', {cls: 'muted', text: ' (phạm vi: ' + arr(i.scope_ids).map(str).join(', ') + ')'}) : null]);
  })));
  else append(body, para('muted', 'Không có vấn đề nào được ghi.'));
}
function buildTeach(spec) {
  var box = el('article', {cls: 'card interaction teach'});
  append(box, el('h4', {text: spec.title}));
  if (spec.basis === 'hypothetical') append(box, para(null, chip('Ví dụ giả định', 'kind-hypothetical')));
  if (spec.prompt) append(box, para(null, spec.prompt));
  if (spec.question && spec.question !== spec.prompt) append(box, para(null, el('strong', {text: spec.question})));
  append(box, goalsLine(spec.goals));
  append(box, refsBlock(spec.refs));
  append(box, gapList(spec.gaps));
  var done, hintBtn;
  var ans = noteArea(spec.id, 'Câu trả lời của bạn (không được chấm; chỉ giữ trong trình duyệt)', {rows: 5, onInput: function (v) { if (done) done.disabled = !v.trim(); }});
  append(box, ans.wrap);
  var hints = arr(spec.hints).map(str).filter(Boolean), hi = 0;
  var hintList = el('ol', {cls: 'answer hint', hidden: true});
  var live = el('div', {'aria-live': 'polite'});
  var status = el('p', {cls: 'tried', hidden: true, text: 'Đã ghi nhận: bạn đã thử trả lời (trang không chấm điểm câu tự luận).'});
  var cl = el('div', {cls: 'answer checklist', hidden: true});
  append(cl, el('p', {}, el('strong', {text: 'Checklist tự đối chiếu — tự tick những ý bạn đã nêu'})));
  var ul = el('ul', {cls: 'plain'});
  arr(spec.checklist).filter(isObj).forEach(function (c) {
    var id = uid('cl');
    var cb = el('input', {type: 'checkbox', id: id});
    append(ul, el('li', {}, [el('label', {cls: 'inline', 'for': id}, [cb, str(c.point)]), refsSim(c.source_ref_ids) ? simChip() : null, refsBlock(c.source_ref_ids, {noneText: false})]));
  });
  if (!ul.firstChild) append(ul, el('li', {cls: 'muted', text: 'Không có checklist cho câu này.'}));
  append(cl, ul);
  if (spec.feedback) append(cl, labelled('Gợi ý chung', spec.feedback));
  function openChecklist() {
    cl.hidden = false;
    if (hintBtn) { hintBtn.disabled = true; hintBtn.textContent = 'Đã mở checklist'; }
  }
  done = btn('Tôi đã trả lời xong', {cls: 'primary', disabled: !(NOTES[spec.id] || '').trim()}, function () {
    if (!(NOTES[spec.id] || '').trim()) return;
    status.hidden = false; openChecklist();
  });
  function hintLabel() { return hi < hints.length ? (hi === 0 ? 'Cần gợi ý' : 'Gợi ý tiếp (' + (hi + 1) + '/' + hints.length + ')') : 'Mở checklist'; }
  hintBtn = btn(hints.length ? 'Cần gợi ý' : 'Cần gợi ý (mở checklist)', {}, function () {
    if (hi < hints.length) {
      append(hintList, el('li', {text: 'Gợi ý ' + (hi + 1) + '/' + hints.length + ': ' + hints[hi]}));
      hintList.hidden = false; hi += 1;
      hintBtn.textContent = hintLabel();
    } else openChecklist();
  });
  append(box, el('div', {cls: 'controls'}, [done, hintBtn]));
  append(live, status); append(live, hintList); append(live, cl);
  append(box, live);
  return box;
}
function bTeachback(body, sec) {
  var tbs = INTER.filter(function (i) { return i.type === 'teach_back'; });
  if (!tbs.length && !QUESTIONS.length) { append(body, sectionEmpty(sec)); return; }
  append(body, para('muted', 'Tự trả lời trước. Checklist chỉ mở sau khi bạn bấm “Tôi đã trả lời xong” hoặc “Cần gợi ý”. Trang không chấm điểm, chỉ ghi nhận bạn đã thử.'));
  if (tbs.length) append(body, el('h3', {text: 'Tự giảng lại'}));
  tbs.forEach(function (it) {
    var p = obj(it.payload);
    append(body, buildTeach({id: it.id, title: str(it.title), prompt: str(it.prompt), question: str(p.question), goals: it.learning_goal_ids,
      refs: it.source_ref_ids, gaps: it.gap_ids, basis: it.basis, checklist: p.checklist, hints: p.hint_levels, feedback: str(it.feedback)}));
  });
  if (QUESTIONS.length) append(body, el('h3', {text: 'Câu hỏi ôn tập khi thuyết trình'}));
  QUESTIONS.forEach(function (q) {
    append(body, buildTeach({id: q.id, title: 'Câu hỏi ôn tập', prompt: '', question: str(q.prompt), goals: q.learning_goal_ids,
      refs: q.source_ref_ids, gaps: [], basis: 'source_backed', checklist: q.checklist, hints: [], feedback: ''}));
  });
}
function buildCard(card, i, total, slide, notesOn) {
  var linkedSim = arr(card.claim_ids).some(function (x) { return claimSim(IX.claim[x]); }) || arr(card.evidence_ids).some(function (x) { return evSim(IX.ev[x]); }) || refsSim(card.source_ref_ids);
  var box = el('article', {cls: 'card pres-card'});
  var h = el(slide ? 'h2' : 'h3', {tabindex: slide ? '-1' : null}, ['Thẻ ' + (i + 1) + '/' + total + ': ' + str(card.title) + ' ', linkedSim ? simChip() : null]);
  append(box, h);
  var cl = arr(card.claim_ids).filter(function (x) { return IX.claim[x]; });
  if (cl.length) { append(box, el('h4', {text: 'Nhận định'})); cl.forEach(function (x) { append(box, claimView(IX.claim[x], true)); }); }
  var nd = arr(card.node_ids).filter(function (x) { return IX.node[x]; });
  if (nd.length) {
    append(box, el('h4', {text: 'Bước trong workflow'}));
    append(box, el('ul', {cls: 'plain'}, nd.map(function (x) { var n = IX.node[x]; return el('li', {cls: 'item'}, [str(n.label) + ' ', nodeKindChip(n.kind), nodeHasGap(n) ? gapChip() : null, el('span', {cls: 'muted', text: ' (' + str(IX.nodeGraph[x] && IX.nodeGraph[x].label) + ')'})]); })));
  }
  var dc = arr(card.decision_ids).filter(function (x) { return IX.dec[x]; });
  if (dc.length) {
    append(box, el('h4', {text: 'Quyết định'}));
    dc.forEach(function (x) {
      var d = IX.dec[x], rec = arr(d.options).filter(function (o) { return isObj(o) && o.id === d.recorded_choice_id; })[0];
      append(box, el('div', {cls: 'item'}, [para(null, str(d.question)), rec ? para(null, [chip('Bài làm tự báo cáo', 'kind-reported'), 'Bài làm ghi nhận lựa chọn: ' + str(rec.label)]) : para('muted', 'Bài làm chưa ghi nhận lựa chọn.'), rec ? refsBlock(d.recorded_choice_ref_ids) : null]));
    });
  }
  var ev = arr(card.evidence_ids).filter(function (x) { return IX.ev[x]; });
  if (ev.length) { append(box, el('h4', {text: 'Bằng chứng'})); ev.forEach(function (x) { append(box, evView(IX.ev[x], true)); }); }
  var sp = arr(card.speaker_prompts).map(str).filter(Boolean);
  if (sp.length) { append(box, el('h4', {text: 'Câu hỏi để bạn tự nói'})); append(box, el('ul', {}, sp.map(function (s) { return el('li', {text: s}); }))); }
  var gl = gapList(card.gap_ids);
  if (gl) { append(box, el('h4', {text: 'Giới hạn / còn thiếu cần nói rõ'})); append(box, gl); }
  append(box, refsBlock(card.source_ref_ids, {noneText: false}));
  var note = noteArea(card.id, 'Ghi chú riêng cho thẻ này (không in, không chia sẻ trừ khi bạn xuất)', {rows: 3, cls: slide && !notesOn ? 'slide-notes-off' : ''});
  append(box, note.wrap);
  return {box: box, heading: h, noteWrap: note.wrap};
}
var slideState = null;
function bPresentation(body, sec) {
  if (!CARDS.length) { append(body, sectionEmpty(sec)); return; }
  var opener = btn('Chế độ trình bày', {cls: 'primary'}, function () { openSlides(0, opener); });
  append(body, el('div', {cls: 'controls no-print'}, [opener, el('span', {cls: 'muted', text: 'Toàn màn hình, mỗi thẻ một trang; phím ← → / PageUp PageDown để chuyển, Esc để thoát.'})]));
  CARDS.forEach(function (c, i) { append(body, buildCard(c, i, CARDS.length, false, true).box); });
}
function openSlides(start, opener) {
  if (slideState) return;
  var titleId = uid('slt');
  var ov = el('div', {cls: 'slides', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': titleId});
  var counter = el('span', {'aria-live': 'polite'});
  var stage = el('div', {cls: 'slides-stage'});
  var toc = el('ol', {cls: 'slides-toc', 'aria-label': 'Mục lục thẻ'});
  var notesOn = false;
  var notesBtn = btn('Hiện ghi chú', {'aria-pressed': 'false'}, function () {
    notesOn = !notesOn;
    notesBtn.setAttribute('aria-pressed', notesOn ? 'true' : 'false');
    notesBtn.textContent = notesOn ? 'Ẩn ghi chú' : 'Hiện ghi chú';
    if (slideState.noteWrap) slideState.noteWrap.classList.toggle('slide-notes-off', !notesOn);
  });
  var prev = btn('← Thẻ trước', {}, function () { go(slideState.i - 1); });
  var next = btn('Thẻ sau →', {cls: 'primary'}, function () { go(slideState.i + 1); });
  var exit = btn('Thoát (Esc)', {}, closeSlides);
  var tocBtns = CARDS.map(function (c, i) { var b = btn((i + 1) + '. ' + trunc(c.title, 28), {}, function () { go(i); }); append(toc, el('li', {}, b)); return b; });
  append(ov, el('div', {cls: 'slides-top'}, [el('h2', {id: titleId, text: 'Chế độ trình bày'}), counter, toc, notesBtn, exit]));
  append(ov, stage);
  append(ov, el('div', {cls: 'slides-bottom'}, [prev, el('span', {cls: 'muted', text: '← → hoặc PageUp/PageDown để chuyển thẻ'}), next]));
  var hiddenSibs = [];
  Array.prototype.forEach.call(document.body.children, function (n) { if (!n.hasAttribute('inert') && n.tagName !== 'SCRIPT') { n.setAttribute('inert', ''); hiddenSibs.push(n); } });
  document.body.appendChild(ov);
  slideState = {i: 0, ov: ov, opener: opener, sibs: hiddenSibs, noteWrap: null};
  function go(i) {
    if (i < 0 || i >= CARDS.length) return;
    slideState.i = i;
    clear(stage);
    var b = buildCard(CARDS[i], i, CARDS.length, true, notesOn);
    slideState.noteWrap = b.noteWrap;
    append(stage, b.box);
    counter.textContent = 'Thẻ ' + (i + 1) + '/' + CARDS.length;
    prev.disabled = i === 0; next.disabled = i === CARDS.length - 1;
    tocBtns.forEach(function (t, k) { if (k === i) t.setAttribute('aria-current', 'step'); else t.removeAttribute('aria-current'); });
    stage.scrollTop = 0;
    b.heading.focus();
  }
  slideState.go = go;
  go(start || 0);
}
function closeSlides() {
  if (!slideState) return;
  var s = slideState;
  slideState = null;
  s.sibs.forEach(function (n) { n.removeAttribute('inert'); });
  if (s.ov.parentNode) s.ov.parentNode.removeChild(s.ov);
  if (s.opener && s.opener.focus) s.opener.focus();
}
function isEditable(t) {
  if (!t || !t.tagName) return false;
  var tg = t.tagName.toLowerCase();
  return tg === 'input' || tg === 'textarea' || tg === 'select' || !!t.isContentEditable;
}
document.addEventListener('keydown', function (e) {
  if (!slideState || isEditable(e.target) || e.altKey || e.ctrlKey || e.metaKey) return;
  if (e.key === 'ArrowRight' || e.key === 'PageDown') { e.preventDefault(); slideState.go(slideState.i + 1); }
  else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); slideState.go(slideState.i - 1); }
  else if (e.key === 'Escape') { e.preventDefault(); closeSlides(); }
});

// ---------------------------------------------------------------- nav, progress, current section
var visited = dict(), current = null, SECS = [], printing = false;
window.addEventListener('beforeprint', function () { printing = true; });
window.addEventListener('afterprint', function () { printing = false; });
function setCurrent(id) {
  if (!id) return;
  current = id;
  SECS.forEach(function (s) { s.classList.toggle('is-current', s.id === id); });
  Array.prototype.forEach.call(document.querySelectorAll('nav.toc a[data-target]'), function (a) {
    if (a.getAttribute('data-target') === id) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current');
  });
  var h = document.getElementById('h-' + id);
  if (printCurrentBtn && h) printCurrentBtn.textContent = 'In mục đang xem (' + trunc(h.textContent, 30) + ')';
  markVisited(id);
}
function markVisited(id) {
  if (visited[id]) return;
  visited[id] = true;
  var a = document.querySelector('nav.toc a[data-target="' + cssKey(id) + '"]');
  if (a) { var m = a.querySelector('.toc-mark'); if (m) { clear(m); append(m, ['✓', el('span', {cls: 'sr-only', text: ' (đã xem)'})]); } }
  var n = Object.keys(visited).length, bar = document.getElementById('toc-bar'), cnt = document.getElementById('toc-count');
  if (bar) { bar.max = SECS.length; bar.value = n; }
  if (cnt) cnt.textContent = 'Đã xem ' + n + '/' + SECS.length + ' mục (chỉ trong phiên này)';
}
function setupNav() {
  Array.prototype.forEach.call(document.querySelectorAll('nav.toc a[data-target]'), function (a) {
    a.addEventListener('click', function () { setCurrent(a.getAttribute('data-target')); });
  });
  SECS.forEach(function (s) { s.addEventListener('focusin', function () { setCurrent(s.id); }); s.addEventListener('pointerdown', function () { setCurrent(s.id); }); });
  if ('IntersectionObserver' in window) {
    var inView = dict();
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { inView[en.target.id] = en.isIntersecting; });
      if (printing || (window.matchMedia && window.matchMedia('print').matches)) return;  // bố cục in không đổi mục đang xem
      for (var i = 0; i < SECS.length; i++) { if (inView[SECS[i].id]) { setCurrent(SECS[i].id); break; } }
    }, {rootMargin: '0px 0px -55% 0px', threshold: 0});
    SECS.forEach(function (s) { io.observe(s); });
  }
  var hash = (location.hash || '').slice(1);
  setCurrent(SECS.some(function (s) { return s.id === hash; }) ? hash : (SECS[0] && SECS[0].id));
}

// ---------------------------------------------------------------- init
var BUILDERS = {overview: bOverview, workflow: bWorkflow, walkthrough: bWalkthrough, decisions: bDecisions,
  evidence: bEvidence, teachback: bTeachback, presentation: bPresentation};
function init() {
  document.body.classList.add('js');
  try { buildToolbar(); } catch (e) { /* trang vẫn dùng được không có thanh công cụ */ }
  SECS = Array.prototype.slice.call(document.querySelectorAll('main section.lesson'));
  SECS.forEach(function (sec) {
    var body = sec.querySelector('.sec-body');
    if (!body) return;
    var b = BUILDERS[sec.getAttribute('data-section')];
    clear(body);
    try { if (b) b(body, sec); }
    catch (e) {
      clear(body);
      append(body, el('p', {cls: 'sec-error', role: 'alert', text: 'Không dựng được mục này (' + str(e && e.message) + '). Các mục khác vẫn dùng được.'}));
    }
  });
  try { loadStored(); } catch (e) { /* bỏ qua */ }
  setupNav();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
"""

for _name, _src in (("CSS", CSS), ("JS", JS)):
    _low = _src.lower()
    assert "</script" not in _low and "</style" not in _low and "<script" not in _low, _name
