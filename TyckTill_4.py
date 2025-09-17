
# natural language processing (NLP) packages
import nltk # has some swedish, use for stopwords and maybe more
import spacy # has swedish but maybe better suited for other types of projects than scentific ones?
import stanza # good for Swedish? uses Talbanken?

# other packages
import pandas as pd
import numpy as np
import geopandas as gpd
import folium
import matplotlib.pyplot as plt

# downloads
#nltk.download('punkt')
#nltk.download('stopwords')
#stanza.download('sv')

# other
from nltk.corpus import stopwords


tycktill_df = pd.read_excel(r'C:\Users\lisajos\QGIS_Projects\TyckTill\NEW\TyckTill_2023-01-01_2024-12-31.xlsx')

# ============================================
# === PRE PROCESSING OF ADDITIONAL COLUMNS ===

# =========
# Kategori

# nothing to fix

# =====================================
# date and time column (Inkommet datum)

# convert to appropriate datetime format
tycktill_df["Inkommet datum"] = pd.to_datetime(tycktill_df["Inkommet datum"], errors="coerce")

# extract date (or time) only
tycktill_df["year"] = tycktill_df["Inkommet datum"].dt.year
tycktill_df["month"] = tycktill_df["Inkommet datum"].dt.month
tycktill_df["weekday"] = tycktill_df["Inkommet datum"].dt.day_name()

# ===========
# coordinates

# handle 0 and null
tycktill_df["Koordinater_x"] = tycktill_df["Koordinater_x"].replace(0, np.nan)
tycktill_df["Koordinater_Y"] = tycktill_df["Koordinater_Y"].replace(0, np.nan)

# =================================
# === PRE PROCESSING OF FRITEXT ===

# FILTERING (removing rows that don't need to be included)

# keep rows that have something in them + remove empty space in the beginning or end of cells and remove any rows that don't have anything left after this
tycktill_df = tycktill_df[tycktill_df["Fritext"].notna() & tycktill_df["Fritext"].str.strip().ne("")]

# remove rows with numbers or symbols (incl emojis) and no text, in other words remove all rows without at least one letter
import re
tycktill_df = tycktill_df[tycktill_df["Fritext"].apply(lambda x: re.search(r"[a-zA-ZåäöÅÄÖ]", str(x)) is not None)]

# make all text lowercase
tycktill_df["clean_Fritext"] = tycktill_df["Fritext"].str.lower()

# clean up text that includes certain symbols or emojis by removing them but keeping the text
tycktill_df["clean_Fritext"] = tycktill_df["clean_Fritext"].str.replace(r"[^a-zA-ZåäöÅÄÖ0-9\s]", "", regex=True)

tycktill_df.to_excel("data/cleaned_dataset.xlsx")

# ============================================
# === TOKENIZE / POS-TAG / LEMMATIZE / ETC ===

# load stopwords
stop_words = set(stopwords.words("swedish"))

# subset tycktill dataset to begin with before committing to processing all 300000+ rows
tycktill_df_subset = tycktill_df.head(50).copy()

nlp = stanza.Pipeline("sv", processors="tokenize,pos,lemma")

def lemmatize_text(text):
    doc = nlp(text)
    lemmas = [
        word.lemma for sentence in doc.sentences for word in sentence.words
        if word.upos != "PUNCT" and word.text.casefold() not in stop_words
    ]
    return lemmas

tycktill_df_subset["lemmas"] = tycktill_df_subset["clean_Fritext"].apply(lemmatize_text)



# =======================