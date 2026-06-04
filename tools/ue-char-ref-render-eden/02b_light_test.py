"""阶段 0 诊断：base vs final color 参数对比网格（多角色 × 多档方案）。

目的：eden 现在编辑器能正常打开了，重新验证当年"final color 糊白 / EV 失效"的结论，
为 03_batch 回归 final color 真实渲染定基准参数。

跑法（交互编辑器）：
1. open_editor.bat 打开 eden 编辑器 → 等完全加载 → 在左上 3D 视口点一下激活它。
2. Window → Developer Tools → Output Log，命令框输入：
   py "D:\\code\\ue_scripts_eth_ue4\\01_setup.py"      （只需第一次，建关卡/灯/相机）
   py "D:\\code\\ue_scripts_eth_ue4\\02b_light_test.py"
3. 跑完自动打开 OUTPUT_DIR，看 grid.png：
   - 行 = 6 个代表角色；列 = base 对照 / final 多档 EV / final 低灯 / Agt 发光档。
   - 重点看：final 是否糊白、EV 调高画面是否变化(EV 是否生效)、emissive 红角/眼睛/皮肤/NPR 描边是否随 final 出现。
4. 把结论告诉我（哪列最接近游戏内、EV 生不生效），我据此定 03 的 final preset。

每张只截 front 一个视角（诊断够用）。黑底 RGB（诊断看色，不做透明）。
"""
import unreal
import os
import math
import subprocess

# ============ 配置 ============
EXTERNAL_PYTHON = r"C:/Users/XINDONG/AppData/Local/Programs/Python/Python312/python.exe"
OUTPUT_DIR    = r"D:/角色识别数据/伊瑟_UE4_skintest"
RESOLUTION    = (1024, 2304)
LEVEL_PATH    = "/Game/Maps/L_CharRefShoot"
WARMUP        = 3   # 每张正式截图前空跑几次，驱动贴图/shader 就绪，防黑剪影/棋盘格

# 皮肤 sat 微调诊断：选用户反馈"太白"的浅肤角色 + 对照，扫 sat 找肤色不橙不白的甜点。
# 关键：本脚本后处理已与 03 成品一致(反相alpha+反预乘+温和提亮+灰底96合成)，所见即所得。
MESHES = [
    ("Chr_AgentM",        "/Game/ArtResources/Characters/Chr/Chr_AgentM/SK_Chr_AgentM_LOD0"),                       # 对照(sat1.0 OK)
    ("Chr_NPC_Aya",       "/Game/ArtResources/Characters/Chr/Chr_NPC_Aya/SK_Chr_NPC_Aya_LOD0"),                     # sat1.0 太白
    ("Chr_Ed_Blackgold",  "/Game/ArtResources/Characters/Chr/Chr_Girl_Home_Eveningdress/Eveningdress_Blackgold/SK_Chr_Girl_Home_Ed_Blackgold_Lod0"),  # 太白
    ("Cst_Nell",          "/Game/ArtResources/Characters/Cst/Cst_Nell/Cst_Nell_Const/SK_Cst_Nell_Const_LOD0"),      # 太白
    ("Cst_Experimenter41","/Game/ArtResources/Characters/Cst/Cst_Experimenter41/Cst_Experimenter41_Hollow/SK_Cst_Experimenter41_Hollow_LOD0"),  # 太白
    ("Chr_Sw_Blackpink",  "/Game/ArtResources/Characters/Chr/Chr_Girl_Home_Sw_Blackpink/Girl_Home_Sw_Blackpink/SK_Chr_Girl_Home_Sw_Blackpink_LOD0"),  # sat1.4 曾偏橙
]

# 方案列：定稿基准(无灯 final + ACES + shoulder0.5)，只扫 sat。sat1.4→橙、sat1.0→白，找中间。
_C = dict(fill=0, rim=0, dir_pitch=-30, dir_yaw=-45, sky=0, dir=0, ev=-1.0,
          flatten=False, shoulder=0.5, capture="ldr", temp=6500)
COLS = [
    {**_C, "name": "sat10", "sat": 1.0},   # 太白
    {**_C, "name": "sat11", "sat": 1.1},
    {**_C, "name": "sat12", "sat": 1.2},
    {**_C, "name": "sat13", "sat": 1.3},
    {**_C, "name": "sat14", "sat": 1.4},   # 太橙
]


# ============ 工具 ============
def log(m):
    print(f"[diag] {m}")
    unreal.log(f"[diag] {m}")


def get_world():
    return unreal.EditorLevelLibrary.get_editor_world()


