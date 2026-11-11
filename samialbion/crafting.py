"""Offline crafting recipes and gross-profit calculations (silver)."""

from dataclasses import dataclass
import gzip
import json
import math
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
    batches: int = 1
    produced: int = 1
    upfront_cost: int = 0
    recovered_value: int = 0
    market_fee: int = 0
    artisan_fee: int = 0


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
                     batches: int = 1, *, target_units: int | None = None,
                     market_tax_enabled: bool = False, market_tax_percent: float = 6.5,
                     artisan_fee_per_batch: int = 0, return_percent: float = 0) -> CraftResult:
    if (batches < 1 or sale_price < 0 or any(price < 0 for price in prices.values())
            or target_units is not None and target_units < 1
            or not (0 <= market_tax_percent <= 100)
            or not (0 <= return_percent <= 100) or artisan_fee_per_batch < 0):
        raise ValueError("Prix et quantités invalides")
    if target_units is not None:
        batches = math.ceil(target_units / recipe.output_amount)
    produced = recipe.output_amount * batches
    upfront_cost = sum(amount * prices.get(item_id, 0) for item_id, amount in recipe.materials) * batches
    recovered_value = round(upfront_cost * return_percent / 100)
    cost = upfront_cost - recovered_value
    revenue = produced * sale_price
    market_fee = round(revenue * market_tax_percent / 100) if market_tax_enabled else 0
    artisan_fee = artisan_fee_per_batch * batches
    profit = revenue - cost - market_fee - artisan_fee
    total_expense = cost + market_fee + artisan_fee
    return CraftResult(
        cost=cost,
        revenue=revenue,
        profit=profit,
        margin_percent=profit / revenue * 100 if revenue else None,
        roi_percent=profit / total_expense * 100 if total_expense else None,
        batches=batches,
        produced=produced,
        upfront_cost=upfront_cost,
        recovered_value=recovered_value,
        market_fee=market_fee,
        artisan_fee=artisan_fee,
    )
