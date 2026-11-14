"""Isolation tests against the real sandbox container. Skipped when the Docker
daemon or the sandbox image is unavailable (build it with scripts/build_sandbox)."""

import subprocess

import pytest

from judge import baselines
from judge.functions import PROBLEMS
from judge.instance import make_instance
from judge.runner import Limits, RunResult, run

pytestmark = pytest.mark.docker

DIM, BUDGET = 5, 500
INST = make_instance(PROBLEMS["STD-001"], DIM, 1)
OPT = "def optimize(f, dim, lower, upper, budget, rng):\n"


@pytest.fixture(scope="module", autouse=True)
def _image() -> None:
    try:
        found = subprocess.run(["docker", "image", "inspect", Limits().image],
                               capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        found = False
    if not found:
        pytest.skip("sandbox image not available")


def go(code: str, **limits: float) -> RunResult:
    return run(code, INST, DIM, INST.lower, INST.upper, BUDGET, 1,
               Limits(**{"timeout_sec": 60, **limits}))  # type: ignore[arg-type]


def probe(body: str, **limits: float) -> RunResult:
    """Run a snippet that must raise inside the sandbox; the run then ends as 'error'."""
    return go(OPT + "".join(f"    {line}\n" for line in body.splitlines()), **limits)


def test_normal_run_works_in_the_sandbox() -> None:
    r = go(baselines.source("differential_evolution"))
    assert (r.status, r.evals) == ("ok", BUDGET), r.error


def test_no_network() -> None:
    r = probe("import socket\nsocket.create_connection(('1.1.1.1', 53), timeout=5)")
    assert r.status == "error" and "OSError" in r.error
    r = probe("import socket\nsocket.getaddrinfo('example.com', 80)")
    assert r.status == "error"


def test_cannot_write_outside_tmp() -> None:
    for path in ("/opt/harness.py", "/home/x", "/etc/x", "/usr/local/x", "/x"):
        r = probe(f"open({path!r}, 'w').write('x')")
        assert r.status == "error" and "Error" in r.error, path


def test_tmp_is_writable_but_small() -> None:
    assert probe("open('/tmp/ok', 'w').write('x')\nf(lower)").status == "ok"
    r = probe("open('/tmp/big', 'wb').write(b'x' * (64 * 1024 * 1024))")
    assert r.status == "error" and "No space left" in r.error


def test_runs_as_unprivileged_user_without_capabilities() -> None:
    r = probe("import os\n"
              "assert os.getuid() == 65534, os.getuid()\n"
              "caps = [l for l in open('/proc/self/status') if l.startswith('CapEff')][0]\n"
              "assert int(caps.split()[1], 16) == 0, caps\n"
              "os.setuid(0)")
    assert r.status == "error" and "PermissionError" in r.error


def test_fork_bomb_is_contained() -> None:
    r = probe("import os\nwhile True:\n    os.fork()", timeout_sec=20)
    assert r.status in ("error", "timeout", "crashed")
    assert go(baselines.source("random_search")).status == "ok"  # host still healthy


def test_memory_limit() -> None:
    r = probe("import numpy as np\nx = np.ones((4096, 1024, 1024))\nx.sum()", memory_mb=128)
    assert r.status in ("error", "crashed")
    assert "MemoryError" in r.error or "memory limit" in r.error


def test_wall_clock_timeout_kills_and_removes_the_container() -> None:
    r = probe("while True:\n    pass", timeout_sec=3)
    assert r.status == "timeout" and r.wall_sec < 30
    left = subprocess.run(["docker", "ps", "-aq", "--filter", "name=tr-run-"],
                          capture_output=True, text=True).stdout.strip()
    assert left == ""


def test_output_flood_is_truncated() -> None:
    r = probe("for _ in range(2000):\n    print('x' * 100000)\nf(lower)")
    assert r.status == "ok", r.error
    assert len(r.log) <= Limits().log_bytes


def test_hidden_function_is_not_in_the_container() -> None:
    r = probe("import os, sys\n"
              "names = [n for root, _, files in os.walk('/opt') for n in files]\n"
              "assert names == ['harness.py'], names\n"
              "assert 'judge' not in sys.modules\n"
              "import judge")
    assert r.status == "error" and "ModuleNotFoundError" in r.error
