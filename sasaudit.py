import argparse
import tempfile
import tomllib
from pathlib import Path

import pandas as pd
from git import Repo
from markdown_it import MarkdownIt
from weasyprint import HTML, CSS
from tabulate import tabulate
from types import SimpleNamespace
import re


# --- Configuration & Templates ---
TEXT_CHARS = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
CSS_PATH = Path("./style.css")
STYLESHEET = [CSS(filename=str(CSS_PATH))] if CSS_PATH.exists() else []


MD_FORMAT = """# {}
## Line Count by Extension
{}
{}
## Line Count by Directory
{}
"""
REQUIRED_KEYS = ["name", "source", "branch", "output", "extra_dependencies", "exclude"]

# --- Utility Functions ---

def is_binary(path: Path) -> bool:
    """Check if file is binary by inspecting the first kilobyte."""
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

def check_dependencies(path: Path, filenames_to_check: list) -> str:
    dependency_set = set()
    try:
        if path.suffix.lower() != ".sas":
            return ""
        with open(path, 'r', encoding="windows-1252") as f:
            for line in f:
                for d in filenames_to_check:
                    index_pos = line.casefold().find(d.casefold())
                    if index_pos != -1:
                        # check if there is %, %include or call execute then add to dependency list
                        if '%' == line[index_pos - 1] or 'include' in line.lower() or 'call execute' in line.lower():
                            dependency_set.add(d)
        dependency_set.discard(path.stem)
        return ", ".join(map(str, dependency_set))
    except:
        return ""

def get_extra_dependencies(extra_dependency_paths: list) -> dict:
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
                fp for fp in working_path.rglob('*') if fp.is_file() and not any(p.startswith('.') for p in fp.parts) and fp.suffix.lower() == ".sas"
            ]
            extra_dependencies = {path.stem: check_oracle_calls(path) for path in paths}
            
    return extra_dependencies

def check_oracle_calls(sas_path: Path):
    calling_oracle_pattern = re.compile(r'(?i)libname\s+\w+\s+oracle\s+.*')
    with open(sas_path, 'r', encoding="windows-1252") as f:
            for line in f:
                if "connect to oracle" in line.lower() or any(calling_oracle_pattern.finditer(line)):
                    return True
    return False

# --- Processing Logic ---

def process_repository(root_path: Path, extra_dependency_paths: list = None, excluded_patterns: list = None) -> pd.DataFrame:
    """Walks directory and aggregates counts into a DataFrame."""
    print("Processing Repository...")
    records = []
    filenames =  [Path(fp).stem for fp in root_path.rglob('*') if Path(fp).is_file() and not any(p.startswith('.') for p in fp.parts) and fp.suffix.lower() == ".sas"]
    extra_dependencies = get_extra_dependencies(extra_dependency_paths if extra_dependency_paths else [])
    filenames.extend(extra_dependencies.keys())

    all_files = root_path.rglob('*')

    filtered_files = [
        path for path in all_files
        if not excluded_patterns or not any(path.match(pattern) for pattern in excluded_patterns )
    ]

    for file_path in filtered_files:
        if file_path.is_file() and not any(p.startswith('.') for p in file_path.parts):
            count = count_lines_in_file(file_path)
            dependencies = check_dependencies(file_path, filenames)
            if count > 0:
                records.append({
                    "File Name": file_path.name,
                    "Extension": file_path.suffix.lower() or "no_ext",
                    "Directory": str(file_path.parent.relative_to(root_path)),
                    "Line Count": count,
                    "Dependencies": dependencies,
                    "Oracle Calls": any(extra_dependencies.get(d, False) == True for d in dependencies.split(", ") if dependencies) or check_oracle_calls(file_path)
                })
    return pd.DataFrame(records)

def export_results(df: pd.DataFrame, args):
    """Generates PDF and CSV files."""
    print("Exporting: {}".format(args.name))
    args.output.mkdir(parents=True, exist_ok=True)
    df_dir = df.copy()

    df_dir['is_sas'] = df_dir['Extension'].eq('.sas').astype(int)
    df_dir['is_not_sas'] = df_dir['Extension'].ne('.sas').astype(int)

    df_ext = df.groupby("Extension")["Line Count"].sum().reset_index()
    df_dir = df_dir.groupby("Directory")[["Directory", "Line Count", "is_sas", "is_not_sas"]].apply(lambda x: pd.Series({
        "SAS Count": (x["is_sas"] * x['Line Count']).sum(),
        "Non-SAS Count": (x["is_not_sas"] * x['Line Count']).sum(),
        "Total Count": x['Line Count'].sum()

    })).reset_index()
    df_files = df.copy().drop("Extension", axis=1)

    is_sas = df["Extension"] == ".sas"
    summary_data = {
        "Total Non-SAS": df.loc[~is_sas, "Line Count"].sum(),
        "Total SAS": df.loc[is_sas, "Line Count"].sum(),
        "Grand Total": df["Line Count"].sum()
    }
    ext_sum_md = tabulate(
        summary_data.items(), 
        tablefmt="github"
    )
    # CSV Exports
    df_files.to_csv(args.output / f"{args.name}_file_details.csv", index=False)
    df_ext.to_csv(args.output / f"{args.name}_ext_summary.csv", index=False)
    df_dir.to_csv(args.output / f"{args.name}_dir_summary.csv", index=False)

    # PDF Export
    md_engine = MarkdownIt().enable('table')
    html_content = md_engine.render(MD_FORMAT.format(
        args.name, 
        df_ext.to_markdown(index=False), 
        ext_sum_md, 
        df_dir.to_markdown(index=False)
    ))

    
    pdf_path = args.output / f"{args.name}_LineCount.pdf"
    HTML(string=html_content).write_pdf(pdf_path, stylesheets=STYLESHEET)

def process_single_repo(args: SimpleNamespace):
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
 

        df_all = process_repository(working_path, args.extra_dependencies, args.exclude)
        
        # Inject metadata
        metadata_fields = {k: v for k, v in args.__dict__.items() if k not in REQUIRED_KEYS}
        for col, val in metadata_fields.items():
            df_all[col] = val

        export_results(df_all, args)
        print(f"Success! Reports for: {args.name}")

# --- Orchestration ---

def process_batch(toml_file: str):
    """Processes multiple repos from a TOML configuration."""
    with open(toml_file, "rb") as f:
        toml_data = tomllib.load(f)
    
    defaults = toml_data.get("defaults", {})

    for repo_name, config in toml_data.get("repo", {}).items():
        args = create_arguments(repo_name, config, defaults)
        process_single_repo(args)


def create_arguments(repo_name, config, defaults):
    merged = {**defaults, **config, "name": repo_name}
    for k in REQUIRED_KEYS:
        merged.setdefault(k, None)
    if merged.get('output'):
        merged['output'] = Path(merged['output'])
    return SimpleNamespace(**merged)

def main():
    parser = argparse.ArgumentParser(description="Code Line Counter (SAS Optimized)")
    parser.add_argument("batch", help="Path to TOML for batch processing")
    args = parser.parse_args()
    process_batch(args.batch)


if __name__ == "__main__":
    main()
