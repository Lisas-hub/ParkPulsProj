##### verkar som Folium och LeafMap är de huvudsakliga kart-packages som finns
# pydeck också men den har ingen inbyggd funktion för att kryssa i flera lager samtidigt
# LeafMap kan visa WMS-lager
# Folium kan visa lite annan symbology, kolla https://python-visualization.github.io/folium/latest/getting_started.html
# Folium kan också ha flera typer av popups (inkl grafer! kanske relevant för parker + resultat, asso man klickar på en park och ser ett resultat av vår analys i en graf)
# kolla https://python-visualization.github.io/folium/latest/user_guide/ui_elements/popups.html
# Grå Folium basemap finns här https://python-visualization.github.io/folium/latest/user_guide/raster_layers/tiles.html
# Här finns Folium polygoner där man kan bestämma färg! https://python-visualization.github.io/folium/latest/user_guide/vector_layers/polygon.html
# och här https://python-visualization.github.io/folium/latest/user_guide/geojson/geojson.html
# och här https://python-visualization.github.io/folium/latest/user_guide/geojson/choropleth.html
# här är symbology alt för Folium punkter https://python-visualization.github.io/folium/latest/user_guide/geojson/geojson_marker.html
# Folium plugins som minimap mm https://python-visualization.github.io/folium/latest/user_guide/plugins.html

import streamlit as st
import geopandas as gpd
import leafmap.foliumap as leafmap
import pandas as pd

st.set_page_config(layout="wide")

m = leafmap.Map(
    center=[59.32, 18.08],
    zoom=10.5,
    minimap_control=True,
    draw_control=False,
    measure_control=False,
    attribution_control=False
)

# Add bus_stop layer
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

# add Kommun_stadskartan layer (municipality boundary)
kommun_gdf = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\GeoJSON\Kommun_Stadskartan_WGS.geojson")
kommun_geojson = kommun_gdf.to_json()
m.add_geojson(kommun_geojson, layer_name="Stockholm municipality")

# Add leisure_park layer
@st.cache_data
def load_and_prepare_OSMpark_gdf():
    OSMpark_gdf = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\GeoJSON\leisure_park_MASKED.geojson")

    # Convert datetime or Timestamp objects to strings
    for col in OSMpark_gdf.columns:
        if OSMpark_gdf[col].apply(lambda x: isinstance(x, pd.Timestamp)).any():
            OSMpark_gdf[col] = OSMpark_gdf[col].astype(str)

    return OSMpark_gdf

OSMpark_gdf = load_and_prepare_OSMpark_gdf()
OSMpark_geojson = OSMpark_gdf.to_json()
m.add_geojson(OSMpark_geojson, layer_name="Parks OSM")

m.add_basemap("HYBRID")
m.add_basemap("OpenTopoMap")
m.add_basemap("ROADMAP")
#m.add_legend(builtin_legend="NWI")
# HITTA FLER BASEMAPS GENOM print(leafmap.basemaps.keys()), KÄLLA https://leafmap.org/notebooks/12_split_map/

# Display the map in Streamlit
m.to_streamlit(height=750)