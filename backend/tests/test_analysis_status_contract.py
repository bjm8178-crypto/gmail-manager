import ast
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "gmail.py").read_text(encoding="utf-8")


def _load():
    tree = ast.parse(SOURCE)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "_final_analysis_status")
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "gmail.py", "exec"), ns)
    return ns["_final_analysis_status"]


def test_router_complete_becomes_completed():
    f = _load()
    assert f("complete", False, 5) == "completed"
    assert f("completed", False, 5) == "completed"


def test_anything_incomplete_is_partial():
    f = _load()
    assert f("complete", True, 5) == "partial"
    assert f("complete", False, None) == "partial"
    assert f("partial", False, 5) == "partial"
    assert f("unavailable", False, 5) == "partial"


def test_pipeline_uses_helper():
    assert "analysis_status = _final_analysis_status(" in SOURCE
    assert 'if analysis_status != "completed" or url_scan_unavailable' not in SOURCE
