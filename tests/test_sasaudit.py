def test_count_lines_skips_blank_lines(tmp_path):
    f = tmp_path / "test.sas                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             """"
Tests for sasaudit.py

Run with:
    pytest test_sasaudit.py -v

Requirements:
    pip install pytest pytest-mock
"""

import pytest
from pathlib import Path
from types import SimpleNamespace

from sasaudit import (
    is_binary,
    count_lines_in_file,
    check_oracle_calls,
    check_dependencies,
    create_arguments,
    process_repository,
    REQUIRED_KEYS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_sas(tmp_path, filename, content):
    """Write a .sas file encoded as windows-1252."""
    p = tmp_path / filename
    p.write_bytes(content.encode("windows-1252"))
    return p

def write_text(tmp_path, filename, content):
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# is_binary
# ---------------------------------------------------------------------------

class TestIsBinary:
    def test_text_file_is_not_binary(self, tmp_path):
        f = write_text(tmp_path, "file.py", "print('hello')\n")
        assert is_binary(f) is False

    def test_binary_file_is_binary(self, tmp_path):
        f = tmp_path / "file.bin"
        f.write_bytes(bytes(range(256)))
        assert is_binary(f) is True

    def test_empty_file_is_not_binary(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        assert is_binary(f) is False

    def test_missing_file_returns_true(self, tmp_path):
        f = tmp_path / "nonexistent.txt"
        assert is_binary(f) is True


# ---------------------------------------------------------------------------
# count_lines_in_file
# ---------------------------------------------------------------------------

class TestCountLinesInFile:
    def test_counts_non_blank_lines(self, tmp_path):
        f = write_text(tmp_path, "file.py", "line one\n\nline two\n\n")
        assert count_lines_in_file(f) == 2

    def test_blank_file_returns_zero(self, tmp_path):
        f = write_text(tmp_path, "file.py", "\n\n\n")
        assert count_lines_in_file(f) == 0

    def test_binary_file_returns_zero(self, tmp_path):
        f = tmp_path / "file.bin"
        f.write_bytes(bytes(range(256)))
        assert count_lines_in_file(f) == 0

    def test_sas_skips_comment_lines(self, tmp_path):
        f = write_sas(tmp_path, "file.sas", "/* this is a comment */\nreal line\n")
        assert count_lines_in_file(f) == 1

    def test_sas_counts_non_comment_lines(self, tmp_path):
        content = "proc print data=mydata;\nrun;\n/* comment */\n\n"
        f = write_sas(tmp_path, "file.sas", content)
        assert count_lines_in_file(f) == 2

    def test_sas_skips_blank_lines(self, tmp_path):
        f = write_sas(tmp_path, "file.sas", "\n\ndata x; run;\n")
        assert count_lines_in_file(f) == 1

    def test_non_sas_does_not_skip_comment_lines(self, tmp_path):
        # /* */ comments in a .py file should still be counted
        f = write_text(tmp_path, "file.py", "/* not a sas file */\ncode\n")
        assert count_lines_in_file(f) == 2


# ---------------------------------------------------------------------------
# check_oracle_calls
# ---------------------------------------------------------------------------

class TestCheckOracleCalls:
    def test_detects_libname_oracle(self, tmp_path):
        f = write_sas(tmp_path, "conn.sas", "libname mylib oracle user=foo password=bar;\n")
        assert check_oracle_calls(f) is True

    def test_detects_connect_to_oracle(self, tmp_path):
        f = write_sas(tmp_path, "conn.sas", "connect to oracle (user=foo);\n")
        assert check_oracle_calls(f) is True

    def test_detects_libname_oracle_case_insensitive(self, tmp_path):
        f = write_sas(tmp_path, "conn.sas", "LIBNAME mylib ORACLE user=foo;\n")
        assert check_oracle_calls(f) is True

    def test_no_oracle_returns_false(self, tmp_path):
        f = write_sas(tmp_path, "clean.sas", "proc print data=mydata;\nrun;\n")
        assert check_oracle_calls(f) is False

    def test_unrelated_libname_returns_false(self, tmp_path):
        f = write_sas(tmp_path, "clean.sas", "libname mylib 'some/path';\n")
        assert check_oracle_calls(f) is False


# ---------------------------------------------------------------------------
# check_dependencies
# ---------------------------------------------------------------------------

class TestCheckDependancies:
    def test_detects_percent_macro_call(self, tmp_path):
        write_sas(tmp_path, "shared.sas", "")
        f = write_sas(tmp_path, "main.sas", "%shared;\n")
        result = check_dependencies(f, ["shared"])
        assert "shared" in result

    def test_detects_include_statement(self, tmp_path):
        f = write_sas(tmp_path, "main.sas", "%include 'shared';\n")
        result = check_dependencies(f, ["shared"])
        assert "shared" in result

    def test_detects_call_execute(self, tmp_path):
        f = write_sas(tmp_path, "main.sas", "call execute('%shared');\n")
        result = check_dependencies(f, ["shared"])
        assert "shared" in result

    def test_non_sas_file_returns_empty(self, tmp_path):
        f = write_text(tmp_path, "script.py", "%include 'shared';\n")
        result = check_dependencies(f, ["shared"])
        assert result == ""

    def test_self_reference_is_excluded(self, tmp_path):
        # A file should not list itself as a dependency
        f = write_sas(tmp_path, "main.sas", "%main;\n")
        result = check_dependencies(f, ["main"])
        assert result == ""

    def test_unrelated_filename_not_matched(self, tmp_path):
        f = write_sas(tmp_path, "main.sas", "proc print data=mydata;\nrun;\n")
        result = check_dependencies(f, ["other"])
        assert result == ""

    def test_returns_comma_separated_multiple_deps(self, tmp_path):
        f = write_sas(tmp_path, "main.sas", "%alpha;\n%beta;\n")
        result = check_dependencies(f, ["alpha", "beta"])
        deps = [d.strip() for d in result.split(",")]
        assert "alpha" in deps
        assert "beta" in deps


# ---------------------------------------------------------------------------
# create_arguments
# ---------------------------------------------------------------------------

class TestCreateArguments:
    def test_repo_config_overrides_defaults(self):
        defaults = {"output": "./out", "business_process": "Default"}
        config = {"source": "/some/path", "business_process": "Estimation"}
        args = create_arguments("MyRepo", config, defaults)
        assert args.business_process == "Estimation"

    def test_defaults_fill_in_missing_repo_keys(self):
        defaults = {"output": "./out", "business_process": "Default"}
        config = {"source": "/some/path"}
        args = create_arguments("MyRepo", config, defaults)
        assert args.business_process == "Default"

    def test_required_keys_default_to_none(self):
        args = create_arguments("MyRepo", {"source": "/some/path"}, {})
        for key in REQUIRED_KEYS:
            assert hasattr(args, key), f"Missing key: {key}"

    def test_name_is_set_from_repo_name(self):
        args = create_arguments("MyRepo", {"source": "/some/path"}, {})
        assert args.name == "MyRepo"

    def test_output_is_converted_to_path(self):
        args = create_arguments("MyRepo", {"source": "/p", "output": "./out"}, {})
        assert isinstance(args.output, Path)

    def test_arbitrary_metadata_keys_are_preserved(self):
        config = {"source": "/p", "cost_center": "739", "custom_field": "hello"}
        args = create_arguments("MyRepo", config, {})
        assert args.cost_center == "739"
        assert args.custom_field == "hello"


# ---------------------------------------------------------------------------
# process_repository
# ---------------------------------------------------------------------------

class TestProcessRepository:
    def test_counts_files_in_directory(self, tmp_path):
        write_text(tmp_path, "script.py", "line one\nline two\n")
        df = process_repository(tmp_path)
        assert len(df) == 1
        assert df.iloc[0]["Line Count"] == 2

    def test_skips_blank_only_files(self, tmp_path):
        write_text(tmp_path, "empty.py", "\n\n\n")
        df = process_repository(tmp_path)
        assert len(df) == 0

    def test_skips_hidden_files(self, tmp_path):
        write_text(tmp_path, ".hidden", "some content\n")
        df = process_repository(tmp_path)
        assert len(df) == 0

    def test_excludes_patterns(self, tmp_path):
        write_text(tmp_path, "script.py", "code\n")
        write_text(tmp_path, "script.for", "fortran\n")
        df = process_repository(tmp_path, excluded_patterns=["*.for"])
        assert all(r["File Name"] != "script.for" for _, r in df.iterrows())

    def test_extension_column_is_lowercase(self, tmp_path):
        write_text(tmp_path, "script.PY", "code\n")
        df = process_repository(tmp_path)
        assert df.iloc[0]["Extension"] == ".py"

    def test_directory_column_is_relative(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        write_text(subdir, "script.py", "code\n")
        df = process_repository(tmp_path)
        assert df.iloc[0]["Directory"] == "subdir"

    # --- Bug #7 regression test ---
    def test_oracle_calls_cross_repo_uses_dependency_names_not_chars(self, tmp_path):
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        write_sas(shared_dir, "oracle_macro.sas", "libname mylib oracle user=foo;\n")

        main_dir = tmp_path / "main"
        main_dir.mkdir()
        write_sas(main_dir, "main.sas", "%oracle_macro;\n")

        extra_deps = {p.stem: True for p in shared_dir.rglob("*.sas")}

        df = process_repository(main_dir, extra_deps)
        # main.sas depends on oracle_macro, which has Oracle calls
        # The Oracle Calls flag should be True 
        row = df[df["File Name"] == "main.sas"]
        assert not row.empty
        assert row.iloc[0]["Oracle Calls"] is True