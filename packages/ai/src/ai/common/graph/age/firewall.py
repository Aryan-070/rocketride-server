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

"""Query firewall for the Cypher -> AGE pipeline.

Two rule families, applied per the design:

- **Resource caps** — enforced on BOTH paths (safe and raw EXECUTE). Raw
  execute skips *semantic* checks, never resource limits: a runaway traversal
  is just as expensive when a trusted app submits it. The database-side
  backstop is a ``statement_timeout`` the emitter sets per transaction.
- **Semantic rules** — safe path only. Writes and procedure CALLs are
  rejected here before translation; the true guard is the read-only
  transaction the node runs safe queries in (server-side, like FalkorDB's
  RO_QUERY), with this check giving precise, pre-flight errors.

Caps are constructor arguments so the node can expose them as config; the
defaults were sanity-checked against the pinned AGE 1.5.0 container.
"""

from __future__ import annotations

from dataclasses import dataclass

from .analysis import CypherFacts
from .errors import AgeFirewallRejected

# Defaults tuned against the pinned container (see the layer README):
# unbounded/deep variable-length traversals are the main resource hazard —
# AGE expands them recursively; depth 10 on a connected graph is already huge.
DEFAULT_MAX_QUERY_LENGTH = 10_000
DEFAULT_MAX_VAR_LENGTH_DEPTH = 10
DEFAULT_STATEMENT_TIMEOUT_MS = 30_000


@dataclass(frozen=True)
class FirewallConfig:
    max_query_length: int = DEFAULT_MAX_QUERY_LENGTH
    max_var_length_depth: int = DEFAULT_MAX_VAR_LENGTH_DEPTH
    # Applied by the emitter as SET LOCAL statement_timeout in the query's
    # transaction — the database-side resource backstop for both paths.
    statement_timeout_ms: int = DEFAULT_STATEMENT_TIMEOUT_MS


def check_resource_caps(facts: CypherFacts, config: FirewallConfig) -> None:
    """Resource caps — both paths. Raises AgeFirewallRejected on violation."""
    if len(facts.query) > config.max_query_length:
        raise AgeFirewallRejected(
            'max_query_length',
            f'query is {len(facts.query)} chars (limit {config.max_query_length})',
        )

    for lower, upper in facts.var_length_ranges:
        if upper is None:
            raise AgeFirewallRejected(
                'unbounded_var_length',
                f'variable-length pattern without an upper bound (use e.g. *1..{config.max_var_length_depth})',
            )
        if upper > config.max_var_length_depth:
            raise AgeFirewallRejected(
                'max_var_length_depth',
                f'variable-length upper bound {upper} exceeds limit {config.max_var_length_depth}',
            )
        if lower is not None and lower > upper:
            raise AgeFirewallRejected('invalid_var_length_range', f'lower bound {lower} exceeds upper bound {upper}')


def check_semantics_readonly(facts: CypherFacts) -> None:
    """Semantic rules — safe path only. Rejects writes and procedure CALLs."""
    if facts.write_clauses:
        clauses = ', '.join(sorted(facts.write_clauses))
        raise AgeFirewallRejected(
            'write_clause',
            f'{clauses} not allowed on the read-only path (use the execute path for writes)',
        )
    if facts.has_call:
        raise AgeFirewallRejected('procedure_call', 'CALL is not allowed on the read-only path')
