from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

OCCASIONS = ("Wedding", "Party", "Festive event", "Casual wear", "Formal event")
JEWELRY_TYPES = ("Any", "Necklace", "Earrings", "Ring", "Bracelet", "Bangles", "Anklet", "Matching set")
METALS = ("No preference", "Gold", "Silver", "Rose gold", "Platinum", "Artificial / imitation")


class JewelryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    total_budget: float = Field(ge=500, le=100_000_000)
    occasion: Literal["Wedding", "Party", "Festive event", "Casual wear", "Formal event"]
    jewelry_type: Literal["Any", "Necklace", "Earrings", "Ring", "Bracelet", "Bangles", "Anklet", "Matching set"] = "Any"
    style: str = Field(default="", max_length=60)
    metal: Literal["No preference", "Gold", "Silver", "Rose gold", "Platinum", "Artificial / imitation"] = "No preference"
    colors: str = Field(default="", max_length=100)
    additional: str = Field(default="", max_length=500)

    @field_validator("total_budget")
    @classmethod
    def _finite(cls, v: float) -> float:
        if v != v:
            raise ValueError("Enter a valid amount.")
        return v
