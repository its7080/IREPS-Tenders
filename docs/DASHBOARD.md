# Analysis Dashboard Guide

`Analysis/script.py` serves a Dash dashboard for exploring merged IREPS tender workbooks.

## Running the dashboard

Install the unified project dependencies from the repository root, then start the app from the `Analysis/` directory:

```bash
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd Analysis
python script.py
```

Open the URL printed by Dash, usually:

```text
http://127.0.0.1:8050/
```

## Input data location

The dashboard currently reads Excel files recursively from:

```text
Analysis/data/
```

The path is hardcoded as `data` in `Analysis/script.py`, so the app should be launched from inside `Analysis/` unless the script is updated to use an absolute path or command-line argument.

## Expected workbook columns

The dashboard expects tender workbooks to include at least the columns used for filtering, metrics, tables, and charts:

| Column | Used for |
| --- | --- |
| `Tender No.` | De-duplication and row identity. |
| `Zone` | Zone filter, advertised-value chart, tender-count chart. |
| `Bidding System` | Bidding-system filter and pie chart. |
| `Due Date/Time` | Date filtering, next due date, closing-soon table. |
| `Advertised Value` | Total/average value metrics and charts. |
| `Doc Link` | Clickable document link when it contains an HTTP URL. |
| `Tender URL` | Clickable tender link when present and containing an HTTP URL. |
| `Bidders` | Unique bidder metric when present. |

Additional columns are preserved in the main table.

## Dashboard features

The app provides:

- multi-select zone filter
- multi-select bidding-system filter
- due-date range picker
- total tender count
- total advertised value
- average advertised value
- next due date
- unique bidder count when available
- most common bidding system
- full tender data table
- advertised value by zone chart
- bidding-system distribution chart
- tender count by zone chart
- table of tenders closing within the next seven days

## Data-loading behavior

At startup, the dashboard:

1. Recursively scans `Analysis/data/` for `.xlsx` files.
2. Reads each workbook with pandas.
3. Strips whitespace from column names.
4. Keeps only workbooks that contain `Tender No.`.
5. Concatenates all rows.
6. Drops duplicate tenders by `Tender No.`.
7. Converts `Due Date/Time` to dates and `Advertised Value` to numeric values.
8. Converts `Tender URL` and `Doc Link` values into markdown links when possible.

## Troubleshooting

- **`KeyError` on startup:** Confirm the input files contain the expected columns.
- **No rows appear:** Confirm files are under `Analysis/data/` and include `Tender No.`.
- **Date filter behaves unexpectedly:** Confirm `Due Date/Time` values are parseable and use day-first date format if needed.
- **Links are not clickable:** Confirm `Tender URL` or `Doc Link` values start with `http`.
- **Port already in use:** Stop the existing process on port `8050` or update the Dash app run configuration.
