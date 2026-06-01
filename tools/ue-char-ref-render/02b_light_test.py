"""UE 灯光对照渲染：同一角色，5 组不同灯光参数 → 5 张 front 图。

使用方法：
1. UE 已启动并加载好项目
2. Tools → Run Python Script → 选本文件
3. 跑完会打开 D:/ref_shots/light_test/，里面 5 张图分别叫 A/B/C/D/E
4. 你看哪张最好，告诉我字母，我就把这组参数写回 02/03

每组参数都列在下面 PRESETS 里，可读可改。
"""
import unreal
import os
import math
import subprocess

# ============ 配置 ============
EXTERNAL_PYTHON = r"C:/Users/XINDONG/AppData/Local/Programs/Python/Python312/python.exe"
OUTPUT_DIR    = r"D:/ref_shots/light_test"
RESOLUTION    = (1024, 2304)
LEVEL_PATH    = "/Game/Maps/L_CharRefShoot"
TEST_CHARACTER = "Boy_Home_Crown"   # 名字子串匹配
SEARCH_DIRS    = ["/Game/ArtResources/Characters/Cst",
                  "/Game/ArtResources/Characters/Chr",
                  "/Game/ArtResources/Characters/Agt"]
FILL_RATIO    = 0.80


def find_test_mesh():
    aal = unreal.EditorAssetLibrary
    for d in SEARCH_DIRS:
        try:
            paths = aal.list_assets(d, recursive=True, include_folder=False)
        except Exception as e:
            print(f"[light_test] list_assets fail {d}: {e}")
            continue
        for p in paths:
            if TEST_CHARACTER not in p:
                continue
            if "_LOD0" not in p:
                continue
            data = aal.find_asset_data(p)
            cname = None
            try:
                cname = str(data.asset_class_path.asset_name)
            except Exception:
                try:
                    cname = str(data.asset_class)
                except Exception:
                    pass
            if cname != "SkeletalMesh":
                continue
            return p
    return None

# 第十三轮：诊断 Chr 角色衣服为什么变黑。5 个 probe：
#   A 当前 cst preset（baseline，复现 bug）
#   B 纯 base_color 捕获（看材质原色，跳过灯光/PP）
#   C 同光 EV=0（隔离 EV 影响）
#   D agt preset（看是否就是 unlit emissive）
#   E cst 光 + ACES（不 flatten，看 toe 是否能救回暗部）
PRESETS = [
    {"name": "A_cst_now",   "sky": 400, "dir": 1900, "fill": 0, "rim": 0,
     "dir_pitch": -30, "dir_yaw": -45,
     "ev": 14.0, "sat": 1.0, "temp": 6500, "capture": "ldr", "flatten": True,
     "note": "current cst preset (broken baseline)"},
    {"name": "B_base_only", "sky": 0, "dir": 0, "fill": 0, "rim": 0,
     "dir_pitch": -30, "dir_yaw": -45,
     "ev": 0.0, "sat": 1.0, "temp": 6500, "capture": "base", "flatten": False,
     "note": "raw base color (no lighting/PP)"},
    {"name": "C_cst_ev0",   "sky": 400, "dir": 1900, "fill": 0, "rim": 0,
     "dir_pitch": -30, "dir_yaw": -45,
     "ev": 0.0, "sat": 1.0, "temp": 6500, "capture": "ldr", "flatten": True,
     "note": "same lights, ev=0 (vs ev=14)"},
    {"name": "D_agt",       "sky": 0, "dir": 0, "fill": 0, "rim": 0,
     "dir_pitch": -30, "dir_yaw": -45,
     "ev": -1.0, "sat": 1.4, "temp": 6500, "capture": "ldr", "flatten": False,
     "shoulder": 0.50,
     "note": "agt preset (unlit emissive style)"},
    {"name": "E_cst_aces",  "sky": 400, "dir": 1900, "fill": 0, "rim": 0,
     "dir_pitch": -30, "dir_yaw": -45,
     "ev": 14.0, "sat": 1.0, "temp": 6500, "capture": "ldr", "flatten": False,
     "note": "cst lights but with ACES (no flatten, has toe)"},
]

