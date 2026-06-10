# Copyright (c) 2026 Aparavi Software AG

import inspect
from typing import Callable, Optional

from rocketlib import IInstanceBase, invoke_function, warning
from ai.common.schema import Question, Answer


class LLMBase(IInstanceBase):
    """Shared base instance for LLM-style nodes.

    This class is the canonical node-level base for LLM providers and adapters.
    Provider-specific request/retry behavior remains in ai.common.chat.ChatBase.
    """

    def _question(
        self,
        question: Question,
        on_chunk: Optional[Callable[[str], None]] = None,
        on_finish: Optional[Callable[[Optional[str]], None]] = None,
        on_reasoning_chunk: Optional[Callable[[str], None]] = None,
    ) -> Answer:
        chat = self.IGlobal._chat
        # Legacy drivers override chat(self, question) without streaming callbacks.
        try:
            accepts_stream = 'on_chunk' in inspect.signature(chat.chat).parameters
        except (TypeError, ValueError):
            accepts_stream = True
        if not accepts_stream:
            return chat.chat(question)
        return chat.chat(
            question,
            on_chunk=on_chunk,
            on_finish=on_finish,
            on_reasoning_chunk=on_reasoning_chunk,
        )

    def writeQuestions(self, question: Question):
        # Emit the model's reasoning on the chat-ui 'thinking' lane (same channel as agents).
        reasoning_parts: list = []

        def _noop(_text: str) -> None:
            pass

        def on_reasoning_chunk(text: str) -> None:
            if text:
                reasoning_parts.append(text)

        try:
            answer = self._question(
                question,
                on_chunk=_noop,
                on_reasoning_chunk=on_reasoning_chunk,
            )
        except Exception as e:
            err_msg = f'**LLM error** — {type(e).__name__}: {e}'
            warning(f'writeQuestions: LLM call failed: {type(e).__name__}: {e}')
            answer = Answer()
            answer.setAnswer(err_msg)
            self.instance.writeAnswers(answer)
            return

        reasoning = ''.join(reasoning_parts).strip()
        if reasoning:
            try:
                self.instance.sendSSE('thinking', message=reasoning)
            except Exception:
                pass
        self.instance.writeAnswers(answer)

    @invoke_function
    def getContextLength(self, _param):
        return self.IGlobal._chat.getTotalTokens()

    @invoke_function
    def getOutputLength(self, _param):
        return self.IGlobal._chat.getOutputTokens()

    @invoke_function
    def getTokenCounter(self, _param):
        return self.IGlobal._chat.getTokens

    @invoke_function
    def ask(self, param):
        return self._question(param.question)
