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
    """Walks the directory and aggregates counts, skipping hidden git files."""
    ext_counts, dir_counts, all_counts = {}, {}, {}

    for file_path in root_path.rglob('*'):
        # Ignore .git directory and the .gitignore file
        if file_path.is_file() and ".git" not in file_path.parts and file_path.name != ".gitignore":
            if is_binary(file_path):
                continue
                
            count = count_lines_in_file(file_path)
            if count > 0:
                ext = file_path.suffix or "no_ext"
                # Relative path for cleaner reporting
                parent = str(file_path.parent.relative_to(root_path))
                ext_counts[ext] = ext_counts.get(ext, 0) + count
                dir_counts[parent] = dir_counts.get(parent, 0) + count
                all_counts[file_path] = count

    return ext_counts, dir_counts, all_counts

def export_results(ext_counts, dir_counts, all_counts, args: Arguments):
    """Generates PDF (with original CSS) and CSV files."""
    args.output.mkdir(parents=True, exist_ok=True)
    
    ext_counts_sum = {}
    ext_counts_sum["Total Non-SAS"] = sum([v for k, v in ext_counts.items() if k != ".sas" ])
    ext_counts_sum["Total SAS"] = ext_counts.get(".sas", 0)
    ext_counts_sum["Grand Total"] = sum(ext_counts.values())
    ext_sum_md = tabulate(ext_counts_sum.items(), tablefmt="github")


    df_ext = pd.DataFrame(ext_counts.items(), columns=["Extension", "Line Count"])
    df_dir = pd.DataFrame(dir_counts.items(), columns=["Directory", "Line Count"])
    
    df_all = pd.DataFrame(all_counts.items(), columns=["File Name", "Line Count"])
    df_all["User ID"] = args.user_id
    df_all["Cost Center"] = args.cost_center
    df_all["Program Supported"] = args.program_supported
    df_all["Business Process"] = args.business_process

    # Generate CSVs
    df_ext.to_csv(args.output / "{}_line_count_extensions.csv".format(args.name), index=False)
    df_dir.to_csv(args.output / "{}_line_count_directory.csv".format(args.name), index=False)
    df_all.to_csv(args.output / "{}_line_count_file.csv".format(args.name), index=False)

    

    # Generate PDF using original style.css
    md = MarkdownIt().enable('table')
    html_content = md.render(MD_FORMAT.format(args.name, df_ext.to_markdown(index=False), ext_sum_md,  df_dir.to_markdown(index=False)))
    
    # Locate style.css (assumes it is in the script's directory)
    css_path = Path("style.css")
    stylesheets = [CSS(filename=str(css_path))] if css_path.exists() else []
    
    HTML(string=html_content).write_pdf(args.output / "{}_LineCount.pdf".format(args.name), stylesheets=stylesheets)


def process_single_repo(args: Arguments):
    source_path = Path(args.source)
    
    # Use a context manager that we only 'activate' if we actually need a temp folder
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
        df_ext, df_dir, df_all, = process_repository(working_path)
        
        # Inject metadata for the CSV export
        metadata_fields = {
            "User ID": args.user_id,
            "Cost Center": args.cost_center,
            "Program Supported": args.program_supported,
            "Business Process": args.business_process
        }
        for col, val in metadata_fields.items():
            df_all[col] = val

        export_results(df_ext, df_dir, df_all, args)
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

def process_batch(toml_data: list):
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
        config = {}
        try:
            config = tomllib.load(open(args.batch, 'rb'))
        except tomllib.TOMLDecodeError as e:
            print("TOML File not formatted correctly.")
            print(e.with_traceback())
        assert len(config) > 0, "Config File is Empty"
        verify_toml(config)

        global DEFAULT_ARGS
        process_batch(config)



    else:
        assert Path(args.output).is_dir(), "Output Isn't a Directory, or Doesn't Exist"
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