# ============ 工具 ============
def log(m):
    print(f"[light_test] {m}")
    unreal.log(f"[light_test] {m}")


def get_world():
    return unreal.EditorLevelLibrary.get_editor_world()


def get_level_subsystem():
    return unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def get_actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


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
              "r.SetNearClipPlane 1"]:
        unreal.SystemLibrary.execute_console_command(w, c)


def neutralize_ppv():
    """01_setup 留下的 PPV_Shoot 把 min/max brightness 锁在 1.0，会盖掉
    SceneCapture 自己的 ev override。这里把它的曝光 override 全关掉。"""
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


def ensure_dir_light(intensity, pitch=-45.0, yaw=-30.0):
    """确保 DirLight_Shoot 存在，设亮度 + 方向。pitch/yaw 每次都重写。"""
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


def ensure_fill_light(intensity):
    eas = get_actor_subsystem()
    f = find_actor_by_label("FillLight_Shoot")
    if f is None:
        f = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500))
        f.set_actor_label("FillLight_Shoot")
        f.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=-20.0, yaw=150.0), False)
    c = f.light_component
    c.set_editor_property("intensity", float(intensity))
    c.set_editor_property("cast_shadows", False)


def ensure_rim_light(intensity):
    eas = get_actor_subsystem()
    r = find_actor_by_label("RimLight_Shoot")
    if r is None:
        r = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500))
        r.set_actor_label("RimLight_Shoot")
        r.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=-10.0, yaw=90.0), False)
    c = r.light_component
    c.set_editor_property("intensity", float(intensity))
    c.set_editor_property("cast_shadows", False)


def apply_preset(p):
    ensure_sky_light(p["sky"])
    ensure_dir_light(p["dir"], p.get("dir_pitch", -45.0), p.get("dir_yaw", -30.0))
    ensure_fill_light(p["fill"])
    ensure_rim_light(p["rim"])
    log(f"applied {p['name']}: sky={p['sky']} dir={p['dir']}(p={p.get('dir_pitch',-45)},y={p.get('dir_yaw',-30)}) fill={p['fill']} rim={p['rim']} ev={p['ev']} sat={p.get('sat',1.0)} temp={p.get('temp',6500)}  ({p['note']})")


def fit_camera(cam, actor):
    origin, extent = actor.get_actor_bounds(only_colliding_components=False)
    height = extent.z * 2
    width = max(extent.x, extent.y) * 2
    sensor_h = 13.365
    focal = cam.get_cine_camera_component().current_focal_length
    v_fov = 2.0 * math.atan(sensor_h / (2.0 * focal))
    aspect_wh = RESOLUTION[0] / RESOLUTION[1]
    h_fov = 2.0 * math.atan(math.tan(v_fov / 2.0) * aspect_wh)
    dist_h = (height / FILL_RATIO) / (2.0 * math.tan(v_fov / 2.0))
    dist_w = (width / FILL_RATIO) / (2.0 * math.tan(h_fov / 2.0))
    dist = max(dist_h, dist_w, 50.0)
    cam_loc = unreal.Vector(origin.x - dist, origin.y, origin.z)
    cam.set_actor_location(cam_loc, False, False)
    look = unreal.MathLibrary.find_look_at_rotation(cam_loc, origin)
    cam.set_actor_rotation(look, False)
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


