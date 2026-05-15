from __future__ import annotations

import glob
import os
from datetime import datetime
from typing import Iterable

import dash
import pandas as pd
import plotly.express as px
from dash import Input, Output, dash_table, dcc, html
from plotly import graph_objects as go

DATA_DIRECTORY = os.environ.get("IREPS_ANALYSIS_DATA_DIR", "data")
TODAY = pd.Timestamp(datetime.today().date())
REQUIRED_COLUMNS = [
    "Tender No.",
    "Zone",
    "Dept.",
    "Tender Title",
    "Type",
    "Due Date/Time",
    "Advertised Value",
    "Bidding System",
    "Contract Type",
    "Earnest Money (Rs.)",
    "Date Time Of Uploading Tender",
    "Tender URL",
    "Doc Link",
    "Bidders",
]
LINK_COLUMNS = ["Tender URL", "Doc Link"]
DATE_COLUMNS = ["Due Date/Time", "Date Time Of Uploading Tender", "Pre-Bid Conference Date Time", "Get Date"]
NUMERIC_COLUMNS = ["Advertised Value", "Earnest Money (Rs.)", "Due Days", "Bidders"]


def _empty_tender_frame() -> pd.DataFrame:
    """Return a schema-compatible empty dataframe so the dashboard can still render."""
    return pd.DataFrame(columns=REQUIRED_COLUMNS)


def read_multiple_files(directory_path: str) -> pd.DataFrame:
    """Read all Excel workbooks recursively and merge tender rows by Tender No."""
    all_files = glob.glob(os.path.join(directory_path, "**", "*.xlsx"), recursive=True)
    dataframes: list[pd.DataFrame] = []

    for file_path in all_files:
        try:
            df = pd.read_excel(file_path)
        except Exception as exc:  # Keep one bad workbook from breaking the dashboard.
            print(f"Skipping {file_path}: {exc}")
            continue

        df.columns = df.columns.astype(str).str.strip()
        if "Tender No." not in df.columns:
            continue

        df["Source File"] = os.path.relpath(file_path, directory_path)
        dataframes.append(df)

    if not dataframes:
        return _empty_tender_frame()

    merged = pd.concat(dataframes, ignore_index=True)
    return merged.drop_duplicates(subset=["Tender No."], keep="first")


