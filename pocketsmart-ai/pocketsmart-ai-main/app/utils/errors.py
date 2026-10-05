"""Shared error type + helpers that turn validation errors into readable messages."""
from typing import Any


class AppError(Exception):
    """An error with a user-friendly message and an HTTP status code."""

    def __init__(self, status_code: int, message: str, errors: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.errors = errors or []


class LoginRequired(Exception):
    """Raised by page routes when the visitor is not logged in."""


def format_errors(raw_errors: list[dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    for err in raw_errors:
        loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "form", "query")]
        field = loc[-1] if loc else "form"
        msg = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
        out.append({"field": field, "message": msg})
    return out


def summarize(errors: list[dict[str, str]]) -> str:
    if not errors:
        return "Please check your input and try again."
    parts = [f"{e['field'].replace('_', ' ').capitalize()}: {e['message']}" for e in errors[:3]]
    return " | ".join(parts)
