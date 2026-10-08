"""Static pre-checks for pasted strategy code (defence in depth - NOT a security boundary)."""
from __future__ import annotations

import ast

from .worker import ALLOWED_IMPORTS, BLOCKED_BUILTINS

MAX_CODE_BYTES = 60_000
BLOCKED_ATTRS = {"__subclasses__", "__globals__", "__builtins__", "__import__", "__code__", "__closure__",
                 "__bases__", "__mro__", "__getattribute__", "__loader__", "f_globals", "f_back", "gi_frame",
                 "system", "popen", "exec_module"}


def check_code(code: str) -> list[str]:
    """Return a list of problems; empty means the static checks passed."""
    problems: list[str] = []
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        return [f"Code is larger than {MAX_CODE_BYTES // 1000} KB"]
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"Syntax error on line {exc.lineno}: {exc.msg}"]
    has_class = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    problems.append(f"Line {node.lineno}: import '{a.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                problems.append(f"Line {node.lineno}: import from '{node.module}' is not allowed")
        elif isinstance(node, ast.Name) and node.id in BLOCKED_BUILTINS | {"__import__", "globals", "locals", "vars"}:
            problems.append(f"Line {node.lineno}: use of '{node.id}' is not allowed")
        elif isinstance(node, ast.Attribute) and node.attr in BLOCKED_ATTRS:
            problems.append(f"Line {node.lineno}: access to '.{node.attr}' is not allowed")
        elif isinstance(node, ast.ClassDef) and node.name == "Strategy":
            has_class = True
            methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
            if "signals" not in methods:
                problems.append("class Strategy must define a `signals(self, bars)` method")
    if not has_class:
        problems.append("Define a class named `Strategy` (see the templates)")
    return problems
