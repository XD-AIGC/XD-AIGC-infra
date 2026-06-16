"""把每个角色的 4 视角 RGBA 单图裁剪、统一缩放后横向拼成一张灰底大图。

用法：
  python 06_compose.py
  python 06_compose.py D:/角色识别数据/火炬之光_透明_v2 "D:/角色识别数据/火炬之光参考图（灰色）_v2"

输出：
  <OUT_DIR>/<mesh_name>.png   # mesh_name 同 04_viewer 分组里的 variants[].name

取景（关键）：渲染端只把角色「尽量大」地塞进方形帧，精确取景在这里定稿——
  1. 每个视角按 alpha 包围盒裁掉空白边；
  2. 同一角色的 4 视角用【同一缩放系数】（参考 = 4 视角里最长的那条边），
     使最长边占格子 CELL_FILL，保证 front/side/back/tq 物理比例一致；
  3. 居中放进 CELL×CELL 方形格子，横向拼接。
  这样人形（瘦高）和怪物（矮胖/带翅）都能吃满格子，画质拉平，且与体型无关。

布局：
  [GAP_OUTER][cell0][GAP_INNER][cell1][GAP_INNER][cell2][GAP_INNER][cell3][GAP_OUTER]
"""
import os
import sys

# 外部 Python (PIL + numpy)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_v = __import__("04_viewer")
from PIL import Image
import numpy as np

# ============ 配置 ============
INPUT_ROOT = sys.argv[1] if len(sys.argv) > 1 else r"D:/角色识别数据/火炬之光_透明_v2"
OUTPUT_DIR = sys.argv[2] if len(sys.argv) > 2 else r"D:/角色识别数据/火炬之光参考图（灰色）_v2"
TARGET_LONG = 1400   # 角色最长边目标像素（统一缩放后所有角色长边≈此值 → 画质一致）
PAD = 48             # 格子四周留白
ALPHA_THR = 16       # alpha 包围盒阈值：> 该值算前景（滤掉羽化/噪声边）
GAP_INNER = 48   # 角色之间留白
GAP_OUTER = 48   # 整张图四周留白
BG_COLOR = (96, 96, 96)  # 深灰底（与灰底重渲的单图背景统一）
SKIP_EXISTING = True  # 已存在跳过，续跑友好


def _crop_to_alpha(im):
    """按 alpha 包围盒裁剪 RGBA；返回 (cropped_rgba, w, h)，全透明则返回 (None,0,0)。"""
    a = np.asarray(im.split()[-1])
    ys, xs = np.where(a > ALPHA_THR)
    if len(xs) == 0:
        return None, 0, 0
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return im.crop((x0, y0, x1, y1)), x1 - x0, y1 - y0


def compose_one(view_paths, out_path):
    """view_paths: [front, side, back, 3/4] 4 个绝对路径；缺图 → 纯灰占位格。

    内容自适应格子：格子尺寸贴着「该角色 4 视角缩放后的最大内容宽×最大内容高」走，
    不用固定方形。瘦高角色 → 高格子，宽矮的四足/飞兽 → 宽矮格子，每个角色都填满
    自己的格子、不浪费竖直/水平空间，同时保持 4 视角【统一缩放】（同一 scale）。
    """
    # 1) 读图 + 裁到 alpha 包围盒；统一缩放系数：最长边 → TARGET_LONG
    crops = []   # 每项: cropped_rgba 或 None
    ref = 0      # 4 视角里最长的边
    for p in view_paths:
        c = None
        if p and os.path.isfile(p):
            c, w, h = _crop_to_alpha(Image.open(p).convert("RGBA"))
            if c is not None:
                ref = max(ref, w, h)
        crops.append(c)
    if ref == 0:
        return False  # 一张有效图都没有
    scale = TARGET_LONG / ref

    # 2) 各视角先在原分辨率合到灰底（避免缩放 alpha 边产生黑边），再按统一 scale 缩放
    flats = []
    for c in crops:
        if c is None:
            flats.append(None)
            continue
        flat = Image.new("RGB", c.size, BG_COLOR)
        flat.paste(c, mask=c.split()[-1])
        nw, nh = max(1, round(c.width * scale)), max(1, round(c.height * scale))
        flats.append(flat.resize((nw, nh), Image.LANCZOS))

    # 3) 格子 = 最大内容宽×高 + padding；逐格居中拼接
    cell_w = max(f.width for f in flats if f) + 2 * PAD
    cell_h = max(f.height for f in flats if f) + 2 * PAD
    n = len(flats)
    W = GAP_OUTER * 2 + cell_w * n + GAP_INNER * (n - 1)
    H = GAP_OUTER * 2 + cell_h
    canvas = Image.new("RGB", (W, H), BG_COLOR)
    x = GAP_OUTER
    for f in flats:
        if f is not None:
            cell = Image.new("RGB", (cell_w, cell_h), BG_COLOR)
            cell.paste(f, ((cell_w - f.width) // 2, (cell_h - f.height) // 2))
            canvas.paste(cell, (x, GAP_OUTER))
        # 缺图：该格保持纯灰
        x += cell_w + GAP_INNER
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path, "PNG", optimize=True)
    return True


def main():
    if not os.path.isdir(INPUT_ROOT):
        print(f"[compose] 输入目录不存在: {INPUT_ROOT}")
        sys.exit(1)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    items = _v.scan(INPUT_ROOT)
    total = sum(len(g["variants"]) for g in items)
    print(f"[compose] 扫到 {len(items)} 角色 / {total} mesh → {OUTPUT_DIR}")

    view_filenames = [vf for vf, _ in _v.VIEWS]  # [v0_front.png, v1_side.png, v2_back.png, v3_tq.png]
    done = skipped = empty = 0
    for g in items:
        for v in g["variants"]:
            mesh_name = v["rel"].split("/")[-1].split(".")[0]  # SK_..._LOD0
            out_path = os.path.join(OUTPUT_DIR, f"{mesh_name}.png")
            if SKIP_EXISTING and os.path.isfile(out_path):
                skipped += 1
                continue
            src_dir = os.path.join(INPUT_ROOT, v["rel"].replace("/", os.sep))
            view_paths = [os.path.join(src_dir, vf) for vf in view_filenames]
            ok = compose_one(view_paths, out_path)
            if ok:
                done += 1
                if done % 20 == 0:
                    print(f"[compose] {done} done, {skipped} skipped")
            else:
                empty += 1
                print(f"[compose] 跳过(无图): {v['rel']}")
    print(f"[compose] 完成: 新生成 {done} / 已存在跳过 {skipped} / 空 {empty}")
    print(f"[compose] 输出: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
