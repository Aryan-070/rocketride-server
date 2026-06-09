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
from __future__ import annotations

from typing import Optional

# Exception class-names treated as hard failures (surfaced as MCP tool errors,
# not agent-actionable). See open-q #14.
HARD_EXC_NAMES = ('ConnectionError', 'AuthenticationException', 'TimeoutError')


class HardError(Exception):
    """A connection/auth-class failure surfaced to the agent as an MCP tool error."""

    def __init__(self, message: str, error_type: str = 'hard') -> None:
        super().__init__(message)
        self.message = message
        self.error_type = error_type


def _extract_dap_failure(exc: Exception) -> Optional[str]:
    """Return the engine failure message if the exception carries a failed DAP result."""
    dap_result = getattr(exc, 'dap_result', None)
    if isinstance(dap_result, dict) and dap_result.get('success') is False:
        return str(dap_result.get('message') or 'engine reported failure')
    return None


def normalize_error(exc: Exception, *, hint: Optional[str] = None) -> dict:
    """Map a client exception to either a HardError (raised) or a structured result.

    The client's exception surface is inconsistent, so we classify by type-name and
    by any attached DAP failure body rather than by exception class alone.
    """
    name = type(exc).__name__
    if name in HARD_EXC_NAMES:
        raise HardError(str(exc), error_type=name)
    message = _extract_dap_failure(exc) or str(exc)
    return {'ok': False, 'error_type': name, 'message': message, 'hint': hint}
