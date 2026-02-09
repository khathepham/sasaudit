import argparse
import json
import shutil
from pathlib import Path

import git
import pandas as pd
from git import Repo, GitCommandError
from markdown_it import MarkdownIt
from weasyprint import HTML, CSS

# Configuration
GIT_DIR = Path("./temp")
TEXT_CHARS = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
MD_FORMAT = """# {}
## Line Count by Extension
{}
## Line Count by Directory
{}
"""

def is_binary(path: Path) -> bool:
    """Check if file is binary by inspecting the first kilobyte."""
    with path.open('rb') as f:
        return bool(f.read(1024).translate(None, TEXT_CHARS))

def count_lines_in_file(path: Path) -> int:
    """Counts non-blank lines. Excludes SAS comments if applicable."""
    ext = path.suffix.lower()
    try:
        # SAS files typically use windows-1252
        encoding = "windows-1252" if ext == ".sas" else "utf-8"
        with path.open(mode="r", encoding=encoding, errors="ignore") as f:
            if ext == ".sas":
                return sum(1 for line in f if (s := line.strip()) and not s.startswith("/*"))
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0

def process_repository(root_path: Path):
    """Walks the directory and aggregates counts, skipping hidden git files."""
    ext_counts, dir_counts = {}, {}

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

    return ext_counts, dir_counts

def export_results(ext_counts, dir_counts, title, output_dir: Path):
    """Generates PDF (with original CSS) and CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    df_ext = pd.DataFrame(ext_counts.items(), columns=["Extension", "Line Count"])
    df_dir = pd.DataFrame(dir_counts.items(), columns=["Directory", "Line Count"])

    # Generate CSVs
    df_ext.to_csv(output_dir / "line_count_extensions.csv", index=False)
    df_dir.to_csv(output_dir / "line_count_directory.csv", index=False)

    # Generate PDF using original style.css
    md = MarkdownIt().enable('table')
    html_content = md.render(MD_FORMAT.format(title, df_ext.to_markdown(index=False), df_dir.to_markdown(index=False)))
    
    # Locate style.css (assumes it is in the script's directory)
    css_path = Path("style.css")
    stylesheets = [CSS(filename=str(css_path))] if css_path.exists() else []
    
    HTML(string=html_content).write_pdf(output_dir / "LineCount.pdf", stylesheets=stylesheets)

def main():
    parser = argparse.ArgumentParser(description="Code Line Counter (SAS Optimized)")
    parser.add_argument("source", help="Directory path or Git Repository URL")
    parser.add_argument("-o", "--output", default="./out", help="Output folder (default: ./out)")
    parser.add_argument("-b", "--branch", help="Specific git branch to clone")
    args = parser.parse_args()

    source_path = Path(args.source)
    output_path = Path(args.output)
    is_remote = False

    # Validation and Cloning
    if not source_path.is_dir():
        try:
            print(f"Validating and cloning: {args.source}")
            git.cmd.Git().ls_remote(args.source)
            repo = Repo.clone_from(args.source, GIT_DIR)
            if args.branch:
                repo.git.checkout(args.branch)
            source_path, is_remote = GIT_DIR, True
        except (GitCommandError, Exception) as e:
            print(f"Error: Could not access path or Git URL. {e}")
            return

    try:
        ext_data, dir_data = process_repository(source_path)
        export_results(ext_data, dir_data, args.source, output_path)
        print(f"Success! Reports generated in: {output_path.resolve()}")
    finally:
        if is_remote and GIT_DIR.exists():
            shutil.rmtree(GIT_DIR)

if __name__ == "__main__":
    main()
