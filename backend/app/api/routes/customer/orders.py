from collections import OrderedDict
from datetime import timedelta
from typing import Final

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.config import settings
from app.core.time import utc_now
from app.domain.phone import phone_suffix_matches
from app.models.order_group import OrderGroup
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.photos import PhotoRepository
from app.schemas.order import CustomerOrderGroupRead, CustomerVerifyRequest
from app.services.orders import OrderService, to_customer_group_dto
from app.services.photos import normalize_uploaded_photo_content_type
from app.services.storage import StorageProvider, StoredFile, get_storage_provider

router = APIRouter()

_customer_verify_attempts: OrderedDict[str, dict] = OrderedDict()
_CUSTOMER_VERIFY_CACHE_MAX_ENTRIES: Final = 10_000
_CUSTOMER_AS_UPLOAD_CHUNK_BYTES: Final = 1024 * 1024


@router.post("/{customer_token}/verify", response_model=CustomerOrderGroupRead)
def verify_customer_order(
    customer_token: str,
    payload: CustomerVerifyRequest,
    request: Request,
    db: Session = Depends(get_session),
) -> CustomerOrderGroupRead:
    group_repo = OrderGroupRepository(db)
    group = _verify_customer_group(
        customer_token=customer_token,
        phone_suffix=payload.phone_suffix,
        request=request,
        group_repo=group_repo,
    )
    photo_repo = PhotoRepository(db)
    lines_with_photos = [
        (line, photo_repo.list_for_order(line.id, customer_visible_only=True))
        for line in group_repo.list_lines(group.id)
    ]
    return to_customer_group_dto(group, lines_with_photos=lines_with_photos)


@router.post("/{customer_token}/as-request", response_model=CustomerOrderGroupRead)
async def submit_customer_as_request(
    customer_token: str,
    request: Request,
    phone_suffix: str = Form(...),
    order_id: str = Form(...),
    memo: str = Form(...),
    files: list[UploadFile] | None = File(default=None),
    db: Session = Depends(get_session),
) -> CustomerOrderGroupRead:
    _ensure_phone_suffix(phone_suffix)
    group_repo = OrderGroupRepository(db)
    group = _verify_customer_group(
        customer_token=customer_token,
        phone_suffix=phone_suffix,
        request=request,
        group_repo=group_repo,
    )
    lines = group_repo.list_lines(group.id)
    if not any(line.id == order_id for line in lines):
        raise HTTPException(status_code=404, detail="order_not_found")

    service = OrderService(db)
    try:
        service.validate_customer_as_request(order_id, memo=memo)
    except ValueError as exc:
        raise customer_as_http_error(exc) from exc

    storage = get_storage_provider()
    stored_files = await _store_customer_as_files(files or [], storage=storage)
    try:
        service.submit_customer_as_request(
            order_id,
            memo=memo,
            stored_files=stored_files,
        )
    except ValueError as exc:
        _delete_stored_files(stored_files, storage=storage)
        raise customer_as_http_error(exc) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _delete_stored_files(stored_files, storage=storage)
        raise HTTPException(status_code=500, detail="customer_as_request_failed") from exc

    photo_repo = PhotoRepository(db)
    lines_with_photos = [
        (line, photo_repo.list_for_order(line.id, customer_visible_only=True))
        for line in group_repo.list_lines(group.id)
    ]
    return to_customer_group_dto(group, lines_with_photos=lines_with_photos)


def _verify_customer_group(
    *,
    customer_token: str,
    phone_suffix: str,
    request: Request,
    group_repo: OrderGroupRepository,
) -> OrderGroup:
    rate_limit_key = _customer_verify_rate_limit_key(customer_token, request)
    _check_customer_verify_lockout(rate_limit_key)

    group = group_repo.get_by_customer_token(customer_token)
    if group is None or not phone_suffix_matches(group.customer_phone, phone_suffix):
        _record_customer_verify_failure(rate_limit_key)
        raise HTTPException(status_code=404, detail="order_not_found")
    _reset_customer_verify_failures(rate_limit_key)
    return group


