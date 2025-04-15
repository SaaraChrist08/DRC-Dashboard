import streamlit as st
import gspread
import pandas as pd
import plotly.express as px
from google.oauth2.service_account import Credentials
from st_aggrid import AgGrid, GridOptionsBuilder
from streamlit_plotly_events import plotly_events  # Import event capture function

# Path to your service account key file
SERVICE_ACCOUNT_FILE = "service_account.json"

# Define the scope for Google APIs
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Authenticate using the service account
credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(credentials)

# Rest of your code remains the same...
# Open the master Google Sheet by key or URL
sheet_name = "DRC_Compiled"
spreadsheet = gc.open(sheet_name)

# Access the "Primary Table" worksheet
worksheet = spreadsheet.worksheet("Main")

# Convert the worksheet data to a Pandas DataFrame
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# Access the "pdftosheets" worksheet for monthly data
worksheet_monthly = spreadsheet.worksheet("pdftosheet")
data_monthly = worksheet_monthly.get_all_records()
df_monthly = pd.DataFrame(data_monthly)

# Ensure numeric columns are numeric
df['SUM of Payable Days'] = pd.to_numeric(df['SUM of Payable Days'], errors='coerce')
df['Updated Absent Days'] = pd.to_numeric(df['Updated Absent Days'], errors='coerce')
df['Extension Days '] = pd.to_numeric(df['Extension Days '], errors='coerce')
df['Year '] = pd.to_numeric(df['Year '], errors='coerce')

# Ensure numeric columns in monthly data
df_monthly['Payable Days'] = pd.to_numeric(df_monthly['Payable Days'], errors='coerce')
df_monthly['Absent Days'] = pd.to_numeric(df_monthly['Absent Days'], errors='coerce')
df_monthly['Days in Month'] = pd.to_numeric(df_monthly['Days in Month'], errors='coerce')

# Filter rows where "Name" has characters
df = df[df['Name'].str.strip().astype(bool)]

df['Defaulter'] = df.apply(
    lambda row: 'Defaulter' if (
        pd.notna(row['Updated Absent Days']) and  # Ensure Updated Absent Days is present
        (
            (pd.isna(row['Year ']) and pd.to_numeric(row['Updated Absent Days'], errors='coerce') > 24) or
            (pd.notna(row['Year ']) and row['Year '] < 2023 and pd.to_numeric(row['Updated Absent Days'], errors='coerce') > 156) or
            (pd.notna(row['Year ']) and row['Year '] >= 2023 and pd.to_numeric(row['Updated Absent Days'], errors='coerce') > 24)
        )
    ) else 'Non-Defaulter',
    axis=1
)


# Streamlit App
st.set_page_config(layout="wide")
st.title("DRC Attendance Dashboard")

# Sidebar for Navigation
st.sidebar.title("Navigation")
page_selection = st.sidebar.radio("Go to", ["Main Dashboard", "Monthly Data", "Individual Dashboard", "Daily Dashboard"])


if page_selection == "Individual Dashboard":
    st.sidebar.title("Filter Options")
    article_list = ["All"] + df['Name'].unique().tolist()
    selected_article = st.sidebar.selectbox("Select Article Name", article_list)
    
    month_list = ["All"] + df_monthly['Month'].unique().tolist()
    selected_month = st.sidebar.selectbox("Select Month", month_list)
    
    if selected_article == "All":
        filtered_df = df
        filtered_monthly_df = df_monthly
    else:
        filtered_df = df[df['Name'] == selected_article]
        filtered_monthly_df = df_monthly[df_monthly['Name'] == selected_article]
    
    if selected_month != "All":
        filtered_monthly_df = filtered_monthly_df[filtered_monthly_df['Month'] == selected_month]
    
    st.subheader(f"Attendance Breakdown for {selected_article} in {selected_month if selected_month != 'All' else 'All Months'}")
    

    # Prepare data for pie chart
    pie_data = {
        'Category': ['Payable Days', 'Absent Days', 'Half Day'],
        'Count': [
            filtered_monthly_df['Payable Days'].sum(),
            filtered_monthly_df['Absent Days'].sum(),
            filtered_monthly_df['Days in Month'].sum() - (filtered_monthly_df['Payable Days'].sum() + filtered_monthly_df['Absent Days'].sum())
            ]
            }
            
    pie_df = pd.DataFrame(pie_data)

    # Create pie chart
    pie_chart = px.pie(
        pie_df, 
        names='Category',
        values='Count',
        color='Category',
        color_discrete_map={'Absent Days': 'tomato', 'Payable Days': 'mediumpurple', 'Half Day': 'papayawhip'},
        title="Attendance Percentage"
        )

    st.plotly_chart(pie_chart, use_container_width=True)

    
    bar_chart = px.bar(
        filtered_monthly_df,
        x='Name',
        y=['Payable Days', 'Absent Days'],
        barmode='group',
        labels={'Name': 'Article Name', 'value': 'Days'},
        color_discrete_map={'Payable Days': 'mediumpurple','Absent Days': 'papayawhip'},
        title=f"Payable vs Absent Days for {selected_article}"
    )
    bar_chart.for_each_trace(lambda t: t.update(name='Payable Days' if 'Payable Days' in t.name else 'Absent Days'))
    st.plotly_chart(bar_chart, use_container_width=True)

