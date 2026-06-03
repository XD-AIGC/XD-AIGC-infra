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
OUTPUT_DIR    = r"D:/角色识别数据/伊瑟_UE4"      # 全量输出（伊瑟 UE4）
WHITELIST_OUTPUT_DIR = r"D:/角色识别数据/伊瑟_UE4_whitelist"   # WHITELIST 模式下使用
RESOLUTION    = (1024, 2304)
LEVEL_PATH    = "/Game/Maps/L_CharRefShoot"
SEARCH_DIRS   = [  # 三组(Prop/Thrown 不需要；Friday 在 Chr 下、走 agt 预设)。只调一组时可注释掉另两行
    "/Game/ArtResources/Characters/Agt",
    "/Game/ArtResources/Characters/Cst",
    "/Game/ArtResources/Characters/Chr",
]
MESH_REQUIRE_PATH = ""                                # 伊瑟 mesh 不在 /Meshes/ 子目录，不做正向路径过滤
NAME_FILTER   = ""                                   # 空 = 不按名字过滤，全部 SkeletalMesh 都渲
EXCLUDE_PATH_KEYWORDS = ["/Weapon/", "/Sub1/", "/Sub2/", "/Sub3/",
                          "/VFX/", "/Effect/", "/Effects/", "/Anim/", "/Animations/"]
EXCLUDE_NAME_KEYWORDS = ["_Weapon", "_VFX", "_Anim", "_Skill", "PhysicsAsset", "Skeleton",
                          "_Physics", "_Skeleton", "ShadowProxy", "_Proxy",
                          "Sub1_", "Sub2_", "Sub3_",
                          "NPC", "uestionMark", "Preview", "_Test",        # 用户要求删:NPC/问号/预览/测试资产
                          "_Rig", "Tentacle", "tentacle", "Suitcase"]      # 零件/rig 子网格(全黑、非角色)
# LOD 策略：有 _LOD0 就只要 _LOD0；完全没有 _LOD 后缀的（单 LOD mesh）也渲

# 已知会让 UE crash 的 mesh 子串（spawn/bounds 时 array OOB / LOD reduction assert），直接跳过
# 加进来的角色不会被渲染。修复了 mesh 后可以删掉。
BAD_MESH_SUBSTRINGS = [
    # 跑全量时若某 mesh 让 UE crash，把名字子串加进来跳过，再重跑续传
]

