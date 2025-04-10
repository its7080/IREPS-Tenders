import os
import glob
import pandas as pd
import dash
from dash import dcc, html, dash_table
import plotly.express as px
from datetime import datetime, timedelta

# Function to read multiple Excel files and merge them (Union based on 'Tender No.')
def read_multiple_files(directory_path):
    all_files = glob.glob(os.path.join(directory_path, '**', '*.xlsx'), recursive=True)
    dataframes = []
    
    for file in all_files:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()  # Standardize column names
        if 'Tender No.' in df.columns:
            dataframes.append(df)
    
    if dataframes:
        merged_data = pd.concat(dataframes, ignore_index=True).drop_duplicates(subset=['Tender No.'], keep='first')
        return merged_data
    else:
        return pd.DataFrame()

# Load data from 'data' folder
directory_path = 'data'
data = read_multiple_files(directory_path)

# Ensure required columns exist and format them
if 'Due Date/Time' in data.columns:
    data['Due Date/Time'] = pd.to_datetime(data['Due Date/Time'], errors='coerce', dayfirst=True)
else:
    data['Due Date/Time'] = pd.NaT

if 'Advertised Value' in data.columns:
    data['Advertised Value'] = pd.to_numeric(data['Advertised Value'], errors='coerce')
else:
    data['Advertised Value'] = 0

# Additional Calculations
total_tenders = len(data)
total_advertised_value = data['Advertised Value'].sum()
average_advertised_value = data['Advertised Value'].mean()
next_due_date = data['Due Date/Time'].min()

unique_bidders = data['Bidders'].nunique() if 'Bidders' in data.columns else "N/A"
most_common_bidding_system = data['Bidding System'].mode()[0] if 'Bidding System' in data.columns else "N/A"

# Filter tenders closing in the next 7 days
today = datetime.today()
closing_soon = data[(data['Due Date/Time'] >= today) & (data['Due Date/Time'] <= today + timedelta(days=7))]

# Initialize Dash app
app = dash.Dash(__name__)

# App Layout
app.layout = html.Div([
    html.H1("IREPS Tenders Dashboard", style={'textAlign': 'center', 'marginBottom': '40px'}),
    
    # Key Metrics in 2x3 card layout
    html.Div([
        html.Div([html.H3("Total Tenders"), html.P(f"{total_tenders}")], style={
            'flex': '0 0 30%',
            'backgroundColor': '#f9f9f9',
            'padding': '20px',
            'boxShadow': '0 4px 8px rgba(0, 0, 0, 0.1)',
            'borderRadius': '10px',
            'textAlign': 'center'
        }),
        html.Div([html.H3("Total Advertised Value"), html.P(f"₹{total_advertised_value:,.2f}")], style={
            'flex': '0 0 30%',
            'backgroundColor': '#f9f9f9',
            'padding': '20px',
            'boxShadow': '0 4px 8px rgba(0, 0, 0, 0.1)',
            'borderRadius': '10px',
            'textAlign': 'center'
        }),
        html.Div([html.H3("Average Advertised Value"), html.P(f"₹{average_advertised_value:,.2f}")], style={
            'flex': '0 0 30%',
            'backgroundColor': '#f9f9f9',
            'padding': '20px',
            'boxShadow': '0 4px 8px rgba(0, 0, 0, 0.1)',
            'borderRadius': '10px',
            'textAlign': 'center'
        }),
        html.Div([html.H3("Next Due Date"), html.P(next_due_date.strftime('%d-%m-%Y') if pd.notna(next_due_date) else "N/A")], style={
            'flex': '0 0 30%',
            'backgroundColor': '#f9f9f9',
            'padding': '20px',
            'boxShadow': '0 4px 8px rgba(0, 0, 0, 0.1)',
            'borderRadius': '10px',
            'textAlign': 'center'
        }),
        html.Div([html.H3("Unique Bidders"), html.P(unique_bidders)], style={
            'flex': '0 0 30%',
            'backgroundColor': '#f9f9f9',
            'padding': '20px',
            'boxShadow': '0 4px 8px rgba(0, 0, 0, 0.1)',
            'borderRadius': '10px',
            'textAlign': 'center'
        }),
        html.Div([html.H3("Most Common Bidding System"), html.P(most_common_bidding_system)], style={
            'flex': '0 0 30%',
            'backgroundColor': '#f9f9f9',
            'padding': '20px',
            'boxShadow': '0 4px 8px rgba(0, 0, 0, 0.1)',
            'borderRadius': '10px',
            'textAlign': 'center'
        }),
    ], style={
        'display': 'flex',
        'flexWrap': 'wrap',
        'justifyContent': 'center',
        'gap': '20px',
        'marginBottom': '40px'
    }),
    
    # Data Table
    html.H2("Tenders Data Table"),
    dash_table.DataTable(
        id='tenders-table',
        columns=[{"name": i, "id": i} for i in data.columns],
        data=data.to_dict('records'),
        page_size=10,
        style_table={'overflowX': 'auto'}
    ),
    
    # Bar Chart - Advertised Value by Zone
    html.H2("Advertised Value by Zone"),
    dcc.Graph(
        figure=px.bar(data, x='Zone', y='Advertised Value', title="Advertised Value by Zone", text_auto=True)
    ),
    
    # Pie Chart - Bidding System Distribution
    html.H2("Bidding System Distribution"),
    dcc.Graph(
        figure=px.pie(data, names='Bidding System', values='Advertised Value', title="Bidding System Distribution")
    ),

    # Bar Chart - Tender Count by Zone
    html.H2("Number of Tenders by Zone"),
    dcc.Graph(
        figure=px.bar(data.groupby("Zone").size().reset_index(name="Tender Count"), 
                      x="Zone", y="Tender Count", title="Tender Count by Zone")
    ),

    # Table for Tenders Closing Soon (Next 7 Days)
    html.H2("Tenders Closing in the Next 7 Days"),
    dash_table.DataTable(
        id='closing-soon-table',
        columns=[{"name": i, "id": i} for i in closing_soon.columns],
        data=closing_soon.to_dict('records'),
        page_size=5,
        style_table={'overflowX': 'auto'}
    )
])

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
