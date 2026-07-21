# Copyright 2026 Aparavi Software AG — MIT License
import json
from ai.modules.mcp.result_envelope import cap_rows


def test_small_result_untouched():
    rows = [{'id': i} for i in range(3)]
    out = cap_rows(rows)
    assert out['rows'] == rows
    assert out['row_count'] == 3
    assert out['truncated'] is False


def test_large_result_truncated_under_cap():
    rows = [{'id': i, 'blob': 'x' * 200} for i in range(1000)]
    out = cap_rows(rows, max_bytes=40_000)
    assert len(json.dumps(out, default=str).encode()) <= 40_000
    assert out['truncated'] is True
    assert out['row_count'] == 1000
    assert len(out['rows']) < 1000
    assert 'notice' in out


def test_custom_rows_key_and_extra():
    out = cap_rows([{'a': 1}], rows_key='matches', extra={'total': 1})
    assert out['matches'] == [{'a': 1}]
    assert out['total'] == 1


def test_empty_rows_not_truncated():
    out = cap_rows([])
    assert out == {'rows': [], 'row_count': 0, 'truncated': False}
    assert 'notice' not in out


def test_single_oversized_row_returns_empty_capped():
    rows = [{'blob': 'x' * 200}]
    out = cap_rows(rows, max_bytes=200)
    assert out['truncated'] is True
    assert out['row_count'] == 1
    assert out['rows'] == []
    assert len(json.dumps(out, default=str).encode()) <= 200


def test_extra_cannot_override_envelope_fields():
    out = cap_rows([], extra={'truncated': 'nope', 'row_count': 999})
    assert out['truncated'] is False
    assert out['row_count'] == 0
