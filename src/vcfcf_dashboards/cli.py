"""CLI: validate / package / sync / delete dashboards and view definitions."""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import requests

from vcfcf_common._profile_cli import add_profile_arg, validate_profile_arg, resolve_profile_from_args
from vcfcf_supermetrics.client import VCFOpsClient, VCFOpsError

from .client import (
    DASHBOARD_CONTENT_TYPES,
    all_skipped_content_types,
    check_dashboard_materialization,
    discover_marker_filename,
    get_current_user,
    import_content_zip,
)
from .id_guard import check_dashboard_id_stability
from .loader import (
    DashboardValidationError,
    check_dashboard_navigations,
    load_all,
    split_navigation_targets,
)
from .packager import build_import_zip
from . import sm_columns
from .summary_bind import WAIT_DEFAULT_S, WAIT_MAX_S, WAIT_POLL_S, bind_summary
from .ui_client import UIClientError, VCFOpsUIClient

DEFAULT_VIEWS = Path("content/views")
DEFAULT_DASHBOARDS = Path("content/dashboards")
DEFAULT_SUPERMETRICS = Path("content/supermetrics")


def _load(args) -> tuple[list, list]:
    return load_all(Path(args.views_dir), Path(args.dashboards_dir))


def _has_navigations(dashboards: list) -> bool:
    return any(w.navigations for d in dashboards for w in d.widgets)


def _navigation_corpus(
    dashboards: list, dashboards_dir: Path, mint: bool = False,
) -> "tuple[list, list[str]]":
    """Every dashboard a ``navigations: - dashboard:`` name may resolve to,
    plus the paths of dashboard YAMLs that failed to load.

    The set is the loaded ``dashboards``, plus ``content/dashboards/`` (always,
    even when ``--dashboards-dir`` points somewhere else, so a subset does
    not lose its siblings), plus every ``third_party/*/dashboards/`` YAML.
    Paths are relative to the working directory, like the rest of this CLI.
    Duplicates are harmless: resolution de-duplicates by name and id.

    ``mint`` uses the minting loader (validate, which already mints ids into
    third-party YAML in its membership pass); package and sync use the core
    loader with no minting so they never write a file. A YAML that fails to
    load is returned in the second list: its own validation reports the
    failure, and an unresolved-target error names it, since the target may
    be one of them.
    """
    corpus = list(dashboards)
    unloadable: list[str] = []
    dirs: list[Path] = []
    try:
        loaded_dir = dashboards_dir.resolve()
    except OSError:
        loaded_dir = dashboards_dir
    if DEFAULT_DASHBOARDS.is_dir() and DEFAULT_DASHBOARDS.resolve() != loaded_dir:
        dirs.append(DEFAULT_DASHBOARDS)
    third_party = Path("third_party")
    if third_party.is_dir():
        dirs.extend(
            proj / "dashboards" for proj in sorted(third_party.iterdir())
            if (proj / "dashboards").is_dir()
        )
    if not dirs:
        return corpus, unloadable
    if mint:
        from .loader import load_dashboard as _load_one
    else:
        from vcfcf_core.dashboards.loader import load_dashboard as _load_one
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for dash_dir in dirs:
            for dp in sorted(dash_dir.rglob("*.y*ml")):
                try:
                    corpus.append(_load_one(dp, enforce_framework_prefix=False, default_name_path=""))
                except Exception:
                    unloadable.append(str(dp))
    return corpus, unloadable


def _report_navigation_errors(sources: list, corpus: list, unloadable: "list[str] | None" = None) -> int:
    """Print one INVALID line per unresolved navigation reference; 1 if any."""
    errors = check_dashboard_navigations(sources, corpus, unloadable=unloadable)
    for msg in errors:
        print(f"INVALID: {msg}", file=sys.stderr)
    return 1 if errors else 0


def _check_import_targets(dashboards: list, allow_outside: bool) -> int:
    """Package / sync: the import zip creates exactly ``dashboards``.

    Every ``dashboard:`` target not among them and every ``dashboard_id``
    target is printed as a ``PREREQUISITE:`` line (it must already exist on
    the instance, or the jump goes nowhere and the product says nothing).
    A named target outside the import fails the command unless the operator
    passed ``--allow-external-navigation-targets``; ``dashboard_id`` targets
    are external by definition and never fail. Returns 1 on failure.
    """
    outside, external = split_navigation_targets(dashboards)
    for line in outside + external:
        print(f"PREREQUISITE: {line}", file=sys.stderr)
    if outside and not allow_outside:
        print(
            f"INVALID: {len(outside)} navigation target(s) are repo dashboards this "
            f"import does not carry. Include them (widen --dashboards-dir), or pass "
            f"--allow-external-navigation-targets once they are installed on the "
            f"target instance.",
            file=sys.stderr,
        )
        return 1
    return 0


def _resolve_import_navigations(args, dashboards: list) -> "tuple[int, list | None]":
    """Package / sync preamble: ``(rc, known_dashboards)``. Reads nothing and
    returns ``(0, None)`` when no dashboard declares navigations."""
    if not _has_navigations(dashboards):
        return 0, None
    known, unloadable = _navigation_corpus(dashboards, Path(args.dashboards_dir))
    if _report_navigation_errors(dashboards, known, unloadable):
        return 1, None
    allow = getattr(args, "allow_external_navigation_targets", False)
    return _check_import_targets(dashboards, allow), known


_TIME_WINDOW_WARNING_PREFIX = "view "
_TIME_WINDOW_WARNING_FRAGMENT = "no time_window is set"


def _is_time_window_warning(msg: str) -> bool:
    """Return True if the warning message is the aggregating-column-no-window warning."""
    return _TIME_WINDOW_WARNING_FRAGMENT in str(msg)


def _extract_view_name_from_time_window_warning(msg: str) -> str:
    """Extract the view name from a time_window warning message string.

    The message format is:
        view '<name>': one or more columns use an aggregating ...
    Returns the name between the first pair of single-quotes, or '' on parse failure.
    """
    s = str(msg)
    start = s.find("'")
    if start == -1:
        return ""
    end = s.find("'", start + 1)
    if end == -1:
        return ""
    return s[start + 1:end]


