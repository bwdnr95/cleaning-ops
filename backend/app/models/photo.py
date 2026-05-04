from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import PhotoType
from app.models.base import Base, CreatedAtMixin


class OrderPhoto(CreatedAtMixin, Base):
    __tablename__ = "order_photos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    uploaded_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    photo_type: Mapped[PhotoType] = mapped_column(String(20), index=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), index=True)
    file_url: Mapped[str] = mapped_column(String(1000))
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(120))
    is_customer_visible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
