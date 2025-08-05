#VISUALISERA EGEN DATA BUSHÅLLSPLATSER
import streamlit as st
import geopandas as gpd
import pandas as pd

# Set page title
st.title('Bus Stop Points Map')

# Load the GeoPackage file
@st.cache_data
def load_data():
    gdf = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\highway_bus_stop_pts.gpkg")
    # Convert to the format needed for st.map (requires 'lat' and 'lon' columns)
    points_df = pd.DataFrame({
        'lat': gdf['y_coord'],
        'lon': gdf['x_coord']
    })
    return points_df

# Load data and display on map
try:
    data = load_data()
    st.map(data)
except Exception as e:
    st.error(f"Error loading or displaying the map: {e}")

