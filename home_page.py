import streamlit as st

st.header("Welcome to the Park Puls interactive web application!")

import folium
from streamlit_folium import st_folium
import pandas as pd

# ***** test table popup *****
m = folium.Map(location=(43, -100), zoom_start=4, tiles=None)
df = pd.DataFrame(
    data=[["apple", "oranges"], ["other", "stuff"]], columns=["cats", "dogs"]
)
html = df.to_html(
    classes="table table-striped table-hover table-condensed table-responsive"
)
popup = folium.Popup(html)

folium.Marker([30, -100], popup=popup).add_to(m)

st_folium(m, width=700, height=500)