# ============ UE 版本兼容层（4.26 无 LevelEditorSubsystem/EditorActorSubsystem）============
def get_level_subsystem():
    cls = getattr(unreal, "LevelEditorSubsystem", None)
    if cls is not None:
        try:
            return unreal.get_editor_subsystem(cls)
        except Exception:
            pass
    return unreal.EditorLevelLibrary


def get_actor_subsystem():
    cls = getattr(unreal, "EditorActorSubsystem", None)
    if cls is not None:
        try:
            return unreal.get_editor_subsystem(cls)
        except Exception:
            pass
    return unreal.EditorLevelLibrary


def find_actor_by_label(label):
    for a in get_actor_subsystem().get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    return None


def set_runtime_cvars():
    w = get_world()
    for c in ["r.PostProcessing.PropagateAlpha 2",
              "r.SceneColorFormat 4",
              "r.HighResScreenshotDelay 4",
              "r.SetNearClipPlane 1",
              # 防首帧黑剪影/棋盘格占位：强制贴图全量加载、关流式、同步编 shader
              "r.Streaming.FullyLoadUsedTextures 1",
              "r.Streaming.Boost 1",
              "r.TextureStreaming 0",
              "r.ShaderCompiler.AsyncCompiling 0"]:
        unreal.SystemLibrary.execute_console_command(w, c)


def neutralize_ppv():
    """01_setup 留的 PPV_Shoot 把 min/max brightness 锁 1.0，会盖掉 SceneCapture 的 ev override。
    清掉它的曝光 override，否则 EV 调不动（这正是当年误判'EV 失效'的嫌疑点之一）。"""
    ppv = find_actor_by_label("PPV_Shoot")
    if ppv is None:
        return
    s = ppv.settings
    for k in ("override_auto_exposure_min_brightness",
              "override_auto_exposure_max_brightness",
              "override_auto_exposure_bias",
              "override_auto_exposure_method"):
        try:
            s.set_editor_property(k, False)
        except Exception:
            pass
    log("PPV_Shoot exposure overrides cleared")


def ensure_dir_light(intensity, pitch=-30.0, yaw=-45.0):
    eas = get_actor_subsystem()
    dl = find_actor_by_label("DirLight_Shoot")
    if dl is None:
        dl = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500))
        dl.set_actor_label("DirLight_Shoot")
    dl.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=float(pitch), yaw=float(yaw)), False)
    c = dl.light_component
    c.set_editor_property("intensity", float(intensity))
    c.set_editor_property("cast_shadows", False)


def ensure_sky_light(intensity):
    eas = get_actor_subsystem()
    sl = find_actor_by_label("SkyLight_Shoot")
    if sl is None:
        sl = eas.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 500))
        sl.set_actor_label("SkyLight_Shoot")
    c = sl.light_component
    c.set_editor_property("intensity", float(intensity))
    c.set_editor_property("cast_shadows", False)
    try:
        if hasattr(c, "recapture_sky"):
            c.recapture_sky()
        elif hasattr(sl, "recapture"):
            sl.recapture()
    except Exception:
        pass


def ensure_extra_light(label, intensity, pitch, yaw):
    eas = get_actor_subsystem()
    x = find_actor_by_label(label)
    if x is None:
        x = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500))
        x.set_actor_label(label)
        x.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=float(pitch), yaw=float(yaw)), False)
    c = x.light_component
    c.set_editor_property("intensity", float(intensity))
    c.set_editor_property("cast_shadows", False)


def apply_lighting(col):
    ensure_sky_light(col.get("sky", 0))
    ensure_dir_light(col.get("dir", 0), col.get("dir_pitch", -30.0), col.get("dir_yaw", -45.0))
    ensure_extra_light("FillLight_Shoot", col.get("fill", 0), -20.0, 150.0)
    ensure_extra_light("RimLight_Shoot", col.get("rim", 0), -10.0, 90.0)


FILL_RATIO   = 0.80
FILL_RATIO_W = 0.88


def fit_camera(cam, actor):
    # 诊断用整体包围盒（含武器/翅膀等远伸件），同时验证"缺件"是否回来
    origin, extent = actor.get_actor_bounds(only_colliding_components=False)
    height = max(extent.z * 2, 50.0)
    width = max(extent.x, extent.y) * 2
    sensor_h = 13.365
    focal = cam.get_cine_camera_component().current_focal_length
    v_fov = 2.0 * math.atan(sensor_h / (2.0 * focal))
    aspect_wh = RESOLUTION[0] / RESOLUTION[1]
    h_fov = 2.0 * math.atan(math.tan(v_fov / 2.0) * aspect_wh)
    dist_h = (height / FILL_RATIO) / (2.0 * math.tan(v_fov / 2.0))
    dist_w = (width / FILL_RATIO_W) / (2.0 * math.tan(h_fov / 2.0))
    dist = max(dist_h, dist_w, 50.0)
    cam_loc = unreal.Vector(origin.x - dist, origin.y, origin.z)
    cam.set_actor_location(cam_loc, False, False)
    cam.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(cam_loc, origin), False)
    cam.get_cine_camera_component().focus_settings.manual_focus_distance = dist
    return dist


