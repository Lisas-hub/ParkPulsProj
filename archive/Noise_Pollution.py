import streamlit as st
import geopandas as gpd
import leafmap.foliumap as leafmap
import pandas as pd

st.set_page_config(layout="wide")

st.title("Noise Pollution in Stockholm")

# Create the map
m = leafmap.Map(
    center=[59.32, 18.08],
    zoom=10.5,
    minimap_control=True,
    draw_control=False,
    measure_control=False,
    attribution_control=False
)

noise_gdf = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\GeoJSON\Bullerkartan_2022_Vag_och_Tagbuller_WGS.geojson")

#@st.cache_data
#def load_and_prepare_noise_gdf():
#    noise_gdf = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\GeoJSON\Bullerkartan_2022_Vag_och_Tagbuller_WGS.geojson")
#    return noise_gdf

#kommun_gdf = gpd.read_file(r"C:\temp\Lisa\Output\GeoJSON\Kommun_Stadskartan_WGS.geojson")
#kommun_geojson = kommun_gdf.to_json()

#noise_gdf = load_and_prepare_noise_gdf()
noise_geojson = noise_gdf.to_json()

m.add_geojson(noise_geojson, layer_name="Noise Pollution")

# Display the map in Streamlit
m.to_streamlit(height=750)