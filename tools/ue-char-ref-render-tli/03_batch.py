"""UE 自动化第 3 步：批量渲染所有角色（4 视角 × N 角色）。

⚠️ 只在 02_test.py 出图 alpha 正确后再跑！

使用方法：
1. UE 菜单：Tools → Run Python Script → 选本文件
2. 看 Output Log 进度
3. 跑完后输出在 OUTPUT_DIR
4. 把输出目录整个 scp 上传服务器，跑 vdb_build.py 即可

如果跑到一半挂了：脚本会跳过已有 PNG，重新跑会续传。
"""
import unreal
import os
import math
import time
import json
import traceback
import subprocess

EXTERNAL_PYTHON = r"C:/Users/XINDONG/AppData/Local/Programs/Python/Python312/python.exe"

# ============ 配置 ============
OUTPUT_DIR    = r"D:/角色识别数据/火炬之光_透明"      # 全量输出：RGBA 透明单图（中间产物，06_compose 再合成灰底；不覆盖原黑底 火炬之光/）
WHITELIST_OUTPUT_DIR = r"D:/ref_shots/tli_alpha_probe"   # WHITELIST 模式下使用（alpha 诊断）
RESOLUTION    = (1024, 2304)
# 灰底重渲：背景从黑 (0,0,0) 改为深灰 sRGB(96,96,96)。背景靠 base color 路的灰背景板提供
# （base color 不受光/不 tonemap，均匀精确）。此值是背景板材质 base color 的 linear 输入。
# 实测标定：0.117 → PNG≈64；按单点反推取 0.22 目标 96，小批保留分图后再精调。
BG_GRAY_LINEAR = 0.22
LEVEL_PATH    = "/Game/Maps/L_CharRefShoot"
SEARCH_DIRS   = ["/Game/Art/Characters", "/Game/Art/Fashion/Heros"]  # 两个目标目录，镜像输出
MESH_REQUIRE_PATH = "/Meshes/"                       # TLI: SkeletalMesh 都在各角色 Meshes/ 下
NAME_FILTER   = ""                                   # 空 = 不按名字过滤，全部 SkeletalMesh 都渲
EXCLUDE_PATH_KEYWORDS = ["/VFX/", "/Effect/", "/Anim/", "/Animations/"]
EXCLUDE_NAME_KEYWORDS = ["_Weapon", "_VFX", "_Anim", "_Skill", "PhysicsAsset", "Skeleton",
                          "_Physics", "_Skeleton", "ShadowProxy", "_Proxy"]
# LOD 策略：有 _LOD0 就只要 _LOD0；完全没有 _LOD 后缀的（单 LOD mesh）也渲

# 已知会让 UE crash 的 mesh 子串（spawn/bounds 时 array OOB / LOD reduction assert），直接跳过
# 加进来的角色不会被渲染。修复了 mesh 后可以删掉。
BAD_MESH_SUBSTRINGS = [
    # 跑全量时若某 mesh 让 UE crash，把名字子串加进来跳过，再重跑续传
]

# 测试白名单：如果非空，只渲染列表里的 mesh path 输出到 preview19/；为空则跑全部到 full/。
# Preview19 名单保留在下方，要切回小批测试只需把 WHITELIST_MESH_PATHS 改成 = _PREVIEW19_PATHS
_TLI_TEST_PATHS = [
    "/Game/Art/Characters/Hero/BingHuoRen/Meshes/SK_BingHuoRen2_Skin",
    "/Game/Art/Characters/Pet/R_AWuAWu/Meshes/SK_R_AWuAWu_Skin",
    "/Game/Art/Characters/Monster/AiRenDiLei/Meshes/SK_AiRenDiLei_Skin",
    "/Game/Art/Characters/Token/FaShuJiuChan/Meshes/SK_FaShuJiuChan_Skin",
    "/Game/Art/Characters/NPC/ABaABa/Meshes/SK_ABaABa_Skin",
    "/Game/Art/Fashion/Heros/Hero/C_BingHuoRen_001/Meshes/SK_C_BingHuoRen_001_Skin",
]
_TLI_MIX_TEST = [
    "/Game/Art/Characters/Hero/MaoNv/Meshes/SK_MaoNv2_Skin",          # NPR→final
    "/Game/Art/Characters/Hero/NanFaShi/Meshes/SK_NanFaShi2_Skin",    # NPR→final
    "/Game/Art/Characters/Hero/YeManRen/Meshes/SK_YeManRen2_Skin",    # NPR→final
    "/Game/Art/Characters/Monster/AiRenDiLei/Meshes/SK_AiRenDiLei_Skin",  # Lit→base
    "/Game/Art/Characters/Pet/R_AWuAWu/Meshes/SK_R_AWuAWu_Skin",          # Lit→base
    "/Game/Art/Characters/Token/FaShuJiuChan/Meshes/SK_FaShuJiuChan_Skin", # Lit→base
    "/Game/Art/Fashion/Heros/Hero/C_BingHuoRen_001/Meshes/SK_C_BingHuoRen_001_Skin",  # NPR→final
]
_TLI_BLACK_TEST = [
    "/Game/Art/Characters/Monster/AiRenHuoQiangShou/Meshes/SK_AiRenHuoQiangShou_Skin",
    "/Game/Art/Characters/Monster/AiRenTouDanShou/Meshes/SK_AiRenTouDanShou_Skin",
    "/Game/Art/Characters/Monster/GaoYuanXiYi/Meshes/SK_GaoYuanXiYi_Skin",
    "/Game/Art/Characters/Monster/Boss/ChuanSuoZhe/Meshes/SK_ChuanSuoZheZheXue_Skin",
]
# alpha 诊断：先渲 3 个代表角色（Lit 怪物 / NPR 英雄 / 时装），保留每路原始 RGBA，
# 分析 alpha matte 质量后再定最终合成方案。全量时改回 []。
_TLI_ALPHA_PROBE = [
    "/Game/Art/Characters/Monster/AiRenDiLei/Meshes/SK_AiRenDiLei_Skin",          # Lit 怪物
    "/Game/Art/Characters/Hero/MaoNv/Meshes/SK_MaoNv2_Skin",                      # NPR 英雄
    "/Game/Art/Fashion/Heros/Hero/C_BingHuoRen_001/Meshes/SK_C_BingHuoRen_001_Skin",  # 时装 NPR
]
WHITELIST_MESH_PATHS = []  # 全量（小批验证时改成 _TLI_ALPHA_PROBE 等）

