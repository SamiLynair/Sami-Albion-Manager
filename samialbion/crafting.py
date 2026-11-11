"""Offline crafting recipes and gross-profit calculations (silver)."""

from dataclasses import dataclass
import gzip
import json
from pathlib import Path


RECIPE_PATH = Path(__file__).resolve().parent / "assets" / "crafting_recipes.json.gz"


@dataclass(frozen=True)
class CraftRecipe:
    item_id: str
    output_amount: int
    materials: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class CraftResult:
    cost: int
    revenue: int
    profit: int
    margin_percent: float | None
    roi_percent: float | None


class CraftingRecipes:
    def __init__(self, source: Path = RECIPE_PATH):
        with gzip.open(source, "rt", encoding="utf-8") as handle:
            records = json.load(handle)
        self.by_id = {
            key: CraftRecipe(key, int(value["amount"]),
                             tuple((material, int(count)) for material, count in value["materials"]))
            for key, value in records.items()
            if int(value["amount"]) > 0 and value["materials"]
        }


def calculate_profit(recipe: CraftRecipe, prices: dict[str, int], sale_price: int,
                     batches: int = 1) -> CraftResult:
    if batches < 1 or sale_price < 0 or any(price < 0 for price in prices.values()):
        raise ValueError("Prix et quantités invalides")
    cost = sum(amount * prices.get(item_id, 0) for item_id, amount in recipe.materials) * batches
    revenue = recipe.output_amount * sale_price * batches
    profit = revenue - cost
    return CraftResult(
        cost=cost,
        revenue=revenue,
        profit=profit,
        margin_percent=profit / revenue * 100 if revenue else None,
        roi_percent=profit / cost * 100 if cost else None,
    )
