# UE 角色参考图批量渲染 — 伊瑟 / eden（UE 4.26）版

`ue-char-ref-render` 的 **伊瑟 UE4.26（eden 工程）** 适配版。

- 渲染框架基于 `ue_scripts_tli`（火炬之光 UE4.26 版）的 UE4.26 兼容层；出图方案 eden 实测后定为 **无灯 final color + 后处理**（见下文），灰底 (96,96,96) RGB。
- 资产/命名沿用 `ue_scripts`（伊瑟 UE5 版）：`Agt / Cst / Chr` 体系（Prop/Thrown 道具不渲）。
- **必须在交互编辑器里跑**（无头 spawn 角色会崩，见下文）。

工程：`D:\eden_Deval_ArtSrc_Johnx\GameProject\GameUE_cpp.uproject`（伊瑟的 UE4.26 版）。

## ⚠️ 运行方式：必须在「交互式编辑器 + 激活的 3D 视口」里跑（重要，踩坑结论）

经实测，eden 这台机器上**无头渲染走不通**，只能开编辑器交互跑。原因（2026-06 实测）：

1. eden 的 GUI 编辑器**默认打不开**：启动会弹「模块过期/重编」框（本机无 VS 无法重编），点"否"就退。
   **加 `-unattended` 可跳过这个框、编辑器就能正常打开**（`open_editor.bat` 就是干这个的）。
2. 但**无头**（`-run=pythonscript` commandlet 或 `-ExecCmds`）下渲染**必崩**：spawn 角色 / 相机 /
   SceneCapture2D / SkeletalMeshActor 时，UE 编辑器的 actor 工厂放置要读**交互式 3D 视口的光标**
   （`GetCursorWorldLocationFromMousePos`），无头没有视口 → C++ 访问违例崩溃。灯/PPV 不走放置所以不崩。
3. 想用 `new_object` 建组件绕开 spawn：这个**定制引擎裁掉了** `register_component` /
   `add_instance_component`，组件注册不进场景 → 渲不出。

**结论**：把 mesh 弄进可渲染场景这一步，无头下做不到。tli/UE5 当初能跑，是因为它们都在**正常打开、有真视口**的编辑器里跑。

### 正确跑法（交互）

```
open_editor.bat              :: 用 -unattended 打开 eden 编辑器
```
1. 等编辑器**完全打开**。
2. **在左上角 3D 视口里点一下、鼠标移上去**，让它成为「当前激活视口」（关键，否则 spawn 仍会读到空视口而崩）。
3. `Window → Developer Tools → Output Log`，在底部命令框依次输入：
   ```
   py "D:\code\ue_scripts_eth_ue4\01_setup.py"
   py "D:\code\ue_scripts_eth_ue4\03_batch.py"
   ```
   （03 先把 `WHITELIST_MESH_PATHS = _ETH_MIX_TEST` 跑小批目检，OK 再设 `[]` 跑全量。）

> `run_ue.bat`（无头 `-unattended`）保留，仅适用于**不 spawn 的** python（如资产探查/清单类）；
> 渲染脚本(01/02/03)在 eden 上**不能**用它，必须走 `open_editor.bat` 交互跑。
> 若交互跑仍崩（视口聚焦不足），说明本机这套定制引擎环境支撑不了，需要一台能**正常构建/打开** eden
> 编辑器的环境（CI 同步匹配二进制 / 装了 VS 的机器）——脚本与配置已就绪，到那种环境直接能用。

## 出图方案（eden 实测定稿 2026-06）

UE4.26 + eden 定制引擎实测（编辑器可正常打开后用诊断网格重测，**推翻早期 base color 方案**）：
- **打灯(sky/dir)会把伊瑟 NPR cel-shader 冲过曝糊白**；**EV bias / 白平衡 在 SceneCapture 失效**（调不动）；
- → 统一用 **无灯 `final color`（真实游戏渲染色，含光照/自发光/NPR 描边）+ ACES tonemapper**。
- 产物 **灰底 (96,96,96) RGB**（`finalize` 的 `TRANSPARENT_BG=False`；设 `True` 改输出透明 RGBA）。

- **分组预设** `PRESETS`（`preset_for_mesh()` 按路径分流；三组 agt/cst/chr 起点一致、各自独立可分别精调）：
  统一 `capture="final"`、无灯(`sky=dir=0`)、`sat=1.3`（诊断挑定：1.4 肤色偏橙、1.0 浅肤偏白）、ACES `shoulder=0.5`。
