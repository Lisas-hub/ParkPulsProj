#FÖRSÖK ATT VISUALISERA EGEN DATA (EXCELFIL)
import streamlit as st
import pandas as pd
#import numpy as np
#import openpyxl #hade problem med openpyxl men kopierade mappar enl kommentar i https://www.reddit.com/r/learnpython/comments/fah9mz/need_help_no_module_named_openpyxl/

#df = pd.read_excel(r"C:\Users\lisajos\QGIS_Projects\Output\WGS84\highway_bus_stop_pts_TEST.xlsx") #sidan fastnar på ladda...
#st.map(df, latitude="y_coord", longitude="x_coord") #sidan fastnar på ladda...

# Read the Excel file
#df = pd.read_excel(r"C:\Users\lisajos\QGIS_Projects\Output\WGS84\highway_bus_stop_pts_TEST.xlsx")

# Rename columns to match what st.map expects
#df = df.rename(columns={"y_coord": "lat", "x_coord": "lon"})

# Display the map
#st.map(df)

import streamlit as st

# Create the SQL connection to pets_db as specified in your secrets file.
conn = st.connection('pets_db', type='sql')