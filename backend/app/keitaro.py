"""Тонкий клиент Keitaro Admin API v1 (https://admin-api.docs.keitaro.io)."""

import time

import httpx

from .config import get_settings

OFFERS_CACHE_TTL = 60


class KeitaroError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class KeitaroClient:
    def __init__(self, base_url: str, api_key: str, transport=None):
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + "/admin_api/v1",
            headers={"Api-Key": api_key},
            timeout=30,
            transport=transport,
        )
        self._offers_cache: tuple[float, list[dict]] | None = None

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise KeitaroError(f"Keitaro недоступен: {exc}") from exc
        if response.status_code >= 400:
            raise KeitaroError(
                f"Keitaro ответил {response.status_code} на {method} {path}: "
                f"{response.text[:500]}",
                response.status_code,
            )
        return response.json() if response.content else None

    # --- справочники ---

    def get_offers(self, fresh: bool = False) -> list[dict]:
        now = time.monotonic()
        if not fresh and self._offers_cache and now - self._offers_cache[0] < OFFERS_CACHE_TTL:
            return self._offers_cache[1]
        offers = self._request("GET", "/offers")
        self._offers_cache = (now, offers)
        return offers

    def get_domains(self) -> list[dict]:
        return self._request("GET", "/domains")

    def get_campaign_groups(self) -> list[dict]:
        return self._request("GET", "/groups", params={"type": "campaigns"})

    def get_traffic_sources(self) -> list[dict]:
        return self._request("GET", "/traffic_sources")

    def create_domain(self, name: str) -> list[dict]:
        return self._request("POST", "/domains", json={"name": name})

    def create_campaign_group(self, name: str) -> dict:
        return self._request("POST", "/groups", json={"name": name, "type": "campaigns"})

    def create_traffic_source(self, name: str) -> dict:
        return self._request("POST", "/traffic_sources", json={"name": name})

    # --- кампании ---

    def get_campaigns(self) -> list[dict]:
        return self._request("GET", "/campaigns")

    def get_campaign(self, campaign_id: int) -> dict:
        return self._request("GET", f"/campaigns/{campaign_id}")

    def create_campaign(self, payload: dict) -> dict:
        return self._request("POST", "/campaigns", json=payload)

    def archive_campaign(self, campaign_id: int) -> None:
        self._request("DELETE", f"/campaigns/{campaign_id}")

    # --- потоки ---

    def get_campaign_streams(self, campaign_id: int) -> list[dict]:
        return self._request("GET", f"/campaigns/{campaign_id}/streams")

    def create_stream(self, payload: dict) -> dict:
        return self._request("POST", "/streams", json=payload)

    def update_stream(self, stream_id: int, payload: dict) -> dict:
        return self._request("PUT", f"/streams/{stream_id}", json=payload)


_client: KeitaroClient | None = None


def get_keitaro() -> KeitaroClient:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.keitaro_url or not settings.keitaro_api_key:
            raise KeitaroError(
                "Не заданы KEITARO_URL и KEITARO_API_KEY в файле .env"
            )
        _client = KeitaroClient(settings.keitaro_url, settings.keitaro_api_key)
    return _client
