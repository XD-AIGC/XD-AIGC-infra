# UE 角色参考图批量渲染

把 UE 项目里的所有 SkeletalMesh 角色，按统一规则（4 视角 + 透明背景 + 镜像目录结构）批量渲染成 PNG，给下游 AIGC 流程做参考图素材。

当前基于《**伊瑟**》UE 项目实现，PRESET 灯光/材质参数也按伊瑟资产体系（Agt / Cst / Chr 三类）调过。换项目可复用框架，但 `SEARCH_DIRS` 和 `preset_for_mesh()` 需要按新项目的资产结构重新对齐。

> 注：样例渲染图与角色资产清单（`docs/`）属项目专有素材，未随本仓库公开。
> 跑完用 `04_viewer.py` 起 HTML 预览，点缩略图全屏放大，`← →` 切视角。

## 输出长这样

```
D:/ref_shots/full/
└── ArtResources/Characters/          # 镜像 UE Content Browser 路径
    ├── Agt/
    │   ├── Agt_Alicorn/SK_Agt_Alicorn_LOD0/
    │   │   ├── v0_front.png   # 1024×2304，透明背景
    │   │   ├── v1_side.png
    │   │   ├── v2_back.png
    │   │   └── v3_tq.png
    │   └── ...
    ├── Chr/
    └── Cst/
```

每个角色 4 张图，分辨率 1024×2304，alpha 透明背景。目录结构和 UE Content Browser 一一对应，方便人眼对照。

## 7 个脚本

| 脚本 | 干什么 | 何时跑 | 在哪跑 |
|---|---|---|---|
| `01_setup.py` | 改 `DefaultEngine.ini` 启用 alpha，建专用 Level + 灯 + 相机 | 第一次部署、改了配置 | UE 内 |
| `02_test.py` | 渲染 1 个测试角色，肉眼验证 alpha 是否正确 | 每次大改后 | UE 内 |
| `02b_light_test.py` | 同一角色在网格参数下跑 N 张图，肉眼比对调参 | 调 PRESET 时 | UE 内 |
| `03_batch.py` | 全量渲染所有 SkeletalMesh | 出正式产物时 | UE 内 |
| `04_viewer.py` | 扫输出目录生成 `viewer.html`，按角色 ID 自动分组（同角色多套装合卡），带搜索/类型筛选/折叠/放大 | 渲染完看效果时 | 外部 Python |
| `05_manifest.py` | 扫输出目录生成 `docs/characters.json` — 命名规范 + 全角色清单（哪些 mesh 属于同一角色的不同套装/颜色） | 渲染完后做资产清单时 | 外部 Python |
| `06_compose.py` | 把每个 mesh 的 4 视角横向拼成一张黑底大图（4416×2432 PNG），flat 输出，文件名 = `mesh_name`，可与 `characters.json` 直接 join | 给下游做参考图素材时 | 外部 Python |

## 前置要求

- **UE 项目已经能在编辑器里正常打开**
- **外部 Python 3.x**（不是 UE 自带的）有 `PIL` 和 `numpy`：
  - 默认路径 `C:/Users/XINDONG/AppData/Local/Programs/Python/Python312/python.exe`
  - 改各脚本顶部的 `EXTERNAL_PYTHON` 常量指向你自己的
  - 这个外部 Python 负责 PNG 后处理（alpha 反相、unpremultiply、合成）
- **Windows / PowerShell**（脚本里有 `os.startfile`、Windows 风格路径，跨平台需要小改）

## 使用流程

### Step 1：搭场景（一次性）

```
UE → Tools → Run Python Script → 选 01_setup.py
```

跑完会提示**重启 UE Editor**（`DefaultEngine.ini` 改动需要重启生效），重启后再继续。

### Step 2：测试单角色

```
UE → Run Python Script → 02_test.py
```

跑完打开 `D:/ref_shots/test/`，拖一张 PNG 进 Photoshop / GIMP / VSCode 看：
- 角色清晰
- 背景棋盘格透明
- 4 视角都对

任何一项不对，把 Output Log 截图发出来。

### Step 3：全量渲染

```
UE → Run Python Script → 03_batch.py
```

输出到 `D:/ref_shots/full/`。中途挂了直接重跑，`SKIP_EXISTING=True` 会续传。

### Step 4：浏览器看图

```
python 04_viewer.py                       # 默认扫 D:/ref_shots/full
python 04_viewer.py D:/ref_shots/test     # 也可扫别的
```

会在被扫目录写 `viewer.html` 并自动打开。点缩略图放大，`← →` 切视角，`ESC` 关闭；顶栏可按路径搜索，按 Agt/非 Agt 筛选。整个目录拷给别人也能离线看。

## 关键配置（每个脚本顶部 `# ============ 配置 ============`）

### `03_batch.py` 常用

| 名字 | 作用 |
|---|---|
| `OUTPUT_DIR` | 全量输出根目录 |
| `WHITELIST_OUTPUT_DIR` | 白名单测试输出目录 |
| `RESOLUTION` | 渲染分辨率（W, H） |
| `SEARCH_DIRS` | 在哪些 Content 目录扫 SkeletalMesh |
| `WHITELIST_MESH_PATHS` | 空 = 全量；指定 list = 只跑这些（用于调试） |
| `_AGT_TEST_PATHS` / `_PREVIEW19_PATHS` | 预置的小批名单，赋给 `WHITELIST_MESH_PATHS` 即可 |
| `BAD_MESH_SUBSTRINGS` | 已知会让 UE crash 的 mesh，跳过 |
| `EXCLUDE_PATH_KEYWORDS` / `EXCLUDE_NAME_KEYWORDS` | 路径/文件名过滤（武器、特效、动画等） |

