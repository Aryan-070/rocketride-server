# Copyright 2026 Aparavi Software AG — MIT License
"""Read-only guards for the convenience query tools.

`execute` bypasses is_sql_safe by design, so the MCP handler enforces read-only
BEFORE issuing the RPC.
"""

import re

from ai.common.database.sql_safety import is_sql_safe

_CYPHER_WRITE = ('CREATE', 'MERGE', 'DELETE', 'SET', 'REMOVE', 'DETACH', 'DROP', 'CALL')
_WORD = re.compile(r'[A-Za-z]+')


def assert_sql_read_only(sql: str) -> None:
    if not is_sql_safe(sql):
        raise ValueError('Only read-only SQL (SELECT/EXPLAIN) is permitted')


def is_cypher_read_only(cypher: str) -> bool:
    tokens = {w.upper() for w in _WORD.findall(cypher)}
    return not tokens.intersection(_CYPHER_WRITE)


def assert_cypher_read_only(cypher: str) -> None:
    if not is_cypher_read_only(cypher):
        raise ValueError('Only read-only Cypher (MATCH/RETURN/WITH) is permitted')