# alpha 诊断期：关掉背景板，背景渲透明（clear_color=0），保留各路原始 RGBA 看 matte
USE_BG_PLANE = False

VIEWS = [("front", 180.0), ("side", -90.0), ("back", 0.0), ("tq", 135.0)]
FILL_RATIO = 0.80
SKIP_EXISTING = True   # 全量续传（中途 crash 重跑自动跳过已完成的 mesh）
KEEP_TMP = False       # 全量：合成后删除 base/final 临时分图
# alpha 提纯双阈值：coverage<=LOW 透明、>=HIGH 拉满实心、中间窄羽化。
# 实测：背景 cov 几乎都 <=2，半透纱裙/白裤 cov 中位 6-8、最低 ~3 → LOW=2/HIGH=4 既让半透材质实心又不脏背景。
ALPHA_LOW = 2.0
ALPHA_HIGH = 4.0
WARMUP_CAPTURES = 3    # 每个 mesh 截图前空跑几次预热（驱动贴图/shader 就绪，防黑剪影）

# ============ 按角色目录分组的渲染预设 ============
# Cst 走原 side45 + 高 EV + flat tonemap（cel-shader lit 材质）
# Agt 是 Unlit emissive，纯靠 PP（无灯 + 低 EV + aces shoulder）调色
# 火炬之光角色为普通 Lit（PBR/卡通）材质，单一预设起步；参数待 02_test/02b 标定后回填。
PRESETS = {
    "default": {  # NPR 英雄基本不吃灯/曝光；怪物类为 Lit，给适中灯光 + 锁定曝光
        "sky": 3, "dir": 10, "dir_pitch": -45, "dir_yaw": -30,
        "ev": 0.0, "sat": 1.0, "flatten": False,
    },
}


def preset_for_mesh(mesh_path):
    # TLI 暂用单一预设；若后续按体型（人形/四足）分组，可在此加分支
    return PRESETS["default"]


# NPR 英雄/时装走 final color（自发光），其余 Lit 走 base color
NPR_PATH_KEYWORDS = ("/Hero/", "/Hero_Showcase/", "/Hero_PC/", "/Hero_Showcase_PC/", "/Fashion/")


def capture_source_for_mesh(mesh_path):
    if any(k in mesh_path for k in NPR_PATH_KEYWORDS):
        return unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
    return unreal.SceneCaptureSource.SCS_BASE_COLOR

# ============ 工具 ============
def log(m):
    print(f"[batch] {m}")
    unreal.log(f"[batch] {m}")


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


def mesh_to_output_dir(mesh_path):
    """把 UE 虚拟路径映射到磁盘镜像目录。
    /Game/ArtResources/Characters/Cst/.../SK_Cst_Dolores_Const_LOD0
      → <OUTPUT_DIR>/ArtResources/Characters/Cst/.../SK_Cst_Dolores_Const_LOD0/
    """
    rel = mesh_path.lstrip("/")
    if rel.startswith("Game/"):
        rel = rel[5:]
    return os.path.join(OUTPUT_DIR, rel.replace("/", os.sep))


