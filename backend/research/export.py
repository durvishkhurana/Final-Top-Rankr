"""Comparison exports for papers and other tools: a LaTeX (booktabs) table and an
IOHanalyzer zip. Both take numbers already computed by the platform."""

import io
import json
import re
import zipfile
from collections.abc import Sequence
from typing import Any

from judge.scoring import checkpoints

_TEX = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "\\": r"\textbackslash{}"}


def tex(text: str) -> str:
    return "".join(_TEX.get(c, c) for c in text)


def to_latex(problem_id: str, dim: int, entries: Sequence[dict[str, Any]]) -> str:
    """One row per entry (keys of ComparedEntry); the best mean is bold.
    Needs \\usepackage{booktabs}."""
    best = max(e["mean"] for e in entries)
    lines = [r"\begin{table}", r"\centering",
             rf"\caption{{AOCC on {tex(problem_id)}, $D={dim}$ (higher is better).}}",
             r"\begin{tabular}{lrrrr}", r"\toprule",
             r"Entry & Runs & Mean AOCC (95\% CI) & Median & Mean rank \\", r"\midrule"]
    for e in entries:
        mean = f"{e['mean']:.3f}"
        if e["mean"] == best:
            mean = rf"\textbf{{{mean}}}"
        rank = "--" if e.get("mean_rank") is None else f"{e['mean_rank']:.2f}"
        lines.append(f"{tex(e['label'])} & {e['runs']} & {mean} ({e['ci_low']:.3f}--"
                     f"{e['ci_high']:.3f}) & {e['median']:.3f} & {rank} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_") or "entry"


def improvements(budget: int, evals: int, trace: Sequence[float | None]
                 ) -> list[tuple[int, float]]:
    """Improvement-only (evaluations, precision) rows, ending at the last evaluation."""
    rows: list[tuple[int, float]] = []
    for point, y in zip(checkpoints(budget), trace, strict=False):
        if y is None or point > max(evals, 1):
            continue
        if not rows or y < rows[-1][1]:
            rows.append((point, y))
    if rows and rows[-1][0] != evals and evals > 0:
        rows.append((evals, rows[-1][1]))
    return rows


Run = tuple[int, int, Sequence[float | None]]  # instance seed, evaluations, precision trace


def to_ioh(problem_id: str, dim: int, budget: int,
           entries: Sequence[tuple[str, Sequence[Run]]]) -> bytes:
    """A zip with one folder per entry in the IOHprofiler format, which IOHanalyzer loads
    directly. y is the precision (f - f_ref), so the target is 0."""
    digits = re.findall(r"\d+", problem_id)
    fid, name = int(digits[-1]) if digits else 1, _slug(problem_id)
    path = f"data_f{fid}_{name}/IOHprofiler_f{fid}_DIM{dim}.dat"
    buffer = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for label, runs in entries:
            folder = _slug(label)
            while folder in used:
                folder += "_"
            used.add(folder)
            blocks, meta_runs = [], []
            for instance, evals, trace in runs:
                rows = improvements(budget, evals, trace)
                if not rows:
                    continue
                blocks.append("evaluations raw_y\n" + "".join(f"{ev} {y:.10e}\n"
                                                              for ev, y in rows))
                ev, y = rows[-1]
                meta_runs.append({"instance": instance, "evals": evals,
                                  "best": {"evals": ev, "y": y, "x": []}})
            zf.writestr(f"{folder}/{path}", "".join(blocks))
            zf.writestr(f"{folder}/IOHprofiler_f{fid}_{name}.json", json.dumps({
                "version": "0.3.5", "suite": "TopRanker", "function_id": fid,
                "function_name": name, "maximization": False,
                "algorithm": {"name": label, "info": "TopRanker export"},
                "attributes": ["evaluations", "raw_y"],
                "scenarios": [{"dimension": dim, "path": path, "runs": meta_runs}]}, indent=2))
    return buffer.getvalue()
