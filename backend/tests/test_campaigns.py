def test_create_campaign_with_two_streams(client, kt):
    response = client.post(
        "/api/campaigns", json={"name": "campaign1", "geo": "au", "offer_id": 3}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "test_ivanov_campaign1"
    assert body["url"] == f"https://in.posdk.xyz/{body['alias']}"

    assert body["warnings"] == []
    campaign = kt.campaigns[0]
    assert campaign["domain_id"] == 10
    assert campaign["group_id"] == 20
    assert campaign["traffic_source_id"] == 30

    first, second = kt.get_campaign_streams(campaign["id"])
    assert first["position"] == 1
    assert first["schema"] == "redirect"
    assert first["action_type"] == "http"
    assert first["action_payload"] == "https://google.com"
    assert first["filters"] == [{"name": "country", "mode": "accept", "payload": ["AU"]}]
    assert second["position"] == 2
    assert second["schema"] == "landings"
    assert second["offers"] == [{"offer_id": 3, "share": 100, "state": "active"}]


def test_prefix_is_not_duplicated(client, kt):
    response = client.post(
        "/api/campaigns", json={"name": "test_ivanov_x", "geo": "MX, RO", "offer_id": 1}
    )
    assert response.json()["name"] == "test_ivanov_x"
    first = kt.get_campaign_streams(kt.campaigns[0]["id"])[0]
    assert first["filters"][0]["payload"] == ["MX", "RO"]


def test_validation(client, kt):
    bad_geo = client.post("/api/campaigns", json={"name": "x", "geo": "AUS", "offer_id": 1})
    assert bad_geo.status_code == 422
    no_offer = client.post("/api/campaigns", json={"name": "x", "geo": "AU", "offer_id": 99})
    assert no_offer.status_code == 404
    assert kt.campaigns == []


def test_missing_domain_group_source_are_created_once(client, kt):
    kt.domains, kt.groups, kt.sources = [], [], []
    for name in ("x", "y"):
        response = client.post(
            "/api/campaigns", json={"name": name, "geo": "AU", "offer_id": 1}
        )
        assert response.status_code == 201, response.text

    assert [d["name"] for d in kt.domains] == ["in.posdk.xyz"]
    assert [g["name"] for g in kt.groups] == ["FORTESTS"]
    assert [s["name"] for s in kt.sources] == ["FORTESTS"]
    for campaign in kt.campaigns:
        assert campaign["domain_id"] == kt.domains[0]["id"]
        assert campaign["group_id"] == kt.groups[0]["id"]
        assert campaign["traffic_source_id"] == kt.sources[0]["id"]


def test_campaign_is_archived_when_stream_creation_fails(client, kt):
    kt.fail_stream_number = 2
    response = client.post("/api/campaigns", json={"name": "x", "geo": "AU", "offer_id": 1})
    assert response.status_code == 502
    assert kt.archived == [kt.campaigns[0]["id"]]


def test_offer_search(client, kt):
    kt.offers.append({"id": 3749, "name": "Miaflow [BEAUTY-RO-BE_0009]"})
    assert [o["id"] for o in client.get("/api/offers?q=miaflow").json()] == [3749]
    assert [o["id"] for o in client.get("/api/offers?q=37").json()] == [3749]


def test_empty_settings_are_skipped(client, kt):
    from app.config import Settings, get_settings
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        keitaro_url="https://tracker.test/",
        keitaro_domain="",
        keitaro_source="",
        keitaro_group="FORTESTS",
    )
    kt.domains = []
    kt.sources = []
    response = client.post("/api/campaigns", json={"name": "x", "geo": "AU", "offer_id": 1})
    assert response.status_code == 201, response.text
    campaign = kt.campaigns[0]
    assert "domain_id" not in campaign and "traffic_source_id" not in campaign
    assert campaign["group_id"] == 20
    assert response.json()["url"] == f"https://tracker.test/{campaign['alias']}"


def test_campaign_is_created_with_warnings_when_links_fail(client, kt):
    from app.keitaro import KeitaroError

    def forbidden(name):
        raise KeitaroError("no permission", 403)

    kt.domains = []
    kt.sources = []
    kt.create_domain = forbidden
    kt.create_traffic_source = forbidden
    response = client.post("/api/campaigns", json={"name": "x", "geo": "AU", "offer_id": 1})

    # кампания всё равно создаётся — без домена и источника, но с группой и потоками
    assert response.status_code == 201, response.text
    warnings = response.json()["warnings"]
    assert len(warnings) == 2
    assert "KEITARO_DOMAIN" in warnings[0] and "нет прав" in warnings[0]
    assert "расширить права ключа" in warnings[0]
    assert "KEITARO_SOURCE" in warnings[1]
    campaign = kt.campaigns[0]
    assert "domain_id" not in campaign and "traffic_source_id" not in campaign
    assert campaign["group_id"] == 20
    assert len(kt.get_campaign_streams(campaign["id"])) == 2


def test_config_exposes_keitaro_admin_url(client):
    from app.config import Settings, get_settings
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, keitaro_url="https://tracker.test/"
    )
    assert client.get("/api/config").json()["keitaro_admin_url"] == "https://tracker.test/admin/"