# ============ 测试白名单（分组逐一精调）============
# 调某组时：WHITELIST_MESH_PATHS 设成对应 _XXX_TEST，只渲该组、反复调 PRESETS["xxx"]；
# 该组满意后换下一组；全部 OK 后设 []（→全量到 OUTPUT_DIR）。路径均取自 eden 真实资产。
_AGT_TEST = [  # 探子，覆盖不同发光/体型 + Friday 系列（同属 Agt）
    "/Game/ArtResources/Characters/Agt/Agt_Alicorn/SK_Agt_Alicorn_LOD0",
    "/Game/ArtResources/Characters/Agt/Agt_CursedFrog/SK_Agt_CursedFrog_LOD0",
    "/Game/ArtResources/Characters/Agt/Agt_Halloween/SK_Agt_Halloween_LOD0",
    "/Game/ArtResources/Characters/Agt/Agt_MirrorBee/SK_Agt_MirrorBee_LOD0",
    "/Game/ArtResources/Characters/Agt/Agt_RetributionAngel/SK_Agt_RetributionAngel_LOD0",
    "/Game/ArtResources/Characters/Agt/Agt_Supernova/SK_Agt_Supernova_LOD0",
    "/Game/ArtResources/Characters/Agt/Agt_WhiteBlast/SK_Agt_WhiteBlast_LOD0",
    "/Game/ArtResources/Characters/Chr/Chr_Friday_Demon/Demon_Undead/SK_Agt_Friday_Demon_Undead_LOD0",
    "/Game/ArtResources/Characters/Chr/Chr_Friday_Mirage/Mirage_BluePorcelain/SK_Agt_Friday_Mirage_BluePorcelain_LOD0",
]
_CST_TEST = [  # 装扮，覆盖觉构/觉异/觉空/觉光 + 深色/浅色/华丽
    "/Game/ArtResources/Characters/Cst/Cst_Abstinence/Cst_Abstinence_Light/SK_Cst_Abstinence_Light_LOD0",  # 黑甲+发光
    "/Game/ArtResources/Characters/Cst/Cst_Admonition/Cst_Admonition_Odd/SK_Cst_Admonition_Odd_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Arielle/Cst_Arielle_Const/SK_Cst_Arielle_Const_LOD0",          # 浅色
    "/Game/ArtResources/Characters/Cst/Cst_Bornova/Cst_Bornova_Odd/SK_Cst_Bornova_Odd_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Experimenter41/Cst_Experimenter41_Hollow/SK_Cst_Experimenter41_Hollow_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Kabbalah/Cst_Kabbalah_Disor/SK_Cst_Kabbalah_Disor_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Nell/Cst_Nell_Const/SK_Cst_Nell_Const_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_SweetDream/Cst_SweetDream_Const/SK_Cst_SweetDream_Const_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Viper/Cst_Viper_Odd/SK_Cst_Viper_Odd_LOD0",
]
_CHR_TEST = [  # 主角套装 + NPC（Friday 系列单独处理，见 BAD_CASES / 后续）
    "/Game/ArtResources/Characters/Chr/Chr_AgentM/SK_Chr_AgentM_LOD0",
    "/Game/ArtResources/Characters/Chr/Chr_NPC_Aya/SK_Chr_NPC_Aya_LOD0",
    "/Game/ArtResources/Characters/Chr/Chr_Boy_Home_Crow/Boy_Home_Crow/SK_Chr_Boy_Home_Crown_LOD0",
    "/Game/ArtResources/Characters/Chr/Chr_Boy_Home_Punk_Navyblack/Boy_Home_Punk_Navyblack/SK_Chr_Boy_Home_Punk_Navyblack_LOD0",
    "/Game/ArtResources/Characters/Chr/Chr_Girl_Home_Eveningdress/Eveningdress_Blackgold/SK_Chr_Girl_Home_Ed_Blackgold_Lod0",
    "/Game/ArtResources/Characters/Chr/Chr_Girl_Home_Sw_Blackpink/Girl_Home_Sw_Blackpink/SK_Chr_Girl_Home_Sw_Blackpink_LOD0",
]
_PROP_TEST = [  # 道具/投掷物
    "/Game/ArtResources/Characters/Prop/Prop_Bottle01/SK_Prop_Bottle01",
    "/Game/ArtResources/Characters/Prop/Prop_Button01/SK_Prop_Button01",
]
_ETH_MIX_TEST = _AGT_TEST + _CST_TEST + _CHR_TEST + _PROP_TEST   # 各组混合
# Cst 全量暴露的问题角色（诊断"贴图加载/参数"用；单独/小批重渲，与全量结果对比）
_CST_DIAG = [
    "/Game/ArtResources/Characters/Cst/Cst_Cabala/Cst_Cabala_Const/SK_Cst_Cabala_const_LOD0",      # 棋盘格(疑似贴图没加载)
    "/Game/ArtResources/Characters/Cst/Cst_Airon/Cst_Airon_Odd/SK_Cst_Airon_Odd_LOD0",             # 脸太白
    "/Game/ArtResources/Characters/Cst/Cst_Celince/Cst_Celince_Hollow/SK_Cst_Celince_Hollow_LOD0", # 脸黑
    "/Game/ArtResources/Characters/Cst/Cst_Cyborg/Cst_Cyborg_Disor/SK_Cst_Cyborg_Disor_LOD0",      # 身体色
    "/Game/ArtResources/Characters/Cst/Cst_Dolores/Cst_Dolores_Const/SK_Cst_Dolores_Const_LOD0",   # 脸色
    "/Game/ArtResources/Characters/Cst/Cst_Gray/Cst_Gray_Disor/SK_Cst_Gray_Disor_LOD0",            # 脸色
    "/Game/ArtResources/Characters/Cst/Cst_Kazama/Cst_Kazama_Hollow/SK_Cst_Kazama_Hollow_LOD0",    # 太深
    "/Game/ArtResources/Characters/Cst/Cst_Dahlia/Cst_Dahlia_Hollow/SK_Cst_Dahlia_Hollow_LOD0",    # 身体色
    "/Game/ArtResources/Characters/Cst/Cst_DokiDoki/Cst_DokiDoki_Const/SK_Cst_DokiDoki_Const_LOD0",# 身体色
    "/Game/ArtResources/Characters/Cst/Cst_Kethos/Cst_Kethos_Odd/SK_Cst_Kethos_Odd_LOD0",          # 脸色
    "/Game/ArtResources/Characters/Cst/Cst_Nell/Cst_Nell_Const/SK_Cst_Nell_Const_LOD0",            # 对照(全量里OK)
    "/Game/ArtResources/Characters/Cst/Cst_Arielle/Cst_Arielle_Const/SK_Cst_Arielle_Const_LOD0",   # 对照(OK)
]
# 取景测试：偏小/偏大/缺件代表，验证 get_fit_bounds(碰撞体取景)修复
_FRAME_TEST = [
    "/Game/ArtResources/Characters/Cst/Cst_Ark/Cst_Ark_Disor/SK_Cst_Ark_Disor_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Astarte/Cst_Astarte_Const/SK_Cst_Astarte_Const_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Bornova/Cst_Bornova_Odd/SK_Cst_Bornova_Odd_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Dahlia/Cst_Dahlia_Hollow/SK_Cst_Dahlia_Hollow_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_DokiDoki/Cst_DokiDoki_Const/SK_Cst_DokiDoki_Const_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Holden/Cst_Holden_Light/SK_Cst_Holden_Light_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Kazama/Cst_Kazama_Hollow/SK_Cst_Kazama_Hollow_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Viper/Cst_Viper_Odd/SK_Cst_Viper_Odd_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Yang/Cst_Yang_Odd/SK_Cst_Yang_Odd_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Worm/Cst_Worm_Const/SK_Cst_Worm_Const_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Mia/Cst_Mia_Light/SK_Cst_Mia_Light_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_HardShield/Cst_HardShield_Hollow/SK_Cst_HardShield_LOD0",  # 偏大
    "/Game/ArtResources/Characters/Cst/Cst_Jellyfish/Cst_Jellyfish_Hollow/SK_Cst_Jellyfish_Hollow_LOD0",  # 偏大
    "/Game/ArtResources/Characters/Cst/Cst_Febian/Cst_Febian_Const/SK_Cst_Febian_Const_LOD0",        # 缺马?
    "/Game/ArtResources/Characters/Cst/Cst_GhostMagic/Cst_GhostMagic_Disor/SK_Cst_GhostMagic_Disor_LOD0",  # 缺杆?
]
# bad case 验证：全黑/缺件/看不清(Cst) + 眼睛黑/Fleet(Chr/Friday)，看修复后哪些好了/哪些仍坏
_VERIFY_TEST = [
    "/Game/ArtResources/Characters/Cst/Cst_Febian/Cst_Febian_Const/SK_Cst_Febian_Const_LOD0",            # 缺马?
    "/Game/ArtResources/Characters/Cst/Cst_GhostMagic/Cst_GhostMagic_Disor/SK_Cst_GhostMagic_Disor_LOD0",# 缺杆?
    "/Game/ArtResources/Characters/Cst/Cst_Prisoner/Cst_Prisoner_Odd/SK_Cst_Prisoner_Odd_LOD0",          # 脚下缺?
    "/Game/ArtResources/Characters/Cst/Cst_PaperCrane/Cst_PaperCrane_Hollow/SK_Cst_PaperCrane_Hollow_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Tailspin/Cst_Tailspin_Odd/SK_Cst_Tailspin_Odd_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_TrainConductorState2/Cst_TrainConductorState2_Odd/SK_Cst_TrainConductorState2_Odd_LOD0",
    "/Game/ArtResources/Characters/Cst/Cst_Snake/Cst_Snake_Hollow/SK_Cst_Snake_Hollow_LOD0",             # 全黑?
    "/Game/ArtResources/Characters/Cst/Cst_TiamatMorph/Cst_TiamatMorph_Hollow/SK_Cst_TiamatMorph_Hollow_LOD0",  # 全黑?
    "/Game/ArtResources/Characters/Cst/Cst_RC77/Cst_RC77_Odd/SK_Cst_RC77_Water_LOD0",                    # 全黑?
    "/Game/ArtResources/Characters/Chr/Chr_Friday/SK_Agt_Friday_LOD0",                                   # 眼睛黑?
    "/Game/ArtResources/Characters/Chr/Chr_Friday_Thorn/Thorn_Crown/SK_Agt_Friday_Thorn_Crown_LOD0",     # 眼睛黑?
    "/Game/ArtResources/Characters/Chr/Chr_Friday_Summer/Summer_BeachStar/SK_Agt_Friday_Summer_BeachStar_LOD0",
    "/Game/ArtResources/Characters/Chr/Chr_Friday_NaughtyGhost/NaughtyGhost_CandleLight/SK_Agt_Friday_NaughtyGhost_CandleLight_LOD0",
    "/Game/ArtResources/Characters/Chr/Chr_Girl_Home_Fleet/Girl_Home_Fleet/SK_Chr_Girl_Home_Fleet_LOD0", # Fleet 衣服色
    "/Game/ArtResources/Characters/Chr/Chr_Boy_Home_Fleet/Boy_Home_Fleet/SK_Chr_Boy_Home_Fleet_LOD0",
]
WHITELIST_MESH_PATHS = []  # [] = 跑 SEARCH_DIRS(当前仅 Cst)+SKIP_EXISTING 续传 → 只补渲已删的"偏小"批

