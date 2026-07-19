"""Unit tests for the normalize_facts node (normalize.py).

Pure-logic tests — no engine / rocketlib required. Cover number/sign parsing,
currency and scale detection (tag-only), label->metric mapping, non-destructive
normalization, idempotency, and cross-batch dedupe (conflicts kept, not dropped).
"""

import os
import sys
import types

# normalize.py has no rocketlib import, but stub it defensively so importing the
# node package stays isolated from the native engine.
rocketlib = types.ModuleType('rocketlib')
rocketlib.debug = lambda *a, **kw: None
sys.modules.setdefault('rocketlib', rocketlib)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'nodes', 'normalize_facts'))
from normalize import (  # noqa: E402
    NODE_OP,
    build_mapping,
    detect_currency,
    detect_scale,
    dedupe_facts,
    map_metric,
    normalize_fact,
    normalize_payload,
    parse_number,
)


CFG = {
    'label_field': 'label',
    'value_field': 'value',
    'default_currency': '',
    'decimal_format': 'auto',
    'mapping': build_mapping({'Turnover': 'revenue'}),
}


# --- number & sign parsing --------------------------------------------------


def test_parse_plain_integer():
    value, neg, source = parse_number(42)
    assert int(value) == 42
    assert neg is False
    assert source == 'none'


def test_parse_us_thousands():
    value, _, _ = parse_number('1,234.5')
    assert value == 1234.5


def test_parse_parentheses_negative():
    value, neg, source = parse_number('(100)')
    assert value == -100
    assert neg is True
    assert source == 'parentheses'


def test_parse_trailing_minus():
    value, neg, source = parse_number('100-')
    assert value == -100
    assert source == 'trailing_minus'


def test_parse_leading_minus():
    value, neg, source = parse_number('-100')
    assert value == -100
    assert source == 'leading_minus'


def test_parse_unicode_minus():
    value, neg, _ = parse_number('−100')
    assert value == -100
    assert neg is True


def test_parse_eu_format():
    value, _, _ = parse_number('1.234.567,89', 'eu')
    assert float(value) == 1234567.89


def test_parse_footnote_stripped():
    value, _, _ = parse_number('1,234(a)')
    assert value == 1234


def test_parse_scale_suffix_then_footnote():
    # Regression: the footnote used to block the end-anchored suffix strip,
    # losing the value while detect_scale still tagged millions.
    value, _, _ = parse_number('1,234m(a)')
    assert value == 1234
    value, _, _ = parse_number('1,234m (b)')
    assert value == 1234


def test_parse_currency_symbol_and_scale_suffix():
    value, neg, source = parse_number('(£456.789m)')
    assert float(value) == -456.789
    assert source == 'parentheses'


def test_parse_sentinel_na():
    assert parse_number('N/A') == (None, False, 'none')
    assert parse_number('—') == (None, False, 'none')


def test_parse_boolean_rejected():
    assert parse_number(True) == (None, False, 'none')


def test_parse_unparseable_returns_none():
    value, _, _ = parse_number('not a number')
    assert value is None


# --- currency detection -----------------------------------------------------


def test_detect_currency_value_symbol():
    assert detect_currency('Revenue', '$5') == ('USD', 'value_symbol')


def test_detect_currency_value_code_overrides_dollar():
    assert detect_currency('x', '$5 CAD') == ('CAD', 'value_code')


def test_detect_currency_label_code():
    assert detect_currency('Revenue in GBP', '5') == ('GBP', 'label_code')


def test_detect_currency_none_and_default():
    assert detect_currency('Revenue', '100') == ('', 'none')
    assert detect_currency('Revenue', '100', default_currency='USD') == ('USD', 'config_default')


# --- scale detection --------------------------------------------------------


def test_detect_scale_label_bracket():
    assert detect_scale('Revenue (in millions)', '5') == (1_000_000, 'millions', 'label')


def test_detect_scale_value_suffix():
    assert detect_scale('Assets', '£500m') == (1_000_000, 'millions', 'value')


def test_detect_scale_thousands_k():
    assert detect_scale('x', '100k') == (1_000, 'thousands', 'value')


def test_detect_scale_billions_bn_suffix():
    assert detect_scale('x', '1.2bn') == (1_000_000_000, 'billions', 'value')


def test_detect_scale_none():
    assert detect_scale('Revenue', '100') == (1, '', 'none')


def test_detect_scale_bare_letter_in_prose_ignored():
    assert detect_scale('summary of the memo', '100') == (1, '', 'none')


# --- label -> metric mapping ------------------------------------------------


def test_map_metric_mapped():
    assert map_metric('Revenue (in millions USD)', CFG['mapping']) == ('revenue', 'mapped')


def test_map_metric_longest_wins():
    assert map_metric('Diluted Earnings Per Share', CFG['mapping']) == ('diluted_eps', 'mapped')


def test_map_metric_config_override():
    assert map_metric('Turnover', CFG['mapping']) == ('revenue', 'mapped')


def test_map_metric_passthrough():
    assert map_metric('Weird Line XYZ', CFG['mapping']) == ('weird line xyz', 'passthrough')


def test_map_metric_empty():
    assert map_metric('', CFG['mapping']) == ('', 'empty')


# --- full fact normalization ------------------------------------------------


