"""Pydantic models that validate what Gemini sends back. Tolerant of small formatting slips
(price strings, over-long text, one bad item) but strict about the overall structure."""
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, model_validator

from app.utils.numbers import parse_amount


def _trunc(n: int):
    def f(v):
        return "" if v is None else str(v).strip()[:n]
    return BeforeValidator(f)


def tolerant(model: type[BaseModel]):
    """Keep the list entries that validate and silently drop the rest."""
    def f(v):
        if not isinstance(v, list):
            return []
        out = []
        for x in v:
            try:
                out.append(model.model_validate(x))
            except ValidationError:
                continue
        return out
    return BeforeValidator(f)


Short = Annotated[str, _trunc(150)]
Long = Annotated[str, _trunc(600)]
Money = Annotated[int, BeforeValidator(parse_amount)]
Qty = Annotated[int, BeforeValidator(lambda v: max(1, parse_amount(v, 1)))]
Tips = Annotated[list[str], BeforeValidator(
    lambda v: [str(x).strip()[:300] for x in v if str(x).strip()][:6] if isinstance(v, list) else [])]


class AIBase(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ---------- Home ----------
class AIHomeItem(AIBase):
    name: Short = Field(min_length=1)
    description: Long = ""
    quantity: Qty = 1
    unit_price: Money = 0
    reason: Long = ""
    search_query: Short = ""
    platform: Short = ""


class AIHomeCategory(AIBase):
    category: Short = Field(min_length=1)
    items: Annotated[list[AIHomeItem], tolerant(AIHomeItem)] = []


class AIHomePlan(AIBase):
    categories: Annotated[list[AIHomeCategory], tolerant(AIHomeCategory)] = []
    tips: Tips = []

    @model_validator(mode="after")
    def _has_items(self):
        if not any(c.items for c in self.categories):
            raise ValueError("no usable items")
        return self


# ---------- Party ----------
class AIPartyItem(AIBase):
    name: Short = Field(min_length=1)
    description: Long = ""
    estimated_cost: Money = 0
    reason: Long = ""
    search_query: Short = ""
    platform: Short = ""


class AIPartyCategory(AIBase):
    category: Short = Field(min_length=1)
    items: Annotated[list[AIPartyItem], tolerant(AIPartyItem)] = []


class AIPartyPlan(AIBase):
    categories: Annotated[list[AIPartyCategory], tolerant(AIPartyCategory)] = []
    tips: Tips = []

    @model_validator(mode="after")
    def _has_items(self):
        if not any(c.items for c in self.categories):
            raise ValueError("no usable items")
        return self


# ---------- Jewelry ----------
class AIOutfit(AIBase):
    colors: Annotated[list[str], BeforeValidator(
        lambda v: [str(x).strip()[:40] for x in v][:8] if isinstance(v, list) else [])] = []
    style: Short = ""
    formality: Short = ""
    notes: Long = ""


class AIJewelryItem(AIBase):
    jewelry_type: Short = Field(min_length=1)
    name: Short = Field(min_length=1)
    description: Long = ""
    estimated_price: Money = 0
    compatibility: Long = ""
    search_query: Short = ""
    platform: Short = ""


class AIJewelryPlan(AIBase):
    outfit_analysis: AIOutfit | None = None
    items: Annotated[list[AIJewelryItem], tolerant(AIJewelryItem)] = []
    styling_tips: Tips = []

    @model_validator(mode="after")
    def _has_items(self):
        if not self.items:
            raise ValueError("no usable items")
        return self