### 渲染预设 `PRESETS`

`03_batch.py` 里按角色目录分组用不同的灯光 + 后处理。当前两组：

```python
PRESETS = {
    "cst": {  # Cst/Chr/Common 等普通 cel-shader（Lit 材质）
        "sky": 400, "dir": 1900, "dir_pitch": -30, "dir_yaw": -45,
        "ev": 14.0, "sat": 1.0, "flatten": True,
    },
    "agt": {  # Agt 角色 emissive 材质
        "sky": 0, "dir": 0, "dir_pitch": -30, "dir_yaw": -45,
        "ev": -1.0, "sat": 1.4, "flatten": False, "shoulder": 0.50,
    },
}
```

`preset_for_mesh(path)` 按路径决定走哪组。要加新组：
1. 在 `PRESETS` 里加一项
2. 在 `preset_for_mesh()` 里加 if 分支

参数怎么调？跑 `02b_light_test.py`，把 `INTENSITY_AXIS / EV_AXIS / SHOULDER_AXIS` 等网格变量改成你想扫的范围，跑完看 `grid.png` 找最优格子。

## 已知坑

- **Agt 系列角色用的是 Unlit + emissive 材质**，灯光对它们完全没用，只能靠 PP（曝光 + ACES shoulder）调。这是 `agt` preset 跟 `cst` 差这么多的原因。
- **`PPV_Shoot`（Level 里的 PostProcessVolume）会抢权**，让 SceneCapture 自己的 EV override 失效。`neutralize_ppv()` 函数会清掉 PPV 的曝光 override，启动时自动调用。
- **`r.PostProcessing.PropagateAlpha=2`** 是必须的，否则 alpha 通道拿不到角色 silhouette。`01_setup.py` 写进了 ini，需要重启 UE 生效。
- **个别 mesh 会让 UE crash**（Array OOB 或 LOD reduction assert），加到 `BAD_MESH_SUBSTRINGS` 跳过即可。
- **DokiDoki_Const_v2_back 显得太小**、**Yang_Odd_v0_front 宠物挡脸** —— 已知 bad case，相机自适应/挂件挂载逻辑需要后续单独调。

## 出错怎么办

把 UE 的 **Output Log**（Window → Developer Tools → Output Log）截图发出来。常见情形：

- **UE 版本 API 差异** → 函数名/枚举改了，需要按版本适配
- **角色资源路径不对** → 改 `SEARCH_DIRS`
- **alpha 没有透明** → 确认 `01_setup.py` 跑过且重启了 UE
- **某个 mesh 一渲就 crash** → 加 `BAD_MESH_SUBSTRINGS`

## 输出后处理

`03_batch.py` 跑完每张 PNG 会自动：
1. 反相 alpha（UE 输出 1−coverage，转成标准 coverage）
2. Unpremultiply RGB
3. 写回原文件

所以输出可以直接当 RGBA PNG 用。

## 输出目录命名规则（伊瑟资产）

`04_viewer.py` 按下面的规则把「同一角色的不同套装」聚合成一张卡，便于查看：

| 类型 | 路径模式 | 角色 ID | 套装/变体字段 |
|---|---|---|---|
| **Agt** | `Agt/Agt_<Name>/SK_..._LOD0` | `Agt_<Name>` | 无（1 角色 = 1 mesh） |
| **Cst** | `Cst/Cst_<Char>/Cst_<Char>_<Style>/SK_..._LOD0` | `Cst_<Char>` | `_Const` / `_Disor` / `_Hollow` / `_Light` / `_Odd` — 觉构 / 觉错 / 觉空 / 觉光 / 觉异 五种觉醒；`_1` `_2` 后缀是同套装的造型/颜色变体 |
| **Chr 男/女主** | `Chr/Chr_Boy_Home_<Theme>/<Theme>_<Color>/SK_..._LOD0` | `Chr_Boy_Home` / `Chr_Girl_Home` | `_Theme`（Crown / Dragon / Summer / Eveningdress / SpringFestival / Sw_*）+ `_Color`（Blackgold / Whitepurple / Greenpink…） |
| **Chr Friday** | `Chr/Chr_Friday_<Series>/<Series>_<Variant>/SK_Agt_Friday_..._LOD0` | `Chr_Friday` | `_Series`（Demon / Heromask / Fantasy / Interstate5 / Thorn / GoldenSpring）+ `_Variant`（同系列内多变体）⚠️ mesh 文件名前缀是 `SK_Agt_Friday_*` 是项目历史遗留 |
| **Chr 其他 NPC** | `Chr/Chr_<Name>/SK_..._LOD0` | `Chr_<Name>` | 一般无变体 |

如果换项目，需要改 `04_viewer.py` 里的 `CHR_MERGE_PREFIXES` 和 `parse_role()` / `variant_label()` 适配新项目的命名约定。

完整的角色资产清单（每个角色 ID 下挂了哪些套装/颜色变体）由 `05_manifest.py` 扫描输出目录生成到 `docs/characters.json`；该清单属项目专有素材，未随本仓库公开。
