from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas.jewelry import JEWELRY_TYPES, METALS, OCCASIONS, JewelryInput
from app.schemas.plan import RecommendationOut
from app.services import recommendation_service as svc
from app.templating import render
from app.utils.deps import require_user, require_user_page
from app.utils.errors import AppError, format_errors, summarize
from app.utils.images import process_upload, save_image

router = APIRouter(tags=["jewelry planner"])


@router.get("/jewelry-planner", response_class=HTMLResponse)
def jewelry_planner_page(request: Request, user: User = Depends(require_user_page)):
    return render(request, "jewelry_planner.html", user=user, occasions=OCCASIONS, jewelry_types=JEWELRY_TYPES,
                  metals=METALS, max_mb=settings.max_upload_mb)


@router.post("/generate-jewelry", response_model=RecommendationOut)
def generate_jewelry(
    total_budget: float = Form(...),
    occasion: str = Form(...),
    jewelry_type: str = Form("Any"),
    style: str = Form(""),
    metal: str = Form("No preference"),
    colors: str = Form(""),
    additional: str = Form(""),
    outfit_image: UploadFile | None = File(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        data = JewelryInput(total_budget=total_budget, occasion=occasion, jewelry_type=jewelry_type, style=style,
                            metal=metal, colors=colors, additional=additional)
    except ValidationError as exc:
        errors = format_errors(exc.errors())
        raise AppError(422, summarize(errors), errors) from None

    image = None
    if outfit_image is not None and outfit_image.filename:
        image = process_upload(outfit_image)  # raises AppError (400/413) for bad files

    result = svc.build_jewelry_plan(data, image)
    image_file = save_image(image) if image else None
    input_data = data.model_dump()
    input_data["outfit_image"] = image.original_name if image else None
    rec = svc.save_recommendation(db, user, "jewelry", input_data, result, image_file)
    return svc.to_out(rec)
