# Python data-processing workspace

A baseline environment for turning messy source data (PDF / image / Excel / CSV)
into analysis-ready, structured data using Python. It targets the common flow of
extracting tables from documents, normalizing types (dates, numbers, encodings),
and exporting to Excel / CSV / JSON or SQLite for aggregation.

## Stack

Installed via `requirements.txt` (see pinned versions there):

- `pandas`, `numpy` — data manipulation
- `pdfplumber` — PDF text/table extraction
- `openpyxl` — Excel (`.xlsx`) read/write
- `reportlab` — PDF generation (used by the demo)
- `tqdm`, `tabulate` — progress bars and table formatting

Python's standard library provides `sqlite3`, `csv`, and `json`.

## Setup

The Cloud Agent environment (`.cursor/environment.json`) installs dependencies
automatically into the user site:

```bash
python3 -m pip install --user -r requirements.txt
```

Locally you can run the same command, or use a virtual environment if you prefer.

## Demo

Run the end-to-end example (PDF table → structured DataFrame → Excel/CSV + SQLite):

```bash
python3 examples/pdf_to_table.py
```

It generates a sample invoice PDF, extracts the table, normalizes mixed date
formats / full-width digits / currency strings, writes `structured.xlsx` and
`structured.csv`, loads the data into SQLite, and prints a `SUM`-by-product
aggregation. Outputs are written to `examples/output/` (git-ignored).
