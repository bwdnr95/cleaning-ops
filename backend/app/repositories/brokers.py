from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.broker import Broker
from app.repositories.base import Repository


class BrokerRepository(Repository[Broker]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Broker)

    def list_all(self) -> list[Broker]:
        stmt = select(Broker).order_by(Broker.is_active.desc(), Broker.name.asc())
        return list(self.db.scalars(stmt))

    def list_active(self) -> list[Broker]:
        stmt = select(Broker).where(Broker.is_active.is_(True)).order_by(Broker.name.asc())
        return list(self.db.scalars(stmt))
