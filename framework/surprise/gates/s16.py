"""S16 gate: PostgreSQL 16.15 as a target (first harness unfreeze). Exit 0 = pass.

Groups (SESSIONS S16):
  instances  per-run PostgreSQL instances: 16.15 target and 15.19 old build from the pinned binaries,
             initialised like the reference, scram behind a passfile, the non-superuser target role,
             DSNs exported for the duration and restored, nothing left running afterwards
  runner     the harness target runner: a private schema per runner, autocommit, refused statements,
             no superuser powers, timeouts, a lost backend, setup SETs as session defaults
  registry   postgres is a target; DuckDB, DataFusion and SQLite are its references
  roles      the LLM roles read a pinned PostgreSQL 16.15 checkout (release notes, executor and
             optimizer sources) and know the dialect
  oracles    every oracle labels PostgreSQL cases with three values; native index presence and the
             15.19 version differential work
  cve        PG-F through the CVE pipeline in fresh processes: stable rerun, measured identity
  m1         the M1 table (real PG-F, injected failures, invalid and pass cases, pg_recall) through
             evaluate_final into the ledger; postgres/ gaps recorded
  seeds      the existing PostgreSQL seed corpus runs on the target
  replay     EXPERIMENT.md 8: the replay tool, a live sample of the old S8 long run, and the full
             2000-record replay recorded in s16_data
  phi        phi of PostgreSQL cases has a plan layer and is the same in two processes
  loop       the main loop on postgres starts, uses and removes its own instances, or reuses
             exported DSNs; the Hunter offers native index presence
  grid       two PostgreSQL cells on their own instances; the report scores recall against PG-F
  sqlancer   SQLancer's PostgreSQL mode: fixture logs classified and converted into PostgreSQL cases,
             then a live cell through the grid with the instance password hidden
  refreeze   the harness changed only in the allowed files and is frozen again
  scope      changes since the base tag stay in scope

PostgreSQL binaries: COEVO_PG_BIN / COEVO_PG_OLD_BIN or the
common checkout's .orch/pg16 and .orch/pg15 (see HANDOFF S16). Output is ASCII only.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from . import s16_cases as C
from .s06 import GateFailure, _ascii, require

FRAMEWORK = Path(__file__).resolve().parents[2]
REPO = FRAMEWORK.parent
DATA = Path(__file__).with_name("s16_data")
FROZEN = Path(__file__).with_name("s04_frozen.json")
WINDOWS = sys.platform == "win32"
_TMP_ROOT = Path(tempfile.gettempdir()) / "coevo-s16-gate"


# ---- helpers ------------------------------------------------------------------------------------

def git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=REPO, capture_output=True, timeout=300)
    if check:
        require(proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr.decode('utf-8', 'replace')[-300:]}")
    return proc.stdout.decode("utf-8", "replace")


def tmpdir(name: str) -> Path:
    path = _TMP_ROOT / name
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def clean_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() not in ("DEEPSEEK_API_KEY", "PUSHPLUS_TOKEN")}
    env.update(extra)
    return env


def py(argv: list[str], *, timeout: float, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *argv], cwd=FRAMEWORK, capture_output=True, text=True,
                          timeout=timeout, env=env or clean_env())


def expect_raises(kind: type[BaseException] | tuple, call: Callable[[], Any], what: str) -> BaseException:
    try:
        call()
    except kind as exc:
        return exc
    except Exception as exc:  # noqa: BLE001 - the wrong exception is the finding
        raise GateFailure(f"{what}: raised {type(exc).__name__}: {_ascii(exc)}") from exc
    raise GateFailure(f"{what}: no error raised")


@contextlib.contextmanager
def env_set(name: str, value: str | None) -> Iterator[None]:
    saved = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = saved


def pg_instance() -> Any:
    from surprise.experiments import pg_instance as P

    return P


@contextlib.contextmanager
def instances(name: str, *, old: bool = True) -> Iterator[dict[str, str]]:
    """Start this group's own target (and old) instance; the DSNs are exported meanwhile."""
    with pg_instance().running(tmpdir(name), old=old) as dsns:
        yield dsns


def runner(**kwargs: Any) -> Any:
    from surprise.harness.oracles.pg_target import PostgresTargetRunner

    return PostgresTargetRunner(**kwargs)


def rows(dsn: str, sql: str) -> list[tuple]:
    import psycopg2

    connection = psycopg2.connect(dsn)
    try:
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.execute(sql)
        return list(cursor.fetchall()) if cursor.description is not None else []
    finally:
        connection.close()


def reachable(dsn: str) -> bool:
    import psycopg2

    try:
        psycopg2.connect(dsn).close()
    except psycopg2.Error:
        return False
    return True


def case(name: str) -> Any:
    from surprise.harness.contracts import SqlCase

    setup, query, predicate = C.CASES[name]
    return SqlCase(engine="postgres", setup=tuple(setup), query=query, predicate=predicate)


def recall_case(name: str) -> Any:
    from seeds.pg_recall import PG_RECALL
    from surprise.harness.contracts import SqlCase

    entry = next(item for item in PG_RECALL if item["name"] == name)
    return SqlCase(engine="postgres", setup=tuple(entry["setup_sqls"]) + tuple(entry["pre_sqls"]),
                   query=entry["query"], predicate=None)


def kind_of(label: Any) -> str | None:
    return label.fail_kind if label.y == "fail" else label.invalid_reason


def show(label: Any) -> str:
    return _ascii(f"{label.y}/{kind_of(label)} switches={list(label.identity.switches)} "
                  f"detail={json.dumps(label.detail, sort_keys=True, default=str)[:400]} "
                  f"cve={json.dumps(label.cve, sort_keys=True, default=str)[:400]}")


def expect(label: Any, y: str, kind: str | None, where: str) -> None:
    require((label.y, kind_of(label)) == (y, kind), f"{where}: expected {y}/{kind}, got {show(label)}")


def stable_rerun(cve: dict[str, Any], where: str) -> None:
    from surprise.harness import constants

    rerun = cve.get("rerun") or {}
    attempts = constants.CVE_RERUN_ATTEMPTS
    require(rerun.get("status") == "ran" and rerun.get("attempts") in (attempts, attempts + constants.CVE_RERUN_EXTENDED)
            and rerun.get("reproduced") == rerun.get("attempts") and rerun.get("stable") is True,
            f"{where}: expected a stable rerun in fresh processes, got {rerun}")


