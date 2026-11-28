"""Trang đóng vai (Be The Agent): mỗi nhiệm vụ một mục, chọn bước tiếp theo rồi xem đáp án.
Dựng từ khuôn, không gọi model, không tác động ra ngoài."""
import ui

CSS = """
.sub{color:var(--muted);font-size:14px;margin:0 0 8px}
.progress{color:var(--muted);font-size:13px;margin:16px 0 0}
.task{padding:40px 0;border-top:1px solid var(--line)}
.task:first-of-type{margin-top:32px}
.task h2{margin:0 0 16px;font-size:20px}
.task h2 .n{color:var(--muted);font-weight:400;margin-right:10px;font-variant-numeric:tabular-nums}
.task p{margin:8px 0}
.choices{display:flex;flex-direction:column;gap:8px;margin:12px 0 0}
.choice{display:block;width:100%;text-align:left;background:transparent;border:1px solid var(--line);border-radius:8px;padding:12px 14px;cursor:pointer;line-height:1.5}
.choice:hover{background:var(--soft)}
.choice:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.choice.picked{border-color:var(--accent)}
.choice .src{display:block;margin-top:4px}
.reveal{display:none;margin-top:24px;padding-top:8px;border-top:1px solid var(--line)}
.shown .reveal{display:block;animation:fade .3s ease both}
@keyframes fade{from{opacity:0}to{opacity:1}}
@media (prefers-reduced-motion:reduce){.shown .reveal{animation:none}}
.warn h3{color:var(--warn)}
.outside{padding-top:40px;border-top:1px solid var(--line)}
.outside h2{margin:0 0 8px}
"""

JS = """
(function(){
var tasks=document.querySelectorAll('.task'),p=document.getElementById('progress');
function upd(){var n=document.querySelectorAll('.task.shown').length;if(p)p.textContent=n+' / '+tasks.length+' nhiệm vụ đã thử';}
tasks.forEach(function(t){t.querySelectorAll('.choice').forEach(function(b){b.addEventListener('click',function(){
t.querySelectorAll('.choice').forEach(function(x){x.classList.remove('picked');x.setAttribute('aria-pressed','false');});
b.classList.add('picked');b.setAttribute('aria-pressed','true');t.classList.add('shown');upd();});});});
upd();
})();
"""


def _sec(by, part, cls=""):
    items = by.get(part, [])
    if not items:
        return ""
    return '<div class="%s"><h3>%s</h3>%s</div>' % (
        cls, ui.esc(ui.PART_LABEL[part]),
        "".join("<p>%s %s</p>" % (ui.esc(i.get("text", "")), ui.src(i)) for i in items))


def render_roleplay(lesson: dict, lab_name: str) -> str:
    tasks = lesson.get("tasks", [])
    parts = []
    for n, t in enumerate(tasks, 1):
        by = ui.by_part(t)
        choices = "".join(
            '<button type="button" class="choice" aria-pressed="false">%s%s</button>'
            % (ui.esc(i.get("text", "")), ui.src(i)) for i in by.get("lua_chon", []))
        parts.append(
            '<section class="task"><h2><span class="n">%d</span>%s</h2>%s'
            '<div><h3>Bạn là agent. Bạn đang thấy</h3>%s</div><div><h3>Công cụ bạn có</h3>%s</div>'
            '<h3>Bước tiếp theo bạn chọn?</h3><div class="choices">%s</div>'
            '<div class="reveal">%s%s</div></section>'
            % (n, ui.esc(t.get("name", "")),
               _sec(by, "muc_tieu"),
               "".join("<p>%s %s</p>" % (ui.esc(i.get("text", "")), ui.src(i)) for i in by.get("agent_thay", [])),
               "".join("<p>%s %s</p>" % (ui.esc(i.get("text", "")), ui.src(i)) for i in by.get("cong_cu", [])),
               choices, _sec(by, "buoc_dung"), _sec(by, "loi_de_mac", "warn")))
    nil = "".join("<li>%s</li>" % ui.esc(x) for x in lesson.get("not_in_lab", []))
    body = (
        '<main class="wrap"><h1>Be The Agent · %s</h1>'
        '<p class="sub">Bản nháp, chờ trợ giảng duyệt.</p>'
        '<p class="progress" id="progress"></p>%s'
        '<section class="outside"><h2>Không có trong bài</h2><ul>%s</ul></section></main>'
        % (ui.esc(lab_name), "".join(parts), nil or "<li class=\"note\">(không có)</li>"))
    out = ui.out_path(lab_name, "roleplay")
    with open(out, "w", encoding="utf-8") as f:
        f.write(ui.page(lab_name, "roleplay", body, extra_css=CSS, script=JS))
    return ui.rel(out)
