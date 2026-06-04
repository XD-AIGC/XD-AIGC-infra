"""把一组渲染结果(每个角色取一个视角)拼成一张带名字的大图，便于整组分析调参。

用法（外部 Python，需 PIL）：
  python grid_sheet.py [root] [view] [cols]
  root  扫描根目录，默认白名单输出 D:/角色识别数据/伊瑟_UE4_whitelist
  view  取哪个视角，默认 v0_front.png（可 v3_tq.png 等）
  cols  每行几个，默认 6
输出： <root>/contact_sheet.png（自动打开）
"""
import os, sys, math
from PIL import Image, ImageDraw, ImageFont

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"D:/角色识别数据/伊瑟_UE4_whitelist"
VIEW = sys.argv[2] if len(sys.argv) > 2 else "v0_front.png"
COLS = int(sys.argv[3]) if len(sys.argv) > 3 else 6
CELL_W = 240          # 每格缩略图宽
LABEL_H = 26          # 名字条高
BG = (40, 40, 40)     # 画布底（比缩略图灰底稍深，衬出每张图边界）
GRAY = (96, 96, 96)   # 缩略图合成底色（交付灰底，透明图合到这上面看真实效果）
PAD = 6

def main():
    if not os.path.isdir(ROOT):
        print("[grid] 目录不存在:", ROOT); sys.exit(1)
    items = []
    for dp, _, fs in os.walk(ROOT):
        if VIEW in fs:
            items.append((os.path.basename(dp), os.path.join(dp, VIEW)))
    items.sort(key=lambda x: x[0].lower())
    if not items:
        print("[grid] 没找到", VIEW, "于", ROOT); sys.exit(1)

    thumbs = []
    cell_h = 0
    for label, p in items:
        src = Image.open(p).convert("RGBA")          # 透明图合成到灰底；老 RGB 图 alpha 全 255 也兼容
        im = Image.new("RGB", src.size, GRAY)
        im.paste(src, mask=src.split()[-1])
        w, h = im.size
        nh = int(h * CELL_W / w)
        thumbs.append((label, im.resize((CELL_W, nh))))
        cell_h = max(cell_h, nh)

    cellH = cell_h + LABEL_H
    rows = math.ceil(len(thumbs) / COLS)
    W, H = COLS * CELL_W, rows * cellH
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except Exception:
        font = ImageFont.load_default()

    for idx, (label, im) in enumerate(thumbs):
        r, c = divmod(idx, COLS)
        x, y = c * CELL_W, r * cellH
        canvas.paste(im, (x, y + (cell_h - im.size[1])))   # 底对齐
        lab = label.replace("SK_", "").replace("_LOD0", "").replace("_Lod0", "")
        if len(lab) > 36:
            lab = lab[:34] + ".."
        draw.text((x + PAD, y + cell_h + 5), lab, fill=(225, 225, 225), font=font)

    out = os.path.join(ROOT, "contact_sheet.png")
    canvas.save(out, "PNG")
    print("[grid] 已生成:", out, "(%d 张, %dx%d)" % (len(thumbs), W, H))
    try:
        os.startfile(out)
    except Exception:
        pass

if __name__ == "__main__":
    main()
