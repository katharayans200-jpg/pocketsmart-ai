"""Validation + sanitising of the optional outfit image upload."""
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps

from app.config import settings
from app.utils.errors import AppError

ALLOWED_EXT = {".jpg", ".jpeg", ".png"}
ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/pjpeg"}
MAX_PIXELS = 40_000_000
MAX_SIDE = 1280


@dataclass
class ProcessedImage:
    data: bytes          # re-encoded JPEG (EXIF/location metadata removed)
    mime_type: str
    original_name: str


def process_upload(upload: UploadFile) -> ProcessedImage:
    name = Path(upload.filename or "").name
    if Path(name).suffix.lower() not in ALLOWED_EXT:
        raise AppError(400, "Unsupported image type. Please upload a JPG, JPEG or PNG file.")
    if upload.content_type and upload.content_type.lower() not in ALLOWED_MIME:
        raise AppError(400, "Unsupported image type. Please upload a JPG, JPEG or PNG file.")
    raw = upload.file.read(settings.max_upload_bytes + 1)
    if not raw:
        raise AppError(400, "The uploaded image is empty.")
    if len(raw) > settings.max_upload_bytes:
        raise AppError(413, f"Image is too large. The maximum size is {settings.max_upload_mb} MB.")
    try:
        probe = Image.open(BytesIO(raw))
        probe.verify()
        img = Image.open(BytesIO(raw))
        if img.format not in {"JPEG", "PNG"}:
            raise ValueError("format")
        if img.width * img.height > MAX_PIXELS:
            raise AppError(400, "Image dimensions are too large. Please upload a smaller image.")
        img.load()
    except AppError:
        raise
    except Exception:  # noqa: BLE001 - any decoding problem means "not a readable image"
        raise AppError(400, "That file could not be read as an image. Please upload a valid JPG or PNG.") from None
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    else:
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return ProcessedImage(data=buf.getvalue(), mime_type="image/jpeg", original_name=name[:80])


def save_image(image: ProcessedImage) -> str:
    """Store the sanitised image in uploads/ under a random name; returns the file name."""
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    (settings.upload_dir / filename).write_bytes(image.data)
    return filename
