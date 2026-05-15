# Analysis Dashboard Guide

`Analysis/script.py` serves an advanced Dash dashboard for exploring merged IREPS tender workbooks. It combines the original tender table and basic charts with deeper value, urgency, department, and priority analytics.

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

By default, the dashboard reads Excel files recursively from:

```text
Analysis/data/
```

The script uses `data` as its default input directory, so launch it from inside `Analysis/`. You can override the location without changing code by setting the `IREPS_ANALYSIS_DATA_DIR` environment variable before starting the app.

Examples:

```bash
IREPS_ANALYSIS_DATA_DIR=/path/to/merged/workbooks python script.py
```

```powershell
$env:IREPS_ANALYSIS_DATA_DIR = "C:\path\to\merged\workbooks"
python script.py
```

## Expected workbook columns

The dashboard can render even when optional columns are missing, but the richest analysis is available when workbooks include these fields:

| Column | Used for |
| --- | --- |
| `Tender No.` | De-duplication and row identity. Workbooks without this column are skipped. |
| `Zone` | Zone filtering and advertised-value-by-zone analysis. |
| `Dept.` | Department filtering and top-department value analysis. |
| `Tender Title` | Tender watchlist context. |
| `Type` | Preserved in the full tender table. |
| `Due Date/Time` | Date filtering, next due date, overdue/closing-soon metrics, urgency chart, and priority scoring. |
| `Advertised Value` | Total/average/median/largest value metrics, value range filtering, charts, and priority scoring. |
| `Doc Link` | Clickable document link when it contains an HTTP URL. |
| `Tender URL` | Clickable tender link when present and containing an HTTP URL. |
| `Bidding System` | Bidding-system filtering, distribution chart, most-common bidding-system metric, and table context. |
| `Date Time Of Uploading Tender` | Monthly upload trend chart. |
| `Earnest Money (Rs.)` | EMD percentage calculation and priority scoring. |
| `Contract Type` | Contract-type filtering. |
| `Bidders` | Optional single/low bidder signal in priority scoring when present. |

Additional columns are preserved in the full filtered table.

## Dashboard features

The upgraded dashboard provides:

- multi-select filters for zone, department, bidding system, and contract type
- due-date range filter
- advertised-value range filter
- quick analysis segments for all tenders, high-priority tenders, tenders closing in seven days, overdue tenders, high-value tenders, and missing-value tenders
- metric cards for total tenders, total value, average/median value, largest tender, next due date, closing-soon count, overdue count, high-priority count, department count, and common bidding system
- advertised value by zone chart
- bidding-system distribution by value chart
- top departments by advertised value chart
- due-date urgency chart
- monthly tender upload trend chart
- advertised-value band distribution chart
- priority tender watchlist with conditional highlighting
- full filtered tender data table with native sorting/filtering and XLSX export

## Priority scoring

The dashboard assigns a `Priority Score` and `Priority Level` to each tender to help focus review. The score is rule-based and intentionally transparent:

1. Tenders that are overdue, due today, or due within seven days receive urgency points.
2. Tenders at or above the 75th percentile of advertised value receive value points.
3. Tenders with high EMD burden (`Earnest Money (Rs.)` as a percentage of `Advertised Value`) receive EMD points.
4. If a `Bidders` column is available, tenders with one or fewer bidders receive bidder-risk points.

Scores are grouped into `Low`, `Medium`, and `High` priority levels. This is an analysis aid, not a procurement decision rule; teams should verify tender details before acting.

## Data-loading behavior

At startup, the dashboard:

1. Recursively scans the configured data directory for `.xlsx` files.
2. Reads each workbook with pandas.
3. Strips whitespace from column names.
4. Keeps only workbooks that contain `Tender No.`.
5. Adds a `Source File` column for traceability.
6. Concatenates all rows.
7. Drops duplicate tenders by `Tender No.`.
8. Adds any missing optional analysis columns as empty fields.
9. Converts date columns to datetimes and numeric columns to numbers.
10. Converts `Tender URL` and `Doc Link` values into markdown links when possible.
11. Derives `Days Until Due`, `Due Status`, `Value Band`, `Upload Month`, `EMD % of Value`, `Priority Score`, and `Priority Level`.

## Troubleshooting

- **No rows appear:** Confirm files are under `Analysis/data/` or set `IREPS_ANALYSIS_DATA_DIR`, and ensure workbooks include `Tender No.`.
- **A workbook is skipped:** Confirm it is a valid `.xlsx` file and has a readable worksheet.
- **Date filter behaves unexpectedly:** Confirm `Due Date/Time` values are parseable; the dashboard parses day-first date formats.
- **Upload trend is empty:** Confirm `Date Time Of Uploading Tender` is present and parseable.
- **Links are not clickable:** Confirm `Tender URL` or `Doc Link` values start with `http`.
- **Port already in use:** Stop the existing process on port `8050` or update the Dash app run configuration in `Analysis/script.py`.
