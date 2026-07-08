"""Unit tests for the schema_validate node (validate.py).

Pure-logic tests — no engine / rocketlib required. Cover each flag code, the
valid/severity rollup, non-destructive provenance handling, custom field names /
maps, and pass-through of every non-fact record shape.
"""

import os
import sys
import types

# validate.py has no rocketlib import, but stub it defensively so importing the
# node package stays isolated from the native engine.
rocketlib = types.ModuleType('rocketlib')
rocketlib.debug = lambda *a, **kw: None
sys.modules.setdefault('rocketlib', rocketlib)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'nodes', 'schema_validate'))
from validate import NODE_OP, default_config, validate_fact, validate_payload  # noqa: E402


def cfg(**overrides):
    c = default_config()
    c.update(overrides)
    return c


CFG = default_config()


def codes(out):
    return [f['code'] for f in out['validation']['flags']]


# --- Checks fire -------------------------------------------------------------


def test_cost_stored_as_revenue_flags_error():
    out = validate_fact({'metric': 'Cost of goods sold', 'category': 'revenue'}, CFG)
    assert 'category_metric_mismatch' in codes(out)
    flag = next(f for f in out['validation']['flags'] if f['code'] == 'category_metric_mismatch')
    assert flag['severity'] == 'error'
    assert flag['field'] == 'category'
    assert out['validation']['valid'] is False
    assert out['validation']['severity'] == 'error'


def test_revenue_stored_as_expense_flags_error():
    out = validate_fact({'metric': 'Net sales', 'category': 'expense'}, CFG)
    assert 'category_metric_mismatch' in codes(out)
    assert out['validation']['valid'] is False


def test_missing_amount_warns():
    out = validate_fact(
        {'metric': 'Revenue', 'category': 'revenue', 'currency': 'USD', 'provenance': [{'op': 'x'}]}, CFG
    )
    assert 'missing_amount' in codes(out)
    assert out['validation']['valid'] is True


def test_non_numeric_amount_warns():
    out = validate_fact({'amount': 'lots', 'currency': 'USD', 'provenance': [{'op': 'x'}]}, CFG)
    assert 'non_numeric_amount' in codes(out)
    assert 'missing_amount' not in codes(out)


def test_bool_amount_is_non_numeric():
    out = validate_fact({'amount': True, 'currency': 'USD', 'provenance': [{'op': 'x'}]}, CFG)
    assert 'non_numeric_amount' in codes(out)


def test_comma_string_amount_non_numeric():
    out = validate_fact({'amount': '1,234', 'currency': 'USD', 'provenance': [{'op': 'x'}]}, CFG)
    assert 'non_numeric_amount' in codes(out)


def test_missing_currency_warns():
    out = validate_fact({'amount': 10, 'provenance': [{'op': 'x'}]}, CFG)
    assert 'missing_currency' in codes(out)
    assert out['validation']['valid'] is True


def test_blank_currency_warns():
    out = validate_fact({'amount': 10, 'currency': '   ', 'provenance': [{'op': 'x'}]}, CFG)
    assert 'missing_currency' in codes(out)


def test_ambiguous_metric_suppresses_mismatch():
    # "cost of revenue" contains both an expense keyword and a revenue keyword.
    out = validate_fact({'metric': 'Cost of revenue', 'category': 'revenue'}, CFG)
    assert 'ambiguous_metric' in codes(out)
    assert 'category_metric_mismatch' not in codes(out)


def test_unknown_metric_no_mismatch():
    out = validate_fact(
        {
            'metric': 'Widgets shipped',
            'category': 'revenue',
            'amount': 5,
            'currency': 'USD',
            'provenance': [{'op': 'x'}],
        },
        CFG,
    )
    assert 'category_metric_mismatch' not in codes(out)
    assert 'ambiguous_metric' not in codes(out)


def test_unknown_category_warns():
    out = validate_fact(
        {
            'metric': 'Revenue',
            'category': 'mystery-bucket',
            'amount': 5,
            'currency': 'USD',
            'provenance': [{'op': 'x'}],
        },
        CFG,
    )
    assert 'unknown_category' in codes(out)
    assert 'category_metric_mismatch' not in codes(out)


def test_sign_mismatch_when_enabled():
    out = validate_fact(
        {'category': 'cost', 'amount': 500, 'currency': 'USD', 'provenance': [{'op': 'x'}]}, cfg(sign='error')
    )
    flag = next(f for f in out['validation']['flags'] if f['code'] == 'sign_category_mismatch')
    assert flag['severity'] == 'error'
    assert out['validation']['valid'] is False


