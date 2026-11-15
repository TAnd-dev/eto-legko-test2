from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from . import schemas
from .config import Settings, get_settings
from .db import get_db
from .keitaro import KeitaroClient, get_keitaro
from .services import campaigns as campaign_service
from .services import streams as stream_service

router = APIRouter(prefix="/api")


@router.get("/config", response_model=schemas.AppConfig)
def config(settings: Settings = Depends(get_settings)):
    return schemas.AppConfig(
        campaign_name_prefix=settings.campaign_name_prefix,
        domain=settings.keitaro_domain,
        group=settings.keitaro_group,
        source=settings.keitaro_source,
        keitaro_admin_url=settings.keitaro_url.rstrip("/") + "/admin/",
    )


def _search(items: list[dict], q: str, limit: int) -> list[dict]:
    q = q.strip().lower()
    if q:
        items = [
            i
            for i in items
            if q in str(i.get("name", "")).lower() or str(i["id"]).startswith(q)
        ]
    return sorted(items, key=lambda i: i["id"], reverse=True)[:limit]


@router.get("/offers", response_model=list[schemas.OfferOut])
def search_offers(q: str = "", kt: KeitaroClient = Depends(get_keitaro)):
    return _search(kt.get_offers(), q, 20)


@router.get("/campaigns", response_model=list[schemas.CampaignOut])
def search_campaigns(q: str = "", kt: KeitaroClient = Depends(get_keitaro)):
    return _search(kt.get_campaigns(), q, 30)


@router.post("/campaigns", response_model=schemas.CampaignCreated, status_code=201)
def create_campaign(
    body: schemas.CampaignCreate,
    kt: KeitaroClient = Depends(get_keitaro),
    settings: Settings = Depends(get_settings),
):
    return campaign_service.create_campaign(
        kt, settings, body.name, body.geo, body.offer_id
    )


@router.get("/campaigns/{campaign_id}/streams", response_model=list[schemas.StreamOut])
def list_streams(campaign_id: int, db: Session = Depends(get_db)):
    return stream_service.list_streams(db, campaign_id)


@router.post(
    "/campaigns/{campaign_id}/fetch-streams", response_model=list[schemas.StreamOut]
)
def fetch_streams(
    campaign_id: int,
    db: Session = Depends(get_db),
    kt: KeitaroClient = Depends(get_keitaro),
):
    return stream_service.fetch_streams(db, kt, campaign_id)


@router.post("/streams/{stream_id}/offers", response_model=schemas.StreamOut)
def add_offer(
    stream_id: int,
    body: schemas.AddOffer,
    db: Session = Depends(get_db),
    kt: KeitaroClient = Depends(get_keitaro),
):
    return stream_service.add_offer(db, kt, stream_id, body.offer_id)


@router.post("/streams/{stream_id}/push", response_model=schemas.StreamOut)
def push(
    stream_id: int,
    db: Session = Depends(get_db),
    kt: KeitaroClient = Depends(get_keitaro),
):
    return stream_service.push(db, kt, stream_id)


@router.post("/streams/{stream_id}/cancel", response_model=schemas.StreamOut)
def cancel(stream_id: int, db: Session = Depends(get_db)):
    return stream_service.cancel(db, stream_id)


@router.post("/stream-offers/{row_id}/remove", response_model=schemas.StreamOut)
def remove_offer(row_id: int, db: Session = Depends(get_db)):
    return stream_service.remove_offer(db, row_id)


@router.post("/stream-offers/{row_id}/bring-back", response_model=schemas.StreamOut)
def bring_back(row_id: int, db: Session = Depends(get_db)):
    return stream_service.bring_back(db, row_id)


@router.post("/stream-offers/{row_id}/pin", response_model=schemas.StreamOut)
def pin(
    row_id: int,
    body: schemas.PinRequest | None = None,
    db: Session = Depends(get_db),
):
    return stream_service.pin(db, row_id, body.share if body else None)


@router.post("/stream-offers/{row_id}/unpin", response_model=schemas.StreamOut)
def unpin(row_id: int, db: Session = Depends(get_db)):
    return stream_service.unpin(db, row_id)
