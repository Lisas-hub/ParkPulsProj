
import geopandas as gpd
import pandas as pd
import re
import numpy as np


# === prepp ===

input_gpkg_main = "data/tycktill_output/tycktill.gpkg"
input_gpkg_filtered = "data/tycktill_output/tycktill_filtered.gpkg"

base_layers = {
    "pts_in_parks": gpd.read_file(input_gpkg_main, layer="pts_in_parks"),
    "pts_with_topics": gpd.read_file(input_gpkg_main, layer="pts_with_topics"),
    "park_overlap": gpd.read_file(input_gpkg_filtered, layer="park_overlap"),
    "park_only_keywords": gpd.read_file(input_gpkg_filtered, layer="park_only_keywords"),
    "park_only_topics": gpd.read_file(input_gpkg_filtered, layer="park_only_topics"),
}

crs_ref = list(base_layers.values())[0].crs
for name, gdf in base_layers.items():
    if gdf.crs != crs_ref:
        base_layers[name] = gdf.to_crs(crs_ref)

# merge BERTopic output columns from pts_with_topics to pts_in_parks
id_col = "Ärendenummer"

bert_cols = [c for c in base_layers["pts_with_topics"].columns if c not in ["geometry", id_col]]

merged_parks = base_layers["pts_in_parks"].merge(
    base_layers["pts_with_topics"][[id_col] + bert_cols],
    on=id_col,
    how="left"
)

base_layers["pts_in_parks"] = merged_parks
print(f"Merged BERTopic info into pts_in_parks ({len(merged_parks)} rows).")

# combine all layers and track which input layer they came from
for name, gdf in base_layers.items():
    gdf["source_layer"] = name

combined = pd.concat(base_layers.values(), ignore_index=True, join="outer")



def merge_duplicate_columns(df):
    """If multiple columns have same logical name, merge into one with first non-null value."""
    new_df = pd.DataFrame(index=df.index)
    seen = set()
    for col in df.columns:
        base = col.split("_topic")[0].split(".")[0]  # strip join suffixes
        if base not in new_df.columns:
            # find all similar columns
            same_cols = [c for c in df.columns if c.split("_topic")[0].split(".")[0] == base]
            if len(same_cols) == 1:
                new_df[base] = df[same_cols[0]]
            else:
                # combine with first non-null
                new_df[base] = df[same_cols].bfill(axis=1).iloc[:, 0]
            seen.update(same_cols)
    return new_df

combined = merge_duplicate_columns(combined)





# if duplicates (same id), group them and collect layers
if id_col in combined.columns:
    layer_map = (
        combined[[id_col, "source_layer"]]
            .drop_duplicates()
            .groupby(id_col)["source_layer"]
            .agg(lambda s: ",".join(sorted(set(s))))
            .rename("source_layers")
    )

    combined = combined.drop_duplicates(subset=id_col, keep="first").merge(
        layer_map, on=id_col, how="left"
    )

else:
    # fallback if no id
    print("⚠️ No Ärendenummer found; falling back to geometry-based deduplication.")
    combined["geom_wkt"] = combined.geometry.to_wkt()
    layer_map = (
        combined[["geom_wkt", "source_layer"]]
        .drop_duplicates()
        .groupby("geom_wkt")["source_layer"]
        .agg(lambda s: ",".join(sorted(set(s))))
        .rename("source_layers")
    )
    combined = combined.drop_duplicates(subset="geom_wkt", keep="first").merge(layer_map, on="geom_wkt", how="left")
    combined = combined.drop(columns="geom_wkt")

gdf_all = gpd.GeoDataFrame(combined, geometry="geometry", crs=crs_ref)
print(f"Combined all layers: {len(gdf_all)} unique Ärendenummer and {len(gdf_all.columns)} columns.")

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

# advanced search
#def advanced_search(text, keywords, window=3):
#    """returns True if keywords or their synonyms/nearby words are found in text"""
#    text = str(text).lower()
#    words = re.findall(r"\w+", text)
#    for kw in keywords:
#        if kw in text:
#            return True
#        for i, w in enumerate(words):
#            if kw in w:
#                window_slice = words[max(0, i - window): i + window + 1]
#                if any(k in token for token in window_slice for k in keywords if k != kw):
#                    return True
#    return False

# find themes
#def find_matched_themes(text):
#    text = str(text).lower()
#    matched = []
#    for theme, words in themes.items():
#        if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words):
#            matched.append(theme)
#        elif advanced_search(text, words):
#            matched.append(theme)
#    return list(set(matched))

#gdf_all["matched_themes"] = gdf_all["clean_Fritext"].apply(find_matched_themes)
#gdf_all["theme_count"] = gdf_all["matched_themes"].apply(len)
#gdf_all["has_theme"] = gdf_all["theme_count"] > 0



text_col = "clean_Fritext"
if text_col not in gdf_all.columns:
    alt = [c for c in gdf_all.columns if "fritext" in c.lower()]
    if alt:
        text_col = alt[0]
    else:
        raise ValueError("No Fritext column found in any layer.")

gdf_all[text_col] = gdf_all[text_col].fillna("").astype(str)

# Vectorized theme search (fast)
patterns = {
    theme: re.compile("|".join(rf"\b{re.escape(w)}\w*\b" for w in words), flags=re.IGNORECASE)
    for theme, words in themes.items()
}

theme_hits = {t: gdf_all[text_col].str.contains(p, na=False) for t, p in patterns.items()}

matched_theme_lists = []
for i in range(len(gdf_all)):
    matched = [theme for theme, mask in theme_hits.items() if mask.iat[i]]
    matched_theme_lists.append(matched)

gdf_all["matched_themes"] = matched_theme_lists
gdf_all["theme_count"] = gdf_all["matched_themes"].apply(len)
gdf_all["has_theme"] = gdf_all["theme_count"] > 0

print(f"Applied theme detection: {gdf_all['has_theme'].sum()} points with themes.")





gdf_all.to_file(f"data/tycktill_output/tycktill_filtered.gpkg", layer=f"park_pts_themes", driver="GPKG", mode="w")
gdf_all.to_excel(f"data/tycktill_output/park_pts_themes.xlsx", index=False)