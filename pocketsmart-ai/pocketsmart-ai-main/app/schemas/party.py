from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EVENT_TYPES = ("Birthday", "Wedding", "Corporate event", "Anniversary", "Other")
VENUE_PREFS = ("Home / own venue", "Banquet hall", "Restaurant", "Outdoor / garden", "No preference")


class PartyInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    total_budget: float = Field(ge=1000, le=100_000_000)
    event_type: Literal["Birthday", "Wedding", "Corporate event", "Anniversary", "Other"]
    guest_count: int = Field(ge=1, le=5000)
    location: str = Field(min_length=2, max_length=100)
    venue_preference: Literal["Home / own venue", "Banquet hall", "Restaurant", "Outdoor / garden", "No preference"] = "No preference"
    needs_catering: bool = True
    needs_decoration: bool = True
    needs_entertainment: bool = True
    additional: str = Field(default="", max_length=500)

    @field_validator("total_budget")
    @classmethod
    def _finite(cls, v: float) -> float:
        if v != v:
            raise ValueError("Enter a valid amount.")
        return v