def check_pgf_profile(label: Any, where: str) -> None:
    from surprise.harness.cve import behavior_shape

    expect(label, "fail", "wrong_result", where)
    require(tuple(label.identity.switches) == tuple(C.PGF_PROFILE["witness_switches"]),
            f"{where}: switches {list(label.identity.switches)}")
    require(behavior_shape(label.identity.behavior) == C.PGF_PROFILE["behavior_shape"],
            f"{where}: behavior {label.identity.behavior}")
    cve = label.cve
    stable_rerun(cve, where)
    profile = cve.get("profile") or {}
    require(profile.get("status") == "ran", f"{where}: tier 3 must run: {profile}")
    for key in ("fix_kind", "fix_set", "version_ladder", "witness_switches"):
        require(profile.get(key) == C.PGF_PROFILE[key], f"{where}: profile {key} {profile.get(key)!r}, "
                f"expected {C.PGF_PROFILE[key]!r}")
    require(C.PGF_PROFILE["plan_diff_has"] in (profile.get("plan_diff") or []),
            f"{where}: plan_diff {profile.get('plan_diff')}")


# ---- instances ----------------------------------------------------------------------------------

_INFO_KEYS = {"kind", "version", "port", "pid", "data_dir", "bin_dir", "log"}


def check_instances() -> str:
    P = pg_instance()
    for kind, version in (("target", C.TARGET_VERSION), ("old", C.OLD_VERSION)):
        found = Path(P.bin_dir(kind))
        exe = found / ("postgres.exe" if WINDOWS else "postgres")
        require(exe.is_file(), f"bin_dir({kind!r}) = {found} has no postgres executable")
        out = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=60).stdout
        require(version in out, f"{exe} --version: {out.strip()!r}, expected {version}")
        with env_set(C.BIN_ENV[kind], str(tmpdir(f"nowhere-{kind}"))):
            expect_raises(Exception, lambda kind=kind: P.bin_dir(kind), f"{C.BIN_ENV[kind]} pointing at an empty dir")
    require(P.KINDS == ("target", "old") and P.TARGET_ROLE == C.TARGET_ROLE
            and P.VERSIONS == {"target": C.TARGET_VERSION, "old": C.OLD_VERSION},
            f"pg_instance constants: {P.KINDS} {P.TARGET_ROLE} {P.VERSIONS}")

    root = tmpdir("instances")
    with env_set(C.TARGET_DSN_ENV, "s16-before"), env_set(C.OLD_DSN_ENV, None):
        with P.running(root) as dsns:
            require(set(dsns) == {"target", "old"}, f"running() yields {sorted(dsns)}")
            require(os.environ.get(C.TARGET_DSN_ENV) == dsns["target"] and os.environ.get(C.OLD_DSN_ENV) == dsns["old"],
                    "running() must export both DSNs while it runs")
            ports = set()
            for kind, version in (("target", C.TARGET_VERSION), ("old", C.OLD_VERSION)):
                dsn = dsns[kind]
                require("password" not in dsn.lower() and "passfile" in dsn.lower(),
                        f"{kind} DSN must name a passfile and carry no password")
                info_text = (root / kind / "instance.json").read_text(encoding="utf-8")
                info = json.loads(info_text)
                require(set(info) <= _INFO_KEYS and info.get("kind") == kind and info.get("version") == version
                        and isinstance(info.get("port"), int) and isinstance(info.get("pid"), int),
                        f"{kind} instance.json: {info}")
                ports.add(info["port"])
                got = rows(dsn, "SELECT current_user, current_setting('server_version')")[0]
                require(got == (C.TARGET_ROLE, version), f"{kind}: connected as {got}")
                for name, want in C.SETTINGS.items():
                    value = rows(dsn, f"SELECT current_setting('{name}')")[0][0]
                    require(value == want, f"{kind}: {name} = {value!r}, expected {want!r}")
                locale = rows(dsn, "SELECT datcollate, datctype FROM pg_database WHERE datname = current_database()")[0]
                require(tuple(locale) == C.DATABASE_LOCALE, f"{kind}: database locale {locale}")
                powers = rows(dsn, "SELECT rolsuper, rolcreaterole FROM pg_roles WHERE rolname = current_user")[0]
                require(tuple(powers) == (False, False), f"{kind}: the target role has {powers}")
                if not WINDOWS:
                    passfile = next(part.split("=", 1)[1] for part in dsn.split() if part.startswith("passfile="))
                    require(oct(Path(passfile).stat().st_mode & 0o777) == "0o600", f"{kind}: passfile mode")
            require(len(ports) == 2, f"target and old must listen on different ports: {ports}")
            other = tmpdir("instances-ensure")
            with P.ensure(other) as again:
                require(again.get("target") == dsns["target"], "ensure() must reuse exported DSNs")
            require(not any(other.iterdir()), "ensure() started an instance although DSNs were exported")
        require(os.environ.get(C.TARGET_DSN_ENV) == "s16-before" and C.OLD_DSN_ENV not in os.environ,
                "running() must restore the environment it found")
        for kind in ("target", "old"):
            require(not reachable(dsns[kind]), f"{kind} instance still accepts connections after running()")
            require(not (root / kind / "data").exists(), f"{kind} data directory left behind")

    leftover = tmpdir("instances-leftover")
    instance = P.PgInstance(leftover / "target", "target").start()
    require(instance.running and reachable(instance.dsn), "PgInstance.start() must leave a running server")
    stopped = P.stop_all(leftover)
    require(len(stopped) == 1 and not instance.running and not reachable(instance.dsn),
            f"stop_all() must stop the abandoned server: {stopped}")
    proc = py(["-m", "surprise.experiments.pg_instance", "check"], timeout=600)
    require(proc.returncode == 0 and C.TARGET_VERSION in proc.stdout and C.OLD_VERSION in proc.stdout,
            f"pg_instance check: exit {proc.returncode}: {_ascii((proc.stdout + proc.stderr)[-400:])}")
    return (f"16.15 and 15.19 from {P.bin_dir('target')} / {P.bin_dir('old')}; settings, locale and the "
            "non-superuser role as pinned; DSNs exported and restored; stop_all and the check CLI work")


# ---- runner -------------------------------------------------------------------------------------

