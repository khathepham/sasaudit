# SASAudit
A Python-based utility to audit codebases, with special support for .sas files. 

## Features
- Ignores /* ... */ comment blocks in SAS files. 
- Handles the conversion between UTF-8 and windows-1252 encoding
- Generates a PDF summary report, and detailed CSVs for further analysis, at the File, Extension, and Directory levels. 



## Getting started

Install requirements to your user environment with:
```sh
pip install -r requirements.txt
```

Otherwise, setup a virtual environment with
```sh
python -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
```

## Running the program
Define your repositories in a TOML file. You can set global defaults for all repos.

Create a TOML file. There is an example at [example.toml](./example.toml).

Run the program using:
```sh
python /path/to/sasaudit.py path/to/toml.toml
```
Example
```sh
python sasaudit.py example.toml
```



## Stipulations
See [Using Nexus Repo Manager > Pypi, aka pip(for python)](https://cfgitlabprd01v.psb.bls.gov/osmr/dsrc/dsrc-hq/-/wikis/using-nexus-repository-manager#pypi-aka-pip-for-python) for instructions on how to setup pip modules for your user/virtual environments without CNTLM. 

It is likely that these commands will need to be replaced with `python3.11 ...` and `pip3.11 ...` instead of `python` and `pip`. This is because `python` and `pip` point to python2 versions that no longer exist on the server, and `python3` and `pip3` point to python 3.6, which while compatible, may have issues with pip install on server.