def test_normalize_fact_full():
    out = normalize_fact({'label': 'Revenue ($ in millions)', 'value': '1,234.5'}, CFG)
    assert out['normalized'] == {
        'metric': 'revenue',
        'value_normalized': 1234.5,
        'currency': 'USD',
        'scale_factor': 1_000_000,
        'scale_unit': 'millions',
        'is_negative': False,
    }
    # Top-level handoff mirror for currency_convert_explicit.
    assert out['amount'] == 1234.5
    assert out['currency'] == 'USD'
    # Raw fields preserved.
    assert out['value'] == '1,234.5'


def test_normalize_fact_negative_gbp_scale():
    out = normalize_fact({'label': 'Cost of Goods Sold', 'value': '(£456.789m)'}, CFG)
    n = out['normalized']
    assert n['metric'] == 'cost_of_goods_sold'
    assert n['value_normalized'] == -456.789
    assert n['currency'] == 'GBP'
    assert n['scale_factor'] == 1_000_000
    assert n['is_negative'] is True
    entry = out['provenance'][-1]
    assert entry['sign_source'] == 'parentheses'
    assert entry['currency_source'] == 'value_symbol'
    assert entry['scale_source'] == 'value'


def test_normalize_fact_unmapped_no_currency():
    out = normalize_fact({'label': 'Weird Line Item XYZ', 'value': 42}, CFG)
    assert out['normalized']['metric'] == 'weird line item xyz'
    assert out['normalized']['value_normalized'] == 42
    assert out['normalized']['currency'] == ''
    assert out['normalized']['scale_factor'] == 1


def test_normalize_fact_non_destructive():
    fact = {'label': 'Revenue', 'value': '100', 'page': 7}
    original = dict(fact)
    out = normalize_fact(fact, CFG)
    assert fact == original  # input not mutated
    assert out['page'] == 7  # extra keys preserved


def test_normalize_fact_scale_not_multiplied():
    out = normalize_fact({'label': 'Revenue (in millions)', 'value': '1,234.5'}, CFG)
    assert out['normalized']['value_normalized'] == 1234.5  # NOT 1_234_500_000
    assert out['normalized']['scale_factor'] == 1_000_000


def test_normalize_fact_scale_suffix_with_footnote():
    # Regression: '1,234m (a)' must keep BOTH the parsed value and the scale
    # tag; the value used to come back null while the scale was still tagged.
    out = normalize_fact({'label': 'Revenue', 'value': '1,234m (a)'}, CFG)
    assert out['normalized']['value_normalized'] == 1234
    assert out['normalized']['scale_factor'] == 1_000_000
    assert out['normalized']['scale_unit'] == 'millions'


def test_normalize_fact_idempotent():
    once = normalize_fact({'label': 'Revenue', 'value': '100'}, CFG)
    twice = normalize_fact(once, CFG)
    assert twice['normalized'] == once['normalized']
    assert twice['normalized']['value_normalized'] == 100


def test_normalize_fact_preserves_existing_provenance():
    out = normalize_fact({'label': 'Revenue', 'value': '100', 'provenance': [{'op': 'extract'}]}, CFG)
    assert len(out['provenance']) == 2
    assert out['provenance'][0] == {'op': 'extract'}
    assert out['provenance'][1]['op'] == NODE_OP


def test_normalize_fact_non_list_provenance_preserved():
    out = normalize_fact({'label': 'Revenue', 'value': '100', 'provenance': 'origin'}, CFG)
    assert out['provenance'][0] == 'origin'
    assert out['provenance'][1]['op'] == NODE_OP


def test_normalize_fact_non_dict_passthrough():
    assert normalize_fact('text', CFG) == 'text'
    assert normalize_fact(42, CFG) == 42


def test_normalize_fact_top_level_not_clobbered():
    out = normalize_fact({'label': 'Revenue', 'value': '100', 'amount': 999, 'currency': 'JPY'}, CFG)
    assert out['amount'] == 999
    assert out['currency'] == 'JPY'


def test_normalize_payload_list_mixed():
    payload = [{'label': 'Revenue', 'value': '100'}, 'bare-text', 7]
    out = normalize_payload(payload, CFG)
    assert out[0]['normalized']['metric'] == 'revenue'
    assert out[1] == 'bare-text'
    assert out[2] == 7


def test_normalize_payload_scalar_passthrough():
    assert normalize_payload('hello', CFG) == 'hello'
    assert normalize_payload(123, CFG) == 123


# --- dedupe -----------------------------------------------------------------


def _fact(metric, value, currency='USD', scale=1, neg=False):
    return {
        'normalized': {
            'metric': metric,
            'value_normalized': value,
            'currency': currency,
            'scale_factor': scale,
            'is_negative': neg,
        }
    }


def test_dedupe_exact_duplicate_dropped():
    out = dedupe_facts([_fact('revenue', 100), _fact('revenue', 100)])
    assert len(out) == 1


def test_dedupe_conflict_kept():
    out = dedupe_facts([_fact('revenue', 100), _fact('revenue', 200)])
    assert len(out) == 2


def test_dedupe_stable_order():
    facts = [_fact('c', 3), _fact('a', 1), _fact('b', 2), _fact('a', 1)]
    out = dedupe_facts(facts)
    assert [f['normalized']['metric'] for f in out] == ['c', 'a', 'b']


def test_dedupe_null_value_never_merged():
    out = dedupe_facts([_fact('revenue', None), _fact('revenue', None)])
    assert len(out) == 2


def test_dedupe_scale_differs_kept():
    out = dedupe_facts([_fact('revenue', 1, scale=1_000_000), _fact('revenue', 1, scale=1_000)])
    assert len(out) == 2


def test_dedupe_non_normalized_passthrough():
    out = dedupe_facts(['a', 'a', 'b'])
    assert out == ['a', 'b']