def cmd_validate(args) -> int:
    validate_profile_arg(args)  # validate --profile name if supplied; exits on unknown profile
    # Determine whether this is a full-corpus validate (no explicit path overrides).
    # Only the full-corpus path does dashboard-embedding suppression of the
    # time_window warning, single-file / explicit-path invocations keep the
    # warning live since there is no dashboard context to consult.
    using_defaults = (
        args.views_dir == str(DEFAULT_VIEWS)
        and args.dashboards_dir == str(DEFAULT_DASHBOARDS)
    )

    if using_defaults:
        # Full-corpus validate: capture time_window warnings during loading so
        # we can suppress them for dashboard-embedded views after the full
        # corpus (including third-party dashboards) is loaded.
        captured_warnings: list = []
        with warnings.catch_warnings(record=True) as _w:
            warnings.simplefilter("always")
            try:
                views, dashboards = _load(args)
            except DashboardValidationError as e:
                print(f"INVALID: {e}", file=sys.stderr)
                return 1
            # Collect all captured warnings; separate time_window ones for
            # deferred re-emit after we know the embedded set.
            for w in _w:
                captured_warnings.append(w)
    else:
        # Single-file / explicit-path validate: let warnings flow normally.
        try:
            views, dashboards = _load(args)
        except DashboardValidationError as e:
            print(f"INVALID: {e}", file=sys.stderr)
            return 1

    print(f"OK: {len(views)} view definition(s), {len(dashboards)} dashboard(s) valid")
    for v in views:
        print(f"  view       {v.id}  {v.name}")
    for d in dashboards:
        print(f"  dashboard  {d.id}  {d.name}")

    rc = 0

    # Dashboard Navigation targets resolve by exact name against every
    # dashboard in the repo (the loaded set, content/dashboards/ and
    # third_party/*/dashboards/). A full-corpus validate checks third-party
    # dashboards as sources too; an explicit-path validate checks the
    # loaded dashboards.
    nav_corpus, nav_unloadable = _navigation_corpus(
        dashboards, Path(args.dashboards_dir), mint=using_defaults,
    )
    nav_sources = nav_corpus if using_defaults else dashboards
    rc |= _report_navigation_errors(nav_sources, nav_corpus, nav_unloadable)

    # supermetric:"<name>" columns bind the way package / sync / build bind
    # them (issue #270, review W2), so validate (RULE-005) fails on what they
    # would fail on.  Third-party views are checked below with the rest of
    # the full-corpus pass; pak views stay with validate-sdk.
    sm_corpus = sm_columns.load_sm_corpus()
    rc |= _report_column_problems(views, sm_corpus)

    # Issue #113 identity guard: dashboard import identity is the NAME, so a
    # changed id: under an unchanged name: silently orphans the previously
    # installed UUID. Compare against the last committed version (git HEAD).
    guard_errors, guard_warnings = check_dashboard_id_stability(
        Path(args.dashboards_dir), baseline=args.id_guard_baseline
    )
    for msg in guard_warnings:
        print(f"WARNING: {msg}", file=sys.stderr)
    if guard_errors:
        for msg in guard_errors:
            print(f"ID-STABILITY: {msg}", file=sys.stderr)
        rc = 1

    if using_defaults:
        try:
            from vcfcf_packaging.project import check_slug_uniqueness, check_project_membership
        except ImportError:
            # vcfcf_packaging not available, re-emit captured warnings and exit
            _replay_non_time_window_warnings(captured_warnings)
            _replay_time_window_warnings_for_standalone_views(captured_warnings, dashboards)
            return rc  # vcfcf_packaging not available, skip checks

        # Slug uniqueness for views and dashboards
        for content_type, default_dir in (
            ("views", DEFAULT_VIEWS),
            ("dashboards", DEFAULT_DASHBOARDS),
        ):
            slug_errors = check_slug_uniqueness(
                content_type=content_type,
                content_type_dir=default_dir,
            )
            if slug_errors:
                for err in slug_errors:
                    print(f"SLUG-COLLISION: {err}", file=sys.stderr)
                rc = 1

        # Project-membership boundary check.
        # Build a full cross-provenance corpus for the dep walker:
        # factory-native content (already loaded) + all third-party content.
        # Use separate lists so the printed output above is unaffected.
        all_views_corpus = list(views)
        all_dashboards_corpus = list(dashboards)
        all_sms: list = []
        all_cgs: list = []

        _third_party = Path("third_party")
        if _third_party.exists():
            try:
                from vcfcf_dashboards.loader import (
                    load_view as _load_view,
                    load_dashboard as _load_dash,
                )
                with warnings.catch_warnings(record=True) as _w2:
                    warnings.simplefilter("always")
                    for _proj_dir in sorted(_third_party.iterdir()):
                        if not _proj_dir.is_dir():
                            continue
                        _tp_views_dir = _proj_dir / "views"
                        if _tp_views_dir.exists():
                            for _vp in sorted(_tp_views_dir.rglob("*.y*ml")):
                                try:
                                    all_views_corpus.append(
                                        _load_view(_vp, enforce_framework_prefix=False)
                                    )
                                except Exception:
                                    pass
                        _tp_dash_dir = _proj_dir / "dashboards"
                        if _tp_dash_dir.exists():
                            for _dp in sorted(_tp_dash_dir.rglob("*.y*ml")):
                                try:
                                    all_dashboards_corpus.append(
                                        _load_dash(
                                            _dp,
                                            enforce_framework_prefix=False,
                                            default_name_path="",
                                        )
                                    )
                                except Exception:
                                    pass
                    captured_warnings.extend(_w2)
            except ImportError:
                pass

            try:
                from vcfcf_supermetrics.loader import load_dir as _sm_load_dir
                for _proj_dir in sorted(_third_party.iterdir()):
                    if not _proj_dir.is_dir():
                        continue
                    _tp_sm_dir = _proj_dir / "supermetrics"
                    if _tp_sm_dir.exists():
                        try:
                            all_sms.extend(
                                _sm_load_dir(_tp_sm_dir, enforce_framework_prefix=False)
                            )
                        except Exception:
                            pass
            except ImportError:
                pass

            try:
                from vcfcf_customgroups.loader import load_dir as _cg_load_dir
                for _proj_dir in sorted(_third_party.iterdir()):
                    if not _proj_dir.is_dir():
                        continue
                    _tp_cg_dir = _proj_dir / "customgroups"
                    if _tp_cg_dir.exists():
                        try:
                            all_cgs.extend(
                                _cg_load_dir(_tp_cg_dir, enforce_framework_prefix=False)
                            )
                        except Exception:
                            pass
            except ImportError:
                pass

        # Also include factory-native SMs and CGs in the corpus
        try:
            from vcfcf_supermetrics.loader import load_dir as _sm_load_dir
            _sm_dir = Path("content/supermetrics")
            if _sm_dir.exists():
                try:
                    all_sms.extend(_sm_load_dir(_sm_dir))
                except Exception:
                    pass
        except ImportError:
            pass

        try:
            from vcfcf_customgroups.loader import load_dir as _cg_load_dir
            _cg_dir = Path("content/customgroups")
            if _cg_dir.exists():
                try:
                    all_cgs.extend(_cg_load_dir(_cg_dir))
                except Exception:
                    pass
        except ImportError:
            pass

        rc |= _report_column_problems(all_views_corpus[len(views):], sm_corpus)

        membership_errors = check_project_membership(
            dashboards=all_dashboards_corpus,
            all_views=all_views_corpus,
            all_supermetrics=all_sms,
            all_customgroups=all_cgs,
        )
        if membership_errors:
            for err in membership_errors:
                print(f"PROJECT-BOUNDARY: {err}", file=sys.stderr)
            rc = 1

        # Now that all dashboards are loaded, build the embedded-view set and
        # selectively re-emit time_window warnings for non-embedded views.
        _replay_non_time_window_warnings(captured_warnings)
        _replay_time_window_warnings_for_standalone_views(captured_warnings, all_dashboards_corpus)

    return rc


