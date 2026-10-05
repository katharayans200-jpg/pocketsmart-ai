"""Optional connectivity check for YOUR Gemini key/model (Milestone 1, Activity 1.3).

Run:   python check_gemini.py                 (text test)
       python check_gemini.py path\\to\\outfit.jpg   (text + image test)
It uses the GEMINI_API_KEY / GEMINI_MODEL values from your .env file and prints only success/failure.
"""
import sys
from pathlib import Path

from app.config import settings
from app.services.gemini_service import GeminiError, ImagePart, get_gemini_service
from app.utils.images import AppError, ProcessedImage  # noqa: F401


def main() -> int:
    if not settings.gemini_api_key or not settings.gemini_model:
        print("FAIL: set GEMINI_API_KEY and GEMINI_MODEL in your .env file first.")
        return 1
    svc = get_gemini_service()
    try:
        out = svc.generate_json('Reply with exactly this JSON: {"status": "ok"}')
        print("Text test OK ->", out)
        if len(sys.argv) > 1:
            path = Path(sys.argv[1])
            mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            out = svc.generate_json('Describe the dominant colours as JSON: {"colors": []}', ImagePart(path.read_bytes(), mime))
            print("Image test OK ->", out)
    except GeminiError as exc:
        print("FAIL:", exc.user_message)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
