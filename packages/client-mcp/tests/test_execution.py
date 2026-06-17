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
# Tests for rocketride_mcp.tools.execution (unit, mock client).

from unittest.mock import AsyncMock, MagicMock

from rocketride_mcp.registry import TaskRegistry
from rocketride_mcp.tooling import ToolRegistry
from rocketride_mcp.tools import execution


def _client(**methods) -> MagicMock:
    c = MagicMock()
    for name, val in methods.items():
        setattr(c, name, AsyncMock(return_value=val))
    return c


async def test_run_pipeline_starts_and_registers_token() -> None:
    tasks = TaskRegistry()
    client = _client(use={'token': 'tok-1'})
    out = await execution.run_pipeline(client, tasks, {'pipeline': {'components': []}})
    assert out['ok'] is True
    assert out['task_token'] == 'tok-1'
    assert 'result' not in out
    assert tasks.get('tok-1') is not None
    client.use.assert_awaited_once()


async def test_run_pipeline_with_inputs_sends_and_returns_result() -> None:
    tasks = TaskRegistry()
    client = _client(use={'token': 'tok-2'}, send={'text': ['done']})
    out = await execution.run_pipeline(client, tasks, {'filepath': '/p.pipe', 'inputs': 'hello'})
    assert out['ok'] is True
    assert out['task_token'] == 'tok-2'
    assert out['result'] == {'text': ['done']}
    client.send.assert_awaited_once_with('tok-2', 'hello', objinfo=None, mimetype=None)


async def test_run_pipeline_requires_pipeline_or_filepath() -> None:
    out = await execution.run_pipeline(_client(), TaskRegistry(), {})
    assert out['ok'] is False
    assert out['error_type'] == 'BadRequest'


async def test_send_data_sends_to_token() -> None:
    client = _client(send={'text': ['ok']})
    out = await execution.send_data(client, TaskRegistry(), {'task_token': 'tok', 'input': 'hi'})
    assert out['ok'] is True
    assert out['result'] == {'text': ['ok']}
    client.send.assert_awaited_once_with('tok', 'hi', objinfo=None, mimetype=None)


async def test_send_data_requires_token_and_input() -> None:
    out = await execution.send_data(_client(), TaskRegistry(), {'input': 'hi'})
    assert out['ok'] is False and out['error_type'] == 'BadRequest'
    out2 = await execution.send_data(_client(), TaskRegistry(), {'task_token': 't'})
    assert out2['ok'] is False and out2['error_type'] == 'BadRequest'


async def test_terminate_stops_and_drops_token() -> None:
    tasks = TaskRegistry()
    tasks.add('tok-x')
    client = _client(terminate=None)
    out = await execution.terminate(client, tasks, {'task_token': 'tok-x'})
    assert out['ok'] is True
    assert out['terminated'] == 'tok-x'
    assert tasks.get('tok-x') is None
    client.terminate.assert_awaited_once_with('tok-x')


async def test_terminate_requires_token() -> None:
    out = await execution.terminate(_client(), TaskRegistry(), {})
    assert out['ok'] is False and out['error_type'] == 'BadRequest'


def test_register_adds_execution_tools() -> None:
    reg = ToolRegistry()
    execution.register(reg)
    names = {s.name for s in reg.specs()}
    assert {'run_pipeline', 'send_data', 'terminate', 'send_files'} <= names


async def test_send_files_uploads_to_token() -> None:
    client = _client(send_files=[{'status': 'ok', 'file': 'a.pdf'}])
    out = await execution.send_files(client, TaskRegistry(), {'task_token': 'tok', 'files': ['a.pdf', 'b.pdf']})
    assert out['ok'] is True
    assert out['result'] == [{'status': 'ok', 'file': 'a.pdf'}]
    # NOTE the SDK arg order: files first, token second
    client.send_files.assert_awaited_once_with(['a.pdf', 'b.pdf'], 'tok')


async def test_send_files_requires_token_and_files() -> None:
    out = await execution.send_files(_client(), TaskRegistry(), {'files': ['a']})
    assert out['ok'] is False and out['error_type'] == 'BadRequest'
    out2 = await execution.send_files(_client(), TaskRegistry(), {'task_token': 't', 'files': []})
    assert out2['ok'] is False and out2['error_type'] == 'BadRequest'


def test_register_includes_send_files() -> None:
    reg = ToolRegistry()
    execution.register(reg)
    assert 'send_files' in {s.name for s in reg.specs()}


async def test_run_pipeline_no_token_returns_error() -> None:
    out = await execution.run_pipeline(_client(use={}), TaskRegistry(), {'pipeline': {'components': []}})
    assert out['ok'] is False
    assert out['error_type'] == 'BadRequest'


async def test_run_pipeline_send_failure_preserves_token() -> None:
    tasks = TaskRegistry()
    client = _client(use={'token': 'tok-3'})
    client.send = AsyncMock(side_effect=RuntimeError('boom'))
    out = await execution.run_pipeline(client, tasks, {'pipeline': {'components': []}, 'inputs': 'x'})
    assert out['ok'] is False
    assert out['task_token'] == 'tok-3'


async def test_send_files_rejects_invalid_entries() -> None:
    out = await execution.send_files(_client(), TaskRegistry(), {'task_token': 't', 'files': [None]})
    assert out['ok'] is False and out['error_type'] == 'BadRequest'
