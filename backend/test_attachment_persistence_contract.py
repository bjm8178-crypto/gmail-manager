"""Regression test for attachment metadata persistence contract.

This test intentionally reads the source AST instead of importing database.py or
main.py, so it cannot initialize PostgreSQL during collection.
"""
from __future__ import annotations

import ast
from pathlib import Path


DATABASE_SOURCE = Path(__file__).with_name("database.py")
REQUIRED_ATTACHMENT_FIELDS = {"attachment_risk", "attachment_details"}


def _function(source: ast.Module, name: str) -> ast.FunctionDef:
    for node in source.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"Function not found: {name}")


def _analysis_fields(source: ast.Module) -> set[str]:
    for node in source.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "_ANALYSIS_FIELDS"
                   for target in node.targets):
                value = node.value
                if isinstance(value, (ast.Tuple, ast.List)):
                    return {
                        element.value
                        for element in value.elts
                        if isinstance(element, ast.Constant) and isinstance(element.value, str)
                    }
    raise AssertionError("_ANALYSIS_FIELDS definition not found")


def _has_attachment_zip_mapping(function: ast.FunctionDef) -> bool:
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "zip" or len(node.args) < 2:
            continue
        values = node.args[1]
        if not isinstance(values, ast.Tuple):
            continue
        names = {
            element.id for element in values.elts
            if isinstance(element, ast.Name)
        }
        if REQUIRED_ATTACHMENT_FIELDS <= names:
            return True
    return False


def test_attachment_fields_are_in_persistence_contract_without_database_import():
    source = ast.parse(DATABASE_SOURCE.read_text(encoding="utf-8"))

    assert REQUIRED_ATTACHMENT_FIELDS <= _analysis_fields(source)

    for function_name in ("save_analyzed_email", "update_analyzed_email"):
        function = _function(source, function_name)
        keyword_only_names = {arg.arg for arg in function.args.kwonlyargs}
        assert REQUIRED_ATTACHMENT_FIELDS <= keyword_only_names
        assert _has_attachment_zip_mapping(function), (
            f"{function_name} must map attachment fields into metadata persistence"
        )
