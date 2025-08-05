import streamlit as st
import geopandas as gpd
import leafmap.foliumap as leafmap
import pandas as pd

st.set_page_config(layout="wide")

st.title("Biotopes in Stockholm")

m = leafmap.Map(
    center=[59.32, 18.08],
    zoom=10.5,
    minimap_control=True,
    draw_control=False,
    measure_control=False,
    attribution_control=False
)

# Add Biotopkartan_2019 layer
# OBS! hade problem m timestamp/datetime64 trots att jag löst problemet förut
# det berodde på att en kolumn i attributtabellen i GIS hette timestamp så jag tror python glitchade ur
# det funkade när jag tog bort kolumnen, hade nog kunnat döpa om den också men tyckte inte den behövdes
@st.cache_data
def load_and_prepare_biotop_gdf():
    biotop_gdf = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\Edited_Attributes\Biotopkartan_2019_Huvudklass_WGS_EDITED.geojson")
    return biotop_gdf

#kommun_gdf = gpd.read_file(r"C:\temp\Lisa\Output\GeoJSON\Kommun_Stadskartan_WGS.geojson")
#kommun_geojson = kommun_gdf.to_json()

biotop_gdf = load_and_prepare_biotop_gdf()
biotop_geojson = biotop_gdf.to_json()

kategori_colors = {
    "Buskmark": "#a6c16f",
    "Odlingsmark": "#f1d271",
    "Skogsmark/trädklädd mark": "#23932f",
    "Urban gråstruktur": "#8a8a8a",
    "Urban grönstruktur": "#dbedb5",
    "Vatten": "#77c1d4",
    "Öppen mark": "#efec8c",
}
def style_function(feature):
    kategori = feature["properties"].get("h_klass", "")
    fill_color = kategori_colors.get(kategori, "lightgray")  # Default if not found
    return {
        "color": fill_color,
        "fillColor": fill_color,
        "weight": 1,
        "fillOpacity": 0.5,
    }

m.add_geojson(biotop_geojson, layer_name="Biotopes", style_callback=style_function)

# Display the map in Streamlit
m.to_streamlit(height=750)