from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ROOM_TYPES = ("Living Room", "Bedroom", "Kitchen", "Dining Room", "Other")


class HomeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    total_budget: float = Field(ge=1000, le=100_000_000, description="Total budget in INR")
    room_type: Literal["Living Room", "Bedroom", "Kitchen", "Dining Room", "Other"]
    num_rooms: int = Field(default=1, ge=1, le=20)
    num_fans: int = Field(default=0, ge=0, le=50)
    num_lights: int = Field(default=0, ge=0, le=100)
    num_furniture: int = Field(default=0, ge=0, le=50)
    num_dining_tables: int = Field(default=0, ge=0, le=10)
    other_furniture: str = Field(default="", max_length=300)
    style: str = Field(default="No preference", max_length=60)
    colors: str = Field(default="", max_length=100)
    additional: str = Field(default="", max_length=500)

    @field_validator("total_budget")
    @classmethod
    def _finite(cls, v: float) -> float:
        if v != v:
            raise ValueError("Enter a valid amount.")
        return v

    @model_validator(mode="after")
    def _something_needed(self):
        if not (self.num_fans or self.num_lights or self.num_furniture or self.num_dining_tables or self.other_furniture):
            raise ValueError("Enter at least one item to plan (fans, lights, furniture, dining table or other furniture).")
        return self
