# SAS Inventory

A command-line tool that scans code repositories and generates detailed inventory reports. It has special support for SAS files, including comment filtering, encoding handling, dependency tracking, macro analysis, and Oracle call detection.

---

## What It Does

For each repository you point it at, SAS Inventory will:

- Count non-blank lines of code across all files
- Skip binary files automatically
- For `.sas` files specifically:
  - Strip out comment lines (block, inline, macro, and star comments) before counting
  - Handle Windows-1252 encoding (common in legacy SAS files)
  - Detect PROC usage (e.g. `PROC SQL`, `PROC SORT`)
  - Detect LIBNAME statements and macro parameter library assignments
  - Detect macro definitions (`%macro`) and macro calls
  - Detect dataset references (`lib.dataset` notation)
  - Detect cross-file dependencies (via `%include`, `%macro`, `call execute`)
  - Detect Oracle database calls (`libname ... oracle` and `connect to oracle`)
  - Optionally extract program descriptions from SAS header comment blocks
- Catalog SAS datasets (`.sas7bdat`) and catalogs (`.sas7bcat`)
- Attach metadata to results (cost center, program name, etc.)
- Export everything to a single **Excel workbook**

---

## Output

For each repository named (e.g. `MyProject`), SAS Inventory creates `MyProject_audit.xlsx` with the following sheets:

| Sheet | Description |
|-------|-------------|
| **Summary** | Total SAS lines, non-SAS lines, and grand total |
| **File Details** | Per-file inventory: line counts, dependencies, Oracle calls, and descriptions |
| **Extension Summary** | Line counts grouped by file extension |
| **Directory Summary** | SAS vs non-SAS line counts per directory |
| **PROC Usage** | Every PROC statement found, with file name and line number |
| **Libname References** | LIBNAME statements and macro parameter library assignments |
| **Macro Definitions** | All `%macro` definitions with locations |
| **Macro Calls** | All user-defined macro calls (excluding SAS built-ins) |
| **Dataset References** | `lib.dataset` references found in DATA, SET, MERGE, UPDATE, and FROM contexts |
| **SAS Datasets & Catalogs** | Inventory of `.sas7bdat` and `.sas7bcat` files found in the repository |

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

SAS Inventory is configured with a `.toml` file. This file tells it which repositories to scan and what metadata to attach to the results.

An example config is included at [`example.toml`](./example.toml). You can copy and edit it to match your setup.

### File Structure

```toml
[defaults]
# These values apply to every repo unless overridden below
output              = "./output"
parse_description   = true

"User ID"           = "N/A"
"Cost Center"       = "739"
"Program Supported" = "CE"
"Business Process"  = ""

[repo.MyProject]
# Path to a local folder OR a Git SSH/HTTPS URL
source = "/path/to/my/project"
```

### Configuration Options

**In `[defaults]`** — set values once, apply to all repos:

| Key | Description |
|-----|-------------|
| `output` | Folder where reports will be saved (created automatically if it doesn't exist) |
| `parse_description` | Set to `true` to extract program descriptions from SAS file header comments (default: `false`) |
| `exclude` | List of file patterns to skip (e.g. `["*.for", "*.log"]`) |

**In each `[repo.Name]`** — configure each individual repository:

| Key | Required | Description |
|-----|----------|-------------|
| `source` | Yes | Local folder path **or** Git URL (SSH or HTTPS) |
| `branch` | No | Git branch to check out (defaults to the repo's default branch) |
| `output` | No | Override the default output folder for this repo |
| `parse_description` | No | Override the default description parsing setting for this repo |
| `extra_dependencies` | No | List of other repo paths/URLs to scan for cross-repo SAS dependencies |
| `exclude` | No | List of file patterns to skip for this repo (overrides defaults) |

Any key set in `[defaults]` can be overridden inside a specific `[repo.Name]` block.

**Custom metadata columns:** Any key that isn't a recognized configuration option (like `"Cost Center"` or `"Business Process"`) is treated as custom metadata and added as a column in the File Details sheet.

### Example: Local Folder

```toml
[defaults]
output              = "./reports"
parse_description   = true
"Cost Center"       = "739"
"Program Supported" = "MY_PROGRAM"
"Business Process"  = "Estimation"

[repo.MyProject]
source             = "/home/user/projects/myproject"
"Business Process" = "Publication"
```

### Example: Remote Git Repository

```toml
[defaults]
output              = "./reports"
parse_description   = true
"Cost Center"       = "739"
"Program Supported" = "MY_PROGRAM"
"Business Process"  = "Data Processing"

[repo.MyProject]
source              = "git@github.com:myorg/myproject.git"
branch              = "main"
extra_dependencies  = ["git@github.com:myorg/shared-macros.git", "shared/macro/directory"]
exclude             = ["*.for"]

[repo.MyProject2]
source = "/path/to/project"
```

---

## Running the Tool

Once your TOML file is set up, run:

```sh
python sas_inventory.py your_config.toml
```

Or with the included example:

```sh
python sas_inventory.py example.toml
```

The tool will print progress as it processes each repository and confirm when each report is done.

---

## Tips

- **Excluding files:** The `exclude` list uses glob-style patterns (same format as `.gitignore`). For example, `"*.for"` skips all Fortran files, `"temp/*"` skips everything in a `temp/` folder.
- **Multiple repos in one run:** Add as many `[repo.Name]` blocks as you like to a single TOML file — SAS Inventory will process them all in sequence.
- **Cross-repo dependencies:** If your SAS project calls macros defined in a shared library, add that library's path or Git URL to `extra_dependencies`. SAS Inventory will note which files in the main project depend on which files in the shared library.
- **Oracle detection:** The `Oracle Calls` column in the File Details sheet flags any SAS file (or its dependencies) that contain Oracle `libname` or `connect to oracle` statements.
- **Description parsing:** When enabled, the tool extracts the program description from each SAS file's header comment block (looking for labels like `Description:`, `Function:`, or `Purpose:`).

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
