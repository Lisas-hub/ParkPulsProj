import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from urllib.error import URLError
import json

st.set_page_config(layout="wide")

st.title("Public Transport")

st.sidebar.header("Stations and stops for public transportation")
st.sidebar.markdown("Select layer(s) to display in the map. All layers derive from OpenStreetMap.") #behövs sidebar text?

# Load
with open(r"C:\Users\lisajos\QGIS_Projects\Output\GeoJSON\highway_bus_stop_pts_MASKED.geojson", "r", encoding="utf-8") as f:
    bus_stop_data = json.load(f)

with open(r"C:\Users\lisajos\QGIS_Projects\Output\Edited_Attributes\railway_subway_entrance_WGS_EDITED.geojson", "r", encoding="utf-8") as f:
    subway_entrance_data = json.load(f)

view_state = pdk.ViewState(
    latitude=59.3296,
    longitude=18.0586,
    zoom=10.3,
    pitch=0
)

# Define layers
ALL_LAYERS = {
    "Bus Stops": pdk.Layer(
        "GeoJsonLayer",
        bus_stop_data,
        opacity=0.8,
        stroked=True,
        filled=True,
        extruded=False,
        wireframe=True,
        pickable=True,
        get_line_color="[0, 0, 0]",
        get_fill_color="[200, 100, 240, 100]",
        get_radius=50
    ),
    "Subway Entrances": pdk.Layer(
        "GeoJsonLayer",
        subway_entrance_data,
        opacity=0.8,
        stroked=True,
        filled=True,
        extruded=False,
        wireframe=True,
        pickable=True,
        get_line_color="[0, 0, 0]",
        get_fill_color="[100, 200, 100, 100]",
        get_radius=50
    ),
}

st.sidebar.markdown("### Map Layers")
selected_layers = [
    layer
    for layer_name, layer in ALL_LAYERS.items()
    if st.sidebar.checkbox(layer_name, True)
]

if selected_layers:
    deck = pdk.Deck(
        layers=selected_layers,
        initial_view_state=view_state,
        map_style="mapbox://styles/mapbox/light-v9"
    )
    st.pydeck_chart(deck, height=700)
else:
    st.error("Please choose at least one layer above.")

# Download button
#st.download_button(label="Download Bus Stops", data=bus_stop_data, file_name=bus_stop_data, mime=None, key=None, help=None, on_click="rerun", args=None, kwargs=None, type="secondary", icon=":material/download:", disabled=False, use_container_width=False)

@st.cache_data
def get_data():
    df = pd.DataFrame(
        np.random.randn(50, 20), columns=("col %d" % i for i in range(20))
    )
    return df

@st.cache_data
def convert_for_download(df):
    return df.to_csv().encode("utf-8")

df = get_data()
csv = convert_for_download(df)

st.download_button(
    label="Download Bus Stops (GeoJSON)",
    data=csv,
    file_name="data.csv",
    mime="text/csv",
    icon=":material/download:",
)