from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.party import EVENT_TYPES, VENUE_PREFS, PartyInput
from app.schemas.plan import RecommendationOut
from app.services import recommendation_service as svc
from app.templating import render
from app.utils.deps import require_user, require_user_page

router = APIRouter(tags=["party planner"])


@router.get("/party-planner", response_class=HTMLResponse)
def party_planner_page(request: Request, user: User = Depends(require_user_page)):
    return render(request, "party_planner.html", user=user, event_types=EVENT_TYPES, venue_prefs=VENUE_PREFS)


@router.post("/generate-party", response_model=RecommendationOut)
def generate_party(payload: PartyInput, user: User = Depends(require_user), db: Session = Depends(get_db)):
    result = svc.build_party_plan(payload)
    rec = svc.save_recommendation(db, user, "party", payload.model_dump(), result)
    return svc.to_out(rec)
