#FÖRSÖK MED FOLIUM IST FÖR LEAFMAP FÖR MAN KAN INTE HA POPUP BOX MED LEAFMAP (ELLER? DUBBELKOLLA)

import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("Socioeconomic data 2")

# See more basemap tiles here https://leaflet-extras.github.io/leaflet-providers/preview/
m = folium.Map(location=(59.32, 18.08), zoom_start=10.5, tiles="cartodb positron")

# Load your GeoDataFrame
soc2_gdf = gpd.read_file(r"C:\Users\lisajos\R_Projects\deso_summary.geojson")

# Add choropleth layer
choropleth = folium.Choropleth(
    geo_data=soc2_gdf,
    name="Ålder 0-6 år",
    data=soc2_gdf,
    columns=["DESO", "Alder_0_6"],
    key_on="feature.properties.DESO",
    bins=25,
    fill_color="YlGn",
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name="Age 0-6",
    highlight=True,
)
choropleth.add_to(m)

# Create popup - något är fel här, det dyker inte upp
popup = folium.GeoJsonPopup(
    fields=["DESO", "Alder_0_6"],
    aliases=["ID", "Ålder 0-6 år"],
    localize=True,
    labels=True,
    style="background-color: yellow;",
)

# Add GeoJson layer for popups
folium.GeoJson(
    soc2_gdf,
    name="Popup Layer",
    popup=popup,
    tooltip=folium.GeoJsonTooltip(fields=["DESO", "Alder_0_6"]),
    style_function=lambda x: {"fillOpacity": 0, "weight": 0},  # transparent layer
).add_to(m)

folium.LayerControl().add_to(m)

# Display map in Streamlit
st_folium(m, use_container_width=True, height=750) # container width kanske påverkar legenden