if page_selection == "Main Dashboard":
    # Sidebar for Article Name Selection
    st.sidebar.title("Filter Options")
    article_list = ["All"] + df['Name'].unique().tolist()
    selected_article = st.sidebar.selectbox("Select Article Name", article_list)

    # Filter data based on selected article name
    if selected_article == "All":
        filtered_df = df
    else:
        filtered_df = df[df['Name'] == selected_article]

    # Display KPIs for selected article
    if selected_article != "All":
        total_present_days = filtered_df['SUM of Payable Days'].sum()
        total_absent_days = filtered_df['Updated Absent Days'].sum()

        st.subheader(f"KPIs for {selected_article}")
        st.metric(label="Total Present Days", value=total_present_days)
        st.metric(label="Total Absent Days", value=total_absent_days)

    # Combined Bar Chart: Present vs Absent of each Article
    st.subheader("Combined Bar Chart: Present vs Absent of each Article")
    present_absent_chart = filtered_df.groupby('Name')[['SUM of Payable Days', 'Updated Absent Days']].sum().reset_index()
    fig1 = px.bar(
        present_absent_chart,
        x='Name',
        y=['SUM of Payable Days', 'Updated Absent Days'],
        barmode='group',
        labels={'Name': 'Name', 'value': 'Count'},
        color_discrete_map={'SUM of Payable Days': 'mediumpurple','Updated Absent Days': 'papayawhip'},
        title="Combined Bar Chart: Present vs Absent of each Article"
    )

    # Update the legend names to reflect the correct labels
    fig1.for_each_trace(lambda t: t.update(name='Present Days' if 'SUM of Payable Days' in t.name else 'Absent Days'))

    st.plotly_chart(fig1, use_container_width=True)

    # Convert 'Updated Absent Days ' to numeric to avoid TypeError
    filtered_df['Updated Absent Days'] = pd.to_numeric(filtered_df['Updated Absent Days'], errors='coerce')

    # Apply defaulter logic
    filtered_df['Defaulter'] = filtered_df.apply(
        lambda row: 'Non-Defaulter' if (
            (pd.notna(row['Year ']) and row['Year '] < 2023 and row['Updated Absent Days'] <= 156) or
            (pd.notna(row['Year ']) and row['Year '] >= 2023 and row['Updated Absent Days'] <= 24) or
            (pd.isna(row['Year ']) and row['Updated Absent Days'] <= 24)  # Handle missing 'Year'
        ) else 'Defaulter',
        axis=1
    )

    # Visualization: Defaulter Chart
    st.subheader("Defaulter Visualization")
    fig2 = px.bar(
        filtered_df,
        x='Name',
        y='Updated Absent Days',
        color='Defaulter',
        color_discrete_map={'Defaulter': 'mediumpurple', 'Non-Defaulter': 'papayawhip'},
        labels={'Updated Absent Days': 'Days Absent', 'Name': 'Name'}
    )
    st.plotly_chart(fig2, use_container_width=True) 


    
    # --- Layout for Funnel Chart and Pie Chart Side by Side ---
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie Chart for Transfer Case
        st.subheader("Transfer Case Distribution")
        transfer_counts = filtered_df[filtered_df['Transfer case '].isin(["Yes", "No"])]
        transfer_counts = transfer_counts['Transfer case '].value_counts().reset_index()
        transfer_counts.columns = ['Transfer case ', 'Count']
        
        fig_pie = px.pie(
            transfer_counts,
            names='Transfer case ',
            values='Count',
            title="Transfer Case Distribution",
            hole=0.4,
            color_discrete_sequence=["mediumpurple", "PapayaWhip"]
        )
        
        st.plotly_chart(fig_pie, use_container_width=True)
    
        # --- Display Names of Articles Under Each Transfer Case ---
        selected_transfer_case = st.radio("Select Transfer Case to View Articles", ["Yes", "No"], index=0)
        articles_under_selected_case = filtered_df[filtered_df['Transfer case '] == selected_transfer_case]['Name'].unique()
        
        st.subheader(f"Articles Under Transfer Case: {selected_transfer_case}")
        st.write(", ".join(articles_under_selected_case) if len(articles_under_selected_case) > 0 else "No articles found.")

    
    with col2:
                            # Funnel Chart for Extension Days
        st.subheader("Funnel Chart: Extension Days by Name")

        # Filter out NaN values and include only rows where 'Extension Days' > 0
        filtered_funnel_df = filtered_df.dropna(subset=['Extension Days '])
        filtered_funnel_df = filtered_funnel_df[filtered_funnel_df['Extension Days '] > 0]

        # Sort the DataFrame in descending order based on 'Extension Days '
        filtered_funnel_df = filtered_funnel_df.sort_values(by='Extension Days ', ascending=False)

        if not filtered_funnel_df.empty:
            fig_funnel = px.funnel(
                filtered_funnel_df,
                y='Name',
                x='Extension Days ',
                title="Extension Days Funnel Chart by Name",
                labels={'Name': 'Article Name', 'Extension Days ': 'Extension Days '},
                color_discrete_sequence=['PapayaWhip']  # Set the color to PapayaWhip
            )
            st.plotly_chart(fig_funnel, use_container_width=True)
        else:
            st.write("No extension data available for selected filters.")



    # Table with Excel-Like Filters (Using AgGrid)
    st.subheader("Detailed Table")
    gb = GridOptionsBuilder.from_dataframe(filtered_df)
    gb.configure_grid_options(domLayout='normal')  # Enable normal scrolling instead of pagination
    gb.configure_side_bar()  # Add a sidebar to configure columns and filters
    gb.configure_default_column(
        filter=True,  # Enable filters
        sortable=True,  # Enable sorting
        resizable=True,  # Allow column resizing
        editable=False  # Make the table non-editable
    )
    
    grid_options = gb.build()

    AgGrid(
        filtered_df,
        gridOptions=grid_options,
        enable_enterprise_modules=True,  # Enable advanced features
        theme="streamlit"  # Use the Streamlit theme for AgGrid
    )

    # Additional Notes
    st.write("""
    - **Instructions**: The table above allows for filtering, sorting, and resizing columns directly.
    """)

