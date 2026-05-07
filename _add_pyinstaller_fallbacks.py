#!/usr/bin/env python3
"""Add PyInstaller-compatible try/except fallbacks for `from alarm_app.xxx` imports.

For each file (excluding main.py, constants.py, tests/, scripts/, vendor_synthid/):
  - Each `from alarm_app.X import Y` (top-level or function-scoped) is wrapped:
        try:
            from alarm_app.X import Y
        except ImportError:
            from X import Y
  - Consecutive top-level alarm_app imports are merged into a single try/except.

Uses the `ast` module to locate import statements precisely, including
multi-line parenthesised forms.
"""

import ast
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
EXCLUDE_FILES = {"main.py", "constants.py", "_add_pyinstaller_fallbacks.py"}
EXCLUDE_DIRS = {
    "tests", "scripts", "__pycache__", "vendor_synthid",
    ".venv", "venv", ".git", "build", "dist", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
}


def find_affected_files() -> list[Path]:
    result: list[Path] = []
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fname in files:
            if not fname.endswith(".py") or fname in EXCLUDE_FILES:
                continue
            fpath = Path(root) / fname
            try:
                content = fpath.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if "from alarm_app." in content:
                result.append(fpath)
    return sorted(result)


def _build_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    """Map id(child) -> parent for every node in the tree."""
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


def find_alarm_app_imports(tree: ast.AST) -> list[ast.ImportFrom]:
    out: list[ast.ImportFrom] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module \
                and (node.module == "alarm_app" or node.module.startswith("alarm_app.")):
            out.append(node)
    return out


def _handler_catches_import_error(handler: ast.ExceptHandler) -> bool:
    """True if this handler catches ImportError (directly, in a tuple, or bare)."""
    t = handler.type
    if t is None:
        return True  # bare except catches everything
    if isinstance(t, ast.Name) and t.id in ("ImportError", "ModuleNotFoundError", "Exception", "BaseException"):
        return True
    if isinstance(t, ast.Tuple):
        for elt in t.elts:
            if isinstance(elt, ast.Name) and elt.id in (
                "ImportError", "ModuleNotFoundError", "Exception", "BaseException",
            ):
                return True
    return False


def is_already_wrapped(node: ast.ImportFrom, parents: dict[int, ast.AST]) -> bool:
    """The import is considered already wrapped only if its IMMEDIATE enclosing
    block is a Try.body whose handler list catches ImportError AND that handler
    contains a fallback `from X import …` of a NON-alarm_app module.

    A try whose except clause is `Exception` does NOT count, because then a
    failed alarm_app import would bubble up to the outer Exception handler
    without trying a flat-name fallback.
    """
    parent = parents.get(id(node))
    if not isinstance(parent, ast.Try):
        return False
    if node not in parent.body:
        return False
    # Need at least one handler that catches ImportError specifically
    has_ie = any(
        h.type is None
        or (isinstance(h.type, ast.Name) and h.type.id in ("ImportError", "ModuleNotFoundError"))
        or (isinstance(h.type, ast.Tuple) and any(
            isinstance(e, ast.Name) and e.id in ("ImportError", "ModuleNotFoundError")
            for e in h.type.elts
        ))
        for h in parent.handlers
    )
    if not has_ie:
        return False
    # And the handler must contain at least one non-alarm_app `from X import`.
    for handler in parent.handlers:
        for stmt in ast.walk(handler):
            if isinstance(stmt, ast.ImportFrom) and stmt.module \
                    and not stmt.module.startswith("alarm_app"):
                return True
    return False


def block_text(lines: list[str], node: ast.ImportFrom) -> tuple[int, int, str, str]:
    """Return (start_idx, end_idx_exclusive, indent_str, joined_source) for the
    import statement, where indent_str is the leading whitespace and
    joined_source is the original source with that indent stripped."""
    start = node.lineno - 1
    end = (node.end_lineno or node.lineno) - 1
    raw = lines[start:end + 1]
    indent = raw[0][: len(raw[0]) - len(raw[0].lstrip())]
    # Strip the common indent off each line
    dedented = []
    for line in raw:
        if line.startswith(indent):
            dedented.append(line[len(indent):])
        else:
            dedented.append(line.lstrip())
    return start, end + 1, indent, "".join(dedented)


