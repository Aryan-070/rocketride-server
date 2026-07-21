# Copyright 2026 Aparavi Software AG — MIT License
import pytest
from ai.modules.mcp.read_guards import (
    assert_sql_read_only,
    is_cypher_read_only,
    assert_cypher_read_only,
)


def test_sql_read_allows_select():
    assert_sql_read_only('SELECT * FROM t')  # no raise


def test_sql_read_blocks_write():
    with pytest.raises(ValueError):
        assert_sql_read_only('DELETE FROM t')


def test_cypher_read_only_detection():
    assert is_cypher_read_only('MATCH (n) RETURN n')
    assert is_cypher_read_only('MATCH (a)-[r]->(b) WITH a RETURN a')
    assert not is_cypher_read_only('CREATE (n:X) RETURN n')
    assert not is_cypher_read_only('MATCH (n) DETACH DELETE n')
    assert not is_cypher_read_only('MATCH (n) SET n.x = 1')


def test_assert_cypher_raises_on_write():
    with pytest.raises(ValueError):
        assert_cypher_read_only('MERGE (n:X)')
