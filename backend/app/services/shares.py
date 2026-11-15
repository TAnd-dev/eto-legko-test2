"""Пересчёт долей офферов в потоке.

Правила:
- удалённые офферы получают 0% и теряют закрепление;
- закреплённые активные сохраняют свою долю;
- остаток до 100% делится поровну между остальными активными,
  лишние проценты от деления достаются первым по порядку.
"""

ACTIVE = "active"


class ShareError(ValueError):
    pass


def recalculate(offers) -> None:
    """Меняет .share (и .pinned у удалённых) у переданных объектов на месте."""
    active = []
    for offer in offers:
        if offer.status == ACTIVE:
            active.append(offer)
        else:
            offer.share = 0
            offer.pinned = False

    if not active:
        return

    free = [o for o in active if not o.pinned]
    pinned_sum = sum(o.share for o in active if o.pinned)

    if pinned_sum > 100:
        raise ShareError(
            f"Закреплённые доли дают в сумме {pinned_sum}% — больше 100%."
        )
    if not free:
        if pinned_sum != 100:
            raise ShareError(
                f"Все офферы закреплены, но их сумма {pinned_sum}%, а не 100%. "
                "Открепите хотя бы один оффер."
            )
        return

    rest = 100 - pinned_sum
    if rest < len(free):
        raise ShareError(
            f"На {len(free)} незакреплённых офферов остаётся всего {rest}% — "
            "уменьшите закреплённые доли."
        )

    base, extra = divmod(rest, len(free))
    for index, offer in enumerate(free):
        offer.share = base + (1 if index < extra else 0)
