# Copyright 2026 Aparavi Software AG — MIT License
"""Cap MCP query results to a byte budget the model can ingest in-band."""

import json

MAX_BYTES = 40_000
_NOTICE = (
    'result exceeded the 40 KB in-band cap - add LIMIT/filters, or route large exports through the filesystem sink'
)


def _size(obj) -> int:
    return len(json.dumps(obj, default=str).encode())


def cap_rows(rows, extra=None, max_bytes=MAX_BYTES, rows_key='rows'):
    total = len(rows)
    kept = list(rows)
    truncated = False
    if not kept:
        out = dict(extra or {})
        out[rows_key] = kept
        out['row_count'] = total
        out['truncated'] = truncated
        return out
    while kept:
        out = dict(extra or {})
        out[rows_key] = kept
        out['row_count'] = total
        out['truncated'] = truncated
        if truncated:
            out['notice'] = _NOTICE
        if _size(out) <= max_bytes:
            return out
        truncated = True
        drop = max(1, len(kept) // 10)
        kept = kept[:-drop]
    out = dict(extra or {})
    out[rows_key] = []
    out['row_count'] = total
    out['truncated'] = True
    out['notice'] = _NOTICE
    return out