VIEWS = [("front", 180.0), ("side", -90.0), ("back", 0.0), ("tq", 135.0)]
FILL_RATIO = 0.80
SKIP_EXISTING = True   # 续传：只补渲已删的"偏小"批，其余跳过
WARMUP_CAPTURES = 6    # 每个 mesh 截图前空跑几次预热（给贴图加载留时间，防黑剪影/棋盘格占位）

# ============ 分组渲染预设（每组一套完整参数，逐组独立精调）============
# eden 实测要点：① final color 强光糊白且本工程 EV 失效；② base color 有真实材质色、不吃灯、
# 不糊白（但裸露皮肤等材质 base 槽可能是占位色，如橙色）；③ Agt 是 Unlit+emissive。
# 每组字段：
#   capture          "base"=截材质原色(推荐 Lit 角色) / "final"=截光照色(Agt 发光用)
#   sky/dir/...      灯光（仅 capture=="final" 时有效）
#   ev/sat/flatten/shoulder  后处理（仅 final 有效；EV 本工程实测失效，主要靠灯光强度）
#   brighten_pct     提亮锚点分位（取前景亮度该分位为基准，70=身体主体；越低越不怕小高光带偏）
#   brighten_target  把锚点分位亮度缩放到该值（0-255，越大越亮；身体主体目标亮度）
#   brighten_max     提亮倍数上限（1.0 = 不提亮；越大越能救黑甲暗图，过大会放大噪声）
PRESETS = {
    "agt": {  # 探子(含 Friday)：base 真实色 + 激进提亮(救暗:Amber/CursedFrog 等)。不开 skin_fix。
        # Alicorn 类"红色 emissive 发光为主"的探子 base 里没发光 → 记 bad case 单独合成处理。
        "capture": "base", "sky": 0, "dir": 0, "dir_pitch": -30, "dir_yaw": -45,
        "ev": 0.0, "sat": 1.0, "flatten": False,
        "brighten_pct": 60.0, "brighten_target": 180.0, "brighten_max": 30.0,
    },
    "cst": {  # 装扮 Lit cel-shader：base + 提亮 + 皮肤占位橙→肤色（与 chr 同一套占位材质）
        "capture": "base", "sky": 0, "dir": 0, "dir_pitch": -30, "dir_yaw": -45,
        "ev": 0.0, "sat": 1.0, "flatten": False,
        "brighten_pct": 70.0, "brighten_target": 170.0, "brighten_max": 15.0,
        "skin_fix": {"h_lo": 5.0, "h_hi": 22.0, "s_min": 0.5,
                     "to_h": 26.0, "to_s": 0.32, "v_gain": 1.25},
    },
    "chr": {  # 主角/NPC：base + 提亮 + 皮肤占位橙→肤色
        "capture": "base", "sky": 0, "dir": 0, "dir_pitch": -30, "dir_yaw": -45,
        "ev": 0.0, "sat": 1.0, "flatten": False,
        "brighten_pct": 70.0, "brighten_target": 170.0, "brighten_max": 15.0,
        # 占位橙皮肤实测 HSV≈(h7°,s0.80)；把 h∈[5,22]&s≥0.5 的红橙重映射成暖肤色
        "skin_fix": {"h_lo": 5.0, "h_hi": 22.0, "s_min": 0.5,
                     "to_h": 26.0, "to_s": 0.32, "v_gain": 1.25},
    },
    "prop": {  # 道具/投掷物
        "capture": "base", "sky": 0, "dir": 0, "dir_pitch": -30, "dir_yaw": -45,
        "ev": 0.0, "sat": 1.0, "flatten": False,
        "brighten_pct": 70.0, "brighten_target": 160.0, "brighten_max": 15.0,
    },
}