if page_selection == "Monthly Data":
    # Monthly Data Section
    worksheet_monthly = spreadsheet.worksheet("pdftosheet")
    data_monthly = worksheet_monthly.get_all_records()
    df_monthly = pd.DataFrame(data_monthly)

    # Ensure numeric columns are numeric
    numeric_cols = ['Payable Days', 'Absent Days', 'Days in Month', 'Salary']
    for col in numeric_cols:
        df_monthly[col] = pd.to_numeric(df_monthly[col], errors='coerce')

    # Dropdown for month selection
    st.sidebar.title("Monthly Data Filter")
    month_list = ["All"] + sorted(df_monthly['Month'].unique().tolist())
    selected_month = st.sidebar.selectbox("Select Month", month_list)

    # Filter based on selected month
    if selected_month == "All":
        filtered_monthly_df = df_monthly
    else:
        filtered_monthly_df = df_monthly[df_monthly['Month'] == selected_month]

        # --- Stacked Bar Chart: Salary per Article by Month + Total Salary ---
    st.subheader("Stacked Salary Chart by Month with Total")

    # Group salary by Name and Month
    salary_stacked = df_monthly.groupby(['Name', 'Month'])['Salary'].sum().reset_index()

    # Calculate total salary per article
    total_salary = df_monthly.groupby('Name')['Salary'].sum().reset_index()
    total_salary['Month'] = 'Total'  # Treat as another month for stacking

    # Combine original monthly salary with total
    combined_salary = pd.concat([salary_stacked, total_salary], ignore_index=True)

    # Plot stacked bar chart including "Total"
    fig_combined = px.bar(
        combined_salary,
        x='Name',
        y='Salary',
        color='Month',
        title="Stacked Salary Chart by Month with Total Salary Included",
        labels={'Salary': 'Salary (₹)', 'Name': 'Article'},
        text_auto=True
    )

    fig_combined.update_layout(barmode='stack')
    st.plotly_chart(fig_combined, use_container_width=True)

    
    

    st.subheader(f"Salary Distribution {'by Month' if selected_month == 'All' else ''}")
    
    if selected_month == "All":
        # Salary trend over months (for "All" selection)
        fig_salary_trend = px.line(
            df_monthly.groupby(['Month', 'Name'])['Salary'].sum().reset_index(),
            x='Month',
            y='Salary',
            color='Name',
            markers=True,
            labels={'Salary': 'Total Salary (₹)', 'Month': 'Month'},
            title="Monthly Salary Trend by Article"
        )
        st.plotly_chart(fig_salary_trend, use_container_width=True)
        
    
    else:
        # Salary bar chart for individual month
        fig_salary = px.bar(
            filtered_monthly_df,
            x='Name',
            y='Salary',
            color='Name',
            labels={'Salary': 'Salary (₹)', 'Name': 'Article'},
            title=f"Salary Distribution for {selected_month}"
        )
        st.plotly_chart(fig_salary, use_container_width=True)

    # --- Present/Absent Days Visualization (Existing Code) ---
    st.subheader(f"Present vs Absent Days for {selected_month if selected_month != 'All' else 'All Months'}")
    present_absent_monthly_chart = filtered_monthly_df.groupby('Name')[['Payable Days', 'Absent Days']].sum().reset_index()
    fig_monthly = px.bar(
        present_absent_monthly_chart,
        x='Name',
        y=['Payable Days', 'Absent Days'],
        barmode='group',
        labels={'Name': 'Article Name', 'value': 'Days'},
        color_discrete_map={'Payable Days': 'mediumpurple','Absent Days': 'papayawhip'},
        title=f"Present vs Absent Days for {selected_month if selected_month != 'All' else 'All Months'}"
    )
    fig_monthly.for_each_trace(lambda t: t.update(name='Payable Days' if 'Payable Days' in t.name else 'Absent Days'))
    st.plotly_chart(fig_monthly, use_container_width=True)

    # --- Detailed Table (Existing Code) ---
    st.subheader("Detailed Monthly Data Table")
    gb_monthly = GridOptionsBuilder.from_dataframe(filtered_monthly_df)
    gb_monthly.configure_grid_options(domLayout='normal')
    gb_monthly.configure_side_bar()
    gb_monthly.configure_default_column(filter=True, sortable=True, resizable=True, editable=False)
    grid_options_monthly = gb_monthly.build()
    AgGrid(filtered_monthly_df, gridOptions=grid_options_monthly, enable_enterprise_modules=True, theme="streamlit")

