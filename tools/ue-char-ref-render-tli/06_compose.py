"""把每个角色的 4 视角 PNG 横向拼成一张黑底大图，flat 输出。

用法：
  python 06_compose.py
  python 06_compose.py D:/ref_shots/full D:/角色识别数据/伊瑟角色参考图

输出：
  <OUT_DIR>/<mesh_name>.png   # mesh_name 同 characters.json 里的 variants[].mesh_name

布局：
  [GAP_OUTER][front][GAP_INNER][side][GAP_INNER][back][GAP_INNER][3/4][GAP_OUTER]
  上下各 GAP_OUTER 留白；黑底 RGB（无 alpha）；保持单图原分辨率 1024×2304。
"""
import os
import sys

# 外部 Python (PIL)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_v = __import__("04_viewer")
from PIL import Image

# ============ 配置 ============
INPUT_ROOT = sys.argv[1] if len(sys.argv) > 1 else r"D:/ref_shots/full"
OUTPUT_DIR = sys.argv[2] if len(sys.argv) > 2 else r"D:/角色识别数据/伊瑟角色参考图"
GAP_INNER = 64   # 角色之间留白
GAP_OUTER = 64   # 整张图四周留白
BG_COLOR = (96, 96, 96)  # 深灰底（与灰底重渲的单图背景统一；原为 (0,0,0) 黑底）
SKIP_EXISTING = True  # 已存在跳过，续跑友好


def compose_one(view_paths, out_path):
    """view_paths: [front, side, back, 3/4] 4 个绝对路径；可能某个不存在 → 用纯黑占位。"""
    imgs = []
    w_each = h_each = None
    for p in view_paths:
        if p and os.path.isfile(p):
            im = Image.open(p).convert("RGBA")
            imgs.append(im)
            w_each, h_each = im.size
        else:
            imgs.append(None)
    if w_each is None:
        return False  # 一张都没有
    n = len(imgs)
    W = GAP_OUTER * 2 + w_each * n + GAP_INNER * (n - 1)
    H = GAP_OUTER * 2 + h_each
    canvas = Image.new("RGB", (W, H), BG_COLOR)
    x = GAP_OUTER
    for im in imgs:
        if im is not None:
            # 用 alpha 合到黑底
            bg = Image.new("RGB", im.size, BG_COLOR)
            bg.paste(im, mask=im.split()[-1])
            canvas.paste(bg, (x, GAP_OUTER))
        x += w_each + GAP_INNER
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
