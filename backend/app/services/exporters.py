from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from openpyxl import Workbook


def to_csv_bytes(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_to_cell(value) for value in row])
    return buffer.getvalue().encode("utf-8-sig")


def to_xlsx_bytes(
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    sheet_name: str = "report",
) -> bytes:
    wb = Workbook(write_only=False)
    try:
        ws = wb.active
        ws.title = sheet_name[:31]
        ws.append(list(headers))
        for row in rows:
            ws.append([_to_cell(value) for value in row])
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
    finally:
        wb.close()


def _to_cell(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value