def shoot_one(actor, cam, preset, output_path):
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
        log(f"ERROR: RT 创建失败 (preset={preset['name']})")
        return
    log(f"  RT ok: {rt.size_x}x{rt.size_y}")

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
    cap = preset.get("capture", "ldr")
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
        pp.set_editor_property("auto_exposure_bias", float(preset["ev"]))
        pp.set_editor_property("override_bloom_intensity", True)
        pp.set_editor_property("bloom_intensity", 0.0)
        # 饱和度（4-vector：RGB+luminance；只调 luminance 通道做整体降饱和）
        sat = float(preset.get("sat", 1.0))
        if sat != 1.0:
            pp.set_editor_property("override_color_saturation", True)
            pp.set_editor_property("color_saturation", unreal.Vector4(sat, sat, sat, 1.0))
        # 白平衡色温（K）
        temp = float(preset.get("temp", 6500))
        if temp != 6500:
            pp.set_editor_property("override_white_temp", True)
            pp.set_editor_property("white_temp", temp)
        # 关 ACES tonemapper：把 film curve 拉平，让 RGB 接近线性输出
        if preset.get("flatten", False):
            pp.set_editor_property("override_film_slope", True)
            pp.set_editor_property("film_slope", 1.0)
            pp.set_editor_property("override_film_toe", True)
            pp.set_editor_property("film_toe", 0.0)
            pp.set_editor_property("override_film_shoulder", True)
            pp.set_editor_property("film_shoulder", 0.0)
            pp.set_editor_property("override_film_black_clip", True)
            pp.set_editor_property("film_black_clip", 0.0)
            pp.set_editor_property("override_film_white_clip", True)
            pp.set_editor_property("film_white_clip", 1.0)
        else:
            # 单独覆盖 shoulder（高光压缩），其它 film 参数走默认
            sh = preset.get("shoulder")
            if sh is not None:
                pp.set_editor_property("override_film_shoulder", True)
                pp.set_editor_property("film_shoulder", float(sh))
            wc = preset.get("white_clip")
            if wc is not None:
                pp.set_editor_property("override_film_white_clip", True)
                pp.set_editor_property("film_white_clip", float(wc))
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
    comp.capture_scene()
    rl.export_render_target(w, rt, os.path.dirname(output_path), os.path.basename(output_path))
    eas.destroy_actor(sc)
    log(f"  saved → {output_path}")


