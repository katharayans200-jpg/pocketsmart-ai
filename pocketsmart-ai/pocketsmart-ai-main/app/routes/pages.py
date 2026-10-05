from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Recommendation, User
from app.services.recommendation_service import history_summary
from app.templating import render
from app.utils.deps import get_optional_user, require_user_page

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
def landing(request: Request, user: User | None = Depends(get_optional_user)):
    return render(request, "index.html", user=user)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user: User = Depends(require_user_page), db: Session = Depends(get_db)):
    recent = db.scalars(select(Recommendation).where(Recommendation.user_id == user.id)
                        .order_by(Recommendation.created_at.desc(), Recommendation.id.desc()).limit(5)).all()
    counts = dict(db.execute(select(Recommendation.planner_type, func.count())
                             .where(Recommendation.user_id == user.id).group_by(Recommendation.planner_type)).all())
    return render(request, "dashboard.html", user=user, recent=[history_summary(r) for r in recent],
                  counts=counts, total=sum(counts.values()))


@router.get("/health")
def health():
    """Liveness check. Never reveals secrets."""
    return {"status": "ok", "ai_mode": "live" if settings.gemini_ready else "demo",
            "gemini_key_configured": bool(settings.gemini_api_key), "gemini_model_configured": bool(settings.gemini_model)}
