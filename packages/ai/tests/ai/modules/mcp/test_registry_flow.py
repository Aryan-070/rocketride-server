# Copyright 2026 Aparavi Software AG. MIT License.
"""Tests for TaskRegistry flow-event machinery (registry.py).

Covers the per-token FLOW-event ring buffers used to buffer pushed
``apaevt_flow`` engine events and drain them via a later ``get_pipeline_trace``
tool. The buffers live in side-structures keyed by token, independent of the
``_tasks`` metadata dict, because execution tools remove one-shot tokens from
the registry while their traces must remain drainable.
"""

from ai.modules.mcp.registry import TaskRegistry, _token_core


# --- _token_core -------------------------------------------------------------


def test_token_core_strips_tk_prefix():
    assert _token_core('tk_abcdef1234567890') == 'abcdef1234567890'


def test_token_core_strips_pk_prefix():
    assert _token_core('pk_abcdef1234567890') == 'abcdef1234567890'


def test_token_core_leaves_unprefixed_token_alone():
    assert _token_core('abcdef1234567890') == 'abcdef1234567890'


def test_token_core_leaves_short_token_alone():
    assert _token_core('ab') == 'ab'


# --- ensure_flow / set_flow_id / subscription flags --------------------------


def test_ensure_flow_is_idempotent_and_does_not_reset_buffer():
    reg = TaskRegistry()
    reg.ensure_flow('tk_aaaaaaaa1111')
    reg.set_flow_id('tk_aaaaaaaa1111', 'aaaaaaaa.src')
    reg.record_flow('aaaaaaaa.src', {'x': 1})

    reg.ensure_flow('tk_aaaaaaaa1111')  # second call must not reset the buffer

    assert reg.flow_since('tk_aaaaaaaa1111')['events'] == [{'seq': 1, 'x': 1}]


def test_mark_flow_subscribed_and_is_flow_subscribed():
    reg = TaskRegistry()
    reg.ensure_flow('tok-1')

    assert reg.is_flow_subscribed('tok-1') is False

    reg.mark_flow_subscribed('tok-1')

    assert reg.is_flow_subscribed('tok-1') is True


def test_is_flow_subscribed_false_for_unknown_token():
    reg = TaskRegistry()

    assert reg.is_flow_subscribed('nope') is False


# --- record_flow routing ------------------------------------------------------


def test_record_flow_exact_match_routes_to_correct_token():
    reg = TaskRegistry()
    reg.set_flow_id('tok-1', 'flow-123')
    reg.set_flow_id('tok-2', 'flow-456')

    ok = reg.record_flow('flow-123', {'step': 'a'})

    assert ok is True
    assert reg.flow_since('tok-1')['events'] == [{'seq': 1, 'step': 'a'}]
    assert reg.flow_since('tok-2')['events'] == []


def test_record_flow_prefix_match_routes_and_caches_id():
    reg = TaskRegistry()
    reg.ensure_flow('tk_abcdef1234567890')  # no flow_id known yet

    ok = reg.record_flow('abcdef12.some-source', {'step': 'a'})

    assert ok is True
    assert reg.flow_since('tk_abcdef1234567890')['events'] == [{'seq': 1, 'step': 'a'}]

    # second event with the *exact* id now hits the exact-match tier because
    # the id was cached on first prefix match
    ok2 = reg.record_flow('abcdef12.some-source', {'step': 'b'})

    assert ok2 is True
    events = reg.flow_since('tk_abcdef1234567890')['events']
    assert [e['step'] for e in events] == ['a', 'b']


def test_record_flow_returns_false_for_unknown_flow_id():
    reg = TaskRegistry()
    reg.set_flow_id('tok-1', 'flow-123')

    ok = reg.record_flow('flow-nope', {'step': 'a'})

    assert ok is False


def test_record_flow_seq_is_monotonic_across_tokens():
    reg = TaskRegistry()
    reg.set_flow_id('tok-1', 'flow-1')
    reg.set_flow_id('tok-2', 'flow-2')

    reg.record_flow('flow-1', {'n': 1})
    reg.record_flow('flow-2', {'n': 2})
    reg.record_flow('flow-1', {'n': 3})

    seqs_1 = [e['seq'] for e in reg.flow_since('tok-1')['events']]
    seqs_2 = [e['seq'] for e in reg.flow_since('tok-2')['events']]

    assert seqs_1 == [1, 3]
    assert seqs_2 == [2]


# --- flow_since paging ---------------------------------------------------------


def test_flow_since_pages_by_cursor():
    reg = TaskRegistry()
    reg.set_flow_id('tok-1', 'flow-1')
    reg.record_flow('flow-1', {'n': 1})
    reg.record_flow('flow-1', {'n': 2})

    first = reg.flow_since('tok-1')
    assert [e['n'] for e in first['events']] == [1, 2]
    assert first['cursor'] == 2

    reg.record_flow('flow-1', {'n': 3})

    second = reg.flow_since('tok-1', since=first['cursor'])
    assert [e['n'] for e in second['events']] == [3]
    assert second['cursor'] == 3


def test_flow_since_unknown_token_returns_empty_with_since_as_cursor():
    reg = TaskRegistry()

    result = reg.flow_since('nope', since=7)

    assert result == {'events': [], 'cursor': 7}


def test_flow_since_empty_buffer_returns_since_as_cursor():
    reg = TaskRegistry()
    reg.ensure_flow('tok-1')

    result = reg.flow_since('tok-1', since=3)

    assert result == {'events': [], 'cursor': 3}


# --- side-map lifecycle: independent of _tasks --------------------------------


def test_flow_buffer_survives_task_removal():
    reg = TaskRegistry()
    reg.add('tok-1', pipeline_ref='/tmp/a.pipe')
    reg.set_flow_id('tok-1', 'flow-1')
    reg.record_flow('flow-1', {'n': 1})

    reg.remove('tok-1')

    assert reg.get('tok-1') is None
    assert reg.flow_since('tok-1')['events'] == [{'seq': 1, 'n': 1}]


# --- bounded side-map: FIFO eviction + ring cap --------------------------------


def test_33rd_tracked_token_evicts_the_first():
    reg = TaskRegistry()
    for i in range(32):
        reg.ensure_flow(f'tok-{i}')

    reg.ensure_flow('tok-32')  # 33rd distinct token

    assert reg.flow_since('tok-0') == {'events': [], 'cursor': 0}  # evicted -> unknown
    # a still-tracked token behaves normally
    reg.set_flow_id('tok-31', 'flow-31')
    reg.record_flow('flow-31', {'n': 1})
    assert reg.flow_since('tok-31')['events'] == [{'seq': 1, 'n': 1}]


def test_ring_buffer_caps_at_500_entries():
    reg = TaskRegistry()
    reg.set_flow_id('tok-1', 'flow-1')

    for i in range(510):
        reg.record_flow('flow-1', {'n': i})

    events = reg.flow_since('tok-1')['events']

    assert len(events) == 500
    assert events[0]['n'] == 10  # oldest 10 evicted
    assert events[-1]['n'] == 509
