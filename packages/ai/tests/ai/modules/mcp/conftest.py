# Copyright 2026 Aparavi Software AG. MIT License.
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / 'src'))

import pytest


class FakeEngineClient:
    def __init__(
        self,
        tasks=None,
        nodes=None,
        token='tok-1',
        result='RESULT',
        services=None,
        service_defs=None,
        validate_result=None,
        task_statuses=None,
        public_token='pub-1',
        base_url='http://localhost:5565',
    ):
        self._tasks = (
            tasks
            if tasks is not None
            else [
                {'name': 'my_pipeline', 'description': 'A running pipeline', 'token': 'live-tok'},
            ]
        )
        self._nodes = nodes if nodes is not None else [{'type': 'parse'}]
        self._token = token
        self._result = result
        self._public_token = public_token
        self.base_url = base_url
        self.sent = []
        self.used = []
        self.tooled = []
        self._tool_result = {}
        self.terminated = []
        self.sent_files = []
        self.saved_templates = []
        self._template_store = {}
        self.deploys_added = []
        self.list_tasks_calls = 0
        self.deploy_list_calls = 0

        # -- introspection (list_components / describe_component / validate) --
        self._services = (
            services
            if services is not None
            else {
                'services': {
                    'ocr': {
                        'title': 'OCR',
                        'protocol': 'ocr',
                        'classType': ['source'],
                        'description': 'Optical character recognition component',
                    },
                    'anthropic': {
                        'title': 'Anthropic LLM',
                        'protocol': 'anthropic',
                        'classType': ['agent', 'tool'],
                        'description': 'Anthropic-backed LLM component',
                    },
                },
                'version': 'x',
            }
        )
        self._service_defs = service_defs if service_defs is not None else dict(self._services.get('services', {}))
        self._validate_result = validate_result if validate_result is not None else {'errors': [], 'warnings': []}
        self.get_services_calls = 0
        self.get_service_calls = []
        self.validate_calls = []

        # -- visibility (monitor / get_task_status) --
        # A list of scripted responses, consumed one per call; the last
        # entry repeats once exhausted. Each entry is either a status dict
        # or an Exception instance/class to be raised.
        self._task_statuses = list(task_statuses) if task_statuses is not None else [{'state': 5, 'completed': True}]
        self.get_task_status_calls = []

    async def list_tasks(self):
        self.list_tasks_calls += 1
        return list(self._tasks)

    async def list_nodes(self):
        return list(self._nodes)

    async def send(self, token, data, objinfo=None, mimetype=None, on_sse=None):
        self.sent.append({'token': token, 'data': data, 'objinfo': objinfo, 'mimetype': mimetype})
        return self._result

    async def get_services(self):
        self.get_services_calls += 1
        return self._services

    async def get_service(self, name):
        self.get_service_calls.append(name)
        definition = self._service_defs.get(name)
        if definition is None:
            return None
        return {'name': name, **definition}

    async def validate(self, pipeline, source=None):
        self.validate_calls.append({'pipeline': pipeline, 'source': source})
        return dict(self._validate_result)

    async def use(self, **kwargs):
        self.used.append(kwargs)
        return {'token': self._token, 'publicToken': self._public_token, **kwargs}

    async def tool(self, token, tool, node_id='', input=None):
        self.tooled.append({'token': token, 'tool': tool, 'node_id': node_id, 'input': input or {}})
        return self._tool_result

    async def terminate(self, token):
        self.terminated.append(token)

    async def send_files(self, files, token):
        self.sent_files.append({'files': files, 'token': token})
        return {'uploaded': len(files)}

    async def fs_read_string(self, path):
        return 'file contents'

    async def fs_list_dir(self, path=''):
        return {'entries': []}

    async def save_template(self, template_id, pipeline):
        # Mirrors rocketride.mixins.store.save_template: writes the bare
        # pipeline dict to `.templates/<id>.json`, with no wrapping record.
        self.saved_templates.append({'template_id': template_id, 'pipeline': pipeline})
        self._template_store[template_id] = pipeline

    async def get_template(self, template_id):
        # Mirrors rocketride.mixins.store.get_template: reads back the bare
        # pipeline dict saved above -- a symmetric, unwrapped round-trip.
        return self._template_store.get(template_id)

    async def deploy_add(self, pipeline, schedule=None):
        self.deploys_added.append({'pipeline': pipeline, 'schedule': schedule})
        return {'project_id': 'dep-1'}

    async def deploy_list(self):
        self.deploy_list_calls += 1
        return [{'project_id': 'dep-1'}]

    async def get_task_status(self, token):
        self.get_task_status_calls.append(token)
        index = min(len(self.get_task_status_calls) - 1, len(self._task_statuses) - 1)
        response = self._task_statuses[index]
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, type) and issubclass(response, BaseException):
            raise response()
        return dict(response)


@pytest.fixture
def fake_engine():
    return FakeEngineClient()
