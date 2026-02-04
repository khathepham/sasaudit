import os

import git
from git import Repo, GitCommandError
import argparse
from pathlib import Path
import json
import pandas as pd
from pprint import pprint
from markdown_it import MarkdownIt
from weasyprint import HTML, CSS


GIT_DIR = "./temp"

MD_FORMAT="""# {}
## Line Count by Extension
{}
## Line Count by Directory
{}
"""

# TODO: add by directory level count - do not count subdir count in dir count. 
# TODO: prettify output (later)

# Source - https://stackoverflow.com/a
# Posted by jfs, modified by community. See post 'Timeline' for change history
# Retrieved 2026-01-27, License - CC BY-SA 3.0

text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})


def is_binary_string(bytes):
    return bool(bytes.translate(None, text_chars))


def list_files(root: str):
    file_list = []
    for root, dir, files in os.walk(root):
        if ".git" not in root:
            for file in files:
                if ".gitignore" not in file:
                    file_list.append(os.path.join(root, file))
    return file_list


def is_valid_git_url_gp(url):
    """
    Checks if a given URL corresponds to a reachable Git repository using GitPython.
    """
    try:
        # The ls-remote command checks for references in the remote repository
        # This will raise a GitCommandError if the URL is invalid or unreachable
        git.cmd.Git().ls_remote(url)
        return True
    except GitCommandError:
        return False
    except Exception as e:
        # Handle other potential errors (e.g., GitPython not installed correctly)
        print(f"An unexpected error occurred: {e}")
        return False


def count_sas_lines(file: str):
    with open(file, encoding="windows-1252") as f:
    with open(file, encoding="windows-1252") as f:
        # Count the line if it's not blank, and it doesn't start with /*
        return sum(1 for line in f if line.strip() and line.strip()[0:2] != "/*")


def count_other_lines(file: str):
    with open(file, 'rb') as f:
        # count the line if it's not blank
        return sum(1 for line in f if line.strip())


def count_lines(files: list):
    line_counts = {".sas": 0}
    line_counts_dir = {}
    for file in files:
        extension = Path(file).suffix
        line_count = 0
        if extension == ".sas":
            line_count = count_sas_lines(file)
            line_counts['.sas'] += line_count
        elif not is_binary_string(open(file, 'rb').read(1024)):  # if is not binary
            line_count = count_other_lines(file)
            line_counts[extension] = line_counts.get(extension, 0) + line_count
        
        line_counts_dir[str(Path(file).parent)] = line_counts_dir.get(str(Path(file).parent), 0) + line_count

    return line_counts, line_counts_dir

def create_pdf(line_count_ext, line_count_dir, title=""):
    df = pd.DataFrame(line_count_dir.items(), columns=["Directory", "Line Count"])
    df2 = pd.DataFrame(line_count_ext.items(), columns=["Extension", "Line Count"])


    # Write to PDF
    md = MarkdownIt().enable('table')
    html_text = md.render(MD_FORMAT.format(title, df2.to_markdown(index=False), df.to_markdown(index=False)))
    css = CSS("style.css")
    html = HTML(string=html_text)
    html.write_pdf('./out/LineCount.pdf', stylesheets=[css])

def create_csv(line_count_ext, line_count_dir):
    with open("./out/line_count_extensions.csv", "w") as f:
        df = pd.DataFrame(line_count_ext.items(), columns=["Extension", "Line Count"])
        f.write(df.to_csv())
    with open("./out/line_count_directory.csv", "w") as f:
        df = pd.DataFrame(line_count_dir.items(), columns=["Directory", "Line Count"])
        f.write(df.to_csv())

def main(dir_or_repo: str, branch: str = None):
    # SETUP
    work_dir = dir_or_repo
    is_git = False
    if not Path(dir_or_repo).is_dir():
        if not is_valid_git_url_gp(dir_or_repo):
            raise ValueError(
                "One of the following issues have occurred: Invalid Path, Invalid git URL, Inaccessible git repo.\n"
                "dir-or-repo: " + dir_or_repo)
        else:
            work_dir = GIT_DIR
            print("Cloning {} into {}".format(dir_or_repo, work_dir))
            repo = Repo.clone_from(dir_or_repo, GIT_DIR)
            if branch:
                repo.head.set_reference(repo.heads[branch])
            repo.head.reset(index=True, working_tree=True)

            is_git = True

    # LOGIC
    try:
        files = list_files(work_dir)
        line_count_ext, line_count_dir = count_lines(files)
        prefix = "temp" if is_git else ""
        line_count_ext = { k.removeprefix(prefix): v for k, v in line_count_ext.items() if v != 0}
        line_count_dir = { k.removeprefix(prefix): v for k, v in line_count_dir.items() if v != 0}

        print(json.dumps(line_count_ext, indent=4))
        print(json.dumps(line_count_dir, indent=4))
        Path("./out").mkdir(parents=True, exist_ok=True)
        create_pdf(line_count_ext, line_count_dir, "Line Count for {}".format(dir_or_repo))
        create_csv(line_count_ext, line_count_dir)
    # DELETE .TEMP IF NEEDED
    finally:
        if is_git:
            print(f"Removing {GIT_DIR}")
            git.rmtree(GIT_DIR)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog="SAS Line Counter for Git Repo",
        description="Counts lines for all types of files, removing blank lines from all and removing comments from SAS."
    )

    parser.add_argument("dir_or_git", metavar="dir-or-git",
                        help="Either a path to a directory, or a link to a Git Repo")

    args = parser.parse_args()

    main(args.dir_or_git)