def collect_meshes():
    aal = unreal.EditorAssetLibrary
    # 白名单优先：测试阶段只跑指定列表
    if WHITELIST_MESH_PATHS:
        result = []
        for p in WHITELIST_MESH_PATHS:
            if not aal.does_asset_exist(p):
                log(f"WHITELIST 缺资源: {p}")
                continue
            data = aal.find_asset_data(p)
            name = str(data.asset_name)
            if any(b in name for b in BAD_MESH_SUBSTRINGS):
                log(f"WHITELIST 跳过 BAD: {name}")
                continue
            result.append((name, p))
        log(f"WHITELIST mode: {len(result)} meshes")
        return sorted(set(result), key=lambda x: x[0])
    result = []
    for d in SEARCH_DIRS:
        try:
            paths = aal.list_assets(d, recursive=True, include_folder=False)
        except Exception as e:
            log(f"list_assets failed for {d}: {e}")
            continue
        for p in paths:
            # 路径过滤：只收 Meshes/ 下的
            if MESH_REQUIRE_PATH and MESH_REQUIRE_PATH not in p:
                continue
            if any(k in p for k in EXCLUDE_PATH_KEYWORDS):
                continue
            data = aal.find_asset_data(p)
            try:
                cname = str(data.asset_class_path.asset_name)
            except Exception:
                cname = str(getattr(data, "asset_class", ""))
            if cname != "SkeletalMesh":
                continue
            name = str(data.asset_name)
            # 名字过滤
            if NAME_FILTER and NAME_FILTER not in name:
                continue
            if any(k in name for k in EXCLUDE_NAME_KEYWORDS):
                continue
            # LOD 策略：有 _LOD0 → 收；_LOD1/2/3 → 跳过；完全没 _LOD → 收（单 LOD）
            if "_LOD" in name and "_LOD0" not in name:
                continue
            if any(b in name for b in BAD_MESH_SUBSTRINGS):
                log(f"  skip BAD mesh: {name}")
                continue
            result.append((name, p))
    # dedup + sort
    result = sorted(set(result), key=lambda x: x[0])
    return result


def set_runtime_cvars():
    w = unreal.EditorLevelLibrary.get_editor_world()
    for c in [
        "r.PostProcessing.PropagateAlpha 2",
        "r.SceneColorFormat 4",
        "r.HighResScreenshotDelay 4",
        # 防「首次渲染黑剪影」：强制贴图全量加载（base color 取 albedo 贴图，没加载完会黑）
        "r.Streaming.FullyLoadUsedTextures 1",
        "r.Streaming.Boost 1",
        "r.TextureStreaming 0",  # 关流式：贴图加载即满载，根治「首帧黑剪影」
        # 尽量同步 shader 编译，避免截图时 shader 没就绪
        "r.ShaderCompiler.AsyncCompiling 0",
    ]:
        unreal.SystemLibrary.execute_console_command(w, c)


def neutralize_ppv():
    """01_setup 留的 PPV_Shoot 把 min/max brightness 锁 1.0，会盖掉 SceneCapture 自己的
    ev override。这里清掉它的曝光 override，否则 Agt 的低 EV 渲不出来。"""
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


def ensure_lights_exist():
    """首次调用时把 Sky/Dir/Fill/Rim 灯都建好。强度后续按 preset 改。"""
    eas = get_actor_subsystem()
    if find_actor_by_label("SkyLight_Shoot") is None:
        sl = eas.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 500))
        sl.set_actor_label("SkyLight_Shoot")
    if find_actor_by_label("DirLight_Shoot") is None:
        dl = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500))
        dl.set_actor_label("DirLight_Shoot")
    for label, pitch, yaw in [("FillLight_Shoot", -20.0, 150.0),
                              ("RimLight_Shoot",  -10.0,  90.0)]:
        if find_actor_by_label(label) is None:
            x = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500))
            x.set_actor_label(label)
            x.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw), False)
            x.light_component.set_editor_property("intensity", 0.0)
            x.light_component.set_editor_property("cast_shadows", False)


_LAST_LIGHTING_KEY = [None]


