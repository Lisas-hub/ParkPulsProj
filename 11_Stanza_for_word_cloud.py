

# >>> STANZA NLP PIPELINE <<<

import stanza
import pandas as pd
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

tycktill_filtered_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg"
df = gpd.read_file(tycktill_filtered_GPKG, layer="all_park_related_pts_with_themes")

# ============================================
# === TOKENIZE / POS-TAG / LEMMATIZE / ETC ===

# ==============
# load stopwords
stop_words = set(stopwords.words("swedish"))

# ===============================
# subset a limited number of rows

#df = df.sample(3000, random_state=42)

rows_before = len(df)

# =================================================================
# set up for saving figures based on number of points in the subset

output_folder = f"data/tycktill_output/STANZA_for_word_cloud"
os.makedirs(output_folder, exist_ok=True)

# ============
# NLP pipeline
nlp = stanza.Pipeline("sv", processors="tokenize,pos,lemma")

lemmatized_rows = []
for i, row in df.iterrows():
    print(f"Processing row {i + 1} of {len(df)}", flush=True)

    text = row["clean_Fritext"]

    doc = nlp(text)
    lemmas = [
        word.lemma for sentence in doc.sentences for word in sentence.words
        if word.upos != "PUNCT" and word.text.casefold() not in stop_words
    ]

    lemmatized_rows.append(lemmas)

df["lemmas"] = lemmatized_rows

df = df[df["lemmas"].astype(bool)]       # remove any now empty rows (had only stopwords and therefor empty)

rows_after = len(df)
removed_rows = rows_before - rows_after

print("\n--- Filtering by municipality ---")
print(f"Removed {removed_rows} rows that were empty after stopword removal, {len(df)} total rows remaining.")


# ====
# Save

df.to_file(f"{output_folder}/STANZA_output.gpkg", layer="all_park_related_pts_with_themes_AND_STANZA", driver="GPKG", mode="w")


# --- Filtering by municipality ---
# Removed 16 rows that were empty after stopword removal, 118556 total rows remaining.