def _ensure_phone_suffix(phone_suffix: str) -> None:
    if len(phone_suffix) != 4 or not phone_suffix.isdigit():
        raise HTTPException(status_code=422, detail="invalid_phone_suffix")


async def _store_customer_as_files(
    files: list[UploadFile],
    *,
    storage: StorageProvider,
) -> list[StoredFile]:
    if len(files) > settings.customer_as_max_files:
        raise HTTPException(status_code=413, detail="too_many_as_photos")

    prepared_files: list[tuple[bytes, str, str]] = []
    total_bytes = 0
    for file in files:
        data, total_bytes = await _read_customer_as_file(file, total_bytes_before=total_bytes)
        try:
            content_type = normalize_uploaded_photo_content_type(file.content_type or "", data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        prepared_files.append((data, file.filename or "as-photo", content_type))

    stored_files: list[StoredFile] = []
    try:
        for data, file_name, content_type in prepared_files:
            stored_files.append(
                storage.save_private(
                    data=data,
                    file_name=file_name,
                    content_type=content_type,
                )
            )
    except HTTPException:
        _delete_stored_files(stored_files, storage=storage)
        raise
    except Exception:  # noqa: BROAD_EXCEPT_OK - upload boundary cleans already-saved files.
        _delete_stored_files(stored_files, storage=storage)
        raise
    return stored_files


async def _read_customer_as_file(
    file: UploadFile,
    *,
    total_bytes_before: int,
) -> tuple[bytes, int]:
    chunks: list[bytes] = []
    file_bytes = 0
    while True:
        read_limit = min(
            _CUSTOMER_AS_UPLOAD_CHUNK_BYTES,
            settings.photo_max_upload_bytes - file_bytes + 1,
            settings.customer_as_max_upload_bytes - total_bytes_before - file_bytes + 1,
        )
        if read_limit <= 0:
            raise HTTPException(status_code=413, detail="as_photos_total_too_large")
        chunk = await file.read(read_limit)
        if not chunk:
            break
        file_bytes += len(chunk)
        if file_bytes > settings.photo_max_upload_bytes:
            raise HTTPException(status_code=413, detail="photo_too_large")
        if total_bytes_before + file_bytes > settings.customer_as_max_upload_bytes:
            raise HTTPException(status_code=413, detail="as_photos_total_too_large")
        chunks.append(chunk)
    return b"".join(chunks), total_bytes_before + file_bytes


def _delete_stored_files(files: list[StoredFile], *, storage: StorageProvider) -> None:
    for file in files:
        storage.delete(file.storage_key)


def customer_as_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    if detail == "order_not_found":
        return HTTPException(status_code=404, detail=detail)
    if detail in {
        "invalid_as_request_status",
        "as_request_already_accepted",
        "as_request_already_pending",
        "as_request_conflict",
    }:
        return HTTPException(status_code=409, detail=detail)
    return HTTPException(status_code=400, detail=detail)


def _customer_verify_rate_limit_key(customer_token: str, request: Request) -> str:
    return f"{customer_token}:{_client_ip(request) or 'unknown'}"


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _check_customer_verify_lockout(rate_limit_key: str) -> None:
    attempt = _customer_verify_attempts.get(rate_limit_key)
    if not attempt or not attempt["locked_until"]:
        return
    if utc_now() < attempt["locked_until"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="customer_verify_locked",
        )
    _customer_verify_attempts[rate_limit_key] = {"count": 0, "locked_until": None}


def _record_customer_verify_failure(rate_limit_key: str) -> None:
    attempt = _customer_verify_attempts.setdefault(
        rate_limit_key, {"count": 0, "locked_until": None}
    )
    _customer_verify_attempts.move_to_end(rate_limit_key)
    while len(_customer_verify_attempts) > _CUSTOMER_VERIFY_CACHE_MAX_ENTRIES:
        _customer_verify_attempts.popitem(last=False)
    attempt["count"] += 1
    if attempt["count"] >= settings.customer_verify_max_attempts:
        attempt["locked_until"] = utc_now() + timedelta(
            minutes=settings.customer_verify_lockout_minutes
        )


def _reset_customer_verify_failures(rate_limit_key: str) -> None:
    _customer_verify_attempts.pop(rate_limit_key, None)
