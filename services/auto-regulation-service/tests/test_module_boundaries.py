"""
Architecture guard: enforce vertical-module boundaries.

Each module under ``app/modules/<name>/`` exposes a single public interface via
its package ``__init__`` (the facade). Other modules must import only that
facade — never another module's internal submodules.

The one sanctioned exception: the ``ml`` module keeps its facade intentionally
light so importing it does not eagerly pull in optional heavy ML libraries
(LightGBM / TensorFlow). Callers therefore import ``ml``'s heavy pieces lazily,
inside a function/``try`` block, guarded by an availability check. Those lazy
(indented) imports of ``app.modules.ml.*`` are allowed; top-level ones are not.
"""
import ast
from pathlib import Path

MODULES_ROOT = Path(__file__).resolve().parents[1] / "app" / "modules"

# Modules whose heavy internals may be imported lazily (function-level) from
# other modules because of optional-dependency graceful degradation.
LAZY_INTERNAL_IMPORT_ALLOWED = {"ml"}


def _owning_module(path: Path) -> str:
    return path.relative_to(MODULES_ROOT).parts[0]


def _cross_module_internal_imports(path: Path, owner: str):
    """Yield (lineno, target, is_lazy) for imports of another module's submodule."""
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        parts = node.module.split(".")
        # match app.modules.<other>.<submodule> (depth >= 4 == reaching past the facade)
        if parts[:2] != ["app", "modules"] or len(parts) < 4:
            continue
        target_module = parts[2]
        if target_module == owner:
            continue  # intra-module direct import is fine
        is_lazy = node.col_offset > 0  # indented == nested in function/try/if
        yield node.lineno, node.module, target_module, is_lazy


def test_no_top_level_cross_module_internal_imports():
    offenders = []
    for path in MODULES_ROOT.rglob("*.py"):
        owner = _owning_module(path)
        for lineno, module, target, is_lazy in _cross_module_internal_imports(path, owner):
            allowed = is_lazy and target in LAZY_INTERNAL_IMPORT_ALLOWED
            if not allowed:
                offenders.append(
                    f"{path.relative_to(MODULES_ROOT.parent.parent)}:{lineno} "
                    f"[{owner}] imports internal '{module}' "
                    f"({'lazy' if is_lazy else 'top-level'})"
                )
    assert not offenders, (
        "Cross-module internal imports detected — import the module's facade "
        "(app.modules.<name>) instead:\n  " + "\n  ".join(offenders)
    )
