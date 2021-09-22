# pyar3

`pyar3` is a Python package providing some tools dedicated to Altarica 3 modelling langage.

## Installation

### Prerequisites 

- Make sure you have the `Python` package manager `pip` installed on your system.
- For Windows users, you can install `Cygwin` 
- It is also recommended to install the virtual environment manager `pew` with `pip install pew`. Then you will be able to create and work in a `Python` virtual environment (see commands `pew new` and `pew workon`).

#### Notes for Windows users

- If you are using `Cygwin`, you must install the `python3-dev` package with the `Cygwin` installer **before** running the `pip install` command.
- The `pip install` process can take a while because `Python` packages are compiled during the installation.


### Install command

Simply execute :
`pip install git+https://github.com/roland-donat/pyar3`


## Script `ar3sto2xls`

Installing `pyar3` package make the script `ar3sto2xls` available in your system path (at least on Linux).

This tool aims to convert stochastic simulator raw result csv file into Excel file with one tab for
each requested indicator.

If you have a raw result file named `results.csv`, execute : `ar3sto2xls results.csv`. This will
produce a file `result.xlsx` next to `results.csv`.
