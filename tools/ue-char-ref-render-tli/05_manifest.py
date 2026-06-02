"""扫输出目录，生成 characters.json —— 火炬之光角色资产清单 + 命名规范。

用法：
  python 05_manifest.py                                   # 扫 D:/角色识别数据/火炬之光 → 同目录 characters.json
  python 05_manifest.py <扫描根> <输出.json>

输出结构：
  {
    "naming_convention": {...},     # 路径/命名规则说明
    "stats": {...},                 # 角色/mesh 计数、类别分布
    "roles": [                      # 按角色文件夹分组
      {
        "role_id": "BingHuoRen",
        "type": "Hero",
        "role_path": "Art/Characters/Hero/BingHuoRen",
        "skin_count": 3,
        "skins": [
          {"mesh_name": "SK_BingHuoRen_Skin", "rel_path": "Art/.../SK_BingHuoRen_Skin.SK_BingHuoRen_Skin"},
          ...
        ]
      },
      ...
    ]
  }
"""
import os
import sys
import json
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_v = __import__("04_viewer")  # 复用 TLI 版 scan / parse_role


NAMING_CONVENTION = {
    "description": (
        "火炬之光（Torchlight / TLI，UE 4.26）角色参考图资产命名约定。"
        "渲染产物镜像 UE Content 路径：Art/<TopDir>/<Type>/<角色文件夹>/Meshes/<皮肤名>/v<n>_<view>.png"
    ),
    "source_dirs": [
        "/Game/Art/Characters",       # Hero / Monster(含 Boss) / NPC / Pet / Token + 各 _Showcase
        "/Game/Art/Fashion/Heros",    # 英雄时装 Hero / Hero_Showcase
    ],
    "types": {
        "Hero": "英雄（NPR 卡通材质，渲染走 final color）",
        "Hero_Showcase": "英雄展示版",
        "Monster": "怪物（含 Boss/Elite 子目录；多为 Lit，Boss 部分为 NPR）",
        "NPC": "NPC",
        "NPC_Showcase": "NPC 展示版",
        "Pet": "宠物",
        "Pet_Showcase": "宠物展示版",
        "Token": "随从/图腾/道具类",
        "Token_Showcase": "Token 展示版",
        "Fashion": "英雄时装（Fashion/Heros 下）",
    },
    "rules": {
        "role_grouping": "按「角色文件夹」（到 Meshes 上一级目录）分组；同文件夹下多个 SK_*_Skin 视为同角色的不同皮肤。",
        "role_id": "角色文件夹名（展示用，可能跨类别重名，role_path 才唯一）。",
        "type": "Characters 的下一级目录名（Boss/Elite 归入其上层如 Monster）；Fashion 路径统一记为 Fashion。",
        "skin": "每个 SkeletalMesh = 一个皮肤；mesh_name 形如 SK_<角色>[<序号>]_Skin（去掉 UE 资产双后缀）。",
        "render": (
            "每皮肤 4 视角（front/side/back/3-4），黑底 1024×2304 PNG。"
            "出图同时截 base+final 两种 capture source、逐像素取较亮者合并，"
            "通吃 Lit(怪物 base 亮)/NPR(英雄·Boss final 亮)；曝光/灯光对该 SceneCapture 无效。"
        ),
    },
    "fields": {
        "role_path": "角色文件夹相对扫描根的路径（唯一分组键）",
        "rel_path": "皮肤 mesh 目录相对扫描根的路径（到 SK_..._Skin 目录）",
        "mesh_name": "SkeletalMesh 资产名（去 UE 双后缀），同 role_id 下多个 = 同角色多皮肤",
    },
}


def _role_path_of(group):
    """从某角色组的第一个皮肤 rel 推出角色文件夹路径（到 Meshes 上一级）。"""
    rel = group["variants"][0]["rel"]
    parts = rel.split("/")
    if "Meshes" in parts:
        return "/".join(parts[:parts.index("Meshes")])
    return "/".join(parts[:-1])


def build_manifest(root):
    items = _v.scan(root)
    total = sum(len(g["variants"]) for g in items)
    multi = [g for g in items if len(g["variants"]) > 1]
    by_type = Counter(g["type"] for g in items)

    roles_out = [
        {
            "role_id": g["roleId"],
            "type": g["type"],
            "role_path": _role_path_of(g),
            "skin_count": len(g["variants"]),
            "skins": [
                {"mesh_name": v["name"], "rel_path": v["rel"]}
                for v in g["variants"]
            ],
        }
        for g in items
    ]

    return {
        "naming_convention": NAMING_CONVENTION,
        "stats": {
            "total_roles": len(items),
            "total_meshes": total,
            "multi_skin_roles": len(multi),
            "max_skins": max((len(g["variants"]) for g in multi), default=0),
            "max_skins_role": (
                max(multi, key=lambda g: len(g["variants"]))["roleId"] if multi else None
            ),
            "roles_by_type": dict(by_type),
        },
        "roles": roles_out,
    }


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else r"D:/角色识别数据/火炬之光"
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "characters.json")
    if not os.path.isdir(root):
        print(f"[manifest] 目录不存在: {root}")
        sys.exit(1)
    manifest = build_manifest(root)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    s = manifest["stats"]
    print(f"[manifest] 扫描 {root}")
    print(f"[manifest] {s['total_roles']} 角色 / {s['total_meshes']} mesh / "
          f"{s['multi_skin_roles']} 多皮肤（最多 {s['max_skins']} 个: {s['max_skins_role']}）")
    print(f"[manifest] 类别分布: {s['roles_by_type']}")
    print(f"[manifest] 已写入: {out}")


if __name__ == "__main__":
    main()
