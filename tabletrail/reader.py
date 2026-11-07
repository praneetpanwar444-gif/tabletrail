"""CSV input is streamed; malformed records never get silently truncated."""

from contextlib import contextmanager
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .errors import TableTrailError


@dataclass(frozen=True)
class Row:
    record: int
    line: int
    cells: list[str]


@contextmanager
def read_table(path: str | Path, delimiter: str = ",", encoding: str = "utf-8-sig"):
    if len(delimiter) != 1 or delimiter in ('"', "\r", "\n", "\x00"):
        raise TableTrailError("Delimiter must be one character other than quote/newline/NUL")
    try:
        with Path(path).open(encoding=encoding, newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter, strict=True)
            headers = next(reader, None)
            if not headers or any(not h.strip() for h in headers):
                raise TableTrailError("CSV needs a header with non-empty column names")
            if len(set(headers)) != len(headers):
                raise TableTrailError("Duplicate column names are ambiguous; rename them first")

            def rows() -> Iterator[Row]:
                for record, cells in enumerate(reader, start=2):
                    if not cells:  # Entirely blank physical records are ignored.
                        continue
                    if len(cells) != len(headers):
                        raise TableTrailError(
                            f"Record {record} (ending line {reader.line_num}) has {len(cells)} "
                            f"fields; expected {len(headers)}")
                    yield Row(record, reader.line_num, cells)

            yield headers, rows()
    except (OSError, UnicodeError, LookupError, csv.Error) as exc:
        raise TableTrailError(f"Cannot read CSV: {exc}") from exc
