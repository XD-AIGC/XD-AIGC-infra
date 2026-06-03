"""03_batch 的后处理(外部 Python，需 PIL+numpy)。从 stdin 读 JSON：
{ pairs:[(out,[tmp..])..], target, maxscale, pct, skin, composite }
对每个 pair：
  - 普通(单截)：自动提亮(可选 skin_fix 占位橙→肤色)。
  - composite(双截 base+emis，Agt 用)：身体用 base 真实色(提亮)，发光处叠 emissive(红角)。
处理完写回 out、删临时文件。spec 走 stdin 避免中文路径编码问题。
"""
import sys, json, os
from PIL import Image
import numpy as np

d = json.loads(sys.stdin.read())
TARGET = float(d["target"]); MAXSCALE = float(d["maxscale"]); PCT = float(d["pct"])
SKIN = d.get("skin"); COMP = d.get("composite")


def brighten(f):
    lum = f.max(2); fg = lum[lum > 10]
    anc = np.percentile(fg, PCT) if fg.size else 255.0
    sc = min(max(TARGET / max(anc, 1.0), 1.0), MAXSCALE)
    return np.clip(f * sc, 0, 255)


def apply_skin(f):
    hsv = np.asarray(Image.fromarray(f.astype("uint8"), "RGB").convert("HSV")).astype("int16")
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    hlo = int(SKIN["h_lo"] * 255 / 360); hhi = int(SKIN["h_hi"] * 255 / 360); smin = int(SKIN["s_min"] * 255)
    m = (H >= hlo) & (H <= hhi) & (S >= smin) & (V > 20)
    H[m] = int(SKIN["to_h"] * 255 / 360); S[m] = int(SKIN["to_s"] * 255)
    V[m] = np.clip(V[m] * SKIN["v_gain"], 0, 255)
    return np.asarray(Image.fromarray(np.stack([H, S, V], -1).astype("uint8"), "HSV").convert("RGB")).astype("float32")


for out, tmps in d["pairs"]:
    tmps = [t for t in tmps if os.path.exists(t)]
    if not tmps:
        continue
    if COMP and len(tmps) >= 2:
        # tmps[0]=base(身体真实色)  tmps[1]=emis(final 无灯=发光)
        base = np.asarray(Image.open(tmps[0]).convert("RGB")).astype("float32")
        emis = np.asarray(Image.open(tmps[1]).convert("RGB")).astype("float32")
        base = brighten(base)
        el = emis.max(2)
        m = el > float(COMP.get("thresh", 40))
        eg = np.clip(emis * float(COMP.get("gain", 1.2)), 0, 255)
        base[m] = np.maximum(base[m], eg[m])         # 发光处叠红 emissive
        f = base
    else:
        f = brighten(np.asarray(Image.open(tmps[0]).convert("RGB")).astype("float32"))
        if SKIN:
            f = apply_skin(f)
    Image.fromarray(np.clip(f, 0, 255).astype("uint8"), "RGB").save(out, optimize=True)
    for t in tmps:
        try:
            os.remove(t)
        except Exception:
            pass
