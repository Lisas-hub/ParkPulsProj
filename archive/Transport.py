import streamlit as st
import geopandas as gpd
import leafmap.foliumap as leafmap
import pandas as pd

st.set_page_config(layout="wide")

st.title("Public Transport in Stockholm")

m = leafmap.Map(
    center=[59.32, 18.08],
    zoom=10.5,
    minimap_control=True,
    draw_control=False,
    measure_control=False,
    attribution_control=False
)

m.add_basemap("ROADMAP")

# add Kommun_stadskartan layer (municipality boundary)
kommun_gdf = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\GeoJSON\Kommun_Stadskartan_WGS.geojson")
kommun_geojson = kommun_gdf.to_json()

# Symbology/style settings of Stockholm boundary
style_kommun = {
    "stroke": True,
    "color": "#000000",
    "weight": 2,
    "opacity": 1,
    "fill": False
}

m.add_geojson(kommun_geojson, layer_name="Stockholm municipality", style=style_kommun)

# Load the GeoJSON and convert datetime columns to string
@st.cache_data
def load_and_prepare_gdf():
    gdf = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\GeoJSON\highway_bus_stop_pts_MASKED.geojson")
    # Convert datetime columns to string
    datetime_cols = [
        "start_date", "check_date:lit", "check_date:tactile_paving",
        "check_date:bin", "check_date", "survey:date", "check_date:shelter"
    ]
    for col in datetime_cols:
        if col in gdf.columns and pd.api.types.is_datetime64_any_dtype(gdf[col]):
            gdf[col] = gdf[col].astype(str)
    return gdf

gdf = load_and_prepare_gdf()

# Extract coordinates for clustering
gdf["lon"] = gdf.geometry.x
gdf["lat"] = gdf.geometry.y

# Add clustered points
m.add_points_from_xy(
    gdf,
    x="lon",
    y="lat",
    color_column="highway",
    icon_names=["bus stop"],
    spin=True,
    add_legend=False,
)

# Display the map in Streamlit
m.to_streamlit(height=750)