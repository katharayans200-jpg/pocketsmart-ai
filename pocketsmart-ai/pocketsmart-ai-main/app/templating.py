from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import settings

templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["gemini_live"] = lambda: settings.gemini_ready


def render(request: Request, name: str, status_code: int = 200, **context):
    context.setdefault("user", None)
    return templates.TemplateResponse(request, name, context, status_code=status_code)