def make_rt(w, h, world, rl):
    if rl is not None and hasattr(rl, "create_render_target_2d"):
        try:
            return rl.create_render_target_2d(
                world, w, h,
                unreal.TextureRenderTargetFormat.RTF_RGBA8,
                unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
            )
        except Exception as e:
            log(f"create_render_target_2d failed: {e}")
    try:
        outer = unreal.get_transient_package() if hasattr(unreal, "get_transient_package") else None
        rt = unreal.new_object(unreal.TextureRenderTarget2D, outer=outer) if outer else unreal.new_object(unreal.TextureRenderTarget2D)
        rt.set_editor_property("render_target_format", unreal.TextureRenderTargetFormat.RTF_RGBA8)
        rt.set_editor_property("clear_color", unreal.LinearColor(0.0, 0.0, 0.0, 0.0))
        if hasattr(rt, "init_custom_format"):
            rt.init_custom_format(w, h, unreal.PixelFormat.PF_B8G8R8A8, False)
        elif hasattr(rt, "init_auto_format"):
            rt.init_auto_format(w, h)
        else:
            rt.set_editor_property("size_x", w)
            rt.set_editor_property("size_y", h)
        return rt
    except Exception as e:
        log(f"new_object RT failed: {e}")
    return None


def shoot_one(actor, cam, col, output_path):
    """对当前 actor（已 fit_camera）按一个 col 方案截 front 一张。"""
    w = get_world()
    cam_loc = cam.get_actor_location()
    cam_rot = cam.get_actor_rotation()
    cc = cam.get_cine_camera_component()
    focal = cc.current_focal_length
    sensor_h = 13.365
    v_fov_rad = 2.0 * math.atan(sensor_h / (2.0 * focal))
    aspect_wh = RESOLUTION[0] / RESOLUTION[1]
    h_fov_deg = math.degrees(2.0 * math.atan(math.tan(v_fov_rad / 2) * aspect_wh))

    rl = getattr(unreal, "RenderingLibrary", None) or getattr(unreal, "KismetRenderingLibrary", None)
    if rl is None:
        log("ERROR: 找不到 RenderingLibrary")
        return
    rt = make_rt(RESOLUTION[0], RESOLUTION[1], w, rl)
    if rt is None:
        log(f"ERROR: RT 创建失败 (col={col['name']})")
        return

    eas = get_actor_subsystem()
    sc = eas.spawn_actor_from_class(unreal.SceneCapture2D, cam_loc)
    sc.set_actor_rotation(cam_rot, False)
    sc.set_actor_label("SceneCap_Tmp")

    comp = None
    for attr in ("scene_capture_component2d", "capture_component_2d", "capture_component2d"):
        c = getattr(sc, attr, None)
        if c is not None:
            comp = c
            break
    if comp is None:
        comp = sc.get_component_by_class(unreal.SceneCaptureComponent2D)

    comp.set_editor_property("texture_target", rt)
    cap = col.get("capture", "ldr")
    if cap == "base":
        comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_BASE_COLOR)
    else:
        comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    comp.set_editor_property("fov_angle", h_fov_deg)
    comp.set_editor_property("capture_every_frame", False)
    comp.set_editor_property("capture_on_movement", False)
    try:
        pp = comp.get_editor_property("post_process_settings")
        pp.set_editor_property("override_auto_exposure_method", True)
        pp.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
        pp.set_editor_property("override_auto_exposure_bias", True)
        pp.set_editor_property("auto_exposure_bias", float(col["ev"]))
        pp.set_editor_property("override_bloom_intensity", True)
        pp.set_editor_property("bloom_intensity", 0.0)
        sat = float(col.get("sat", 1.0))
        if sat != 1.0:
            pp.set_editor_property("override_color_saturation", True)
            pp.set_editor_property("color_saturation", unreal.Vector4(sat, sat, sat, 1.0))
        temp = float(col.get("temp", 6500))
        if temp != 6500:
            pp.set_editor_property("override_white_temp", True)
            pp.set_editor_property("white_temp", temp)
        if col.get("flatten", False):
            for k, v in [("film_slope", 1.0), ("film_toe", 0.0), ("film_shoulder", 0.0),
                         ("film_black_clip", 0.0), ("film_white_clip", 1.0)]:
                pp.set_editor_property(f"override_{k}", True)
                pp.set_editor_property(k, v)
        else:
            sh = col.get("shoulder")
            if sh is not None:
                pp.set_editor_property("override_film_shoulder", True)
                pp.set_editor_property("film_shoulder", float(sh))
        comp.set_editor_property("post_process_settings", pp)
        comp.set_editor_property("post_process_blend_weight", 1.0)
    except Exception as e:
        log(f"PP override failed: {e}")

    # front 视角
    actor.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0), False)
    new_origin, _ = actor.get_actor_bounds(only_colliding_components=False)
    _d = cam_loc - actor.get_actor_location()
    cam_dist = math.sqrt(_d.x * _d.x + _d.y * _d.y + _d.z * _d.z)
    sc_loc = unreal.Vector(new_origin.x - cam_dist, new_origin.y, new_origin.z)
    sc.set_actor_location(sc_loc, False, False)
    sc.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(sc_loc, new_origin), False)
    for _ in range(WARMUP):           # 预热：空跑驱动贴图/shader 就绪
        comp.capture_scene()
    comp.capture_scene()
    rl.export_render_target(w, rt, os.path.dirname(output_path), os.path.basename(output_path))
    eas.destroy_actor(sc)


