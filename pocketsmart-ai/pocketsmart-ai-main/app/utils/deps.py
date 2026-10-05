"""FastAPI dependencies for session-based authentication."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.utils.errors import LoginRequired


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_user(user: User | None = Depends(get_optional_user)) -> User:
    """For JSON/API routes: respond 401 when not logged in."""
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    return user


def require_user_page(user: User | None = Depends(get_optional_user)) -> User:
    """For HTML pages: redirect to /login when not logged in."""
    if user is None:
        raise LoginRequired()
    return user
