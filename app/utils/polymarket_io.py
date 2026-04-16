"""CSV read path with mtime cache for polymarket-alerts data files."""
import csv
import os
from typing import Optional

# mtime cache: filepath -> (mtime, fieldnames, rows). Invalidates when file changes.
_CSV_CACHE: dict[str, tuple[float, list[str], list[dict]]] = {}


def _read_csv_cached(
    filepath: str,
    required_columns: Optional[tuple[str, ...]] = None,
) -> Optional[tuple[list[str], list[dict]]]:
    """
    Read CSV with mtime caching. Returns (fieldnames, rows) or None.
    Cache invalidates automatically when file mtime changes.
    If required_columns is set and the default comma read is missing any of them,
    tries csv.Sniffer to detect delimiter (e.g. semicolon) and re-reads.
    """
    if not filepath or not os.path.isfile(filepath):
        return None
    try:
        mtime = os.path.getmtime(filepath)
    except OSError:
        return None
    if filepath in _CSV_CACHE:
        cached_mtime, cached_fieldnames, cached_rows = _CSV_CACHE[filepath]
        if cached_mtime == mtime:
            return (cached_fieldnames, cached_rows)
    try:
        with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        # If caller expects certain columns and we don't have them, try sniffing delimiter
        if required_columns and fieldnames:
            headers_lower = [h.strip().lower() for h in fieldnames if h]
            missing = [c for c in required_columns if c.lower() not in headers_lower]
            if missing:
                try:
                    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f2:
                        sample = f2.read(4096)
                    if sample and "\n" in sample:
                        try:
                            sniffer = csv.Sniffer()
                            dialect = sniffer.sniff(sample, delimiters=",;\t")
                            with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f3:
                                reader2 = csv.DictReader(f3, dialect=dialect)
                                fn2 = list(reader2.fieldnames or [])
                                rows2 = list(reader2)
                            fn2_lower = [h.strip().lower() for h in fn2 if h]
                            if all(c.lower() in fn2_lower for c in required_columns):
                                fieldnames, rows = fn2, rows2
                        except (csv.Error, Exception):
                            pass
                except (IOError, OSError):
                    pass
        _CSV_CACHE[filepath] = (mtime, fieldnames, rows)
        return (fieldnames, rows)
    except (IOError, csv.Error):
        return None
