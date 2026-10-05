from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Recommendation, User
from app.schemas.plan import RecommendationOut
from app.services import recommendation_service as svc
from app.templating import render
from app.utils.deps import require_user, require_user_page

router = APIRouter(tags=["history"])


def _own(db: Session, user: User, rec_id: int) -> Recommendation:
    """Fetch a recommendation only if it belongs to this user (404 otherwise, so ids can't be probed)."""
    rec = db.scalar(select(Recommendation).where(Recommendation.id == rec_id, Recommendation.user_id == user.id))
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    return rec


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request, user: User = Depends(require_user_page)):
    return render(request, "history.html", user=user)


@router.get("/history/{recommendation_id}", response_class=HTMLResponse)
def history_detail_page(recommendation_id: int, request: Request, user: User = Depends(require_user_page),
                        db: Session = Depends(get_db)):
    rec = _own(db, user, recommendation_id)
    return render(request, "recommendations.html", user=user, rec_id=rec.id)


@router.get("/recommendations/history")
def recommendation_history(planner: Literal["home", "party", "jewelry"] | None = None,
                           limit: int = Query(100, ge=1, le=200),
                           user: User = Depends(require_user), db: Session = Depends(get_db)):
    stmt = select(Recommendation).where(Recommendation.user_id == user.id)
    if planner:
        stmt = stmt.where(Recommendation.planner_type == planner)
    recs = db.scalars(stmt.order_by(Recommendation.created_at.desc(), Recommendation.id.desc()).limit(limit)).all()
    return {"count": len(recs), "items": [svc.history_summary(r) for r in recs]}


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationOut)
def recommendation_detail(recommendation_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return svc.to_out(_own(db, user, recommendation_id))


@router.get("/recommendations/{recommendation_id}/image")
def recommendation_image(recommendation_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    rec = _own(db, user, recommendation_id)
    if not rec.image_path:
        raise HTTPException(status_code=404, detail="No image saved for this recommendation.")
    path = (settings.upload_dir / rec.image_path).resolve()
    if settings.upload_dir.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
