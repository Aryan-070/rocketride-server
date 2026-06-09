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
# Tests for rocketride_mcp.tooling.

from rocketride_mcp.tooling import ToolRegistry


def test_register_and_enumerate() -> None:
    reg = ToolRegistry()

    @reg.register('echo', 'Echo back', {'type': 'object', 'properties': {}})
    async def _echo(client, tasks, args):  # noqa: ANN001
        return {'ok': True, 'value': args.get('v')}

    specs = reg.specs()
    assert len(specs) == 1
    assert specs[0].name == 'echo'
    assert specs[0].description == 'Echo back'
    assert specs[0].input_schema['type'] == 'object'


def test_get_returns_spec_or_none() -> None:
    reg = ToolRegistry()

    @reg.register('a', 'A', {'type': 'object'})
    async def _a(client, tasks, args):  # noqa: ANN001
        return {'ok': True}

    assert reg.get('a').name == 'a'
    assert reg.get('missing') is None


async def test_handler_is_callable() -> None:
    reg = ToolRegistry()

    @reg.register('echo', 'Echo', {'type': 'object'})
    async def _echo(client, tasks, args):  # noqa: ANN001
        return {'ok': True, 'value': args['v']}

    out = await reg.get('echo').handler(None, None, {'v': 42})
    assert out == {'ok': True, 'value': 42}
