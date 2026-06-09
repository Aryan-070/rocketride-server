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
# Tests for rocketride_mcp.errors.

import pytest

from rocketride_mcp.errors import HardError, normalize_error


# Name-matched hard failures become HardError (→ MCP tool error)
def test_connection_class_raises_hard_error() -> None:
    exc = ConnectionError('socket closed')
    with pytest.raises(HardError) as ei:
        normalize_error(exc)
    assert ei.value.error_type == 'ConnectionError'
    assert 'socket closed' in ei.value.message


def test_timeout_raises_hard_error() -> None:
    import asyncio

    with pytest.raises(HardError) as ei:
        normalize_error(asyncio.TimeoutError())
    assert ei.value.error_type == 'TimeoutError'


# Actionable failures become a structured dict the agent can act on
def test_actionable_failure_returns_structured() -> None:
    out = normalize_error(ValueError('missing env key OPENAI_API_KEY'), hint='call set_env')
    assert out['ok'] is False
    assert out['error_type'] == 'ValueError'
    assert 'OPENAI_API_KEY' in out['message']
    assert out['hint'] == 'call set_env'


# A client exception carrying a DAP failure body uses its message
def test_dap_failure_message_extracted() -> None:
    exc = RuntimeError('generic')
    exc.dap_result = {'success': False, 'message': 'lane wiring invalid'}
    out = normalize_error(exc)
    assert out['ok'] is False
    assert out['message'] == 'lane wiring invalid'
