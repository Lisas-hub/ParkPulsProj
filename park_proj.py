# Öppna appen via Win R > cmd
# alternativt terminalen i Pycharm
# och skriv
# streamlit run C:\Users\lisajos\PycharmProjects\park_proj\park_proj.py

import streamlit as st

home_page = st.Page("home_page.py", title="Home Page")
#page_1 = st.Page("archive/page_1.py", title="Page 1") # mapping demo pydeck - clickable layers
#page_2 = st.Page("archive/page_2.py", title="Page 2") # mapping demo leafmap - clustered points
#page_3 = st.Page("archive/page_3.py", title="Page 3") # mapping demo leafmap - topographic map
#page_4 = st.Page("archive/page_4.py", title="Page 4") # busshållsplatser test
#page_5 = st.Page("archive/page_5.py", title="Page 5") # Google Sheets API test
#page_6 = st.Page("archive/page_6.py", title="Page 6") # Excel test
#page_7 = st.Page("archive/page_7.py", title="Page 7") # test folium map w sociotop map and attached attributes
#page_8 = st.Page("archive/page_8.py", title="Page 8") # leafmap splitmap test
#page_9 = st.Page("archive/page_9.py", title="Page 9") # pydeck test
#page_10 = st.Page("archive/page_10.py", title="Page 10") # OG bus stops test copy
#UGS = st.Page("archive/UGS.py", title="Urban Green Spaces")
#transport = st.Page("archive/Transport.py", title="Transportation")
#biotope = st.Page("archive/Biotope.py", title="Biotopes **slow to load**")
#noise = st.Page("archive/Noise_Pollution.py", title="Noise Pollution **slow to load**")
#socio_economic = st.Page("archive/Socio_economic.py", title="Socio economic")
#socio_economic2 = st.Page("archive/Socio_economic_2.py", title="Socio economic 2")
parks = st.Page("Parks.py", title="Parks")
parks2 = st.Page("Parks2.py", title="Parks2")

page_TOPICS = st.Page("page_TOPICS.py", title="Park related topics in TyckTill comments")
page_SENTIMENTS = st.Page("page_SENTIMENTS.py", title="Sentiments in parks")
page_TYCKTILL = st.Page("page_TYCKTILL.py", title="TyckTill")
page_TYCKTILL2 = st.Page("page_TYCKTILL2.py", title="TyckTill2")
page_TYCKTILL3 = st.Page("page_TYCKTILL3.py", title="TyckTill3")
page_TYCKTILL4 = st.Page("page_TYCKTILL4.py", title="TyckTill4")
page_TYCKTILL5 = st.Page("page_TYCKTILL5.py", title="TyckTill5")

#pg = st.navigation([page_TYCKTILL4, page_TYCKTILL3, page_TYCKTILL2, page_TYCKTILL, page_TOPICS, parks2, parks])
pg = st.navigation([page_TYCKTILL5, page_TYCKTILL4, page_TYCKTILL3])
pg.run()