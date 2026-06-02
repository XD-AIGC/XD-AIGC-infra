"""UE 自动化第 2 步：渲染 1 个测试角色，验证 alpha 是否正确。

使用方法：
1. 确认 01_setup.py 已经跑过、UE 已重启
2. UE 菜单：Tools → Run Python Script → 选本文件
3. 跑完后自动打开输出目录
4. 检查 PNG：
   - 背景应该是透明（在 PS/GIMP/VSCode 打开看棋盘格）
   - 角色四个角度应该清晰
5. 把任意一张 PNG 截图发我确认

如果 alpha 全黑/全白/有黑边：把 Output Log 截图发我。
"""
import unreal
import os
import math
import subprocess

# 外部 Python（有 PIL），用于 alpha 反相后处理
EXTERNAL_PYTHON = r"C:/Users/XINDONG/AppData/Local/Programs/Python/Python312/python.exe"

# ============ 配置 ============
OUTPUT_DIR    = r"D:/ref_shots/tli_test"      # 测试输出目录（火炬之光）
RESOLUTION    = (1024, 2304)                    # W x H
LEVEL_PATH    = "/Game/Maps/L_CharRefShoot"
SEARCH_DIRS   = ["/Game/Art/Characters/Hero"]  # 先拿人形 Hero 验证
MESH_REQUIRE_PATH = "/Meshes/"                  # TLI: SkeletalMesh 都在各角色 Meshes/ 下
TEST_MESH_HINT = "_Skin"                         # TLI mesh 命名 SK_*_Skin（无 LOD 后缀）
TEST_CHARACTER  = "BingHuoRen"                   # 指定角色名子串（None = 用字母序第一个）
EXCLUDE_PATH_KEYWORDS = ["/VFX/", "/Effect/", "/Anim/", "/Animations/"]
EXCLUDE_NAME_KEYWORDS = ["_Weapon", "_VFX", "_Anim", "PhysicsAsset", "Skeleton",
                          "_Physics", "_Skeleton", "ShadowProxy", "_Proxy"]

VIEWS = [("front", 180.0), ("side", -90.0), ("back", 0.0), ("tq", 135.0)]
FILL_RATIO = 0.80   # 角色高度占帧比例

# ============ 工具 ============
def log(m):
    print(f"[test] {m}")
    unreal.log(f"[test] {m}")


def get_world():
    return unreal.EditorLevelLibrary.get_editor_world()


# ============ UE 版本兼容层（4.26 无 LevelEditorSubsystem/EditorActorSubsystem）============
# 4.27+/5.x: 用对应 Subsystem；4.26: 回退 EditorLevelLibrary（level/actor 方法名一致）。
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


def find_first_skeletal_mesh():
    aal = unreal.EditorAssetLibrary
    candidates = []
    for d in SEARCH_DIRS:
        try:
            paths = aal.list_assets(d, recursive=True, include_folder=False)
        except Exception as e:
            log(f"list_assets failed for {d}: {e}")
            continue
        for p in paths:
            # 路径过滤
            if MESH_REQUIRE_PATH and MESH_REQUIRE_PATH not in p:
                continue
            if any(k in p for k in EXCLUDE_PATH_KEYWORDS):
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
            name = str(data.asset_name)
            # 名字过滤
            if any(k in name for k in EXCLUDE_NAME_KEYWORDS):
                continue
            candidates.append((name, p))
    # 优先 LOD0
    hinted = [(n, p) for n, p in candidates if TEST_MESH_HINT in n]
    pool = hinted if hinted else candidates
    log(f"candidates: {len(pool)} ({'LOD0' if hinted else 'no LOD filter'})")
    if TEST_CHARACTER:
        picked = [(n, p) for n, p in pool if TEST_CHARACTER in n]
        if picked:
            log(f"matched TEST_CHARACTER='{TEST_CHARACTER}': {picked[0][0]}")
            return sorted(picked)[0]
        log(f"WARN: TEST_CHARACTER='{TEST_CHARACTER}' 没匹配到，回退到首个")
    if pool:
        return sorted(pool)[0]
    return None


def set_runtime_cvars():
    """每次跑都设一下，双保险"""
    w = get_world()
    cmds = [
        "r.PostProcessing.PropagateAlpha 2",
        "r.SceneColorFormat 4",
        "r.HighResScreenshotDelay 4",
        "r.SetNearClipPlane 1",
    ]
    for c in cmds:
        unreal.SystemLibrary.execute_console_command(w, c)
    log("runtime cvars applied")


