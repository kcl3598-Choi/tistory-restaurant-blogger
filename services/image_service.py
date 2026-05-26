import os
import uuid
from pathlib import Path
from typing import List
from PIL import Image


UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
MAX_SIZE = (1920, 1920)
MAX_FILE_BYTES = 4 * 1024 * 1024  # 4MB (Claude Vision 5MB 제한 여유)


def save_and_resize(file_bytes: bytes, original_filename: str) -> str:
    """업로드된 이미지를 저장하고 필요시 리사이즈합니다. 저장 경로를 반환합니다."""
    UPLOAD_DIR.mkdir(exist_ok=True)

    ext = Path(original_filename).suffix.lower() or ".jpg"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / unique_name

    # PIL로 열어서 크기 확인 및 리사이즈
    import io
    img = Image.open(io.BytesIO(file_bytes))

    # EXIF 회전 보정
    try:
        from PIL.ExifTags import TAGS
        exif = img._getexif()
        if exif:
            for tag_id, value in exif.items():
                if TAGS.get(tag_id) == "Orientation":
                    rotations = {3: 180, 6: 270, 8: 90}
                    if value in rotations:
                        img = img.rotate(rotations[value], expand=True)
                    break
    except Exception:
        pass

    # 최대 크기 초과 시 리사이즈
    if img.width > MAX_SIZE[0] or img.height > MAX_SIZE[1]:
        img.thumbnail(MAX_SIZE, Image.LANCZOS)

    # RGBA → RGB 변환 (JPEG 저장 호환)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
        ext = ".jpg"
        save_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.jpg"

    # 저장 (JPEG는 품질 85%)
    if ext in (".jpg", ".jpeg"):
        img.save(save_path, "JPEG", quality=85, optimize=True)
    elif ext == ".png":
        img.save(save_path, "PNG", optimize=True)
    else:
        img.save(save_path)

    # 여전히 너무 크면 품질 낮춰서 재저장
    if os.path.getsize(save_path) > MAX_FILE_BYTES:
        img.save(save_path, "JPEG", quality=65, optimize=True)

    return str(save_path)


def cleanup_uploads(paths: List[str]):
    """처리 완료된 임시 파일들을 삭제합니다."""
    for path in paths:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass
