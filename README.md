# pyar3

`pyar3` is a Python package providing some tools dedicated to Altarica 3 modelling langage.

## Installation

Simply execute :
`pip install git+https://github.com/roland-donat/pyar3`

## Script `ar3sto2xls`

Installing `pyar3` package make the script `ar3sto2xls` available in your system path (at least on Linux).

This tool aims to convert stochastic simulator raw result csv file into Excel file with one tab for
each requested indicator.

If you have a raw result file named `results.csv`, execute : `ar3sto2xls results.csv`. This will
produce a file `result.xlsx` next to `results.csv`.