def check_runner() -> str:
    from surprise.harness.oracles import pg_target as T

    require(T.TARGET_DSN_ENV == C.TARGET_DSN_ENV and T.OLD_DSN_ENV == C.OLD_DSN_ENV, "DSN variable names")
    with env_set(C.TARGET_DSN_ENV, None):
        error = expect_raises(ConnectionError, lambda: T.PostgresTargetRunner(), "a runner without a DSN")
        require(C.TARGET_DSN_ENV in str(error), f"the error must name {C.TARGET_DSN_ENV}: {error}")
    with instances("runner") as dsns:
        first, second, killer = runner(), runner(), runner()
        require("passfile" not in repr(first) and dsns["target"] not in repr(first), "repr must hide the DSN")
        outcomes = first.setup(list(C.T_SETUP))
        require([error for _sql, error in outcomes] == [None] * len(C.T_SETUP), f"setup: {outcomes}")
        require(first.engine_version == C.TARGET_VERSION, f"engine_version {first.engine_version!r}")
        result = first.run(C.T_QUERY)
        require(result.ok and result.rows == [[3, 4]], f"{C.T_QUERY}: {result.error or result.rows}")
        second.setup(["CREATE TABLE t(a INT, b INT)", "INSERT INTO t VALUES (9, 9)"])
        require(second.run("SELECT a FROM t").rows == [[9]] and first.run("SELECT count(*) FROM t").rows == [[3]],
                "two runners must not see each other's tables")
        schema = first.run("SELECT current_schema()").rows[0][0]
        require(schema.startswith("coevo_t_") and schema != second.run("SELECT current_schema()").rows[0][0],
                f"private schemas: {schema}")
        for sql in C.REFUSED:
            result = first.run(sql)
            require(not result.ok and str(result.error).startswith("NotApplicable"), f"{sql!r} must be refused: {result.error}")
        require(first.run("SELECT current_schema()").rows[0][0] == schema, "a refused statement changed the schema")
        refused = first.setup(["CREATE TABLE u(a INT)", "BEGIN"])
        require(refused[0][1] is None and str(refused[1][1]).startswith("NotApplicable"), f"setup refusal: {refused}")
        first.setup(list(C.T_SETUP))
        schema = first.run("SELECT current_schema()").rows[0][0]
        for sql in C.NOT_SUPERUSER:
            result = first.run(sql)
            low = str(result.error).lower()
            require(not result.ok and not low.startswith("notapplicable") and ("permission denied" in low or "superuser" in low),
                    f"{sql!r} must be refused by the server: {result.error}")
        started = time.monotonic()
        result = first.run(C.SLOW_QUERY, timeout_s=2.0)
        require(result.timed_out and time.monotonic() - started < 20, f"timeout: {result.error} after {time.monotonic() - started:.1f}s")
        require(first.run("SELECT 1").rows == [[1]], "the runner must be usable after a timeout")
        pid = first.backend_pid
        require(isinstance(pid, int), f"backend_pid {pid!r}")
        require(killer.run(f"SELECT pg_terminate_backend({pid})").rows == [[True]], "could not end the backend")
        lost = first.run("SELECT count(*) FROM t")
        require(not lost.ok and lost.is_internal_error, f"a lost backend is an internal error: {lost.error}")
        back = first.run("SELECT count(*) FROM t")
        require(back.ok and back.rows == [[3]] and first.run("SELECT current_schema()").rows[0][0] == schema,
                f"after reconnecting the same schema is used: {back.error or back.rows}")

        third = runner()
        third.setup(list(C.T_SETUP) + ["SET enable_hashjoin = off", "SET work_mem = '64kB'"])
        third.run("RESET enable_hashjoin")
        require(third.run("SHOW enable_hashjoin").rows == [["off"]], "RESET must return to the setup's SET")
        third.run("SET enable_hashjoin = on")
        third.run("RESET enable_hashjoin")
        require(third.run("SHOW enable_hashjoin").rows == [["off"]] and third.run("SHOW work_mem").rows == [["64kB"]],
                "setup SETs are the session defaults")
        third.setup(list(C.T_SETUP))
        require(third.run("SHOW enable_hashjoin").rows == [["on"]], "a new setup starts from the server defaults")
        fourth = runner()
        fourth.setup(["CREATE TEMP TABLE tt(a INT)", "INSERT INTO tt VALUES (1)", "SET enable_seqscan = off"])
        require(fourth.run("SELECT a FROM tt").rows == [[1]], "a setup with session-bound objects keeps its session")

        texts = []
        for _ in range(2):
            other = runner()
            texts.append(other.setup(["CREATE TABLE v(a INT)", "INSERT INTO v VALUES ('x')"])[1][1])
            other.close()
        require(texts[0] == texts[1] and texts[0] and "coevo_t_" not in texts[0],
                f"error text must be the same in every runner: {texts}")
        plan = first.explain_plan(C.T_QUERY)
        require(isinstance(plan, list) and plan and "Plan" in plan[0], f"explain_plan: {str(plan)[:200]}")
        for item in (first, second, third, fourth, killer):
            item.close()
            item.close()
        probe = runner()
        probe.setup([])
        left = probe.run(f"SELECT count(*) FROM pg_namespace WHERE nspname = '{schema}' OR nspname LIKE 'coevo\\_t\\_%'")
        require(left.ok and left.rows[0][0] == 1, f"close() must drop the schemas (only the probe's own is left): {left.rows}")
        probe.close()
        old = runner(env=C.OLD_DSN_ENV)
        require(old.engine_version == C.OLD_VERSION, f"old runner: {old.engine_version}")
        old.close()
    return ("private schemas, refused statements, no superuser powers, timeout, a lost backend, setup SETs as "
            "session defaults, stable error text, schemas dropped on close; old runner on 15.19")


# ---- registry -----------------------------------------------------------------------------------

