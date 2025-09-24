


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
import folium
import matplotlib.pyplot as plt
#import seaborn as sns
from wordcloud import WordCloud
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
parks = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

subset_within_parks = gpd.sjoin(tycktill_df_geo, parks, how="inner", predicate="within")
tycktill_df_geo["in_park"] = tycktill_df_geo.index.isin(subset_within_parks.index)

# ============================================
# subset by parks and a limited number of rows

# subset tycktill dataset to begin with before committing to processing all 300000+ rows
n_points = 500        # *** RERUN? Update here! ***

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

# ======================================================================================
# truncate text before sentiment (because there is a limit to text length with the model

from transformers import AutoTokenizer, pipeline

tokenizer = AutoTokenizer.from_pretrained("KBLab/robust-swedish-sentiment-multiclass")

# ================================================================
# ============ PRETRAINED LANGUAGE MODEL FOR SWEDISH =============
# ========== KBLab/robust-swedish-sentiment-multiclass ===========
# https://huggingface.co/KBLab/robust-swedish-sentiment-multiclass

from transformers import pipeline
from transformers import AutoTokenizer

model_name = "KBLab/robust-swedish-sentiment-multiclass"
tokenizer = AutoTokenizer.from_pretrained(model_name)

# load model
model = pipeline(
    "text-classification",
    model="KBLab/robust-swedish-sentiment-multiclass",
    top_k=None  # Get all class scores, not just the top one
)


def prepare_inputs(texts, tokenizer, max_length=512):
    return tokenizer(
        texts,
        truncation=True,
        max_length=max_length,
        padding=False,         # Or True/“max_length” if batching
        return_tensors=None    # Set to "pt" if feeding directly to model
    )

# Apply to your DataFrame column
texts = subset_tycktill_df["clean_Fritext"].astype(str).tolist()

# apply sentiment analysis
# Run through the sentiment pipeline directly — it handles truncation automatically
sentiments = model(texts, truncation=True)
#sentiments = model(texts)
subset_tycktill_df["sentiment_label"] = [s[0]["label"] for s in sentiments]
subset_tycktill_df["sentiment_score"] = [s[0]["score"] for s in sentiments]
subset_tycktill_df["sentiment_all"] = sentiments # keep all class scores (positive/neutral/negative)
subset_tycktill_df.to_excel("data/tycktill_with_sentiment.xlsx", index=False)

# ================
# make point layer

tycktill_pts_with_sentiment = gpd.GeoDataFrame(
    subset_tycktill_df, geometry=gpd.points_from_xy(
        subset_tycktill_df['Koordinater_x'],
        subset_tycktill_df['Koordinater_Y']
    ),
    crs=4326)

tycktill_pts_with_sentiment.to_file(f"{output_folder}/tycktill.gpkg", layer="tycktill_pts_with_sentiment", driver="GPKG", mode="w")
# =================================================================================================================================

