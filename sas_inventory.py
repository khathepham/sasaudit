import argparse
import re
import tempfile
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

import pandas as pd
from git import Repo

from sas_description_parser import extract_description, NO_DESCRIPTION


# --- Configuration ---

@dataclass
class RepoConfig:
    name: str
    source: str
    output: Path
    branch: str | None = None
    extra_dependencies: list = field(default_factory=list)
    exclude: list = field(default_factory=list)
    parse_description: bool = False
    extra: dict = field(default_factory=dict)  # arbitrary TOML keys injected as metadata columns

_REPO_CONFIG_KEYS = {f.name for f in fields(RepoConfig) if f.name != 'extra'}


# --- Constants ---

TEXT_CHARS = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})

_MACRO_COMMENT_RE = re.compile(r'%\*[^;]*;')
_PROC_RE = re.compile(r'(?i)\bPROC\s+(\w+)')
_LIBNAME_VALID_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,7}$')
_LIBNAME_STMT_RE = re.compile(r'(?i)\bLIBNAME\s+(\w+)\s*(\w*)\s*(.*?)(?:;|$)')
_MACRO_PARAM_RE = re.compile(r'(?i)\b(mLibname|mLibrary|mLib|mSchema|mDatabase)\s*=\s*([^\s,);]+)')
_MACRO_DEF_RE = re.compile(r'(?i)%MACRO\s+(\w+)')
_MACRO_CALL_RE = re.compile(r'%([A-Za-z_]\w*)')
_TRIGGER_KWS_RE = re.compile(r'(?i)\b(DATA|SET|MERGE|UPDATE|FROM)\b')
_LIBDS_RE = re.compile(r'(?i)\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b')
_VALID_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_ORACLE_LIBNAME_RE = re.compile(r'(?i)libname\s+\w+\s+oracle\b')

_MACRO_KEYWORDS = {
    'MACRO', 'MEND', 'LET', 'IF', 'THEN', 'ELSE', 'DO', 'END', 'TO', 'BY',
    'UNTIL', 'WHILE', 'GOTO', 'RETURN', 'GLOBAL', 'LOCAL', 'PUT', 'INCLUDE',
    'ABORT', 'STR', 'NRSTR', 'QUOTE', 'NRQUOTE', 'BQUOTE', 'NRBQUOTE',
    'UNQUOTE', 'SUPERQ', 'EVAL', 'SYSEVALF', 'SYSFUNC', 'SYSCALL',
    'SUBSTR', 'SCAN', 'UPCASE', 'LOWCASE', 'INDEX', 'LENGTH', 'TRIM',
    'LEFT', 'RIGHT', 'COMPRESS', 'STRIP', 'TRANWRD', 'TRANSLATE',
    'CAT', 'CATS', 'CATT', 'CATX', 'OPEN', 'CLOSE', 'EXIST', 'VARNUM',
    'QTRIM', 'NLITERAL', 'KSTRIP', 'KCMPRES',
}


# --- File Utilities ---

def is_binary(path: Path) -> bool:
    """Check if a file is binary by inspecting the first kilobyte."""
    try:
        with path.open('rb') as f:
            return bool(f.read(1024).translate(None, TEXT_CHARS))
    except Exception:
        return True


def count_lines_in_file(path: Path) -> int:
    """Counts non-blank lines. Excludes SAS comments if applicable."""
    if is_binary(path):
        return 0
    ext = path.suffix.lower()
    enc = "windows-1252" if ext == ".sas" else "utf-8"
    try:
        lines = path.read_text(encoding=enc, errors="ignore").splitlines()
        if ext == ".sas":
            return sum(1 for l in lines if (s := l.strip()) and not s.startswith("/*"))
        return sum(1 for l in lines if l.strip())
    except Exception:
        return 0


def strip_sas_comments(lines: list) -> list:
    """
    Returns (line_num, cleaned_line) pairs with SAS comments removed.
    Handles /* ... */ block comments (including multi-line),
    %* ... ; macro-style comments, and leading * ... ; star comments.
    """
    result = []
    in_block_comment = False

    for i, line in enumerate(lines, start=1):
        cleaned = line.replace('\r', '').strip()

        # Continue stripping inside a block comment
        if in_block_comment:
            if '*/' in cleaned:
                in_block_comment = False
                cleaned = cleaned[cleaned.index('*/') + 2:].strip()
            else:
                continue

        # Strip %* ... ; macro-style comments
        while True:
            m = _MACRO_COMMENT_RE.search(cleaned)
            if m:
                cleaned = (cleaned[:m.start()] + ' ' + cleaned[m.end():]).strip()
            else:
                break

        # Strip /* ... */ inline/block comments iteratively
        while '/*' in cleaned:
            start = cleaned.index('/*')
            end_rel = cleaned[start + 2:].find('*/')
            if end_rel >= 0:
                cleaned = (cleaned[:start] + ' ' + cleaned[start + 2 + end_rel + 2:]).strip()
            else:
                cleaned = cleaned[:start].strip()
                in_block_comment = True
                break

        cleaned = cleaned.strip()

        if not cleaned or cleaned.startswith('*'):
            continue

        result.append((i, cleaned))

    return result


