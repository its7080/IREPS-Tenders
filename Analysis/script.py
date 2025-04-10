import os
import glob
import pandas as pd
import dash
from dash import dcc, html, dash_table, Input, Output
import plotly.express as px
from datetime import datetime, timedelta

# Function to read and merge Excel files
def read_multiple_files(directory_path):
    all_files = glob.glob(os.path.join(directory_path, '**', '*.xlsx'), recursive=True)
    dataframes = []
    for file in all_files:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()
        if 'Tender No.' in df.columns:
            dataframes.append(df)
    return pd.concat(dataframes, ignore_index=True).drop_duplicates(subset=['Tender No.'], keep='first') if dataframes else pd.DataFrame()

# Load data
directory_path = 'data'
data = read_multiple_files(directory_path)

# Convert columns
data['Due Date/Time'] = pd.to_datetime(data.get('Due Date/Time'), errors='coerce', dayfirst=True)
data['Advertised Value'] = pd.to_numeric(data.get('Advertised Value'), errors='coerce')

# Make URLs clickable (Tender URL + Doc Link)
for col in ['Tender URL', 'Doc Link']:
    if col in data.columns:
        data[col] = data[col].apply(
            lambda x: f"[Click Here]({x})" if pd.notna(x) and isinstance(x, str) and x.startswith('http') else x
        )

# Metrics function
def get_metrics(df):
    return {
        "total_tenders": len(df),
        "total_value": df['Advertised Value'].sum(),
        "avg_value": df['Advertised Value'].mean(),
        "next_due": df['Due Date/Time'].min(),
        "unique_bidders": df['Bidders'].nunique() if 'Bidders' in df.columns else "N/A",
        "common_system": df['Bidding System'].mode()[0] if 'Bidding System' in df.columns and not df['Bidding System'].isna().all() else "N/A"
    }

# Dash app
app = dash.Dash(__name__)

# App layout
app.layout = html.Div([
    html.H1("IREPS Tenders Dashboard", style={'textAlign': 'center', 'marginBottom': '40px'}),

    # Filters
    html.Div([
        html.Div([
            html.Label("Select Zone(s)"),
            dcc.Dropdown(
                id='zone-filter',
                options=[{'label': z, 'value': z} for z in sorted(data['Zone'].dropna().unique())],
                placeholder="Select Zone(s)",
                multi=True
            )
        ], style={'width': '30%', 'marginRight': '20px'}),

        html.Div([
            html.Label("Select Bidding System(s)"),
            dcc.Dropdown(
                id='bidding-filter',
                options=[{'label': b, 'value': b} for b in sorted(data['Bidding System'].dropna().unique())],
                placeholder="Select Bidding System(s)",
                multi=True
            )
        ], style={'width': '30%', 'marginRight': '20px'}),

        html.Div([
            html.Label("Due Date Range"),
            dcc.DatePickerRange(
                id='date-filter',
                start_date=data['Due Date/Time'].min(),
                end_date=data['Due Date/Time'].max(),
                display_format='DD-MM-YYYY'
            )
        ], style={'width': '30%'})
    ], style={'display': 'flex', 'marginBottom': '40px', 'justifyContent': 'space-between'}),

    # Metrics Grid
    html.Div(id='metrics-container', style={
        'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'center', 'gap': '20px', 'marginBottom': '40px'
    }),

    # Main Table
    html.H2("Tenders Data Table"),
    dash_table.DataTable(
        id='tenders-table',
        columns=[
            {"name": i, "id": i, "presentation": "markdown"} if i in ["Tender URL", "Doc Link"] else {"name": i, "id": i}
            for i in data.columns
        ],
        page_size=10,
        style_table={'overflowX': 'auto'},
        style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'},
        style_data={'whiteSpace': 'normal', 'height': 'auto'},
        style_cell={'textAlign': 'left'}
    ),

    # Charts
    html.H2("Advertised Value by Zone"),
    dcc.Graph(id='zone-bar-chart'),

    html.H2("Bidding System Distribution"),
    dcc.Graph(id='bidding-pie-chart'),

    html.H2("Tender Count by Zone"),
    dcc.Graph(id='tender-count-chart'),

    # Tenders Closing Soon
    html.H2("Tenders Closing in the Next 7 Days"),
    dash_table.DataTable(
        id='closing-soon-table',
        columns=[
            {"name": i, "id": i, "presentation": "markdown"} if i in ["Tender URL", "Doc Link"] else {"name": i, "id": i}
            for i in data.columns
        ],
        page_size=5,
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left'}
    )
])

# Callback to update visuals based on filters
@app.callback(
    Output('metrics-container', 'children'),
    Output('tenders-table', 'data'),
    Output('zone-bar-chart', 'figure'),
    Output('bidding-pie-chart', 'figure'),
    Output('tender-count-chart', 'figure'),
    Output('closing-soon-table', 'data'),
    Input('zone-filter', 'value'),
    Input('bidding-filter', 'value'),
    Input('date-filter', 'start_date'),
    Input('date-filter', 'end_date')
)
def update_dashboard(selected_zone, selected_bidding, start_date, end_date):
    df = data.copy()
    if selected_zone:
        df = df[df['Zone'].isin(selected_zone)]
    if selected_bidding:
        df = df[df['Bidding System'].isin(selected_bidding)]
    if start_date and end_date:
        df = df[(df['Due Date/Time'] >= pd.to_datetime(start_date)) & (df['Due Date/Time'] <= pd.to_datetime(end_date))]

    metrics = get_metrics(df)

    # Metric cards
    cards = [
        html.Div([html.H3("Total Tenders"), html.P(f"{metrics['total_tenders']}")], style=card_style()),
        html.Div([html.H3("Total Advertised Value"), html.P(f"₹{metrics['total_value']:,.2f}")], style=card_style()),
        html.Div([html.H3("Average Advertised Value"), html.P(f"₹{metrics['avg_value']:,.2f}")], style=card_style()),
        html.Div([html.H3("Next Due Date"), html.P(metrics['next_due'].strftime('%d-%m-%Y') if pd.notna(metrics['next_due']) else "N/A")], style=card_style()),
        html.Div([html.H3("Unique Bidders"), html.P(metrics['unique_bidders'])], style=card_style()),
        html.Div([html.H3("Most Common Bidding System"), html.P(metrics['common_system'])], style=card_style())
    ]

    # Charts
    bar_chart = px.bar(df, x='Zone', y='Advertised Value', title="Advertised Value by Zone", text_auto=True)
    pie_chart = px.pie(df, names='Bidding System', values='Advertised Value', title="Bidding System Distribution")
    count_chart = px.bar(df.groupby("Zone").size().reset_index(name="Tender Count"), x="Zone", y="Tender Count", title="Tender Count by Zone")

    # Tenders closing soon
    today = datetime.today()
    closing = df[(df['Due Date/Time'] >= today) & (df['Due Date/Time'] <= today + timedelta(days=7))]

    return cards, df.to_dict('records'), bar_chart, pie_chart, count_chart, closing.to_dict('records')

# Reusable card style
def card_style():
    return {
        'flex': '0 0 30%',
        'backgroundColor': '#f9f9f9',
        'padding': '20px',
        'boxShadow': '0 4px 8px rgba(0, 0, 0, 0.1)',
        'borderRadius': '10px',
        'textAlign': 'center'
    }

# Run app
if __name__ == '__main__':
    app.run(debug=True)
