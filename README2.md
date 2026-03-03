# SASAudit

A command-line tool that scans code repositories and generates line count reports. It has special support for SAS files, including comment filtering, encoding handling, dependency tracking, and Oracle call detection.

---

## What It Does

For each repository you point it at, SASAudit will:

- Count non-blank lines of code across all files
- Skip binary files automatically
- For `.sas` files specifically:
  - Strip out comment lines (lines starting with `/*`) before counting
  - Handle Windows-1252 encoding (common in legacy SAS files)
  - Detect which SAS files depend on other SAS files (via `%include`, `%macro`, `call execute`)
  - Detect Oracle database calls (`libname ... oracle` and `connect to oracle`)
- Attach metadata to results — any custom fields you define in the TOML will appear as columns in the CSV
- Export everything to a **PDF summary report** and **three CSV files**

---

## Output Files

For each repository named (e.g. `MyProject`), SASAudit creates:

| File | Description |
|------|-------------|
| `MyProject_LineCount.pdf` | Summary report with line counts by extension and directory |
| `MyProject_file_details.csv` | One row per file: name, directory, line count, dependencies, Oracle calls, metadata |
| `MyProject_ext_summary.csv` | Line counts grouped by file extension |
| `MyProject_dir_summary.csv` | Line counts per directory, broken out as SAS vs. non-SAS |

---

## Prerequisites

- **Python 3.11 or newer** installed and accessible from the command line
- **pip** (Python's package manager) — usually included with Python
- **Git** — only required if you are scanning remote Git repositories

> **Note (server environments):** On some servers, `python` and `pip` may point to old versions. Use `python3.11` and `pip3.11` instead if the default commands don't work.

---

## Setup

You only need to do this once.

**Option 1 — Install into your user environment (simpler):**

```sh
pip install -r requirements.txt
```

**Option 2 — Install into a virtual environment (recommended if you want to keep things isolated):**

```sh
python -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
```

> On Windows, replace `source ./venv/bin/activate` with `venv\Scripts\activate`.
>
> Each time you open a new terminal session, you'll need to re-run the `activate` command before running the tool.

---

## Configuration: The TOML File

SASAudit is configured with a `.toml` file. This file tells it which repositories to scan and what metadata to attach to the results.

An example config is included at [`example.toml`](./example.toml). You can copy and edit it to match your setup.

### File Structure

```toml
[defaults]
# These values apply to every repo unless overridden below
user_id = "N/A"
cost_center = "739"
program_supported = "CE"
business_process = "CE Processing"
output = "./output"
exclude = []

[repo]

[repo.MyProject]
# Path to a local folder OR a Git SSH/HTTPS URL
source = "/path/to/my/project"
```

### Configuration Options

**In `[defaults]`** — set values once, apply to all repos:

| Key | Description |
|-----|-------------|
| `output` | Folder where reports will be saved (created automatically if it doesn't exist) |
| `exclude` | List of file patterns to skip (e.g. `["*.for", "*.log"]`) |

**In each `[repo.Name]`** — configure each individual repository:

| Key | Required | Description |
|-----|----------|-------------|
| `source` | Yes | Local folder path **or** Git URL (SSH or HTTPS) |
| `branch` | No | Git branch to check out (defaults to the repo's default branch) |
| `output` | No | Override the default output folder for this repo |
| `extra_dependencies` | No | List of other repo paths/URLs to scan for cross-repo SAS dependencies |
| `exclude` | No | List of file patterns to skip for this repo (overrides defaults) |

**Metadata fields** — Any other key you add (e.g. `cost_center`, `business_process`, `user_id`) will automatically appear as a column in the file details CSV. Add as many or as few as you need. These can be set in `[defaults]` and overridden per repo.

Any `[defaults]` key can be overridden inside a specific `[repo.Name]` block.

### Example: Local Folder

```toml
[defaults]
output = "./reports"
cost_center = "739"
program_supported = "MY_PROGRAM"
business_process = "Data Processing"
exclude = []

[repo.MyProject]
source = "/home/user/projects/myproject"
business_process = "Estimation"
```

### Example: Remote Git Repository

```toml
[defaults]
output = "./reports"
cost_center = "739"
program_supported = "MY_PROGRAM"
business_process = "Data Processing"
exclude = []

[repo.MyProject]
source = "git@github.com:myorg/myproject.git"
branch = "main"
extra_dependencies = ["git@github.com:myorg/shared-macros.git"]
exclude = ["*.for"]
```

---

## Running the Tool

Once your TOML file is set up, run:

```sh
python sasaudit.py your_config.toml
```

Or with the included example:

```sh
python sasaudit.py example.toml
```

The tool will print progress as it processes each repository and confirm when each report is done.

---

## Tips

- **Excluding files:** The `exclude` list uses glob-style patterns (same format as `.gitignore`). For example, `"*.for"` skips all Fortran files, `"temp/*"` skips everything in a `temp/` folder.
- **Multiple repos in one run:** Add as many `[repo.Name]` blocks as you like to a single TOML file — SASAudit will process them all in sequence.
- **Cross-repo dependencies:** If your SAS project calls macros defined in a shared library, add that library's path or Git URL to `extra_dependencies`. SASAudit will note which files in the main project depend on which files in the shared library.
- **Oracle detection:** The `Oracle Calls` column in the file details CSV flags any SAS file (or its dependencies) that contain Oracle `libname` or `connect to oracle` statements.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `python: command not found` | Try `python3`, `python3.11`, or `python3.12` |
| `pip: command not found` | Try `pip3` or `pip3.11` |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| Git clone fails | Make sure you have SSH keys or credentials set up for the remote |
| Output folder is empty | Check that the `source` path in your TOML is correct |
| Encoding errors in SAS files | SAS files are read as Windows-1252 automatically — check if the file has an unusual encoding |