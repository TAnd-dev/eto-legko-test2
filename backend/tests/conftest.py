import os

os.environ["DATABASE_URL"] = "sqlite://"  # до импорта приложения

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db import Base, get_db
from app.keitaro import KeitaroError, get_keitaro
from app.main import app


class FakeKeitaro:
    """Keitaro в памяти: хранит то, что хранил бы трекер."""

    def __init__(self):
        self.offers = [{"id": i, "name": f"Offer {i}"} for i in range(1, 8)]
        self.domains = [{"id": 10, "name": "in.posdk.xyz"}]
        self.groups = [{"id": 20, "name": "FORTESTS"}]
        self.sources = [{"id": 30, "name": "FORTESTS"}]
        self.campaigns = []
        self.streams = []
        self.archived = []
        self.fail_stream_number = None
        self._next_id = 100

    def _id(self):
        self._next_id += 1
        return self._next_id

    def get_offers(self, fresh=False):
        return self.offers

    def get_domains(self):
        return self.domains

    def get_campaign_groups(self):
        return self.groups

    def get_traffic_sources(self):
        return self.sources

    def _create(self, items, name):
        item = {"id": self._id(), "name": name}
        items.append(item)
        return item

    def create_domain(self, name):
        return self._create(self.domains, name)

    def create_campaign_group(self, name):
        return self._create(self.groups, name)

    def create_traffic_source(self, name):
        return self._create(self.sources, name)

    def get_campaigns(self):
        return self.campaigns

    def create_campaign(self, payload):
        campaign = {"id": self._id(), **payload}
        self.campaigns.append(campaign)
        return campaign

    def archive_campaign(self, campaign_id):
        self.archived.append(campaign_id)

    def get_campaign_streams(self, campaign_id):
        return [s for s in self.streams if s["campaign_id"] == campaign_id]

    def create_stream(self, payload):
        number = len(self.get_campaign_streams(payload["campaign_id"])) + 1
        if self.fail_stream_number == number:
            raise KeitaroError("boom", 500)
        stream = {"id": self._id(), **payload}
        stream["offers"] = [dict(o) for o in payload.get("offers", [])]
        self.streams.append(stream)
        return stream

    def update_stream(self, stream_id, payload):
        stream = next(s for s in self.streams if s["id"] == stream_id)
        stream.update({**payload, "offers": [dict(o) for o in payload["offers"]]})
        return stream

    # помощники для тестов
    def seed_campaign(self, offer_shares: dict[int, int]) -> int:
        campaign = self.create_campaign({"name": "c", "alias": "a"})
        self.create_stream(
            {"campaign_id": campaign["id"], "name": "Flow 1", "position": 1}
        )
        self.create_stream(
            {
                "campaign_id": campaign["id"],
                "name": "Flow 2",
                "position": 2,
                "offers": [
                    {"offer_id": k, "share": v, "state": "active"}
                    for k, v in offer_shares.items()
                ],
            }
        )
        return campaign["id"]

    def shares(self, campaign_id) -> dict[int, int]:
        stream = self.get_campaign_streams(campaign_id)[1]
        return {o["offer_id"]: o["share"] for o in stream["offers"]}


@pytest.fixture
def kt():
    return FakeKeitaro()


@pytest.fixture
def client(kt):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_keitaro] = lambda: kt
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        keitaro_domain="https://in.posdk.xyz/",
        keitaro_group="FORTESTS",
        keitaro_source="FORTESTS",
        campaign_name_prefix="test_ivanov_",
    )
    yield TestClient(app)
    app.dependency_overrides.clear()