def post_and_compose_grid(png_paths, row_labels, col_labels):
    """每张直接用原始 RGB（黑底，诊断看色）；拼成 ROWxCOL 网格 grid.png（row-major）。"""
    if not png_paths or not os.path.exists(EXTERNAL_PYTHON):
        log(f"WARN: 跳过拼图（外部 Python 缺失？{EXTERNAL_PYTHON}）")
        return
    rows = len(row_labels)
    cols = len(col_labels)
    py = (
        "import sys, os\n"
        "from PIL import Image, ImageDraw, ImageFont\n"
        "import numpy as np\n"
        "out_dir=sys.argv[1]; rows=int(sys.argv[2]); cols=int(sys.argv[3])\n"
        "row_labels=sys.argv[4].split('|'); col_labels=sys.argv[5].split('|')\n"
        "paths=sys.argv[6:]\n"
        "GRAY=np.array([96,96,96],dtype='float32')\n"
        "ims=[]\n"
        "for p in paths:\n"
        "    arr=np.asarray(Image.open(p).convert('RGBA')).astype('float32')\n"  # 与 03 finalize 一致
        "    rgb=arr[...,:3].copy(); a=255.0-arr[...,3]; af=a/255.0\n"
        "    m=af>0.003\n"
        "    rgb[m]=np.clip(rgb[m]/af[m][:,None],0,255)\n"                       # 反预乘
        "    lum=rgb.max(axis=2); fg=lum[a>8]\n"
        "    anc=np.percentile(fg,45) if fg.size else 255.0\n"
        "    sc=min(max(135.0/max(anc,1.0),1.0),2.5)\n"                          # 温和提亮
        "    rgb=np.clip(rgb*sc,0,255)\n"
        "    comp=rgb*af[...,None]+GRAY[None,None,:]*(1.0-af[...,None])\n"        # 合成灰底96
        "    im=Image.fromarray(np.clip(comp,0,255).astype('uint8'),'RGB')\n"
        "    ims.append(im)\n"
        "w,h=ims[0].size\n"
        "scale=0.26\n"
        "cw,ch=int(w*scale),int(h*scale)\n"
        "row_pad=160; col_pad=44\n"
        "tot_w=row_pad+cw*cols; tot_h=col_pad+ch*rows\n"
        "stitched=Image.new('RGB',(tot_w,tot_h),(40,40,40))\n"
        "draw=ImageDraw.Draw(stitched)\n"
        "try: font=ImageFont.truetype('arial.ttf',26)\n"
        "except: font=ImageFont.load_default()\n"
        "for c,lab in enumerate(col_labels):\n"
        "    draw.text((row_pad+c*cw+8,8),lab,fill=(255,255,0),font=font)\n"
        "for r,lab in enumerate(row_labels):\n"
        "    draw.text((8,col_pad+r*ch+ch//2-12),lab,fill=(0,255,255),font=font)\n"
        "for r in range(rows):\n"
        "    for c in range(cols):\n"
        "        idx=r*cols+c\n"
        "        if idx<len(ims):\n"
        "            stitched.paste(ims[idx].resize((cw,ch)),(row_pad+c*cw,col_pad+r*ch))\n"
        "stitched.save(os.path.join(out_dir,'grid.png'))\n"
        "print(f'grid saved {tot_w}x{tot_h}')\n"
    )
    try:
        r = subprocess.run(
            [EXTERNAL_PYTHON, "-X", "utf8", "-c", py, OUTPUT_DIR,
             str(rows), str(cols), "|".join(row_labels), "|".join(col_labels)] + png_paths,
            capture_output=True, text=True, encoding="utf-8", timeout=180)
        if r.returncode == 0:
            log(f"grid ok ({len(png_paths)} files) — {r.stdout.strip()}")
        else:
            log(f"grid FAIL: {r.stderr[:500]}")
    except Exception as e:
        log(f"grid exception: {e}")


