from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ACTIVE = "active"
REMOVED = "removed"


class Stream(Base):
    __tablename__ = "streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    keitaro_stream_id: Mapped[int] = mapped_column(unique=True)
    keitaro_campaign_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str]
    position: Mapped[int] = mapped_column(default=0)
    has_offers: Mapped[bool] = mapped_column(default=False)

    offers: Mapped[list["StreamOffer"]] = relationship(
        back_populates="stream",
        cascade="all, delete-orphan",
        order_by="StreamOffer.id",
    )

    @property
    def dirty(self) -> bool:
        """Есть неопубликованные изменения (поток «жёлтый»)."""
        return any(o.changed for o in self.offers)


class StreamOffer(Base):
    __tablename__ = "stream_offers"
    __table_args__ = (UniqueConstraint("stream_id", "keitaro_offer_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stream_id: Mapped[int] = mapped_column(ForeignKey("streams.id"))
    keitaro_offer_id: Mapped[int]
    offer_name: Mapped[str] = mapped_column(default="")

    # Черновик — то, что видит пользователь в обёртке.
    status: Mapped[str] = mapped_column(default=ACTIVE)
    share: Mapped[int] = mapped_column(default=0)
    pinned: Mapped[bool] = mapped_column(default=False)

    # Последнее состояние, совпадающее с Keitaro. NULL — ещё не публиковался.
    published_status: Mapped[str | None] = mapped_column(default=None)
    published_share: Mapped[int | None] = mapped_column(default=None)

    stream: Mapped[Stream] = relationship(back_populates="offers")

    @property
    def changed(self) -> bool:
        return (
            self.status != self.published_status
            or self.share != self.published_share
        )
