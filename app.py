import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import plotly.express as px
from folium.plugins import MarkerCluster
import folium
 
# Load cleaned data
@st.cache_data
def load_data():

    # api
    dtypes = {
        "category": "object",  # Replace with appropriate types (e.g., "str", "float64")
        "concurrent_loc": "object",
        "sdabnumber": "object",
        "sdabdecisiondate": "object"  # Use "object" for mixed types initially
    }

    develop_permit2_df = pd.read_csv("https://data.calgary.ca/resource/6933-unw5.csv?$limit=500000", dtype=dtypes)

    # Handle missing data
    # Drop columns with too many missing values (arbitrary threshold: 90% missing)
    columns_to_drop = ['concurrent_loc', 'sdabnumber', 'sdabhearingdate', 'sdabdecision', 'sdabdecisiondate']
    develop_permit2_df.drop(columns=columns_to_drop, axis=1, inplace=True)

    # Fill missing values for essential columns
    develop_permit2_df.fillna({'ward' : develop_permit2_df['ward'].median()}, inplace=True)
    develop_permit2_df.fillna({'decision': 'Unknown'}, inplace=True) # 'Unknown' as placeholder

    # Parse date columns into datetime format
    date_columns = ['applieddate', 'decisiondate', 'releasedate', 'mustcommencedate', 'canceledrefuseddate']
    for col in date_columns:
        develop_permit2_df[col] = pd.to_datetime(develop_permit2_df[col], errors='coerce')

    # Create derived columns
    develop_permit2_df['processing_time'] = (develop_permit2_df['decisiondate'] - develop_permit2_df['applieddate']).dt.days
    develop_permit2_df['approval_indicator'] = develop_permit2_df['decision'].apply(lambda x: 1 if x == 'Approval' else 0)

    # Filter out rows with negative 'process_time'
    develop_permit3_df = develop_permit2_df[develop_permit2_df['processing_time'] >= 0]

    # Use .loc to avoid SettingWithCopyWarning
    develop_permit3_df.loc[:, 'category'] = develop_permit3_df['category'].str.lower().str.strip()
    develop_permit3_df.loc[:, 'proposedusecode'] = develop_permit3_df['proposedusecode'].str.lower().str.strip()

    # return and load data
    return develop_permit3_df

data = load_data()

# Sidebar for navigation
st.sidebar.title("Calgary Development Permit Dashboard")
options = st.sidebar.radio(
    "Select a visualization",
    [
        "Permit Categories", 
        "Application Trends", 
        "Geospatial Heatmap",
        "Geospatial MarkerClusterMap",
        "Geospatial ScatterMap",
        "Processing Time Analysis",
        "Permit Status Breakdown",
        "Search Permits"
    ]
)

# Sidebar filters
st.sidebar.subheader("Filters")
# selected_year = st.sidebar.slider("Select Year", 1989, 2024, 2020)
selected_year = st.sidebar.selectbox(
    "Select Year", data['applieddate'].dt.year.unique()
)
selected_quadrant = st.sidebar.multiselect(
    "Select Quadrant", data['quadrant'].unique(), default=data['quadrant'].unique()
)
selected_ward = st.sidebar.multiselect(
    "Select Ward", sorted(data['ward'].dropna().unique()), default=sorted(data['ward'].dropna().unique())
)

# Filter data
data['applieddate'] = pd.to_datetime(data['applieddate'])
data_filtered = data[
    # (data['applieddate'].dt.year == selected_year) &
    (data['applieddate'].dt.year == selected_year) &
    (data['quadrant'].isin(selected_quadrant)) &
    (data['ward'].isin(selected_ward))
]

# Main dashboard
st.title("City of Calgary Development Permit Analytics")

if options == "Permit Categories":
    st.header("Top 15 Permit Categories")
    top_categories = data['category'].value_counts().head(15)

    fig = px.bar(
    x=top_categories.values,
    y=top_categories.index,
    orientation='h',
    color=top_categories.index,
    color_discrete_sequence=px.colors.sequential.Viridis,
    title='Top 15 Permit Categories',
    labels={'x': 'Number of Permits', 'y': 'Category'},
    )

    # Highlight categories starting with "residential"
    for i, index in enumerate(top_categories.index):
        if index.lower().startswith("residential"):
            fig.data[i].marker.line.color = 'red'
            fig.data[i].marker.line.width = 3

    # Bolden specific categories on the y-axis
    categories_to_bold = ["residential - secondary suite", "residential - new single / semi / duplex", "residential - multi-family"]
    for i, category in enumerate(top_categories.index):
        if category in categories_to_bold:
            fig.data[i].text = f"<b>{category}</b>"

    fig.update_layout(showlegend=False)
    st.plotly_chart(fig)


