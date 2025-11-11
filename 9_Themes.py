
import os
import re
import pandas as pd
import geopandas as gpd


# TO DO
# search only praise category (in parks) - what are people saying?


# prepp
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
    #print(f"Loading layer: {layer}")
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
    "safety": ["säkerhet", "trygg", "otrygg", "farlig", "rädd", "olyck"], # olyckor plockades inte upp så fixa med varsioner av samma ord
    "accessibility": ["rullstol", "tillgänglig", "rörelsehindrad", "rullator", "permobil"],
    "cleanliness": ["skräp", "sop", "ren", "smutsigt", "papperskorg", "skräpkorg", "nedskräpning", "soptunn", "byggsäck", "råttor"],
    "vandalism/damages": ["klott", "skadegörelse", "vandalism", "glas", "glassplitt", "glasbit"],                                      # lägg till brand/eld?
    "maintenance": ["trasig", "reparera", "slit", "underhåll", "fixa", "laga", "misskött", "saner", "åtgärd"], # trasigt plockades inte upp
    "noise": ["ljud", "buller", "högljutt", "högljudd", "tyst", "hög musik", "oljud"],
    "nature/biodiversity": ["natur", "invasiv", "biodiersitet", "djur", "blomm", "parkslide"],
    "illumination": ["belysning", "mörk", "lyktstolp", "gatulamp", "lamp", "lys", "belysingsstolpe"],
    "socialising": ["umgås", "vänner", "familj"],
    "drugs/alcohol": ["kanyl", "drog", "missbruk", "alkohol", "droghandel", "marijuana", "joint"],
    "illegal parking": ["felparkering", "felparker", "stående", "övergiv", "parkeringsböt"],
    "praise": ["tack", "underbar", "fantastisk"]                                                           # ta bort? folk skriver ju tack även i slutet på meddelanden
}

swedish_endings = (r"(t|a|an|en|et|ar|er|or|na|n|s|as|at|ad|ade|ats|arna|erna|orna|arnas|ernas|ornas|ing|ingar|ande|ande|ning|ningar)?")

# regex for each theme
theme_patterns = {
    theme: re.compile(
        r"\b(" + "|".join(
            rf"{re.escape(word)}{swedish_endings}" for word in words
        ) + r")\b",
        flags=re.IGNORECASE
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
gdf_combined.to_file(output_file_gpkg, layer="all_park_related_pts_with_themes", driver="GPKG", mode="w")
gdf_combined.drop(columns="geometry").to_excel(output_file_excel, index=False)

print(f"\nSaved combined dataset with themes:")
print(f" - {output_file_excel}")
print(f" - {output_file_gpkg}")

# summary
theme_counts = grouped["themes"].dropna().str.split("; ").explode().value_counts()
print("\nTheme counts:\n", theme_counts)