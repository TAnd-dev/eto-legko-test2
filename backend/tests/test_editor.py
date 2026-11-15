"""Сценарии редактора из видео, через HTTP API с Keitaro в памяти."""


def fetch(client, campaign_id):
    response = client.post(f"/api/campaigns/{campaign_id}/fetch-streams")
    assert response.status_code == 200, response.text
    return response.json()


def offers_stream(streams):
    return next(s for s in streams if s["has_offers"])


def view(stream):
    """{offer_id: (share, status)}"""
    return {o["keitaro_offer_id"]: (o["share"], o["status"]) for o in stream["offers"]}


def row_id(stream, offer_id):
    return next(o["id"] for o in stream["offers"] if o["keitaro_offer_id"] == offer_id)


def post(client, url, json=None, status=200):
    response = client.post(url, json=json)
    assert response.status_code == status, response.text
    return response.json()


def test_fetch_shows_offers_only_for_stream_with_offers(client, kt):
    cid = kt.seed_campaign({1: 33, 2: 33, 3: 34})
    streams = fetch(client, cid)

    assert [s["name"] for s in streams] == ["Flow 1", "Flow 2"]
    assert streams[0]["has_offers"] is False and streams[0]["offers"] == []
    assert view(streams[1]) == {1: (33, "active"), 2: (33, "active"), 3: (34, "active")}
    assert streams[1]["dirty"] is False


def test_add_offer_recalculates_and_waits_for_push(client, kt):
    cid = kt.seed_campaign({1: 33, 2: 33, 3: 34})
    stream = offers_stream(fetch(client, cid))

    stream = post(client, f"/api/streams/{stream['id']}/offers", {"offer_id": 4})
    assert view(stream) == {i: (25, "active") for i in (1, 2, 3, 4)}
    assert stream["dirty"] is True
    assert kt.shares(cid) == {1: 33, 2: 33, 3: 34}  # в Keitaro пока без изменений

    stream = post(client, f"/api/streams/{stream['id']}/push")
    assert stream["dirty"] is False
    assert kt.shares(cid) == {1: 25, 2: 25, 3: 25, 4: 25}


def test_cancel_drops_unpublished_offer(client, kt):
    cid = kt.seed_campaign({1: 33, 2: 33, 3: 34})
    stream = offers_stream(fetch(client, cid))
    post(client, f"/api/streams/{stream['id']}/offers", {"offer_id": 4})

    stream = post(client, f"/api/streams/{stream['id']}/cancel")
    assert view(stream) == {1: (33, "active"), 2: (33, "active"), 3: (34, "active")}
    assert stream["dirty"] is False


def test_cancel_reverts_unpublished_removal(client, kt):
    cid = kt.seed_campaign({1: 50, 2: 50})
    stream = offers_stream(fetch(client, cid))
    post(client, f"/api/stream-offers/{row_id(stream, 1)}/remove")

    stream = post(client, f"/api/streams/{stream['id']}/cancel")
    assert view(stream) == {1: (50, "active"), 2: (50, "active")}
    assert stream["dirty"] is False


def test_remove_keeps_offer_in_archive_and_bring_back_restores(client, kt):
    cid = kt.seed_campaign({1: 25, 2: 25, 3: 25, 4: 25})
    stream = offers_stream(fetch(client, cid))

    stream = post(client, f"/api/stream-offers/{row_id(stream, 4)}/remove")
    assert view(stream)[4] == (0, "removed")
    assert [view(stream)[i][0] for i in (1, 2, 3)] == [34, 33, 33]
    assert stream["dirty"] is True

    stream = post(client, f"/api/streams/{stream['id']}/push")
    assert kt.shares(cid) == {1: 34, 2: 33, 3: 33}
    assert view(stream)[4] == (0, "removed")  # остался у нас серым
    assert stream["dirty"] is False

    stream = post(client, f"/api/stream-offers/{row_id(stream, 4)}/bring-back")
    assert stream["dirty"] is True
    post(client, f"/api/streams/{stream['id']}/push")
    assert kt.shares(cid) == {1: 25, 2: 25, 3: 25, 4: 25}


