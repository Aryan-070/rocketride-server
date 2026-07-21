# Copyright 2026 Aparavi Software AG — MIT License
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from ai.common.database.db_instance_base import DatabaseInstanceBase
from ai.common.schema import Question, QuestionType


class _ConcreteDB(DatabaseInstanceBase):
    """Minimal concrete subclass — DatabaseInstanceBase is an ABC, and Python's
    ``object.__new__`` refuses to instantiate a class with unimplemented
    abstract methods even when ``__init__`` is bypassed.
    """

    def _db_display_name(self):
        return 'TestDB'

    def _db_dialect(self):
        return 'testdb'


def _make_instance(allow_execute=True):
    inst = _ConcreteDB.__new__(_ConcreteDB)
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE t (id INTEGER, name TEXT)'))
        conn.execute(text("INSERT INTO t VALUES (1,'a'),(2,'b')"))
    written = {}
    inst.IGlobal = SimpleNamespace(allow_execute=allow_execute, max_execute_rows=25000, engine=engine)
    inst.instance = SimpleNamespace(
        getListeners=lambda: ['answers'],
        writeText=lambda *_a, **_k: None,
        writeTable=lambda v: written.setdefault('table', v),
        writeAnswers=lambda a: written.setdefault('answers', a),
    )
    inst._written = written
    return inst


def test_execute_type_runs_raw_select_no_llm():
    inst = _make_instance()
    q = Question(type=QuestionType.EXECUTE)
    q.addQuestion('SELECT id, name FROM t ORDER BY id')
    inst.writeQuestions(q)
    # LLM path must not have been taken; rows come back structured
    ans = inst._written['answers']
    assert '"row_count": 2' in str(ans) or getattr(ans, 'rows', None) == 2


def test_execute_blocked_when_disabled():
    inst = _make_instance(allow_execute=False)
    q = Question(type=QuestionType.EXECUTE)
    q.addQuestion('SELECT 1')
    with pytest.raises(ValueError):
        inst.writeQuestions(q)


def test_execute_rejects_write_statement():
    inst = _make_instance()
    q = Question(type=QuestionType.EXECUTE)
    q.addQuestion('DELETE FROM t')
    with pytest.raises(ValueError):
        inst.writeQuestions(q)
