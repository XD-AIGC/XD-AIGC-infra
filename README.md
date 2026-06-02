# XD-AIGC-infra

XD-AIGC 组基建：常用工具、CLI、Python 脚本等基础库。

> 使用各工具前请先建立对应的 conda 环境（见各子目录说明）。

## 工具

| 目录 | 说明 |
|---|---|
| [`tools/ue-char-ref-render/`](tools/ue-char-ref-render/) | UE 角色参考图批量渲染流水线：把 SkeletalMesh 角色按 4 视角 + 透明背景批量渲染成 PNG，并生成 HTML 预览 / 资产清单 / 拼接参考图（UE5 版） |
| [`tools/ue-char-ref-render-tli/`](tools/ue-char-ref-render-tli/) | 上面流水线的 **UE 4.26 + 火炬之光** 适配版：4.26 兼容层、按角色文件夹/皮肤分组、base+final 双截取较亮合并出图 |
