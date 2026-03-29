# medieval-cpi

Prototype workspace for medieval CPI-style text normalization and matching.

## Data Sources

- Allen-Unger Global Commodity Prices Database: [allen-unger-data](https://datasets.iisg.amsterdam/dataset.xhtml?persistentId=hdl:10622/3SV0BO)
- Winchester Pipe Rolls (1208-1209): [winchester-pipe-rolls](https://archive.org/details/piperollofbishop00churrich) — full transcription with raw prices.

## Technical primer

This project is meant to explore a practical pipeline for documentary and historical-text work:

- Allen-Unger-style normalization and editorial workflows for comparing variant spellings
- Winchester Pipe Rolls as a motivating corpus for messy medieval orthography and quantitative analysis
- pandas for quick tabular exploration and CSV wrangling
- polars for faster, columnar processing when the data gets larger
- rapidfuzz for fuzzy matching across spellings, names, and place forms
- pint for handling units and quantities when records include money, weights, measures, or conversions

## What success looks like

A successful first pass should be able to:

1. Load one or more CSV files containing medieval entries.
2. Identify the relevant text columns and normalize obvious noise.
3. Suggest likely matches between variant spellings and a controlled form.
4. Produce a reviewable output table with source text, candidate standard form, and confidence score.
5. Keep the pipeline simple enough that a researcher can inspect and override every decision.

The goal is not perfect automation. The goal is a small, explainable workflow that helps turn inconsistent medieval spellings into something searchable and comparable.