def _report_column_problems(views: list, corpus) -> int:
    """Validate's ``supermetric:"<name>"`` column check: one line per column
    that does not bind to exactly one SM.  Unresolved, ambiguous and
    failed-to-load sets are ``SM-COLUMN:`` errors (rc 1); an SM with no id
    yet is a WARNING only, since ``vcfcf_supermetrics validate`` mints it
    and the chain order should not decide the result."""
    rc = 0
    for kind, msg in sm_columns.column_errors(views, corpus):
        if kind == "unusable":
            print(f"WARNING: {msg}", file=sys.stderr)
        else:
            print(f"SM-COLUMN: {msg}", file=sys.stderr)
            rc = 1
    return rc


def _replay_non_time_window_warnings(captured: list) -> None:
    """Re-emit all captured warnings that are NOT the time_window advisory."""
    for w in captured:
        if not (issubclass(w.category, UserWarning) and _is_time_window_warning(str(w.message))):
            warnings.warn_explicit(
                message=w.message,
                category=w.category,
                filename=w.filename,
                lineno=w.lineno,
                source=w.source,
            )


def _replay_time_window_warnings_for_standalone_views(captured: list, all_dashboards: list) -> None:
    """Re-emit time_window warnings only for views NOT embedded in any dashboard.

    Uses extract_view_names_from_dashboards to build the embedded set, then
    suppresses the warning for views whose names appear in that set.
    """
    try:
        from vcfcf_common.dep_walker import extract_view_names_from_dashboards
    except ImportError:
        # dep_walker unavailable, re-emit all time_window warnings unchanged
        for w in captured:
            if issubclass(w.category, UserWarning) and _is_time_window_warning(str(w.message)):
                warnings.warn_explicit(
                    message=w.message,
                    category=w.category,
                    filename=w.filename,
                    lineno=w.lineno,
                    source=w.source,
                )
        return

    embedded_names: set = set(extract_view_names_from_dashboards(all_dashboards))

    for w in captured:
        if not (issubclass(w.category, UserWarning) and _is_time_window_warning(str(w.message))):
            continue
        view_name = _extract_view_name_from_time_window_warning(str(w.message))
        if view_name and view_name in embedded_names:
            # Suppress: view is embedded in a dashboard; time selector drives aggregation.
            continue
        # Re-emit: view is standalone or name could not be extracted.
        warnings.warn_explicit(
            message=w.message,
            category=w.category,
            filename=w.filename,
            lineno=w.lineno,
            source=w.source,
        )


def cmd_package(args) -> int:
    try:
        views, dashboards = _load(args)
    except DashboardValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    nav_rc, known = _resolve_import_navigations(args, dashboards)
    if nav_rc:
        return 1
    # supermetric:"<name>" columns bind per view, to the view's own content
    # set then the factory (issue #270); a column that does not bind fails
    # here, before anything is written.
    corpus, col_rc = _column_corpus(
        views, getattr(args, "supermetrics_dir", str(DEFAULT_SUPERMETRICS)))
    if col_rc:
        return 1
    blob = build_import_zip(
        views, dashboards, sm_resolver=corpus.resolver().uuid_for,
        known_dashboards=known,
    )
    out = Path(args.output)
    out.write_bytes(blob)
    print(f"wrote {out} ({len(blob)} bytes)")
    return 0