def post_and_compose_grid(png_paths, row_labels, col_labels):
    """每张：反相 alpha + unpremultiply + 合成到白底；再拼成 ROWxCOL 网格 grid.png。
    png_paths 必须按 row-major 排列（先 row=0 的所有列，再 row=1...）。"""
    if not png_paths or not os.path.exists(EXTERNAL_PYTHON):
        log(f"WARN: 跳过后处理（外部 Python 缺失？{EXTERNAL_PYTHON}）")
        return
    rows = len(row_labels)
    cols = len(col_labels)
    if rows * cols != len(png_paths):
        log(f"WARN: grid {rows}x{cols} 与图片数 {len(png_paths)} 不符，按行序拼")
    py = (
        "import sys, os\n"
        "from PIL import Image, ImageDraw, ImageFont\n"
        "import numpy as np\n"
        "bg=(255,255,255)\n"
        "out_dir=sys.argv[1]\n"
        "rows=int(sys.argv[2])\n"
        "cols=int(sys.argv[3])\n"
        "row_labels=sys.argv[4].split('|')\n"
        "col_labels=sys.argv[5].split('|')\n"
        "paths=sys.argv[6:]\n"
        "ims=[]\n"
        "for p in paths:\n"
        "    arr=np.array(Image.open(p).convert('RGBA'))\n"
        "    a=255-arr[:,:,3]\n"
        "    if a.min()==a.max():\n"
        "        # 没有有效 alpha 信息（BASE_COLOR 等捕获模式），原样保留 RGB\n"
        "        rgb_out=arr[:,:,:3].astype(np.float32)\n"
        "    else:\n"
        "        af=a.astype(np.float32)/255.0\n"
        "        rgb=arr[:,:,:3].astype(np.float32)\n"
        "        m=af>0\n"
        "        rgb[m]=np.clip(rgb[m]/af[m][:,None],0,255)\n"
        "        rgb_out=rgb*af[:,:,None]+np.array(bg,dtype=np.float32)[None,None,:]*(1-af[:,:,None])\n"
        "    im=Image.fromarray(rgb_out.astype(np.uint8),'RGB')\n"
        "    im.save(p,optimize=True)\n"
        "    ims.append(im)\n"
        "w,h=ims[0].size\n"
        "scale=0.30\n"
        "cw,ch=int(w*scale),int(h*scale)\n"
        "row_pad=120\n"
        "col_pad=60\n"
        "tot_w=row_pad+cw*cols\n"
        "tot_h=col_pad+ch*rows\n"
        "stitched=Image.new('RGB',(tot_w,tot_h),bg)\n"
        "draw=ImageDraw.Draw(stitched)\n"
        "try: font=ImageFont.truetype('arial.ttf',32)\n"
        "except: font=ImageFont.load_default()\n"
        "for c,lab in enumerate(col_labels):\n"
        "    draw.text((row_pad+c*cw+8,8),lab,fill=(0,0,0),font=font)\n"
        "for r,lab in enumerate(row_labels):\n"
        "    draw.text((8,col_pad+r*ch+ch//2-16),lab,fill=(0,0,0),font=font)\n"
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
            [EXTERNAL_PYTHON, "-c", py, OUTPUT_DIR,
             str(rows), str(cols), "|".join(row_labels), "|".join(col_labels)] + png_paths,
            capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            log(f"grid ok ({len(png_paths)} files) — {r.stdout.strip()}")
        else:
            log(f"post-process FAIL: {r.stderr[:500]}")
    except Exception as e:
        log(f"post-process exception: {e}")


def main():
    log("=" * 60)
    log("Lighting Comparison Test")
    log("=" * 60)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    get_level_subsystem().load_level(LEVEL_PATH)
    set_runtime_cvars()
    neutralize_ppv()

    aal = unreal.EditorAssetLibrary
    mesh_path = find_test_mesh()
    if mesh_path is None:
        log(f"ERROR: 找不到含 '{TEST_CHARACTER}' 的 SkeletalMesh")
        return
    log(f"test mesh: {mesh_path}")
    mesh = aal.load_asset(mesh_path)

    eas = get_actor_subsystem()
    anchor = find_actor_by_label("SpawnAnchor")
    spawn_loc = anchor.get_actor_location() if anchor else unreal.Vector(0, 0, 0)
    actor = eas.spawn_actor_from_object(mesh, spawn_loc)
    cam = find_actor_by_label("Cam_Shoot")
    fit_camera(cam, actor)

    # 依次跑所有网格 cell
    written = []
    for i, p in enumerate(PRESETS):
        log(f"--- [{i+1}/{len(PRESETS)}] ---")
        apply_preset(p)
        out = os.path.join(OUTPUT_DIR, f"{p['name']}.png")
        shoot_one(actor, cam, p, out)
        if os.path.exists(out):
            written.append(out)

    eas.destroy_actor(actor)

    log("-" * 40)
    row_labels = ["probe"]
    col_labels = [p["name"] for p in PRESETS]
    post_and_compose_grid(written, row_labels, col_labels)

    log("\n" + "=" * 60)
    log("DONE")
    log("=" * 60)
    log(f"输出: {OUTPUT_DIR}")
    log(f"Chr 衣服变黑诊断：{len(PRESETS)} 个 probe 横排对比")
    log(">>> 看 B_base_only：衣服有色 = 材质 OK，是渲染问题；衣服仍黑 = 材质本身 base=0")
    log(">>> 看 D_agt：能正常显示 = Chr 也是 unlit emissive 体系")
    log(">>> 看 E_cst_aces：能正常显示 = flatten 把暗部压死了，换 ACES 即可")

    try:
        os.startfile(OUTPUT_DIR)
    except Exception:
        pass


main()