def check_registry() -> str:
    from surprise.harness.oracles import judge
    from surprise.harness.oracles import registry as R
    from surprise.harness.oracles.cross_dbms import default_reference_factories
    from surprise.harness.oracles.pg_reference import PostgresReferenceRunner
    from surprise.harness.oracles.pg_target import PostgresTargetRunner

    require(R.TARGET_ENGINES == ("duckdb", "datafusion", "postgres"), f"TARGET_ENGINES {R.TARGET_ENGINES}")
    require(R.REFERENCE_ENGINES == ("duckdb", "datafusion", "sqlite", "postgres"), f"REFERENCE_ENGINES {R.REFERENCE_ENGINES}")
    with env_set(C.TARGET_DSN_ENV, None):
        error = expect_raises(ValueError, lambda: R.runner_factory_for("postgres"),
                              "runner_factory_for('postgres') without a target instance")
        require(C.TARGET_DSN_ENV in str(error), f"the error must name {C.TARGET_DSN_ENV}: {error}")
    R.validate_request(case("plain"), "tlp", R.make_options())
    expect_raises(ValueError, lambda: R.validate_options(
        R.make_options(reference_factories={"postgres": PostgresReferenceRunner}), target_engine="postgres"),
        "postgres as a reference of a postgres target")
    refs = sorted(default_reference_factories("postgres"))
    require(refs == ["datafusion", "duckdb", "sqlite"], f"references of postgres: {refs}")
    with instances("registry", old=False):
        require(R.runner_factory_for("postgres") is PostgresTargetRunner, "runner_factory_for('postgres') with an instance")
        tlp = judge(case("plain_pred"), "tlp")
        expect(tlp, "pass", None, "tlp on postgres")
        variant = judge(case("plain"), "plan_variant")
        expect(variant, "pass", None, "plan variant on postgres")
        require(variant.detail.get("variants_compared", 0) >= 20, f"PostgreSQL switch groups compared: {variant.detail}")
    return f"targets {R.TARGET_ENGINES}; references of postgres {refs}; tlp and plan variant judge a PostgreSQL case"


# ---- roles --------------------------------------------------------------------------------------

def _base_role_constants() -> dict[str, Any]:
    source = git("show", f"{C.BASE_TAG}:framework/surprise/roles/constants.py")
    namespace: dict[str, Any] = {"__name__": "s16_base_role_constants"}
    exec(compile(source, "base roles/constants.py", "exec"), namespace)  # noqa: S102 - our own file
    return namespace["as_dict"]()


def check_roles() -> str:
    from types import SimpleNamespace

    from surprise.roles import constants as RC
    from surprise.roles import open_sources
    from surprise.roles import source as S
    from surprise.roles import sources_map as M
    from surprise.roles.conjecturer import select_sources
    from surprise.roles.implementer import _DIALECT
    from surprise.roles.prior import prior_evidence

    have, base = RC.as_dict(), _base_role_constants()
    changed = sorted(name for name in set(base) | set(have) if have.get(name) != base.get(name))
    require(not changed, f"roles/constants.py must not change in S16: {changed}")
    require(M.EXTRA_SOURCE_DIRS == C.EXTRA_SOURCE_DIRS and M.EXTRA_SOURCE_COMMITS == C.EXTRA_SOURCE_COMMITS,
            f"extra source checkouts: {M.EXTRA_SOURCE_DIRS} {M.EXTRA_SOURCE_COMMITS}")
    require(sorted(open_sources()) == ["datafusion", "duckdb"], "open_sources() keeps DuckDB and DataFusion only")
    extra = S.open_extra_sources(("postgres",))
    require(sorted(extra) == ["postgres"] and extra["postgres"].commit == C.PG_SOURCE_COMMIT,
            f"open_extra_sources(('postgres',)): {sorted(extra)}")
    require(S.open_extra_sources(("duckdb",)) == {} and S.open_extra_sources(("duckdb", "datafusion")) == {},
            "no extra checkout for engines that do not need one")
    readers = S.readers_for(("postgres",))
    require(sorted(readers) == ["datafusion", "duckdb", "postgres"], f"readers_for(('postgres',)): {sorted(readers)}")
    require(sorted(S.readers_for(("duckdb",))) == ["datafusion", "duckdb"], "a DuckDB run reads what it read before")
    with env_set(RC.SOURCE_ROOT_ENV, str(tmpdir("roles-empty-root"))):
        require(S.open_extra_sources(("postgres",)) == {}, "a missing PostgreSQL checkout is left out, not an error")

    lines = prior_evidence(["postgres|plan_variant|join|unknown|unknown", "postgres|tlp|aggregate|unknown|unknown"], readers)
    require(lines, "prior evidence for PostgreSQL units is empty")
    prefix = f"EVIDENCE postgres {C.PG_RELEASE_NOTES}:"
    require(all(line.startswith(prefix) for line in lines), f"PostgreSQL evidence must come from the release notes: {lines[:3]}")
    require(prior_evidence(["postgres|plan_variant|join|unknown|unknown"], readers)
            == prior_evidence(["postgres|plan_variant|join|unknown|unknown"], readers), "prior evidence is deterministic")

    memo = select_sources("postgres", SimpleNamespace(interventions=("enable_memoize",)), None, readers)
    paths = sorted({snippet.path for snippet in memo})
    require(any(path in paths for path in C.PG_MEMOIZE_FILES), f"enable_memoize must reach {C.PG_MEMOIZE_FILES}: {paths}")
    joined = select_sources("postgres", SimpleNamespace(interventions=()), {"features": ["ast:join:inner", "ast:agg"]}, readers)
    require(joined and all(snippet.path.startswith("src/") for snippet in joined),
            f"feature rules must reach PostgreSQL sources: {[s.path for s in joined][:5]}")
    require("PostgreSQL" in _DIALECT.get("postgres", ""), f"implementer dialect for postgres: {_DIALECT.get('postgres')!r}")
    runtime = (FRAMEWORK / "surprise" / "roles" / "runtime.py").read_text(encoding="utf-8")
    require("readers_for(" in runtime, "roles/runtime.py must build its readers with readers_for(engines)")
    return (f"optional postgres checkout {C.PG_SOURCE_COMMIT[:12]} (roles constants unchanged); {len(lines)} "
            f"release-note evidence lines; memoize -> {paths}; dialect hint present")


# ---- oracles ------------------------------------------------------------------------------------

def check_oracles() -> str:
    from surprise.harness.contracts import LABELS, ORACLE_IDS
    from surprise.harness.oracles import judge

    seen: dict[str, set[str]] = {oracle: set() for oracle in ORACLE_IDS}
    with instances("oracles"):
        for oracle in ORACLE_IDS:
            for name in C.EVERY_ORACLE_CASES:
                label = judge(case(name), oracle)
                require(label.y in LABELS and label.invalid_reason != "harness_error",
                        f"{oracle} on {name}: {show(label)}")
                seen[oracle].add(label.y)
        index = judge(case("indexable"), "index_presence")
        expect(index, "pass", None, "index presence on an indexable query")
        compared = index.detail.get("index_variants_compared") or []
        require(len(compared) >= 4, f"native index variants compared: {index.detail}")
        expect(judge(case("no_table"), "index_presence"), "invalid", "not_applicable", "index presence without a table")
        version = judge(case("plain"), "version_differential")
        expect(version, "pass", None, "version differential on a plain query")
        require((version.detail.get("old_version"), version.detail.get("new_version")) == (C.OLD_VERSION, C.TARGET_VERSION),
                f"versions compared: {version.detail}")
        cross = judge(case("plain"), "cross_dbms")
        expect(cross, "pass", None, "cross-DBMS on a plain query")
        require(len(cross.detail.get("voters", [])) >= 3, f"cross-DBMS voters: {cross.detail.get('voters')}")
        variant = judge(case("PG-F"), "plan_variant")
        expect(variant, "fail", "wrong_result", "plan variant on PG-F")
        require(tuple(variant.identity.switches) == tuple(C.PGF_PROFILE["witness_switches"]),
                f"PG-F switch: {variant.identity.switches}")
    labelled = {oracle: sorted(values) for oracle, values in seen.items()}
    return f"labels per oracle on {len(C.EVERY_ORACLE_CASES)} cases: {labelled}; {len(compared)} index variants compared"


