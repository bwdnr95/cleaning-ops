from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.repositories.partners import PartnerRepository
from app.schemas.partner import PartnerRead

router = APIRouter()


@router.get("", response_model=list[PartnerRead])
def list_partners(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> list:
    return PartnerRepository(db).list_active()
