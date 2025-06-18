# ----------------------------------------------------------------------
# East Group - Territory Intelligence Dashboard
# Phase 2: Analytics & Visualization (Corrected Version)
# ----------------------------------------------------------------------

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
import geopandas # To handle the geometry data correctly

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="East Group Territory Intelligence",
    page_icon="🏢",
    layout="wide"
)

# --- DATABASE CONNECTION ---
# Get credentials from Streamlit's secure secrets manager
DB_USER = st.secrets["DB_USER"]
DB_PASSWORD = st.secrets["DB_PASSWORD"]
DB_HOST = st.secrets["DB_HOST"]
DB_PORT = st.secrets["DB_PORT"]
DB_NAME = st.secrets["DB_NAME"]

# Create the database engine using the secrets
# NOTE: We are back to using psycopg2, as the WKT method in the query handles the geometry.
db_engine = create_engine(f'postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')
# Create a standard SQLAlchemy engine.
# The special SQL query will handle the geometry conversion.
db_engine = create_engine(f'postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

# --- DATA LOADING AND CACHING (FINAL, CORRECTED VERSION) ---
@st.cache_data(ttl=600)
def load_data_from_db():
    """
    Connects to the PostgreSQL database and loads property data.
    This version converts the geometry to text within the SQL query itself
    to avoid any parsing errors in Python.
    """
    print("Loading data from database using robust WKT method...")
    try:
        # This new SQL query tells PostGIS to convert the 'coordinates' column
        # to a simple text format (WKT) before sending it to Python.
        query = """
            SELECT *, ST_AsText(coordinates) as wkt_coordinates
            FROM territory_properties
        """

        # Step 1: Read the data as a NORMAL pandas DataFrame.
        df = pd.read_sql(query, db_engine)

        if df.empty:
            st.warning("No data returned from the database.")
            return geopandas.GeoDataFrame()

        # Step 2: Convert the text 'wkt_coordinates' into a real geometry column.
        # This creates the GeoDataFrame correctly and safely.
        gdf = geopandas.GeoDataFrame(
            df, geometry=geopandas.GeoSeries.from_wkt(df['wkt_coordinates']), crs="EPSG:4326"
        )

        # Create lat/lon columns for the map plotting from the new geometry
        if not gdf.empty:
            gdf['lat'] = gdf.geometry.y
            gdf['lon'] = gdf.geometry.x

        print("Data loaded and converted successfully.")
        return gdf

    except Exception as e:
        st.error(f"An error occurred while loading or processing data: {e}")
        return geopandas.GeoDataFrame()

# Load the data using the new function
geo_df = load_data_from_db()

if geo_df.empty:
    st.warning("No data to display. Please ensure Phase 1 ran successfully and populated the database.")
    st.stop()

# --- SIDEBAR FILTERS ---
st.sidebar.header("Dashboard Filters")

# Filter by City
cities = sorted(geo_df['city'].unique())
selected_cities = st.sidebar.multiselect(
    "Select City/Submarket",
    options=cities,
    default=cities
)

# Filter by Square Footage
min_sqft = int(geo_df['square_footage'].min())
max_sqft = int(geo_df['square_footage'].max())
selected_sqft = st.sidebar.slider(
    "Filter by Square Footage",
    min_value=min_sqft,
    max_value=max_sqft,
    value=(min_sqft, max_sqft),
    step=10000
)

# Filter by Clear Height
heights = sorted(geo_df['clear_height_ft'].astype(int).unique())
selected_height = st.sidebar.multiselect(
    "Filter by Clear Height (ft)",
    options=heights,
    default=heights,
)

# --- APPLY FILTERS TO THE DATAFRAME ---
filtered_df = geo_df[
    (geo_df['city'].isin(selected_cities)) &
    (geo_df['square_footage'].between(selected_sqft[0], selected_sqft[1])) &
    (geo_df['clear_height_ft'].isin(selected_height))
].copy()

# --- MAIN DASHBOARD LAYOUT ---
st.title("🏢 East Group Territory Intelligence")
st.markdown(f"An interactive analytics dashboard for **Ryan Collins' Territory**")
st.markdown("---")

# Display Key Performance Indicators (KPIs)
st.subheader("Market Snapshot (Filtered)")

col1, col2, col3 = st.columns(3)
col1.metric("Total Properties", f"{len(filtered_df):,}")
col2.metric("Total Square Footage", f"{filtered_df['square_footage'].sum() / 1_000_000:.2f} M SF")
avg_sf = filtered_df['square_footage'].mean()
col3.metric("Avg. Building Size (SF)", f"{avg_sf:,.0f}" if len(filtered_df) > 0 else "N/A")
st.markdown("---")

# --- INTERACTIVE MAP ---
st.subheader("Territory Property Map")

if not filtered_df.empty:
    px.set_mapbox_access_token("pk.eyJ1IjoiZ2lzdXNlci1zaW1vbmIiLCJhIjoiY2w5cTIxeDluMGR3eTN2bXN2a3ZndjRraSJ9.Qwnau5aXh6a5Cj02f2VtXA") # Public demo token
    fig_map = px.scatter_mapbox(
        filtered_df,
        lat="lat",
        lon="lon",
        color="city",
        size="square_footage",
        hover_name="address",
        hover_data={"square_footage": ":,", "clear_height_ft": True, "city": False},
        zoom=7,
        height=600,
        mapbox_style="carto-positron"
    )
    fig_map.update_layout(legend_title_text='City/Submarket')
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.warning("No properties match the selected filters.")

# --- RAW DATA TABLE ---
st.subheader("Filtered Property Data")
# Define columns to show, excluding helper columns we created
display_cols = [
    'address', 'city', 'state', 'zip_code', 'square_footage',
    'clear_height_ft', 'dock_doors', 'year_built',
    'last_sale_price', 'current_lease_rate_psf', 'is_vacant'
]
# Filter the list to only include columns that actually exist in the dataframe
display_cols_exist = [col for col in display_cols if col in filtered_df.columns]
st.dataframe(filtered_df[display_cols_exist])