def cmd_sync(args) -> int:
    try:
        views, dashboards = _load(args)
    except DashboardValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    if not views and not dashboards:
        print("nothing to sync", file=sys.stderr)
        return 1
    nav_rc, known = _resolve_import_navigations(args, dashboards)
    if nav_rc:
        return 1
    # Every supermetric:"<name>" view column must bind to exactly one SM of
    # the view's own content set or the factory (issue #270), before the
    # instance is touched.  The same corpus and resolver feed the referent
    # check, the renderer and the post-import walker.
    supermetrics_dir = getattr(args, "supermetrics_dir", str(DEFAULT_SUPERMETRICS))
    corpus, col_rc = _column_corpus(views, supermetrics_dir, primary_required=True)
    if col_rc:
        print("sync aborted before import; nothing was imported", file=sys.stderr)
        return 1
    resolver = corpus.resolver()

    profile, default = resolve_profile_from_args(args)
    client = VCFOpsClient.from_env(profile=profile, default_profile=default)

    # Referent check before the import (issue #154): the super metrics the
    # synced views and dashboards use are loaded from the repo SM YAML and
    # every @supermetric:"<name>" in their formulas must resolve (repo, then
    # target).  A missing one is named, referrer and referent, and nothing
    # is imported.  Read-only.
    if _check_sm_referents_before_import(
        client, views, dashboards,
        supermetrics_dir=supermetrics_dir, corpus=corpus,
    ):
        return 1

    try:
        user = get_current_user(client)
        marker = discover_marker_filename(client)
        blob = build_import_zip(
            views, dashboards, owner_user_id=user["id"], marker_filename=marker,
            sm_resolver=resolver.uuid_for, known_dashboards=known,
        )
        result = import_content_zip(client, blob)
    except VCFOpsError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 2
    print(f"state: {result.get('state')}")
    for s in result.get("operationSummaries", []):
        print(
            f"  {s.get('contentType','?'):20s} "
            f"imported={s.get('imported',0)} "
            f"skipped={s.get('skipped',0)} "
            f"failed={s.get('failed',0)} "
            f"state={s.get('state','?')}"
        )
        for msg in s.get("errorMessages", []) or []:
            print(f"    ERROR: {msg}")
    if result.get("state") != "FINISHED":
        return 1

    # A FINISHED import that imported nothing and skipped everything is
    # not a successful sync: the instance still holds the old content.
    # State alone used to gate this, so an all-skipped import reported ok.
    #
    # This zip carries BOTH content types, so each flag is attributed to
    # the content of its own type only. Naming dashboards because the
    # co-shipped views were skipped would be a false statement about
    # content the same envelope reports as imported.
    names_by_type = {
        "DASHBOARDS": [d.name for d in dashboards],
        "VIEW_DEFINITIONS": [v.name for v in views],
    }
    flagged = all_skipped_content_types(result, DASHBOARD_CONTENT_TYPES)
    if flagged:
        for ct, (imported, skipped) in sorted(flagged.items()):
            print(
                f"WARNING: content type {ct}: imported={imported} "
                f"skipped={skipped}. The import finished but changed nothing "
                f"of this type on the instance.",
                file=sys.stderr,
            )
            affected = names_by_type.get(ct) or []
            if affected:
                print(
                    f"WARNING: affected {ct} content: " + ", ".join(affected),
                    file=sys.stderr,
                )
        print(
            "WARNING: existing objects with the same ids/names were left as "
            "they were. Verify on the instance before treating this sync as "
            "applied; deleting the existing object and re-syncing is the "
            "reliable way to force an update.",
            file=sys.stderr,
        )
        # Same units as the affected line above: item names, not type
        # names, so the operator does not have to translate between two
        # vocabularies to work out what actually landed.
        unaffected = [
            name
            for ct in sorted(names_by_type)
            if ct not in flagged
            for name in names_by_type[ct]
        ]
        if unaffected:
            print(
                "WARNING: not affected (imported normally): "
                + ", ".join(unaffected),
                file=sys.stderr,
            )

    # --- Phase-2 materialization: a FINISHED import only covers phase 1 (#167) ---
    # Skipped when this import changed no dashboard (all skipped): what is on
    # the instance is not what this run imported, so a pre-existing stuck
    # dashboard must not fail this sync. The bundle-sync handler does the same.
    mat_rc = 0
    if getattr(args, "skip_materialization_check", False):
        pass
    elif "DASHBOARDS" in flagged:
        if dashboards:
            print("MATERIALIZATION SKIPPED: the import changed no dashboards")
    else:
        mat_rc = _report_materialization(
            client, dashboards,
            recheck_wait_s=getattr(args, "materialization_wait", None),
        )

    # --- Dependency walker: check SM enablement + OOTB metric collection state ---
    dep_rc = _run_dep_walker(
        client,
        views=views,
        dashboards=dashboards,
        supermetrics_dir=supermetrics_dir,
        auto_enable_metrics=getattr(args, "auto_enable_metrics", False),
        skip_metric_check=getattr(args, "skip_metric_check", False),
        corpus=corpus,
    )
    return dep_rc or mat_rc


def _report_materialization(client, dashboards: list, recheck_wait_s=None) -> int:
    """Report whether the imported dashboards finished building (#167).

    Every line starts ``MATERIALIZATION <STATE>:`` so a run is easy to grep:

    - ``MATERIALIZATION OK:`` (stdout) count of dashboards that finished.
    - ``MATERIALIZATION WAIT:`` (stdout) some are still building; one
      re-check follows after the stated wait.
    - ``MATERIALIZATION INCOMPLETE:`` (stderr, WARNING) still building after
      the re-check with every pending adapter installed; names the pending
      adapter kinds and resources. Not a failure: it may still finish.
    - ``MATERIALIZATION STALLED:`` (stderr, WARNING, rc 1) waiting on an
      adapter kind the target lacks; never completes on its own.
    - ``MATERIALIZATION ABSENT:`` (stderr, WARNING) in the import, not on
      the instance afterwards.
    - ``MATERIALIZATION UNCHECKED:`` (stderr, WARNING) the check itself
      failed. Never a failure.
    """
    if not dashboards:
        return 0

    def _on_wait(count: int, seconds: int) -> None:
        print(
            f"MATERIALIZATION WAIT: {count} dashboard(s) still building; "
            f"re-checking once in {seconds} s",
            flush=True,
        )

    try:
        statuses = check_dashboard_materialization(
            client, dashboards, recheck_wait_s=recheck_wait_s, on_wait=_on_wait,
        )
    except Exception as e:  # noqa: BLE001  advisory check; a transport error is a WARNING
        print(
            f"WARNING: MATERIALIZATION UNCHECKED: could not check whether the "
            f"imported dashboards finished building: {e}",
            file=sys.stderr,
        )
        return 0
    return report_materialization_statuses(statuses)


