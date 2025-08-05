import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
import pandas as pd
import json

st.set_page_config(layout="wide")

st.title("Split-panel Map")

# Create the map
m = leafmap.Map(
    center=[59.32, 18.08],
    zoom=10.5,
    minimap_control=True,
    draw_control=False,
    measure_control=False,
    attribution_control=False,
    dragging=False #detta löser issue m drag funktionen, källa https://github.com/jupyter-widgets/ipyleaflet/issues/1066
)

# OBS! VERKAR SOM LEAFMAP SPLITMAP BARA FUNGERAR MED BASEMAPS, INTE MINA FILER
# Folium har dual map men INTE en split map funktion
# ipyleaflet har en split funktion
m.split_map(left_layer="ROADMAP", right_layer="HYBRID")

m.to_streamlit(height=700)