def make_fallback(original_src: str) -> str:
    """Return the same import source with `alarm_app.` stripped from the module."""
    # Replace only at the start of `from ` segment, but a simple textual swap of
    # `alarm_app.` is safe because that token cannot appear elsewhere in a
    # `from alarm_app.X import Y` statement.
    return original_src.replace("alarm_app.", "")


def process_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as e:
        print(f"  SKIP (syntax error): {path}: {e}")
        return False

    imports = find_alarm_app_imports(tree)
    if not imports:
        return False

    parents = _build_parent_map(tree)
    # Filter out already-wrapped imports (i.e., those already inside a
    # try/except ImportError with a non-alarm_app fallback).
    targets = [n for n in imports if not is_already_wrapped(n, parents)]
    if not targets:
        return False

    # Compute (start, end, indent, src) for each, sorted by start ascending
    spans = []
    for node in targets:
        start, end, indent, src = block_text(lines, node)
        spans.append({"start": start, "end": end, "indent": indent, "src": src})
    spans.sort(key=lambda s: s["start"])

    # Group consecutive top-level (indent == "") spans that are adjacent in the
    # file (only blank/comment lines between them).
    groups: list[list[dict]] = []
    for span in spans:
        if span["indent"] != "":
            # Function-scoped: never merge with siblings (different scopes possible)
            groups.append([span])
            continue
        if groups and groups[-1] and groups[-1][0]["indent"] == "":
            prev = groups[-1][-1]
            # Check that lines between prev["end"] and span["start"] are blank/comment
            between = lines[prev["end"]:span["start"]]
            if all(l.strip() == "" or l.lstrip().startswith("#") for l in between):
                groups[-1].append(span)
                continue
        groups.append([span])

    # Build replacements (start, end_exclusive, new_text) per group
    replacements = []
    for group in groups:
        first = group[0]
        last = group[-1]
        indent = first["indent"]
        # Concatenate source of all imports in the group, preserving any
        # blank/comment lines between them inside the try-block.
        original_chunk = "".join(lines[first["start"]:last["end"]])
        # Dedent the chunk by `indent` for the inner-block source.
        if indent:
            dedented_lines = []
            for line in original_chunk.splitlines(keepends=True):
                if line.startswith(indent):
                    dedented_lines.append(line[len(indent):])
                else:
                    dedented_lines.append(line.lstrip() if line.strip() else line)
            inner_src = "".join(dedented_lines)
        else:
            inner_src = original_chunk
        # Make sure inner_src ends with newline
        if not inner_src.endswith("\n"):
            inner_src += "\n"
        fallback_src = make_fallback(inner_src)

        # Indent inner blocks by 4 spaces under the indent
        def indent_block(s: str, prefix: str) -> str:
            return "".join(
                (prefix + line) if line.strip() else line
                for line in s.splitlines(keepends=True)
            )

        new_text = (
            f"{indent}try:\n"
            f"{indent_block(inner_src, indent + '    ')}"
            f"{indent}except ImportError:\n"
            f"{indent_block(fallback_src, indent + '    ')}"
        )
        replacements.append((first["start"], last["end"], new_text))

    # Apply replacements from end to start
    new_lines = list(lines)
    for start, end, new_text in reversed(replacements):
        new_lines[start:end] = [new_text]

    new_content = "".join(new_lines)
    if new_content == text:
        return False

    # Sanity-check: parse the result
    try:
        ast.parse(new_content, filename=str(path))
    except SyntaxError as e:
        print(f"  ABORT (would produce invalid syntax): {path}: {e}")
        return False

    path.write_text(new_content, encoding="utf-8")
    return True


def main() -> int:
    files = find_affected_files()
    print(f"Found {len(files)} files with 'from alarm_app.' imports")
    modified: list[str] = []
    skipped: list[str] = []
    for fpath in files:
        rel = fpath.relative_to(BASE)
        try:
            changed = process_file(fpath)
        except Exception as e:
            print(f"  ERROR in {rel}: {e}")
            skipped.append(str(rel))
            continue
        if changed:
            modified.append(str(rel))
            print(f"  MODIFIED: {rel}")
        else:
            print(f"  UNCHANGED: {rel}")
    print(f"\nModified {len(modified)} files; skipped {len(skipped)}")
    return 0 if not skipped else 1


if __name__ == "__main__":
    sys.exit(main())