def report_materialization_statuses(statuses: list) -> int:
    """Print the ``MATERIALIZATION OK:`` count and one WARNING line per
    dashboard that did not finish building; return 1 when any is STALLED.

    Shared by this CLI and the pak installer (issue #244) so an operator
    reads the same lines whichever path installed the dashboard.
    """
    from vcfcf_core.dashboards.materialization import (
        COMPLETE,
        STALLED,
        describe_status,
    )

    rc = 0
    done = sum(1 for st in statuses if st.state == COMPLETE)
    if done:
        print(f"MATERIALIZATION OK: {done} of {len(statuses)} dashboard(s) finished building")
    for st in statuses:
        if st.state == COMPLETE:
            continue
        label = st.state.upper()
        print(f"WARNING: MATERIALIZATION {label}: {describe_status(st)}", file=sys.stderr)
        if st.state == STALLED:
            rc = 1
    return rc


def _load_repo_sms(supermetrics_dir: str) -> tuple[list, str]:
    """Load the SM YAML under ``supermetrics_dir``, read-only.

    Returns ``(defs, error)``: an absent directory is ``([], "")``, a load
    failure is ``([], message)``.  Loaded without the framework-prefix rule
    and without minting ids (``sm_columns.load_sm_dir_readonly``), so a
    check never rewrites a file.
    """
    defs, err, _idless = sm_columns.load_sm_dir_readonly(supermetrics_dir)
    return defs, err


def _column_corpus(views: list, supermetrics_dir: str, primary_required: bool = False):
    """Load the SM corpus and check every ``supermetric:"<name>"`` column
    of ``views`` binds to exactly one SM (issue #270).

    Returns ``(corpus, rc)``; rc 1 after printing one ``ERROR:`` line per
    column that is ambiguous, unresolved, or names an id-less SM.  A corpus
    directory that does not load is a WARN naming it (its SMs then cannot
    resolve, which the column check reports if a column needs one), except
    ``supermetrics_dir`` when ``primary_required`` (sync: the referent check
    cannot run without it), which is an ERROR and rc 1.
    """
    corpus = sm_columns.load_sm_corpus(supermetrics_dir)
    if corpus.primary_error and primary_required:
        print(
            f"ERROR: cannot check super metric references: the super metric "
            f"YAML in {supermetrics_dir} does not load: {corpus.primary_error}",
            file=sys.stderr,
        )
        return corpus, 1
    if corpus.primary_error:
        print(
            f"WARN  could not load super metric YAML from {supermetrics_dir}: "
            f"{corpus.primary_error}",
            file=sys.stderr,
        )
    for extra, err in corpus.extra_errors:
        print(f"WARN  could not load super metric YAML from {extra}: {err}",
              file=sys.stderr)
    errors = corpus.resolver().column_errors(views)
    for msg in errors:
        print(f"ERROR: {msg}", file=sys.stderr)
    return corpus, (1 if errors else 0)


def _check_sm_referents_before_import(
    client,
    views: list,
    dashboards: list,
    supermetrics_dir: str = str(DEFAULT_SUPERMETRICS),
    corpus=None,
) -> int:
    """Resolve the ``@supermetric:"<name>"`` referents of every super metric
    the synced views and dashboards use, before the import (issue #154).

    The SM corpus is ``sm_columns.load_sm_corpus(supermetrics_dir)``:
    ``supermetrics_dir`` plus ``content/supermetrics``, every
    ``third_party/*/supermetrics`` and every
    ``content/sdk-adapters/*/supermetrics`` (``corpus``, when the caller
    loaded it).  A content set whose YAML did not load, or an ambiguous name,
    is an ERROR and nothing is imported.  A
    ``supermetric:"<name>"`` column resolves through the corpus resolver the
    renderer uses (the view's own content set, then the factory, issue
    #270); an ``sm_<uuid>`` column or widget
    key resolves by id in the corpus.  Those SMs are taken, plus their
    in-corpus referents transitively, and each referent must resolve
    against the corpus or the target instance.  Returns 1 when one does not,
    when a target lookup failed (DEP-ERROR lines naming referrer and
    referent), or when ``supermetrics_dir`` exists but does not load (the
    check cannot run, so nothing is imported); 0 otherwise.  An extra corpus
    directory that does not load, or a column or widget whose SM is in no
    loaded directory, is a WARN naming it.  Read-only: ``find_by_name``
    lookups only, and every SM YAML is loaded without minting ids.
    """
    try:
        from vcfcf_common.dep_walker import check_sm_referents, supermetrics_used_by
    except ImportError as e:
        print(f"WARN  dep walker unavailable: {e}", file=sys.stderr)
        return 0

    if corpus is None:
        # Loaded here, so warned here; a caller that passes a corpus has
        # already said which directories did not load.
        corpus = sm_columns.load_sm_corpus(supermetrics_dir)
        for extra, extra_err in corpus.extra_errors:
            print(
                f"WARN  could not load super metric YAML from {extra}: {extra_err}; "
                f"super metrics defined there are not checked before the import",
                file=sys.stderr,
            )
    if corpus.primary_error:
        print(
            f"ERROR: cannot check super metric references: the super metric "
            f"YAML in {supermetrics_dir} does not load: {corpus.primary_error}",
            file=sys.stderr,
        )
        print("sync aborted before import; nothing was imported", file=sys.stderr)
        return 1
    repo_sms = list(corpus.defs)

    # A supermetric:"<name>" column resolves exactly as the renderer will
    # resolve it in this sync: the same corpus, the same resolver.
    from vcfcf_core.supermetrics.column_resolver import SmColumnResolutionError
    try:
        used, unresolved = supermetrics_used_by(
            views, dashboards, repo_sms, column_resolver=corpus.resolver()
        )
    except SmColumnResolutionError as e:
        print(f"ERROR: cannot check super metric references: {e}", file=sys.stderr)
        print("sync aborted before import; nothing was imported", file=sys.stderr)
        return 1
    for ref in unresolved:
        print(
            f"WARN  {ref}, which is in no loaded super metric YAML; its "
            f"@supermetric cross-references are not checked before the import",
            file=sys.stderr,
        )
    if not used:
        return 0
    walk = check_sm_referents(
        client, used, sm_name_map={d.name: d.id for d in repo_sms if d.id}
    )
    for level, msg in walk.messages:
        if level == "ERROR":
            print(f"DEP-{level}  {msg}", file=sys.stderr)
        else:
            print(f"DEP-{level}  {msg}")
    if not walk.ok:
        print(
            "sync aborted before import: unresolved super metric reference(s) "
            "(see DEP-ERROR above); nothing was imported",
            file=sys.stderr,
        )
        return 1
    return 0


