# Copyright 2026 Aparavi Software AG. MIT License.
import asyncio

import pytest


def test_make_engine_client_requires_uri(monkeypatch):
    from ai.modules.mcp.engine import make_engine_client

    monkeypatch.delenv('ROCKETRIDE_URI', raising=False)
    monkeypatch.setenv('ROCKETRIDE_APIKEY', 'k')
    with pytest.raises(ValueError):
        make_engine_client({})


def test_make_engine_client_requires_auth(monkeypatch):
    from ai.modules.mcp.engine import make_engine_client

    monkeypatch.setenv('ROCKETRIDE_URI', 'ws://localhost:5565')
    monkeypatch.delenv('ROCKETRIDE_AUTH', raising=False)
    monkeypatch.delenv('ROCKETRIDE_APIKEY', raising=False)
    with pytest.raises(ValueError):
        make_engine_client({})


class _FakeAccountApi:
    """Stand-in for RocketRideClient.account (cached_property sub-API)."""

    def __init__(self) -> None:
        self.get_environment_keys_calls = 0

    async def get_environment_keys(self) -> list:
        self.get_environment_keys_calls += 1
        return ['ROCKETRIDE_FOO']

    async def set_env(self, scope, env, scope_id=None):  # pragma: no cover - must NOT be called
        raise AssertionError('seam.set_env must call client.set_env, not client.account.set_env')


class _FakeDeployApi:
    """Stand-in for RocketRideClient.deploy (cached_property sub-API)."""

    def __init__(self) -> None:
        self.add_calls = []
        self.list_calls = 0

    async def add(self, pipeline, *, schedule=None) -> dict:
        self.add_calls.append({'pipeline': pipeline, 'schedule': schedule})
        return {'project_id': 'dep-1'}

    async def list(self) -> list:
        self.list_calls += 1
        return [{'project_id': 'dep-1'}]


class _FakeUnderlyingClient:
    """Stand-in for RocketRideClient that records lifecycle calls without any I/O."""

    def __init__(self) -> None:
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.request_calls = 0
        self.get_services_calls = 0
        self.get_service_calls = []
        self.validate_calls = []
        self.use_calls = []
        self.send_calls = []
        self.terminate_calls = []
        self.send_files_calls = []
        self.set_env_calls = []
        self.fs_read_string_calls = []
        self.fs_list_dir_calls = []
        self.save_template_calls = []
        self.get_template_calls = []
        self.get_task_status_calls = []
        self.account = _FakeAccountApi()
        self.deploy = _FakeDeployApi()

    async def connect(self) -> None:
        self.connect_calls += 1

    async def disconnect(self) -> None:
        self.disconnect_calls += 1

    def build_request(self, command: str) -> dict:
        return {'command': command}

    async def request(self, req: dict) -> dict:
        self.request_calls += 1
        return {'body': {'tasks': []}}

    async def use(self, **kwargs) -> dict:
        self.use_calls.append(kwargs)
        return {'token': 'tok', **kwargs}

    async def send(
        self,
        token: str,
        data: bytes,
        objinfo: dict = None,
        mimetype: str = None,
        on_sse=None,
    ) -> dict:
        self.send_calls.append(
            {'token': token, 'data': data, 'objinfo': objinfo, 'mimetype': mimetype, 'on_sse': on_sse}
        )
        return {'ok': True}

    async def get_services(self) -> dict:
        self.get_services_calls += 1
        return {'services': {'ocr': {}}, 'version': 'x'}

    async def get_service(self, service: str) -> dict:
        self.get_service_calls.append(service)
        return {'name': service}

    async def validate(self, pipeline, *, source=None) -> dict:
        self.validate_calls.append({'pipeline': pipeline, 'source': source})
        return {'valid': True}

    async def terminate(self, token: str) -> None:
        self.terminate_calls.append(token)

    async def send_files(self, files, token: str) -> dict:
        self.send_files_calls.append({'files': files, 'token': token})
        return {'uploaded': len(files)}

    def set_env(self, env: dict) -> None:
        self.set_env_calls.append(env)

    async def fs_read_string(self, path: str) -> str:
        self.fs_read_string_calls.append(path)
        return 'contents'

    async def fs_list_dir(self, path: str = '') -> dict:
        self.fs_list_dir_calls.append(path)
        return {'entries': []}

    async def save_template(self, template_id: str, pipeline: dict) -> None:
        self.save_template_calls.append({'template_id': template_id, 'pipeline': pipeline})

    async def get_template(self, template_id: str) -> dict:
        self.get_template_calls.append(template_id)
        return {'template_id': template_id}

    async def get_task_status(self, token: str) -> dict:
        self.get_task_status_calls.append(token)
        return {'state': 5, 'completed': True}


