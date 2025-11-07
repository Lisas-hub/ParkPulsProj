
import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import branca.colormap as cm
import numpy as np
import mapclassify

st.set_page_config(layout="wide")

# ===========
# load layers

@st.cache_data(show_spinner="Loading spatial data...")
def load_layer(path: str, layer_name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path, layer=layer_name)
    return gdf.to_crs(epsg=4326)

sentiments_per_park = load_layer(
    r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\tycktill.gpkg",
    "sentiments_per_park"
) # column to use is called "sentiment_score_per_ha"
stats_per_park = load_layer(
    r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\tycktill.gpkg",
    "stats_per_park"
) # column to use is called "Idé_rel" which shows ideas per park (normalised count)

sentiments_per_park = sentiments_per_park.dropna(subset=["sentiment_score_per_ha"])

# ==========
# page setup

st.title("Vad tycker besökarna om Stockholms parker?")
st.text("Sammanställd data från appen TyckTill")

tab1, tab2 = st.tabs(["General", "Sentiments"])

# initialize selected layer variable
if "selected_layer" not in st.session_state:
    st.session_state.selected_layer = None
    st.session_state.layer_column = None
    st.session_state.layer_type = None

# ===========
# general tab
with tab1:
    st.write("Select a general layer:")
    if st.button("Stats per Park"):
        st.session_state.selected_layer = stats_per_park
        st.session_state.layer_column = "Idé_rel"
        st.session_state.layer_type = "stats"

# ==============
# sentiments tab
with tab2:
    st.write("Select a sentiments layer:")
    if st.button("Sentiments per Park"):
        st.session_state.selected_layer = sentiments_per_park
        st.session_state.layer_column = "sentiment_score_per_ha"
        st.session_state.layer_type = "sentiments"

# ===========
# display map

if st.session_state.selected_layer is not None:
    m = folium.Map(location=(59.33, 17.99), zoom_start=10.5, tiles=None)

    # satellite basemap from ESRI
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satellite',
        overlay=False,
        control=True
    ).add_to(m)

    # --- sentiments layer with quantile-based coloring ---
    if st.session_state.layer_type == "sentiments":
        n_classes = 5
        values = st.session_state.selected_layer[st.session_state.layer_column].values
        quantiles = np.quantile(values, np.linspace(0, 1, n_classes + 1))
        colors = ["#d73027", "#f4a582", "#f7f7f7", "#a6dba0", "#1b7837"]

        def get_color(value):
            for i in range(n_classes):
                if quantiles[i] <= value <= quantiles[i + 1]:
                    return colors[i]
            return colors[-1]

        def style_function(feature):
            value = feature["properties"][st.session_state.layer_column]
            return {
                "fillColor": get_color(value),
                "color": "black",
                "weight": 0.5,
                "fillOpacity": 0.6
            }

        folium.GeoJson(
            st.session_state.selected_layer,
            style_function=style_function,
            tooltip=folium.features.GeoJsonTooltip(
                fields=[st.session_state.layer_column],
                aliases=["Sentiment score per ha:"],
                localize=True
            )
        ).add_to(m)

    # --- stats layer (optional linear coloring) ---
    elif st.session_state.layer_type == "stats":
        n_classes = 5

        # Extract values
        values = stats_per_park["Idé_rel"].values

        # Compute Jenks breaks
        classifier = mapclassify.NaturalBreaks(values, k=n_classes)
        breaks = classifier.bins  # these are the upper bounds of each class

        # Define a color palette
        colors = ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]


        # Function to get color for a value
        def get_color(value):
            for i, b in enumerate(breaks):
                if value <= b:
                    return colors[i]
            return colors[-1]


        # Style function for Folium
        def style_function(feature):
            value = feature["properties"]["Idé_rel"]
            return {
                "fillColor": get_color(value),
                "color": "black",
                "weight": 0.5,
                "fillOpacity": 0.7
            }

        folium.GeoJson(
            stats_per_park,
            style_function=style_function,
            tooltip=folium.features.GeoJsonTooltip(
                fields=["Idé_rel"],
                aliases=["Ideas per park:"],
                localize=True
            )
        ).add_to(m)

    st_folium(m, width=1200, height=800)
else:
    st.info("Select a layer using the buttons above to display the map.")