def ensure_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """Add missing optional columns used by the advanced dashboard."""
    df = df.copy()
    for column in columns:
        if column not in df.columns:
            df[column] = pd.NA
    return df


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize dates, numbers, links, and derived analytical fields."""
    df = ensure_columns(df, REQUIRED_COLUMNS)
    df = df.copy()

    for column in DATE_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce", dayfirst=True)

    for column in NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in ["Zone", "Dept.", "Bidding System", "Contract Type", "Type"]:
        df[column] = df[column].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")

    for column in LINK_COLUMNS:
        if column in df.columns:
            df[column] = df[column].apply(
                lambda value: f"[Click Here]({value})"
                if pd.notna(value) and isinstance(value, str) and value.startswith("http")
                else value
            )

    df["Days Until Due"] = (df["Due Date/Time"].dt.normalize() - TODAY).dt.days
    df["Due Status"] = pd.cut(
        df["Days Until Due"],
        bins=[-10_000, -1, 0, 7, 30, 90, 10_000],
        labels=["Overdue", "Due Today", "Due in 7 Days", "Due in 30 Days", "Due in 90 Days", "Later"],
    ).astype("object")
    df.loc[df["Days Until Due"].isna(), "Due Status"] = "No Due Date"

    value = df["Advertised Value"].fillna(0)
    df["Value Band"] = pd.cut(
        value,
        bins=[-1, 0, 100_000, 1_000_000, 10_000_000, 100_000_000, float("inf")],
        labels=["No Value", "≤ ₹1L", "₹1L-₹10L", "₹10L-₹1Cr", "₹1Cr-₹10Cr", "> ₹10Cr"],
    ).astype("object")

    df["Upload Month"] = df["Date Time Of Uploading Tender"].dt.to_period("M").astype("string")
    df["EMD % of Value"] = (df["Earnest Money (Rs.)"] / df["Advertised Value"].replace(0, pd.NA) * 100).round(2)

    value_75 = df["Advertised Value"].quantile(0.75) if df["Advertised Value"].notna().any() else 0
    df["Priority Score"] = 0
    df.loc[df["Due Status"].isin(["Overdue", "Due Today", "Due in 7 Days"]), "Priority Score"] += 40
    df.loc[df["Advertised Value"] >= value_75, "Priority Score"] += 30
    df.loc[df["EMD % of Value"] >= 5, "Priority Score"] += 15
    df.loc[df["Bidders"].fillna(2) <= 1, "Priority Score"] += 15
    df["Priority Level"] = pd.cut(
        df["Priority Score"],
        bins=[-1, 29, 59, 100],
        labels=["Low", "Medium", "High"],
    ).astype("object")

    return df


raw_data = read_multiple_files(DATA_DIRECTORY)
data = prepare_data(raw_data)


def dropdown_options(column: str) -> list[dict[str, str]]:
    values = sorted(value for value in data[column].dropna().unique() if str(value).strip())
    return [{"label": value, "value": value} for value in values]


def value_slider_bounds() -> tuple[int, int]:
    values = data["Advertised Value"].dropna()
    if values.empty:
        return 0, 0
    return int(max(values.min(), 0)), int(max(values.max(), 0))



def date_picker_value(value: object) -> object:
    """Return None instead of NaT so Dash can serialize empty date ranges."""
    return None if pd.isna(value) else value

def format_currency(value: object) -> str:
    if pd.isna(value):
        return "₹0.00"
    return f"₹{float(value):,.2f}"


def get_metrics(df: pd.DataFrame) -> dict[str, object]:
    next_due = df.loc[df["Due Date/Time"].notna() & (df["Due Date/Time"] >= TODAY), "Due Date/Time"].min()
    return {
        "total_tenders": len(df),
        "total_value": df["Advertised Value"].sum(skipna=True),
        "avg_value": df["Advertised Value"].mean(skipna=True),
        "median_value": df["Advertised Value"].median(skipna=True),
        "max_value": df["Advertised Value"].max(skipna=True),
        "next_due": next_due,
        "closing_soon": int(df["Due Status"].isin(["Due Today", "Due in 7 Days"]).sum()),
        "overdue": int((df["Due Status"] == "Overdue").sum()),
        "high_priority": int((df["Priority Level"] == "High").sum()),
        "unique_departments": df["Dept."].nunique(),
        "common_system": df["Bidding System"].mode().iloc[0] if not df["Bidding System"].mode().empty else "N/A",
    }


def metric_card(title: str, value: object, subtitle: str | None = None) -> html.Div:
    children = [html.H3(title), html.P(value, className="metric-value")]
    if subtitle:
        children.append(html.Span(subtitle, className="metric-subtitle"))
    return html.Div(children, className="metric-card")


def empty_figure(title: str, message: str = "No matching tender data") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=title, template="plotly_white", annotations=[{"text": message, "showarrow": False}])
    return fig


def table_records(df: pd.DataFrame) -> list[dict[str, object]]:
    display = df.copy()
    for column in DATE_COLUMNS:
        if column in display.columns:
            display[column] = display[column].dt.strftime("%d-%m-%Y %H:%M").fillna("")
    for column in ["Advertised Value", "Earnest Money (Rs.)"]:
        if column in display.columns:
            display[column] = display[column].apply(lambda value: "" if pd.isna(value) else round(float(value), 2))
    return display.where(pd.notna(display), None).to_dict("records")


min_value, max_value = value_slider_bounds()
value_step = max(int((max_value - min_value) / 100), 1) if max_value > min_value else 1

app = dash.Dash(__name__)
app.title = "IREPS Advanced Tender Analysis"

app.layout = html.Div(
    [
        html.Div(
            [
                html.H1("IREPS Advanced Tender Analysis"),
                html.P(
                    "Explore tender value, urgency, department concentration, bidding patterns, and priority signals from merged IREPS workbooks."
                ),
            ],
            className="hero",
        ),
        html.Div(
            [
                html.Div([html.Label("Zone"), dcc.Dropdown(id="zone-filter", options=dropdown_options("Zone"), multi=True)], className="filter-card"),
                html.Div([html.Label("Department"), dcc.Dropdown(id="dept-filter", options=dropdown_options("Dept."), multi=True)], className="filter-card"),
                html.Div([html.Label("Bidding System"), dcc.Dropdown(id="bidding-filter", options=dropdown_options("Bidding System"), multi=True)], className="filter-card"),
                html.Div([html.Label("Contract Type"), dcc.Dropdown(id="contract-filter", options=dropdown_options("Contract Type"), multi=True)], className="filter-card"),
                html.Div(
                    [
                        html.Label("Due Date Range"),
                        dcc.DatePickerRange(
                            id="date-filter",
                            start_date=date_picker_value(data["Due Date/Time"].min()),
                            end_date=date_picker_value(data["Due Date/Time"].max()),
                            display_format="DD-MM-YYYY",
                        ),
                    ],
                    className="filter-card",
                ),
                html.Div(
                    [
                        html.Label("Advertised Value Range"),
                        dcc.RangeSlider(
                            id="value-filter",
                            min=min_value,
                            max=max_value,
                            step=value_step,
                            value=[min_value, max_value],
                            tooltip={"placement": "bottom", "always_visible": False},
                        ),
                    ],
                    className="filter-card wide",
                ),
                html.Div(
                    [
                        html.Label("Analysis Segment"),
                        dcc.Dropdown(
                            id="segment-filter",
                            value="all",
                            options=[
                                {"label": "All Tenders", "value": "all"},
                                {"label": "High Priority", "value": "high_priority"},
                                {"label": "Closing in 7 Days", "value": "closing_soon"},
                                {"label": "Overdue", "value": "overdue"},
                                {"label": "High Value", "value": "high_value"},
                                {"label": "Missing Advertised Value", "value": "missing_value"},
                            ],
                            clearable=False,
                        ),
                    ],
                    className="filter-card",
                ),
            ],
            className="filters-grid",
        ),
        html.Div(id="metrics-container", className="metrics-grid"),
        html.Div(
            [
                dcc.Graph(id="zone-bar-chart"),
                dcc.Graph(id="bidding-pie-chart"),
                dcc.Graph(id="dept-value-chart"),
                dcc.Graph(id="due-status-chart"),
                dcc.Graph(id="upload-trend-chart"),
                dcc.Graph(id="value-band-chart"),
            ],
            className="charts-grid",
        ),
        html.H2("Priority Tender Watchlist"),
        dash_table.DataTable(
            id="priority-table",
            columns=[{"name": column, "id": column, "presentation": "markdown"} if column in LINK_COLUMNS else {"name": column, "id": column} for column in data.columns],
            page_size=8,
            sort_action="native",
            filter_action="native",
            style_table={"overflowX": "auto"},
            style_header={"backgroundColor": "#1f2937", "color": "white", "fontWeight": "bold"},
            style_cell={"textAlign": "left", "minWidth": "120px", "whiteSpace": "normal", "height": "auto"},
            style_data_conditional=[
                {"if": {"filter_query": "{Priority Level} = High"}, "backgroundColor": "#fee2e2"},
                {"if": {"filter_query": "{Due Status} = Overdue"}, "color": "#b91c1c", "fontWeight": "bold"},
            ],
        ),
        html.H2("Filtered Tender Data"),
        dash_table.DataTable(
            id="tenders-table",
            columns=[{"name": column, "id": column, "presentation": "markdown"} if column in LINK_COLUMNS else {"name": column, "id": column} for column in data.columns],
            page_size=15,
            sort_action="native",
            filter_action="native",
            export_format="xlsx",
            style_table={"overflowX": "auto"},
            style_header={"backgroundColor": "#e5e7eb", "fontWeight": "bold"},
            style_data={"whiteSpace": "normal", "height": "auto"},
            style_cell={"textAlign": "left", "minWidth": "120px"},
        ),
    ],
    className="page",
)

app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body { margin: 0; background: #f3f4f6; color: #111827; font-family: Arial, sans-serif; }
            .page { padding: 24px; }
            .hero { background: linear-gradient(135deg, #0f172a, #1d4ed8); color: white; padding: 28px; border-radius: 18px; margin-bottom: 24px; }
            .hero h1 { margin: 0 0 8px; }
            .hero p { max-width: 920px; margin: 0; line-height: 1.5; }
            .filters-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 24px; }
            .filter-card, .metric-card { background: white; padding: 16px; border-radius: 14px; box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08); }
            .filter-card label { display: block; font-weight: 700; margin-bottom: 8px; }
            .wide { grid-column: span 2; }
            .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; margin-bottom: 24px; }
            .metric-card h3 { color: #475569; font-size: 0.95rem; margin: 0 0 8px; }
            .metric-value { color: #0f172a; font-size: 1.6rem; font-weight: 800; margin: 0; }
            .metric-subtitle { color: #64748b; font-size: 0.85rem; }
            .charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(430px, 1fr)); gap: 18px; margin-bottom: 24px; }
            h2 { margin-top: 28px; }
            @media (max-width: 720px) { .wide { grid-column: span 1; } .charts-grid { grid-template-columns: 1fr; } }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>{%config%}{%scripts%}{%renderer%}</footer>
    </body>
</html>
"""


