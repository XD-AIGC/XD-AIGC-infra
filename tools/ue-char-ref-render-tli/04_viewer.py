"""扫描渲染输出目录，按角色 ID 分组生成可点击放大的 HTML 预览页。

用法：
  python 04_viewer.py                       # 默认扫 D:/ref_shots/full
  python 04_viewer.py D:/ref_shots/test     # 扫别的目录

会在被扫目录根写 viewer.html 并自动打开。所有图片走相对路径，
拷走整个目录（连同 viewer.html）也能离线看。

分组规则（基于伊瑟资产命名）：
  - Agt: 每个 Agt_<Name> 独立角色，无套装
  - Cst: Cst_<Char> 一个角色，下挂 1~5 个觉醒套装（Const/Disor/Hollow/Light/Odd）
  - Chr: Chr_Boy_Home / Chr_Girl_Home / Chr_Friday 三个合并基底，下挂多套装；
         其他 Chr_<x> 各自独立
  - Prop / Thrown: 按第二段目录原样分组

功能：
  - 卡片列表，每个角色一张卡，套装多时压成一张卡多行 4 视角
  - 顶栏：搜索（路径/角色名/套装名）、类型筛选、>=2 套装的角色筛选
  - 点缩略图全屏预览；← → 切视角，ESC / 点空白关闭
"""
import os
import sys
import json
import re
import webbrowser

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"D:/角色识别数据/火炬之光"

VIEWS = [
    ("v0_front.png", "front"),
    ("v1_side.png",  "side"),
    ("v2_back.png",  "back"),
    ("v3_tq.png",    "3/4"),
]

# 火炬之光分组：路径形如 Art/Characters/<Type>/<角色文件夹>/Meshes/SK_..._Skin
#   - 同一角色文件夹下的多个 SK_*_Skin = 同角色的多套皮肤（变体）
#   - Type = Characters 的下一级（Hero / Monster / NPC / Pet / Token + 各 _Showcase；
#            Boss 在 Monster/Boss 下，归 Monster）；Fashion 路径归 "Fashion"
CATEGORY_ANCHORS = ("Characters", "Fashion")


def parse_role(rel):
    """返回 (type, role_key, role_id)。
    role_key = 角色目录完整路径（分组键，唯一）；role_id = 角色文件夹名（展示用）。
    """
    parts = rel.split("/")
    if "Meshes" in parts:
        mi = parts.index("Meshes")
        char_parts = parts[:mi]
    else:
        char_parts = parts[:-1]
    role_key = "/".join(char_parts) if char_parts else rel
    role_id = char_parts[-1] if char_parts else rel
    typ = "?"
    if "Fashion" in parts:
        typ = "Fashion"
    elif "Characters" in parts:
        ci = parts.index("Characters")
        if ci + 1 < len(parts):
            typ = parts[ci + 1]
    return typ, role_key, role_id


def scan(root):
    """扫目录，按角色文件夹聚合；同文件夹多个 SK_*_Skin 作为皮肤变体。"""
    raw = []  # (rel_dir, [views])
    front = VIEWS[0][0]
    for dirpath, _dirs, files in os.walk(root):
        if front not in files:
            continue
        rel = os.path.relpath(dirpath, root).replace("\\", "/")
        views = [{"src": f"{rel}/{f}", "label": lab} for f, lab in VIEWS if f in files]
        raw.append((rel, views))

    groups = {}  # role_key → dict
    for rel, views in raw:
        typ, role_key, role_id = parse_role(rel)
        mesh_name = rel.split("/")[-1].split(".")[0]  # SK_..._Skin（去 UE 双后缀，皮肤名）
        if role_key not in groups:
            groups[role_key] = {"roleId": role_id, "type": typ, "variants": []}
        groups[role_key]["variants"].append({"name": mesh_name, "rel": rel, "views": views})

    items = list(groups.values())
    items.sort(key=lambda g: (g["type"].lower(), g["roleId"].lower()))
    for g in items:
        g["variants"].sort(key=lambda v: v["name"].lower())
    return items