# --- SAS Analyzers ---

def find_procs(cleaned_lines: list) -> list:
    """Returns list of {'proc_name', 'line_num'} dicts."""
    results = []
    for line_num, clean in cleaned_lines:
        m = _PROC_RE.search(clean)
        if m:
            results.append({'proc_name': m.group(1).upper(), 'line_num': line_num})
    return results


def find_libnames(cleaned_lines: list) -> list:
    """
    Returns list of {'libname', 'engine', 'path', 'source_type', 'line_num'} dicts.
    Detects both direct LIBNAME statements and macro parameter assignments
    (mLibname=, mLibrary=, mLib=, mSchema=, mDatabase=).
    """
    results = []
    for line_num, clean in cleaned_lines:
        # Direct LIBNAME statement
        m = _LIBNAME_STMT_RE.search(clean)
        if m:
            libname = m.group(1)
            engine   = m.group(2).strip()
            if _LIBNAME_VALID_RE.match(libname) and libname.upper() != 'LIBNAME' and engine.upper() != 'CLEAR':
                path_val = m.group(3).strip().strip('"\';').strip()
                results.append({
                    'libname': libname,
                    'engine': engine,
                    'path': path_val,
                    'source_type': 'LIBNAME',
                    'line_num': line_num,
                })

        # Macro parameter libnames — skip %let assignments
        if '%let' not in clean.lower():
            for mp in _MACRO_PARAM_RE.finditer(clean):
                libname = mp.group(2).strip('"\' ')
                if _LIBNAME_VALID_RE.match(libname):
                    results.append({
                        'libname': libname,
                        'engine': 'MACRO_PARAM',
                        'path': 'Assigned via macro parameter',
                        'source_type': 'MACRO_PARAM',
                        'line_num': line_num,
                    })

    return results


def find_macro_defs(cleaned_lines: list) -> list:
    """Returns list of {'macro_name', 'line_num'} dicts for %macro definitions."""
    results = []
    for line_num, clean in cleaned_lines:
        m = _MACRO_DEF_RE.search(clean)
        if m:
            results.append({'macro_name': m.group(1), 'line_num': line_num})
    return results


def find_macro_calls(cleaned_lines: list) -> list:
    """
    Returns list of {'macro_name', 'line_num'} dicts for user-defined macro calls.
    Excludes SAS built-in macro keywords and functions.
    """
    results = []
    for line_num, clean in cleaned_lines:
        for m in _MACRO_CALL_RE.finditer(clean):
            name = m.group(1)
            if name.upper() not in _MACRO_KEYWORDS:
                results.append({'macro_name': name, 'line_num': line_num})
    return results


def find_dataset_refs(cleaned_lines: list) -> list:
    """
    Returns list of {'library', 'dataset', 'ref_type', 'line_num'} dicts.
    Detects lib.dataset notation in DATA, SET, MERGE, UPDATE, and FROM contexts.
    """
    results = []
    for line_num, clean in cleaned_lines:
        kw_match = _TRIGGER_KWS_RE.search(clean)
        if not kw_match:
            continue

        ref_type = kw_match.group(1).upper()
        for m in _LIBDS_RE.finditer(clean):
            library = m.group(1)
            dataset = m.group(2)
            if _VALID_NAME_RE.match(library) and _VALID_NAME_RE.match(dataset):
                results.append({
                    'library': library,
                    'dataset': dataset,
                    'ref_type': ref_type,
                    'line_num': line_num,
                })
    return results


def find_dependencies(cleaned_lines: list, filenames_to_check: list, stem: str = '') -> str:
    """Returns comma-separated dependency names found in the cleaned lines."""
    filenames_cf = [(d, d.casefold()) for d in filenames_to_check]
    dependency_set = set()
    for _, clean in cleaned_lines:
        clean_cf = clean.casefold()
        has_include = 'include' in clean_cf
        has_call_execute = 'call execute' in clean_cf
        for d, d_cf in filenames_cf:
            index_pos = clean_cf.find(d_cf)
            if index_pos != -1:
                if (index_pos > 0 and clean[index_pos - 1] == '%') or \
                   has_include or has_call_execute:
                    dependency_set.add(d)
    dependency_set.discard(stem)
    return ", ".join(map(str, dependency_set))


def check_oracle_calls(cleaned_lines: list) -> bool:
    """Returns True if the file contains Oracle LIBNAME or CONNECT TO ORACLE."""
    for _, clean in cleaned_lines:
        if 'connect to oracle' in clean.lower() or _ORACLE_LIBNAME_RE.search(clean):
            return True
    return False


