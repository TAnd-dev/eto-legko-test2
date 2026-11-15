import re
import secrets
import string

from ..config import Settings
from ..keitaro import KeitaroClient, KeitaroError
from .errors import ServiceError

REDIRECT_URL = "https://google.com"
ALIAS_ALPHABET = string.ascii_letters + string.digits


def full_name(name: str, prefix: str) -> str:
    name = name.strip()
    if prefix and not name.startswith(prefix):
        return prefix + name
    return name


def parse_geo(geo: str) -> list[str]:
    codes = [code.strip().upper() for code in geo.split(",") if code.strip()]
    if not codes:
        raise ServiceError("Укажите гео-код страны, например AU.", 422)
    for code in codes:
        if not re.fullmatch(r"[A-Z]{2}", code):
            raise ServiceError(
                f"«{code}» не похоже на двухбуквенный код страны (AU, MX, RO…).", 422
            )
    return codes


def _domain_key(value: str) -> str:
    return re.sub(r"^https?://", "", value.strip().lower()).strip("/")


class LinkUnavailable(Exception):
    """Домен, группу или источник не удалось ни найти, ни создать."""


def _find_or_create(
    name: str, fetch, create, what: str, setting: str, key=lambda v: v.strip().lower()
) -> int | None:
    """ID записи с таким именем; если её нет в Keitaro — создаём.

    Пустое имя в .env означает «не проставлять это поле».
    """
    name = name.strip()
    if not name:
        return None
    try:
        for item in fetch():
            if key(str(item.get("name", ""))) == key(name):
                return item["id"]
        created = create(name)
    except KeitaroError as exc:
        if exc.status_code == 403:
            reason = "у API-ключа нет прав на этот раздел"
            advice = (
                "Вы можете расширить права ключа в Keitaro — тогда запись "
                f"создастся при следующей кампании — или оставить {setting} "
                "в .env пустым."
            )
        else:
            reason = exc.message
            advice = f"Чтобы убрать предупреждение, оставьте {setting} в .env пустым."
        raise LinkUnavailable(
            f"Кампания создана без {what} «{name}»: {reason}. {advice}"
        ) from exc
    # Keitaro на создание домена отвечает списком, на остальное — объектом.
    if isinstance(created, list):
        created = created[0]
    return created["id"]


def create_campaign(
    kt: KeitaroClient, settings: Settings, name: str, geo: str, offer_id: int
) -> dict:
    name = full_name(name, settings.campaign_name_prefix)
    if not name:
        raise ServiceError("Укажите название кампании.", 422)
    countries = parse_geo(geo)

    if not any(o["id"] == offer_id for o in kt.get_offers()):
        raise ServiceError(f"Оффер {offer_id} не найден в Keitaro.", 404)

    # Домен, группа и источник не должны мешать созданию кампании:
    # если что-то из них недоступно, создаём без него и предупреждаем.
    warnings: list[str] = []

    def link(*args) -> int | None:
        try:
            return _find_or_create(*args)
        except LinkUnavailable as exc:
            warnings.append(str(exc))
            return None

    links = {
        "domain_id": link(
            _domain_key(settings.keitaro_domain),
            kt.get_domains,
            kt.create_domain,
            "домена",
            "KEITARO_DOMAIN",
            _domain_key,
        ),
        "group_id": link(
            settings.keitaro_group,
            kt.get_campaign_groups,
            kt.create_campaign_group,
            "группы",
            "KEITARO_GROUP",
        ),
        "traffic_source_id": link(
            settings.keitaro_source,
            kt.get_traffic_sources,
            kt.create_traffic_source,
            "источника",
            "KEITARO_SOURCE",
        ),
    }

    campaign = kt.create_campaign(
        {
            "name": name,
            "alias": "".join(secrets.choice(ALIAS_ALPHABET) for _ in range(8)),
            "type": "position",
            "state": "active",
            **{field: value for field, value in links.items() if value is not None},
        }
    )

    common = {
        "campaign_id": campaign["id"],
        "type": "regular",
        "state": "active",
        "collect_clicks": True,
        "filter_or": False,
        "weight": 100,
    }
    try:
        kt.create_stream(
            {
                **common,
                "name": "Flow 1",
                "position": 1,
                "schema": "redirect",
                "action_type": "http",
                "action_payload": REDIRECT_URL,
                "filters": [
                    {"name": "country", "mode": "accept", "payload": countries}
                ],
            }
        )
        kt.create_stream(
            {
                **common,
                "name": "Flow 2",
                "position": 2,
                "schema": "landings",
                "action_type": "http",
                "offers": [{"offer_id": offer_id, "share": 100, "state": "active"}],
            }
        )
    except KeitaroError as exc:
        try:
            kt.archive_campaign(campaign["id"])
            cleanup = "кампания убрана в архив"
        except KeitaroError:
            cleanup = f"кампанию {campaign['id']} убрать не удалось, удалите вручную"
        raise ServiceError(
            f"Не удалось создать потоки ({cleanup}): {exc.message}", 502
        ) from exc

    alias = campaign.get("alias", "")
    return {
        "id": campaign["id"],
        "name": campaign.get("name", name),
        "alias": alias,
        "warnings": warnings,
        # без своего домена кампания открывается по адресу самого трекера
        "url": (
            f"https://{_domain_key(settings.keitaro_domain)}/{alias}"
            if links["domain_id"] is not None
            else f"{settings.keitaro_url.rstrip('/')}/{alias}"
        ),
    }