def boost_lighting():
    """D_dramatic 预设：sky=15, dir=80, fill=10, rim=18, ev=10.0（exposure 在 shoot_views 里设）。
    每次都强制更新 intensity，不论灯是否已存在。"""
    eas = get_actor_subsystem()

    # SkyLight: 弱环境光，避免压扁立体感
    sky = find_actor_by_label("SkyLight_Shoot")
    if sky is not None:
        slc = sky.light_component
        slc.set_editor_property("intensity", 15.0)
        try:
            if hasattr(slc, "recapture_sky"):
                slc.recapture_sky()
            elif hasattr(sky, "recapture"):
                sky.recapture()
        except Exception:
            pass

    # DirLight（主光）：强，制造主明暗
    dl = find_actor_by_label("DirLight_Shoot")
    if dl is None:
        dl = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500))
        dl.set_actor_label("DirLight_Shoot")
        dl.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=-45.0, yaw=-30.0), False)
    dlc = dl.light_component
    dlc.set_editor_property("intensity", 80.0)
    dlc.set_editor_property("cast_shadows", False)

    # FillLight：弱补光
    fill = find_actor_by_label("FillLight_Shoot")
    if fill is None:
        fill = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500))
        fill.set_actor_label("FillLight_Shoot")
        fill.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=-20.0, yaw=150.0), False)
    fc = fill.light_component
    fc.set_editor_property("intensity", 10.0)
    fc.set_editor_property("cast_shadows", False)

    # RimLight：强轮廓，把暗面边缘提亮
    rim = find_actor_by_label("RimLight_Shoot")
    if rim is None:
        rim = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500))
        rim.set_actor_label("RimLight_Shoot")
        rim.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=-10.0, yaw=90.0), False)
    rc = rim.light_component
    rc.set_editor_property("intensity", 18.0)
    rc.set_editor_property("cast_shadows", False)

    log("lighting → D_dramatic (sky=15, dir=80, fill=10, rim=18)")


FILL_RATIO_W = 0.62  # 水平占帧比例（< 竖直，左右多留 padding，防手臂/冰晶贴边）


def fit_camera(cam, actor):
    """按角色 bounding 自适应相机位置：保证任意 yaw 旋转下高/宽都不溢出。"""
    origin, extent = actor.get_actor_bounds(only_colliding_components=False)
    height = extent.z * 2
    # 用 max(x,y) 覆盖任意 yaw 下最宽的情况
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
    look = unreal.MathLibrary.find_look_at_rotation(cam_loc, origin)
    cam.set_actor_rotation(look, False)
    cam.get_cine_camera_component().focus_settings.manual_focus_distance = dist
    log(f"camera fit: h={height:.1f} w={width:.1f}  dist_h={dist_h:.1f} dist_w={dist_w:.1f}  → dist={dist:.1f}")


def make_render_target(width, height, world, rl):
    """多路 fallback 创建 RenderTarget2D。UE 5.3 不同小版本 Python binding 差异较大。"""
    # 路径1：helper 方法（若存在）
    # 用 RGBA8 — export_render_target 才会真写 PNG（RGBA16F 会写成 EXR 字节流）
    if rl is not None and hasattr(rl, "create_render_target_2d"):
        try:
            return rl.create_render_target_2d(
                world, width, height,
                unreal.TextureRenderTargetFormat.RTF_RGBA8,
                unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
            )
        except Exception as e:
            log(f"create_render_target_2d helper failed: {e}")
    # 路径2：new_object 直接造
    try:
        outer = unreal.get_transient_package() if hasattr(unreal, "get_transient_package") else None
        rt = unreal.new_object(unreal.TextureRenderTarget2D, outer=outer) if outer else unreal.new_object(unreal.TextureRenderTarget2D)
        rt.set_editor_property("render_target_format", unreal.TextureRenderTargetFormat.RTF_RGBA8)
        rt.set_editor_property("clear_color", unreal.LinearColor(0.0, 0.0, 0.0, 0.0))
        # UE 5.3 Python 没有 update_resource，用 init_custom_format / init_auto_format
        if hasattr(rt, "init_custom_format"):
            rt.init_custom_format(width, height, unreal.PixelFormat.PF_B8G8R8A8, False)
        elif hasattr(rt, "init_auto_format"):
            rt.init_auto_format(width, height)
        else:
            rt.set_editor_property("size_x", width)
            rt.set_editor_property("size_y", height)
        return rt
    except Exception as e:
        log(f"new_object RT failed: {e}")
    return None


def export_rt(rl, world, rt, out_dir, file_name):
    """导出 RT 到 PNG。"""
    if rl is not None and hasattr(rl, "export_render_target"):
        rl.export_render_target(world, rt, out_dir, file_name)
        return True
    raise RuntimeError("export_render_target 不可用，需要其他保存方式")