def apply_lighting(preset):
    """按 preset 设 Sky + Dir 强度/方向。Fill/Rim 始终 0。同一 preset 连续多次时跳过。"""
    key = (preset.get("sky"), preset.get("dir"),
           preset.get("dir_pitch"), preset.get("dir_yaw"))
    if _LAST_LIGHTING_KEY[0] == key:
        return
    sky = find_actor_by_label("SkyLight_Shoot")
    if sky is not None:
        slc = sky.light_component
        slc.set_editor_property("intensity", float(preset.get("sky", 0)))
        slc.set_editor_property("cast_shadows", False)
        try:
            if hasattr(slc, "recapture_sky"):
                slc.recapture_sky()
            elif hasattr(sky, "recapture"):
                sky.recapture()
        except Exception:
            pass
    dl = find_actor_by_label("DirLight_Shoot")
    if dl is not None:
        dl.set_actor_rotation(unreal.Rotator(
            roll=0.0,
            pitch=float(preset.get("dir_pitch", -30)),
            yaw=float(preset.get("dir_yaw", -45))), False)
        dlc = dl.light_component
        dlc.set_editor_property("intensity", float(preset.get("dir", 0)))
        dlc.set_editor_property("cast_shadows", False)
    _LAST_LIGHTING_KEY[0] = key
    log(f"lighting → sky={preset.get('sky')} dir={preset.get('dir')} "
        f"(p={preset.get('dir_pitch')},y={preset.get('dir_yaw')})")


def make_render_target(width, height, world, rl):
    if rl is not None and hasattr(rl, "create_render_target_2d"):
        try:
            return rl.create_render_target_2d(
                world, width, height,
                unreal.TextureRenderTargetFormat.RTF_RGBA8,
                unreal.LinearColor(0.0, 0.0, 0.0, 0.0),
            )
        except Exception as e:
            log(f"create_render_target_2d helper failed: {e}")
    try:
        outer = unreal.get_transient_package() if hasattr(unreal, "get_transient_package") else None
        rt = unreal.new_object(unreal.TextureRenderTarget2D, outer=outer) if outer else unreal.new_object(unreal.TextureRenderTarget2D)
        rt.set_editor_property("render_target_format", unreal.TextureRenderTargetFormat.RTF_RGBA8)
        rt.set_editor_property("clear_color", unreal.LinearColor(0.0, 0.0, 0.0, 0.0))
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
    if rl is not None and hasattr(rl, "export_render_target"):
        rl.export_render_target(world, rt, out_dir, file_name)
        return True
    raise RuntimeError("export_render_target 不可用")


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
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    ues.set_level_viewport_camera_info(actor.get_actor_location(), actor.get_actor_rotation())
    return None


def eject_pilot(sub):
    if sub is not None and hasattr(sub, "eject_pilot_level_actor"):
        try:
            sub.eject_pilot_level_actor()
        except Exception:
            pass


FILL_RATIO_W = 0.62  # 水平占帧比例（< 竖直，左右多留 padding，防手臂/冰晶贴边）


def fit_camera(cam, actor):
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
    look = unreal.MathLibrary.find_look_at_rotation(cam_loc, origin)
    cam.set_actor_rotation(look, False)
    cam.get_cine_camera_component().focus_settings.manual_focus_distance = dist


_SC_STATE = {"rt": None, "sc": None, "comp": None}
_LAST_PP_KEY = [None]


def get_or_create_capture(cam):
    """复用同一个 SceneCapture2D + RenderTarget（批量时避免反复创建）。
    PP 不在这里设，由 apply_capture_pp 按 preset 改。"""
    if _SC_STATE["sc"] is not None:
        return _SC_STATE["comp"], _SC_STATE["rt"]
    w = unreal.EditorLevelLibrary.get_editor_world()
    cc = cam.get_cine_camera_component()
    focal = cc.current_focal_length
    sensor_h = 13.365
    v_fov_rad = 2.0 * math.atan(sensor_h / (2.0 * focal))
    aspect_wh = RESOLUTION[0] / RESOLUTION[1]
    h_fov_rad = 2.0 * math.atan(math.tan(v_fov_rad / 2) * aspect_wh)
    h_fov_deg = math.degrees(h_fov_rad)
    rl = getattr(unreal, "RenderingLibrary", None) or getattr(unreal, "KismetRenderingLibrary", None)
    _SC_STATE["rl"] = rl
    rt = make_render_target(RESOLUTION[0], RESOLUTION[1], w, rl)
    if rt is None:
        raise RuntimeError("创建 RenderTarget 失败")
    eas = get_actor_subsystem()
    sc = eas.spawn_actor_from_class(unreal.SceneCapture2D, cam.get_actor_location())
    sc.set_actor_label("SceneCap_Batch")
    comp = None
    for attr in ("scene_capture_component2d", "capture_component_2d", "capture_component2d"):
        c = getattr(sc, attr, None)
        if c is not None:
            comp = c
            break
    if comp is None:
        comp = sc.get_component_by_class(unreal.SceneCaptureComponent2D)
    if comp is None:
        raise RuntimeError("拿不到 SceneCaptureComponent2D")
    comp.set_editor_property("texture_target", rt)
    # 火炬之光：final color 不吃灯光/曝光，只有 base color 稳定完整 → 全用 base color
    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_BASE_COLOR)
    comp.set_editor_property("fov_angle", h_fov_deg)
    comp.set_editor_property("capture_every_frame", False)
    comp.set_editor_property("capture_on_movement", False)
    _SC_STATE["rt"] = rt
    _SC_STATE["sc"] = sc
    _SC_STATE["comp"] = comp
    log(f"SceneCapture init: focal={focal}mm h_fov={h_fov_deg:.2f}°")
    return comp, rt