def test_sign_mismatch_off_disables():
    out = validate_fact(
        {'category': 'cost', 'amount': 500, 'currency': 'USD', 'provenance': [{'op': 'x'}]}, cfg(sign='off')
    )
    assert 'sign_category_mismatch' not in codes(out)


def test_sign_zero_never_flags():
    out = validate_fact(
        {'category': 'cost', 'amount': 0, 'currency': 'USD', 'provenance': [{'op': 'x'}]}, cfg(sign='error')
    )
    assert 'sign_category_mismatch' not in codes(out)


def test_revenue_negative_amount_sign_flag():
    out = validate_fact(
        {'category': 'revenue', 'amount': -5, 'currency': 'USD', 'provenance': [{'op': 'x'}]}, cfg(sign='warning')
    )
    assert 'sign_category_mismatch' in codes(out)


def test_missing_provenance_flags_per_config():
    out = validate_fact({'amount': 5, 'currency': 'USD'}, CFG)
    flag = next(f for f in out['validation']['flags'] if f['code'] == 'missing_provenance')
    assert flag['severity'] == 'error'
    assert out['validation']['valid'] is False


def test_missing_provenance_off():
    out = validate_fact({'amount': 5, 'currency': 'USD'}, cfg(require_provenance='off'))
    assert 'missing_provenance' not in codes(out)
    # Entry is still appended.
    assert out['provenance'][-1]['op'] == NODE_OP


# --- Output rollup -----------------------------------------------------------


def test_clean_fact_valid_ok():
    fact = {'metric': 'Revenue', 'category': 'revenue', 'amount': 100, 'currency': 'USD', 'provenance': [{'op': 'x'}]}
    out = validate_fact(fact, CFG)
    assert out['validation']['flags'] == []
    assert out['validation']['valid'] is True
    assert out['validation']['severity'] == 'ok'


def test_warnings_do_not_invalidate():
    out = validate_fact({'amount': 100, 'provenance': [{'op': 'x'}]}, CFG)  # missing_currency only
    assert out['validation']['valid'] is True
    assert out['validation']['severity'] == 'warning'


def test_existing_validation_key_overwritten():
    fact = {
        'metric': 'Revenue',
        'category': 'revenue',
        'amount': 100,
        'currency': 'USD',
        'provenance': [{'op': 'x'}],
        'validation': {'op': 'stale', 'valid': False, 'flags': [{'code': 'old'}]},
    }
    out = validate_fact(fact, CFG)
    assert out['validation']['op'] == NODE_OP
    assert out['validation']['flags'] == []
    assert out['provenance'][-1]['op'] == NODE_OP


# --- Pass-through / shapes ---------------------------------------------------


def test_plain_text_passthrough():
    assert validate_payload('hello', CFG) == 'hello'


def test_scalar_passthrough():
    assert validate_payload(123, CFG) == 123
    assert validate_payload(1.5, CFG) == 1.5
    assert validate_payload(None, CFG) is None


def test_non_dict_fact_passthrough():
    assert validate_fact('15000000', CFG) == '15000000'
    assert validate_fact(42, CFG) == 42


def test_list_of_non_dicts_passthrough():
    assert validate_payload([1, 'a'], CFG) == [1, 'a']


def test_mixed_list_validates_dicts_only():
    payload = [
        {'metric': 'Revenue', 'category': 'revenue', 'amount': 1, 'currency': 'USD', 'provenance': [{'op': 'x'}]},
        'note',
        {'metric': 'Cost of goods sold', 'category': 'revenue'},
    ]
    out = validate_payload(payload, CFG)
    assert len(out) == 3
    assert out[0]['validation']['valid'] is True
    assert out[1] == 'note'
    assert 'category_metric_mismatch' in codes(out[2])


def test_empty_list_returns_empty():
    assert validate_payload([], CFG) == []


def test_empty_dict_gets_block_not_dropped():
    out = validate_fact({}, CFG)
    assert 'missing_amount' in codes(out)
    assert 'missing_currency' in codes(out)
    assert 'missing_provenance' in codes(out)
    assert out['validation']['op'] == NODE_OP


# --- Provenance --------------------------------------------------------------