elif options == "Application Trends":
    st.header("Monthly Application Trends")
    data['applieddate'] = pd.to_datetime(data['applieddate'])
    data['month_year'] = data['applieddate'].dt.to_period('M')
    monthly_trend = data['month_year'].value_counts().sort_index()

    monthly_trend.index = monthly_trend.index.to_timestamp()

    fig = px.line(
        x=monthly_trend.index,
        y=monthly_trend.values,
        title="Monthly Application Trends",
        labels={"x": "Month-Year", "y": "Number of Applications"},
        markers=True  # Add markers to the line plot
    )

    st.plotly_chart(fig)

elif options == "Geospatial Heatmap":
    st.header("Permit Density Heatmap")
    map_center = [data['latitude'].mean(), data['longitude'].mean()]
    heatmap = folium.Map(location=map_center, zoom_start=10.4)
    heat_data = data[['latitude', 'longitude']].dropna().values.tolist()
    HeatMap(heat_data, radius=8, blur=10).add_to(heatmap)
    st_folium(heatmap, width=700, height=500)

elif options == "Geospatial MarkerClusterMap":
    st.header("Permit MarkerClustermap")
    map_center = [data['latitude'].mean(), data['longitude'].mean()]
    calg_marker_cluster = folium.Map(location=map_center, zoom_start=10.4)
    
    # Filter for non-null latitude and longitude values
    filtered_df = data.dropna(subset=['latitude', 'longitude'])
    
    # Create marker cluster and add markers with popups (optional)
    marker_cluster = MarkerCluster().add_to(calg_marker_cluster)
    for index, row in filtered_df.iterrows():
        lat = row['latitude']
        lng = row['longitude']
        popup_text = f"Permit Details (Optional: Add details here)"  # Add details if desired
        folium.Marker([lat, lng], popup=popup_text).add_to(marker_cluster)
    
    # Display the map in Streamlit
    st.components.v1.html(calg_marker_cluster._repr_html_(), width=700, height=500)

elif options == "Geospatial ScatterMap":
    fig = px.scatter_mapbox(data, 
        lat="latitude", 
        lon="longitude", 
        color="category",
        hover_data=["category", "decision", "processing_time", "applieddate", "communityname"],
        zoom=9, 
        height=600,
        title="Calgary Development Permits Count")

    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":50,"l":0,"b":0})

    st.plotly_chart(fig)

elif options == "Processing Time Analysis":
    st.header("Processing Time Analysis")
    data_filtered['processing_time'] = (data_filtered['decisiondate'] - data_filtered['applieddate']).dt.days

    fig = px.histogram(data_filtered, 
        x="processing_time", 
        nbins=30, 
        marginal="box", # or kde, box, rug', 'box', 'violin', or 'histogram'
        color_discrete_sequence=["coral"])
    fig.update_layout(title="Distribution of Processing Times",
        xaxis_title="Processing Time (Days)",
        yaxis_title="Frequency")
    st.plotly_chart(fig)

elif options == "Permit Status Breakdown":
    st.header("Permit Status Breakdown")
    status_counts = data_filtered['statuscurrent'].value_counts()

    fig = px.bar(status_counts, 
        x=status_counts.index, 
        y=status_counts.values,
        labels={'x':'Status', 'y':'Number of Permits'},
        title="Current Permit Status",
        color_discrete_sequence=["orange"])
    fig.update_xaxes(title_text="Status")
    st.plotly_chart(fig)

elif options == "Search Permits":
    st.header("Search Permits by Address or Category")
    search_type = st.radio("Search by:", ["Address", "Category"])
    search_query = st.text_input("Enter your search query:")
    if search_query:
        if search_type == "Address":
            search_results = data[data['address'].str.contains(search_query, case=False, na=False)]
        else:
            search_results = data[data['category'].str.contains(search_query, case=False, na=False)]
        
        st.write(f"Found {len(search_results)} results:")
        st.dataframe(search_results)