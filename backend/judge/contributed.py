"""Contributed fitness functions. Their source is only ever executed inside a sandbox
container (sandbox/evaluator.py); the worker relays points to it."""

import json
import struct
import subprocess
import sys
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from types import TracebackType
from typing import Any

import numpy as np

from .functions import Array, Problem
from .runner import HARNESS, Limits, docker_cmd

EVALUATOR = HARNESS.with_name("evaluator.py")


class SandboxedFunction:
    """Callable f(X) backed by an evaluator container. Use as a context manager.
    If the evaluator dies or stalls, every later value is NaN (which the judge treats
    as a failed evaluation) instead of blocking the worker."""

    def __init__(self, source: str, dim: int, limits: Limits | None = None,
                 sandbox: bool = True) -> None:
        self.dim, self.limits, self.sandbox = dim, limits or Limits(), sandbox
        self.name = f"tr-eval-{uuid.uuid4().hex[:12]}"
        if sandbox:
            cmd = docker_cmd(self.name, self.limits)
            cmd[-1:-1] = ["--entrypoint", "python"]
            cmd += ["-I", "/opt/evaluator.py"]
        else:  # no isolation: tests with trusted source only
            cmd = [sys.executable, "-I", str(EVALUATOR)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL)
        self.lock = threading.Lock()
        self.alive = True
        job = json.dumps({"code": source, "dim": dim}).encode()
        reply = self._exchange(struct.pack("<I", len(job)) + job, 1)
        self.loaded = reply == b"\x00"
        self.alive = self.alive and self.loaded

    def _stop(self) -> None:
        self.alive = False
        if self.sandbox:
            subprocess.run(["docker", "kill", self.name], capture_output=True)
        self.proc.kill()

    def _exchange(self, payload: bytes, expect: int) -> bytes | None:
        """One request/response with a watchdog, so a stalled evaluator cannot hang us."""
        # shortcut: one Timer thread per call is slow for one-point-at-a-time optimizers;
        # switch to a single watchdog thread if contributed problems get heavy use.
        assert self.proc.stdin and self.proc.stdout
        timer = threading.Timer(self.limits.timeout_sec, self._stop)
        timer.start()
        try:
            self.proc.stdin.write(payload)
            self.proc.stdin.flush()
            data = self.proc.stdout.read(expect)
            return data if len(data) == expect else None
        except OSError:
            return None
        finally:
            timer.cancel()

    def __call__(self, X: Array) -> Array:
        X = np.ascontiguousarray(X, dtype=np.float64).reshape(-1, self.dim)
        with self.lock:
            if self.alive:
                data = self._exchange(struct.pack("<I", len(X)) + X.tobytes(), 8 * len(X))
                if data is not None:
                    return np.frombuffer(data, dtype=np.float64).copy()
                self._stop()
        return np.full(len(X), np.nan)

    def __enter__(self) -> "SandboxedFunction":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        self._stop()
        self.proc.wait()


def smoke_test(source: str, lower: float, upper: float, dims: list[int],
               limits: Limits | None = None, sandbox: bool = True) -> dict[str, Any]:
    """Checks a contributed function before a human reviews it: it loads, returns one
    finite value per point, and gives the same values when asked again."""
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: Any, detail: str = "") -> bool:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    for dim in dims:
        with SandboxedFunction(source, dim, limits, sandbox) as f:
            if not check(f"dim {dim}: the code loads and defines f", f.loaded):
                break
            X = np.random.default_rng(dim).uniform(lower, upper, (200, dim))
            first, again = f(X), f(X)
            finite = np.isfinite(first)
            check(f"dim {dim}: finite values on 200 random points", finite.all(),
                  f"{int((~finite).sum())} of 200 values were not finite")
            check(f"dim {dim}: same input gives the same output",
                  np.array_equal(first, again, equal_nan=True))
            # instances shift the landscape by up to 0.2 of the half-width (see register)
            margin = 0.2 * (upper - lower) / 2
            corners = np.array([np.full(dim, lower - margin), np.full(dim, lower),
                                np.full(dim, upper), np.full(dim, upper + margin)])
            check(f"dim {dim}: finite at the corners of the box and slightly beyond",
                  np.isfinite(f(corners)).all())
            if finite.all():
                check(f"dim {dim}: not constant", float(np.ptp(first)) > 0,
                      "every random point had the same value")
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


@contextmanager
def bind(problem: Problem, dim: int, limits: Limits | None = None, sandbox: bool = True
         ) -> Iterator[Problem]:
    """The problem with a live function: contributed problems get an evaluator container
    for as long as the block runs; built-in problems are returned unchanged."""
    if problem.source is None:
        yield problem
        return
    with SandboxedFunction(problem.source, dim, limits, sandbox) as f:
        if not f.loaded:
            raise RuntimeError(f"contributed function {problem.id} could not be loaded")
        yield replace(problem, fn=f)
