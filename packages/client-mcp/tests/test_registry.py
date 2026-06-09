# =============================================================================
# MIT License
# Copyright (c) 2026 Aparavi Software AG
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# =============================================================================
# Tests for rocketride_mcp.registry.

from rocketride_mcp.registry import TaskRegistry


def test_add_and_get() -> None:
    reg = TaskRegistry()
    info = reg.add('tok-1', pipeline_ref='/x/y.pipe', label='ingest')
    assert info.token == 'tok-1'
    assert info.pipeline_ref == '/x/y.pipe'
    assert info.meta['label'] == 'ingest'
    assert reg.get('tok-1') is info


def test_get_unknown_returns_none() -> None:
    assert TaskRegistry().get('nope') is None


def test_remove_and_tokens() -> None:
    reg = TaskRegistry()
    reg.add('a')
    reg.add('b')
    assert set(reg.tokens()) == {'a', 'b'}
    reg.remove('a')
    assert reg.tokens() == ['b']
    reg.remove('missing')  # no error


def test_clear() -> None:
    reg = TaskRegistry()
    reg.add('a')
    reg.clear()
    assert reg.tokens() == []
