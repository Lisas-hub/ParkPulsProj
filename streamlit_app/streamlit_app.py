
import streamlit as st

#home_page = st.Page("home_page.py", title="Home page")
page_TYCKTILL5 = st.Page("Page_TYCKTILL5.py", title="Tyck till resultat")

pg = st.navigation([page_TYCKTILL5])
pg.run()