# Add this new condition for the Daily Dashboard
elif page_selection == "Daily Dashboard":
    st.title("Daily Attendance Dashboard")
    
    # Open the daily attendance Google Sheet
    daily_sheet_key = "1J2XQPhOc2OqDcjjg_9-WLA7RbtveaLI5ddK91I6cwlw"
    daily_spreadsheet = gc.open_by_key(daily_sheet_key)
    
    # Get all worksheet names except "Sheet1"
    worksheets = daily_spreadsheet.worksheets()
    available_sheets = [ws.title for ws in worksheets if ws.title != "Sheet1"]
    
    # Sidebar filters
    st.sidebar.title("Daily Data Filters")
    selected_sheet = st.sidebar.selectbox("Select Month Sheet", available_sheets)
    
    # Load the selected worksheet
    daily_worksheet = daily_spreadsheet.worksheet(selected_sheet)
    daily_data = daily_worksheet.get_all_records()
    daily_df = pd.DataFrame(daily_data)
    
    # Convert date column to datetime for filtering
    if 'Date' in daily_df.columns:
        daily_df['Date'] = pd.to_datetime(daily_df['Date'], errors='coerce', dayfirst=True)
        
        # Date range selector
        min_date = daily_df['Date'].min()
        max_date = daily_df['Date'].max()
        date_range = st.sidebar.date_input(
            "Select Date Range",
            value=[min_date, max_date],
            min_value=min_date,
            max_value=max_date
        )
        
        # Filter by date range
        if len(date_range) == 2:
            start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
            daily_df = daily_df[(daily_df['Date'] >= start_date) & (daily_df['Date'] <= end_date)]
    
    # Staff name filter
    staff_names = ["All"] + sorted(daily_df['Staff Name'].unique().tolist())
    selected_staff = st.sidebar.selectbox("Select Staff Member", staff_names)
    
    if selected_staff != "All":
        daily_df = daily_df[daily_df['Staff Name'] == selected_staff]
    
    # Clean and process Hours Worked column - convert to numeric hours
    if 'Hours Worked' in daily_df.columns:
        def convert_to_hours(hours_str):
            if pd.isna(hours_str):
                return 0.0
            
            # If it's already a number, return it directly
            try:
                return float(hours_str)
            except:
                pass
                
            # Handle time strings (HH:MM:SS)
            if isinstance(hours_str, str):
                # Remove any extra characters or multiple time entries
                clean_str = hours_str.split()[0]  # Take first part if multiple times
                
                # Handle HH:MM:SS format
                if clean_str.count(':') == 2:
                    try:
                        h, m, s = map(float, clean_str.split(':'))
                        return h + m/60 + s/3600
                    except:
                        pass
                
                # Handle HH:MM format
                elif clean_str.count(':') == 1:
                    try:
                        h, m = map(float, clean_str.split(':'))
                        return h + m/60
                    except:
                        pass
            
            # If all else fails, return 0
            return 0.0
        
        daily_df['Hours Worked'] = daily_df['Hours Worked'].apply(convert_to_hours)
        daily_df['Hours Worked'] = pd.to_numeric(daily_df['Hours Worked'], errors='coerce').fillna(0)
    
    # Display KPIs
    st.subheader("Daily Attendance Summary")
    
    col1, col2 = st.columns(2)
    with col1:
        total_records = len(daily_df)
        st.metric("Total Records", total_records)
    
    with col2:
        if 'Hours Worked' in daily_df.columns:
            avg_hours = daily_df['Hours Worked'].mean()
            st.metric("Average Hours Worked", f"{avg_hours:.2f} hours")
    
    # Display the data table
    st.subheader(f"Daily Attendance Data - {selected_sheet}")
    
    # Configure AgGrid for the daily data
    display_df = daily_df.copy()
    
    # Format Hours Worked for display (optional)
    if 'Hours Worked' in display_df.columns:
        display_df['Hours Worked Display'] = display_df['Hours Worked'].apply(
            lambda x: f"{int(x)}:{int((x % 1) * 60):02d}" if pd.notna(x) else "--"
        )
    
    gb_daily = GridOptionsBuilder.from_dataframe(display_df)
    gb_daily.configure_grid_options(domLayout='normal')
    gb_daily.configure_side_bar()
    gb_daily.configure_default_column(
        filter=True, 
        sortable=True, 
        resizable=True, 
        editable=False
    )
    grid_options_daily = gb_daily.build()
    
    AgGrid(
        display_df,
        gridOptions=grid_options_daily,
        enable_enterprise_modules=True,
        theme="streamlit",
        height=500,
        width='100%'
    )
    
    # Visualization: Attendance Status Count
    if 'Attendance' in daily_df.columns:
        st.subheader("Attendance Status Distribution")
        status_counts = daily_df['Attendance'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        
        fig = px.pie(
            status_counts,
            names='Status',
            values='Count',
            title="Attendance Status Distribution",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Visualization: Hours Worked Trend
    if 'Hours Worked' in daily_df.columns and 'Date' in daily_df.columns:
        st.subheader("Hours Worked Trend Over Time")
        try:
            fig = px.line(
                daily_df,
                x='Date',
                y='Hours Worked',
                color='Staff Name' if selected_staff == "All" else None,
                title="Daily Hours Worked Trend",
                markers=True,
                labels={'Hours Worked': 'Hours Worked'}
            )
            
            # Set y-axis range to start from 0
            fig.update_yaxes(rangemode="tozero")
            
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not display hours worked trend: {str(e)}")