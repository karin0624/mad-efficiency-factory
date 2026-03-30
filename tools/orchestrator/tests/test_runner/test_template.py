"""Tests for runner/template.py — template resolution engine."""

from tools.orchestrator.runner.template import (
    evaluate_condition,
    resolve,
    resolve_dict,
)


class TestResolve:
    def test_simple_variable(self):
        assert resolve("{{ foo }}", {"foo": "bar"}) == "bar"

    def test_no_whitespace(self):
        assert resolve("{{foo}}", {"foo": "bar"}) == "bar"

    def test_extra_whitespace(self):
        assert resolve("{{  foo  }}", {"foo": "bar"}) == "bar"

    def test_multiple_variables(self):
        result = resolve("{{ a }}/{{ b }}", {"a": "x", "b": "y"})
        assert result == "x/y"

    def test_mixed_text_and_vars(self):
        result = resolve("path/{{ dir }}/file.md", {"dir": "specs"})
        assert result == "path/specs/file.md"

    def test_dotted_access(self):
        variables = {"result": {"bar": "baz"}}
        assert resolve("{{ result.bar }}", variables) == "baz"

    def test_nested_dotted_access(self):
        variables = {"a": {"b": {"c": "deep"}}}
        assert resolve("{{ a.b.c }}", variables) == "deep"

    def test_missing_variable_returns_literal(self):
        assert resolve("{{ missing }}", {}) == "missing"

    def test_no_template(self):
        assert resolve("plain text", {}) == "plain text"

    def test_empty_string(self):
        assert resolve("", {}) == ""

    def test_integer_value(self):
        assert resolve("{{ num }}", {"num": 42}) == "42"

    def test_bool_value(self):
        assert resolve("{{ flag }}", {"flag": True}) == "True"

    def test_in_expression_list(self):
        variables = {"x": "a1", "RUN_A1": ["a1-what", "a1"]}
        assert resolve("{{ x in RUN_A1 }}", variables) == "True"

    def test_in_expression_not_found(self):
        variables = {"x": "b1", "RUN_A1": ["a1-what", "a1"]}
        assert resolve("{{ x in RUN_A1 }}", variables) == "False"

    def test_in_expression_string(self):
        variables = {"x": "a1", "RUN_A1": "a1-what,a1"}
        assert resolve("{{ x in RUN_A1 }}", variables) == "True"

    def test_not_expression(self):
        variables = {"flag": False}
        assert resolve("{{ not flag }}", variables) == "True"

    def test_not_expression_true(self):
        variables = {"flag": True}
        assert resolve("{{ not flag }}", variables) == "False"


class TestEvaluateCondition:
    def test_empty_is_true(self):
        assert evaluate_condition("", {}) is True

    def test_none_is_true(self):
        assert evaluate_condition("", {}) is True

    def test_true_string(self):
        assert evaluate_condition("{{ flag }}", {"flag": True}) is True

    def test_false_string(self):
        assert evaluate_condition("{{ flag }}", {"flag": False}) is False

    def test_truthy_value(self):
        assert evaluate_condition("{{ x }}", {"x": "something"}) is True

    def test_none_value(self):
        assert evaluate_condition("{{ x }}", {"x": None}) is False

    def test_in_expression(self):
        variables = {"resume_point": "a1-what", "RUN_A1": ["a1-what", "a1"]}
        assert evaluate_condition("{{ resume_point in RUN_A1 }}", variables) is True

    def test_in_expression_false(self):
        variables = {"resume_point": "b2", "RUN_A1": ["a1-what", "a1"]}
        assert evaluate_condition("{{ resume_point in RUN_A1 }}", variables) is False


class TestResolveDict:
    def test_resolves_all_values(self):
        result = resolve_dict(
            {"A": "{{ x }}", "B": "{{ y }}"},
            {"x": "1", "y": "2"},
        )
        assert result == {"A": "1", "B": "2"}

    def test_mixed_literal_and_template(self):
        result = resolve_dict(
            {"path": "/home/{{ user }}/work"},
            {"user": "alice"},
        )
        assert result == {"path": "/home/alice/work"}
