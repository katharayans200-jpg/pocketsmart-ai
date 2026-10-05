from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.home import ROOM_TYPES, HomeInput
from app.schemas.plan import RecommendationOut
from app.services import recommendation_service as svc
from app.templating import render
from app.utils.deps import require_user, require_user_page

router = APIRouter(tags=["home planner"])

STYLES = ["No preference", "Modern", "Minimalist", "Contemporary", "Traditional", "Scandinavian", "Industrial", "Bohemian"]


@router.get("/home-planner", response_class=HTMLResponse)
def home_planner_page(request: Request, user: User = Depends(require_user_page)):
    return render(request, "home_planner.html", user=user, room_types=ROOM_TYPES, styles=STYLES)


@router.post("/generate-home", response_model=RecommendationOut)
def generate_home(payload: HomeInput, user: User = Depends(require_user), db: Session = Depends(get_db)):
    result = svc.build_home_plan(payload)
    rec = svc.save_recommendation(db, user, "home", payload.model_dump(), result)
    return svc.to_out(rec)
