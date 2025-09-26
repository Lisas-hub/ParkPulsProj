
# >>> PLOTS per kategori <<<

import pandas as pd
import numpy as np
from collections import Counter
import geopandas as gpd
import folium
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
import os

# =====================================
# set up for saving in the right folder

kategori_input = input("☆☆☆ Enter the Kategori used in the first script (e.g. Felanmälan): ")

if not kategori_input:
    print("❌ enter a valid kategori ❌")
    exit()

output_folder = os.path.join("data", "tyck_till_output", "per_kategori")

# ======================
# load processed dataset
df = pd.read_excel(f"{output_folder}/tycktill_with_sentiment_{kategori_input}.xlsx", parse_dates=["Inkommet datum"])

# ===========
# figurer med bara en kategori? eller slå ihop excelfiler

