# line-counter



## Getting started

Run this to allow GitPython to run anywhere in your user environment.
```sh
pip install -r requirements.txt
```

Otherwise, setup a virtual environment with
```sh
python -m venv venv
source ./venv/bin/activate
pip install -r requirements
```

## Running the program

```sh
python line-counter [Directory-or-Git-Link]
```

Git link can be ssh or http.

A PDF Summary and CSV summaries will be placed in the 'out' folder. 

## Stipulations

On CEIS Servers, it is likely that these commands will need to be replaced with `python3.11 ...` and `pip3.11 ...` instead of `python` and `pip`. This is because `python` and `pip` point to python2 versions that no longer exist on the server, and `python3` and `pip3` point to python 3.6, which while compatible, may have issues with pip install on server. 

See [Using Nexus Repo Manager > Pypi, aka pip(for python)](https://cfgitlabprd01v.psb.bls.gov/osmr/dsrc/dsrc-hq/-/wikis/using-nexus-repository-manager#pypi-aka-pip-for-python) for instructions on how to setup pip modules for your user/virtual environments on the servers. 