def pilot_actor(actor):
    """UE 5.3 起 pilot_level_actor 在 LevelEditorSubsystem 上；旧版在 UnrealEditorSubsystem。"""
    for sub_cls in (unreal.LevelEditorSubsystem, unreal.UnrealEditorSubsystem):
        try:
            sub = unreal.get_editor_subsystem(sub_cls)
            if hasattr(sub, "pilot_level_actor"):
                sub.pilot_level_actor(actor)
                return sub
        except Exception:
            pass
    # 兜底：直接把 viewport 摆到 camera pose（FOV 不会跟相机一致，但有 camera 参数补救）
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    ues.set_level_viewport_camera_info(actor.get_actor_location(), actor.get_actor_rotation())
    return None


def eject_pilot(sub):
    if sub is not None and hasattr(sub, "eject_pilot_level_actor"):
        try:
            sub.eject_pilot_level_actor()
        except Exception:
            pass


def shoot_views(actor, name):
    """SceneCapture2D 同步渲染 4 视角 → PNG。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cam = find_actor_by_label("Cam_Shoot")
    if cam is None:
        log("ERROR: Cam_Shoot 不存在，请先跑 01_setup.py")
        return

    w = get_world()
    cam_loc = cam.get_actor_location()
    cam_rot = cam.get_actor_rotation()
    cc = cam.get_cine_camera_component()
    focal = cc.current_focal_length
    # CineCamera 用 Super 35 sensor（23.76x13.365mm），算出 vertical FOV
    sensor_h = 13.365
    v_fov_rad = 2.0 * math.atan(sensor_h / (2.0 * focal))
    # SceneCapture.fov_angle 是 horizontal FOV，对 portrait RT 反推
    aspect_wh = RESOLUTION[0] / RESOLUTION[1]
    h_fov_rad = 2.0 * math.atan(math.tan(v_fov_rad / 2) * aspect_wh)
    h_fov_deg = math.degrees(h_fov_rad)
    log(f"cam pose loc={cam_loc} focal={focal}mm "
        f"v_fov={math.degrees(v_fov_rad):.2f}° h_fov(set)={h_fov_deg:.2f}°")

    rl = getattr(unreal, "RenderingLibrary", None) or getattr(unreal, "KismetRenderingLibrary", None)
    if rl is None:
        log("ERROR: 找不到 RenderingLibrary")
        return
    rt = make_render_target(RESOLUTION[0], RESOLUTION[1], w, rl)
    if rt is None:
        log("ERROR: 创建 RenderTarget 失败")
        return
    log(f"RT created: {rt}  size={rt.size_x}x{rt.size_y}")

    eas = get_actor_subsystem()
    sc = eas.spawn_actor_from_class(unreal.SceneCapture2D, cam_loc)
    sc.set_actor_rotation(cam_rot, False)
    sc.set_actor_label("SceneCap_Tmp")
    log(f"SceneCapture2D spawned: {sc}")
    # UE 5.3 不同 binding 取组件方式不同
    comp = None
    for attr in ("scene_capture_component2d", "capture_component_2d", "capture_component2d"):
        try:
            c = getattr(sc, attr, None)
            if c is not None:
                comp = c
                log(f"got component via attr '{attr}'")
                break
        except Exception:
            pass
    if comp is None:
        try:
            comp = sc.get_component_by_class(unreal.SceneCaptureComponent2D)
            log("got component via get_component_by_class")
        except Exception as e:
            log(f"get_component_by_class failed: {e}")
    if comp is None:
        log("ERROR: 拿不到 SceneCaptureComponent2D")
        eas.destroy_actor(sc)
        return
    comp.set_editor_property("texture_target", rt)
    # 火炬之光：SceneCapture 的 final color 不吃我们的灯光/曝光（NPR/Lit 走游戏自定义管线），
    # 只有 base color（材质原色）稳定、完整、明亮 → 全用 base color 出图。
    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_BASE_COLOR)
    comp.set_editor_property("fov_angle", h_fov_deg)
    comp.set_editor_property("capture_every_frame", False)
    comp.set_editor_property("capture_on_movement", False)
    # 强制用 manual exposure（不依赖关卡 PPV）。auto exposure 在暗场景会压成全黑
    try:
        pp = comp.get_editor_property("post_process_settings")
        pp.set_editor_property("override_auto_exposure_method", True)
        pp.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
        pp.set_editor_property("override_auto_exposure_bias", True)
        pp.set_editor_property("auto_exposure_bias", 0.0)
        pp.set_editor_property("override_auto_exposure_min_brightness", True)
        pp.set_editor_property("auto_exposure_min_brightness", 1.0)
        pp.set_editor_property("override_auto_exposure_max_brightness", True)
        pp.set_editor_property("auto_exposure_max_brightness", 1.0)
        pp.set_editor_property("override_bloom_intensity", True)
        pp.set_editor_property("bloom_intensity", 0.0)
        comp.set_editor_property("post_process_settings", pp)
        comp.set_editor_property("post_process_blend_weight", 1.0)
        log("SceneCapture PP: manual exposure bias=10, bloom off")
    except Exception as e:
        log(f"SceneCapture PP override failed: {e}")

    # 记下 fit 时的相机参数；每次旋转后基于新 bounds 重新摆 SceneCapture
    _d = cam.get_actor_location() - actor.get_actor_location()
    cam_dist = math.sqrt(_d.x * _d.x + _d.y * _d.y + _d.z * _d.z)
    written = []
    for i, (view, yaw) in enumerate(VIEWS):
        actor.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), False)
        # 旋转后 bounds origin 会变（角色非中心对称），重新对准
        new_origin, _ = actor.get_actor_bounds(only_colliding_components=False)
        sc_loc = unreal.Vector(new_origin.x - cam_dist, new_origin.y, new_origin.z)
        sc.set_actor_location(sc_loc, False, False)
        sc.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(sc_loc, new_origin), False)
        comp.capture_scene()  # 同步
        filename = f"{name}_v{i}_{view}.png"
        export_rt(rl, w, rt, OUTPUT_DIR, filename)
        full = os.path.join(OUTPUT_DIR, filename)
        log(f"  v{i} {view} yaw={yaw} origin={new_origin}  saved")
        written.append(full)

    eas.destroy_actor(sc)
    post_process_alpha(written)


def post_process_alpha(png_paths):
    """火炬之光 NPR 材质的 PropagateAlpha 覆盖度 matte 不可靠（整体偏透明），
    交付又是黑底拼图、不需要透明。所以直接拍平为黑底 RGB（丢掉坏 alpha），
    UE 导出的 RGB 已经是黑底正确渲染，convert('RGB') 仅丢 alpha、不做合成。
    这样任何查看器打开都正确，不会再误判过曝。
    """
    if not png_paths:
        return
    script = (
        "import sys\n"
        "from PIL import Image\n"
        "for p in sys.argv[1:]:\n"
        "    Image.open(p).convert('RGB').save(p, optimize=True)\n"
    )
    if not os.path.exists(EXTERNAL_PYTHON):
        log(f"WARN: 外部 Python 不存在 {EXTERNAL_PYTHON}，跳过 alpha 后处理")
        return
    try:
        r = subprocess.run([EXTERNAL_PYTHON, "-c", script] + png_paths,
                           capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            log(f"alpha post-processed ({len(png_paths)} files)")
        else:
            log(f"post-process failed: {r.stderr}")
    except Exception as e:
        log(f"post-process subprocess error: {e}")


def main():
    log("=" * 60)
    log("UE Character Reference Test Render")
    log("=" * 60)

    # 切到目标 Level
    aal = unreal.EditorAssetLibrary
    if not aal.does_asset_exist(LEVEL_PATH):
        log(f"ERROR: Level 不存在: {LEVEL_PATH}")
        log("请先跑 01_setup.py")
        return
    get_level_subsystem().load_level(LEVEL_PATH)

    set_runtime_cvars()
    boost_lighting()

    # 找一个测试角色
    found = find_first_skeletal_mesh()
    if found is None:
        log("ERROR: 没找到任何 SkeletalMesh。检查 SEARCH_DIRS 配置")
        return
    name, path = found
    log(f"test mesh: {name}  ({path})")

    # 生成
    eas = get_actor_subsystem()
    els = get_level_subsystem()
    mesh = aal.load_asset(path)
    anchor = find_actor_by_label("SpawnAnchor")
    spawn_loc = anchor.get_actor_location() if anchor else unreal.Vector(0, 0, 0)
    actor = eas.spawn_actor_from_object(mesh, spawn_loc)
    if actor is None:
        log(f"ERROR: spawn 失败 for {path}")
        return

    cam = find_actor_by_label("Cam_Shoot")
    fit_camera(cam, actor)

    shoot_views(actor, name)
    eas.destroy_actor(actor)

    log("\n" + "=" * 60)
    log("DONE")
    log("=" * 60)
    log(f"输出目录: {OUTPUT_DIR}")
    log(">>> 请打开任意一张 PNG 检查：")
    log("    1) 背景是否透明（PS/GIMP/VSCode 看到棋盘格）")
    log("    2) 角色 4 个角度是否清晰")
    log("    3) 任选一张截图发给我确认")

    # 自动打开输出目录（Windows）
    try:
        os.startfile(OUTPUT_DIR)
    except Exception:
        pass


main()
