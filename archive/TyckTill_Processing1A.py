
# >>> STANZA NLP PIPELINE using n_points subset <<<

# natural language processing (NLP) packages
import nltk # has some swedish, use for stopwords and maybe more
import spacy # has swedish but maybe better suited for other types of projects than scentific ones?
import stanza # good for Swedish? uses Talbanken?

# additional/other packages
import pandas as pd
import numpy as np
from collections import Counter
import geopandas as gpd
from shapely.geometry import Point
import os

from nltk.corpus import stopwords

# downloads
#nltk.download('punkt')
#nltk.download('stopwords')
#stanza.download('sv')

# ===============================
# === LOAD PRE-PROCESSED DATA ===

tycktill_df = pd.read_excel("data/cleaned_dataset.xlsx")

# ============================================
# === TOKENIZE / POS-TAG / LEMMATIZE / ETC ===

# ==============
# load stopwords
stop_words = set(stopwords.words("swedish"))

# ======================
# create geometry column

tycktill_df["geometry"] = tycktill_df.apply(lambda row: Point(row["Koordinater_x"], row["Koordinater_Y"]), axis=1)
tycktill_df_geo = gpd.GeoDataFrame(tycktill_df, geometry="geometry", crs="EPSG:4326").to_crs("EPSG:3006")

# =================================================
# prepp for filtering inside or outside parks later
parks = gpd.read_file("../data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

subset_within_parks = gpd.sjoin(tycktill_df_geo, parks, how="inner", predicate="within")
tycktill_df_geo["in_park"] = tycktill_df_geo.index.isin(subset_within_parks.index)

# ============================================
# subset by parks and a limited number of rows

# subset tycktill dataset to begin with before committing to processing all 300000+ rows
n_points = 10000        # *** RERUN? Update here! ***

sample_in = tycktill_df_geo[tycktill_df_geo["in_park"]].sample(n=n_points, random_state=1) # in_park = true
sample_out = tycktill_df_geo[~tycktill_df_geo["in_park"]].sample(n=n_points, random_state=1) # in_park = false

subset_tycktill_df = pd.concat([sample_in, sample_out]).copy() # get an equal number from within and outside parks

# =================================================================
# set up for saving figures based on number of points in the subset

output_folder = f"data/tyck_till_output/sample_{n_points * 2}_points"
os.makedirs(output_folder, exist_ok=True)


# ============
# NLP pipeline
nlp = stanza.Pipeline("sv", processors="tokenize,pos,lemma")

lemmatized_rows = []
for i, row in subset_tycktill_df.iterrows():
    print(f"Processing row {i + 1} of {len(subset_tycktill_df)}", flush=True)

    text = row["clean_Fritext"]

    doc = nlp(text)
    lemmas = [
        word.lemma for sentence in doc.sentences for word in sentence.words
        if word.upos != "PUNCT" and word.text.casefold() not in stop_words
    ]

    lemmatized_rows.append(lemmas)

subset_tycktill_df["lemmas"] = lemmatized_rows

subset_tycktill_df.to_excel(f"{output_folder}/tycktill_with_lemmas.xlsx", index=False)

