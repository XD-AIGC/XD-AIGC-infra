"""UE 自动化第 1 步：搭建渲染场景 + 改项目设置。

使用方法：
1. 打开你的 UE 项目
2. UE 菜单：Tools → Run Python Script → 选本文件
3. 看输出窗口（Window → Developer Tools → Output Log）
4. 跑完后**重启 UE Editor**（ini 改动需要重启生效）
5. 重启后跑 02_test.py

如果有报错：把 Output Log 截图发给我。
"""
import unreal
import os
import sys

# ============ 配置（按需改） ============
LEVEL_PATH    = "/Game/Maps/L_CharRefShoot"   # 新建 Level 的位置
RESOLUTION    = (1024, 2304)                    # 渲染分辨率 W x H
FOCAL_LENGTH  = 23.0                            # 焦距 mm（你定的）

# ============ 工具函数 ============
def log(msg):
    print(f"[setup] {msg}")
    unreal.log(f"[setup] {msg}")


def patch_project_ini():
    """改 DefaultEngine.ini 启用 alpha 通道支持（关键）"""
    project_dir = unreal.SystemLibrary.get_project_directory()
    ini_path = os.path.join(project_dir, "Config", "DefaultEngine.ini")

    needed_section = "[/Script/Engine.RendererSettings]"
    needed_lines = [
        # 2 = linear-only。alpha = 1-coverage、RGB 是 premultiplied。
        # 后处理脚本会反相 alpha + unpremultiply RGB。
        "r.PostProcessing.PropagateAlpha=2",
        "r.SceneColorFormat=4",
        "r.DefaultFeature.AntiAliasing=2",
        "r.DefaultFeature.AutoExposure=False",
        "r.DefaultFeature.Bloom=False",
    ]

    if os.path.exists(ini_path):
        with open(ini_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = ""

    changed = False
    if needed_section not in content:
        content += f"\n\n{needed_section}\n"
        changed = True
        log(f"added section {needed_section}")

    for line in needed_lines:
        key = line.split("=")[0]
        # remove existing line for this key (any value)
        new_content_lines = []
        for cl in content.splitlines():
            if cl.strip().startswith(key + "="):
                changed = True
                log(f"replaced: {cl.strip()} -> {line}")
                continue
            new_content_lines.append(cl)
        content = "\n".join(new_content_lines)
        # add under the section
        content = content.replace(needed_section, f"{needed_section}\n{line}", 1)
        if line in content:
            pass  # OK
        else:
            changed = True

    if changed:
        # backup (only first time, preserve the original pre-modification state)
        import shutil
        import stat
        backup_path = ini_path + ".bak_charref"
        if os.path.exists(ini_path) and not os.path.exists(backup_path):
            try:
                shutil.copy(ini_path, backup_path)
                log(f"backup saved: {backup_path}")
            except Exception as e:
                log(f"backup skipped ({e})")
        else:
            log(f"backup already exists, keeping original: {backup_path}")
        # clear readonly bit so we can write (P4 leaves files readonly)
        if os.path.exists(ini_path):
            try:
                os.chmod(ini_path, stat.S_IWRITE | stat.S_IREAD)
            except Exception as e:
                log(f"chmod failed ({e}), trying write anyway")
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(content)
        log(f"ini updated: {ini_path}")
        log("!!! 请重启 UE Editor 让 ini 生效 !!!")
        return True
    log("ini already configured, no changes")
    return False


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


def create_or_load_level():
    aal = unreal.EditorAssetLibrary
    els = get_level_subsystem()
    if aal.does_asset_exist(LEVEL_PATH):
        log(f"level exists, loading: {LEVEL_PATH}")
        els.load_level(LEVEL_PATH)
    else:
        log(f"creating new level: {LEVEL_PATH}")
        # ensure parent folder
        parent = LEVEL_PATH.rsplit("/", 1)[0]
        if not aal.does_directory_exist(parent):
            aal.make_directory(parent)
        els.new_level(LEVEL_PATH)


def clean_default_actors():
    """删除新关卡里 UE 自动生成的环境物（保留我们要加的）"""
    eas = get_actor_subsystem()
    keep_labels = {"Cam_Shoot", "SpawnAnchor", "PPV_Shoot",
                   "DirLight_Shoot", "SkyLight_Shoot"}
    for a in eas.get_all_level_actors():
        label = a.get_actor_label()
        if label in keep_labels:
            continue
        cn = a.get_class().get_name()
        # 默认场景里这些都是干扰项
        if cn in ("DirectionalLight", "SkyLight", "SkyAtmosphere",
                  "VolumetricCloud", "SunSky", "ExponentialHeightFog",
                  "PlayerStart", "Floor", "StaticMeshActor"):
            log(f"removing default actor: {label} ({cn})")
            eas.destroy_actor(a)


def add_post_process():
    els = get_level_subsystem()
    ppv = get_actor_subsystem().spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
    ppv.set_actor_label("PPV_Shoot")
    ppv.unbound = True
    s = ppv.settings
    # 关 Bloom（白底会洇染）
    s.set_editor_property("override_bloom_intensity", True)
    s.set_editor_property("bloom_intensity", 0.0)
    # 锁定曝光（每张亮度一致）
    s.set_editor_property("override_auto_exposure_min_brightness", True)
    s.set_editor_property("auto_exposure_min_brightness", 1.0)
    s.set_editor_property("override_auto_exposure_max_brightness", True)
    s.set_editor_property("auto_exposure_max_brightness", 1.0)
    # 关晕影
    s.set_editor_property("override_vignette_intensity", True)
    s.set_editor_property("vignette_intensity", 0.0)
    # 关色差
    s.set_editor_property("override_scene_fringe_intensity", True)
    s.set_editor_property("scene_fringe_intensity", 0.0)
    log("added PPV_Shoot (bloom/exposure/vignette off)")


def add_lights():
    eas = get_actor_subsystem()

    # Directional light：前上方 45°
    dl = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500))
    dl.set_actor_label("DirLight_Shoot")
    dl.set_actor_rotation(unreal.Rotator(-45, -30, 0), False)
    dlc = dl.light_component
    dlc.set_editor_property("intensity", 30.0)
    dlc.set_editor_property("cast_shadows", False)
    log("added DirLight_Shoot (no shadow)")

    # SkyLight：环境补光
    sl = eas.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 500))
    sl.set_actor_label("SkyLight_Shoot")
    slc = sl.light_component
    slc.set_editor_property("intensity", 5.0)
    slc.set_editor_property("cast_shadows", False)
    # 必须 recapture 一次否则 SkyLight cubemap 为空 = 没环境光
    try:
        if hasattr(slc, "recapture_sky"):
            slc.recapture_sky()
        elif hasattr(sl, "recapture"):
            sl.recapture()
    except Exception as e:
        log(f"skylight recapture skipped: {e}")
    log("added SkyLight_Shoot (no shadow)")


