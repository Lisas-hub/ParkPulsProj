
# >>> STANZA NLP PIPELINE per kategori <<<

# natural language processing (NLP) packages
import nltk # has some swedish, use for stopwords and maybe more
import spacy # has swedish but maybe better suited for other types of projects than scentific ones?
import stanza # good for Swedish? uses Talbanken?

# additional/other packages
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

df = pd.read_excel("data/cleaned_dataset.xlsx")

# ============================================
# === TOKENIZE / POS-TAG / LEMMATIZE / ETC ===

# ==============
# load stopwords
stop_words = set(stopwords.words("swedish"))

# ======================
# create geometry column

df["geometry"] = df.apply(lambda row: Point(row["Koordinater_x"], row["Koordinater_Y"]), axis=1)
df_geo = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326").to_crs("EPSG:3006")

# =================================================
# prepp for filtering inside or outside parks later
parks = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

subset_within_parks = gpd.sjoin(df_geo, parks, how="inner", predicate="within")
df_geo["in_park"] = df_geo.index.isin(subset_within_parks.index)

# ============================================
# subset by parks and a limited number of rows

# subset dataset to begin with before committing to processing all 300000+ rows
kategori_filter = "Remiss skickad"
#in_park_filter = True
# ^^RERUN? Update here!^^

subset_df = df_geo[
    (df_geo["Kategori"] == kategori_filter) #&
    #(df_geo["in_park"] == in_park_filter)
].copy()

rows_before = len(subset_df)

print(f"Selected {rows_before} rows with Kategori = '{kategori_filter}' out of {len(df_geo)} total rows.")
#print(f"Selected {len(subset_df)} rows with Kategori = '{kategori_filter}' and in_park = {in_park_filter} out of {len(df_geo)} total rows.")


# =================================================================
# set up for saving figures based on number of points in the subset

output_folder = f"data/tyck_till_output/per_kategori"
os.makedirs(output_folder, exist_ok=True)

# ============
# NLP pipeline
nlp = stanza.Pipeline("sv", processors="tokenize,pos,lemma")

lemmatized_rows = []
for i, row in subset_df.iterrows():
    print(f"Processing row {i + 1} of {len(subset_df)}", flush=True)

    text = row["clean_Fritext"]

    doc = nlp(text)
    lemmas = [
        word.lemma for sentence in doc.sentences for word in sentence.words
        if word.upos != "PUNCT" and word.text.casefold() not in stop_words
    ]

    lemmatized_rows.append(lemmas)

subset_df["lemmas"] = lemmatized_rows

subset_df = subset_df[subset_df["lemmas"].astype(bool)]       # remove any now empty rows (had only stopwords and therefor empty)

rows_after = len(subset_df)
removed_rows = rows_before - rows_after

print("\n--- Filtering by municipality ---")
print(f"Removed {removed_rows} rows that were empty after stopword removal, {len(subset_df)} total rows remaining.")


# ====
# Sav

subset_df.to_excel(f"{output_folder}/tycktill_with_lemmas_{kategori_filter}.xlsx", index=False)
#subset_df.to_excel(f"{output_folder}/tycktill_with_lemmas_{kategori_filter}_in_park_{in_park_filter}.xlsx", index=False)