# ---- cve ----------------------------------------------------------------------------------------

def check_cve() -> str:
    from surprise.harness.cve import certify
    from surprise.harness.cve.certify import _single_thread_prelude

    require(_single_thread_prelude("postgres") == C.SINGLE_THREAD_PRELUDE,
            f"single-thread prelude for postgres: {_single_thread_prelude('postgres')}")
    with instances("cve"):
        first = certify(case("PG-F"), "plan_variant", diagnose=True)
        check_pgf_profile(first, "PG-F tier 3")
        again = certify(case("PG-F"), "plan_variant", diagnose=True)
        require(first.to_dict() == again.to_dict(), "tier 3 on PG-F twice must give equal labels")
        clean = certify(case("plain"), "plan_variant", diagnose=True)
        expect(clean, "pass", None, "a plain PostgreSQL case")
    profile = first.cve["profile"]
    return (f"PG-F: fail, rerun {first.cve['rerun']['reproduced']}/{first.cve['rerun']['attempts']} in fresh processes, "
            f"fix set {profile['fix_set']}, ladder {profile['version_ladder']}, plan diff has MEMOIZE")


# ---- m1 -----------------------------------------------------------------------------------------

def check_m1() -> str:
    from surprise.harness.contracts import LABELS
    from surprise.harness.evaluate import evaluate_final
    from surprise.harness.ledger import Ledger
    from surprise.harness.manifest import build_manifest

    from . import s16_fixtures as F

    run = "gate-s16-m1"
    counts = {label: 0 for label in LABELS}
    with instances("m1"), tempfile.TemporaryDirectory(prefix="s16-m1-") as tmp:
        manifest = build_manifest(run)
        environment = manifest["environment"]
        require(environment["engines"].get("postgres") == C.TARGET_VERSION
                and environment["old_engines"].get("postgres") == C.OLD_VERSION,
                f"manifest PostgreSQL versions: {environment['engines']} {environment['old_engines']}")
        with Ledger(Path(tmp) / "ledger.sqlite") as ledger:
            ledger.start_run(run, manifest)
            written = 0

            def final(sql_case: Any, oracle: str, **kwargs: Any) -> Any:
                nonlocal written
                record = evaluate_final(sql_case, oracle, ledger=ledger, run_id=run, purpose="m1", **kwargs)
                written += 1
                require(ledger.count(run_id=run) == written, f"{oracle}: one record per call")
                counts[record.label.y] += 1
                require(isinstance(record.label.cve, dict) and record.label.cve.get("schema") == 1,
                        f"{oracle}: CVE evidence missing")
                return record.label

            for name, oracle in C.CONFIRMED.items():
                check_pgf_profile(final(case(name), oracle, diagnose=True), f"M1 {name}")
            for name, (case_name, oracle, factory, kind) in C.INJECTED.items():
                label = final(case(case_name), oracle, runner_factory=getattr(F, factory))
                expect(label, "fail", kind, f"M1 injected {name}")
                stable_rerun(label.cve, f"M1 injected {name}")
                if oracle == "cross_dbms":
                    require(label.detail.get("outliers") == ["postgres"] and len(label.detail.get("voters", [])) >= 3,
                            f"{name}: the target must be the only outlier of three or more voters: {label.detail}")
                if oracle == "version_differential":
                    majority = (label.detail.get("direction_evidence") or {}).get("majority") or []
                    require(len(majority) >= 2 and label.detail.get("old_version") == C.OLD_VERSION,
                            f"{name}: the old rows need two engines behind them: {label.detail}")
            for (name, oracle), reason in C.INVALID.items():
                expect(final(case(name), oracle), "invalid", reason, f"M1 {name}/{oracle}")
            for name, oracle in C.PASS:
                expect(final(case(name), oracle), "pass", None, f"M1 {name}/{oracle}")
            for name in C.RECALL_PASS:
                expect(final(recall_case(name), "plan_variant"), "pass", None, f"M1 pg_recall {name}")
            require(ledger.label_counts(run_id=run) == counts,
                    f"ledger counts {ledger.label_counts(run_id=run)} != {counts}")
        with Ledger(Path(tmp) / "ledger.sqlite") as reopened:
            stored = reopened.records(run_id=run)
            require(len(stored) == written, "every record survives reopening the ledger")
    gaps = ", ".join(sorted(C.RECALL_GAPS))
    return (f"{written} final labels ({counts['fail']} fail, {counts['invalid']} invalid, {counts['pass']} pass); "
            f"postgres/ gaps recorded: {gaps}")


# ---- seeds --------------------------------------------------------------------------------------

def check_seeds() -> str:
    from seeds.store import SeedCorpus

    seeds = SeedCorpus.load(FRAMEWORK / "seeds" / "corpus.json").for_engine("postgres").seeds
    require(len(seeds) == C.PG_SEEDS, f"{len(seeds)} PostgreSQL seeds, expected {C.PG_SEEDS}")
    setups = queries = 0
    with instances("seeds", old=False):
        engine = runner()
        try:
            for seed in seeds:
                outcomes = engine.setup(list(seed.setup_sqls))
                if all(error is None for _sql, error in outcomes):
                    setups += 1
                    if engine.run(seed.query).ok:
                        queries += 1
        finally:
            engine.close()
    require(setups >= C.MIN_SEED_SETUPS_OK and queries >= C.MIN_SEED_QUERIES_OK,
            f"{setups} setups and {queries} queries ran; need {C.MIN_SEED_SETUPS_OK} and {C.MIN_SEED_QUERIES_OK}")
    return f"{len(seeds)} PostgreSQL seeds: {setups} setups and {queries} queries run on 16.15"


# ---- replay -------------------------------------------------------------------------------------