@app.callback(
    Output("metrics-container", "children"),
    Output("tenders-table", "data"),
    Output("priority-table", "data"),
    Output("zone-bar-chart", "figure"),
    Output("bidding-pie-chart", "figure"),
    Output("dept-value-chart", "figure"),
    Output("due-status-chart", "figure"),
    Output("upload-trend-chart", "figure"),
    Output("value-band-chart", "figure"),
    Input("zone-filter", "value"),
    Input("dept-filter", "value"),
    Input("bidding-filter", "value"),
    Input("contract-filter", "value"),
    Input("date-filter", "start_date"),
    Input("date-filter", "end_date"),
    Input("value-filter", "value"),
    Input("segment-filter", "value"),
)
def update_dashboard(selected_zone, selected_dept, selected_bidding, selected_contract, start_date, end_date, value_range, segment):
    df = data.copy()

    if selected_zone:
        df = df[df["Zone"].isin(selected_zone)]
    if selected_dept:
        df = df[df["Dept."].isin(selected_dept)]
    if selected_bidding:
        df = df[df["Bidding System"].isin(selected_bidding)]
    if selected_contract:
        df = df[df["Contract Type"].isin(selected_contract)]
    if start_date:
        df = df[df["Due Date/Time"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["Due Date/Time"] <= pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]
    if value_range and len(value_range) == 2:
        df = df[df["Advertised Value"].between(value_range[0], value_range[1], inclusive="both") | df["Advertised Value"].isna()]

    high_value_cutoff = data["Advertised Value"].quantile(0.75) if data["Advertised Value"].notna().any() else 0
    if segment == "high_priority":
        df = df[df["Priority Level"] == "High"]
    elif segment == "closing_soon":
        df = df[df["Due Status"].isin(["Due Today", "Due in 7 Days"])]
    elif segment == "overdue":
        df = df[df["Due Status"] == "Overdue"]
    elif segment == "high_value":
        df = df[df["Advertised Value"] >= high_value_cutoff]
    elif segment == "missing_value":
        df = df[df["Advertised Value"].isna()]

    metrics = get_metrics(df)
    cards = [
        metric_card("Total Tenders", f"{metrics['total_tenders']:,}", "after all active filters"),
        metric_card("Total Advertised Value", format_currency(metrics["total_value"]), "sum of visible tenders"),
        metric_card("Average Value", format_currency(metrics["avg_value"]), f"median {format_currency(metrics['median_value'])}"),
        metric_card("Largest Tender", format_currency(metrics["max_value"]), "highest advertised value"),
        metric_card("Next Due Date", metrics["next_due"].strftime("%d-%m-%Y") if pd.notna(metrics["next_due"]) else "N/A", "future due dates only"),
        metric_card("Closing Soon", f"{metrics['closing_soon']:,}", "due today or within 7 days"),
        metric_card("Overdue", f"{metrics['overdue']:,}", "based on local run date"),
        metric_card("High Priority", f"{metrics['high_priority']:,}", "urgency/value/EMD score"),
        metric_card("Departments", f"{metrics['unique_departments']:,}", f"common system: {metrics['common_system']}"),
    ]

    if df.empty:
        empty_records: list[dict[str, object]] = []
        return (
            cards,
            empty_records,
            empty_records,
            empty_figure("Advertised Value by Zone"),
            empty_figure("Bidding System Distribution"),
            empty_figure("Top Departments by Advertised Value"),
            empty_figure("Due-Date Urgency"),
            empty_figure("Tender Upload Trend"),
            empty_figure("Advertised Value Bands"),
        )

    zone_summary = df.groupby("Zone", as_index=False)["Advertised Value"].sum().sort_values("Advertised Value", ascending=False)
    bar_chart = px.bar(zone_summary, x="Zone", y="Advertised Value", title="Advertised Value by Zone", text_auto=",.2s", template="plotly_white")

    bidding_summary = df.groupby("Bidding System", as_index=False)["Advertised Value"].sum()
    pie_chart = px.pie(bidding_summary, names="Bidding System", values="Advertised Value", title="Bidding System Distribution by Value", hole=0.35)

    dept_summary = df.groupby("Dept.", as_index=False).agg({"Advertised Value": "sum", "Tender No.": "count"}).rename(columns={"Tender No.": "Tender Count"})
    dept_summary = dept_summary.sort_values("Advertised Value", ascending=False).head(15)
    dept_chart = px.bar(dept_summary, x="Advertised Value", y="Dept.", color="Tender Count", orientation="h", title="Top Departments by Advertised Value", template="plotly_white")

    due_order = ["Overdue", "Due Today", "Due in 7 Days", "Due in 30 Days", "Due in 90 Days", "Later", "No Due Date"]
    due_summary = df.groupby("Due Status", as_index=False).size().rename(columns={"size": "Tender Count"})
    due_summary["Due Status"] = pd.Categorical(due_summary["Due Status"], due_order, ordered=True)
    due_summary = due_summary.sort_values("Due Status")
    due_chart = px.bar(due_summary, x="Due Status", y="Tender Count", title="Due-Date Urgency", color="Due Status", template="plotly_white")

    trend_df = df.dropna(subset=["Upload Month"]).groupby("Upload Month", as_index=False).agg({"Tender No.": "count", "Advertised Value": "sum"}).rename(columns={"Tender No.": "Tender Count"})
    trend_chart = px.line(trend_df, x="Upload Month", y="Tender Count", markers=True, title="Tender Upload Trend", template="plotly_white") if not trend_df.empty else empty_figure("Tender Upload Trend")

    band_order = ["No Value", "≤ ₹1L", "₹1L-₹10L", "₹10L-₹1Cr", "₹1Cr-₹10Cr", "> ₹10Cr"]
    band_summary = df.groupby("Value Band", as_index=False).size().rename(columns={"size": "Tender Count"})
    band_summary["Value Band"] = pd.Categorical(band_summary["Value Band"], band_order, ordered=True)
    band_summary = band_summary.sort_values("Value Band")
    band_chart = px.bar(band_summary, x="Value Band", y="Tender Count", title="Advertised Value Bands", color="Value Band", template="plotly_white")

    priority_columns = [
        "Priority Level",
        "Priority Score",
        "Due Status",
        "Days Until Due",
        "Tender No.",
        "Tender Title",
        "Zone",
        "Dept.",
        "Advertised Value",
        "Earnest Money (Rs.)",
        "EMD % of Value",
        "Due Date/Time",
        "Bidding System",
        "Doc Link",
    ]
    priority_df = df.sort_values(["Priority Score", "Advertised Value"], ascending=[False, False]).head(50)

    return (
        cards,
        table_records(df),
        table_records(priority_df[[column for column in priority_columns if column in priority_df.columns]]),
        bar_chart,
        pie_chart,
        dept_chart,
        due_chart,
        trend_chart,
        band_chart,
    )


if __name__ == "__main__":
    app.run(debug=True)
