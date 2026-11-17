import csv
import io
from typing import Any

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from judge import baselines
from judge.scoring import checkpoints
from research import stats

from .test_api import RANDOM, other_client, signup, submit
from .test_contests import contest_body, enter, make

CMAES = baselines.source("cmaes")


def test_a12_and_holm() -> None:
    assert stats.a12([3, 4], [1, 2]) == 1.0
    assert stats.a12([1, 2], [3, 4]) == 0.0
    assert stats.a12([1, 2], [1, 2]) == 0.5
    assert stats.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert stats.holm([0.5, 0.9]) == [1.0, 1.0]


def test_bootstrap_interval_contains_the_mean_and_is_stable() -> None:
    values = list(np.random.default_rng(1).normal(0.5, 0.1, 30))
    low, high = stats.bootstrap_ci(values)
    assert low < np.mean(values) < high and high - low < 0.15
    assert stats.bootstrap_ci(values) == (low, high)
    assert stats.bootstrap_ci([0.3]) == (0.3, 0.3)


def test_ecdf_counts_reached_targets() -> None:
    # one run reaching 1e-1 at the second checkpoint and 1e-8 at the third
    assert stats.ecdf([[1e3, 1e-1, 1e-9]], targets=[1, 1e-1, 1e-8]) == pytest.approx(
        [0, 2 / 3, 1])
    assert stats.ecdf([[None, 0.5]], targets=[1]) == [0, 1]  # a failed checkpoint is unmet
    assert stats.ecdf([]) == []


def test_compare_finds_the_clear_winner_and_no_difference_between_equals() -> None:
    blocks = [(i, s) for i in (1, 2, 3) for s in range(1, 6)]
    rng = np.random.default_rng(0)
    good = {b: 0.8 + 0.01 * rng.random() for b in blocks}
    bad = {b: 0.3 + 0.01 * rng.random() for b in blocks}
    same = dict(bad)
    out = stats.compare({1: good, 2: bad, 3: same})
    pairs = {(p["a"], p["b"]): p for p in out["pairs"]}
    assert pairs[1, 2]["significant"] and pairs[1, 2]["better"] == 1 and pairs[1, 2]["a12"] == 1
    assert pairs[2, 3]["p"] == 1.0 and pairs[2, 3]["better"] is None
    assert pairs[1, 2]["p_holm"] >= pairs[1, 2]["p"]
    assert out["summary"][1]["mean_rank"] == 1.0 and out["blocks"] == 15
    assert out["friedman_p"] is not None and out["friedman_p"] < 0.05


@pytest.mark.anyio
async def test_compare_and_export_judged_submissions(client: AsyncClient,
                                                     queued: list[int]) -> None:
    await signup(client, "ada")
    weak = await submit(client, queued, "STD-001", RANDOM)
    async with await other_client() as bob:
        await signup(bob, "bob")
        strong = await submit(bob, queued, "STD-001", CMAES)
    other = await submit(client, queued, "STD-002", RANDOM)

    ids: dict[str, Any] = {"problem_id": "STD-001", "dim": 5,
                           "ids": [weak["id"], strong["id"]]}
    r = await client.get("/api/research/compare", params=ids)
    assert r.status_code == 200, r.text
    out = r.json()
    assert [e["label"] for e in out["entries"]] == ["Ada", "Bob"]
    weak_e, strong_e = out["entries"]
    assert strong_e["mean"] > weak_e["mean"] and strong_e["runs"] == 15
    assert strong_e["ci_low"] <= strong_e["mean"] <= strong_e["ci_high"]
    assert strong_e["mean_rank"] < weak_e["mean_rank"] and out["blocks"] == 15
    assert out["pairs"][0]["significant"] and out["pairs"][0]["better"] == strong["id"]
    assert out["friedman_p"] is None  # only for three or more
    ecdf = strong_e["ecdf"]
    assert len(ecdf) == len(out["checkpoints"]) and ecdf == sorted(ecdf) and ecdf[-1] > 0.5

    mixed = {**ids, "ids": [weak["id"], other["id"]]}
    assert (await client.get("/api/research/compare", params=mixed)).status_code == 422
    one = {**ids, "ids": [weak["id"]]}
    assert (await client.get("/api/research/compare", params=one)).status_code == 422

    r = await client.get("/api/research/runs", params=ids)
    assert r.headers["content-type"].startswith("text/csv")
    assert "STD-001-d5-runs.csv" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 30 and {row["name"] for row in rows} == {"Ada", "Bob"}
    last = f"precision_at_{checkpoints(strong['budget'])[-1]}"
    assert float(rows[0][last]) == pytest.approx(float(rows[0]["precision"]))

    r = await client.get(f"/api/submissions/{strong['id']}/export", params={"format": "json"})
    runs = r.json()
    assert len(runs) == 15 and "code" not in runs[0] and "log" not in runs[0]
    assert set(runs[0]) >= {"instance_seed", "seed", "status", "aocc", "precision"}

    r = await client.get("/api/problems/STD-001/leaderboard/export", params={"dim": 5})
    board = list(csv.DictReader(io.StringIO(r.text)))
    assert [b["name"] for b in board] == ["Bob", "Ada"] and board[0]["rank"] == "1"


@pytest.mark.anyio
async def test_contest_ranking_export(client: AsyncClient, queued: list[int],
                                      session: AsyncSession) -> None:
    await make(session, client, "teach", "instructor")
    cid = (await client.post("/api/contests", json=contest_body())).json()["id"]
    async with await other_client() as ada:
        await signup(ada, "ada")
        await ada.post(f"/api/contests/{cid}/join", json={})
        await enter(ada, queued, cid, "STD-001", RANDOM)
    r = await client.get(f"/api/contests/{cid}/leaderboard/export")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert list(rows[0])[-2:] == ["STD-001@5", "TR-001@5"]
    assert rows[0]["name"] == "Ada" and rows[0]["TR-001@5"] == "" and rows[0]["final"] == "False"
