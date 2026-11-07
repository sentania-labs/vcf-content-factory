"""Install order of the two distributed installers (#302).

A View widget that lists every object of a kind pins a helper custom group
by display name, bound at dashboard import
(knowledge/context/wire-formats/view_widget_all_objects_of_kind.md). The
group has to exist first, so custom groups install before dashboards, as the
factory syncer already does. The dependencies that must hold:

- super metrics before custom groups (a group rule may reference an SM);
- custom groups before views + dashboards (#302);
- views before dashboards (one import: the ``views_and_dashboards`` entry);
- views before reports (reports reference views);
- symptoms before alerts (alerts reference symptoms);
- super metrics imported before they are enabled on the Default Policy.

Uninstall runs the reverse where it matters, as the factory syncer does
(reverse sync_order): dashboards before views, views before custom groups,
alerts before symptoms, custom groups before super metrics.

install.py is read from its live registry; install.ps1 has no Python
loader, so its registry block is parsed statically. Both must yield the
same install and uninstall order.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "vcfcf_packaging" / "templates"

EXPECTED_ORDER = [
    "supermetrics",
    "customgroups",
    "views_and_dashboards",
    "sm_enable",
    "builtin_metric_enables",
    "reports",
    "symptoms",
    "alerts",
]


EXPECTED_UNINSTALL_ORDER = [
    "dashboards",
    "reports",
    "views",
    "alerts",
    "customgroups",
    "supermetrics",
    "builtin_metric_enables",
    "symptoms",
]


def _py_order(kind):
    path = TEMPLATES / "install.py"
    spec = importlib.util.spec_from_file_location("_install_template_order", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_install_template_order"] = mod
    spec.loader.exec_module(mod)
    entries = [e for e in mod._CONTENT_REGISTRY
               if e[f"{kind}_fn"] is not None and e[f"{kind}_order"] is not None]
    entries.sort(key=lambda e: e[f"{kind}_order"])
    return [(e["content_type"], float(e[f"{kind}_order"])) for e in entries]


def _ps1_order(kind):
    prefix = {"install": "Install", "uninstall": "Uninstall"}[kind]
    text = (TEMPLATES / "install.ps1").read_text(encoding="utf-8")
    m = re.search(r"^\$script:ContentRegistry = @\((.*?)^\)\s*$", text, re.S | re.M)
    assert m, "ContentRegistry block not found in install.ps1"
    out = []
    for body in re.findall(r"@\{(.*?)\n\s*\}", m.group(1), re.S):
        ct = re.search(r'^\s*ContentType\s*=\s*"([^"]+)"', body, re.M)
        order = re.search(rf"^\s*{prefix}Order\s*=\s*(\S+)", body, re.M)
        fn = re.search(rf"^\s*{prefix}Fn\s*=\s*(\S+)", body, re.M)
        assert ct and order and fn, f"unparsed registry entry: {body!r}"
        if order.group(1) == "$null" or fn.group(1) == "$null":
            continue
        out.append((ct.group(1), float(order.group(1))))
    out.sort(key=lambda e: e[1])
    return out


def _py_install_order():
    return _py_order("install")


def _ps1_install_order():
    out = _ps1_order("install")
    assert len(out) == len(EXPECTED_ORDER), out
    return out


def _py_uninstall_order():
    return _py_order("uninstall")


def _ps1_uninstall_order():
    out = _ps1_order("uninstall")
    assert len(out) == len(EXPECTED_UNINSTALL_ORDER), out
    return out


@pytest.mark.parametrize("reader", [_py_install_order, _ps1_install_order],
                         ids=["install.py", "install.ps1"])
def test_install_order(reader):
    order = [ct for ct, _ in reader()]
    assert order == EXPECTED_ORDER
    pos = order.index
    assert pos("supermetrics") < pos("customgroups") < pos("views_and_dashboards")
    assert pos("views_and_dashboards") < pos("reports")
    assert pos("symptoms") < pos("alerts")
    assert pos("supermetrics") < pos("sm_enable")


@pytest.mark.parametrize("reader", [_py_uninstall_order, _ps1_uninstall_order],
                         ids=["install.py", "install.ps1"])
def test_uninstall_order(reader):
    order = [ct for ct, _ in reader()]
    assert order == EXPECTED_UNINSTALL_ORDER
    pos = order.index
    assert pos("dashboards") < pos("views") < pos("customgroups")
    assert pos("reports") < pos("views")
    assert pos("alerts") < pos("symptoms")
    assert pos("customgroups") < pos("supermetrics")


def test_installers_agree_on_order_values():
    assert _py_install_order() == _ps1_install_order()
    assert _py_uninstall_order() == _ps1_uninstall_order()