def apply_capture_pp(comp, preset):
    """每个 mesh 渲染前按 preset 改 PP。preset 没变就跳过。"""
    key = (preset.get("ev"), preset.get("sat"), preset.get("flatten"), preset.get("shoulder"))
    if _LAST_PP_KEY[0] == key:
        return
    try:
        pp = comp.get_editor_property("post_process_settings")
        # 曝光
        pp.set_editor_property("override_auto_exposure_method", True)
        pp.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
        pp.set_editor_property("override_auto_exposure_bias", True)
        pp.set_editor_property("auto_exposure_bias", float(preset["ev"]))
        pp.set_editor_property("override_auto_exposure_min_brightness", True)
        pp.set_editor_property("auto_exposure_min_brightness", 1.0)
        pp.set_editor_property("override_auto_exposure_max_brightness", True)
        pp.set_editor_property("auto_exposure_max_brightness", 1.0)
        pp.set_editor_property("override_bloom_intensity", True)
        pp.set_editor_property("bloom_intensity", 0.0)
        # 饱和度
        sat = float(preset.get("sat", 1.0))
        if sat != 1.0:
            pp.set_editor_property("override_color_saturation", True)
            pp.set_editor_property("color_saturation", unreal.Vector4(sat, sat, sat, 1.0))
        else:
            pp.set_editor_property("override_color_saturation", False)
        # Film curve
        if preset.get("flatten", False):
            for k, v in [("film_slope", 1.0), ("film_toe", 0.0),
                         ("film_shoulder", 0.0),
                         ("film_black_clip", 0.0), ("film_white_clip", 1.0)]:
                pp.set_editor_property(f"override_{k}", True)
                pp.set_editor_property(k, v)
        else:
            # ACES 走默认，只在 preset 指定时覆盖 shoulder
            for k in ("film_slope", "film_toe", "film_black_clip", "film_white_clip"):
                pp.set_editor_property(f"override_{k}", False)
            sh = preset.get("shoulder")
            if sh is not None:
                pp.set_editor_property("override_film_shoulder", True)
                pp.set_editor_property("film_shoulder", float(sh))
            else:
                pp.set_editor_property("override_film_shoulder", False)
        comp.set_editor_property("post_process_settings", pp)
        comp.set_editor_property("post_process_blend_weight", 1.0)
        _LAST_PP_KEY[0] = key
        log(f"PP → ev={preset['ev']} sat={sat} flatten={preset.get('flatten')} "
            f"shoulder={preset.get('shoulder')}")
    except Exception as e:
        log(f"apply_capture_pp failed: {e}")


# ============ 灰背景板 ============
# base color / final color LDR 两路的「无几何」像素都不吃 RenderTarget 的 clear_color
# （实测背景恒为 0/黑）。所以放一块实体 Lit 灰板当背景：base color 路直接读到板的
# base color = 灰；combine_max 取 max 后背景=灰，角色与边缘抗锯齿零损失。
_BG_STATE = {"plane": None, "mat": None}


def _make_gray_bg_material():
    aal = unreal.EditorAssetLibrary
    mat_path = "/Game/_CharRef/M_CharRefGrayBG"
    if aal.does_asset_exist(mat_path):
        return aal.load_asset(mat_path)
    try:
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_CharRefGrayBG", "/Game/_CharRef", unreal.Material, unreal.MaterialFactoryNew())
        mat.set_editor_property("two_sided", True)  # 双面，免背面剔除朝向问题
        node = unreal.MaterialEditingLibrary.create_material_expression(
            mat, unreal.MaterialExpressionConstant3Vector)
        node.set_editor_property("constant", unreal.LinearColor(
            BG_GRAY_LINEAR, BG_GRAY_LINEAR, BG_GRAY_LINEAR, 1.0))
        unreal.MaterialEditingLibrary.connect_material_property(
            node, "", unreal.MaterialProperty.MP_BASE_COLOR)
        unreal.MaterialEditingLibrary.recompile_material(mat)
        aal.save_asset(mat_path)
        log(f"gray bg material created: base_color_linear={BG_GRAY_LINEAR}")
        return mat
    except Exception as e:
        log(f"make gray bg material failed: {e}")
        return None