def check_replay() -> str:
    from surprise.harness.manifest import harness_hash

    evidence = DATA / C.REPLAY_EVIDENCE
    require(evidence.is_file(), f"the full replay record {evidence.name} is missing")
    full = json.loads(evidence.read_text(encoding="utf-8"))
    require(full.get("harness") == harness_hash()["hash"], "the recorded replay ran on a different harness")
    require(full.get("sampled") == C.REPLAY_FULL and full.get("different") == []
            and full.get("source", {}).get("ledger_sha256") == C.REPLAY_LEDGER_SHA256,
            f"full replay: sampled {full.get('sampled')}, {len(full.get('different') or [])} different, "
            f"source {full.get('source')}")
    from surprise.harness.manifest import file_digest

    run_dir = FRAMEWORK / C.REPLAY_RUN
    require(run_dir.is_dir(), f"{C.REPLAY_RUN} is missing on this machine")
    require(file_digest(run_dir / "ledger.sqlite") == C.REPLAY_LEDGER_SHA256,
            f"{C.REPLAY_RUN}/ledger.sqlite is not the long run pinned at {C.BASE_TAG}")
    out = tmpdir("replay") / "replay.json"
    proc = py(["-m", "surprise.metrics.replay", str(run_dir), "--sample", str(C.REPLAY_LIVE), "--seed", "16",
               "--out", str(out), "--workers", "2"], timeout=3600)
    require(proc.returncode == 0, f"replay exit {proc.returncode}: {_ascii((proc.stdout + proc.stderr)[-600:])}")
    live = json.loads(out.read_text(encoding="utf-8"))
    require(live.get("sampled") == C.REPLAY_LIVE and live.get("different") == [],
            f"live replay: {live.get('sampled')} sampled, different {str(live.get('different'))[:400]}")
    require(set(live.get("strata", {})) and all("|" in key for key in live["strata"]),
            f"strata are oracle|label: {list(live.get('strata', {}))[:5]}")
    return (f"full replay of {full['sampled']} records identical; live sample of {live['sampled']} identical "
            f"({len(live['strata'])} strata)")


# ---- phi ----------------------------------------------------------------------------------------

def check_phi() -> str:
    from surprise.features.extract import extract_isolated

    shown = {}
    with instances("phi", old=False):
        for name in C.PHI_CASES:
            first, second = extract_isolated(case(name)), extract_isolated(case(name))
            require(first.to_dict() == second.to_dict(), f"phi of {name} differs between two processes")
            require(first.engine == "postgres" and first.layers.get("plan") == "ok",
                    f"{name}: phi layers {dict(first.layers)}")
            shown[name] = len(first.features)
        pgf = extract_isolated(case("PG-F"))
        missing = [leaf for leaf in C.PGF_PLAN_LEAVES if leaf not in pgf.features]
        require(not missing, f"PG-F plan leaves missing {missing}: {[f for f in pgf.features if f.startswith('plan:')]}")
        plain = extract_isolated(case("plain_pred"))
        require(plain.layers.get("data") == "ok", f"plain_pred data layer {dict(plain.layers)}")
    return f"phi stable across processes for {sorted(shown)}; PG-F plan has {list(C.PGF_PLAN_LEAVES)}"


# ---- loop ---------------------------------------------------------------------------------------

def _loop_argv(out: Path) -> list[str]:
    return ["-m", "surprise.experiments.loop", "--out", str(out), "--seed", str(C.LOOP_SEED), "--engine", "postgres",
            "--max-experiments", str(C.LOOP_EXPERIMENTS)]


def check_loop() -> str:
    from surprise.harness.contracts import ORACLE_IDS, SqlCase
    from surprise.harness.ledger import Ledger
    from surprise.harness.manifest import verify_manifest
    from surprise.hunter.operators import oracle_options

    P = pg_instance()
    options = oracle_options(SqlCase(engine="postgres", setup=C.T_SETUP, query=C.T_QUERY), ORACLE_IDS)
    require(("index_presence", None) in options, f"the Hunter must offer native index presence on postgres: {options}")
    out = tmpdir("loop") / "run"
    env = clean_env()
    env.pop(C.TARGET_DSN_ENV, None)
    env.pop(C.OLD_DSN_ENV, None)
    proc = py(_loop_argv(out), timeout=3600, env=env)
    require(proc.returncode == 0, f"loop on postgres exited {proc.returncode}: {_ascii((proc.stdout + proc.stderr)[-800:])}")
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    require(report.get("experiments") == C.LOOP_EXPERIMENTS and report.get("engines") == ["postgres"],
            f"loop report: {report.get('experiments')} experiments on {report.get('engines')}")
    with Ledger(out / "ledger.sqlite") as ledger:
        run_id = ledger.run_ids()[0]
        records = list(ledger.records(run_id=run_id))
        manifest = ledger.run_manifest(run_id)
    require(all(record.case.engine == "postgres" for record in records), "every record is a PostgreSQL case")
    errors = sum(1 for record in records if record.label.invalid_reason == "harness_error")
    require(errors <= C.LOOP_MAX_HARNESS_ERROR * len(records), f"{errors} harness errors in {len(records)} records")
    labels = {record.label.y for record in records}
    require({"pass", "invalid"} <= labels, f"labels seen: {sorted(labels)}")
    environment = manifest.get("environment") or {}
    require((environment.get("engines") or {}).get("postgres") == C.TARGET_VERSION
            and (environment.get("old_engines") or {}).get("postgres") == C.OLD_VERSION,
            f"run manifest PostgreSQL versions: {environment.get('engines')} {environment.get('old_engines')}")
    require(verify_manifest(manifest) == [], "the run manifest verifies")
    info = json.loads((out / "pg" / "target" / "instance.json").read_text(encoding="utf-8"))
    require(info.get("version") == C.TARGET_VERSION, f"the loop's own instance: {info}")
    require(not (out / "pg" / "target" / "data").exists() and not (out / "pg" / "old" / "data").exists(),
            "the loop must remove its instances' data directories")
    require(P.stop_all(out) == [], "a PostgreSQL server under the run directory is still running")

    reused = tmpdir("loop-reuse") / "run"
    with instances("loop-dsn"):
        proc = py(_loop_argv(reused), timeout=3600, env=clean_env())
    require(proc.returncode == 0 and not (reused / "pg").exists(),
            f"with DSNs exported the loop must use them and start nothing: exit {proc.returncode}")
    oracles = sorted({record.label.oracle for record in records})
    return (f"{len(records)} experiments on postgres ({sorted(labels)}, oracles {oracles}, {errors} harness errors); "
            "own instances started and removed; exported DSNs reused")


