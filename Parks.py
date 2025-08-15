import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium


st.set_page_config(layout="wide")
st.title("Parks in Stockholm")

# TO-DO-LIST
# CHANGE INPUT FILE TO VARIABLES_for_streamlit.py
# add NAMN_combined to feedback section in the sidebar? maybe skip, some polygons have MANY names
# add municipality boundary
# add more variables
# make the stars rating stay? like the rating stays even if the page re-loads? if possible
# can there be a section of "your ratings?" where you can see multiple ratings you have done in one place?

# See more basemap tiles here https://leaflet-extras.github.io/leaflet-providers/preview/
m = folium.Map(location=(59.33, 17.99), zoom_start=10.5,
               tiles=None)  # can add basemap here but not give an alias, instead need to use code below


# ======= satellite basemap w labels =======
# cons - labels get covered by whatever layer is added ontop
#folium.TileLayer(
#    tiles='https://tiles.stadiamaps.com/tiles/alidade_satellite/{z}/{x}/{y}{r}.jpg',
#    attr='&copy; CNES, Distribution Airbus DS, © Airbus DS, © PlanetObserver (Contains Copernicus Data) | '
#         '&copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> '
#         '&copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> '
#         '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
#    name='Stadia Alidade Satellite',
#    overlay=False,
#    control=True,
#).add_to(m)

# ======= basemap w just labels =======
folium.TileLayer(
    tiles='https://tiles.stadiamaps.com/tiles/stamen_toner_labels/{z}/{x}/{y}{r}.png',
    attr='&copy; <a href="https://www.stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://www.stamen.com/">Stamen Design</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    name='Stamen Toner Labels',
    overlay=True,
    control=True,
    max_zoom=20,
    min_zoom=0
).add_to(m)

# ======= satellite basemap from ESRI =======
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri',
    name='Esri Satellite',
    overlay=True,
    control=True
).add_to(m)

#folium.LayerControl(collapsed=False).add_to(m)


@st.cache_data(show_spinner=False)
def load_gdf():
    return gpd.read_file(r"C:\Users\lisajos\PycharmProjects\park_proj\data\VARIABLES.gpkg", layer="all_variables")

sociotop2024_gdf = load_gdf()

popup = folium.GeoJsonPopup(
    fields=["NAMN_top5",
            "TYP_combined",
            "typology",
            "variable_religious",
            "variable_swim_areas",
            "BIOTOP_combined",
            "amenities",
            "variable_public_transport",
            "variable_amenity_food"],
    aliases=["Name(s)",
             "Sociotop",
             "Typology",
             "Religious",
             "Swimming facility",
             "Biotop",
             "Amenities",
             "Public transport within 200 m",
             "Food establishments within 200 m"],
    localize=True,
    labels=True,
)

folium.GeoJson(
    sociotop2024_gdf,
    name="Parks",
    popup=popup,
    style_function=lambda x: {
        "fillColor": "#ffffff",
        "color": "#ffffff",
        "weight": 1.3,
        "fillOpacity": 0.4,
    },
).add_to(m)

# Sidebar

st.sidebar.title("Feedback")
st.sidebar.markdown("Click any park to leave feedback on it here!")

out = st_folium(m, key="map", use_container_width=True, height=750)

if out and out.get("last_object_clicked"):
    clicked_lat = out["last_object_clicked"]["lat"]
    clicked_lon = out["last_object_clicked"]["lng"]
    st.sidebar.markdown(f"add park name(s)?")  # ***CHANGE THIS SO COLUMN NAMN_combined IS SHOWN HERE***

    st.sidebar.header("Leave a rating")

    # Display feedback widget for the selected marker
    feedback = st.sidebar.feedback("stars", key=f"feedback_{clicked_lat}_{clicked_lon}")
    if feedback is not None:
        st.sidebar.markdown(f"You rated this park {feedback + 1} stars")

    st.sidebar.header("Leave a comment")

    with st.sidebar.form("comment_form"):
        comment = st.text_area(
            label="",
            placeholder="add comment here",
            label_visibility="collapsed"
        )
        submitted = st.form_submit_button("Submit")
        if submitted:
            st.sidebar.write("Thank you for your comment!")