TEMPLATE = r"""<!doctype html>
<html lang="zh"><head>
<meta charset="utf-8">
<title>UE Char Ref Viewer (__ROLES__ roles / __MESHES__ meshes)</title>
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
       background: #1a1a1a; color: #ddd; }
header { position: sticky; top: 0; background: #222; padding: 10px 16px;
         border-bottom: 1px solid #333; z-index: 10;
         display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
header h1 { margin: 0; font-size: 13px; font-weight: normal; color: #888; }
header input { background: #111; color: #ddd; border: 1px solid #444;
               padding: 6px 10px; font-size: 13px; width: 260px; border-radius: 4px; }
.pill { background: #2a2a2a; color: #aaa; padding: 4px 10px; border-radius: 12px;
        font-size: 12px; cursor: pointer; user-select: none; border: 1px solid #333; }
.pill.active { background: #4a90e2; color: #fff; border-color: #4a90e2; }
.count { margin-left: auto; color: #666; font-size: 12px; }
main { padding: 14px; }
.card { background: #222; border: 1px solid #2d2d2d; border-radius: 6px;
        margin-bottom: 14px; padding: 10px 12px; }
.card-head { display: flex; align-items: center; gap: 10px; cursor: pointer;
             margin-bottom: 8px; padding: 2px 0; }
.card-head .arrow { color: #666; font-size: 10px; width: 12px; }
.card-head .role { color: #ddd; font-size: 15px; font-weight: 500; }
.card-head .type-tag { color: #888; font-size: 11px; background: #333;
                       padding: 2px 6px; border-radius: 3px; }
.card-head .nvar { color: #4a90e2; font-size: 11px; background: #1a3050;
                   padding: 2px 6px; border-radius: 3px; }
.card-body { display: block; }
.card.collapsed .card-body { display: none; }
.card.collapsed .arrow::before { content: '▶'; }
.card:not(.collapsed) .arrow::before { content: '▼'; }
.variant { margin-bottom: 10px; }
.variant:last-child { margin-bottom: 0; }
.variant .vname { color: #aaa; font-size: 12px; font-family: Consolas, monospace;
                  margin-bottom: 4px; }
.variant .vpath { color: #555; font-size: 10px; font-family: Consolas, monospace;
                  margin-bottom: 4px; word-break: break-all; }
.row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.thumb { position: relative; background: repeating-conic-gradient(#1d1d1d 0% 25%, #252525 0% 50%) 50% / 16px 16px;
         border-radius: 4px; overflow: hidden; aspect-ratio: 1/1; cursor: zoom-in; }
.thumb img { width: 100%; height: 100%; object-fit: contain; display: block; }
.thumb .label { position: absolute; bottom: 4px; left: 4px; background: rgba(0,0,0,0.6);
                color: #ccc; padding: 1px 6px; border-radius: 3px; font-size: 10px; }
.thumb:hover { outline: 2px solid #4a90e2; }

#lb { position: fixed; inset: 0; background: rgba(0,0,0,0.93); display: none;
      align-items: center; justify-content: center; z-index: 100; }
#lb.on { display: flex; }
#lb img { max-width: 95vw; max-height: 95vh;
          background: repeating-conic-gradient(#1d1d1d 0% 25%, #252525 0% 50%) 50% / 32px 32px; }
#lb .meta { position: absolute; top: 12px; left: 16px; color: #eee; font-size: 12px;
            font-family: Consolas, monospace; background: rgba(0,0,0,0.6);
            padding: 6px 10px; border-radius: 4px; max-width: 70vw; }
#lb .nav { position: absolute; top: 50%; transform: translateY(-50%); color: #fff;
           background: rgba(255,255,255,0.1); border: 0; width: 50px; height: 70px;
           font-size: 28px; cursor: pointer; border-radius: 4px; }
#lb .nav:hover { background: rgba(255,255,255,0.25); }
#lb .prev { left: 16px; } #lb .next { right: 16px; }
#lb .close { position: absolute; top: 12px; right: 16px; color: #fff;
             background: transparent; border: 0; font-size: 28px; cursor: pointer; }
</style></head><body>
<header>
  <h1>UE Char Ref Viewer</h1>
  <input id="q" placeholder="搜角色/套装/路径..." autocomplete="off">
  <span class="pill active" data-filter="all">全部</span>
  <span class="pill" data-filter="Hero">Hero</span>
  <span class="pill" data-filter="Monster">Monster</span>
  <span class="pill" data-filter="Pet">Pet</span>
  <span class="pill" data-filter="Token">Token</span>
  <span class="pill" data-filter="NPC">NPC</span>
  <span class="pill" data-filter="Fashion">Fashion</span>
  <span class="pill" data-filter="multi">仅多皮肤</span>
  <span class="pill" data-toggle="collapseAll">折叠全部</span>
  <span class="count" id="count"></span>
</header>
<main id="grid"></main>

<div id="lb">
  <button class="close" id="lbClose">×</button>
  <div class="meta" id="lbMeta"></div>
  <button class="nav prev" id="lbPrev">‹</button>
  <img id="lbImg" alt="">
  <button class="nav next" id="lbNext">›</button>
</div>

<script>
const DATA = __DATA__;
const grid = document.getElementById('grid');
const q = document.getElementById('q');
const count = document.getElementById('count');
let filter = 'all';
let allCollapsed = false;

function matches(g) {
  if (filter === 'multi' && g.variants.length < 2) return false;
  if (filter !== 'all' && filter !== 'multi' && !g.type.includes(filter)) return false;
  const term = q.value.trim().toLowerCase();
  if (!term) return true;
  if (g.roleId.toLowerCase().includes(term)) return true;
  return g.variants.some(v =>
    v.name.toLowerCase().includes(term) || v.rel.toLowerCase().includes(term)
  );
}

function esc(s) {
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function render() {
  const filtered = DATA.filter(matches);
  const totalMeshes = filtered.reduce((s, g) => s + g.variants.length, 0);
  count.textContent = filtered.length + ' roles / ' + totalMeshes + ' meshes';
  grid.innerHTML = filtered.map((g, gi) => {
    const gIdx = DATA.indexOf(g);
    const multi = g.variants.length > 1;
    const collapsedClass = (allCollapsed && multi) ? ' collapsed' : '';
    const variants = g.variants.map((v, vi) => {
      const thumbs = v.views.map((view, viewIdx) =>
        '<div class="thumb" data-card="' + gIdx + '" data-var="' + vi + '" data-view="' + viewIdx + '">' +
          '<img src="' + esc(view.src) + '" alt="' + esc(view.label) + '" loading="lazy">' +
          '<div class="label">' + esc(view.label) + '</div>' +
        '</div>'
      ).join('');
      const head = multi
        ? '<div class="vname">' + esc(v.name) + '</div>' +
          '<div class="vpath">' + esc(v.rel) + '</div>'
        : '<div class="vpath">' + esc(v.rel) + '</div>';
      return '<div class="variant">' + head + '<div class="row">' + thumbs + '</div></div>';
    }).join('');
    const nvar = multi ? '<span class="nvar">' + g.variants.length + ' 皮肤</span>' : '';
    return '<div class="card' + collapsedClass + '" data-card="' + gIdx + '">' +
      '<div class="card-head">' +
        '<span class="arrow"></span>' +
        '<span class="role">' + esc(g.roleId) + '</span>' +
        '<span class="type-tag">' + esc(g.type) + '</span>' +
        nvar +
      '</div>' +
      '<div class="card-body">' + variants + '</div>' +
    '</div>';
  }).join('');
}

const lb = document.getElementById('lb');
const lbImg = document.getElementById('lbImg');
const lbMeta = document.getElementById('lbMeta');
let lbCard = 0, lbVar = 0, lbView = 0;

function openLb(c, vr, vi) { lbCard = c; lbVar = vr; lbView = vi; updateLb(); lb.classList.add('on'); }
function updateLb() {
  const g = DATA[lbCard];
  const v = g.variants[lbVar];
  const view = v.views[lbView];
  lbImg.src = view.src;
  const label = g.roleId + (g.variants.length > 1 ? ' / ' + v.name : '');
  lbMeta.textContent = label + '  ·  ' + view.label + ' (' + (lbView + 1) + '/' + v.views.length + ')';
}
function closeLb() { lb.classList.remove('on'); lbImg.src = ''; }
function navLb(d) {
  const v = DATA[lbCard].variants[lbVar];
  lbView = (lbView + d + v.views.length) % v.views.length;
  updateLb();
}

grid.addEventListener('click', e => {
  const t = e.target.closest('.thumb');
  if (t) { openLb(+t.dataset.card, +t.dataset.var, +t.dataset.view); return; }
  const h = e.target.closest('.card-head');
  if (h) {
    const card = h.closest('.card');
    if (card.querySelector('.nvar')) card.classList.toggle('collapsed');
  }
});
document.getElementById('lbClose').onclick = closeLb;
document.getElementById('lbPrev').onclick = () => navLb(-1);
document.getElementById('lbNext').onclick = () => navLb(1);
lb.addEventListener('click', e => { if (e.target === lb) closeLb(); });
document.addEventListener('keydown', e => {
  if (!lb.classList.contains('on')) return;
  if (e.key === 'Escape') closeLb();
  else if (e.key === 'ArrowLeft') navLb(-1);
  else if (e.key === 'ArrowRight') navLb(1);
});
q.addEventListener('input', render);
document.querySelectorAll('.pill').forEach(p => p.onclick = () => {
  if (p.dataset.toggle === 'collapseAll') {
    allCollapsed = !allCollapsed;
    p.textContent = allCollapsed ? '展开全部' : '折叠全部';
    p.classList.toggle('active', allCollapsed);
    render();
    return;
  }
  document.querySelectorAll('.pill[data-filter]').forEach(x => x.classList.remove('active'));
  p.classList.add('active'); filter = p.dataset.filter; render();
});
render();
</script></body></html>"""


def main():
    if not os.path.isdir(ROOT):
        print(f"[viewer] 目录不存在: {ROOT}")
        sys.exit(1)
    items = scan(ROOT)
    total_meshes = sum(len(g["variants"]) for g in items)
    print(f"[viewer] 扫描 {ROOT}: {len(items)} 个角色 / {total_meshes} 个 mesh")
    multi = [g for g in items if len(g["variants"]) > 1]
    print(f"[viewer] 多套装角色 {len(multi)} 个，最多套装: " +
          (f"{max((len(g['variants']) for g in multi), default=0)} ({max(multi, key=lambda g: len(g['variants']))['roleId']})" if multi else "无"))
    doc = TEMPLATE.replace("__DATA__", json.dumps(items, ensure_ascii=False)) \
                  .replace("__ROLES__", str(len(items))) \
                  .replace("__MESHES__", str(total_meshes))
    out = os.path.join(ROOT, "viewer.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"[viewer] 已生成: {out}")
    try:
        os.startfile(out)
    except Exception:
        webbrowser.open(f"file:///{out.replace(os.sep, '/')}")


if __name__ == "__main__":
    main()