def preset_for_mesh(mesh_path):
    if "/Agt/" in mesh_path or "Friday" in mesh_path:   # Friday 系列属 Agt（mesh 名 SK_Agt_Friday_*，只是资产在 /Chr/ 下）
        return PRESETS["agt"]
    if "/Chr/" in mesh_path:
        return PRESETS["chr"]
    if "/Prop/" in mesh_path or "/Thrown/" in mesh_path:
        return PRESETS["prop"]
    return PRESETS["cst"]   # 默认 Cst（数量最多）


def capture_source_for_mesh(mesh_path):
    if preset_for_mesh(mesh_path).get("capture", "base") == "final":
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


FILL_RATIO_W = 0.88  # 水平占帧比例：收紧左右留白，宽角色(翅膀)完整入画前提下尽量大；正常角色仍由高度决定


def get_fit_bounds(actor):
    """取景用包围盒：优先碰撞体(身体)，排除无碰撞的远伸件(武器/翅膀/坐骑/特效)防取景被撑大→角色显小；
    碰撞体退化(无物理体)时回退整体包围盒，保证不崩。"""
    try:
        o, e = actor.get_actor_bounds(only_colliding_components=True)
        if e.x >= 5.0 or e.y >= 5.0 or e.z >= 5.0:
            return o, e
    except Exception:
        pass
    return actor.get_actor_bounds(only_colliding_components=False)


