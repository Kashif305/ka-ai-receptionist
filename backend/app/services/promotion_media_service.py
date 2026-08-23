import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


ALLOWED_MEDIA = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class MediaValidationError(ValueError):
    pass


@dataclass(frozen=True)
class StoredMedia:
    url: str
    filename: str
    content_type: str
    size: int


class LocalPromotionMediaStorage:
    def __init__(self, directory: str | Path | None = None, url_prefix: str | None = None):
        self.directory = Path(directory or settings.promotion_media_directory).resolve()
        self.url_prefix = (url_prefix or settings.promotion_media_url_prefix).rstrip("/")

    @staticmethod
    def _safe_stem(filename: str) -> str:
        basename = Path(filename.replace("\\", "/")).name
        stem = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(basename).stem).strip("-_")
        return (stem or "flyer")[:80]

    @staticmethod
    def _signature_matches(content: bytes, content_type: str) -> bool:
        if content_type == "image/jpeg":
            return content.startswith(b"\xff\xd8\xff")
        if content_type == "image/png":
            return content.startswith(b"\x89PNG\r\n\x1a\n")
        if content_type == "image/webp":
            return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
        return False

    def save(self, filename: str, content_type: str, content: bytes) -> StoredMedia:
        suffix = Path(Path(filename.replace("\\", "/")).name).suffix.lower()
        expected_type = ALLOWED_MEDIA.get(suffix)
        if expected_type is None or expected_type != content_type:
            raise MediaValidationError("Flyer must be a JPEG, PNG, or WebP with a matching extension")
        if not content or len(content) > settings.promotion_media_max_bytes:
            raise MediaValidationError(
                f"Flyer must be non-empty and no larger than {settings.promotion_media_max_bytes} bytes"
            )
        if not self._signature_matches(content, content_type):
            raise MediaValidationError("Flyer content does not match its declared image type")

        stored_name = f"{self._safe_stem(filename)}-{uuid.uuid4().hex}{suffix}"
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = (self.directory / stored_name).resolve()
        if destination.parent != self.directory:
            raise MediaValidationError("Invalid flyer filename")
        destination.write_bytes(content)
        return StoredMedia(
            url=f"{self.url_prefix}/{stored_name}",
            filename=stored_name,
            content_type=content_type,
            size=len(content),
        )
