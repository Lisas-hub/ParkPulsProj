
# >>> STANZA NLP PIPELINE per kategori <<<

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

input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

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
parks = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

subset_within_parks = gpd.sjoin(tycktill_df_geo, parks, how="inner", predicate="within")
tycktill_df_geo["in_park"] = tycktill_df_geo.index.isin(subset_within_parks.index)

# ============================================
# subset by parks and a limited number of rows
municipality = gpd.read_file(f"{input_directory}\\Output\\Kommun_Stadskartan_SWEREF99TM.gpkg").to_crs("EPSG:3006")
municipality_geom = municipality.geometry.iloc[0]

# subset tycktill dataset to begin with before committing to processing all 300000+ rows
kategori_filter = "Remiss skickad"
#in_park_filter = True
# ^^RERUN? Update here!^^

subset_tycktill_df = tycktill_df_geo[
    (tycktill_df_geo["Kategori"] == kategori_filter) &
    #(tycktill_df_geo["in_park"] == in_park_filter) &
    (tycktill_df_geo.geometry.within(municipality_geom))
].copy()

print(f"Selected {len(subset_tycktill_df)} rows with Kategori = '{kategori_filter}' out of {len(tycktill_df_geo)} total rows.")
#print(f"Selected {len(subset_tycktill_df)} rows with Kategori = '{kategori_filter}' and in_park = {in_park_filter} out of {len(tycktill_df_geo)} total rows.")

# Selected 2122 rows with Kategori = 'Beröm' out of 393989 total rows.
# Selected 6257 rows with Kategori = 'Idé' out of 393989 total rows.
# Selected 8487 rows with Kategori = 'Klagomål' out of 393989 total rows.
# Selected 8503 rows with Kategori = 'Fråga' out of 393989 total rows.

# Selected 78357 rows with Kategori = 'Felanmälan' and in_park = True out of 393989 total rows.  *** NOT with 'in municipality' filter ***
# Selected 78356 rows with Kategori = 'Felanmälan' and in_park = True out of 393989 total rows.  *** WITH 'in municipality' filter ***

# Selected 2 rows with Kategori = 'Fordonsflytt' and in_park = True out of 393989 total rows.    *** WITH 'in municipality' filter ***
# Selected 43 rows with Kategori = 'Arbetsorder ska skickas' out of 393989 total rows.           *** WITH 'in municipality' filter ***
# Selected 18 rows with Kategori = 'Ordningsstörning' out of 393989 total rows.                  *** WITH 'in municipality' filter ***
# Selected 64 rows with Kategori = 'Remiss skickad' out of 393989 total rows.                    *** WITH 'in municipality' filter ***

# =================================================================
# set up for saving figures based on number of points in the subset

output_folder = f"data/tyck_till_output/per_kategori"
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

# ===============
# Topic Modelling    *** move to after sentiments and run topic model on all rows at once? ***

from bertopic import BERTopic
from sentence_transformers import SentenceTransformer

texts = subset_tycktill_df['lemmas'].apply(lambda words: ' '.join(words)).tolist()

embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# create topic model
topic_model = BERTopic(
    embedding_model=embedding_model,
    language="swedish",
    min_topic_size=2, # probably adjust this one when using a bigger subset
    verbose=True
)

topics, probs = topic_model.fit_transform(texts)
subset_tycktill_df['topic'] = topics
subset_tycktill_df['topic_prob'] = probs

topic_info = topic_model.get_topic_info()
topic_words = topic_model.get_topic(0)
print(topic_info)
print(topic_words)

def get_top_words(topic_num):
    words = topic_model.get_topic(topic_num)
    return ', '.join([word for word, _ in words]) if words else ''

subset_tycktill_df['topic_keywords'] = subset_tycktill_df['topic'].apply(get_top_words)

# ====
# Save

subset_tycktill_df.to_excel(f"{output_folder}/tycktill_with_lemmas_{kategori_filter}.xlsx", index=False)
#subset_tycktill_df.to_excel(f"{output_folder}/tycktill_with_lemmas_{kategori_filter}_in_park_{in_park_filter}.xlsx", index=False)