def fit_camera(cam, actor):
    origin, extent = get_fit_bounds(actor)
    height = max(extent.z * 2, 50.0)
    width = max(extent.x, extent.y) * 2
    sensor_h = 13.365
    focal = cam.get_cine_camera_component().current_focal_length
    v_fov = 2.0 * math.atan(sensor_h / (2.0 * focal))
    aspect_wh = RESOLUTION[0] / RESOLUTION[1]
    h_fov = 2.0 * math.atan(math.tan(v_fov / 2.0) * aspect_wh)
    dist_h = (height / FILL_RATIO) / (2.0 * math.tan(v_fov / 2.0))
    dist_w = (width / FILL_RATIO_W) / (2.0 * math.tan(h_fov / 2.0))
    # 整体完整、不裁：取 height/width 两者所需的较远距离，保证宽翅膀也完整入画（宽角色会偏小，已接受）。
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


def cleanup_capture():
    if _SC_STATE["sc"] is not None:
        try:
            get_actor_subsystem().destroy_actor(_SC_STATE["sc"])
        except Exception:
            pass
    _SC_STATE["rt"] = None
    _SC_STATE["sc"] = None
    _SC_STATE["comp"] = None


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
    # 每个 mesh 同时截 base + final 两种 source，后处理逐像素取较亮者合并 →
    # 通吃 Lit(base 亮) / NPR(final 亮) / 混合材质，无需按类别猜
    preset = preset_for_mesh(mesh_path)
    apply_lighting(preset)
    apply_capture_pp(comp, preset)
    sc_actor = _SC_STATE["sc"]
    _d = cam.get_actor_location() - actor.get_actor_location()
    cam_dist = math.sqrt(_d.x * _d.x + _d.y * _d.y + _d.z * _d.z)

    w = unreal.EditorLevelLibrary.get_editor_world()
    # eden 实测：final color 强光下糊白且 EV 失效；base color 有真实材质色但偏暗。
    # 故 Cst/Chr/Prop/Thrown 用 base（后处理自动提亮），Agt(Unlit emissive) 用 final（无灯、不糊、保留发光）。
    SOURCES = [("img", capture_source_for_mesh(mesh_path))]
    failed_views = []
    groups = [(out_paths[i], []) for i in range(len(VIEWS))]  # (最终输出, [tmp])
    for src_tag, src in SOURCES:
        comp.set_editor_property("capture_source", src)
        # 预热：对准角色空跑几次，驱动贴图/shader 就绪，否则首帧黑剪影。丢弃。
        try:
            actor.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=VIEWS[0][1]), False)
            wo, _ = get_fit_bounds(actor)
            sc_actor.set_actor_location(unreal.Vector(wo.x - cam_dist, wo.y, wo.z), False, False)
            sc_actor.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(
                unreal.Vector(wo.x - cam_dist, wo.y, wo.z), wo), False)
            for _ in range(WARMUP_CAPTURES):
                comp.capture_scene()
        except Exception:
            pass
        for i, (view, yaw) in enumerate(VIEWS):
            try:
                actor.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), False)
                new_origin, _ = get_fit_bounds(actor)
                sc_loc = unreal.Vector(new_origin.x - cam_dist, new_origin.y, new_origin.z)
                sc_actor.set_actor_location(sc_loc, False, False)
                sc_actor.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(sc_loc, new_origin), False)
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
    finalize(groups, preset.get("brighten_target", 170.0), preset.get("brighten_max", 15.0),
             preset.get("brighten_pct", 70.0), preset.get("skin_fix"))

    if failed_views:
        return ("partial", label, failed_views)
    return ("ok", label, [])


