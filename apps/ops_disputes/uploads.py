import hashlib
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction

from .models import EvidenceFile

MAX_BYTES = 5 * 1024 * 1024


def save_evidence(item, upload):
    if upload.size > MAX_BYTES or item.files.count() >= 10:
        raise ValidationError("Limit: 5 MB per file and 10 files per evidence item.")
    data = upload.read(MAX_BYTES + 1)
    name = Path(upload.name.replace("\\", "/")).name[:200]
    extension = Path(name).suffix.lower()
    text = ""
    if extension == ".pdf" and data.startswith(b"%PDF-"):
        mime = "application/pdf"
    elif extension == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif extension in {".jpg", ".jpeg"} and data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif extension == ".txt":
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError("Text files must use UTF-8.") from exc
        if "\x00" in text:
            raise ValidationError("Binary content is not a text document.")
        mime = "text/plain"
    else:
        raise ValidationError("Upload a PDF, PNG, JPEG or UTF-8 text file.")
    if len(data) > MAX_BYTES or not data:
        raise ValidationError("Upload a nonempty file smaller than 5 MB.")
    path = default_storage.save(
        f"evidence/{item.dispute.workspace_id}/{uuid4().hex}{extension}", ContentFile(data)
    )
    try:
        with transaction.atomic():
            evidence = EvidenceFile.objects.create(
                item=item,
                file_path=path,
                filename=name,
                mime_type=mime,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                text_content=text[:12000],
            )
            item.status = "uploaded"
            item.save(update_fields=["status"])
        return evidence
    except Exception:
        default_storage.delete(path)
        raise
