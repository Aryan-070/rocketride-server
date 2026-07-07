# Copyright 2026 Aparavi Software AG. MIT License.
"""Error normalization for MCP tool handlers.

The RocketRide client's exception surface is inconsistent: some failures
collapse to a bare ``RuntimeError``, others carry typed classes
(``ConnectionError``, ``AuthenticationException``, ``TimeoutError``, ...)
with an attached ``dap_result`` body. ``normalize_error`` classifies by
type-name (not class identity, since most failures collapse to
``RuntimeError``) into either a hard failure (raised as ``HardError``,
surfaced to the agent as an MCP tool error) or a structured, self-correctable
result dict.
"""

from typing import Any, Optional

HARD_EXC_NAMES = ('ConnectionError', 'AuthenticationException', 'TimeoutError')


class HardError(Exception):
    """A non-self-correctable failure (connection/auth lost, timeout).

    Raised by ``normalize_error`` for exceptions whose type name is in
    ``HARD_EXC_NAMES``; callers let this propagate so the MCP dispatch layer
    surfaces it as an MCP tool error rather than an in-band ``{ok: False}``
    result.
    """

    def __init__(self, message: str, error_type: str = 'hard'):
        super().__init__(message)
        self.message = message
        self.error_type = error_type


def _bad(message: str, hint: str) -> dict:
    """Build a structured bad-request result for a tool handler."""
    return {
        'ok': False,
        'error_type': 'BadRequest',
        'message': message,
        'hint': hint,
    }


def _extract_dap_failure(exc: Exception) -> Optional[str]:
    """Pull the failure message out of an attached DAP result, if any.

    Returns ``None`` when the exception has no ``dap_result`` attribute, or
    when the attached ``dap_result`` does not report ``success is False``.
    """
    dap_result: Any = getattr(exc, 'dap_result', None)
    if not isinstance(dap_result, dict):
        return None
    if dap_result.get('success') is False:
        return dap_result.get('message')
    return None


def normalize_error(exc: Exception, *, hint: Optional[str] = None) -> dict:
    """Classify ``exc`` into a hard failure or a structured result dict.

    Hard failures (type name in ``HARD_EXC_NAMES``) raise ``HardError`` so
    the MCP dispatch layer surfaces them as a tool error. Everything else
    returns ``{ok: False, error_type, message, hint}`` so the agent can
    self-correct (e.g. missing env -> call ``set_env``).
    """
    error_type = type(exc).__name__
    if error_type in HARD_EXC_NAMES:
        raise HardError(str(exc), error_type=error_type)
    return {
        'ok': False,
        'error_type': error_type,
        'message': _extract_dap_failure(exc) or str(exc),
        'hint': hint,
    }
