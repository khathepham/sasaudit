import argparse
from pathlib import Path

from dataclasses import dataclass, fields
import pandas as pd
from git import Repo
from markdown_it import MarkdownIt
from weasyprint import HTML, CSS
from tabulate import tabulate
import tomllib
import tempfile

# TODO: Grand Total SAS vs Non-SAS
# TODO: (Later) Convert sas7bdat to csv to count lines?
# TODO: Set parameters for Cost Center, App Cateogory, Business Process, etc. 
# TODO: Create csv matching DBES excel

# Configuration
GIT_DIR = Path("./temp")
TEXT_CHARS = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
MD_FORMAT = """# {}
## Line Count by Extension
{}
{}
## Line Count by Directory
{}
"""
DEFAULT_ARGS = {}

@dataclass
class Arguments():
    name: str
    source: str
    branch: str
    cost_center: str
    program_supported: str
    business_process: str
    app_category: str
    location: str
    output: Path
    user_id: str


def is_binary(path: Path) -> bool:
    """Check if file is binary by inspecting the first kilobyte."""
    with path.open('rb') as f:
        return bool(f.read(1024).translate(None, TEXT_CHARS))

def count_lines_in_file(path: Path) -> int:
    """Counts non-blank lines. Excludes SAS comments if applicable."""
    if is_binary(path): return 0
    ext = path.suffix.lower()
    enc = "windows-1252" if ext == ".sas" else "utf-8"
    
    try:
        lines = path.read_text(encoding=enc, errors="ignore").splitlines()
        if ext == ".sas":
            return sum(1 for l in lines if (s := l.strip()) and not s.startswith("/*"))
        return sum(1 for l in lines if l.strip())
    except Exception:
        return 0

def count_lines_in_binary(path: Path) -> int:
    ext = path.suffix.lower()
    if ext == ".sas7bdat":
        df = pd.read_sas(path, format='sas7bdat', encoding='latin1')
        return len(df) # Counts rows/observations
    return 0

def process_repository(root_path: Path):
    """Walks the directory and aggregates counts into a list of dicts."""
    records = []

    for file_path in root_path.rglob('*'):
        # Skip hidden files/folders and specific git metadata
        if file_path.is_file() and not any(p.startswith('.') for p in file_path.parts):
            
            # Use your existing line count logic (recommendation 2)
            count = count_lines_in_file(file_path)
            
            if count > 0:
                records.append({
                    "File Name": file_path.name,
                    "Extension": file_path.suffix.lower() or "no_ext",
                    "Directory": str(file_path.parent.relative_to(root_path)),
                    "Line Count": count
                })

    return pd.DataFrame(records)


def export_results(df: pd.DataFrame, args: Arguments):
    """Generates PDF and CSV files using Pandas aggregation."""
    args.output.mkdir(parents=True, exist_ok=True)

    # 1. Generate Summary DataFrames via GroupBy
    df_ext = df.groupby("Extension")["Line Count"].sum().reset_index()
    df_dir = df.groupby("Directory")["Line Count"].sum().reset_index()

    # 2. SAS vs Non-SAS Grand Totals
    # Create a boolean mask to split the data
    is_sas = df["Extension"] == ".sas"
    summary_data = {
        "Total Non-SAS": df.loc[~is_sas, "Line Count"].sum(),
        "Total SAS": df.loc[is_sas, "Line Count"].sum(),
        "Grand Total": df["Line Count"].sum()
    }
    # Convert dict to markdown table for the PDF
    ext_sum_md = pd.Series(summary_data).to_frame("Line Count").to_markdown()

    # 3. Generate CSVs
    # Full file list already contains metadata columns injected in process_single_repo
    df.to_csv(args.output / f"{args.name}_file_details.csv", index=False)
    df_ext.to_csv(args.output / f"{args.name}_ext_summary.csv", index=False)
    df_dir.to_csv(args.output / f"{args.name}_dir_summary.csv", index=False)

    # 4. Generate PDF
    md_engine = MarkdownIt().enable('table')
    html_content = md_engine.render(MD_FORMAT.format(
        args.name, 
        df_ext.to_markdown(index=False), 
        ext_sum_md, 
        df_dir.to_markdown(index=False)
    ))
    
    css_path = Path("style.css")
    stylesheets = [CSS(filename=str(css_path))] if css_path.exists() else []
    
    pdf_path = args.output / f"{args.name}_LineCount.pdf"
    HTML(string=html_content).write_pdf(pdf_path, stylesheets=stylesheets)


