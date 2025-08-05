import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
import branca.colormap as cm

st.set_page_config(layout="wide")

st.title("Socioeconomic data")

soc_gdf = gpd.read_file(r"C:\Users\lisajos\R_Projects\deso_summary.geojson")

# List available numeric columns for mapping (excluding geometry and ID fields)
exclude_cols = ["geometry", "NAMN", "id", "DESO", "MedianInk_SCB_median", "MedianInk_SCB_sd"]
numeric_cols = soc_gdf.select_dtypes(include='number').columns.difference(exclude_cols)

# Dropdown for user to select which variable to map
selected_variable = st.selectbox("Select a variable to visualize", numeric_cols)

m = leafmap.Map(
    center=[59.32, 18.08],
    zoom=10.5,
    minimap_control=True,
    draw_control=False,
    measure_control=False,
    attribution_control=False
)

soc_geojson = soc_gdf.to_json()

# Create color map
print(cm.linear.__dict__.keys())

values = soc_gdf[selected_variable]
colormap = cm.LinearColormap(["white", "blue"], vmin=values.min(), vmax=values.max())
colormap.caption = f"{selected_variable} by NAMN"

# Define style function
def style_function(feature):
    value = feature["properties"][selected_variable]
    color = "#8c8c8c" if value is None else colormap(value)
    return {
        "fillOpacity": 0.7,
        "weight": 0.5,
        "color": "black",
        "fillColor": color,
    }

# Add styled GeoJSON layer
m.add_geojson(soc_geojson, layer_name="MedianInk_SCB_mean", style_function=style_function)

#m.add_geojson(soc_geojson, layer_name="Socioeconomic") #add style = xxx ? see UGS.py

# Show colorbar and map
colormap.add_to(m)
m.to_streamlit(height=750)

st.markdown("Rate this park")
sentiment_mapping = ["one", "two", "three", "four", "five"]
selected = st.feedback("stars")
if selected is not None:
    st.markdown(f"You selected {sentiment_mapping[selected]} star(s).")