def get_or_create_bg_plane():
    if not USE_BG_PLANE:
        return None
    if _BG_STATE["plane"] is not None:
        return _BG_STATE["plane"]
    eas = get_actor_subsystem()
    if _BG_STATE["mat"] is None:
        _BG_STATE["mat"] = _make_gray_bg_material()
    plane_mesh = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Plane")
    if plane_mesh is None:
        log("WARN: /Engine/BasicShapes/Plane 不存在，背景板跳过")
        return None
    plane = eas.spawn_actor_from_object(plane_mesh, unreal.Vector(0, 0, 0))
    plane.set_actor_label("CharRef_BGPlane")
    plane.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=90.0, yaw=0.0), False)  # 竖直，正对相机(-X)
    plane.set_actor_scale3d(unreal.Vector(500.0, 500.0, 1.0))  # 100×500 = 5万单位，必覆盖视野
    mat = _BG_STATE["mat"]
    try:
        smc = plane.static_mesh_component
        if mat is not None:
            smc.set_material(0, mat)
        smc.set_editor_property("cast_shadow", False)  # 背景板不投阴影
    except Exception as e:
        log(f"bg plane component setup failed: {e}")
    _BG_STATE["plane"] = plane
    log("bg plane spawned")
    return plane


def place_bg_plane(plane, origin, cam_dist):
    """把背景板摆到角色后方(+X)、竖直正对相机，距离足够远不穿模。"""
    if plane is None:
        return
    plane.set_actor_location(
        unreal.Vector(origin.x + cam_dist * 2.0, origin.y, origin.z), False, False)


def cleanup_capture():
    if _SC_STATE["sc"] is not None:
        try:
            get_actor_subsystem().destroy_actor(_SC_STATE["sc"])
        except Exception:
            pass
    _SC_STATE["rt"] = None
    _SC_STATE["sc"] = None
    _SC_STATE["comp"] = None
    if _BG_STATE["plane"] is not None:
        try:
            get_actor_subsystem().destroy_actor(_BG_STATE["plane"])
        except Exception:
            pass
    _BG_STATE["plane"] = None


def shoot_one(mesh_path, mesh_name):
    """渲染一个角色的 4 视角。输出目录镜像 UE 路径。返回 (status, label, failed_views)"""
    mesh_dir = mesh_to_output_dir(mesh_path)
    label = mesh_name  # 完整 mesh 名做 log，不再做命名清洗
    out_paths = [
        os.path.join(mesh_dir, f"v{i}_{view}.png")
        for i, (view, _) in enumerate(VIEWS)
    ]
    if SKIP_EXISTING and all(os.path.exists(p) for p in out_paths):
        return ("skip", label, [])
    os.makedirs(mesh_dir, exist_ok=True)

    aal = unreal.EditorAssetLibrary
    eas = get_actor_subsystem()

    mesh = aal.load_asset(mesh_path)
    if mesh is None:
        return ("fail", label, ["load_asset"])

    # 等 mesh 异步编译完，否则 spawn → get_actor_bounds 会读到未初始化数据 → C++ assert crash
    # UE 5.3 Python: AssetCompilingManager 不是 unreal 顶层模块，需要这样取
    try:
        acm_cls = getattr(unreal, "AssetCompilingManager", None)
        acm = acm_cls.get() if acm_cls else None
        if acm is None:
            # fallback: console command 触发 finish all
            unreal.SystemLibrary.execute_console_command(
                unreal.EditorLevelLibrary.get_editor_world(),
                "AssetManager.AssetAuditUI 0")
        else:
            if hasattr(acm, "finish_compilation_for_objects"):
                acm.finish_compilation_for_objects([mesh])
            elif hasattr(acm, "finish_all_compilation"):
                acm.finish_all_compilation()
    except Exception as e:
        log(f"  wait-compile skipped: {e}")

    anchor = find_actor_by_label("SpawnAnchor")
    spawn_loc = anchor.get_actor_location() if anchor else unreal.Vector(0, 0, 0)
    actor = eas.spawn_actor_from_object(mesh, spawn_loc)
    if actor is None:
        return ("fail", label, ["spawn"])

    cam = find_actor_by_label("Cam_Shoot")
    if cam is None:
        eas.destroy_actor(actor)
        return ("fail", label, ["no_camera"])

    fit_camera(cam, actor)
    comp, rt = get_or_create_capture(cam)
    bg_plane = get_or_create_bg_plane()  # 灰背景板
    # 每个 mesh 同时截 base + final 两种 source，后处理逐像素取较亮者合并 →
    # 通吃 Lit(base 亮) / NPR(final 亮) / 混合材质，无需按类别猜
    preset = preset_for_mesh(mesh_path)
    apply_lighting(preset)
    apply_capture_pp(comp, preset)
    sc_actor = _SC_STATE["sc"]
    _d = cam.get_actor_location() - actor.get_actor_location()
    cam_dist = math.sqrt(_d.x * _d.x + _d.y * _d.y + _d.z * _d.z)

    w = unreal.EditorLevelLibrary.get_editor_world()
    SOURCES = [
        ("base", unreal.SceneCaptureSource.SCS_BASE_COLOR),
        ("final", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR),
    ]
    failed_views = []
    groups = [(out_paths[i], []) for i in range(len(VIEWS))]  # (最终输出, [base_tmp, final_tmp])
    for src_tag, src in SOURCES:
        comp.set_editor_property("capture_source", src)
        # 背景板只在 base color 路显示（base color 不受光/不 tonemap → 均匀精确灰）；
        # final color 路隐藏背景板（背景=黑），combine_max 取 max → 背景=base 的均匀灰。
        if bg_plane is not None:
            hide = (src_tag != "base")
            try:
                bg_plane.set_actor_hidden_in_game(hide)
            except Exception:
                pass
            try:
                bg_plane.set_is_temporarily_hidden_in_editor(hide)
            except Exception:
                pass
        # 预热：对准角色空跑几次，驱动贴图/shader 就绪，否则首帧黑剪影。丢弃。
        try:
            actor.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=VIEWS[0][1]), False)
            wo, _ = actor.get_actor_bounds(only_colliding_components=False)
            sc_actor.set_actor_location(unreal.Vector(wo.x - cam_dist, wo.y, wo.z), False, False)
            sc_actor.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(
                unreal.Vector(wo.x - cam_dist, wo.y, wo.z), wo), False)
            place_bg_plane(bg_plane, wo, cam_dist)
            for _ in range(WARMUP_CAPTURES):
                comp.capture_scene()
        except Exception:
            pass
        for i, (view, yaw) in enumerate(VIEWS):
            try:
                actor.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), False)
                new_origin, _ = actor.get_actor_bounds(only_colliding_components=False)
                sc_loc = unreal.Vector(new_origin.x - cam_dist, new_origin.y, new_origin.z)
                sc_actor.set_actor_location(sc_loc, False, False)
                sc_actor.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(sc_loc, new_origin), False)
                place_bg_plane(bg_plane, new_origin, cam_dist)
                tmp_name = f"v{i}_{view}__{src_tag}.png"
                comp.capture_scene()
                export_rt(_SC_STATE["rl"], w, rt, mesh_dir, tmp_name)
                groups[i][1].append(os.path.join(mesh_dir, tmp_name))
            except Exception as e:
                failed_views.append(f"{view}/{src_tag}:{e}")
    eas.destroy_actor(actor)
    # 释放 mesh 资源，避免批量时内存累积把 UE 撑挂
    try:
        unreal.EditorAssetLibrary.unload_asset(mesh_path)
    except Exception:
        pass
    combine_max(groups)

    if failed_views:
        return ("partial", label, failed_views)
    return ("ok", label, [])