def main():
    log("=" * 60)
    log("阶段0 诊断：base vs final 参数对比网格")
    log("=" * 60)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    get_level_subsystem().load_level(LEVEL_PATH)
    set_runtime_cvars()
    neutralize_ppv()

    aal = unreal.EditorAssetLibrary
    eas = get_actor_subsystem()
    cam = find_actor_by_label("Cam_Shoot")
    if cam is None:
        log("ERROR: 没有 Cam_Shoot，请先跑 01_setup.py")
        return
    anchor = find_actor_by_label("SpawnAnchor")
    spawn_loc = anchor.get_actor_location() if anchor else unreal.Vector(0, 0, 0)

    written = []   # row-major：先 mesh0 的所有 col，再 mesh1 ...
    row_labels = []
    for mi, (mlabel, mpath) in enumerate(MESHES):
        if not aal.does_asset_exist(mpath):
            log(f"[{mi+1}/{len(MESHES)}] 缺资源，跳过: {mpath}")
            # 仍补齐占位，保证 grid 对齐
            row_labels.append(mlabel + "(missing)")
            for _ in COLS:
                written.append(None)
            continue
        log(f"[{mi+1}/{len(MESHES)}] {mlabel}")
        mesh = aal.load_asset(mpath)
        actor = eas.spawn_actor_from_object(mesh, spawn_loc)
        if actor is None:
            log(f"  spawn 失败: {mpath}")
            row_labels.append(mlabel + "(spawn-fail)")
            for _ in COLS:
                written.append(None)
            continue
        fit_camera(cam, actor)
        row_labels.append(mlabel)
        for col in COLS:
            apply_lighting(col)
            out = os.path.join(OUTPUT_DIR, f"{mlabel}__{col['name']}.png")
            try:
                shoot_one(actor, cam, col, out)
                written.append(out if os.path.exists(out) else None)
                log(f"    {col['name']:<9} → {'ok' if os.path.exists(out) else 'MISS'}")
            except Exception as e:
                log(f"    {col['name']} ERROR: {e}")
                written.append(None)
        eas.destroy_actor(actor)
        try:
            unreal.EditorAssetLibrary.unload_asset(mpath)
            unreal.SystemLibrary.collect_garbage()
        except Exception:
            pass

    col_labels = [c["name"] for c in COLS]
    # grid 拼接需要每格都有文件；用占位黑图补 None
    placeholder = os.path.join(OUTPUT_DIR, "_blank.png")
    if any(p is None for p in written):
        try:
            from_rl = getattr(unreal, "RenderingLibrary", None) or getattr(unreal, "KismetRenderingLibrary", None)
            blank_rt = make_rt(RESOLUTION[0], RESOLUTION[1], get_world(), from_rl)
            from_rl.export_render_target(get_world(), blank_rt, OUTPUT_DIR, "_blank.png")
        except Exception:
            placeholder = None
    grid_inputs = [p if p else placeholder for p in written]
    grid_inputs = [p for p in grid_inputs if p]
    if len(grid_inputs) == len(written):
        post_and_compose_grid(grid_inputs, row_labels, col_labels)
    else:
        log("WARN: 有缺图且无占位，单图已出但 grid 跳过；逐张看 OUTPUT_DIR")

    log("\n" + "=" * 60)
    log("DONE — 看 grid.png")
    log("=" * 60)
    log(f"输出: {OUTPUT_DIR}")
    log(">>> 灯光扫描：看 grid.png 哪列皮肤白皙自然(不橙)、衣服又不过曝糊白")
    log(">>> 列：noLight→dir300/700/1200/1900(方向光渐强)→sky600(纯天光验证)")
    try:
        os.startfile(OUTPUT_DIR)
    except Exception:
        pass


main()
