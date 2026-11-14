"""Executes one run: starts the sandbox, relays points to the hidden function,
enforces the budget and records the trace. The worker side is the only source of
truth; nothing the submission reports about its own result is used.
"""

import json
import math
import os
import struct
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .functions import Array
from .scoring import best_so_far_at, checkpoints

HARNESS = Path(__file__).resolve().parents[2] / "sandbox" / "harness.py"
MAX_RESULT_BYTES = 100_000


@dataclass(frozen=True)
class Limits:
    image: str = "topranker-sandbox:latest"
    runtime: str = "runc"
    cpu: float = 1.0
    memory_mb: int = 512
    timeout_sec: float = 120.0
    pids: int = 64
    log_bytes: int = 64_000

    @classmethod
    def from_env(cls) -> "Limits":
        env = os.environ
        return cls(
            image=env.get("SANDBOX_IMAGE", cls.image),
            runtime=env.get("SANDBOX_RUNTIME", cls.runtime),
            cpu=float(env.get("SANDBOX_CPU", cls.cpu)),
            memory_mb=int(env.get("SANDBOX_MEMORY_MB", cls.memory_mb)),
            timeout_sec=float(env.get("SANDBOX_TIMEOUT_SEC", cls.timeout_sec)),
        )


@dataclass
class RunResult:
    status: str  # ok | error | timeout | crashed
    error: str = ""
    evals: int = 0
    f_best: float = math.inf
    trace: list[float] = field(default_factory=list)  # best-so-far at checkpoints(budget)
    log: str = ""
    wall_sec: float = 0.0


def docker_cmd(name: str, limits: Limits) -> list[str]:
    cmd = [
        "docker", "run", "--rm", "-i", "--name", name,
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
        "--user", "65534:65534",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", str(limits.pids),
        "--memory", f"{limits.memory_mb}m",
        "--memory-swap", f"{limits.memory_mb}m",
        "--cpus", str(limits.cpu),
    ]  # fmt: skip
    if limits.runtime != "runc":
        cmd += ["--runtime", limits.runtime]
    return [*cmd, limits.image]


def run(
    code: str,
    f: Callable[[Array], Array],
    dim: int,
    lower: Array,
    upper: Array,
    budget: int,
    seed: int,
    limits: Limits | None = None,
    sandbox: bool = True,
) -> RunResult:
    """Run a submission once. sandbox=False runs the harness as a plain local
    process with no isolation: only for trusted code (tests, reference runs)."""
    limits = limits or Limits()
    name = f"tr-run-{uuid.uuid4().hex[:12]}"
    cmd = docker_cmd(name, limits) if sandbox else [sys.executable, "-I", str(HARNESS)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    assert proc.stdin and proc.stdout and proc.stderr
    stdin, stdout, stderr = proc.stdin, proc.stdout, proc.stderr

    def stop() -> None:
        if sandbox:
            subprocess.run(["docker", "kill", name], capture_output=True)
        proc.kill()

    timed_out = threading.Event()

    def on_timeout() -> None:
        timed_out.set()
        stop()

    log = bytearray()

    def drain_log() -> None:
        # Keep reading past the cap so a chatty submission never blocks on a full pipe.
        while chunk := os.read(stderr.fileno(), 65536):
            log.extend(chunk[: max(0, limits.log_bytes - len(log))])

    timer = threading.Timer(limits.timeout_sec, on_timeout)
    drainer = threading.Thread(target=drain_log, daemon=True)
    timer.start()
    drainer.start()

    points = checkpoints(budget)
    result = RunResult(status="crashed")
    start = time.monotonic()
    try:
        job = json.dumps({"code": code, "dim": dim, "lower": lower.tolist(),
                          "upper": upper.tolist(), "budget": budget, "seed": seed}).encode()
        stdin.write(struct.pack("<I", len(job)) + job)
        stdin.flush()
        while len(head := stdout.read(4)) == 4:
            (n,) = struct.unpack("<I", head)
            if n == 0:
                (size,) = struct.unpack("<I", stdout.read(4))
                if size > MAX_RESULT_BYTES:
                    break
                outcome = json.loads(stdout.read(size))
                result.status = "ok" if outcome["ok"] else "error"
                result.error = str(outcome["error"])
                break
            if n > budget - result.evals:
                result.error = "protocol violation: more points sent than the budget allows"
                break
            raw = stdout.read(n * dim * 8)
            if len(raw) != n * dim * 8:
                break
            X = np.clip(np.frombuffer(raw, dtype=np.float64).reshape(n, dim), lower, upper)
            with np.errstate(all="ignore"):
                values = np.asarray(f(X), dtype=np.float64)
            values = np.where(np.isfinite(values), values, np.inf)
            result.trace += best_so_far_at(values, result.f_best, result.evals, points)
            result.f_best = min(result.f_best, float(values.min()))
            result.evals += n
            stdin.write(values.tobytes())
            stdin.flush()
    except (OSError, ValueError, KeyError, TypeError, struct.error):
        pass  # broken pipe or malformed message: reported as crashed below
    finally:
        try:
            proc.wait(timeout=5 if result.status != "crashed" else 0.5)
        except subprocess.TimeoutExpired:
            pass
        timer.cancel()
        stop()
        proc.wait()
        drainer.join(timeout=5)

    result.wall_sec = time.monotonic() - start
    if result.status == "crashed":
        if timed_out.is_set():
            result.status = "timeout"
            result.error = f"exceeded the {limits.timeout_sec:g}s wall-clock limit"
        elif not result.error:
            result.error = (f"the run ended unexpectedly (exit code {proc.returncode}); "
                            "the usual cause is exceeding the memory limit")
    result.trace += [result.f_best] * (len(points) - len(result.trace))
    result.log = bytes(log).decode("utf-8", errors="replace")
    return result
