
import geopandas as gpd
import pandas as pd
import re
import numpy as np


main_gpkg = "data/tycktill_output/tycktill.gpkg"
filtered_gpkg = "data/tycktill_output/tycktill_filtered.gpkg"

# load main_gpkg layers
pts_in_parks = gpd.read_file(main_gpkg, layer="pts_in_parks")
pts_with_topics = gpd.read_file(main_gpkg, layer="pts_with_topics")

# convert Ärendenummer
pts_in_parks["Ärendenummer"] = pts_in_parks["Ärendenummer"].astype(str)
pts_with_topics["Ärendenummer"] = pts_with_topics["Ärendenummer"].astype(str)

#print(pts_in_parks.columns)
#print(pts_with_topics.columns)

# specify and merge new columns
topic_cols = ["Ärendenummer", "clean_Fritext", "sentiment_label", "sentiment_score", "sentiment_all", "topic", "topic_prob", "topic_keywords"]
pts_topics_subset = pts_with_topics[topic_cols]

merged = pts_in_parks.merge(pts_topics_subset, on="Ärendenummer", how="inner", sort=False)
#print(merged.columns)

# drop rows that are not one of the main 4 (ex Fråga, Remiss skickad, etc)
valid_categories = ["Klagomål", "Beröm", "Idé", "Felanmälan"]
base = merged[merged["Kategori"].isin(valid_categories)]
base["source_layer"] = "base"

base.to_file(filtered_gpkg, layer="TEST1", driver="GPKG", mode="w")
base.to_excel(f"data/tycktill_output/TEST1.xlsx", index=False)



# OLD
# ==========================================================
# === add sentiment and BERTopic columns to pts_in_parks ===

# drop geometry in pts_with_topics
#pts_topics_subset = pts_with_topics.drop(columns="geometry")







# load filtered_gpkg layers + drop geometries
layer_names = ["park_overlap", "park_only_keywords", "park_only_topics"]
layers = {}
for name in layer_names:
    df = gpd.read_file(filtered_gpkg, layer=name).drop(columns="geometry")
    df["Ärendenummer"] = df["Ärendenummer"].astype(str).str.strip()
    df["source_layer"] = name
    layers[name] = df

others_combined = pd.concat(layers.values(), ignore_index=True)


combined = pd.concat([base.drop(columns="geometry", errors="ignore"), others_combined], ignore_index=True)



# track what input layer a point belongs to
layer_map = (
    combined.groupby("Ärendenummer")["source_layer"]
    .agg(lambda x: ",".join(sorted(set(x))))
    .reset_index()
    .rename(columns={"source_layer": "found_in_layers"})
)

final = combined.merge(layer_map, on="Ärendenummer", how="left")


#merged1 = base.merge(layer_map, on="Ärendenummer", how="left")
#merged1["found_in_layers"] = merged1["found_in_layers"].fillna("none")


# Combine clean_Fritext_x and clean_Fritext_y safely
if "clean_Fritext_x" in final.columns and "clean_Fritext_y" in final.columns:
    # Prefer _x if it exists, otherwise use _y
    final["clean_Fritext"] = final["clean_Fritext_x"].combine_first(final["clean_Fritext_y"])
    # Drop the old columns
    final = final.drop(columns=["clean_Fritext_x", "clean_Fritext_y"])
elif "clean_Fritext_y" in final.columns:
    final = final.rename(columns={"clean_Fritext_y": "clean_Fritext"})
elif "clean_Fritext_x" in final.columns:
    final = final.rename(columns={"clean_Fritext_x": "clean_Fritext"})



final.to_excel(f"data/tycktill_output/TEST2.xlsx", index=False)


# *** NU FUNKAR DET SOM JAG VILL ***
# men alla base rows saknar data i kolumner som fylldes på i ett tidigare steg??? så ändra ordningen



themes = {
    "safety": ["säkerhet", "trygg", "otrygg", "farlig", "rädd", "olycka"], # olyckor plockades inte upp så fixa med varsioner av samma ord
    "accessibility": ["rullstol", "tillgänglig", "rörelsehindrad", "rullator", "permobil"],
    "cleanliness": ["skräp", "sopor", "rent", "smutsigt", "papperskorg", "skräpkorg", "nedskräpning", "soptunna", "byggsäck"],
    "vandalism/damages": ["klotter", "skadegörelse", "vandalism", "glas", "glassplitter"],                                      # lägg till brand/eld?
    "maintenance": ["trasig", "reparera", "sliten", "underhåll", "fixa", "laga", "misskött", "sanera"],
    "noise": ["ljud", "buller", "högljutt", "tyst", "hög musik", "oljud"],
    "nature/biodiversity": ["natur", "invasiv", "biodiersitet", "djur", "blommor", "parkslide"],
    "illumination": ["belysning", "mörkt", "lyktstolpe", "gatulampa"],
    "socialising": ["umgås", "vänner", "familj"],
    "drugs/alcohol": ["kanyl", "droger", "missbruk", "alkohol", "droghandel", "marijuana", "joint"],
    "illegal parking": ["felparkering", "felparkerad", "stående", "övergiven", "parkeringsböter"]
}

theme_patterns = {
    theme: re.compile(r"\b(" + "|".join(map(re.escape, words)) + r")\b", re.IGNORECASE)
    for theme, words in themes.items()
}

def detect_themes(text):
    if not isinstance(text, str) or not text.strip():
        return ""
    found = [theme for theme, pattern in theme_patterns.items() if pattern.search(text)]
    return ",".join(found) if found else ""

final["themes_found"] = final["clean_Fritext"].apply(detect_themes)

final.drop(columns="geometry").to_excel(f"data/tycktill_output/TEST3.xlsx", index=False)   # detta alt droppar geometri innan save (borde gå snabbare)
#final.to_excel(f"data/tycktill_output/TEST3.xlsx", index=False)


