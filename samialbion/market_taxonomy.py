"""Offline, three-level Albion marketplace classification.

The two game-defined shop category keys come from a bundled snapshot of
ao-bin-dumps/items.xml. The final item-family level is derived locally from
localized item names, with conservative fallbacks for newer entries.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import re


SHOP_INDEX_PATH = Path(__file__).resolve().parent / "assets" / "market_shop_index.json.gz"

# The labels and order visible at Albion's marketplace.
MARKET_ROOTS = (
    "Armes", "Armure de Poitrine", "Armure de Tête", "Armure de Pieds",
    "Armes Secondaires", "Capes", "Sacs", "Monture", "Consommable",
    "Équipement de Récolte", "Fabrication", "Artefact", "Agriculture",
    "Mobilier", "Cosmétique", "Autre",
)

WEAPONS = {
    "axe": "Hache", "dagger": "Dague", "hammer": "Marteau",
    "mace": "Masse", "quarterstaff": "Long bâton", "spear": "Lance",
    "sword": "Épée", "knuckles": "Gants de guerre",
    "arcanestaff": "Bâton ésotérique", "cursestaff": "Bâton damné",
    "firestaff": "Bâton de feu", "froststaff": "Bâton de givre",
    "holystaff": "Bâton béni", "naturestaff": "Bâton naturel",
    "shapeshifter": "Bâton métamorphe", "bow": "Arc", "crossbow": "Arbalète",
}
OFFHAND = {
    "book": "Livres", "orb": "Orbes", "totem": "Totems",
    "horn": "Cornes", "torch": "Torches", "shield": "Boucliers",
}
MOUNTS = {
    "ridinghorse": "Chevaux", "armoredhorse": "Chevaux blindés", "ox": "Bœufs",
    "mule": "Mules", "cougar": "Félins", "direwolf": "Loups",
    "direbear": "Ours", "direboar": "Sangliers",
    "swampdragon": "Dragons des marais", "giantstag": "Cerfs",
    "rare_mount": "Montures rares", "battle_mount": "Montures de combat",
}
CONSUMABLES = {
    "cooked": "Nourriture", "potion": "Potions", "fishingbait": "Appâts",
    "fish": "Poissons", "maps": "Cartes", "kill_emotes": "Emotes",
    "other": "Autres consommables", "vanity": "Objets cosmétiques",
}
RESOURCES = {
    "fiber": "Fibre", "hide": "Peau", "ore": "Minerai", "rock": "Pierre brute",
    "wood": "Bois", "cloth": "Tissu", "leather": "Cuir",
    "metalbar": "Lingot", "stoneblock": "Bloc de pierre",
    "planks": "Planches", "other": "Autres matériaux",
}
FARMING = {
    "animals": "Animaux", "seed": "Graines", "journal": "Journaux",
    "farming": "Cultures", "cooked": "Produits alimentaires",
}
TOOLS = {
    "demolitionhammer": "Marteau de démolition", "fishing": "Canne à pêche",
    "pickaxe": "Pioche", "sickle": "Faucille", "skinningknife": "Couteau de dépeçage",
    "stonehammer": "Marteau de tailleur", "woodaxe": "Hache de bûcheron",
}
GATHERER = {
    "fiber": "Fibres", "fish": "Pêche", "hide": "Peaux",
    "ore": "Minerai", "rock": "Pierre", "wood": "Bois",
}
GEAR_SLOTS = {
    "helmet": "Casques", "armor": "Armures", "shoes": "Chaussures",
    "backpack": "Sacs de récolte",
}
MATERIALS = {
    "essence": "Essences", "rune": "Runes", "relic": "Reliques",
    "soul": "Âmes", "other": "Autres matériaux magiques",
}
EPITHETS = (
    " du grand maître", " du grand-maître", " de l'ancien", " de l'ancienne",
    " du maître", " de la maîtresse", " de l'expert", " de l'experte",
    " de l'adepte", " de l'apprenti", " du compagnon", " de l'initié",
    " du débutant", " du novice", " de la novice",
)
VARIANT_RE = re.compile(r"@\d+$")
TIER_RE = re.compile(r"^T\d+_")
LEVEL_RE = re.compile(r"_LEVEL[1-4]$")


def market_family_key(item_id: str) -> str:
    return LEVEL_RE.sub("", TIER_RE.sub("", VARIANT_RE.sub("", item_id)))


def family_title(name: str) -> str:
    value = name.strip()
    normalized = value.casefold().replace("’", "'")
    for ending in EPITHETS:
        if normalized.endswith(ending):
            return value[: len(value) - len(ending)].strip()
    return value


def _weapon_fallback(item_id: str) -> str:
    key = market_family_key(item_id).upper()
    for fragment, group in (
        ("CROSSBOW", "Arbalète"), ("BOW", "Arc"), ("CURSED", "Bâton damné"),
        ("FIRESTAFF", "Bâton de feu"), ("FROSTSTAFF", "Bâton de givre"),
        ("NATURESTAFF", "Bâton naturel"), ("HOLYSTAFF", "Bâton béni"),
        ("ARCANESTAFF", "Bâton ésotérique"), ("SHAPESHIFTER", "Bâton métamorphe"),
        ("QUARTERSTAFF", "Long bâton"), ("SPEAR", "Lance"),
        ("HAMMER", "Marteau"), ("DAGGER", "Dague"), ("KNUCKLE", "Gants de guerre"),
        ("GLOVE", "Gants de guerre"), ("SWORD", "Épée"), ("AXE", "Hache"),
        ("MACE", "Masse"), ("STAFF", "Bâton"),
    ):
        if fragment in key:
            return group
    return "Autres armes"


def _shop_path(shop: tuple[str, str], item_id: str, family: str) -> tuple[str, str, str]:
    category, sub = shop
    if category in ("melee", "magic", "ranged"):
        return "Armes", WEAPONS.get(sub, "Autres armes"), family
    if category == "armor":
        slot = sub.rsplit("_", 1)[-1]
        root = {"helmet": "Armure de Tête", "armor": "Armure de Poitrine",
                "shoes": "Armure de Pieds"}.get(slot, "Armure de Poitrine")
        material = sub.split("_", 1)[0]
        return root, {"cloth": "Tissu", "leather": "Cuir", "plate": "Plaque",
                      "unique": "Spécial"}.get(material, "Autre"), family
    if category == "offhand":
        return "Armes Secondaires", OFFHAND.get(sub, "Autres"), family
    if category == "accessories":
        root = "Capes" if sub == "cape" else "Sacs"
        return root, root, family
    if category == "mounts":
        return "Monture", MOUNTS.get(sub, "Autres montures"), family
    if category == "consumables":
        if sub in ("vanity", "kill_emotes"):
            return "Cosmétique", "Emotes et objets", family
        return "Consommable", CONSUMABLES.get(sub, "Autres consommables"), family
    if category == "gatherergear":
        gather, _, piece = sub.partition("gatherer_")
        return "Équipement de Récolte", GATHERER.get(gather, "Autre récolte"), GEAR_SLOTS.get(piece, family)
    if category == "tools":
        return "Équipement de Récolte", "Outils", TOOLS.get(sub, family)
    if category == "resources":
        refined = sub in ("cloth", "leather", "metalbar", "stoneblock", "planks")
        return "Fabrication", "Ressources raffinées" if refined else "Ressources brutes", RESOURCES.get(sub, family)
    if category == "cityresources":
        return "Fabrication", "Ressources de ville", family
    if category == "luxurygoods":
        return "Fabrication", "Produits de luxe", sub.capitalize()
    if category == "materials":
        return "Fabrication", "Matériaux magiques", MATERIALS.get(sub, family)
    if category == "artefacts":
        return "Artefact", {
            "magic_artefact": "Armes magiques", "ranged_artefact": "Armes à distance",
            "melee_artefact": "Armes de mêlée", "armor_artefact": "Armures",
            "offhand_artefact": "Armes secondaires", "other": "Autres artefacts",
        }.get(sub, "Autres artefacts"), family
    if category == "farmables":
        return "Agriculture", "Élevage" if sub == "animals" else "Semences", family
    if category == "products":
        return "Agriculture", "Produits agricoles", FARMING.get(sub, family)
    if category == "trophies":
        return "Mobilier", "Trophées", family
    if category == "furniture":
        return "Mobilier", "Meubles et décorations", family
    if category == "labourers":
        return "Mobilier", "Ouvriers", family
    if category == "skillbooks":
        return "Autre", "Livres de compétence", family
    if category == "token":
        return "Autre", "Jetons", family
    return "Autre", "Objets divers", family


def _fallback_path(item_id: str, family: str) -> tuple[str, str, str]:
    key = item_id.upper()
    parts = key.split("_")
    kind = parts[1] if len(parts) > 1 else key
    if key.startswith("SKIN_") or any(tag in key for tag in ("VANITY", "AVATAR", "MOUNTSKIN", "UNLOCK_SKIN")):
        group = "Apparences de montures" if "SKIN_" in key else (
            "Portraits et avatars" if "AVATAR" in key else "Tenues et objets cosmétiques")
        return "Cosmétique", group, family
    if kind in ("MAIN", "2H"):
        if "TOOL" in key:
            return "Équipement de Récolte", "Outils", family
        return "Armes", _weapon_fallback(key), family
    if kind in ("HEAD", "ARMOR", "SHOES"):
        root = {"HEAD": "Armure de Tête", "ARMOR": "Armure de Poitrine", "SHOES": "Armure de Pieds"}[kind]
        material = next((label for fragment, label in (("CLOTH", "Tissu"),
            ("LEATHER", "Cuir"), ("PLATE", "Plaque")) if fragment in key), "Spécial")
        return root, material, family
    if kind == "OFF":
        return "Armes Secondaires", "Autres armes secondaires", family
    if kind in ("CAPEITEM", "CAPE"):
        return "Capes", "Capes", family
    if kind in ("BAG", "BACKPACK"):
        return "Sacs", "Sacs", family
    if kind in ("MOUNT", "HORSE", "OX", "ARMORED", "DIREWOLF", "DIREBOAR", "COUGAR", "GIANTSTAG"):
        return "Monture", "Autres montures", family
    if kind in ("POTION", "MEAL", "CONSUMABLE", "FOOD", "FOCUSPOTION"):
        return "Consommable", "Potions" if kind in ("POTION", "FOCUSPOTION") else "Nourriture", family
    if kind in ("ORE", "FIBER", "WOOD", "HIDE", "ROCK", "FISH"):
        return "Fabrication", "Ressources brutes", RESOURCES.get(kind.lower(), family)
    if kind in ("METALBAR", "CLOTH", "LEATHER", "PLANKS", "STONEBLOCK"):
        return "Fabrication", "Ressources raffinées", RESOURCES.get(kind.lower(), family)
    if kind in ("RUNE", "RELIC", "ESSENCE", "SOUL", "SHARD", "ALCHEMY"):
        return "Fabrication", "Matériaux magiques", family
    if kind == "ARTEFACT":
        return "Artefact", "Autres artefacts", family
    if kind in ("FARM", "SEED", "CROP", "HERB", "ANIMAL"):
        return "Agriculture", "Élevage" if kind in ("FARM", "ANIMAL") else "Semences et cultures", family
    if kind == "JOURNAL":
        return "Agriculture", "Journaux d'ouvrier", family
    if kind in ("FURNITUREITEM", "FURNITURE", "LABOURER"):
        return "Mobilier", "Meubles et décorations", family
    if kind in ("LOOTCHEST", "LOOTBAG"):
        return "Autre", "Coffres et butin", family
    if kind in ("SKILLBOOK", "LEARNINGPOINTS"):
        return "Autre", "Livres de compétence", family
    if kind in ("RANDOM", "TOKEN"):
        return "Autre", "Jetons et cartes", family
    return "Autre", "Objets divers", family


class MarketTaxonomy:
    def __init__(self, entries: dict[str, dict[str, str]], index_path: Path = SHOP_INDEX_PATH):
        with gzip.open(index_path, "rt", encoding="utf-8") as stream:
            shop_items = json.load(stream)["shop_items"]
        self.by_id = {item_id: tuple(values) for item_id, values in shop_items.items()}
        self.by_family = {market_family_key(item_id): tuple(values)
                          for item_id, values in shop_items.items()}

        labels: dict[str, tuple[tuple[int, int], str]] = {}
        for item_id, item in entries.items():
            family_key = market_family_key(item_id)
            tier_match = re.match(r"^T(\d+)_", item_id)
            tier = int(tier_match.group(1)) if tier_match else 0
            name = item.get("fr") or item.get("en") or item_id
            title = family_title(name)
            priority = (abs(tier - 4) if tier else 99, len(title))
            if family_key not in labels or priority < labels[family_key][0]:
                labels[family_key] = (priority, title)
        self.family_names = {key: record[1] for key, record in labels.items()}

    def path_for(self, item_id: str) -> tuple[str, str, str]:
        family_key = market_family_key(item_id)
        family = self.family_names.get(family_key, item_id)
        key = item_id.upper()
        if (key.startswith("SKIN_") or "VANITY" in key or "AVATAR" in key or
                "UNLOCK_SKIN" in key):
            return _fallback_path(item_id, family)
        if "DEBUG" in key:
            return "Autre", "Objets techniques", family
        shop = self.by_id.get(VARIANT_RE.sub("", item_id)) or self.by_family.get(family_key)
        return _shop_path(shop, item_id, family) if shop else _fallback_path(item_id, family)