def _make_client_with_fake(monkeypatch):
    """Build a real WsEngineClient (no network) and swap in the fake underlying client."""
    from ai.modules.mcp.engine import WsEngineClient

    client = WsEngineClient(uri='ws://localhost:5565', auth='test-auth')
    fake = _FakeUnderlyingClient()
    client._client = fake
    return client, fake


async def test_ensure_connected_memoizes_across_sequential_calls(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    await client.list_tasks()
    await client.list_tasks()

    assert fake.connect_calls == 1
    assert fake.request_calls == 2
    assert client._connected is True


async def test_ensure_connected_memoizes_under_concurrent_calls(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    await asyncio.gather(client.list_tasks(), client.list_tasks())

    assert fake.connect_calls == 1
    assert client._connected is True


async def test_close_disconnects_when_connected(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    await client.list_tasks()
    assert client._connected is True

    await client.close()

    assert fake.disconnect_calls == 1
    assert client._connected is False


async def test_close_is_noop_when_never_connected(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    await client.close()

    assert fake.disconnect_calls == 0
    assert client._connected is False


async def test_close_is_idempotent_when_called_twice(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    await client.list_tasks()
    await client.close()
    await client.close()

    assert fake.disconnect_calls == 1
    assert client._connected is False


async def test_get_services_calls_sdk(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    result = await client.get_services()

    assert fake.get_services_calls == 1
    assert result == {'services': {'ocr': {}}, 'version': 'x'}


async def test_get_service_calls_sdk_with_name(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    result = await client.get_service('ocr')

    assert fake.get_service_calls == ['ocr']
    assert result == {'name': 'ocr'}


async def test_validate_calls_sdk_with_pipeline_and_source(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)
    pipeline = {'components': []}

    result = await client.validate(pipeline, source='file.pipe')

    assert fake.validate_calls == [{'pipeline': pipeline, 'source': 'file.pipe'}]
    assert result == {'valid': True}


async def test_validate_defaults_source_to_none(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    await client.validate({'components': []})

    assert fake.validate_calls == [{'pipeline': {'components': []}, 'source': None}]


async def test_use_passes_full_kwargs_and_returns_dict(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    result = await client.use(filepath='p.pipe', ttl=30, env={'X': '1'}, name='n')

    assert fake.use_calls == [{'filepath': 'p.pipe', 'ttl': 30, 'env': {'X': '1'}, 'name': 'n'}]
    assert result == {'token': 'tok', 'filepath': 'p.pipe', 'ttl': 30, 'env': {'X': '1'}, 'name': 'n'}


async def test_send_forwards_objinfo_mimetype(monkeypatch):
    """The seam's `send` must forward `objinfo`/`mimetype`/`on_sse` through to
    the underlying SDK client unchanged, not just `token`/`data`.
    """
    client, fake = _make_client_with_fake(monkeypatch)

    def _on_sse(_event):  # pragma: no cover - identity/passthrough check only
        pass

    result = await client.send('tok-1', 'payload', objinfo={'name': 'a.txt'}, mimetype='text/plain', on_sse=_on_sse)

    assert fake.send_calls == [
        {'token': 'tok-1', 'data': 'payload', 'objinfo': {'name': 'a.txt'}, 'mimetype': 'text/plain', 'on_sse': _on_sse}
    ]
    assert result == {'ok': True}


async def test_terminate_calls_sdk_with_token(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    result = await client.terminate('tok-1')

    assert fake.terminate_calls == ['tok-1']
    assert result is None


async def test_send_files_passes_files_then_token(monkeypatch):
    """Footgun: SDK arg order is (files, token) — token second, not first."""
    client, fake = _make_client_with_fake(monkeypatch)
    files = ['/tmp/a.pdf', ('/tmp/b.pdf', {'name': 'b'})]

    result = await client.send_files(files, 'tok-2')

    assert fake.send_files_calls == [{'files': files, 'token': 'tok-2'}]
    assert result == {'uploaded': 2}


async def test_set_env_calls_local_connection_setter_not_account(monkeypatch):
    """Footgun: must call client.set_env (local), never client.account.set_env (server write)."""
    client, fake = _make_client_with_fake(monkeypatch)

    result = await client.set_env({'ROCKETRIDE_FOO': 'bar'})

    assert fake.set_env_calls == [{'ROCKETRIDE_FOO': 'bar'}]
    assert fake.account.get_environment_keys_calls == 0
    assert result is None


async def test_get_environment_keys_calls_account_sub_api(monkeypatch):
    """Footgun: must call client.account.get_environment_keys(), not a top-level method."""
    client, fake = _make_client_with_fake(monkeypatch)

    result = await client.get_environment_keys()

    assert fake.account.get_environment_keys_calls == 1
    assert result == ['ROCKETRIDE_FOO']


async def test_fs_read_string_calls_sdk_with_path(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    result = await client.fs_read_string('/store/a.txt')

    assert fake.fs_read_string_calls == ['/store/a.txt']
    assert result == 'contents'


async def test_fs_list_dir_calls_sdk_not_fs_dir(monkeypatch):
    """Footgun: real SDK method name is fs_list_dir, not fs_dir."""
    client, fake = _make_client_with_fake(monkeypatch)

    result = await client.fs_list_dir('/store')

    assert fake.fs_list_dir_calls == ['/store']
    assert result == {'entries': []}


async def test_fs_list_dir_defaults_path_to_empty_string(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    await client.fs_list_dir()

    assert fake.fs_list_dir_calls == ['']


async def test_save_template_calls_sdk_with_id_and_pipeline(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)
    pipeline = {'components': []}

    result = await client.save_template('tpl-1', pipeline)

    assert fake.save_template_calls == [{'template_id': 'tpl-1', 'pipeline': pipeline}]
    assert result is None


async def test_get_template_calls_sdk_with_id(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    result = await client.get_template('tpl-1')

    assert fake.get_template_calls == ['tpl-1']
    assert result == {'template_id': 'tpl-1'}


async def test_deploy_add_passes_schedule_as_keyword(monkeypatch):
    """Footgun: client.deploy.add(pipeline, schedule=schedule) — schedule is keyword-only."""
    client, fake = _make_client_with_fake(monkeypatch)
    pipeline = {'components': []}

    result = await client.deploy_add(pipeline, schedule='0/15 * * * *')

    assert fake.deploy.add_calls == [{'pipeline': pipeline, 'schedule': '0/15 * * * *'}]
    assert result == {'project_id': 'dep-1'}


async def test_deploy_add_defaults_schedule_to_none(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    await client.deploy_add({'components': []})

    assert fake.deploy.add_calls == [{'pipeline': {'components': []}, 'schedule': None}]


async def test_deploy_list_calls_sdk(monkeypatch):
    """Footgun: seam calls client.deploy.list() (sub-API), not a top-level method."""
    client, fake = _make_client_with_fake(monkeypatch)

    result = await client.deploy_list()

    assert fake.deploy.list_calls == 1
    assert result == [{'project_id': 'dep-1'}]


async def test_get_task_status_calls_sdk_with_token(monkeypatch):
    client, fake = _make_client_with_fake(monkeypatch)

    result = await client.get_task_status('tok-3')

    assert fake.get_task_status_calls == ['tok-3']
    assert result == {'state': 5, 'completed': True}
