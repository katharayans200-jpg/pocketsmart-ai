from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.auth import LoginIn, RegisterIn
from app.templating import render
from app.utils.deps import get_optional_user
from app.utils.errors import format_errors
from app.utils.security import hash_password, verify_password

router = APIRouter(tags=["auth"])


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user: User | None = Depends(get_optional_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "register.html")


@router.post("/register")
def register(request: Request, username: str = Form(""), email: str = Form(""), password: str = Form(""),
             confirm_password: str = Form(""), db: Session = Depends(get_db)):
    values = {"username": username.strip(), "email": email.strip()}
    try:
        data = RegisterIn(username=username, email=email, password=password, confirm_password=confirm_password)
    except ValidationError as exc:
        errors = format_errors(exc.errors())
        return render(request, "register.html", 400, errors=errors, values=values,
                      error="Please fix the problems below.")
    email_norm = data.email.lower()
    taken = db.scalar(select(User).where(or_(func.lower(User.username) == data.username.lower(), User.email == email_norm)))
    if taken:
        field = "username" if taken.username.lower() == data.username.lower() else "email"
        return render(request, "register.html", 409, values=values,
                      errors=[{"field": field, "message": f"That {field} is already registered."}],
                      error=f"That {field} is already registered. Try logging in instead.")
    user = User(username=data.username, email=email_norm, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: User | None = Depends(get_optional_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "login.html")


@router.post("/login")
def login(request: Request, username: str = Form(""), password: str = Form(""), db: Session = Depends(get_db)):
    try:
        data = LoginIn(username=username.strip(), password=password)
    except ValidationError:
        data = None
    user = None
    if data and data.username and data.password:
        ident = data.username.lower()
        user = db.scalar(select(User).where(or_(func.lower(User.username) == ident, User.email == ident)))
    # always run a hash check (against a dummy hash if the user is unknown) to keep timing similar
    ok = verify_password(password, user.password_hash if user else None)
    if not (user and ok):
        return render(request, "login.html", 401, values={"username": username.strip()},
                      error="Incorrect username/email or password.")
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