def parse_sas_file(path: Path, filenames_to_check: list = None, parse_description: bool = False) -> dict:
    """
    Reads a SAS file once, strips comments once, and runs all checks.
    Returns a dict with keys: procs, libnames, macro_defs, macro_calls,
    dataset_refs, dependencies, oracle_calls, description.
    """
    empty = {
        'procs': [], 'libnames': [], 'macro_defs': [],
        'macro_calls': [], 'dataset_refs': [], 'dependencies': '',
        'oracle_calls': False, 'description': NO_DESCRIPTION,
        'line_count': 0
    }
    if path.suffix.lower() != '.sas':
        return empty
    try:
        raw_lines = path.read_text(encoding='windows-1252', errors='ignore').splitlines()
    except Exception:
        return empty

    cleaned = strip_sas_comments(raw_lines)
    line_count = sum(1 for l in raw_lines if (s := l.strip()) and not s.startswith("/*"))

    return {
        'procs':        find_procs(cleaned),
        'libnames':     find_libnames(cleaned),
        'macro_defs':   find_macro_defs(cleaned),
        'macro_calls':  find_macro_calls(cleaned),
        'dataset_refs': find_dataset_refs(cleaned),
        'dependencies': find_dependencies(cleaned, filenames_to_check or [], path.stem),
        'oracle_calls': check_oracle_calls(cleaned),
        'description':  extract_description(raw_lines) if parse_description else NO_DESCRIPTION,
        'line_count':   line_count
    }


# --- Repository Processing ---

def _has_oracle_calls(path: Path) -> bool:
    """Quick check for Oracle calls without running full SAS analysis."""
    try:
        raw_lines = path.read_text(encoding='windows-1252', errors='ignore').splitlines()
    except Exception:
        return False
    return check_oracle_calls(strip_sas_comments(raw_lines))


def get_extra_dependencies(extra_dependency_paths: list) -> dict:
    """Clones/reads extra repos and returns {stem: has_oracle_calls} for each SAS file."""
    extra_dependencies = {}
    if not extra_dependency_paths:
        return {}
    for d in extra_dependency_paths:
        source_path = Path(d)
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_path = source_path
            if not source_path.is_dir():
                try:
                    Repo.clone_from(d, tmp_dir)
                    working_path = Path(tmp_dir)
                except Exception as e:
                    print("Unable to get dependencies for {}.\nError: {}".format(d, e))
                    continue
            paths = [
                fp for fp in working_path.rglob('*')
                if fp.is_file() and not any(p.startswith('.') for p in fp.parts)
                and fp.suffix.lower() == ".sas"
            ]
            extra_dependencies.update({p.stem: _has_oracle_calls(p) for p in paths})

    return extra_dependencies


def process_repository(root_path: Path, extra_dependency_paths: list = None, excluded_patterns: list = None, parse_description: bool = False) -> dict:
    """Walks directory, analyzes each file, and returns a dict of DataFrames."""
    print("Processing Repository...")
    records = []
    proc_records = []
    libname_records = []
    macro_def_records = []
    macro_call_records = []
    dataset_ref_records = []
    dataset_catalog_records = []

    all_files = [
        fp for fp in root_path.rglob('*')
        if fp.is_file() and not any(p.startswith('.') for p in fp.parts)
        and (not excluded_patterns or not any(fp.match(pat) for pat in excluded_patterns))
    ]
    filenames = [fp.stem for fp in all_files if fp.suffix.lower() == ".sas"]
    extra_dependencies = get_extra_dependencies(extra_dependency_paths if extra_dependency_paths else [])
    filenames.extend(extra_dependencies.keys())

    sub_record_lists = {
        'procs': proc_records,
        'libnames': libname_records,
        'macro_defs': macro_def_records,
        'macro_calls': macro_call_records,
        'dataset_refs': dataset_ref_records,
    }

    for file_path in all_files:
        suffix = file_path.suffix.lower()
        file_name = file_path.name
        directory = str(file_path.parent.relative_to(root_path))

        if suffix in (".sas7bcat", ".sas7bdat"):
            dataset_catalog_records.append({
                "File Name": file_name,
                "Directory": directory,
                "Type": suffix,
            })
            continue

        parsed = parse_sas_file(file_path, filenames, parse_description)
        count = parsed['line_count'] if suffix == '.sas' else count_lines_in_file(file_path)
        if count == 0:
            continue

        dependencies = parsed['dependencies']
        oracle_calls = parsed['oracle_calls'] or any(
            extra_dependencies.get(d, False) for d in dependencies.split(", ") if dependencies
        )

        records.append({
            "File Name": file_name,
            "Extension": suffix or "no_ext",
            "Directory": directory,
            "Line Count": count,
            "Dependencies": dependencies,
            "Oracle Calls": oracle_calls,
            "Description": parsed['description']
        })

        for key, record_list in sub_record_lists.items():
            for r in parsed[key]:
                record_list.append({"File Name": file_name, "Directory": directory, **r})

    return {
        'files':        pd.DataFrame(records),
        'procs':        pd.DataFrame(proc_records),
        'libnames':     pd.DataFrame(libname_records),
        'macro_defs':   pd.DataFrame(macro_def_records),
        'macro_calls':  pd.DataFrame(macro_call_records),
        'dataset_refs': pd.DataFrame(dataset_ref_records),
        'dataset_catalog': pd.DataFrame(dataset_catalog_records),
    }


