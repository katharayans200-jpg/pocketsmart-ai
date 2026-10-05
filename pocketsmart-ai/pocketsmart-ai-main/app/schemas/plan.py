"""Unified result schema used by all three planners (stored in the DB and sent to the browser)."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Link(BaseModel):
    label: str
    url: str


class PlanItem(BaseModel):
    name: str
    category: str
    description: str = ""
    quantity: int = 1
    unit_price: int = 0          # estimated, INR
    total_price: int = 0         # quantity x unit_price, computed in Python
    reason: str = ""
    platform: str | None = None
    links: list[Link] = Field(default_factory=list)
    price_adjusted: bool = False  # True when the price was scaled down to fit the budget
    is_sample: bool = False       # True for demo/fallback sample items (not AI generated)


class PlanSection(BaseModel):
    key: str
    name: str
    allocation: int
    subtotal: int
    remaining: int
    note: str | None = None
    items: list[PlanItem] = Field(default_factory=list)


class PlanSummary(BaseModel):
    title: str
    total_budget: int
    planned_total: int
    remaining: int
    percent_used: float


class OutfitAnalysis(BaseModel):
    colors: list[str] = Field(default_factory=list)
    style: str = ""
    formality: str = ""
    notes: str = ""


class PlanResult(BaseModel):
    planner: Literal["home", "party", "jewelry"]
    source: Literal["gemini", "demo", "fallback"]
    model: str | None = None
    notice: str | None = None
    summary: PlanSummary
    sections: list[PlanSection]
    warnings: list[str] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)
    outfit_analysis: OutfitAnalysis | None = None
    price_note: str = ""
    generated_at: str = ""


class RecommendationOut(BaseModel):
    id: int
    planner_type: str
    created_at: datetime
    input: dict[str, Any]
    result: PlanResult
    has_image: bool = False
