# =============================================================================
# RocketRide Engine
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

"""
Tool grouping for the Pipedrive node.

Full v1 coverage is ~230 tools, which is far more than an LLM can choose between
reliably. Every tool is therefore tagged with a resource group, and the node only
publishes the groups named in the ``pipedrive.toolGroups`` config field. The
filtering happens in ``IInstance._collect_tool_methods()``, so a group that is not
published is invisible to ``tool.query`` and rejected by ``tool.invoke`` alike.
"""

from __future__ import annotations

from typing import Callable

from rocketlib import tool_function

#: Every group this node implements.
ALL_GROUPS = frozenset(
    {
        'activities',
        'call_logs',
        'deals',
        'fields',
        'files',
        'filters',
        'goals',
        'leads',
        'mailbox',
        'misc',
        'notes',
        'org_relationships',
        'organizations',
        'permission_sets',
        'persons',
        'pipelines',
        'products',
        'projects',
        'roles',
        'search',
        'stages',
        'subscriptions',
        'teams',
        'users',
        'webhooks',
    }
)

#: Published when the operator has not chosen otherwise — the everyday CRM surface.
DEFAULT_GROUPS = frozenset(
    {'deals', 'persons', 'organizations', 'activities', 'pipelines', 'stages', 'notes', 'search'}
)

#: The generic escape-hatch tool, gated by ``pipedrive.allowRawRequest`` instead
#: of by a tool group.
RAW_REQUEST_TOOL = 'request'


def normalize_groups(raw) -> frozenset:
    """Turn the configured ``toolGroups`` value into a set of known group names.

    Accepts a list or a comma-separated string, ignores unknown names (they are
    surfaced as a warning by ``IGlobal.validateConfig``), and treats ``all`` as
    every implemented group. An empty or missing value falls back to the defaults.
    """
    if isinstance(raw, str):
        raw = raw.split(',')
    if not isinstance(raw, (list, tuple, set, frozenset)):
        return DEFAULT_GROUPS

    names = {str(g).strip().lower() for g in raw if str(g).strip()}
    if not names:
        return DEFAULT_GROUPS
    if 'all' in names or '*' in names:
        return ALL_GROUPS
    selected = names & ALL_GROUPS
    return frozenset(selected) if selected else DEFAULT_GROUPS


def pipedrive_tool(*, group: str, input_schema=None, description=None) -> Callable:
    """``@tool_function`` plus the resource group the tool belongs to.

    The group is stamped on the function so ``IInstance._collect_tool_methods()``
    can filter the published tool list without a separate registry to keep in sync.
    """
    if group not in ALL_GROUPS:
        raise ValueError(f'pipedrive_tool: unknown group "{group}"')

    def decorator(fn: Callable) -> Callable:
        fn = tool_function(input_schema=input_schema, description=description)(fn)
        fn.__pipedrive_group__ = group
        return fn

    return decorator
