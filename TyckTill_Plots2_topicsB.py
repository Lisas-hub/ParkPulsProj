
import geopandas as gpd
import pandas as pd
import re


 # === prepp ===

input_gpkg1 = gpd.read_file("data/tycktill_output/tycktill.gpkg", layer="pts_in_parks")

input_gpkg2 = "data/tycktill_output/tycktill_filtered.gpkg"

layers_to_load = ["park_overlap", "park_only_keywords", "park_only_topics"]

gdfs = {}
for layer in layers_to_load:
    gdfs[layer] = gpd.read_file(input_gpkg2, layer=layer)
    print(f"Loaded {layer}: {len(gdfs[layer])} rows")

themes = {
    "safety": ["säkerhet", "trygg", "otrygg", "farligt"],
    "accessibility": ["rullstol", "tillgänglig"],
    "cleanliness": ["skräp", "sopor", "rent", "smutsigt", "klotter"],
    #"maintenance": ["trasig", "reparera", "sliten", "underhåll", "fixa"],
    "noise": ["ljud", "buller", "högljutt", "tyst"]
}

# === find themes ===
def find_matched_themes(text):
    """Return list of themes matched in text."""
    text = str(text).lower()
    matched = []
    for theme, words in themes.items():
        if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words):
            matched.append(theme)
    return matched

for name, gdf in gdfs.items():
    gdf["matched_themes"] = gdf["clean_Fritext"].apply(find_matched_themes)
    gdf["theme_count"] = gdf["matched_themes"].apply(len)
    gdf["has_theme"] = gdf["theme_count"] > 0