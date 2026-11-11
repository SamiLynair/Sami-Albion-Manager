"""Entirely offline item index for Sami Albion Manager.

No HTTP client, market API, authentication or game-process interaction.
"""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import json
from pathlib import Path
import re
import unicodedata

from .market_taxonomy import MARKET_ROOTS, MarketTaxonomy


ASSETS = Path(__file__).resolve().parent / "assets"
SOURCE_PATH = ASSETS / "catalog.json.gz"

CATEGORIES = (
    "Équipements", "Ressources brutes", "Ressources raffinées",
    "Consommables", "Montures", "Agriculture", "Artefacts",
    "Mobilier", "Cosmétiques", "Objets divers",
)
QUALITIES = (
    "Normale", "Acceptable", "Admirable", "Formidable", "Exceptionnelle",
)
TIER_RE = re.compile(r"^T(\d+)_")
ENCHANT_RE = re.compile(r"@(\d+)$")
LEVEL_RE = re.compile(r"_LEVEL([1-4])(?:@\d+)?$")


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


def item_category(item_id: str) -> str:
    components = item_id.split("_")
    kind = components[1] if len(components) > 1 else item_id
    if kind in ("VANITY", "AVATAR", "AVATARRING", "UNLOCK", "MOUNTSKIN") or "VANITY" in item_id:
        return "Cosmétiques"
    if kind in ("ORE", "FIBER", "WOOD", "HIDE", "ROCK", "FISH", "FISHING"):
        return "Ressources brutes"
    if kind in ("METALBAR", "CLOTH", "LEATHER", "PLANKS", "STONEBLOCK"):
        return "Ressources raffinées"
    if kind in ("POTION", "MEAL", "CONSUMABLE", "FOOD", "FOCUSPOTION"):
        return "Consommables"
    if kind in ("FARM", "SEED", "CROP", "HERB", "ANIMAL", "PASTURE"):
        return "Agriculture"
    if kind in ("ARTEFACT", "RUNE", "SOUL", "RELIC", "ESSENCE"):
        return "Artefacts"
    if kind in ("FURNITUREITEM", "LABOURER", "FURNITURE", "DECORATION"):
        return "Mobilier"
    if kind in ("MOUNT", "HORSE", "OX", "ARMORED", "DIREWOLF", "DIREBOAR", "COUGAR", "GIANTSTAG", "MOUNTSKIN"):
        return "Montures"
    if kind in ("HEAD", "ARMOR", "SHOES", "MAIN", "2H", "OFF", "BAG", "CAPE", "CAPEITEM", "BACKPACK", "TOOL"):
        return "Équipements"
    return "Objets divers"


@dataclass(frozen=True, slots=True)
class GameItem:
    item_id: str
    name_fr: str
    name_en: str
    tier: int
    enchantment: int
    category: str
    market_path: tuple[str, str, str]
    has_qualities: bool
    search_text: str

    @property
    def name(self) -> str:
        return self.name_fr or self.name_en or self.item_id


class OfflineItemCatalog:
    def __init__(self, source: Path = SOURCE_PATH):
        with gzip.open(source, "rt", encoding="utf-8") as handle:
            entries = json.load(handle)["items"]

        taxonomy = MarketTaxonomy(entries)

        items = []
        for item_id, source_record in entries.items():
            name_fr = source_record.get("fr") or ""
            name_en = source_record.get("en") or ""
            tier_match = TIER_RE.match(item_id)
            enchant_match = ENCHANT_RE.search(item_id)
            level_match = LEVEL_RE.search(item_id)
            tier = int(tier_match.group(1)) if tier_match else 0
            enchantment = int(enchant_match.group(1)) if enchant_match else (
                int(level_match.group(1)) if level_match else 0
            )
            category = item_category(item_id)
            items.append(GameItem(
                item_id=item_id,
                name_fr=name_fr,
                name_en=name_en,
                tier=tier,
                enchantment=enchantment,
                category=category,
                market_path=taxonomy.path_for(item_id),
                has_qualities=category == "Équipements" and tier > 0,
                search_text=fold(" ".join((item_id, name_fr, name_en))),
            ))
        order = {category: n for n, category in enumerate(MARKET_ROOTS)}
        self.items = sorted(items, key=lambda i: (order[i.market_path[0]],
                             fold(i.market_path[1]), fold(i.market_path[2]), i.tier, i.enchantment))
        self.by_id = {item.item_id: item for item in self.items}

    def find(
        self,
        query: str = "",
        *,
        category: str | None = None,
        market_path: tuple[str, ...] | None = None,
        tier: int | None = None,
        enchantment: int | None = None,
        quality: int | None = None,
    ) -> list[GameItem]:
        terms = fold(query).split()
        return [
            item for item in self.items
            if (not terms or all(term in item.search_text for term in terms))
            and (not category or item.category == category)
            and (not market_path or item.market_path[:len(market_path)] == market_path)
            and (tier is None or item.tier == tier)
            and (enchantment is None or item.enchantment == enchantment)
            and (quality is None or (1 <= quality <= 5 and item.has_qualities))
        ]
