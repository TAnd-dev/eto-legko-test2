from pydantic import BaseModel, ConfigDict, Field


class OfferOut(BaseModel):
    id: int
    name: str


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1)
    geo: str = Field(min_length=2)
    offer_id: int


class CampaignCreated(BaseModel):
    id: int
    name: str
    alias: str
    url: str
    warnings: list[str] = []


class CampaignOut(BaseModel):
    id: int
    name: str
    alias: str = ""
    state: str = ""


class AppConfig(BaseModel):
    campaign_name_prefix: str
    domain: str
    group: str
    source: str
    keitaro_admin_url: str


class StreamOfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keitaro_offer_id: int
    offer_name: str
    status: str
    share: int
    pinned: bool
    published_status: str | None
    published_share: int | None
    changed: bool


class StreamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keitaro_stream_id: int
    name: str
    position: int
    has_offers: bool
    dirty: bool
    offers: list[StreamOfferOut]


class AddOffer(BaseModel):
    offer_id: int


class PinRequest(BaseModel):
    share: int | None = Field(default=None, ge=1, le=100)
