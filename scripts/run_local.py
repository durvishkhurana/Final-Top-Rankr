"""Judge an optimizer file locally and print the result.

    python scripts/run_local.py my_optimizer.py --problem STD-004 --dim 10
    python scripts/run_local.py --baseline cmaes --problem TR-003

Runs in the sandbox container by default. --no-sandbox runs the file as a plain
local process with no isolation; use it only for code you trust.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from judge import baselines  # noqa: E402
from judge.evaluate import PUBLIC_INSTANCE_SEEDS, RUN_SEEDS, judge  # noqa: E402
from judge.functions import PROBLEMS  # noqa: E402
from judge.runner import Limits  # noqa: E402

F_REF_FILE = ROOT / "data" / "f_ref.json"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file", nargs="?", help="Python file defining optimize(...)")
    ap.add_argument("--baseline", choices=baselines.NAMES)
    ap.add_argument("--problem", default="STD-001", choices=sorted(PROBLEMS))
    ap.add_argument("--dim", type=int, default=5)
    ap.add_argument("--budget", type=int, help="default: 2000 x dim")
    ap.add_argument("--instances", type=int, nargs="+", default=list(PUBLIC_INSTANCE_SEEDS))
    ap.add_argument("--seeds", type=int, nargs="+", default=list(RUN_SEEDS))
    ap.add_argument("--no-sandbox", action="store_true")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = ap.parse_args()
    if bool(args.file) == bool(args.baseline):
        ap.error("give a file or --baseline, not both")

    code = baselines.source(args.baseline) if args.baseline else Path(args.file).read_text("utf-8")
    f_ref = None
    if F_REF_FILE.exists():
        stored = json.loads(F_REF_FILE.read_text()).get(args.problem, {}).get(str(args.dim), {})
        f_ref = {int(k): v for k, v in stored.items()}

    out = judge(code, PROBLEMS[args.problem], args.dim, args.instances, args.seeds,
                args.budget, f_ref, Limits.from_env(), sandbox=not args.no_sandbox)
    if args.json:
        print(json.dumps(out, indent=1))
        return

    print(f"{args.problem}  dim={args.dim}  budget={out['budget']}")
    print(f"{'instance':>8} {'seed':>4} {'status':>8} {'evals':>7} {'precision':>10} "
          f"{'AOCC':>6} {'sec':>6}")
    for r in out["runs"]:
        prec = f"{r['precision']:.3e}" if r["precision"] is not None else "-"
        print(f"{r['instance_seed']:>8} {r['seed']:>4} {r['status']:>8} {r['evals']:>7} "
              f"{prec:>10} {r['aocc']:>6.3f} {r['wall_sec']:>6.2f}")
    for r in out["runs"]:
        if r["status"] != "ok":
            print(f"\n[instance {r['instance_seed']} seed {r['seed']}] {r['error'].strip()}")
            break
    med = out["median_precision"]
    print(f"\nscore {out['score']:.0f} / 1000   AOCC {out['aocc']:.4f}   "
          f"IQR across seeds {out['iqr']:.4f}   "
          f"median precision {'-' if med is None else format(med, '.3e')}")
    if out["f_ref_provisional"]:
        print("note: no stored best-known value for this problem; scored against the best "
              "of these runs. Run scripts/compute_f_ref.py first for comparable scores.")


if __name__ == "__main__":
    main()
