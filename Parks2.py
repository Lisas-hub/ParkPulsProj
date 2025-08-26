import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import geopandas as gpd

st.set_page_config(layout="wide")

st.title("Welcome to the Park Puls map!")

# TO DO
# make polygon extent highlight somehow when you hover over it (without having to open a popup)


# Load layers
@st.cache_data(show_spinner="Loading spatial data...")
def load_layer(path: str, layer_name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path, layer=layer_name)
    return gdf.to_crs(epsg=4326)
layer_variables = load_layer(path=r"C:\Users\lisajos\PycharmProjects\park_proj\data\VARIABLES_for_streamlit.gpkg", layer_name="VARIABLES_for_streamlit")
layer_variables = layer_variables.to_crs(epsg=4326) # apparently WGS84 is necessary for folium?? But it was fine without it before


#Load map
m = folium.Map(location=(59.33, 17.99), zoom_start=10.5, tiles=None)


# ===== DROPDOWN LIST TO SELECT THEME =====

themes = {
    "Amenities": ["NAMN_top5", "TYP_combined", "typology", "amenities"],
    "Environment": ["NAMN_top5", "BIOTOP_combined"],
    "Accessibility": ["NAMN_top5"], # *** ADD COLUMNS (+ aliases below) ***
    "Socioeconomic factors": ["NAMN_top5"] # *** ADD COLUMNS (+ aliases below) ***
}
column_aliases = {
    "NAMN_top5": "Name(s)",
    "TYP_combined": "Typology1",
    "typology": "Typology2",
    "BIOTOP_combined": "Biotope",
    "amenities": "Amenities",
}

layer_options = list(themes.keys())
selected_layer = st.selectbox("Select a theme to view in the dropdown list", layer_options)
st.markdown("Click a park to view more information")

# Filter to only the relevant columns + geometry
selected_columns = themes[selected_layer] + ["geometry"]
layer_variables_filtered = layer_variables[selected_columns].copy()

# Display selected layer
folium.GeoJson(
    layer_variables_filtered,
    name=selected_layer,
    tooltip=folium.GeoJsonTooltip(fields=themes[selected_layer]),
    style_function=lambda feature: {
        "fillColor": "yellow",
        "color": "black",
        "weight": 0.5,
        "fillOpacity": 0.4
    }
).add_to(m)

# Get only relevant popup columns for this theme
popup_cols = [col for col in themes[selected_layer] if col in layer_variables_filtered.columns]

# Create feature group to show park polygons as a single item in the layer panel
layer_variables_group = folium.FeatureGroup(name="Parks")


# ==== BASEMAPS ====

# Add custom pane for labels so that they show up on top
folium.map.CustomPane("labels").add_to(m)

# satellite basemap from ESRI
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri',
    name='Esri Satellite',
    overlay=False,
    control=True
).add_to(m)

# just labels
folium.TileLayer(
    tiles='https://tiles.stadiamaps.com/tiles/stamen_toner_labels/{z}/{x}/{y}{r}.png',
    attr='&copy; <a href="https://www.stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://www.stamen.com/">Stamen Design</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    name='Stamen Toner Labels',
    overlay=True,
    control=True,
    pane='labels' # makes labels go on top
).add_to(m)


# ==== TABLE POPUP ====

for _, row in layer_variables.iterrows():
    # Extract selected columns
    attr_df = pd.DataFrame([row[popup_cols]])
    attr_df = attr_df.rename(columns={k: column_aliases.get(k, k) for k in popup_cols})
    # Transpose table
    attr_df = attr_df.T.reset_index()
    attr_df.columns = ["Field", "Value"]
    # Convert to HTML table
    html = attr_df.to_html(
        index=False,
        escape=False,
        classes = "table table-striped table-hover table-condensed table-bordered"
    )
    style = """
            <style>
                td:first-child {
                    width: 150px;
                    font-weight: bold;
                }
            </style>
            """
    full_html = style + html

    popup = folium.Popup(full_html, max_width=500)

    folium.GeoJson(
        row.geometry,
        popup=popup,
        style_function=lambda x: {
            "fillColor": "#ffffff",
            "color": "#ffffff",
            "weight": 1.3,
            "fillOpacity": 0.4,
        }
    ).add_to(layer_variables_group)

layer_variables_group.add_to(m)


# ==== LAYER CONTROL ====

folium.LayerControl('topright', collapsed=False).add_to(m)


# ==== SIDEBAR ====

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


# ==== DOWNLOAD BUTTON ====

import numpy as np
import pandas as pd

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
    label="Example file (file type)",
    data=csv,
    file_name="data.csv",
    mime="text/csv",
    icon=":material/download:",
)





