"""Code similarity for instructors: token and syntax-tree comparison with identifiers,
numbers and strings normalised away, so renaming variables does not hide a copy.
It finds pairs worth a human look; it does not detect AI-written code."""

import ast
import builtins
import io
import itertools
import keyword
import tokenize
from difflib import SequenceMatcher
from typing import Any

KEEP = set(keyword.kwlist) | set(dir(builtins)) | {"np", "numpy", "scipy", "math", "rng"}
SKIP = {tokenize.COMMENT, tokenize.NL, tokenize.ENCODING, tokenize.ENDMARKER}
STRUCTURE = {tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE}  # width-independent


def tokens(code: str) -> list[str]:
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type in SKIP:
                continue
            if tok.type == tokenize.NAME:
                out.append(tok.string if tok.string in KEEP else "ID")
            elif tok.type == tokenize.NUMBER:
                out.append("NUM")
            elif tok.type == tokenize.STRING:
                out.append("STR")
            elif tok.type in STRUCTURE:
                out.append(tokenize.tok_name[tok.type])
            else:
                out.append(tok.string or tokenize.tok_name[tok.type])
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return code.split()
    return out


def shape(code: str) -> list[str]:
    try:
        return [type(node).__name__ for node in ast.walk(ast.parse(code))]
    except SyntaxError:
        return []


def _shingles(seq: list[str], k: int = 5) -> set[tuple[str, ...]]:
    return {tuple(seq[i:i + k]) for i in range(max(len(seq) - k + 1, 1))}


def compare(a: str, b: str) -> dict[str, float]:
    ta, tb = _shingles(tokens(a)), _shingles(tokens(b))
    token = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    structure = SequenceMatcher(None, shape(a), shape(b), autojunk=False).ratio()
    return {"token": round(token, 3), "structure": round(structure, 3)}


def closest(code: str, references: dict[str, str]) -> tuple[str | None, float]:
    """The reference (e.g. a starter template) this code is most similar to."""
    best: tuple[str | None, float] = (None, 0.0)
    for name, ref in references.items():
        score = max(compare(code, ref).values())
        if score > best[1]:
            best = (name, score)
    return best


def similar_pairs(items: list[tuple[int, str]], templates: dict[str, str] | None = None,
                  top: int = 20, margin: float = 0.02) -> list[dict[str, Any]]:
    """items: (submission id, code). Returns the most similar pairs, most similar first.
    A pair built on the same starter template is kept only if the two are more alike
    than either is to the template; otherwise the template explains the similarity."""
    base = {i: closest(code, templates or {}) for i, code in items}
    pairs = []
    for (ida, a), (idb, b) in itertools.combinations(items, 2):
        scores = compare(a, b)
        value = max(scores["token"], scores["structure"])
        (ta, sa), (tb, sb) = base[ida], base[idb]
        if ta is not None and ta == tb and value <= max(sa, sb) + margin:
            continue
        pairs.append({"a": ida, "b": idb, **scores, "similarity": value})
    pairs.sort(key=lambda p: p["similarity"], reverse=True)
    return pairs[:top]