# ---- grid and report ----------------------------------------------------------------------------

def _known_pg(tmp: Path) -> Path:
    out = tmp / "known_pg.json"
    with instances("known"):
        proc = py(["-m", "surprise.metrics.recall", "known", "--cases", str(DATA / C.KNOWN_CASES), "--out", str(out)],
                  timeout=3600)
    require(proc.returncode == 0, f"recall known on PG-F: {_ascii((proc.stdout + proc.stderr)[-600:])}")
    known = json.loads(out.read_text(encoding="utf-8"))
    item = known["items"][0]
    require(item["y"] == "fail" and item["key"] == C.PGF_KEY and known["engines"].get("postgres") == C.TARGET_VERSION,
            f"known PG-F: {item} engines {known['engines']}")
    return out


def check_grid() -> str:
    P = pg_instance()
    tmp = tmpdir("grid")
    known = _known_pg(tmp)
    raw = {"schema": 1, "name": "s16-pg", "budget": {"minutes": C.GRID_MINUTES}, "seeds": list(C.GRID_SEEDS),
           "concurrency": 2, "reference": "nollm", "known": str(known),
           "arms": [{"name": "nollm", "kind": "surprise", "engines": ["postgres"]}]}
    cfg = tmp / "grid.json"
    cfg.write_text(json.dumps(raw), encoding="utf-8")
    out = tmp / "out"
    env = clean_env()
    env.pop(C.TARGET_DSN_ENV, None)
    env.pop(C.OLD_DSN_ENV, None)
    proc = py(["-m", "surprise.experiments.grid", "run", str(cfg), "--out", str(out)], timeout=3600, env=env)
    require(proc.returncode == 0, f"PostgreSQL grid exited {proc.returncode}: {_ascii((proc.stdout + proc.stderr)[-600:])}")
    ports = set()
    for seed in C.GRID_SEEDS:
        cell = out / "cells" / "nollm" / f"s{seed}-r0"
        info = json.loads((cell / "cell.json").read_text(encoding="utf-8"))
        require(info.get("status") == "done" and info.get("returncode") == 0, f"cell s{seed}: {info.get('status')}")
        instance = json.loads((cell / "pg" / "target" / "instance.json").read_text(encoding="utf-8"))
        ports.add(instance["port"])
    require(len(ports) == len(C.GRID_SEEDS), f"each cell needs its own instance: ports {ports}")
    require(P.stop_all(out) == [], "a PostgreSQL server under the grid directory is still running")
    proc = py(["-m", "surprise.metrics.report", str(out)], timeout=1800)
    require(proc.returncode == 0, f"report on the PostgreSQL grid: {_ascii((proc.stdout + proc.stderr)[-600:])}")
    report = json.loads((out / "report" / "report.json").read_text(encoding="utf-8"))
    cells = report["arms"]["nollm"]["cells"]
    require(sorted(cells) == [f"nollm/s{seed}-r0" for seed in C.GRID_SEEDS], f"report cells {cells}")
    recall = report["rq6"]["arms"]["nollm"]["recall"]
    require(recall.get("n") == len(C.GRID_SEEDS), f"recall must be scored per PostgreSQL cell against PG-F: {recall}")
    return f"two PostgreSQL cells done on their own instances (ports {sorted(ports)}); report with recall against PG-F"


# ---- sqlancer -----------------------------------------------------------------------------------