def test_offers_deleted_in_keitaro_become_removed_on_fetch(client, kt):
    cid = kt.seed_campaign({1: 25, 2: 25, 3: 25, 4: 25})
    fetch(client, cid)

    kt.get_campaign_streams(cid)[1]["offers"] = [
        {"offer_id": 1, "share": 50, "state": "active"},
        {"offer_id": 2, "share": 50, "state": "active"},
    ]
    stream = offers_stream(fetch(client, cid))

    assert view(stream) == {
        1: (50, "active"),
        2: (50, "active"),
        3: (0, "removed"),
        4: (0, "removed"),
    }
    assert stream["dirty"] is False

    stream = post(client, f"/api/stream-offers/{row_id(stream, 3)}/bring-back")
    assert stream["dirty"] is True
    assert [view(stream)[i][0] for i in (1, 2, 3)] == [34, 33, 33]


def test_pinned_share_survives_recalculation(client, kt):
    cid = kt.seed_campaign({1: 25, 2: 25, 3: 25, 4: 25})
    stream = offers_stream(fetch(client, cid))
    stream = post(client, f"/api/stream-offers/{row_id(stream, 4)}/remove")
    stream = post(client, f"/api/stream-offers/{row_id(stream, 3)}/remove")
    post(client, f"/api/streams/{stream['id']}/push")
    assert kt.shares(cid) == {1: 50, 2: 50}

    # закрепляем 25% у первого и возвращаем третий
    stream = post(client, f"/api/stream-offers/{row_id(stream, 1)}/pin", {"share": 25})
    assert view(stream)[1] == (25, "active") and view(stream)[2] == (75, "active")
    stream = post(client, f"/api/stream-offers/{row_id(stream, 3)}/bring-back")
    assert view(stream)[1][0] == 25
    assert (view(stream)[2][0], view(stream)[3][0]) == (38, 37)

    post(client, f"/api/streams/{stream['id']}/push")
    assert kt.shares(cid) == {1: 25, 2: 38, 3: 37}
    assert sum(kt.shares(cid).values()) == 100


def test_pin_without_value_keeps_current_share(client, kt):
    cid = kt.seed_campaign({1: 25, 2: 25, 3: 25, 4: 25})
    stream = offers_stream(fetch(client, cid))
    stream = post(client, f"/api/stream-offers/{row_id(stream, 1)}/pin")
    assert stream["dirty"] is False
    stream = post(client, f"/api/stream-offers/{row_id(stream, 4)}/remove")
    assert [view(stream)[i][0] for i in (1, 2, 3, 4)] == [25, 38, 37, 0]


def test_guards(client, kt):
    cid = kt.seed_campaign({1: 100})
    streams = fetch(client, cid)
    plain, stream = streams[0], streams[1]

    post(client, f"/api/streams/{plain['id']}/offers", {"offer_id": 2}, status=400)
    post(client, f"/api/streams/{stream['id']}/offers", {"offer_id": 1}, status=409)
    post(client, f"/api/streams/{stream['id']}/offers", {"offer_id": 999}, status=404)

    # нельзя опубликовать поток без офферов
    post(client, f"/api/stream-offers/{row_id(stream, 1)}/remove")
    post(client, f"/api/streams/{stream['id']}/push", status=400)
    assert kt.shares(cid) == {1: 100}

    # нельзя оставить только закреплённые с суммой меньше 100
    post(client, f"/api/streams/{stream['id']}/cancel")
    post(client, f"/api/streams/{stream['id']}/offers", {"offer_id": 2})
    post(client, f"/api/stream-offers/{row_id(stream, 1)}/pin", {"share": 30})
    stream = client.get(f"/api/campaigns/{cid}/streams").json()[1]
    post(client, f"/api/stream-offers/{row_id(stream, 2)}/remove", status=422)
    stream = client.get(f"/api/campaigns/{cid}/streams").json()[1]
    assert view(stream) == {1: (30, "active"), 2: (70, "active")}  # ничего не сломалось


def test_fetch_keeps_unpublished_draft(client, kt):
    cid = kt.seed_campaign({1: 50, 2: 50})
    stream = offers_stream(fetch(client, cid))
    post(client, f"/api/streams/{stream['id']}/offers", {"offer_id": 3})

    stream = offers_stream(fetch(client, cid))
    assert view(stream) == {1: (34, "active"), 2: (33, "active"), 3: (33, "active")}
    assert stream["dirty"] is True
