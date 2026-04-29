
import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import geopandas as gpd
from folium.plugins import FastMarkerCluster
import branca.colormap as cm
import numpy as np

st.set_page_config(layout="wide")

st.title("Sentiment score per ha")

# load layers
@st.cache_data(show_spinner="Loading spatial data...")
def load_layer(path: str, layer_name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path, layer=layer_name)
    return gdf.to_crs(epsg=4326)

sentiments_per_park = load_layer(
    r"/data/tycktill_output/tycktill.gpkg",
    "sentiments_per_park"
)

# drop NaN rows (for visualisation purposes - folium/bianca can't handle these)
sentiments_per_park = sentiments_per_park.dropna(subset=["sentiment_score_per_ha"])

# drop invalid geometries
sentiments_per_park = sentiments_per_park[~sentiments_per_park.is_empty]
sentiments_per_park = sentiments_per_park[sentiments_per_park.is_valid]

# === map ===

m = folium.Map(location=(59.33, 17.99), zoom_start=10.5, tiles=None)

# ==== BASEMAPS ====

# satellite basemap from ESRI
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri',
    name='Esri Satellite',
    overlay=False,
    control=True
).add_to(m)

# just labels
#folium.TileLayer(
#    tiles='https://tiles.stadiamaps.com/tiles/stamen_toner_labels/{z}/{x}/{y}{r}.png',
#    attr='&copy; <a href="https://www.stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://www.stamen.com/">Stamen Design</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
#    name='Stamen Toner Labels',
#    overlay=True,
#    control=True,
#    pane='labels' # makes labels go on top
#).add_to(m)

# ==== DATA LAYERS ====

# ================
# continous legend
# (with mostly negative values this gives a map of mostly one color)

#min_val = sentiments_per_park["sentiment_score_per_ha"].min()
#max_val = sentiments_per_park["sentiment_score_per_ha"].max()

#colormap = cm.LinearColormap(
#    colors=["#3b4cc0", "#f7f7f7", "#d73027"],  # blue → white → red, CVD-safe diverging scale
#    vmin=min_val,
#    vmax=max_val,
#    caption="Sentiment score per hectare"
#)

#def style_function(feature):
#    value = feature["properties"]["sentiment_score_per_ha"]
#    return {
#        "fillColor": colormap(value),
#        "color": "black",  # polygon border
#        "weight": 0.5,
#        "fillOpacity": 0.6  # slightly transparent for basemap visibility
#    }

#folium.GeoJson(
#    sentiments_per_park,
#    style_function=style_function,
#    name="Sentiment per park",
#    tooltip=folium.features.GeoJsonTooltip(
#        fields=["sentiment_score_per_ha"],
#        aliases=["Sentiment score per ha:"],
#        localize=True
#    )
#).add_to(m)

#colormap.add_to(m)

# =================
# categories legend
# (that shows differences between parks better)

n_classes = 5

# compute quantiles
quantiles = np.quantile(
    sentiments_per_park["sentiment_score_per_ha"],
    np.linspace(0, 1, n_classes + 1)
)
colors = ["#d73027", "#f4a582", "#f7f7f7", "#a6dba0", "#1b7837"]

def get_color(value):
    for i in range(n_classes):
        if quantiles[i] <= value <= quantiles[i+1]:
            return colors[i]
    return colors[-1]

def style_function(feature):
    value = feature["properties"]["sentiment_score_per_ha"]
    return {
        "fillColor": get_color(value),
        "color": "black",
        "weight": 0.5,
        "fillOpacity": 0.6
    }

folium.GeoJson(
    sentiments_per_park,
    style_function=style_function,
    name="Sentiment per park",
    tooltip=folium.features.GeoJsonTooltip(
        fields=["sentiment_score_per_ha"],
        aliases=["Sentiment score per ha:"],
        localize=True
    )
).add_to(m)

# need to add custom legend

# ==== LAYER CONTROL ====

folium.LayerControl('topright', collapsed=False).add_to(m)


st_folium(m, width=1200, height=800)