def _run_dep_walker(
    client,
    views: list,
    dashboards: list,
    supermetrics_dir: str = str(DEFAULT_SUPERMETRICS),
    customgroups_dir: str = "customgroups",
    auto_enable_metrics: bool = False,
    skip_metric_check: bool = False,
    corpus=None,
) -> int:
    """Run the dependency walker after a successful views/dashboards sync.

    Loads the SM YAML from supermetrics_dir (if it exists) to build the
    sm_name_map so SM refs discovered by UUID can be annotated with names.
    The SM definitions themselves are NOT re-synced here, they're passed
    to the walker only for the name map and to tell the walker which SMs
    are in the current sync batch (the walker skips those for the enable
    check, since the SM sync+enable flow handles them).

    Loads the customgroups corpus from customgroups_dir so the walker can
    validate customgroup references found in view ``customgroup:`` fields.

    ``corpus`` (an ``sm_columns.SmCorpus``, loaded when None) gives the
    walker the resolver the renderer used, so a ``supermetric:"<name>"``
    column is checked and enabled as the SM it was bound to (issue #266).
    """
    try:
        from vcfcf_common.dep_walker import walk_and_check
    except ImportError as e:
        print(f"WARN  dep walker unavailable: {e}", file=sys.stderr)
        return 0

    # Load SM defs for name map (optional, walker degrades gracefully if absent)
    sm_defs, _err = _load_repo_sms(supermetrics_dir)

    sm_name_map = {d.name: d.id for d in sm_defs}
    if corpus is None:
        corpus = sm_columns.load_sm_corpus(supermetrics_dir)

    # Load customgroup defs for ref validation (optional, walker degrades gracefully)
    cg_defs: list = []
    cg_dir = Path(customgroups_dir)
    if cg_dir.exists():
        try:
            from vcfcf_customgroups.loader import load_dir as _cg_load_dir
            cg_defs = _cg_load_dir(cg_dir)
        except Exception:
            pass  # non-fatal: customgroup validation will be skipped

    # For dashboard-only syncs, supermetrics list is empty, the walker
    # will still check pre-existing SM refs from views/dashboards.  The
    # @supermetric referents of the SMs they use were already checked before
    # the import (_check_sm_referents_before_import); passing those SMs here
    # would mark them "in this sync batch" and skip their enable check.
    walk = walk_and_check(
        client=client,
        supermetrics=[],  # not syncing SMs here; pass empty list
        views=views,
        dashboards=dashboards,
        customgroups=cg_defs,
        auto_enable_metrics=auto_enable_metrics,
        skip_metric_check=skip_metric_check,
        sm_name_map=sm_name_map,
        sm_column_resolver=corpus.resolver(),
    )
    for level, msg in walk.messages:
        if level == "ERROR":
            print(f"DEP-{level}  {msg}", file=sys.stderr)
        else:
            print(f"DEP-{level}  {msg}")
    if not walk.ok:
        print("sync incomplete: dependency check found errors (see DEP-ERROR above)",
              file=sys.stderr)
        return 1
    return 0


