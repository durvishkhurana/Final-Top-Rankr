"""Tables offered for download as CSV (for spreadsheets, R, pandas) or JSON."""

import csv
import io
import json
from collections.abc import Sequence
from typing import Any, Literal

from fastapi import Response

Format = Literal["csv", "json"]


def table(columns: Sequence[str], rows: list[dict[str, Any]], name: str, fmt: Format
          ) -> Response:
    """rows are flat dicts holding at least the columns, with JSON-ready values."""
    disposition = {"Content-Disposition": f'attachment; filename="{name}.{fmt}"'}
    if fmt == "json":
        return Response(json.dumps([{c: r[c] for c in columns} for r in rows]),
                        media_type="application/json", headers=disposition)
    out = io.StringIO()
    writer = csv.DictWriter(out, columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return Response(out.getvalue(), media_type="text/csv", headers=disposition)
