
import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import geopandas as gpd
from folium.plugins import FastMarkerCluster

st.set_page_config(layout="wide")

# load layers
@st.cache_data(show_spinner="Loading spatial data...")
def load_layer(path: str, layer_name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path, layer=layer_name)
    return gdf.to_crs(epsg=4326)

layer_variables = load_layer(
    r"/data/VARIABLES_for_streamlit.gpkg",
    "VARIABLES_for_streamlit"
)
pts_by_location = load_layer(
    r"/data/tycktill_output/BERTopic_filtered/tycktill_filtered.gpkg",
    "pts_in_parks_with_topics"
)
pts_by_keyword = load_layer(
    r"/data/tycktill_output/BERTopic_filtered/tycktill_filtered.gpkg",
    "park_comments_by_keyword"
)
pts_by_BERTopic = load_layer(
    r"/data/tycktill_output/BERTopic_filtered/tycktill_filtered.gpkg",
    "park_comments_by_BERTopic"
)

# === reduce data size ===

# drop most columns in polygon layer
layer_variables = layer_variables[["geometry"]]      # <<< add any other columns to keep

# simplify polygons
#layer_variables["geometry"] = layer_variables["geometry"].simplify(tolerance=0.0005)


# === map ===

# load map
m = folium.Map(location=(59.33, 17.99), zoom_start=10.5, tiles=None)

# ==== BASEMAPS ====

# add custom pane for labels so that they show up on top
folium.map.CustomPane("labels").add_to(m)

# satellite basemap from ESRI
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri',
    name='Esri Satellite',
    overlay=False,
    control=True
).add_to(m)

# just labels
folium.TileLayer(
    tiles='https://tiles.stadiamaps.com/tiles/stamen_toner_labels/{z}/{x}/{y}{r}.png',
    attr='&copy; <a href="https://www.stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://www.stamen.com/">Stamen Design</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    name='Stamen Toner Labels',
    overlay=True,
    control=True,
    pane='labels' # makes labels go on top
).add_to(m)


# ==== DATA LAYERS ====

# Polygon layer
folium.GeoJson(
    layer_variables,
    name="Parks",
    style_function=lambda feature: {
        "fillColor": "yellow",
        "color": "black",
        "weight": 0.5,
        "fillOpacity": 0.4
    }
).add_to(m)

# Point layers
#folium.GeoJson(pts_by_location, name="Points by location").add_to(m)
#folium.GeoJson(pts_by_keyword, name="Points by keyword").add_to(m)
#folium.GeoJson(pts_by_BERTopic, name="Points by BERTopic").add_to(m)

# Point layers (fastmarkerclustered to reduce size)
for gdf, name in [
    (pts_by_location, "Points by location"),
    (pts_by_keyword, "Points by keyword"),
    (pts_by_BERTopic, "Points by BERTopic"),
]:
    # extract coordinates
    coords = [[geom.y, geom.x] for geom in gdf.geometry if geom and not geom.is_empty]
    # add cluster layer
    FastMarkerCluster(coords, name=name).add_to(m)


# ==== LAYER CONTROL ====

folium.LayerControl('topright', collapsed=False).add_to(m)


# ==== SIDEBAR ====

st.sidebar.title("Feedback")
st.sidebar.markdown("Click any park to leave feedback on it here!")


st_data = st_folium(m, width=1200, height=800)