def _resolve_dashboard_ids(
    ui: VCFOpsUIClient, targets: list[str]
) -> list[tuple[str, str]]:
    """Resolve a mixed list of UUIDs and display names to (uuid, name) pairs.

    For entries that look like UUIDs (contain hyphens), the name is looked
    up from the server list. Entries that don't look like UUIDs are matched
    by name. Raises SystemExit if any target cannot be resolved.
    """
    import re
    uuid_pat = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
    )
    server_list = ui.list_dashboards()
    by_id = {d["id"]: d["name"] for d in server_list}
    by_name = {d["name"]: d["id"] for d in server_list}

    resolved: list[tuple[str, str]] = []
    errors: list[str] = []
    for t in targets:
        if uuid_pat.match(t):
            name = by_id.get(t, t)  # if not found, use uuid as name (silent no-op)
            resolved.append((t, name))
        else:
            uid = by_name.get(t)
            if uid is None:
                errors.append(f"  dashboard not found by name: {t!r}")
            else:
                resolved.append((uid, t))
    if errors:
        print("ERROR: could not resolve the following targets:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    return resolved


def _resolve_view_ids(
    ui: VCFOpsUIClient, targets: list[str]
) -> list[tuple[str, str]]:
    """Resolve a mixed list of view UUIDs and names to (uuid, name) pairs.

    View list comes from Ext.Direct getGroupedViewDefinitionThumbnails.
    The response is a grouped structure; we flatten it to find all views.
    Raises SystemExit if any target cannot be resolved.
    """
    import re
    uuid_pat = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
    )

    groups = ui.list_views()
    # getGroupedViewDefinitionThumbnails returns a two-level nested dict:
    #   result[viewType][resourceKind] = [view dicts]
    # e.g. {"LIST": {"VirtualMachine": [...], "HostSystem": [...]}, ...}
    # Iterating a dict yields string keys, not dicts or lists, so the old
    # flat-list traversal silently produced an empty result.  Flatten both
    # levels explicitly, with a list-of-dicts fallback for older API shapes.
    all_views: list[dict] = []
    if isinstance(groups, dict):
        # Nested-dict shape: viewType -> resourceKind -> [views]
        for resource_map in groups.values():
            if isinstance(resource_map, dict):
                for view_list in resource_map.values():
                    if isinstance(view_list, list):
                        all_views.extend(view_list)
            elif isinstance(resource_map, list):
                # One level of nesting only
                all_views.extend(resource_map)
    elif isinstance(groups, list):
        for item in groups:
            if isinstance(item, dict):
                # Group object: may have viewDefinitions or similar key
                for key in ("viewDefinitions", "views", "items"):
                    sub = item.get(key)
                    if isinstance(sub, list):
                        all_views.extend(sub)
                        break
                else:
                    # If no known sub-key, treat item itself as a view entry
                    if "id" in item:
                        all_views.append(item)
            elif isinstance(item, list):
                all_views.extend(item)

    by_id = {v["id"]: v.get("name", v["id"]) for v in all_views if "id" in v}
    by_name = {v.get("name", ""): v["id"] for v in all_views if "id" in v and v.get("name")}

    resolved: list[tuple[str, str]] = []
    errors: list[str] = []
    for t in targets:
        if uuid_pat.match(t):
            name = by_id.get(t, t)
            resolved.append((t, name))
        else:
            uid = by_name.get(t)
            if uid is None:
                errors.append(f"  view not found by name: {t!r}")
            else:
                resolved.append((uid, t))
    if errors:
        print("ERROR: could not resolve the following targets:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    return resolved


def cmd_delete_dashboard(args) -> int:
    """Delete one or more dashboards by UUID or display name.

    Uses the unsupported VCF Ops UI session (Struts action layer), not the
    Suite API. Credentials come from the standard VCFOPS_* env vars.
    Deleting a non-existent UUID is a silent no-op.
    """
    try:
        profile, default = resolve_profile_from_args(args)
        ui = VCFOpsUIClient.from_env(profile=profile, default_profile=default)
        ui.login()
    except UIClientError as e:
        print(f"FAILED (UI login): {e}", file=sys.stderr)
        return 2
    try:
        targets = _resolve_dashboard_ids(ui, args.targets)
        if not targets:
            print("nothing to delete", file=sys.stderr)
            return 1
        print(f"{'Would delete' if args.dry_run else 'Deleting'} "
              f"{len(targets)} dashboard(s):")
        for uid, name in targets:
            print(f"  {uid}  {name}")
        if args.dry_run:
            return 0
        ui.delete_dashboards(targets)
        print("done")
        return 0
    except UIClientError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 2
    finally:
        ui.logout()


def cmd_delete_view(args) -> int:
    """Delete one or more view definitions by UUID or display name.

    Uses the unsupported VCF Ops UI session (Ext.Direct RPC layer), not the
    Suite API. Credentials come from the standard VCFOPS_* env vars.
    Unlike dashboard delete, deleting a non-existent view UUID raises an
    error, this command surfaces that as a non-zero exit.
    """
    try:
        profile, default = resolve_profile_from_args(args)
        ui = VCFOpsUIClient.from_env(profile=profile, default_profile=default)
        ui.login()
    except UIClientError as e:
        print(f"FAILED (UI login): {e}", file=sys.stderr)
        return 2
    try:
        targets = _resolve_view_ids(ui, args.targets)
        if not targets:
            print("nothing to delete", file=sys.stderr)
            return 1
        print(f"{'Would delete' if args.dry_run else 'Deleting'} "
              f"{len(targets)} view(s):")
        for uid, name in targets:
            print(f"  {uid}  {name}")
        if args.dry_run:
            return 0
        failed = 0
        for uid, name in targets:
            try:
                ui.delete_view(uid, name)
                print(f"  deleted {uid}  {name}")
            except UIClientError as e:
                print(f"  FAILED {uid}  {name}: {e}", file=sys.stderr)
                failed += 1
        return 0 if failed == 0 else 2
    except UIClientError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 2
    finally:
        ui.logout()


def cmd_bind_summary(args) -> int:
    """Bind every `summary_for` dashboard to every listed resource kind's Summary tab.

    Post-import route over the unsupported UI session (Struts layer); a
    pak carries the same binding in content/dashboards/dashboards.properties
    instead. See vcfcf_dashboards/summary_bind.py for the flow and
    knowledge/context/api-surface/summary_dashboard_assignment.md for the
    mechanism (binding is a template COPY; the printed template UUID is
    the only handle on it).
    """
    validate_profile_arg(args)
    wait_s = WAIT_DEFAULT_S if args.wait_timeout is None else args.wait_timeout
    if args.wait_timeout is not None and not args.wait:
        print("WARN: --wait-timeout has no effect without --wait.", file=sys.stderr)
    try:
        _views, dashboards = _load(args)
    except DashboardValidationError as e:
        print(f"FAILED (load): {e}", file=sys.stderr)
        return 1
    if args.dry_run:
        return bind_summary(None, dashboards, only=args.dashboard, unbind=args.unbind, dry_run=True)
    try:
        profile, default = resolve_profile_from_args(args)
        ui = VCFOpsUIClient.from_env(profile=profile, default_profile=default)
        ui.login()
    except (UIClientError, requests.RequestException) as e:
        print(f"FAILED (UI login): {e}", file=sys.stderr)
        return 2
    try:
        return bind_summary(ui, dashboards, only=args.dashboard, unbind=args.unbind,
                            wait=args.wait, wait_s=wait_s)
    except (UIClientError, requests.RequestException) as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 2
    finally:
        ui.logout()


def _wait_seconds(text: str) -> int:
    """argparse type: a whole number of seconds from 0 to WAIT_MAX_S."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number of seconds: {text!r}") from None
    if value < 0 or value > WAIT_MAX_S:
        raise argparse.ArgumentTypeError(f"must be 0 to {WAIT_MAX_S}, got {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vcfcf_dashboards")
    p.add_argument("--views-dir", default=str(DEFAULT_VIEWS),
                   help=f"Path to views YAML directory (default: {DEFAULT_VIEWS})")
    p.add_argument("--dashboards-dir", default=str(DEFAULT_DASHBOARDS),
                   help=f"Path to dashboards YAML directory (default: {DEFAULT_DASHBOARDS})")
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate YAML")
    pv.add_argument(
        "--id-guard-baseline",
        metavar="REV",
        default=None,
        help=(
            "CI plumbing for the #113 dashboard id-stability guard, not an "
            "operator switch: in ADDITION to the always-on HEAD comparison, "
            "compare dashboard ids against this git rev and every commit "
            "between it and HEAD, unioning the findings. CI passes the PR "
            "merge-base so a re-id committed anywhere on the PR branch is "
            "still caught. The rev must be an ancestor of HEAD (it can "
            "only widen the comparison, never narrow or disable it); a "
            "non-ancestor rev fails validation, an unresolvable rev warns "
            "and degrades to the HEAD-only comparison."
        ),
    )
    add_profile_arg(pv, default="prod")
    pv.set_defaults(func=cmd_validate)

    pp = sub.add_parser("package", help="build the import ZIP locally")
    pp.add_argument("-o", "--output", default="dashboards-content.zip")
    pp.add_argument(
        "--allow-external-navigation-targets",
        action="store_true",
        default=False,
        help=(
            "Allow a Dashboard Navigation to a repo dashboard this import does "
            "not carry (it is listed as a PREREQUISITE and must already be "
            "installed). Default: fail."
        ),
    )
    pp.set_defaults(func=cmd_package)

    ps = sub.add_parser("sync", help="build and import to VCF Ops")
    ps.add_argument(
        "--supermetrics-dir",
        default=str(DEFAULT_SUPERMETRICS),
        metavar="DIR",
        help=(
            "Path to the supermetrics/ YAML directory. Used to check the "
            "@supermetric cross-references of the super metrics the synced "
            "views and dashboards use (before the import, together with "
            "content/supermetrics, third_party/*/supermetrics and "
            "content/sdk-adapters/*/supermetrics, which also resolve "
            "supermetric:\"<name>\" view columns) and to build the SM "
            "name map for dependency check annotations. Default: content/supermetrics"
        ),
    )
    ps.add_argument(
        "--auto-enable-metrics",
        action="store_true",
        default=False,
        help=(
            "Enable OOTB metrics with defaultMonitored=false on the Default Policy. "
            "Default: warn and flag, but do not modify the policy."
        ),
    )
    ps.add_argument(
        "--skip-metric-check",
        action="store_true",
        default=False,
        help=(
            "Skip the OOTB metric defaultMonitored check entirely. "
            "Use when you know the target policy already covers these metrics."
        ),
    )
    ps.add_argument(
        "--skip-materialization-check",
        action="store_true",
        default=False,
        help=(
            "Skip the post-import check that each dashboard finished building "
            "(one DASHBOARDS export plus an adapter-kind read). Default: check, "
            "and fail when a dashboard waits on an adapter that is not installed."
        ),
    )
    ps.add_argument(
        "--materialization-wait",
        type=int,
        default=None,
        metavar="SECONDS",
        help=(
            "Seconds to wait before the one re-check of dashboards still "
            "building after the import (default 180, or "
            "VCFCF_MATERIALIZATION_WAIT_S; capped at 900; 0 reports them at once)."
        ),
    )
    ps.add_argument(
        "--allow-external-navigation-targets",
        action="store_true",
        default=False,
        help=(
            "Allow a Dashboard Navigation to a repo dashboard this import does "
            "not carry (it is listed as a PREREQUISITE and must already be "
            "installed). Default: fail."
        ),
    )
    add_profile_arg(ps, default="devel")
    ps.set_defaults(func=cmd_sync)

    pdd = sub.add_parser(
        "delete-dashboard",
        help="delete dashboard(s) by UUID or name via UI session",
    )
    pdd.add_argument(
        "targets",
        nargs="+",
        metavar="UUID-OR-NAME",
        help="dashboard UUID(s) or display name(s) to delete",
    )
    pdd.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be deleted without deleting",
    )
    add_profile_arg(pdd, default="devel")
    pdd.set_defaults(func=cmd_delete_dashboard)

    pdv = sub.add_parser(
        "delete-view",
        help="delete view definition(s) by UUID or name via UI session",
    )
    pdv.add_argument(
        "targets",
        nargs="+",
        metavar="UUID-OR-NAME",
        help="view UUID(s) or display name(s) to delete",
    )
    pdv.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be deleted without deleting",
    )
    add_profile_arg(pdv, default="devel")
    pdv.set_defaults(func=cmd_delete_view)

    pbs = sub.add_parser(
        "bind-summary",
        help="bind summary_for dashboards to every listed resource kind's Summary tab via UI session",
    )
    pbs.add_argument(
        "--dashboard",
        metavar="NAME",
        default=None,
        help="only this dashboard (exact YAML name); default: every dashboard with summary_for",
    )
    pbs.add_argument(
        "--unbind",
        action="store_true",
        help="restore the built-in Summary page (resetAssociations with the kind's defaultTemplateName) instead of binding",
    )
    pbs.add_argument(
        "--dry-run",
        action="store_true",
        help="print the association map only; no session, nothing written",
    )
    pbs.add_argument(
        "--wait",
        action="store_true",
        help=("when a dashboard is still building (isLoading: true), re-check every "
              f"{WAIT_POLL_S} s until it is built, then bind (default: refuse it, nothing "
              "written; a copy of an unfinished dashboard stays unfinished, issue #200)"),
    )
    pbs.add_argument(
        "--wait-timeout",
        type=_wait_seconds,
        default=None,
        metavar="SECONDS",
        help=f"with --wait, the wait budget for the whole run, not per dashboard (default "
             f"{WAIT_DEFAULT_S}: one 10-minute importer tick plus a margin; at most "
             f"{WAIT_MAX_S}); a dashboard still building when it is spent is an ERROR",
    )
    pbs.epilog = ("Exit codes: 0 every kind bound (or reset); 1 nothing to do or the YAML "
                  "did not load; 2 any ERROR (a dashboard still building, not installed, "
                  "named twice, a kind not found, a refused or not-taken association, a "
                  "UI login or transport failure). A refused association skips that "
                  "dashboard only; the run goes on.")
    add_profile_arg(pbs, default="devel")
    pbs.set_defaults(func=cmd_bind_summary)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
