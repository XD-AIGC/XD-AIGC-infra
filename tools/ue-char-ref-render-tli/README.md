# UE 角色参考图批量渲染 — 火炬之光（TLI / UE 4.26）版

`ue-char-ref-render`（5.3 / 伊瑟 版）的 **UE 4.26 + 火炬之光** 适配版。框架与渲染原理一致，差异在「版本兼容层 + 项目配置 + 出图取色方案」。

## 与 5.3/伊瑟 版的关键差异

1. **UE 4.26 兼容层**：4.26 无 `LevelEditorSubsystem` / `EditorActorSubsystem`，`get_level_subsystem()` / `get_actor_subsystem()` 改为「有子系统则用、否则回退 `EditorLevelLibrary`」（level/actor 方法名一致）。资产类型读取、RenderTarget 创建均有多路 fallback。
2. **目标目录**：`/Game/Art/Characters`（Hero / Monster〔含 Boss〕/ NPC / Pet / Token + 各 _Showcase）+ `/Game/Art/Fashion/Heros`。SkeletalMesh 都在 `各角色/Meshes/SK_*_Skin`（`MESH_REQUIRE_PATH="/Meshes/"` 正向过滤；排除 `_Skeleton`/`_Physics`/`ShadowProxy`/`_Proxy`）。无 `_LOD` 后缀；部分角色多套皮肤全渲。
3. **输出**：`D:/角色识别数据/火炬之光/`（镜像 UE 路径）。

## 出图取色方案（最重要，反直觉）

火炬之光材质分两类，且这套 SceneCapture 对它们行为很特殊，踩坑后的最终方案：

- **每个 mesh 同时截 `base color` + `final color`，后处理逐像素 `np.maximum` 取较亮者合并**（`03_batch.py` 的 `combine_max`）。Lit 怪物 base 亮、NPR 英雄/Boss final 亮，max 自动各取所长，**无需按类别分类**。
- **必须关贴图流式 `r.TextureStreaming 0`**（+ `FullyLoadUsedTextures` / `Boost`）：否则阻塞式 Python 循环里贴图来不及流入 → 首帧黑剪影（这是黑剪影的主因）。
- 每个 mesh 截图前**空跑 `WARMUP_CAPTURES` 帧预热**，驱动贴图/shader 就绪。
- 后处理**丢弃 alpha、拍平黑底 RGB**：NPR 的 `PropagateAlpha` 覆盖度 matte 不可靠（alpha 均值极低），交付是黑底拼图不需透明。
- ⚠️ **曝光 / 灯光对这套 SceneCapture 完全无效**（dir 60→300、EV 0→8 零变化），不要再去调灯光/曝光。

## 执行流程

| 步骤 | 在哪跑 | 说明 |
|---|---|---|
| `01_setup.py` | UE 内 | 建场景 + 改 `DefaultEngine.ini`（自动指向当前 TLI 工程）→ **跑完重启 UE** |
| `02_test.py` | UE 内 | 渲 1 个角色验证 alpha / 朝向 / 出图 |
| `02b_light_test.py` | UE 内 | 单角色多参数 sweep 出 `grid.png`（用于诊断；本项目已确定走 base+final 双截）|
| `03_batch.py` | UE 内 | 全量渲染（先 `WHITELIST_MESH_PATHS = _TLI_MIX_TEST` 跑小批验证，OK 再设 `[]` 跑全量）|
| `04_viewer.py` | 外部 Python | 生成 `viewer.html`：按角色文件夹分组、按 Hero/Monster/Pet/Token/NPC/Fashion 类别筛选、多皮肤合卡 |
| `05_manifest.py` | 外部 Python | 生成 `characters.json`：命名规范 + 全角色清单（同角色多皮肤）|
| `06_compose.py` | 外部 Python | 每个 mesh 的 4 视角横向拼成一张黑底大图 |

UE 4.26 定制版菜单无 Tools，跑脚本用控制台：`py "D:/.../ue_scripts_tli/01_setup.py"`。外部脚本用本机带 PIL/numpy 的 Python。

## 已知 bad case（约 1%）

黑剪影已从 24% 降到 ~1.1%。剩余多为特效/半透明 mesh（如能量柱）与深色精英怪——前者 base/final 都近黑，后者底色本身暗。后续可加「逐图提亮」优化。
