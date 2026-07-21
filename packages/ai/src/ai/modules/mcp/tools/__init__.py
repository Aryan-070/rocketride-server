# Copyright 2026 Aparavi Software AG. MIT License.
"""Tool registration entry point for the MCP tool surface.

``register_all(registry)`` populates one shared ``ToolRegistry`` (built once
in ``handlers.build_mcp_server``) by calling each tool module's own
``register(registry)``. Later tasks append imports here, one per remaining
tool group, e.g.:

    from . import capability
    capability.register(registry)
    from . import visibility
    visibility.register(registry)
"""

from ..tooling import ToolRegistry
from . import capability
from . import execution
from . import introspection
from . import query
from . import visibility


def register_all(registry: ToolRegistry) -> None:
    """Register every tool module's tools against ``registry``.

    Wires the introspection tools (`list_components`, `describe_component`,
    `validate_pipeline`, `describe_pipeline`), the execution tools
    (`run_pipeline`, `send_data`, `terminate`, `send_files`), the capability
    tools (`set_env`, `list_env_keys`, `store_read`, `store_list`,
    `save_template`, `load_template`, `deploy_add`), the visibility tool
    (`monitor`), and the convenience query tool (`sql_query`) -- 18 tools
    total.
    """
    introspection.register(registry)
    execution.register(registry)
    capability.register(registry)
    visibility.register(registry)
    query.register(registry)
