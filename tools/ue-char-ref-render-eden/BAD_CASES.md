# Bad cases（参数对整组 OK，个别角色效果不好，单独记录、后续单独处理）

记录格式：`角色 mesh — 现象 — 根因 — 可能的单独处理`

## Cst 组（参数已定型：capture=base, brighten_pct=70, target=170, max=15）

- **Cst_Arielle_Const** — 裸露皮肤(腿)偏橙 — 皮肤材质 base color 槽是占位橙色，真实肤色只在 NPR 光照里 — 后续可单独做颜色重映射或单独用 final 极弱灯。
- **Cst_Viper_Odd** — 同上，裸露皮肤偏橙 — 同上 — 同上。
- **Cst_Bornova_Odd** — 取景偏小 — 推测 actor bounds 含远伸组件(武器/披风/特效)把主体缩小 — 后续可单独收紧取景 / 忽略远伸组件。
- **Cst_SweetDream_Const** — 黑色手脚末端与纯黑背景重叠、剪影丢失 — 角色末端接近纯黑 — 下游需纯黑底，故保留；后续可单独描边或局部提亮。

### 全量后用户 review 的 Cst bad case（已确认，材质/资产层面，渲染参数无解）

- **全黑（水/透明/特殊材质）**：`Cst_RC77_Water`、`Cst_Snake_Hollow`、`Cst_TiamatMorph_Hollow`、`Cst_DokiDoki_Disor` — base 近黑，需该材质单独处理或弃用。
- **看不清/薄片异形**：`Cst_PaperCrane_Hollow`、`Cst_Tailspin_Odd`、`Cst_TrainConductorState2_Odd`（武器主导/薄片）。
- **缺件**：`Cst_Febian`(马未出)、`Cst_Prisoner`(脚下) — 组件可能不在主 SK / 无碰撞被取景排除。`Cst_GhostMagic`(杆) 修复后已回。
- **皮肤偏白**：`Cst_BloodDiamond_Hollow` 等 — 皮肤非橙占位色，skin_fix 不普适。
- **Jellyfish**：渲染成错误图标（mesh 本身坏）。
- **宽翅膀角色偏小**：已按用户选择「完整不裁」处理（宽的偏小、可接受），非 bad case。
- 已排除不渲：`*_Rig`/`Tentacle`/`Suitcase` 零件、`NPC`/`QuestionMark`/`Preview`/`_Test`。

## Chr 组

- **眼睛纯黑**（Friday 系列等）：`Chr_Friday`、`Friday_Thorn_Crown`、`Summer_HoloSinger`、`Summer_BeachStar`、`Spring_VoidViolet`、`NaughtyGhost_WizardHat`、`NaughtyGhost_CandleLight` 等 — 眼睛是特殊材质，base 截不到（同 Agt 红 emissive）→ UE/材质本身，渲染侧无解。
- **Fleet 衣服色**（`Chr_Girl_Home_Fleet`/`Chr_Boy_Home_Fleet`）：base 出材质真实色；若与游戏内不同，是游戏用光照/NPR 着色所致 — 待确认是否接受。

## Agt 组（参数已定型：capture=base, brighten_pct=60, target=180, max=30, 不开 skin_fix）

Agt 角色风格极杂，base 直出对多数 OK（Halloween/MirrorBee/Supernova/WhiteBlast 好）。以下 bad case：

- **Agt_Alicorn**（及红色 emissive 发光为主的探子）— base 不含 emissive，标志性红角丢失 — 需单独"合成 pass"(打灯 base 身体 + 无灯 final 红角叠加，见 post_process.py 的 composite 逻辑，已验证 Alicorn 可行)。
- **Agt_Amber** — base 身体近乎纯黑(albedo 即黑)，自适应提亮救不回(near-0 像素) — 需单独打灯(final+light)或合成。
- **Agt_CursedFrog / Agt_RetributionAngel** — 略暗(身上亮部件抬高了自适应锚点) — 可接受，或单独降 brighten_pct 提一提。

> 计划：主流程(全量)跑完后，对"红色发光为主 + 近黑"的 Agt 单独跑一个 composite pass。

## Prop 组

（待评估）
