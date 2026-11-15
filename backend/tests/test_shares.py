from types import SimpleNamespace

import pytest

from app.services.shares import ShareError, recalculate


def offer(share=0, status="active", pinned=False):
    return SimpleNamespace(share=share, status=status, pinned=pinned)


def shares(offers):
    return [o.share for o in offers]


def test_four_offers_get_25_each():
    offers = [offer(33), offer(33), offer(34), offer()]
    recalculate(offers)
    assert shares(offers) == [25, 25, 25, 25]


def test_remainder_goes_to_first_offers():
    offers = [offer(), offer(), offer()]
    recalculate(offers)
    assert shares(offers) == [34, 33, 33]


def test_single_offer_gets_100():
    offers = [offer()]
    recalculate(offers)
    assert shares(offers) == [100]


def test_removed_offer_gets_zero_and_loses_pin():
    offers = [offer(50), offer(50, status="removed", pinned=True)]
    recalculate(offers)
    assert shares(offers) == [100, 0]
    assert offers[1].pinned is False


def test_pinned_share_is_kept_and_rest_split():
    # сценарий из видео: закреплён 25%, вернули ещё один оффер
    offers = [offer(25, pinned=True), offer(75), offer(0)]
    recalculate(offers)
    assert shares(offers) == [25, 38, 37]
    assert sum(shares(offers)) == 100


def test_all_removed_is_fine():
    offers = [offer(100, status="removed")]
    recalculate(offers)
    assert shares(offers) == [0]


def test_pinned_over_100_fails():
    with pytest.raises(ShareError):
        recalculate([offer(60, pinned=True), offer(50, pinned=True), offer()])


def test_all_pinned_must_sum_to_100():
    with pytest.raises(ShareError):
        recalculate([offer(25, pinned=True), offer(25, pinned=True)])
    offers = [offer(25, pinned=True), offer(75, pinned=True)]
    recalculate(offers)
    assert shares(offers) == [25, 75]


def test_not_enough_left_for_free_offers():
    with pytest.raises(ShareError):
        recalculate([offer(99, pinned=True), offer(), offer()])