def test_provenance_preserved_and_appended():
    fact = {'amount': 1, 'currency': 'USD', 'provenance': [{'op': 'normalize_facts'}]}
    out = validate_fact(fact, CFG)
    assert len(out['provenance']) == 2
    assert out['provenance'][0] == {'op': 'normalize_facts'}
    assert out['provenance'][1]['op'] == NODE_OP


def test_provenance_created_when_absent():
    out = validate_fact({'amount': 1, 'currency': 'USD'}, CFG)
    assert out['provenance'] == [{'op': NODE_OP, 'valid': False, 'flag_codes': ['missing_provenance']}]
    assert 'missing_provenance' in codes(out)


def test_malformed_provenance_preserved_in_place():
    out = validate_fact({'amount': 1, 'currency': 'USD', 'provenance': 'origin'}, CFG)
    assert out['provenance'][0] == 'origin'
    assert out['provenance'][1]['op'] == NODE_OP
    assert 'malformed_provenance' in codes(out)
    # A non-list provenance is also "missing" for the provenance guard.
    assert 'missing_provenance' in codes(out)


def test_provenance_flag_codes_recorded():
    out = validate_fact({'metric': 'Cost of goods sold', 'category': 'revenue', 'provenance': [{'op': 'x'}]}, CFG)
    assert 'category_metric_mismatch' in out['provenance'][-1]['flag_codes']
    clean = validate_fact(
        {'metric': 'Revenue', 'category': 'revenue', 'amount': 1, 'currency': 'USD', 'provenance': [{'op': 'x'}]}, CFG
    )
    assert clean['provenance'][-1]['flag_codes'] == []


# --- Non-mutation & custom config -------------------------------------------


def test_input_not_mutated():
    fact = {'metric': 'Cost of goods sold', 'category': 'revenue', 'provenance': [{'op': 'x'}]}
    validate_fact(fact, CFG)
    assert fact == {'metric': 'Cost of goods sold', 'category': 'revenue', 'provenance': [{'op': 'x'}]}


def test_custom_field_names_and_list_payload():
    c = cfg(amount_field='value', currency_field='ccy', metric_field='kpi', category_field='bucket')
    payload = [
        {'kpi': 'Cost of goods sold', 'bucket': 'revenue', 'value': 5, 'ccy': 'USD', 'provenance': [{'op': 'x'}]},
        {'kpi': 'Revenue', 'bucket': 'revenue', 'value': 9, 'ccy': 'USD', 'provenance': [{'op': 'x'}]},
    ]
    out = validate_payload(payload, c)
    assert 'category_metric_mismatch' in codes(out[0])
    assert out[1]['validation']['valid'] is True
    assert out[0]['value'] == 5 and out[0]['ccy'] == 'USD'


def test_custom_category_metric_map():
    c = cfg(category_metric_map={'revenue': ['widget'], 'expense': ['gadget']})
    out = validate_fact({'metric': 'gadget sales', 'category': 'revenue', 'provenance': [{'op': 'x'}]}, c)
    assert 'category_metric_mismatch' in codes(out)


def test_empty_map_skips_mismatch():
    c = cfg(category_metric_map={})
    out = validate_fact(
        {
            'metric': 'Cost of goods sold',
            'category': 'revenue',
            'amount': 1,
            'currency': 'USD',
            'provenance': [{'op': 'x'}],
        },
        c,
    )
    assert 'category_metric_mismatch' not in codes(out)


def test_custom_map_omitting_declared_category_still_flags():
    # Regression: a mismatch must fire even when the declared canonical category
    # is not a key in the (custom) map — the metric infers one class, the fact
    # declares another, and that disagreement is a real inconsistency.
    c = cfg(category_metric_map={'revenue': ['widget'], 'expense': ['gadget']})
    out = validate_fact({'metric': 'widget', 'category': 'asset', 'provenance': [{'op': 'x'}]}, c)
    assert 'category_metric_mismatch' in codes(out)


def test_readme_flagship_example_two_flags():
    # Pins the declared-over-inferred sign precedence: a cost metric declared as
    # revenue with a positive amount yields exactly the mismatch + provenance
    # flags — the sign check does NOT fire because declared 'revenue' is a
    # positive class consistent with +500.
    out = validate_fact({'metric': 'Cost of goods sold', 'category': 'revenue', 'amount': 500, 'currency': 'USD'}, CFG)
    assert codes(out) == ['category_metric_mismatch', 'missing_provenance']
    assert 'sign_category_mismatch' not in codes(out)
    assert out['validation']['valid'] is False
    assert out['validation']['severity'] == 'error'