- **温和提亮**（`finalize` 内联，不再依赖 `post_process.py`）：以前景亮度 `brighten_pct=45` 分位为锚缩放到 `brighten_target=135`，`scale∈[1, brighten_max=2.5]`，只提不压 → 救暗角色、正常亮度不动。
- **背景/alpha**：`PropagateAlpha=2` 导出 coverage，`finalize` 反相 alpha + 反预乘 RGB，再合成灰底（或输出透明）。
- **贴图加载坑**：长批量 + `TextureStreaming 0` 会显存堆满 → 截到棋盘格占位/错色。修法：`WARMUP_CAPTURES=6` + 每个 mesh `collect_garbage`（已设）。
- **取景**（`get_fit_bounds` + `fit_camera`）：用**整体包围盒**（含武器/坐骑/披风，修早期"缺件"）；竖长画面「**完整不裁、宽角色偏小**」（`FILL_RATIO_W=0.88`）。

> `post_process.py` 还含 `composite`（打灯 base 身体 + 无灯 final 红角叠加），用于 Agt 红色 emissive 发光角色的单独处理（未并入主流程，见 BAD_CASES）。

## 资产结构（已探查 eden 工程）

`SEARCH_DIRS = ["/Game/ArtResources/Characters"]`，共 674 个 SkeletalMesh：

| 类型 | 数量 | 命名 |
|---|---|---|
| Agt 探子 | 81 | `Agt/Agt_<Name>/SK_Agt_<Name>_LOD0`（+ `_1` 皮肤变体） |
| Cst 装扮 | 479 | `Cst/Cst_<Char>/Cst_<Char>_<觉醒>/SK_..._LOD0`（觉醒=Const/Disor/Hollow/Light/Odd） |
| Chr 角色 | 102 | 男/女主多套装、Friday 系列、其他 NPC |
| Prop / Thrown | 4 | 道具/投掷物 |

排除：`Sub1/2/3`（配件：手机/眼镜等）、`Weapon/VFX/Effect/Anim`。eden 用 `_LOD0` 后缀（无 _LOD1/2/3 独立资产）。

## 执行流程

UE 内脚本(01/02/03)**必须在交互编辑器里跑**(`open_editor.bat` 开 → 点击激活 3D 视口 → Output Log 输入 `py "完整路径\xx.py"`)。**无头不行**(spawn 角色崩，见上文)。

| 步骤 | 在哪跑 | 说明 |
|---|---|---|
| `01_setup.py` | 交互编辑器 | 建 `L_CharRefShoot` 关卡 + 灯/相机/PPV；改 `DefaultEngine.ini`（PropagateAlpha=2 等）|
| `02_test.py` | 交互编辑器 | 渲 1 个角色冒烟验证（可选） |
| `02b_light_test.py` | 交互编辑器 | 诊断对比网格（多角色×多档：base-vs-final / 灯光 / sat 调参用） |
| `03_batch.py` | 交互编辑器 | 批量渲染。**先 `WHITELIST_MESH_PATHS=_XXX_TEST` 跑分组小批目检，OK 再设 `[]` 跑全量**；`SEARCH_DIRS` 控制渲哪几组 |
| `grid_sheet.py` | 外部 Python | 把一组结果(每角色取一视角)拼成带名字大图，整组 review 调参用 |
| `04_viewer.py` | 外部 Python | 扫输出生成 `viewer.html`（按 Agt/Cst/Chr 分组、多套装合卡、点图放大） |
| `05_manifest.py` | 外部 Python | 生成 `docs/characters.json`（命名规范 + 全角色清单） |
| `06_compose.py` | 外部 Python | 每个 mesh 4 视角横向拼成黑底大图 |

> 调参工作流：每组 `WHITELIST=_XXX_TEST` 跑小批 → `grid_sheet.py` 出拼图整组看 → 调该组 `PRESETS["xxx"]` → 满意换下一组 → 全部 OK 设 `[]` 跑全量。个别角色不好当 bad case(见 `BAD_CASES.md`)。

外部脚本用本机带 PIL/numpy 的 Python（各脚本顶部 `EXTERNAL_PYTHON` 常量，默认 `Python312`）。

```
python 04_viewer.py D:/角色识别数据/伊瑟_UE4
python 05_manifest.py D:/角色识别数据/伊瑟_UE4
python 06_compose.py D:/角色识别数据/伊瑟_UE4
```

## 输出目录

- 全量：`D:/角色识别数据/伊瑟_UE4/`（镜像 UE 路径）
- 小批验证：`D:/角色识别数据/伊瑟_UE4_whitelist/`
- 拼图：`D:/角色识别数据/伊瑟_UE4_compose/`

## 注意点

- `01_setup.py` 会改 eden 的 `Config/DefaultEngine.ini`（已自动备份 `.bak_charref`）。**本地用、不要提交到 P4**，以免影响别人/打包。
- preset 是起步值，正式跑前务必用 `_ETH_MIX_TEST` 小批**人眼目检**（Agt/Cst/Chr 都出图、灰底干净、4 视角正确、肤色不橙不白）再跑全量。
- 中途挂了重跑会续传（`03_batch.py` 的 `SKIP_EXISTING=True`；小批验证期可设 `False` 覆盖重渲）。
