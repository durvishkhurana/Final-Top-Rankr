"""Starter templates offered in the submission editor."""

from pathlib import Path

TEMPLATES = {
    "random_search": "Random search",
    "one_plus_one_es": "(1+1) evolution strategy",
    "minimal_de": "Minimal differential evolution",
}


def source(name: str) -> str:
    return (Path(__file__).parent / f"{name}.py").read_text(encoding="utf-8")
