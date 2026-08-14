# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

def _parse_version(v_str):
    try:
        return tuple(int(x) for x in str(v_str).strip().split("."))
    except Exception:
        return (0,)


def _get_app_version():
    from org.telegram.messenger import BuildVars
    return BuildVars.BUILD_VERSION_STRING


def check_app_version(app_version_expr):
    # app_version_expr: ">=1.2.3" | "<=1.2.3" | "==1.2.3"
    # operators can have > and = or = and > in any order
    if not app_version_expr:
        return True
    expr = str(app_version_expr).strip()
    try:
        if expr.startswith(">=") or expr.startswith("=>"):
            op, ver_str = ">=", expr[2:]
        elif expr.startswith("<=") or expr.startswith("=<"):
            op, ver_str = "<=", expr[2:]
        elif expr.startswith("=="):
            op, ver_str = "==", expr[2:]
        else:
            return True

        app_ver = _parse_version(_get_app_version())
        req_ver = _parse_version(ver_str.strip())

        if op == ">=":
            return app_ver >= req_ver
        if op == "<=":
            return app_ver <= req_ver
        if op == "==":
            return app_ver == req_ver
    except Exception:
        return True
    return True