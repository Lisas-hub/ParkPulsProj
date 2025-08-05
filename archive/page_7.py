import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("Parks in Stockholm")

# See more basemap tiles here https://leaflet-extras.github.io/leaflet-providers/preview/
m = folium.Map(location=(59.32, 18.08), zoom_start=10.5, tiles=None) # can add basemap here but not give an alias, instead need to use code below

folium.TileLayer(
    "cartodbpositron",
    name="Basemap"
).add_to(m)

# caching to stop my map reloading on a loop because of the GeoJsonPopup layer
@st.cache_data(show_spinner=False)
def load_gdf():
    # Load GeoDataFrame
    return gpd.read_file(r"C:\Users\lisajos\PycharmProjects\Variables\VARIABLES.gpkg", layer="all_variables")

sociotop2024_gdf = load_gdf()

# Create popup # THIS IS FOR GeoJsonPopup (click), not GeoJsonTooltip (hover), the latter does not support aliases
# ====== ALT 1 / GeoJsonPopup (popup appears on click) / supports aliases =====
popup = folium.GeoJsonPopup(
    fields=["variable_sports", "variable_schools"],
    aliases=["Sports facilities", "Schools"],
    localize=True,
    labels=True,
) # see more about popups here https://python-visualization.github.io/folium/latest/user_guide/ui_elements/popups.html

folium.GeoJson(
    sociotop2024_gdf,
    name="Parks",
    popup=popup,
    style_function=lambda x: {
        "fillColor": "#529c65",
        "color": "#000000",
        "weight": 0.5,
        "fillOpacity": 0.7,
    },
).add_to(m)

# ====== ALT 2 / GeoJsonTooltip (popup appears on hover) / does not support aliases but can be added through a work around =====
sociotop2024_gdf['custom_tooltip'] = (
    "Sports facilities: " + sociotop2024_gdf['variable_sports'].astype(str) + "<br>" +
    "Schools: " + sociotop2024_gdf['variable_schools'].astype(str) + "<br>" +
    "Play areas: " + sociotop2024_gdf['variable_play_areas'].astype(str) + "<br>" +
    "Religious: " + sociotop2024_gdf['variable_religious'].astype(str) + "<br>" +
    "Gardens: " + sociotop2024_gdf['variable_gardens'].astype(str) + "<br>" +
    "Swimming areas: " + sociotop2024_gdf['variable_swim_areas'].astype(str)
)

folium.GeoJson(
    sociotop2024_gdf,
    name="Parks_2",
    #tooltip=folium.GeoJsonTooltip(fields=["variable_sports", "variable_schools"]), # use this if no custom tooltip column
    tooltip=folium.GeoJsonTooltip(
        fields=["custom_tooltip"],
        labels=False,  # no labels needed, it's already formatted
        sticky=True,
    ),
    style_function=lambda x: {
        "fillColor": "#529c65",
        "color": "#000000",
        "weight": 0.5,
        "fillOpacity": 0.7,
    },
).add_to(m)

# rating
out = st_folium(m, key="map", use_container_width=True, height=750)

if out and out.get("last_object_clicked"):
    clicked_lat = out["last_object_clicked"]["lat"]
    clicked_lon = out["last_object_clicked"]["lng"]
    st.write(f"Selected marker at ({clicked_lat}, {clicked_lon})")

    # Display feedback widget for the selected marker
    feedback = st.feedback("stars", key=f"feedback_{clicked_lat}_{clicked_lon}")
    if feedback is not None:
        st.sidebar.markdown(f"Feedback for marker at ({clicked_lat}, {clicked_lon}): {feedback + 1} stars")

#folium.LayerControl().add_to(m)

# Display map in Streamlit
#st_folium(m, use_container_width=True, height=750)