def export_results(data: dict, args):
    """Generates Excel workbook."""
    print("Exporting: {}".format(args.name))
    args.output.mkdir(parents=True, exist_ok=True)

    df = data['files']

    is_sas = df['Extension'].eq('.sas')
    df_ext = df.groupby("Extension")["Line Count"].sum().reset_index()
    df_dir = df.assign(
        is_sas=is_sas.astype(int),
        is_not_sas=(~is_sas).astype(int),
    ).groupby("Directory")[["Directory", "Line Count", "is_sas", "is_not_sas"]].apply(lambda x: pd.Series({
        "SAS Count": (x["is_sas"] * x['Line Count']).sum(),
        "Non-SAS Count": (x["is_not_sas"] * x['Line Count']).sum(),
        "Total Count": x['Line Count'].sum()
    })).reset_index()
    df_files = df.drop("Extension", axis=1)

    df_summary = pd.DataFrame([
        {"Metric": "Total SAS Lines",     "Value": int(df.loc[is_sas, "Line Count"].sum())},
        {"Metric": "Total Non-SAS Lines", "Value": int(df.loc[~is_sas, "Line Count"].sum())},
        {"Metric": "Grand Total",         "Value": int(df["Line Count"].sum())},
    ])

    xlsx_path = args.output / f"{args.name}_audit.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Summary", index=False)
        df_files.to_excel(writer, sheet_name="File Details", index=False)
        df_ext.to_excel(writer, sheet_name="Extension Summary", index=False)
        df_dir.to_excel(writer, sheet_name="Directory Summary", index=False)
        data['procs'].to_excel(writer, sheet_name="PROC Usage", index=False)
        data['libnames'].to_excel(writer, sheet_name="Libname References", index=False)
        data['macro_defs'].to_excel(writer, sheet_name="Macro Definitions", index=False)
        data['macro_calls'].to_excel(writer, sheet_name="Macro Calls", index=False)
        data['dataset_refs'].to_excel(writer, sheet_name="Dataset References", index=False)
        data['dataset_catalog'].to_excel(writer, sheet_name="SAS Datasets & Catalogs", index=False)


# --- Orchestration ---

def create_repo_config(repo_name, config, defaults) -> RepoConfig:
    """Builds a RepoConfig from TOML config, merging in defaults."""
    merged = {**defaults, **config, "name": repo_name}
    if merged.get('output'):
        merged['output'] = Path(merged['output'])
    known = {k: merged[k] for k in _REPO_CONFIG_KEYS if k in merged}
    extra = {k: v for k, v in merged.items() if k not in _REPO_CONFIG_KEYS}
    return RepoConfig(**known, extra=extra)


def process_single_repo(args: RepoConfig):
    """Handles logic for a single repository source."""
    source_path = Path(args.source)

    with tempfile.TemporaryDirectory() as tmp_dir:
        working_path = source_path
        if not source_path.is_dir():
            try:
                print(f"Cloning: {args.source}")
                repo = Repo.clone_from(args.source, tmp_dir)
                if args.branch:
                    repo.git.checkout(args.branch)
                working_path = Path(tmp_dir)
            except Exception as e:
                print(f"Error: {e}")
                return

        data = process_repository(working_path, args.extra_dependencies, args.exclude, args.parse_description)

        # Inject name + any extra TOML metadata into the file-level sheet only
        for col, val in {"name": args.name, **args.extra}.items():
            data['files'][col] = val

        export_results(data, args)
        print(f"Success! Reports for: {args.name}")


def process_batch(toml_file: str):
    """Processes multiple repos from a TOML configuration."""
    with open(toml_file, "rb") as f:
        toml_data = tomllib.load(f)

    defaults = toml_data.get("defaults", {})

    for repo_name, config in toml_data.get("repo", {}).items():
        args = create_repo_config(repo_name, config, defaults)
        process_single_repo(args)


def main():
    parser = argparse.ArgumentParser(description="SAS Inventory")
    parser.add_argument("batch", help="Path to TOML for batch processing")
    args = parser.parse_args()
    process_batch(args.batch)


if __name__ == "__main__":
    main()