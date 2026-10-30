"""상담 접수 첨부 파일(기획서·참고 자료). DATA_DIR/uploads 에 저장하고 관리자만 내려받는다."""
import os
from pathlib import Path
import re
import secrets
import unicodedata

if __package__:
    from .site_store import data_dir
else:
    from site_store import data_dir

ALLOWED = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".hwp", ".hwpx", ".txt", ".md",
           ".png", ".jpg", ".jpeg", ".zip"}
MAX_FILES = 3
MAX_FILE_BYTES = 10 * 1024 * 1024
CHUNK = 256 * 1024


class UploadError(ValueError):
    pass


def root():
    folder = data_dir() / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def max_total():
    return int(os.environ.get("UPLOADS_MAX_TOTAL_MB") or 2048) * 1024 * 1024


def used_bytes():
    return sum(f.stat().st_size for f in root().rglob("*") if f.is_file())


def clean_name(name):
    """Keep a readable display name; the stored file name never comes from the client."""
    name = unicodedata.normalize("NFC", Path(str(name or "")).name)
    name = re.sub(r"[\x00-\x1f\x7f\\/:*?\"<>|]+", "_", name).strip(" .")
    return name[:120] or "file"


def check(files):
    files = [f for f in files if getattr(f, "filename", "")]
    if len(files) > MAX_FILES:
        raise UploadError(f"첨부 파일은 {MAX_FILES}개까지 올릴 수 있습니다.")
    for f in files:
        if Path(clean_name(f.filename)).suffix.lower() not in ALLOWED:
            raise UploadError(f"'{clean_name(f.filename)}'은(는) 올릴 수 없는 형식입니다. PDF, 워드, 파워포인트, 엑셀, 한글, 이미지, ZIP 파일을 올려 주세요.")
    return files


async def save(inquiry_id, files):
    """Stream files to disk with size checks. Returns [(display_name, stored_relpath, size)]; cleans up on failure."""
    saved = []
    folder = root() / str(inquiry_id)
    budget = max_total() - used_bytes()
    try:
        for f in files:
            folder.mkdir(parents=True, exist_ok=True)
            display = clean_name(f.filename)
            stored = f"{secrets.token_hex(12)}{Path(display).suffix.lower()}"
            path = folder / stored
            size = 0
            with path.open("wb") as out:
                while chunk := await f.read(CHUNK):
                    size += len(chunk)
                    if size > MAX_FILE_BYTES:
                        raise UploadError(f"'{display}' 파일이 10MB를 넘습니다. 10MB 이하로 줄이거나 메일로 보내 주세요.")
                    if size > budget:
                        raise UploadError("지금은 파일을 받을 수 없습니다. 파일 없이 접수하시고 메일로 보내 주세요.")
                    out.write(chunk)
            if size == 0:
                path.unlink(missing_ok=True)
                raise UploadError(f"'{display}' 파일이 비어 있습니다.")
            budget -= size
            saved.append((display, f"{inquiry_id}/{stored}", size))
    except Exception:
        for _, rel, _ in saved:
            (root() / rel).unlink(missing_ok=True)
        if 'path' in locals():
            path.unlink(missing_ok=True)
        raise
    return saved


def path_of(stored_relpath):
    path = (root() / stored_relpath).resolve()
    if root().resolve() not in path.parents:
        raise UploadError("잘못된 파일 경로입니다.")
    return path