def process_single_repo(args: Arguments):
    source_path = Path(args.source)
    
    # Use temp folder if we need to use git
    with tempfile.TemporaryDirectory() as tmp_dir:
        working_path = source_path
        
        # Check if we need to clone
        if not source_path.is_dir():
            try:
                print(f"Cloning remote repository: {args.source}")
                repo = Repo.clone_from(args.source, tmp_dir)
                if args.branch:
                    repo.git.checkout(args.branch)
                
                working_path = Path(tmp_dir)
                # Auto-fill name from URL if missing
                if not args.name:
                    args.name = args.source.rstrip('/').split('/')[-1].replace('.git', '')
            except Exception as e:
                return print(f"Error: Could not access path or Git URL. {e}")
        else:
            if not args.name:
                args.name = source_path.name

        # Process using the determined path
        df_all = process_repository(working_path)
        
        # Inject metadata for the CSV export
        metadata_fields = {
            "User ID": args.user_id,
            "Cost Center": args.cost_center,
            "Program Supported": args.program_supported,
            "Business Process": args.business_process
        }
        for col, val in metadata_fields.items():
            df_all[col] = val

        export_results(df_all, args)
        print(f"Success! Reports generated for: {args.name}")

def verify_toml(toml: dict):
    defaults = toml["defaults"]
    assert defaults["user_id"], "default.user-id not set"
    assert defaults["cost_center"], "default.cost-center not set"
    assert defaults["program_supported"], "default.program-supported not set"
    assert defaults["app_category"], "default.app-category not set"
    assert defaults["location"], "default.location not set"
    assert defaults['output'], "default.output not set"
    assert Path(defaults["output"]), "default.output isn't a valid path name"

    assert len(toml["repo"]) > 0, "No repositories listed."
    for repo, v in toml["repo"].items():
        assert v["source"], "No source selected for {}".format(repo)

def process_batch(toml_data: dict):
    defaults = toml_data.get("defaults", {})
    
    for repo_name, config in toml_data.get("repo", {}).items():
        # Merge defaults with repo-specific config
        # repo config takes precedence
        merged_config = {**defaults, **config, "name": repo_name}
        
        # Filter config to only include valid Argument fields
        valid_keys = {f.name for f in fields(Arguments)}
        filtered_config = {k: v for k, v in merged_config.items() if k in valid_keys}
        
        for k in valid_keys:
            filtered_config[k] = filtered_config.get(k, None)

        # Ensure 'output' is a Path object
        if 'output' in filtered_config:
            filtered_config['output'] = Path(filtered_config['output'])
            
        args = Arguments(**filtered_config)
        process_single_repo(args)
   


def main():
    parser = argparse.ArgumentParser(description="Code Line Counter (SAS Optimized)")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-s", "--source", help="Directory path or Git Repository URL")
    group.add_argument("-t", "--batch", help="use a toml for input instead of cmd args, allowing for batch processing. Not compatible with other cmds")
    
    parser.add_argument("-o", "--output", default="./out", help="Output folder (default: ./out)")
    parser.add_argument("-b", "--branch", help="Specific git branch to clone")
    parser.add_argument("-u", "--user-id", default="N/A", help="Set ID of User for full output, if using git repo.")
    parser.add_argument("-c", "--cost-center", default="N/A", help="Set cost center")
    parser.add_argument("-p", "--program-supported", default="N/A", help="Set Program Office")
    parser.add_argument("-z", "--business-process", default="N/A", help="Set Business Process")
    parser.add_argument("-l", "--location", default="N/A", help="Where the program runs, on Server, Desktop, etc, etc.")
    parser.add_argument("-a", "--app-category", default="N/A", help="Category of the App, Prod, Dev, etc.")
 
    parser.add_argument("--count-sas7bdat", help="Count sas7bdat files", action="store_true")

    args = parser.parse_args()


    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.exists():
            return print(f"Error: TOML file not found at {batch_path}")
            
        with open(batch_path, "rb") as f:
            data = tomllib.load(f)
            verify_toml(data) # Using your existing verification logic
            process_batch(data)

    else:
        assert Path(args.output), "Output Isn't a Directory, or Doesn't Exist"
        arguments = Arguments(
            name = None,
            source = args.source,
            branch = args.branch,
            cost_center= args.cost_center,
            program_supported=args.program_supported,
            business_process=args.business_process,
            location=args.location,
            output=Path(args.output),
            app_category=args.app_category,
            user_id=args.user_id
        )
        process_single_repo(arguments)

if __name__ == "__main__":
    main()
