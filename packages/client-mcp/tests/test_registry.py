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


# --- Flow buffer ------------------------------------------------------------


def test_add_stores_flow_id() -> None:
    reg = TaskRegistry()
    info = reg.add('tok-1', flow_id='abc123')
    assert info.flow_id == 'abc123'


def test_record_flow_routes_by_flow_id_and_flow_since_returns_it() -> None:
    reg = TaskRegistry()
    reg.add('tok-1', flow_id='id-1')
    ok = reg.record_flow('id-1', {'op': 'enter', 'pipes': ['twelvelabs_1'], 'trace': {}})
    assert ok is True
    res = reg.flow_since('tok-1', 0)
    assert len(res['events']) == 1
    assert res['events'][0]['op'] == 'enter'
    assert res['events'][0]['seq'] == res['cursor']


def test_flow_since_cursor_pages_only_newer_events() -> None:
    reg = TaskRegistry()
    reg.add('tok-1', flow_id='id-1')
    reg.record_flow('id-1', {'op': 'enter'})
    first = reg.flow_since('tok-1', 0)
    cursor = first['cursor']
    reg.record_flow('id-1', {'op': 'leave'})
    second = reg.flow_since('tok-1', cursor)
    assert len(second['events']) == 1
    assert second['events'][0]['op'] == 'leave'


def test_record_flow_unknown_id_is_dropped() -> None:
    reg = TaskRegistry()
    reg.add('tok-1', flow_id='id-1')
    assert reg.record_flow('id-unknown', {'op': 'enter'}) is False


def test_flow_since_unknown_token_returns_empty() -> None:
    reg = TaskRegistry()
    res = reg.flow_since('nope', 0)
    assert res['events'] == []
    assert res['cursor'] == 0


def test_flow_buffer_is_bounded() -> None:
    reg = TaskRegistry(flow_max=3)
    reg.add('tok-1', flow_id='id-1')
    for i in range(5):
        reg.record_flow('id-1', {'op': f'e{i}'})
    res = reg.flow_since('tok-1', 0)
    assert len(res['events']) == 3  # oldest two dropped
    assert [e['op'] for e in res['events']] == ['e2', 'e3', 'e4']


def test_record_flow_routes_adopted_token_by_id_prefix() -> None:
    # Adopted task has no flow_id; control.id == <bare-token-hex>[:8] + '.' + source.
    # The token carries a 'tk_' display prefix the engine strips — so the event
    # id is '228fc01a.dropper_1', NOT 'tk_228fc...'.
    reg = TaskRegistry()
    reg.add('tk_228fc01a697a1601834414b4c87e27fa')  # no flow_id
    ok = reg.record_flow('228fc01a.dropper_1', {'op': 'enter'})
    assert ok is True
    res = reg.flow_since('tk_228fc01a697a1601834414b4c87e27fa', 0)
    assert len(res['events']) == 1


def test_record_flow_prefix_match_lazily_binds_flow_id() -> None:
    reg = TaskRegistry()
    reg.add('tk_228fc01a697a1601834414b4c87e27fa')
    reg.record_flow('228fc01a.dropper_1', {'op': 'enter'})
    # After first prefix match the exact control.id is cached for fast routing.
    assert reg.get('tk_228fc01a697a1601834414b4c87e27fa').flow_id == '228fc01a.dropper_1'


def test_record_flow_prefix_no_match_is_dropped() -> None:
    reg = TaskRegistry()
    reg.add('tk_999999aa0000')
    assert reg.record_flow('228fc01a.dropper_1', {'op': 'enter'}) is False


def test_record_flow_prefix_works_for_unprefixed_token() -> None:
    # A token with no 'xx_' display prefix routes by its own first 8 chars.
    reg = TaskRegistry()
    reg.add('228fc01a697a1601834414b4c87e27fa')
    assert reg.record_flow('228fc01a.dropper_1', {'op': 'enter'}) is True
