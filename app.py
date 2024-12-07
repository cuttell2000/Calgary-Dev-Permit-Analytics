import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import plotly.express as px
import io
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
import pickle

# Load cleaned data
@st.cache_data
def load_data():

    # api
    develop_permit2_df = pd.read_csv("https://data.calgary.ca/resource/6933-unw5.csv?$limit=500000")

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

    # develop_permit3_df['category'] = develop_permit3_df['category'].str.lower().str.strip()
    # develop_permit3_df['proposedusecode'] = develop_permit3_df['proposedusecode'].str.lower().str.strip()

    # Use .loc to avoid SettingWithCopyWarning

    develop_permit3_df.loc[:, 'category'] = develop_permit3_df['category'].str.lower().str.strip()
    develop_permit3_df.loc[:, 'proposedusecode'] = develop_permit3_df['proposedusecode'].str.lower().str.strip()

    # return and load data
    return develop_permit3_df

data = load_data()

# dashboard
def dev_permit_dashboard():

    import streamlit as st
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    import folium
    from folium.plugins import HeatMap
    from streamlit_folium import st_folium
    import plotly.express as px
    import io
    from folium.plugins import MarkerCluster
    from streamlit_folium import folium_static

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
        # heatmap = folium.Map(location=map_center, zoom_start=11)
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

# Permit Prediction Model
def permit_predictive_model():

    import streamlit as st
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, classification_report
    import numpy as np
    from imblearn.over_sampling import RandomOverSampler
    from imblearn.under_sampling import RandomUnderSampler

    import pickle

    # load data
    # Feature Engineering
    data_ml = data.copy()

    # Encode categorical columns
    data_ml['status_encoded'] = data_ml['statuscurrent'].astype('category').cat.codes
    data_ml['quadrant_encoded'] = data_ml['quadrant'].astype('category').cat.codes

    # resample the imbalanced class distribution of target variable apporval_indicator to make it balanced
    # with the independent variables

    # copy data
    data_ml2 = data_ml.copy()

    # from exploratory data analysis

    # Class Distribution:
    # approval_indicator
    # 1    158610
    # 0      5349
    # Name: count, dtype: int64

    # Class Percentages:
    # approval_indicator
    # 1    96.737599
    # 0     3.262401
    # Name: count, dtype: float64

    # Check for class imbalance (threshold is subjective)
    imbalance_threshold = 20  # Example: 20% difference

    # Count the occurrences of each class in the target variable
    class_counts = data_ml2['approval_indicator'].value_counts()

    # Calculate the percentage of each class
    class_percentages = class_counts / len(data_ml2) * 100

    if abs(class_percentages.iloc[0] - class_percentages.iloc[1]) > imbalance_threshold:
        print("\nWARNING: Potential Class Imbalance detected.")
        print("Applying Random Oversampling...")

        # Separate features (X) and target variable (y)
        X = data_ml2.drop('approval_indicator', axis=1)
        y = data_ml2['approval_indicator']

        # Initialize and apply RandomOverSampler
        oversampler = RandomOverSampler(random_state=42)
        X_resampled, y_resampled = oversampler.fit_resample(X, y)

        # Create a new DataFrame with the resampled data
        data_ml_resampled = pd.DataFrame(X_resampled, columns=X.columns)
        data_ml_resampled['approval_indicator'] = y_resampled

        data_ml2 = data_ml_resampled
        
    elif abs(class_percentages.iloc[0] - class_percentages.iloc[1]) < (100 - imbalance_threshold):
        print("\nWARNING: Potential Class Imbalance detected.")
        print("Applying Random Undersampling...")

        # Separate features (X) and target variable (y)
        X = data_ml2.drop('approval_indicator', axis=1)
        y = data_ml2['approval_indicator']

        # Initialize and apply RandomUnderSampler
        undersampler = RandomUnderSampler(random_state=42)
        X_resampled, y_resampled = undersampler.fit_resample(X, y)

        # Create a new DataFrame with the resampled data
        data_ml_resampled = pd.DataFrame(X_resampled, columns=X.columns)
        data_ml_resampled['approval_indicator'] = y_resampled

        data_ml2 = data_ml_resampled
        
    else:
        print("\nClass balance appears to be appropriate.")

    # Now data_ml2 holds the balanced dataset (either oversampled, undersampled, or original)
    # Proceed with your model training using data_ml2

    # Prepare data for modeling
    features = ['category', 'processing_time', 'quadrant_encoded', 'ward']
    X = data_ml2[features].copy()

    # Handle categorical data (One-Hot Encoding or Label Encoding as needed)
    X['category'] = X['category'].fillna('Unknown')  # Replace NaN with 'Unknown'
    X = pd.get_dummies(X, columns=['category'], drop_first=True)

    # Target variable
    y = data_ml2['approval_indicator']

    # Split into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train a Random Forest Classifier
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Evaluate model
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    st.sidebar.write(f"Model Accuracy: {accuracy:.2%}")

    # Save model to varibale for pickle
    model_approval = model

    # Save the models to files
    with open('approval_model.pkl', 'wb') as f:
        pickle.dump(model_approval, f)

    # Load models
    with open('approval_model.pkl', 'rb') as f:
        approval_model = pickle.load(f)

    # Sidebar for navigation
    st.sidebar.title("Calgary Development Permit Predictive Model")
    options = st.sidebar.radio(
        "Select a model",
        [
            "Permit Approval Prediction"
        ]
    )

    # Main model
    st.title("City of Calgary Development Permit Predictive Analytics")

    if options == "Permit Approval Prediction":
        st.header("Permit Approval Prediction")

        # User inputs for prediction
        st.subheader("Input Permit Details")
        input_category = st.selectbox("Select Category", data_ml2['category'].fillna('Unknown').unique())
        input_processing_time = st.slider("Processing Time (days)", int(data_ml2['processing_time'].min()), int(data_ml2['processing_time'].max()), 30)
        input_quadrant = st.selectbox("Select Quadrant", data_ml2['quadrant'].unique())
        input_ward = st.slider("Select Ward", int(data_ml2['ward'].min()), int(data_ml2['ward'].max()), 7)

        # Preprocess inputs
        input_data = {
            'processing_time': input_processing_time,
            'quadrant_encoded': data_ml2[data_ml2['quadrant'] == input_quadrant]['quadrant_encoded'].values[0],
            'ward': input_ward,
        }

        # One-hot encode category
        for col in X.columns:
            if col.startswith('category_'):
                input_data[col] = 1 if f"category_{input_category}" in col else 0

        input_df = pd.DataFrame([input_data])

        # Make prediction
        prediction = model.predict(input_df)
        prediction_prob = model.predict_proba(input_df)[0]

        # Display prediction result
        if prediction[0] == 1:
            st.success(f"Approval Likely (Confidence: {prediction_prob[1]:.2%})")
        else:
            st.error(f"Approval Unlikely (Confidence: {prediction_prob[0]:.2%})")

permit_page_names_to_funcs = {
    "Permits Dashboard": dev_permit_dashboard,
    "Permit Predictive Model": permit_predictive_model
}

analytics_name = st.sidebar.selectbox("Choose an analytics", permit_page_names_to_funcs.keys())
permit_page_names_to_funcs[analytics_name]()