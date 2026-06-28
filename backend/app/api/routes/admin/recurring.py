from fastapi import APIRouter, Depends, HTTPException, Response

from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.domain.constants import RecurringContractStatus
from app.schemas.recurring import (
    ApproveOccurrencesRequest,
    ApproveOccurrencesResult,
    PendingOccurrenceRead,
    RecurringContractCreate,
    RecurringContractRead,
    RecurringContractSummaryRead,
    RecurringContractUpdate,
    RecurringOccurrenceRead,
    SkipOccurrencesRequest,
    SkipOccurrencesResult,
)
from app.services.recurring import RecurringService

router = APIRouter()


def _err(exc: ValueError) -> HTTPException:
    detail = str(exc)
    return HTTPException(status_code=404 if detail.endswith("_not_found") else 400, detail=detail)


@router.get("/contracts", response_model=list[RecurringContractSummaryRead])
def list_contracts(db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    return RecurringService(db).list_contract_summaries()


@router.post("/contracts", response_model=RecurringContractRead, status_code=201)
def create_contract(
    payload: RecurringContractCreate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    svc = RecurringService(db)
    try:
        contract = svc.create_contract(payload, actor_user_id=user.id)
    except ValueError as exc:
        raise _err(exc) from exc
    return svc.to_contract_read(contract)


@router.get("/contracts/{contract_id}", response_model=RecurringContractRead)
def get_contract(contract_id: str, db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    svc = RecurringService(db)
    contract = svc.get_contract(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="recurring_contract_not_found")
    return svc.to_contract_read(contract)


@router.get("/contracts/{contract_id}/occurrences", response_model=list[RecurringOccurrenceRead])
def list_contract_occurrences(
    contract_id: str, db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)
):
    try:
        return RecurringService(db).list_contract_occurrences(contract_id)
    except ValueError as exc:
        raise _err(exc) from exc


@router.patch("/contracts/{contract_id}", response_model=RecurringContractRead)
def update_contract(
    contract_id: str,
    payload: RecurringContractUpdate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    svc = RecurringService(db)
    try:
        contract = svc.update_contract(contract_id, payload, actor_user_id=user.id)
    except ValueError as exc:
        raise _err(exc) from exc
    return svc.to_contract_read(contract)


@router.post("/contracts/{contract_id}/pause", response_model=RecurringContractRead)
def pause_contract(contract_id: str, db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    svc = RecurringService(db)
    try:
        return svc.to_contract_read(svc.set_status(contract_id, RecurringContractStatus.PAUSED))
    except ValueError as exc:
        raise _err(exc) from exc


@router.post("/contracts/{contract_id}/resume", response_model=RecurringContractRead)
def resume_contract(contract_id: str, db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    svc = RecurringService(db)
    try:
        return svc.to_contract_read(svc.set_status(contract_id, RecurringContractStatus.ACTIVE))
    except ValueError as exc:
        raise _err(exc) from exc


@router.post("/contracts/{contract_id}/end", response_model=RecurringContractRead)
def end_contract(contract_id: str, db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    svc = RecurringService(db)
    try:
        return svc.to_contract_read(svc.set_status(contract_id, RecurringContractStatus.ENDED))
    except ValueError as exc:
        raise _err(exc) from exc


@router.delete("/contracts/{contract_id}", status_code=204)
def delete_contract(contract_id: str, db: Session = Depends(get_session), user: CurrentUser = Depends(require_admin)):
    svc = RecurringService(db)
    try:
        svc.delete_contract(contract_id, actor_user_id=user.id)
    except ValueError as exc:
        raise _err(exc) from exc
    return Response(status_code=204)


@router.post("/occurrences/sync", response_model=list[PendingOccurrenceRead])
def sync_occurrences(db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    svc = RecurringService(db)
    svc.sync_due_occurrences()
    return svc.list_pending_views()


@router.get("/occurrences/pending", response_model=list[PendingOccurrenceRead])
def list_pending(db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    return RecurringService(db).list_pending_views()


@router.post("/occurrences/approve", response_model=ApproveOccurrencesResult)
def approve_occurrences(
    payload: ApproveOccurrencesRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    return RecurringService(db).approve_occurrences(payload.items, actor_user_id=user.id)


@router.post("/occurrences/skip", response_model=SkipOccurrencesResult)
def skip_occurrences(
    payload: SkipOccurrencesRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    return RecurringService(db).skip_occurrences(payload.items, actor_user_id=user.id)
