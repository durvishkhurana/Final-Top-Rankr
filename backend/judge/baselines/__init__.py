"""Baseline optimizers. Each file is an ordinary submission and is judged like one."""

from pathlib import Path

NAMES = ("random_search", "differential_evolution", "cmaes")


def source(name: str) -> str:
    return (Path(__file__).parent / f"{name}.py").read_text(encoding="utf-8")
