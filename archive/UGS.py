import streamlit as st
import geopandas as gpd
import leafmap.foliumap as leafmap
import pandas as pd

st.set_page_config(layout="wide")

st.title("Urban Green Spaces in Stockholm")

# Create the map
m = leafmap.Map(
    center=[59.32, 18.08],
    zoom=10.5,
    minimap_control=True,
    draw_control=False,
    measure_control=False,
    attribution_control=False
)

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

# Add leisure_park layer
@st.cache_data
def load_and_prepare_OSMpark_gdf():
    OSMpark_gdf = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\Edited_Attributes\leisure_park_MASKED_EDITED.geojson")

    # Convert datetime or Timestamp objects to strings
    for col in OSMpark_gdf.columns:
        if OSMpark_gdf[col].apply(lambda x: isinstance(x, pd.Timestamp)).any():
            OSMpark_gdf[col] = OSMpark_gdf[col].astype(str)

    return OSMpark_gdf

OSMpark_gdf = load_and_prepare_OSMpark_gdf()
OSMpark_geojson = OSMpark_gdf.to_json()

# Symbology/style settings of OSM parks
style_OSM = {
    "stroke": True,
    "color": "#5ec1a5",
    "weight": 2,
    "opacity": 1,
    "fill": True,
    "fillColor": "#5ec1a5",
    "fillOpacity": 0.5,
}
hover_style_OSM = {"fillOpacity": 0.7}

m.add_geojson(OSMpark_geojson, layer_name="Parks OSM", style=style_OSM, hover_style=hover_style_OSM)

# Add Sociotop_2024 layer
sociotop24_gdf = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\GeoJSON\Sociotop_2024_WGS.geojson")
sociotop24_geojson = sociotop24_gdf.to_json()

# Symbology/style settings of Sociotop_2024 layer
style_sociotop24 = {
    "stroke": True,
    "color": "#388342",
    "weight": 2,
    "opacity": 1,
    "fill": True,
    "fillColor": "#388342",
    "fillOpacity": 0.5,
}
hover_style_sociotop24 = {"fillOpacity": 0.7}

m.add_geojson(sociotop24_geojson, layer_name="Sociotop 2024", style=style_sociotop24, hover_style=hover_style_sociotop24)

# Add Stadskartan_Mark_area layer (green spaces from Stockholm municipality)
mark_area_gdf = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\GeoJSON\Stadskartan_Mark_area_WGS.geojson")
mark_area_geojson = mark_area_gdf.to_json()

kategori_colors = {
    "Grönområde": "#07af1f",
    "Skogsmark": "#086816",
}
def style_function(feature):
    kategori = feature["properties"].get("KATEGORI", "")
    fill_color = kategori_colors.get(kategori, "lightgray")  # Default if not found
    return {
        "color": fill_color,
        "fillColor": fill_color,
        "weight": 1,
        "fillOpacity": 0.5,
    }

m.add_geojson(mark_area_geojson, layer_name="Stadskartan UGS", style_callback=style_function)

# Display the map in Streamlit
m.to_streamlit(height=750)