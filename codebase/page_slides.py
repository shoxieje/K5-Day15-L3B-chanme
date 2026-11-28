"""Slide cho một lab: dựng thẳng từ bài học đã kiểm nguồn, không gọi model."""
import ui

MAX_BULLETS = 4

CSS = """
.deck{position:fixed;left:0;right:0;top:49px;bottom:0;overflow:hidden;background:var(--bg);touch-action:pan-y}
.stage{position:absolute;left:50%;top:50%;transform-origin:center;background:var(--bg)}
.slide{position:absolute;inset:0;display:none;flex-direction:column;justify-content:center;padding:96px 128px}
.slide.on{display:flex}
.slide h1{font-size:68px;line-height:1.15;margin:0 0 24px;letter-spacing:-.02em}
.slide h2{font-size:44px;line-height:1.2;margin:0 0 40px;letter-spacing:-.015em}
.slide h3{font-size:18px;margin:28px 0 10px}
.slide ul{list-style:none;padding:0;margin:0}
.slide li{font-size:28px;line-height:1.4;margin:0 0 12px;padding-left:28px;position:relative}
.slide li:before{content:"";position:absolute;left:0;top:.62em;width:10px;height:10px;border-radius:50%;background:var(--accent)}
.slide li.warn:before{background:var(--warn)}
.slide .src{font-size:15px;margin-left:8px}
.slide .sub{font-size:28px;color:var(--muted);margin:0}
.slide .tag{display:inline-block;font-size:20px;color:var(--warn);border:1px solid var(--warn);border-radius:999px;padding:4px 18px;margin-top:40px;align-self:flex-start}
.slide ol{margin:0;padding:0;list-style:none;columns:2;column-gap:64px}
.slide ol li{break-inside:avoid}
.slide ol li:before{display:none}
.slide ol li{padding-left:0}
.slide .cols{display:grid;grid-template-columns:1fr 1fr;gap:64px}
.slide .cols h3{margin-top:0}
.slide .empty{color:var(--muted);font-size:24px}
.ctr{position:fixed;right:16px;bottom:10px;font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums;z-index:6}
.stage.portrait .slide{padding:56px 48px}
.stage.portrait .slide h1{font-size:60px}
.stage.portrait .slide h2{font-size:42px}
.stage.portrait .slide li{font-size:30px}
.stage.portrait .slide ol{columns:1}
.stage.portrait .slide .cols{grid-template-columns:1fr;gap:8px}
@page{size:1280px 720px;margin:0}
@media print{
html,body{background:#fff}
.deck{position:static;overflow:visible}
.stage{position:static;transform:none!important;width:auto!important;height:auto!important}
.slide{display:flex!important;position:relative;width:1280px;height:720px;page-break-after:always;break-after:page;overflow:hidden;background:#fff}
.slide:last-child{page-break-after:auto;break-after:auto}
.ctr{display:none}
}
"""

SCRIPT = """
(function(){
var st=document.getElementById('stage'),sl=[].slice.call(st.children),c=document.getElementById('ctr'),i=0,dk=st.parentNode;
try{var h=parseInt(location.hash.slice(1),10);if(h>=1&&h<=sl.length)i=h-1}catch(e){}
function fit(){var w=dk.clientWidth,h=dk.clientHeight,p=w<h;
st.className='stage'+(p?' portrait':'');
var W=p?720:1280,H=p?1280:720;st.style.width=W+'px';st.style.height=H+'px';
var s=Math.min(w/W,h/H);st.style.transform='translate(-50%,-50%) scale('+s+')'}
function show(n){i=Math.max(0,Math.min(sl.length-1,n));
sl.forEach(function(e,k){e.classList.toggle('on',k===i)});
c.textContent=(i+1)+' / '+sl.length;
try{history.replaceState(null,'','#'+(i+1))}catch(e){}}
document.addEventListener('keydown',function(e){
if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown'){e.preventDefault();show(i+1)}
else if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();show(i-1)}
else if(e.key==='Home')show(0);else if(e.key==='End')show(sl.length-1)});
dk.addEventListener('click',function(e){if(e.target.closest('a'))return;show(e.clientX>window.innerWidth/2?i+1:i-1)});
var x0=null;
dk.addEventListener('touchstart',function(e){x0=e.touches[0].clientX},{passive:true});
dk.addEventListener('touchend',function(e){if(x0===null)return;var d=e.changedTouches[0].clientX-x0;x0=null;
if(Math.abs(d)>40){show(d<0?i+1:i-1);e.preventDefault()}});
window.addEventListener('resize',fit);fit();show(i);
})();
"""


def _bullets(items, warn=False):
    if not items:
        return '<p class="empty">Không có trong nguồn.</p>'
    cls = ' class="warn"' if warn else ""
    return "<ul>%s</ul>" % "".join(
        "<li%s>%s%s</li>" % (cls, ui.esc(it.get("text", "")), ui.src(it)) for it in items[:MAX_BULLETS]
    )


def _section(label, items, warn=False):
    return "<h3>%s</h3>%s" % (ui.esc(label), _bullets(items, warn))


def render_slides(lesson: dict, lab_name: str) -> str:
    tasks = lesson.get("tasks", []) or []
    not_in = lesson.get("not_in_lab", []) or []
    L = ui.PART_LABEL
    slides = []

    slides.append(
        '<section class="slide"><h1>%s</h1><p class="sub">%d nhiệm vụ trong lab</p>'
        '<span class="tag">Bản nháp, chờ trợ giảng duyệt</span></section>' % (ui.esc(lab_name), len(tasks))
    )
    names = "".join("<li>%s</li>" % ui.esc(t.get("name", "")) for t in tasks)
    slides.append('<section class="slide"><h2>Tổng quan</h2><ol>%s</ol></section>' % names)

    for n, t in enumerate(tasks, 1):
        p = ui.by_part(t)
        slides.append(
            '<section class="slide"><h2>%d. %s</h2>%s%s%s</section>'
            % (n, ui.esc(t.get("name", "")), _section(L["muc_tieu"], p.get("muc_tieu", [])),
               _section(L["agent_thay"], p.get("agent_thay", [])), _section(L["cong_cu"], p.get("cong_cu", [])))
        )
        slides.append(
            '<section class="slide"><h2>Bước đúng / Lỗi dễ mắc</h2><p class="note" style="margin:-24px 0 24px">%s</p>'
            '<div class="cols"><div>%s</div><div>%s</div></div></section>'
            % (ui.esc(t.get("name", "")), _section(L["buoc_dung"], p.get("buoc_dung", [])),
               _section(L["loi_de_mac"], p.get("loi_de_mac", []), warn=True))
        )

    out = "".join("<li>%s</li>" % ui.esc(x) for x in not_in[:MAX_BULLETS * 2]) or ""
    slides.append(
        '<section class="slide"><h2>Không có trong bài</h2>%s</section>'
        % ("<ul>%s</ul>" % out if out else '<p class="empty">Không có mục nào.</p>')
    )

    body = '<div class="deck"><div class="stage" id="stage">%s</div></div><div class="ctr" id="ctr"></div>' % "".join(slides)
    path = ui.out_path(lab_name, "slides")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ui.page(lab_name, "slides", body, extra_css=CSS, script=SCRIPT))
    return ui.rel(path)