def finalize(groups, target=170.0, maxscale=15.0, pct=70.0, skin=None):
    """groups: [(out_path, [tmp]), ...]。单源截图(base 或 Agt 的 final)，黑底 RGB。
    ① 自动提亮：以前景亮度 pct 分位为锚缩放到 ~target，scale∈[1,maxscale]，只提不压。
    ② 可选 skin_fix(skin 非 None)：把"占位橙皮肤"色相带重映射成自然肤色
       (HSV 选 h∈[h_lo,h_hi]&s≥s_min 的红橙像素 → 改 h=to_h、s=to_s、v*v_gain)。
    target/maxscale/pct/skin 由各组 preset 传入，分组独立调。丢 alpha、删临时文件。
    """
    pairs = [(out, tmps) for out, tmps in groups if tmps]
    if not pairs or not os.path.exists(EXTERNAL_PYTHON):
        return
    spec = json.dumps({"pairs": pairs, "target": float(target), "maxscale": float(maxscale),
                       "pct": float(pct), "skin": skin}, ensure_ascii=False)
    script = (
        "import sys, json, os\n"
        "from PIL import Image\n"
        "import numpy as np\n"
        "d = json.loads(sys.stdin.read())\n"
        "target=float(d['target']); maxscale=float(d['maxscale']); pct=float(d['pct']); skin=d['skin']\n"
        "for out, tmps in d['pairs']:\n"
        "    src = next((t for t in tmps if os.path.exists(t)), None)\n"
        "    if src is None:\n"
        "        continue\n"
        "    f = np.asarray(Image.open(src).convert('RGB')).astype('float32')\n"
        "    lum = f.max(axis=2)\n"
        "    fg = lum[lum > 10]\n"                          # 忽略黑底
        "    anchor = np.percentile(fg, pct) if fg.size else 255.0\n"
        "    scale = min(max(target / max(anchor, 1.0), 1.0), maxscale)\n"  # 只提不压，封顶
        "    f = np.clip(f * scale, 0, 255).astype('uint8')\n"
        "    if skin:\n"                                    # 占位橙皮肤 → 自然肤色
        "        hsv = np.asarray(Image.fromarray(f,'RGB').convert('HSV')).astype('int16')\n"
        "        H,S,V = hsv[...,0],hsv[...,1],hsv[...,2]\n"
        "        hlo=int(skin['h_lo']*255/360); hhi=int(skin['h_hi']*255/360); smin=int(skin['s_min']*255)\n"
        "        m=(H>=hlo)&(H<=hhi)&(S>=smin)&(V>20)\n"
        "        H[m]=int(skin['to_h']*255/360); S[m]=int(skin['to_s']*255)\n"
        "        V[m]=np.clip(V[m]*skin['v_gain'],0,255)\n"
        "        f=np.asarray(Image.fromarray(np.stack([H,S,V],-1).astype('uint8'),'HSV').convert('RGB'))\n"
        "    Image.fromarray(f.astype('uint8'), 'RGB').save(out, optimize=True)\n"
        "    for t in tmps:\n"
        "        try:\n"
        "            os.remove(t)\n"
        "        except Exception:\n"
        "            pass\n"
    )
    try:
        subprocess.run([EXTERNAL_PYTHON, "-X", "utf8", "-c", script],
                       input=spec, capture_output=True, text=True,
                       encoding="utf-8", timeout=180)
    except Exception as e:
        log(f"finalize error: {e}")


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
        # 每个 mesh 都 GC 释放上一个的贴图/显存（TextureStreaming 0 下防显存堆满→棋盘格占位）
        try:
            unreal.SystemLibrary.collect_garbage()
        except Exception:
            try:
                unreal.SystemLibrary.execute_console_command(
                    unreal.EditorLevelLibrary.get_editor_world(), "obj gc")
            except Exception:
                pass
        # 每 10 个增量保存日志（防止 UE 中途挂时丢失进度信息）
        if (i + 1) % 10 == 0:
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

# 无头跑（run_ue.bat 设了 UE_HEADLESS_QUIT=1）跑完自动退出完整编辑器；交互在编辑器内跑时不触发
if os.environ.get("UE_HEADLESS_QUIT"):
    try:
        unreal.SystemLibrary.execute_console_command(
            unreal.EditorLevelLibrary.get_editor_world(), "QUIT_EDITOR")
    except Exception:
        pass
