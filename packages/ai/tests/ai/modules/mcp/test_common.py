# Copyright 2026 Aparavi Software AG. MIT License.
"""Tests for `tools/_common.py` `load_pipeline` (moved here from Task 1's
deferred/blocked test bodies once `tools.py` -> `tools/` package migration
unblocked it — see task-1-report.md and task-3-brief.md).
"""

import json

import pytest


def test_load_pipeline_inline_dict():
    from ai.modules.mcp.tools._common import load_pipeline

    pipeline = {'source': 'a', 'components': []}

    assert load_pipeline({'pipeline': pipeline}) == pipeline


def test_load_pipeline_unwraps_nested_wrapper():
    from ai.modules.mcp.tools._common import load_pipeline

    inner = {'source': 'a', 'components': []}

    assert load_pipeline({'pipeline': {'pipeline': inner}}) == inner


def test_load_pipeline_reads_dot_pipe_file(tmp_path):
    from ai.modules.mcp.tools._common import load_pipeline

    pipeline = {'source': 'a', 'components': []}
    f = tmp_path / 'x.pipe'
    f.write_text(json.dumps(pipeline), encoding='utf-8')

    assert load_pipeline({'filepath': str(f)}) == pipeline


def test_load_pipeline_reads_and_unwraps_dot_pipe_file(tmp_path):
    from ai.modules.mcp.tools._common import load_pipeline

    inner = {'source': 'a', 'components': []}
    f = tmp_path / 'x.pipe'
    f.write_text(json.dumps({'pipeline': inner}), encoding='utf-8')

    assert load_pipeline({'filepath': str(f)}) == inner


def test_load_pipeline_raises_when_neither_supplied():
    from ai.modules.mcp.tools._common import load_pipeline

    with pytest.raises(ValueError):
        load_pipeline({})


def test_load_pipeline_raises_when_not_an_object():
    from ai.modules.mcp.tools._common import load_pipeline

    with pytest.raises(ValueError):
        load_pipeline({'pipeline': ['not', 'an', 'object']})
