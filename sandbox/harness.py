"""Runs inside the sandbox container. Loads the submitted optimizer and gives it a
proxy f that sends points to the worker; the real function never enters this process.

Protocol (little-endian, over the process's original stdin/stdout):
  worker  -> harness : u32 length + JSON job {code, dim, lower, upper, budget, seed}
  harness -> worker  : u32 n + n*dim float64      (evaluate n points)
  worker  -> harness : n float64
  harness -> worker  : u32 0 + u32 length + JSON {ok, error}   (finished)
"""

import json
import os
import struct
import sys
import traceback

import numpy as np


class BudgetExhausted(Exception):
    """Raised by f when the evaluation budget is used up. The run then ends normally."""


def main() -> None:
    # Keep private copies of the protocol pipes, then point fd 0/1 elsewhere so that
    # nothing the submission prints or reads can touch the protocol.
    rx = os.fdopen(os.dup(0), "rb")
    tx = os.fdopen(os.dup(1), "wb")
    os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    def read(n: int) -> bytes:
        data = rx.read(n)
        if len(data) != n:
            os._exit(3)  # worker went away
        return data

    job = json.loads(read(struct.unpack("<I", read(4))[0]))
    dim, budget = job["dim"], job["budget"]
    used = 0

    def f(X):
        nonlocal used
        X = np.asarray(X, dtype=np.float64)
        if X.ndim not in (1, 2) or X.shape[-1] != dim:
            raise ValueError(f"f expects shape ({dim},) or (n, {dim}), got {X.shape}")
        P = np.ascontiguousarray(X.reshape(-1, dim))
        remaining = budget - used
        if remaining <= 0:
            raise BudgetExhausted
        sent = P[:remaining]
        if len(sent):
            tx.write(struct.pack("<I", len(sent)) + sent.tobytes())
            tx.flush()
            used += len(sent)
            values = np.frombuffer(read(8 * len(sent)), dtype=np.float64).copy()
        else:
            values = np.empty(0)
        if len(P) > remaining:
            raise BudgetExhausted
        return float(values[0]) if X.ndim == 1 else values

    result = {"ok": True, "error": ""}
    try:
        namespace = {"__name__": "solution", "BudgetExhausted": BudgetExhausted}
        exec(compile(job["code"], "solution.py", "exec"), namespace)
        optimize = namespace.get("optimize")
        if not callable(optimize):
            raise TypeError(
                "the submission must define optimize(f, dim, lower, upper, budget, rng)"
            )
        optimize(f, dim, np.array(job["lower"]), np.array(job["upper"]), budget,
                 np.random.default_rng(job["seed"]))
    except BudgetExhausted:
        pass
    except BaseException:  # includes SystemExit / KeyboardInterrupt raised by the submission
        result = {"ok": False, "error": traceback.format_exc(limit=-8)[-4000:]}

    payload = json.dumps(result).encode()
    tx.write(struct.pack("<II", 0, len(payload)) + payload)
    tx.flush()
    os._exit(0)  # do not wait for threads the submission may have left running


if __name__ == "__main__":
    main()