def check_sqlancer() -> str:
    from surprise.harness.ledger import Ledger

    P = pg_instance()
    tmp = tmpdir("sqlancer")
    logs = tmp / "logs"
    logs.mkdir()
    for name in C.SQLANCER_FIXTURES:
        text = (DATA / "sqlancer" / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        (logs / name).write_text(text, encoding="utf-8", newline="\n")
    out = tmp / "replay"
    env = clean_env()
    env.pop(C.TARGET_DSN_ENV, None)
    env.pop(C.OLD_DSN_ENV, None)
    proc = py(["-m", "surprise.baselines.sqlancer_run", "--out", str(out), "--seed", "7", "--engine", "postgres",
               "--replay-logs", str(logs)], timeout=1800, env=env)
    require(proc.returncode == 0, f"replay of the PostgreSQL SQLancer fixtures: {_ascii((proc.stdout + proc.stderr)[-800:])}")
    rows = {Path(row["log"]).name: row for row in
            (json.loads(line) for line in (out / "sqlancer" / "reports.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())}
    for name, spec in C.SQLANCER_FIXTURES.items():
        row = rows.get(name)
        require(row is not None, f"reports.jsonl has no line for {name}")
        for key, value in spec.items():
            require(row.get(key) == value, f"{name}: {key} is {row.get(key)!r}, expected {value!r}")
    with Ledger(out / "ledger.sqlite") as ledger:
        run_id = ledger.run_ids()[0]
        records = list(ledger.records(run_id=run_id))
        manifest = ledger.run_manifest(run_id)
    require(manifest.get("baseline") == "sqlancer"
            and (manifest.get("environment", {}).get("engines") or {}).get("postgres") == C.TARGET_VERSION,
            f"replay manifest: baseline {manifest.get('baseline')!r}, engines {manifest.get('environment', {}).get('engines')}")
    by_id = {record.record_id: record for record in records}
    for name, want in C.SQLANCER_CASES.items():
        record = by_id.get(rows[name].get("record_id"))
        require(record is not None, f"{name}: no ledger record")
        require(record.case.to_dict() == want, f"{name}: converted case {record.case.to_dict()}")
        require(record.label.y == "pass" and record.label.invalid_reason != "harness_error",
                f"{name}: a PostgreSQL case without a defect must pass, got {record.label.y}/{record.label.invalid_reason}")
    require(P.stop_all(out) == [] and not (out / "pg" / "target" / "data").exists(), "the replay left an instance behind")

    live = tmp / "live"
    raw = {"schema": 1, "name": "s16-sqlancer", "budget": {"minutes": C.SQLANCER_LIVE_MINUTES}, "seeds": [7],
           "arms": [{"name": "sqlancer", "kind": "sqlancer", "engine": "postgres", "run": True}]}
    cfg = tmp / "live.json"
    cfg.write_text(json.dumps(raw), encoding="utf-8")
    proc = py(["-m", "surprise.experiments.grid", "run", str(cfg), "--out", str(live)],
              timeout=C.SQLANCER_LIVE_MINUTES * 60 + 1800, env=env)
    require(proc.returncode == 0, f"live SQLancer grid on postgres exited {proc.returncode}: {_ascii(proc.stderr[-600:])}")
    cell = live / "cells" / "sqlancer" / "s7-r0"
    info = json.loads((cell / "cell.json").read_text(encoding="utf-8"))
    require(info.get("status") == "done" and info.get("killed") is False, f"live cell: {info.get('status')} {info.get('killed')}")
    report = json.loads((cell / "report.json").read_text(encoding="utf-8"))
    stats = report.get("sqlancer") or {}
    require(report.get("status") == "budget_minutes", f"live status {report.get('status')!r}")
    require(isinstance(report.get("executions"), int) and report["executions"] >= C.SQLANCER_MIN_EXECUTIONS,
            f"SQLancer executed {report.get('executions')} queries on postgres")
    require(C.PG_JDBC in (stats.get("jdbc") or []), f"JDBC drivers {stats.get('jdbc')}")
    command = stats.get("command") or []
    require("--password" in command and command[command.index("--password") + 1] == "<hidden>",
            "the stored SQLancer command must hide the password")
    require(P.stop_all(live) == [], "a PostgreSQL server under the SQLancer grid is still running")
    proc = py(["-m", "surprise.metrics.report", str(live)], timeout=1800)
    require(proc.returncode == 0, f"report on the SQLancer PostgreSQL grid: {_ascii(proc.stderr[-600:])}")
    return (f"{len(C.SQLANCER_FIXTURES)} PostgreSQL fixtures classified, two converted and judged pass; live: "
            f"{report['executions']} queries, {stats.get('reports')} reports, password hidden")


# ---- refreeze -----------------------------------------------------------------------------------

def check_refreeze() -> str:
    from surprise.harness import constants
    from surprise.harness.manifest import verify_manifest

    changed = sorted({p for p in git("diff", "--name-only", C.BASE_TAG, "--", "framework/surprise/harness").split("\n") if p})
    untracked = sorted({p for p in git("ls-files", "--others", "--exclude-standard", "--",
                                       "framework/surprise/harness").split("\n") if p})
    require(set(changed) <= set(C.HARNESS_CHANGED) and not untracked,
            f"harness changes outside the unfreeze: {sorted(set(changed) - set(C.HARNESS_CHANGED))} untracked {untracked}")
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    problems = verify_manifest(frozen)
    require(problems == [], f"the harness is re-frozen (gates/s04_frozen.json): {problems[:4]}")
    base = json.loads(git("show", f"{C.BASE_TAG}:framework/surprise/gates/s04_frozen.json"))
    added = sorted(set(frozen["harness"]["files"]) - set(base["harness"]["files"]))
    require(added == ["surprise/harness/oracles/pg_target.py"] and set(base["harness"]["files"]) <= set(frozen["harness"]["files"]),
            f"files added to the frozen list: {added}")
    require(frozen.get("constants") == base.get("constants") == constants.as_dict(), "the harness constants are unchanged")
    environment = frozen.get("environment") or {}
    require((environment.get("engines") or {}).get("postgres") == C.TARGET_VERSION
            and (environment.get("old_engines") or {}).get("postgres") == C.OLD_VERSION,
            f"the frozen manifest must record PostgreSQL {C.TARGET_VERSION} and {C.OLD_VERSION}")
    return (f"{len(changed)} harness files changed, all in the unfreeze; re-frozen ({len(frozen['harness']['files'])} files, "
            f"hash {frozen['harness']['hash'][:12]}); constants unchanged")


# ---- scope --------------------------------------------------------------------------------------

def check_scope() -> str:
    tags = git("tag", "--list", C.DONE_TAG).split()
    if C.DONE_TAG in tags:
        changed = git("diff", "--name-only", C.BASE_TAG, C.DONE_TAG).split("\n")
        frozen = git("diff", "--name-only", C.BASE_TAG, C.DONE_TAG, "--", *C.FROZEN_PATHS).split("\n")
        where = f"{C.BASE_TAG}..{C.DONE_TAG}"
    else:
        changed = git("diff", "--name-only", C.BASE_TAG).split("\n")
        changed += git("ls-files", "--others", "--exclude-standard").split("\n")
        frozen = git("diff", "--name-only", C.BASE_TAG, "--", *C.FROZEN_PATHS).split("\n")
        where = f"{C.BASE_TAG}..work tree"
    changed = sorted({path.strip() for path in changed if path.strip()})
    frozen = sorted({path.strip() for path in frozen if path.strip()} - set(C.HARNESS_CHANGED))
    require(not frozen, f"frozen paths changed ({where}): {frozen[:10]}")
    outside = [path for path in changed if not any(path.startswith(prefix) for prefix in C.ALLOWED_CHANGES)]
    require(not outside, f"changes outside S16 scope ({where}): {outside[:10]}")
    return f"{len(changed)} paths changed ({where}), all in scope; harness changed only in the unfreeze"


GROUPS: dict[str, Callable[[], str]] = {
    "instances": check_instances,
    "runner": check_runner,
    "registry": check_registry,
    "roles": check_roles,
    "oracles": check_oracles,
    "cve": check_cve,
    "m1": check_m1,
    "seeds": check_seeds,
    "replay": check_replay,
    "phi": check_phi,
    "loop": check_loop,
    "grid": check_grid,
    "sqlancer": check_sqlancer,
    "refreeze": check_refreeze,
    "scope": check_scope,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S16 gate (PostgreSQL target)")
    parser.add_argument("--only", nargs="+", choices=list(GROUPS), metavar="GROUP")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(FRAMEWORK))
    selected = args.only or list(GROUPS)
    failed = 0
    for name in selected:
        started = time.monotonic()
        try:
            detail = GROUPS[name]()
        except GateFailure as exc:
            failed += 1
            print(f"[FAIL] {name}: {_ascii(exc)}", flush=True)
        except Exception as exc:  # noqa: BLE001 - a crash in a check is a failure, reported with its type
            failed += 1
            print(f"[FAIL] {name}: {type(exc).__name__}: {_ascii(exc)}", flush=True)
        else:
            print(f"[PASS] {name}: {_ascii(detail)} ({time.monotonic() - started:.0f}s)", flush=True)
    passed = len(selected) - failed
    label = "" if not args.only else f" [only: {', '.join(selected)}]"
    print(f"S16 GATE{label}: {'PASS' if failed == 0 else 'FAIL'} ({passed}/{len(selected)} groups passed)", flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
