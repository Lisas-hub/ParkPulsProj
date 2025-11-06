
import os
import re
import pandas as pd
import geopandas as gpd


input_folder = "data/tycktill_output/BERTopic_filtered"
output_file_excel = os.path.join(input_folder, "all_park_related_pts_with_themes.xlsx")
output_file_gpkg = os.path.join(input_folder, "tycktill_filtered.gpkg")

layers = {
    "pts_in_parks": "pts_in_parks_with_topics",
    "by_keyword": "park_comments_by_keyword",
    "by_BERTopic": "park_comments_by_BERTopic"
}

dfs = {}
for name, layer in layers.items():
    print(f"Loading layer: {layer}")
    gdf = gpd.read_file(f"{input_folder}/tycktill_filtered.gpkg", layer=layer)
    gdf = gdf.to_crs(4326)                                                             # change to crs 3006 ??
    gdf["source_filter"] = name
    dfs[name] = gdf

combined = pd.concat(dfs.values(), ignore_index=True)

grouped = (
    combined.groupby("Ärendenummer")
    .agg({
        **{col: "first" for col in combined.columns if col not in ["source_filter", "Ärendenummer"]},
        "source_filter": lambda x: "; ".join(sorted(set(x)))
    })
    .reset_index()
)

print(f"Combined and deduplicated: {len(grouped)} unique comments")


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

# regex for each theme
theme_patterns = {
    theme: re.compile(
        r"\b(" + "|".join(map(re.escape, words)) + r")\b", flags=re.IGNORECASE
    )
    for theme, words in themes.items()
}

# search for themes
def find_themes(text):
    """Return list of theme names found in a comment."""
    text = str(text)
    matched = [theme for theme, pattern in theme_patterns.items() if pattern.search(text)]
    return "; ".join(matched) if matched else None

grouped["themes"] = grouped["clean_Fritext"].apply(find_themes)


#save
gdf_combined = gpd.GeoDataFrame(
    grouped,
    geometry=gpd.points_from_xy(grouped["Koordinater_x"], grouped["Koordinater_Y"]),
    crs=4326
)
gdf_combined.to_excel(output_file_excel, index=False)
gdf_combined.to_file(output_file_gpkg, layer="all_park_related_pts_with_themes", driver="GPKG", mode="w")

print(f"\nSaved combined dataset with themes:")
print(f" - {output_file_excel}")
print(f" - {output_file_gpkg}")

# summary
theme_counts = grouped["themes"].dropna().str.split("; ").explode().value_counts()
print("\nTheme counts:\n", theme_counts)