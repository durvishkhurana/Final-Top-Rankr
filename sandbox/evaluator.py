"""Runs inside a sandbox container. Evaluates a contributed fitness function for the
worker, so contributed code never executes in the worker process.

Protocol (little-endian, over the process's original stdin/stdout):
  worker    -> evaluator : u32 length + JSON job {code, dim}
  evaluator -> worker    : u8 status (0 ok, 1 the code could not be loaded)
  worker    -> evaluator : u32 n + n*dim float64
  evaluator -> worker    : n float64   (NaN where the function failed)

The code must define f(X): X has shape (n, dim), the result n values. A function
written for one point at a time is also accepted and is called row by row.
"""

import json
import os
import struct
import sys

import numpy as np


def main() -> None:
    rx = os.fdopen(os.dup(0), "rb")
    tx = os.fdopen(os.dup(1), "wb")
    os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    def read(n: int) -> bytes:
        data = rx.read(n)
        if len(data) != n:
            os._exit(0)  # worker closed the pipe: finished
        return data

    job = json.loads(read(struct.unpack("<I", read(4))[0]))
    dim = job["dim"]
    try:
        namespace = {"__name__": "problem"}
        exec(compile(job["code"], "problem.py", "exec"), namespace)
        f = namespace["f"]
        assert callable(f)
        status = 0
    except BaseException:
        status = 1
    tx.write(struct.pack("<B", status))
    tx.flush()

    while True:
        (n,) = struct.unpack("<I", read(4))
        X = np.frombuffer(read(n * dim * 8), dtype=np.float64).reshape(n, dim)
        try:
            values = np.asarray(f(X.copy()), dtype=np.float64)
            if values.shape != (n,):  # not vectorised: one point at a time
                values = np.array([float(f(x.copy())) for x in X])
        except BaseException:
            try:
                values = np.array([float(f(x.copy())) for x in X])
            except BaseException:
                values = np.full(n, np.nan)
        tx.write(np.ascontiguousarray(values, dtype=np.float64).tobytes())
        tx.flush()


if __name__ == "__main__":
    main()