def combine_max(groups):
    """把每视角的 base/final 两路合成为【RGBA 透明单图】（伊瑟式，供 06_compose 合成任意底色）：
      RGB   = max(base, final)         —— 与原黑底图同款角色色（Lit→base 亮、NPR→final 亮）
      alpha = 提纯后的 coverage         —— final 路 PropagateAlpha 给的是 1-coverage，
              反相得 coverage，再 cov/ALPHA_THR 拉满：实心区 α=255、最外圈羽化抗锯齿。
    base 路 alpha 全 0（无 matte），coverage 只能取自 final 路。spec 走 stdin 避免中文路径编码问题。
    """
    pairs = [(out, tmps) for out, tmps in groups if tmps]
    if not pairs or not os.path.exists(EXTERNAL_PYTHON):
        return
    spec = json.dumps({"pairs": pairs, "keep_tmp": bool(KEEP_TMP),
                       "low": float(ALPHA_LOW), "high": float(ALPHA_HIGH)}, ensure_ascii=False)
    script = (
        "import sys, json, os\n"
        "from PIL import Image\n"
        "import numpy as np\n"
        "d = json.loads(sys.stdin.read())\n"
        "low = d['low']; high = d['high']; keep = d['keep_tmp']\n"
        "for out, tmps in d['pairs']:\n"
        "    base = final = None\n"
        "    for t in tmps:\n"
        "        if not os.path.exists(t):\n"
        "            continue\n"
        "        arr = np.asarray(Image.open(t).convert('RGBA')).astype(np.float32)\n"
        "        if t.endswith('__base.png'):\n"
        "            base = arr\n"
        "        else:\n"
        "            final = arr\n"
        "    if base is None and final is None:\n"
        "        continue\n"
        "    rgbs = [x[:, :, :3] for x in (base, final) if x is not None]\n"
        "    rgb = rgbs[0] if len(rgbs) == 1 else np.maximum(rgbs[0], rgbs[1])\n"
        "    # alpha = final 覆盖(含 translucent 纱裙) ∪ base 几何(opaque 实体)。\n"
        "    # final 路某些视角对下半身/opaque 渲染缺失，但 base color 完整渲了 opaque，取并集补回。\n"
        "    if final is not None:\n"
        "        cov = 255.0 - final[:, :, 3]\n"
        "        af = np.clip((cov - low) / (high - low), 0.0, 1.0)\n"
        "    else:\n"
        "        af = np.ones(rgb.shape[:2], np.float32)\n"
        "    if base is not None:\n"
        "        bgeo = np.clip((base[:, :, :3].max(2) - low) / (high - low), 0.0, 1.0)\n"
        "    else:\n"
        "        bgeo = np.zeros(rgb.shape[:2], np.float32)\n"
        "    a = np.maximum(af, bgeo) * 255.0\n"
        "    outarr = np.dstack([rgb, a]).astype(np.uint8)\n"
        "    Image.fromarray(outarr, 'RGBA').save(out, optimize=True)\n"
        "    if not keep:\n"
        "        for t in tmps:\n"
        "            try:\n"
        "                os.remove(t)\n"
        "            except Exception:\n"
        "                pass\n"
    )
    try:
        subprocess.run([EXTERNAL_PYTHON, "-X", "utf8", "-c", script],
                       input=spec, capture_output=True, text=True,
                       encoding="utf-8", timeout=180)
    except Exception as e:
        log(f"combine error: {e}")


