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

import json
from typing import Any, Dict


def load_pipeline(args: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve a pipeline config from `pipeline` (inline dict) or `filepath` (JSON/JSON5 file).

    Raises ValueError on missing/invalid input (callers convert to a BadRequest result).
    """
    args = args or {}
    pipeline = args.get('pipeline')
    if pipeline is None:
        filepath = args.get('filepath')
        if not filepath:
            raise ValueError('Provide either `pipeline` (inline dict) or `filepath`')
        with open(filepath, 'r', encoding='utf-8') as fh:
            text = fh.read()
        try:
            pipeline = json.loads(text)
        except json.JSONDecodeError:
            try:
                import json5  # optional; .pipe files may use JSON5
            except ImportError as exc:
                raise ValueError('File is not valid JSON (install json5 for JSON5 support)') from exc
            pipeline = json5.loads(text)
    if isinstance(pipeline, dict) and 'pipeline' in pipeline and 'components' not in pipeline:
        pipeline = pipeline['pipeline']
    if not isinstance(pipeline, dict):
        raise ValueError('Pipeline must be a JSON object')
    return pipeline