def add_camera():
    cam = get_actor_subsystem().spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(-300, 0, 100))
    cam.set_actor_label("Cam_Shoot")
    cc = cam.get_cine_camera_component()
    cc.set_editor_property("current_focal_length", FOCAL_LENGTH)
    cc.set_editor_property("current_aperture", 22.0)
    # 关自动对焦，避免角色变远后失焦
    focus = cc.focus_settings
    focus.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
    focus.set_editor_property("manual_focus_distance", 500.0)
    log(f"added Cam_Shoot (focal={FOCAL_LENGTH}mm, Super 35)")


def add_spawn_anchor():
    anchor = get_actor_subsystem().spawn_actor_from_class(unreal.TargetPoint, unreal.Vector(0, 0, 0))
    anchor.set_actor_label("SpawnAnchor")
    log("added SpawnAnchor at origin")


def save_level():
    els = get_level_subsystem()
    els.save_current_level()
    log(f"level saved: {LEVEL_PATH}")


# ============ 主流程 ============
def main():
    log("=" * 60)
    log("UE Character Reference Auto Setup")
    log("=" * 60)

    restart_needed = patch_project_ini()

    log("\n--- 设置场景 ---")
    create_or_load_level()
    clean_default_actors()
    add_post_process()
    add_lights()
    add_camera()
    add_spawn_anchor()
    save_level()

    log("\n" + "=" * 60)
    log("DONE")
    log("=" * 60)
    if restart_needed:
        log(">>> ini 文件已修改，请【关闭 UE Editor】然后重新打开 <<<")
        log(">>> 重新打开后再跑 02_test.py")
    else:
        log(">>> ini 已是正确配置，可以直接跑 02_test.py")


main()
