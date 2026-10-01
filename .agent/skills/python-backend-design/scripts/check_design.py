"""Mechanical checker for the python-backend-design rules.

Usage: edit TARGET_DIR below and run the file, or call main("<project-dir>").
"""

# ---- config ----
TARGET_DIR = "."
IGNORE_DIRS = {".venv", "venv", "__pycache__", ".git", "tests", "node_modules"}
# ----------------

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

LAYERS = ("core", "adapters", "services", "entrypoints", "wiring")
FORBIDDEN_IMPORTS = {
    "core": {"adapters", "services", "entrypoints", "wiring", "config"},
    "adapters": {"services", "entrypoints", "wiring"},
    "services": {"adapters", "entrypoints", "wiring"},
}
IO_MODULES = {"os", "requests", "httpx", "sqlite3", "boto3", "subprocess", "socket",
              "psycopg", "psycopg2", "sqlalchemy", "aiohttp", "urllib"}
IO_CALLS = {"open", "print", "input"}
# Submodules of IO_MODULES that do no I/O (pure string parsing) and are fine in core.
PURE_SUBMODULES = {"urllib.parse"}
ALLOWED_BASES = {"Protocol", "Exception", "AppError", "BaseModel"}
BANNED_CLASS_SUFFIXES = ("Factory", "Builder", "Manager", "Helper", "Helpers", "Utils", "Util")


@dataclass(frozen=True, slots=True)
class Violation:
    path: str
    line: int
    rule: str
    message: str


def detect_layer(path: Path, root: Path) -> str | None:
    rel = path.relative_to(root)
    for part in rel.parts[:-1]:
        if part in LAYERS:
            return part
    return path.stem if path.stem in LAYERS else None


def imported_roots(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [a.name.split(".")[0] for a in node.names]
    if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
        return [node.module.split(".")[0]]
    return []


def imports_only_pure(node: ast.AST) -> bool:
    """True if every module this import statement names is in PURE_SUBMODULES."""
    if isinstance(node, ast.Import):
        names = [a.name for a in node.names]
    elif isinstance(node, ast.ImportFrom) and node.module:
        names = [node.module]
    else:
        return False
    return all(name in PURE_SUBMODULES for name in names)


def base_name(b: ast.expr) -> str:
    if isinstance(b, ast.Name):
        return b.id
    if isinstance(b, ast.Attribute):
        return b.attr
    if isinstance(b, ast.Subscript):
        return base_name(b.value)
    return ""


def check_file(path: Path, root: Path) -> list[Violation]:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [Violation(str(path), e.lineno or 0, "syntax", str(e))]

    layer = detect_layer(path, root)
    out: list[Violation] = []
    add = lambda n, rule, msg: out.append(Violation(str(path), getattr(n, "lineno", 0), rule, msg))
    sync_defs, async_defs = 0, 0

    for node in ast.walk(tree):
        for mod in imported_roots(node):
            if mod in {"argparse", "click", "typer"}:
                add(node, "config", f"'{mod}' used; put config in UPPERCASE variables + Settings")
            if mod == "abc":
                add(node, "no-abc", "ABC/abstractmethod used; use typing.Protocol")
            if mod == "pydantic" and layer != "entrypoints":
                add(node, "pydantic-boundary", "pydantic outside entrypoints; use frozen dataclasses")
            if layer in FORBIDDEN_IMPORTS and mod in FORBIDDEN_IMPORTS[layer]:
                add(node, "layer-direction", f"'{layer}' must not import '{mod}'")
            if layer == "core" and mod in IO_MODULES and not imports_only_pure(node):
                add(node, "pure-core", f"core imports I/O module '{mod}'")

        if isinstance(node, ast.Attribute) and node.attr == "argv" and base_name(node.value) == "sys":
            add(node, "config", "sys.argv used; put config in UPPERCASE variables + Settings")
        if isinstance(node, ast.Global):
            add(node, "no-global", "'global' keyword; pass state explicitly")
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            add(node, "errors", "bare 'except:'; catch specific exceptions")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if layer == "core" and node.func.id in IO_CALLS:
                add(node, "pure-core", f"'{node.func.id}()' in core")
        if isinstance(node, ast.ClassDef):
            if any(k.arg == "metaclass" for k in node.keywords):
                add(node, "no-magic", f"metaclass on '{node.name}'")
            bases = [base_name(b) for b in node.bases]
            bad = [b for b in bases if b not in ALLOWED_BASES and not b.endswith("Error")]
            if bad:
                add(node, "no-inheritance", f"'{node.name}' inherits {bad}; use composition/Protocol")
            if len(bases) > 1:
                add(node, "no-inheritance", f"'{node.name}' uses multiple inheritance")
            if any(isinstance(s, ast.Assign) and any(getattr(t, "id", "") == "_instance" for t in s.targets)
                   for s in node.body):
                add(node, "no-singleton", f"'{node.name}' looks like a singleton")
            if node.name.endswith(BANNED_CLASS_SUFFIXES):
                add(node, "no-pattern-class", f"'{node.name}' is a factory/builder/god class; use a dict registry or module functions")
            methods = [s for s in node.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if methods and all(any(base_name(d) == "staticmethod" for d in m.decorator_list) for m in methods):
                add(node, "no-pattern-class", f"'{node.name}' has only staticmethods; make them module-level functions")
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            sync_defs += 1
        if isinstance(node, ast.AsyncFunctionDef) and not node.name.startswith("_"):
            async_defs += 1

    for stmt in tree.body:  # module-level mutable state
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and isinstance(stmt.value, (ast.List, ast.Dict, ast.Set)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            for t in targets:
                if isinstance(t, ast.Name) and not t.id.isupper():
                    add(stmt, "no-global-state", f"module-level mutable '{t.id}'; use UPPERCASE constant or pass explicitly")

    if layer in {"services", "adapters"} and sync_defs and async_defs:
        add(tree, "sync-async", "module mixes public sync and async functions; keep the chain one kind")
    return out


def check_path(target_dir: str) -> list[Violation]:
    root = Path(target_dir).resolve()
    files = [root] if root.is_file() else [
        p for p in root.rglob("*.py") if not (set(p.relative_to(root).parts) & IGNORE_DIRS)
    ]
    base = root.parent if root.is_file() else root
    return [v for f in sorted(files) for v in check_file(f, base)]


def main(target_dir: str = TARGET_DIR) -> int:
    violations = check_path(target_dir)
    for v in violations:
        print(f"{v.path}:{v.line}: [{v.rule}] {v.message}")
    print(f"\n{len(violations)} violation(s) found." if violations else "No violations found.")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
