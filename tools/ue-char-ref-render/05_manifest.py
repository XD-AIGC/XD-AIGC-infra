"""扫输出目录，生成 docs/characters.json —— 角色资产清单 + 命名规范。

用法：
  python 05_manifest.py                                  # 扫 D:/ref_shots/full → 写到 docs/characters.json
  python 05_manifest.py D:/ref_shots/full out.json       # 自定义输入/输出

输出结构：
  {
    "naming_convention": {...},     # 路径命名规则说明
    "stats": {...},                 # 角色/mesh 计数
    "roles": [                      # 按角色 ID 分组的资产清单
      {
        "role_id": "Cst_Cabala",
        "type": "Cst",
        "variant_count": 4,
        "variants": [
          {"name": "Hollow", "rel_path": "...", "mesh_name": "SK_Cst_Cabala_Hollow_LOD0"},
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

# 复用 04_viewer 的 parse_role / variant_label / scan
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_v = __import__("04_viewer")


NAMING_CONVENTION = {
    "description": (
        "基于伊瑟 UE 项目的角色资产命名约定。路径形如 "
        "ArtResources/Characters/<TYPE>/<ROLE_DIR>/(<VARIANT_DIR>/)?SK_<...>_LOD0/v<n>_<view>.png"
    ),
    "type_words": list(_v.TYPE_WORDS),
    "chr_merge_prefixes": list(_v.CHR_MERGE_PREFIXES),
    "cst_awakening_styles": {
        "Const": "觉构",
        "Disor": "觉错",
        "Hollow": "觉空",
        "Light": "觉光",
        "Odd": "觉异",
    },
    "types": {
        "Agt": {
            "pattern": "Agt/Agt_<Name>/SK_..._LOD0",
            "role_id_rule": "Agt_<Name>",
            "variant_rule": "无 — 1 角色 = 1 mesh",
            "example": "Agt/Agt_Alicorn/SK_Agt_Alicorn_LOD0 → 角色 Agt_Alicorn",
        },
        "Cst": {
            "pattern": "Cst/Cst_<Char>/Cst_<Char>_<Style>(_<idx>)?/SK_..._LOD0",
            "role_id_rule": "Cst_<Char>",
            "variant_rule": (
                "套装关键词 = Const/Disor/Hollow/Light/Odd（觉醒五系）；"
                "_1 _2 后缀 = 同套装的造型/颜色变体"
            ),
            "example": (
                "Cst/Cst_Cabala/Cst_Cabala_Hollow/SK_Cst_Cabala_Hollow_LOD0 "
                "→ 角色 Cst_Cabala / 变体 Hollow（觉空）"
            ),
        },
        "Chr": {
            "pattern": "多种 sub-pattern，见 sub_patterns",
            "role_id_rule": (
                "若 char_dir 以 Chr_Boy_Home / Chr_Girl_Home / Chr_Friday 开头 "
                "→ 合并到该 prefix；否则 = char_dir"
            ),
            "sub_patterns": {
                "single_npc": {
                    "pattern": "Chr/Chr_<Name>/SK_..._LOD0",
                    "example": "Chr/Chr_AgentM/SK_Chr_AgentM_LOD0 → 角色 Chr_AgentM",
                },
                "player_outfit": {
                    "pattern": "Chr/Chr_Boy_Home_<Theme>/<Theme>_<Color>/SK_..._LOD0",
                    "role_id_rule": "Chr_Boy_Home / Chr_Girl_Home（玩家男/女主固定基底）",
                    "variant_rule": "_<Theme>（Crown/Dragon/Summer/Eveningdress/SpringFestival/Sw_*）+ _<Color>（Blackgold/Whitepurple/Greenpink…）",
                    "example": (
                        "Chr/Chr_Boy_Home_Eveningdress/Eveningdress_Blackgold/"
                        "SK_Chr_Boy_Home_Ed_Blackgold_LOD0 "
                        "→ 角色 Chr_Boy_Home / 变体 Ed_Blackgold（晚礼服·黑金）"
                    ),
                },
                "friday_series": {
                    "pattern": "Chr/Chr_Friday_<Series>/<Series>_<Variant>/SK_Agt_Friday_..._LOD0",
                    "role_id_rule": "Chr_Friday（基底）",
                    "variant_rule": "_<Series>（Demon/Heromask/Fantasy/Interstate5/Thorn/GoldenSpring）+ _<Variant>",
                    "warning": "mesh 文件名前缀是 SK_Agt_Friday_*（不是 Chr）— 项目历史遗留命名不一致",
                    "example": (
                        "Chr/Chr_Friday_Heromask/Heromask_Hero/SK_Agt_Friday_Heromask_Hero_LOD0 "
                        "→ 角色 Chr_Friday / 变体 Heromask_Hero"
                    ),
                },
            },
        },
        "Prop": {
            "pattern": "Prop/Prop_<Name>/SK_..._LOD0",
            "role_id_rule": "Prop_<Name>",
            "variant_rule": "一般无变体",
            "example": "Prop/Prop_Bottle01/SK_Prop_Bottle01",
        },
        "Thrown": {
            "pattern": "Thrown/<...>",
            "role_id_rule": "按第二段目录原样分组",
        },
    },
    "fields": {
        "rel_path": "相对扫描根目录的路径（到 mesh 所在目录）",
        "mesh_name": "SK_..._LOD0 文件夹名（去 .重复后缀）",
        "role_id": "角色 ID，同 role_id 的多个 variant 视为「同角色不同套装/颜色」",
        "variant.name": "套装/颜色标签，已去除角色 ID 前缀；重名时追加 [mesh_name] 后缀去重",
    },
}


def build_manifest(root):
    items = _v.scan(root)
    # 给每个 variant 加上 mesh_name 字段
    for g in items:
        for v in g["variants"]:
            mesh_name = v["rel"].split("/")[-1].split(".")[0]
            v["mesh_name"] = mesh_name
    total = sum(len(g["variants"]) for g in items)
    multi = [g for g in items if len(g["variants"]) > 1]
    from collections import Counter
    by_type = Counter(g["type"] for g in items)

    roles_out = [
        {
            "role_id": g["roleId"],
            "type": g["type"],
            "variant_count": len(g["variants"]),
            "variants": [
                {"name": v["name"], "rel_path": v["rel"], "mesh_name": v["mesh_name"]}
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
            "multi_variant_roles": len(multi),
            "max_variants": max((len(g["variants"]) for g in multi), default=0),
            "max_variants_role": (
                max(multi, key=lambda g: len(g["variants"]))["roleId"] if multi else None
            ),
            "roles_by_type": dict(by_type),
        },
        "roles": roles_out,
    }


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else r"D:/ref_shots/full"
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "docs", "characters.json"
    )
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
          f"{s['multi_variant_roles']} 多套装（最多 {s['max_variants']} 个: {s['max_variants_role']}）")
    print(f"[manifest] 类型分布: {s['roles_by_type']}")
    print(f"[manifest] 已写入: {out}")


if __name__ == "__main__":
    main()