def main():
    log("=" * 60)
    log("UE Character Reference BATCH Render")
    log("=" * 60)

    aal = unreal.EditorAssetLibrary
    if not aal.does_asset_exist(LEVEL_PATH):
        log(f"ERROR: 请先跑 01_setup.py 建 Level")
        return
    get_level_subsystem().load_level(LEVEL_PATH)
    set_runtime_cvars()
    neutralize_ppv()
    ensure_lights_exist()

    # WHITELIST 模式下切到独立目录，避免和 full 跑混
    global OUTPUT_DIR
    if WHITELIST_MESH_PATHS:
        OUTPUT_DIR = WHITELIST_OUTPUT_DIR
        log(f"WHITELIST mode → output to {OUTPUT_DIR}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    meshes = collect_meshes()
    log(f"found {len(meshes)} skeletal meshes")
    if not meshes:
        log("没找到符合条件的 SkeletalMesh，检查 NAME_FILTER / SEARCH_DIRS")
        return

    t0 = time.time()
    stats = {"ok": 0, "skip": 0, "fail": 0, "partial": 0}
    errors = []

    for i, (name, path) in enumerate(meshes):
        try:
            status, clean, failed_views = shoot_one(path, name)
            stats[status] = stats.get(status, 0) + 1
            elapsed = time.time() - t0
            eta = elapsed / (i + 1) * (len(meshes) - i - 1)
            log(f"[{i+1}/{len(meshes)}] {status:<7} {clean}  (ETA {eta/60:.1f}min)")
            if failed_views:
                errors.append({"name": clean, "path": path, "failed": failed_views})
        except Exception as e:
            stats["fail"] += 1
            log(f"[{i+1}/{len(meshes)}] FATAL {name}: {e}")
            log(traceback.format_exc())
            errors.append({"name": name, "path": path, "error": str(e)})
        # 每 10 个强制 GC + 增量保存日志（防止 UE 中途挂时丢失进度信息）
        if (i + 1) % 10 == 0:
            try:
                unreal.SystemLibrary.collect_garbage()
            except Exception:
                try:
                    unreal.SystemLibrary.execute_console_command(
                        unreal.EditorLevelLibrary.get_editor_world(), "obj gc")
                except Exception:
                    pass
            try:
                with open(os.path.join(OUTPUT_DIR, "_batch_log.json"), "w", encoding="utf-8") as f:
                    json.dump({"stats": stats, "errors": errors,
                               "elapsed_sec": time.time() - t0,
                               "progress": f"{i+1}/{len(meshes)}",
                               "total": len(meshes)},
                              f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    cleanup_capture()

    # write log
    log_file = os.path.join(OUTPUT_DIR, "_batch_log.json")
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump({"stats": stats, "errors": errors,
                   "elapsed_sec": time.time() - t0,
                   "total": len(meshes)},
                  f, ensure_ascii=False, indent=2)

    log("\n" + "=" * 60)
    log("DONE")
    log("=" * 60)
    log(f"成功 {stats.get('ok', 0)} · 跳过 {stats.get('skip', 0)} · "
        f"部分失败 {stats.get('partial', 0)} · 整体失败 {stats.get('fail', 0)}")
    log(f"耗时 {(time.time()-t0)/60:.1f} 分钟")
    log(f"输出目录: {OUTPUT_DIR}")
    log(f"日志: {log_file}")
    log(">>> 失败的角色看 _batch_log.json，重跑本脚本会自动续传")

    try:
        os.startfile(OUTPUT_DIR)
    except Exception:
        pass


main()
