"""Логика редактора: черновик в нашей БД, публикация в Keitaro."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..keitaro import KeitaroClient
from ..models import ACTIVE, REMOVED, Stream, StreamOffer
from .errors import ServiceError
from .shares import ShareError, recalculate


def _recalculate(stream: Stream) -> None:
    try:
        recalculate(stream.offers)
    except ShareError as exc:
        raise ServiceError(str(exc), 422) from exc


def list_streams(db: Session, campaign_id: int) -> list[Stream]:
    return list(
        db.scalars(
            select(Stream)
            .where(Stream.keitaro_campaign_id == campaign_id)
            .order_by(Stream.position, Stream.id)
        )
    )


def get_stream(db: Session, stream_id: int) -> Stream:
    stream = db.get(Stream, stream_id)
    if stream is None:
        raise ServiceError("Поток не найден.", 404)
    return stream


def get_stream_offer(db: Session, stream_offer_id: int) -> StreamOffer:
    row = db.get(StreamOffer, stream_offer_id)
    if row is None:
        raise ServiceError("Оффер в потоке не найден.", 404)
    return row


def fetch_streams(db: Session, kt: KeitaroClient, campaign_id: int) -> list[Stream]:
    remote_streams = kt.get_campaign_streams(campaign_id)
    offer_names = {o["id"]: o.get("name", "") for o in kt.get_offers(fresh=True)}
    local = {s.keitaro_stream_id: s for s in list_streams(db, campaign_id)}

    for remote in remote_streams:
        stream = local.pop(remote["id"], None)
        if stream is None:
            stream = Stream(
                keitaro_stream_id=remote["id"], keitaro_campaign_id=campaign_id
            )
            db.add(stream)
        stream.name = remote.get("name") or f"Stream {remote['id']}"
        stream.position = remote.get("position") or 0

        remote_offers = {
            o["offer_id"]: o
            for o in (remote.get("offers") or [])
            if o.get("state", ACTIVE) == ACTIVE
        }
        stream.has_offers = bool(remote_offers) or bool(stream.offers)
        _sync_offers(stream, remote_offers, offer_names)

    # Потоки, которых в Keitaro больше нет.
    for stream in local.values():
        db.delete(stream)

    db.commit()
    return list_streams(db, campaign_id)


def _sync_offers(stream: Stream, remote_offers: dict, offer_names: dict) -> None:
    was_dirty = stream.dirty
    rows = {o.keitaro_offer_id: o for o in stream.offers}

    for offer_id, remote in remote_offers.items():
        share = int(remote.get("share") or 0)
        row = rows.get(offer_id)
        if row is None:
            row = StreamOffer(
                keitaro_offer_id=offer_id, status=ACTIVE, share=share, pinned=False
            )
            stream.offers.append(row)
        elif not was_dirty:
            row.status = ACTIVE
            row.share = share
        row.published_status = ACTIVE
        row.published_share = share
        row.offer_name = offer_names.get(offer_id, row.offer_name or f"Offer {offer_id}")

    for offer_id, row in rows.items():
        if offer_id in remote_offers:
            continue
        # Обёртка знала оффер как опубликованный, а в Keitaro его удалили:
        # считаем, что его удалили и у нас.
        if row.published_status == ACTIVE:
            row.status = REMOVED
            row.share = 0
            row.pinned = False
            row.published_status = REMOVED
            row.published_share = 0

    if was_dirty:
        try:
            recalculate(stream.offers)
        except ShareError:
            # Закрепления больше не сходятся с новым составом — снимаем их.
            for row in stream.offers:
                row.pinned = False
            recalculate(stream.offers)


def add_offer(db: Session, kt: KeitaroClient, stream_id: int, offer_id: int) -> Stream:
    stream = get_stream(db, stream_id)
    if not stream.has_offers:
        raise ServiceError("В этот поток нельзя добавлять офферы: он без офферов.", 400)

    existing = next((o for o in stream.offers if o.keitaro_offer_id == offer_id), None)
    if existing is not None:
        if existing.status == ACTIVE:
            raise ServiceError("Этот оффер уже есть в потоке.", 409)
        existing.status = ACTIVE
    else:
        offer = next((o for o in kt.get_offers() if o["id"] == offer_id), None)
        if offer is None:
            raise ServiceError(f"Оффер {offer_id} не найден в Keitaro.", 404)
        stream.offers.append(
            StreamOffer(
                keitaro_offer_id=offer_id,
                offer_name=offer.get("name", ""),
                status=ACTIVE,
                share=0,
            )
        )
    _recalculate(stream)
    db.commit()
    return stream


def remove_offer(db: Session, stream_offer_id: int) -> Stream:
    row = get_stream_offer(db, stream_offer_id)
    if row.status == REMOVED:
        raise ServiceError("Оффер уже удалён.", 409)
    row.status = REMOVED
    _recalculate(row.stream)
    db.commit()
    return row.stream


def bring_back(db: Session, stream_offer_id: int) -> Stream:
    row = get_stream_offer(db, stream_offer_id)
    if row.status == ACTIVE:
        raise ServiceError("Оффер и так в потоке.", 409)
    row.status = ACTIVE
    _recalculate(row.stream)
    db.commit()
    return row.stream


def pin(db: Session, stream_offer_id: int, share: int | None = None) -> Stream:
    row = get_stream_offer(db, stream_offer_id)
    if row.status != ACTIVE:
        raise ServiceError("Закрепить можно только активный оффер.", 400)
    if share is not None:
        row.share = share
    row.pinned = True
    _recalculate(row.stream)
    db.commit()
    return row.stream


def unpin(db: Session, stream_offer_id: int) -> Stream:
    row = get_stream_offer(db, stream_offer_id)
    row.pinned = False
    _recalculate(row.stream)
    db.commit()
    return row.stream


def push(db: Session, kt: KeitaroClient, stream_id: int) -> Stream:
    stream = get_stream(db, stream_id)
    if not stream.dirty:
        return stream
    active = [o for o in stream.offers if o.status == ACTIVE]
    if not active:
        raise ServiceError(
            "В потоке не осталось офферов — публиковать нечего. "
            "Верните хотя бы один оффер или нажмите Cancel.",
            400,
        )
    total = sum(o.share for o in active)
    if total != 100:
        raise ServiceError(f"Сумма долей {total}%, а должна быть 100%.", 422)

    kt.update_stream(
        stream.keitaro_stream_id,
        {
            "offers": [
                {"offer_id": o.keitaro_offer_id, "share": o.share, "state": "active"}
                for o in active
            ]
        },
    )
    for row in stream.offers:
        row.published_status = row.status
        row.published_share = row.share
    db.commit()
    return stream


def cancel(db: Session, stream_id: int) -> Stream:
    stream = get_stream(db, stream_id)
    for row in list(stream.offers):
        if row.published_status is None:
            stream.offers.remove(row)  # добавлен, но не опубликован
            continue
        row.status = row.published_status
        row.share = row.published_share or 0
        if row.status == REMOVED:
            row.pinned = False
    db.commit()
    return stream
