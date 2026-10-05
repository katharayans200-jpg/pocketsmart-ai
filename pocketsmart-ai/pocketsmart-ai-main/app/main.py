"""PocketSmart AI - FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import init_db
from app.routes import auth, history, home, jewelry, pages, party
from app.templating import render
from app.utils.errors import AppError, LoginRequired, format_errors, summarize

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pocketsmart")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    mode = "LIVE (Gemini model: %s)" % settings.gemini_model if settings.gemini_ready else "DEMO (sample data)"
    log.info("PocketSmart AI started - AI mode: %s", mode)
    yield


def _wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


def create_app() -> FastAPI:
    app = FastAPI(title="PocketSmart AI", description="Smart budget & recommendation assistant", version="1.0.0",
                  lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie="pocketsmart_session",
                       same_site="lax", https_only=settings.cookie_secure, max_age=60 * 60 * 24 * 7)
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                           allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    for r in (pages.router, auth.router, home.router, party.router, jewelry.router, history.router):
        app.include_router(r)

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse({"detail": exc.message, "errors": exc.errors}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        errors = format_errors(exc.errors())
        return JSONResponse({"detail": summarize(errors), "errors": errors}, status_code=422)

    @app.exception_handler(LoginRequired)
    async def _login_required(_: Request, __: LoginRequired):
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        if _wants_html(request) and exc.status_code in (404, 405):
            return render(request, "error.html", exc.status_code, code=exc.status_code,
                          message="We couldn't find that page." if exc.status_code == 404 else "That action isn't allowed here.")
        return JSONResponse({"detail": exc.detail, "errors": []}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        log.exception("Unhandled error: %s", type(exc).__name__)
        return JSONResponse({"detail": "Something went wrong on our side. Please try again.", "errors": []}, status_code=500)

    return app


app = create_app()
