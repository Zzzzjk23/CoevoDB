"""S3 independent acceptance gate. Expectations measured before dispatch.

Run from framework/: python -m surprise.gates.s03 [--only registry local cross version matrix]
PostgreSQL reference: COEVO_REFERENCE_PG_DSN or local port 55432 (see HANDOFF).
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ORACLES = ('tlp', 'norec', 'plan_variant', 'index_presence', 'equivalent_query',
           'version_differential', 'cross_dbms')
SETUP = ('CREATE TABLE t(a INT, b INT)', 'INSERT INTO t VALUES (1,1),(2,NULL),(3,3)')
ALL_SETUP = ('CREATE TABLE t(v INT)', 'INSERT INTO t VALUES (1),(1),(2),(2),(2),(NULL)',
             'CREATE TABLE u(v INT)', 'INSERT INTO u VALUES (1),(2),(NULL)')
EXPECTED = {'EXCEPT ALL': [[1], [2], [2]], 'INTERSECT ALL': [[1], [2], [None]]}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def case(engine='duckdb', query='SELECT a, b FROM t', predicate='b > 1', setup=SETUP):
    from surprise.harness.contracts import SqlCase
    return SqlCase(engine, tuple(setup), query, predicate)


def judge(x, oracle, **kwargs):
    from surprise.harness.oracles import judge as implementation
    return implementation(x, oracle, **kwargs)


def label_is(label, y, reason=None):
    require(label.y == y, f'expected {y}, got {label.to_dict()}')
    if reason is not None:
        require(label.invalid_reason == reason, f'expected {reason}, got {label.to_dict()}')
    if y == 'fail':
        require(label.fail_kind in ('wrong_result', 'error_mismatch', 'crash'), 'missing fail kind')
    require(label.cve == {}, 'S3 must not implement CVE')


def check_registry():
    from surprise.harness.contracts import INVALID_REASONS
    from surprise.harness.oracles import registry
    require(callable(registry.get_handler) and callable(registry.register), 'missing registry API')
    needed = {'untrusted_rewrite', 'direction_unknown', 'insufficient_engines', 'non_unique_outlier'}
    require(needed <= set(INVALID_REASONS), f'missing invalid reasons {needed - set(INVALID_REASONS)}')
    for engine in ('duckdb', 'datafusion'):
        for oracle in ORACLES[:3]:
            a = judge(case(engine), oracle)
            label_is(a, 'pass')
            require(a.to_dict() == judge(case(engine), oracle).to_dict(), 'unstable sound adapter')
            require(callable(registry.get_handler(oracle)), 'non-callable registry entry')
    for bad_case, bad_oracle in ((case(), 'no_such_oracle'), (case('sqlite'), 'tlp')):
        try:
            judge(bad_case, bad_oracle)
        except ValueError:
            pass
        else:
            raise AssertionError('unknown oracle / unsupported target must raise')
    return '3 existing oracles x 2 engines pass; registry and invalid sources checked'


def check_local():
    from oracles.db_runner import QueryResult
    from targets.duckdb_runner import DuckDBRunner
    indexed = case(query='SELECT a, b FROM t WHERE a = 3', predicate=None)
    actual = judge(indexed, 'index_presence')
    label_is(actual, 'pass')
    require(bool(actual.detail.get('indexes_created')), 'index oracle did not create any ART index')
    label_is(judge(case('datafusion'), 'index_presence'), 'invalid', 'not_applicable')

    class IndexMismatch(DuckDBRunner):
        def __init__(self):
            super().__init__()
            self.indexed = False

        def run(self, sql, timeout_s=10.0):
            result = super().run(sql, timeout_s)
            if 'CREATE' in sql.upper() and 'INDEX' in sql.upper() and result.ok:
                self.indexed = True
            if self.indexed and sql.strip().rstrip(';') == indexed.query:
                return QueryResult(rows=[])
            return result

    injected = judge(indexed, 'index_presence', runner_factory=IndexMismatch)
    label_is(injected, 'fail')
    require(injected.fail_kind == 'wrong_result', 'index discrepancy not mapped to wrong_result')
    rules = [
        ('double_negation', 'SELECT a FROM t WHERE b > 1', [[3]]),
        ('demorgan', 'SELECT a FROM t WHERE NOT (b > 1 AND a < 3)', [[1], [3]]),
        ('case_to_coalesce', 'SELECT CASE WHEN b IS NOT NULL THEN b ELSE 0 END AS v FROM t', [[1], [0], [3]]),
    ]
    from surprise.harness.oracles.rewrites import RULES, apply_rule
    from oracles.normalize import loose_bag
    from targets.datafusion_runner import DataFusionRunner
    for rule, query, expected in rules:
        require(rule in RULES, f'missing rule {rule}')
        proof = RULES[rule].get('proof') if isinstance(RULES[rule], dict) else getattr(RULES[rule], 'proof', None)
        require(isinstance(proof, str) and len(proof) >= 30, f'{rule} lacks equivalence argument')
        rewritten = apply_rule(query, rule)
        require(isinstance(rewritten, str) and rewritten != query, f'{rule} did not rewrite')
        for engine, factory in (('duckdb', DuckDBRunner), ('datafusion', DataFusionRunner)):
            r = factory()
            try:
                require(all(error is None for _, error in r.setup(SETUP)), 'rewrite setup failed')
                left, right = r.run(query), r.run(rewritten)
                require(left.ok and right.ok, 'rewrite does not execute')
                require(loose_bag(left.rows) == loose_bag(expected) == loose_bag(right.rows),
                        f'{engine}/{rule} lost NULL or multiplicity semantics')
            finally:
                r.close()
            label_is(judge(case(engine, query, None), 'equivalent_query', rewrite_rule=rule), 'pass')
    untrusted = case(query='SELECT a FROM t WHERE b > 1', predicate=None)
    label_is(judge(untrusted, 'equivalent_query', paired_query='SELECT a FROM t'),
             'invalid', 'untrusted_rewrite')
    label_is(judge(untrusted, 'equivalent_query', rewrite_rule='double_negation',
                   paired_query='SELECT a FROM t'), 'invalid', 'untrusted_rewrite')
    label_is(judge(untrusted, 'equivalent_query', rewrite_rule='invented_rule'),
             'invalid', 'untrusted_rewrite')
    require(apply_rule('SELECT 1', 'demorgan') is None, 'non-applicable De Morgan rule must decline')
    for query in (
        'SELECT a FROM t WHERE NOT (b BETWEEN 1 AND 3)',
        'SELECT a FROM t WHERE NOT (CASE WHEN a > 0 THEN b > 0 AND b < 5 ELSE FALSE END)',
    ):
        require(apply_rule(query, 'demorgan') is None, 'De Morgan split AND inside BETWEEN/CASE')
        for engine in ('duckdb', 'datafusion'):
            label_is(judge(case(engine, query, None), 'equivalent_query', rewrite_rule='demorgan'),
                     'invalid', 'not_applicable')
    literal_case = case('duckdb', predicate=None, setup=('CREATE TABLE t(s VARCHAR)',
        "INSERT INTO t VALUES (NULL), ('ZZ')"),
        query="SELECT CASE WHEN s IS NOT NULL THEN s ELSE 'ABC' END FROM t")
    certified = apply_rule(literal_case.query, 'case_to_coalesce')
    require(isinstance(certified, str), 'literal CASE shape must remain supported')
    label_is(judge(literal_case, 'equivalent_query', rewrite_rule='case_to_coalesce',
        paired_query=certified.replace("'ABC'", "'abc'")), 'invalid', 'untrusted_rewrite')
    escaped = r"SELECT E'abc\' CASE WHEN b IS NOT NULL THEN b ELSE 0 END \'xyz' FROM t"
    require(apply_rule(escaped, 'case_to_coalesce') is None,
            'CASE rule rewrote SQL text inside an escaped string literal')
    for engine in ('duckdb', 'datafusion'):
        label_is(judge(case(engine, escaped, None), 'equivalent_query',
                       rewrite_rule='case_to_coalesce'), 'invalid', 'not_applicable')
    return 'ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected'


def constant_factory(rows):
    from oracles.db_runner import QueryResult
    class Constant:
        engine_version = 'fixture'
        def setup(self, statements):
            return [(s, None) for s in statements]
        def run(self, sql, timeout_s=10.0):
            return QueryResult(rows=rows)
        def close(self):
            pass
    return Constant


def check_cross():
    from oracles.normalize import loose_bag
    from surprise.harness.oracles.pg_reference import PostgresReferenceRunner, is_readonly_query
    from oracles.db_runner import QueryResult
    require(not is_readonly_query('SELECT 1; SELECT 2'), 'PG reference accepted multiple statements')
    require(not is_readonly_query('SELECT 1; SET ROLE coevo'), 'PG reference accepted embedded state change')
    require(not is_readonly_query('WITH x AS (SELECT 1 AS a) SELECT a INTO z FROM x'),
            'PG reference accepted SELECT INTO after a WITH head')

    class SetupRecorder(PostgresReferenceRunner):
        def __init__(self):
            super().__init__()
            self.executed = []
        def _reset(self):
            self._schema = 's03_gate_recorder'
        def _execute(self, statement, *, timeout_ms, fetch):
            self.executed.append(statement)
            return QueryResult()

    recorder = SetupRecorder()
    try:
        for unsafe in ('SELECT 1; COMMIT', 'CREATE TABLE z(a INT); END'):
            outcomes = recorder.setup([unsafe])
            require(outcomes and outcomes[0][1] is not None, 'PG setup accepted embedded transaction control')
        require(not recorder.executed, 'PG setup executed a statement that can commit its private schema')
    finally:
        recorder.close()
    r = PostgresReferenceRunner()
    try:
        require(str(r.engine_version).startswith('16.'), f'expected PostgreSQL 16, got {r.engine_version}')
        require(all(error is None for _, error in r.setup(ALL_SETUP)), 'PG reference setup failed')
        for op, expected in EXPECTED.items():
            result = r.run(f'SELECT v FROM t {op} SELECT v FROM u')
            require(result.ok and loose_bag(result.rows) == loose_bag(expected), f'PG/{op} differs from measured truth')
    finally:
        r.close()
    for op in EXPECTED:
        x = case('datafusion', f'SELECT v FROM t {op} SELECT v FROM u', None, ALL_SETUP)
        actual = judge(x, 'cross_dbms')
        label_is(actual, 'fail')
        require(actual.fail_kind == 'wrong_result', 'DF ALL defect must be wrong_result')
        require(set(actual.detail.get('voters', [])) >= {'duckdb', 'postgres', 'datafusion'}, 'no real three-engine quorum')
        require(actual.detail.get('outliers') == ['datafusion'], f'not the unique outlier: {actual.detail}')
        require(bool(actual.identity.behavior), 'missing behavior identity')
        require(actual.to_dict() == judge(x, 'cross_dbms').to_dict(), 'cross label unstable')
    x = case('datafusion', 'SELECT v FROM t EXCEPT ALL SELECT v FROM u', None, ALL_SETUP)
    label_is(judge(x, 'cross_dbms', reference_factories={'duckdb': constant_factory(EXPECTED['EXCEPT ALL'])}),
             'invalid', 'insufficient_engines')
    label_is(judge(x, 'cross_dbms', reference_factories={
        'duckdb': constant_factory([[1]]), 'postgres': constant_factory([[1]]), 'sqlite': constant_factory([])}),
        'invalid', 'non_unique_outlier')
    label_is(judge(x, 'cross_dbms', reference_factories={
        'duckdb': constant_factory([[1]]), 'postgres': constant_factory([[1]]), 'sqlite': constant_factory([[2]])}),
        'invalid', 'non_unique_outlier')
    try:
        judge(x, 'cross_dbms', reference_factories={'duckdb_old': constant_factory([])})
    except ValueError:
        pass
    else:
        raise AssertionError('a second version may not count as an independent engine')
    label_is(judge(case(query='SELECT a, b FROM t', predicate=None), 'cross_dbms'), 'pass')
    return 'PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected'


def check_version():
    from oracles.normalize import loose_bag
    recall = json.loads((ROOT / 'docs/recall_repros.json').read_text(encoding='utf-8'))['F2']
    x = case(query=recall['q'], predicate=None, setup=recall['setup'])
    actual = judge(x, 'version_differential')
    label_is(actual, 'fail')
    require(actual.fail_kind == 'wrong_result', 'F2 must be a result regression')
    detail = actual.detail
    require(detail.get('direction') == 'regression', f'wrong direction: {detail}')
    require(detail.get('old_version') == '1.1.3' and detail.get('new_version') == '1.5.5', 'wrong DuckDB versions')
    require(loose_bag(detail.get('old_rows', [])) == loose_bag([[10, 30], [20, 30]]), 'old result differs from pre-dispatch probe')
    require(loose_bag(detail.get('new_rows', [])) == loose_bag([[10, 10], [20, 20]]), 'new result differs from pre-dispatch probe')
    require(bool(detail.get('direction_evidence')), 'regression has no independent direction evidence')
    require(actual.to_dict() == judge(x, 'version_differential').to_dict(), 'version label unstable')
    witnessed = judge(x, 'version_differential', reference_factories={})
    label_is(witnessed, 'fail')
    require(witnessed.detail.get('direction') == 'regression' and witnessed.identity.switches,
            'F2 without references lacks independent sound-oracle identity')
    for engine, old in (('duckdb', '1.1.3'), ('datafusion', '50.0.0')):
        clean = judge(case(engine), 'version_differential')
        label_is(clean, 'pass')
        require(clean.detail.get('old_version') == old, f'{engine} old environment not used')
    for engine in ('duckdb', 'datafusion'):
        unknown = case(engine, query='SELECT version()', predicate=None, setup=())
        label_is(judge(unknown, 'version_differential', reference_factories={}), 'invalid', 'direction_unknown')
    require(not (ROOT / '.venvs/datafusion-50.0.0/Lib/site-packages/duckdb').exists(), 'old DF environment polluted with DuckDB')
    return 'F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid'


def check_matrix():
    from surprise.harness.contracts import LABELS
    from surprise.harness.oracles import IMPLEMENTED
    from surprise.harness.evaluate import evaluate
    from surprise.harness.ledger import Ledger
    from surprise.harness.manifest import build_manifest, verify_manifest
    require(set(IMPLEMENTED) == set(ORACLES), f'not all 7 oracles: {IMPLEMENTED}')
    with tempfile.TemporaryDirectory(prefix='s03-gate-') as temp:
        with Ledger(Path(temp) / 'ledger.sqlite') as ledger:
            manifest = build_manifest('s03-matrix')
            ledger.start_run('s03-matrix', manifest)
            for engine in ('duckdb', 'datafusion'):
                for oracle in ORACLES:
                    record = evaluate(case(engine), oracle, ledger=ledger, run_id='s03-matrix', purpose='s03-gate')
                    require(record.label.y in LABELS, 'non-ternary label')
                    require(record.label.invalid_reason != 'harness_error', f'{engine}/{oracle} hidden execution failure: {record.label.to_dict()}')
                    label_is(record.label, 'invalid', 'not_applicable') if engine == 'datafusion' and oracle == 'index_presence' else None
                    require(record.label.to_dict() == judge(case(engine), oracle).to_dict(), f'{engine}/{oracle}: evaluate != judge')
            require(ledger.count(run_id='s03-matrix') == 14, 'not exactly 14 records')
            require(not verify_manifest(manifest), 'manifest verification failed')
            hashed = set(manifest['harness']['files'])
            require({'targets/datafusion_runner.py', 'targets/sqlite_runner.py', 'oracles/equivalence.py',
                     'scripts/cross_engine.py'} <= hashed, 'new legacy dependencies not hashed')
    return '7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified'


CHECKS = {'registry': check_registry, 'local': check_local, 'cross': check_cross,
          'version': check_version, 'matrix': check_matrix}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', nargs='+', choices=list(CHECKS))
    args = parser.parse_args()
    names = args.only or list(CHECKS)
    passed = 0
    for name in names:
        try:
            detail = CHECKS[name]()
        except Exception as exc:
            message = f'{type(exc).__name__}: {exc}'.encode('ascii', 'backslashreplace').decode('ascii')
            print(f'[FAIL] {name}: {message}', flush=True)
        else:
            passed += 1
            print(f'[PASS] {name}: {detail}', flush=True)
    print(f'S03 GATE: {"PASS" if passed == len(names) else "FAIL"} ({passed}/{len(names)} groups passed)')
    return 0 if passed == len(names) else 1


if __name__ == '__main__':
    sys.exit(main())
