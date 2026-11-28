"""Trang 3 của mỗi lab: tóm tắt một trang (cheat sheet).
Không gọi model: chỉ dựng từ bài học đã kiểm nguồn."""
import ui

CSS = """
.meta{color:var(--muted);font-size:14px;margin:0 0 20px}
.toc{border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:8px 0;margin:0 0 8px;font-size:14px}
.toc ol{margin:0;padding-left:20px;columns:2;column-gap:24px}
.toc a{color:var(--fg);text-decoration:none}.toc a:hover{color:var(--accent)}
.task{padding:20px 0;border-bottom:1px solid var(--line);break-inside:avoid}
.task h2{font-size:18px;margin:0 0 6px}
.goal{margin:4px 0 8px}
ul.steps,ul.warn{list-style:none;padding:0;margin:0}
ul.steps li{display:flex;gap:10px;align-items:flex-start;padding:3px 0}
ul.steps input{margin:5px 0 0;flex:none;accent-color:var(--accent)}
ul.steps label{cursor:pointer}
ul.warn li{padding:2px 0 2px 12px;border-left:2px solid var(--warn);margin:4px 0;color:var(--fg)}
ul.warn li::before{content:"";}
.sec h3{margin:16px 0 4px}
.warnh{color:var(--warn)}
.all{padding-top:8px}
.all h2{font-size:18px;margin:24px 0 6px}
.empty{color:var(--muted);font-size:14px}
@media (max-width:520px){.toc ol{columns:1}}
@media print{.wrap{max-width:none;padding:0}h1{font-size:22px}.task{padding:10px 0}body{font-size:12.5px;line-height:1.45}.toc{display:none}.src{font-size:10px}}
"""


def _steps(items):
    if not items:
        return ""
    lis = "".join(
        '<li><input type="checkbox" id="%s"><label for="%s">%s %s</label></li>' % (i, i, ui.esc(it.get("text")), ui.src(it))
        for n, it in enumerate(items) for i in ["s%d-%d" % (id(items) % 100000, n)]
    )
    return '<h3>%s</h3><ul class="steps">%s</ul>' % (ui.PART_LABEL["buoc_dung"], lis)


def _warns(items, head=True):
    if not items:
        return ""
    lis = "".join("<li>%s %s</li>" % (ui.esc(it.get("text")), ui.src(it)) for it in items)
    h = '<h3 class="warnh">%s</h3>' % ui.PART_LABEL["loi_de_mac"] if head else ""
    return '%s<ul class="warn">%s</ul>' % (h, lis)


def render_summary(lesson: dict, lab_name: str) -> str:
    tasks = lesson.get("tasks", []) or []
    not_in = lesson.get("not_in_lab", []) or []
    n_items = sum(len(t.get("items", [])) for t in tasks)

    toc = "".join('<li><a href="#t%d">%s</a></li>' % (i, ui.esc(t.get("name"))) for i, t in enumerate(tasks, 1))
    cards, all_warn = [], []
    for i, t in enumerate(tasks, 1):
        p = ui.by_part(t)
        goals = "".join('<p class="goal">%s %s</p>' % (ui.esc(g.get("text")), ui.src(g)) for g in p.get("muc_tieu", [])[:2])
        warns = p.get("loi_de_mac", [])
        for w in warns:
            all_warn.append((t.get("name"), w))
        cards.append(
            '<section class="task" id="t%d"><h2>%d. %s</h2>%s%s%s</section>'
            % (i, i, ui.esc(t.get("name")), goals, _steps(p.get("buoc_dung", [])), _warns(warns))
        )

    if all_warn:
        agg = '<ul class="warn">%s</ul>' % "".join(
            "<li><strong>%s</strong> · %s %s</li>" % (ui.esc(n), ui.esc(w.get("text")), ui.src(w)) for n, w in all_warn
        )
    else:
        agg = '<p class="empty">Chưa có lỗi nào được ghi nhận.</p>'
    nil = (
        "<ul>%s</ul>" % "".join("<li>%s</li>" % ui.esc(x) for x in not_in)
        if not_in else '<p class="empty">Không có mục nào.</p>'
    )

    body = (
        '<main class="wrap"><h1>Tóm tắt · %s</h1>'
        '<p class="meta">%d nhiệm vụ · %d ý có nguồn · Bản nháp, chờ trợ giảng duyệt</p>'
        '<nav class="toc" aria-label="Mục lục"><ol>%s</ol></nav>%s'
        '<section class="all"><h2>Lỗi dễ mắc của cả bài</h2>%s'
        "<h2>Không có trong bài</h2>%s</section></main>"
        % (ui.esc(lab_name), len(tasks), n_items, toc, "".join(cards), agg, nil)
    )
    path = ui.out_path(lab_name, "summary")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ui.page(lab_name, "summary", body, extra_css=CSS))
    return ui.rel(path)
