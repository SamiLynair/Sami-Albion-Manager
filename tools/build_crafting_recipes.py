"""Build compact offline recipes from ao-data/ao-bin-dumps items.json.

Usage: python tools/build_crafting_recipes.py /path/to/items.json
Source: https://github.com/ao-data/ao-bin-dumps (Albion game-data dump).
The primary/standard recipe is used when the game lists multiple alternatives.
"""

import gzip
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "samialbion/assets/catalog.json.gz"
DESTINATION = ROOT / "samialbion/assets/crafting_recipes.json.gz"


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def material_id(resource, known):
    name = resource.get("@uniquename", "")
    level = str(resource.get("@enchantmentlevel", "0"))
    if level not in ("", "0") and f"{name}@{level}" in known:
        return f"{name}@{level}"
    return name


def recipe(requirements, known):
    for requirement in as_list(requirements):
        if not isinstance(requirement, dict):
            continue
        materials = []
        for resource in as_list(requirement.get("craftresource")):
            if not isinstance(resource, dict):
                continue
            name = material_id(resource, known)
            amount = int(resource.get("@count", "0"))
            if amount > 0 and name in known:
                materials.append([name, amount])
            elif amount > 0:
                materials = []
                break
        if materials:
            return {"amount": int(requirement.get("@amountcrafted", "1")), "materials": materials}
    return None


def main(source):
    with gzip.open(CATALOG, "rt", encoding="utf-8") as file:
        entries = json.load(file)["items"]
        known = {key for key, value in entries.items()
                 if (value.get("fr") or "").strip() or (value.get("en") or "").strip()}
    with open(source, encoding="utf-8") as file:
        dump = json.load(file)["items"]
    result = {}
    for section in dump.values():
        for entry in as_list(section):
            if not isinstance(entry, dict):
                continue
            name = entry.get("@uniquename", "")
            if name not in known:
                continue
            base = recipe(entry.get("craftingrequirements"), known)
            if base:
                result[name] = base
            for enchanted in as_list(entry.get("enchantments", {}).get("enchantment") if isinstance(entry.get("enchantments"), dict) else None):
                level = enchanted.get("@enchantmentlevel")
                if level and f"{name}@{level}" in known:
                    alternate = recipe(enchanted.get("craftingrequirements"), known)
                    if alternate:
                        result[f"{name}@{level}"] = alternate
    with gzip.open(DESTINATION, "wt", encoding="utf-8", compresslevel=9) as file:
        json.dump(result, file, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    print(f"{len(result)} recipes → {DESTINATION}")


if __name__ == "__main__":
    main(sys.argv[1])
