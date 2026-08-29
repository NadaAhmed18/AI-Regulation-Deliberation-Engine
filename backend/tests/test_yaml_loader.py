"""
TEST: YAML Loader Validation

Covers the validation contract of `load_persona()`:
    - A well-formed persona file loads successfully.
    - A missing required field raises ValueError.
    - A required field with the wrong type raises ValueError.
    - A required field that is an empty/whitespace-only string raises ValueError.
    - A malformed `priorities`/`expertise` list raises ValueError.
    - Syntactically invalid YAML raises ValueError (not a raw yaml.YAMLError).
    - A nonexistent file raises FileNotFoundError.

Plain `assert`-based `test_*` functions: discoverable by `pytest`, and also
runnable standalone with no extra dependency. Run as a module from the
`backend/` root — relative imports work natively, no `sys.path` hacks needed:

    python -m tests.test_yaml_loader
"""

import tempfile
from pathlib import Path

from src.utils.yaml_loader import load_persona

VALID_PERSONA_PATH = Path("personas/persona_a.yaml")


def _write_temp_yaml(content: str) -> Path:
    """Write `content` to a temp .yaml file and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    )
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


def test_valid_persona_loads_successfully():
    persona = load_persona(VALID_PERSONA_PATH)
    assert persona["name"]
    assert persona["background"]
    assert persona["stance"]
    assert persona["tone"]


def test_missing_required_field_raises_value_error():
    path = _write_temp_yaml(
        "name: 'Test Persona'\n"
        "background: 'Some background.'\n"
        "tone: 'Neutral.'\n"
        # 'stance' is intentionally missing
    )
    try:
        raised = False
        try:
            load_persona(path)
        except ValueError as e:
            raised = True
            assert "stance" in str(e)
        assert raised, "Expected ValueError for missing required field."
    finally:
        path.unlink()


def test_non_string_required_field_raises_value_error():
    path = _write_temp_yaml(
        "name: 'Test Persona'\n"
        "background: 'Some background.'\n"
        "stance: 123\n"  # invalid: must be a string
        "tone: 'Neutral.'\n"
    )
    try:
        raised = False
        try:
            load_persona(path)
        except ValueError as e:
            raised = True
            assert "stance" in str(e)
        assert raised, "Expected ValueError for non-string required field."
    finally:
        path.unlink()


def test_empty_string_required_field_raises_value_error():
    path = _write_temp_yaml(
        "name: 'Test Persona'\n"
        "background: '   '\n"  # whitespace-only: invalid
        "stance: 'Pro-Innovation'\n"
        "tone: 'Direct.'\n"
    )
    try:
        raised = False
        try:
            load_persona(path)
        except ValueError as e:
            raised = True
            assert "background" in str(e)
        assert raised, "Expected ValueError for empty/whitespace-only field."
    finally:
        path.unlink()


def test_invalid_optional_list_field_raises_value_error():
    path = _write_temp_yaml(
        "name: 'Test Persona'\n"
        "background: 'Some background.'\n"
        "stance: 'Pro-Innovation'\n"
        "tone: 'Direct.'\n"
        "priorities: 'not a list'\n"  # invalid: must be list[str]
    )
    try:
        raised = False
        try:
            load_persona(path)
        except ValueError as e:
            raised = True
            assert "priorities" in str(e)
        assert raised, "Expected ValueError for malformed 'priorities' field."
    finally:
        path.unlink()


def test_invalid_yaml_syntax_raises_value_error():
    path = _write_temp_yaml(
        "name: 'Unclosed string\n"
        "background: [this is not valid: yaml\n"
    )
    try:
        raised = False
        try:
            load_persona(path)
        except ValueError:
            raised = True
        assert raised, "Expected ValueError for syntactically invalid YAML."
    finally:
        path.unlink()


def test_nonexistent_file_raises_file_not_found_error():
    raised = False
    try:
        load_persona(Path("personas/does_not_exist.yaml"))
    except FileNotFoundError:
        raised = True
    assert raised, "Expected FileNotFoundError for a nonexistent persona file."


def _run_all_tests():
    tests = [
        test_valid_persona_loads_successfully,
        test_missing_required_field_raises_value_error,
        test_non_string_required_field_raises_value_error,
        test_empty_string_required_field_raises_value_error,
        test_invalid_optional_list_field_raises_value_error,
        test_invalid_yaml_syntax_raises_value_error,
        test_nonexistent_file_raises_file_not_found_error,
    ]
    for test_fn in tests:
        test_fn()
        print(f"{test_fn.__name__}")
    print("\nAll yaml_loader validation tests passed.")


if __name__ == "__main__":
    _run_all_tests()
