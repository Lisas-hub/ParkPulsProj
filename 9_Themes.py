
import os
import re
import pandas as pd
import geopandas as gpd



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

sentiment_tables = {}

for name, layer in layers.items():
    gdf = gpd.read_file(f"{input_folder}/tycktill_filtered.gpkg", layer=layer)
    gdf = gdf.to_crs(4326)
    gdf["source_filter"] = name
    dfs[name] = gdf

    print(f"{name}: {len(gdf)} rows")

    # Count sentiment per layer
    sentiment_tables[name] = gdf["sentiment_label"].value_counts().rename(name)

sentiment_df = pd.concat(sentiment_tables.values(), axis=1).fillna(0).astype(int)

print("\n=== Sentiment per layer ===")
print(sentiment_df)

print("=== ROW COUNTS PER LAYER BEFORE COMBINING ===")
for name, layer in layers.items():
    gdf = gpd.read_file(f"{input_folder}/tycktill_filtered.gpkg", layer=layer)
    gdf = gdf.to_crs(4326)                                                             # change to crs 3006 ??
    gdf["source_filter"] = name
    dfs[name] = gdf

    print(f"{name}: {len(gdf)} rows")

combined = pd.concat(dfs.values(), ignore_index=True)

print("\n=== AFTER CONCATENATION ===")
print(f"Total rows (raw combined): {len(combined)}")

print("\nRows per single-layer source_filter BEFORE grouping by Ärendenummer:")
print(combined["source_filter"].value_counts())

grouped = (
    combined.groupby("Ärendenummer")
    .agg({
        **{col: "first" for col in combined.columns if col not in ["source_filter", "Ärendenummer"]},
        "source_filter": lambda x: "; ".join(sorted(set(x)))
    })
    .reset_index()
)

print("\n=== AFTER GROUPING/DEDUPLICATION ===")
print(f"Total unique Ärendenummer: {len(grouped)}")

print("\nRows per source_filter combination AFTER grouping:")
print(grouped["source_filter"].value_counts())

themes = {
    "safety": ["säkerhet", "trygg", "otrygg", "farlig", "rädd", "olyck", "risk", "otäck"],
    "accessibility": ["rullstol", "tillgänglig", "rörelsehindrad", "rullator", "permobil"],
    "cleanliness": ["skräp", "ren", "smutsig", "skräpigt", "nedskräpning", "sop", "sophög",
                    "papperskorg", "papperskorgens", "skräpkorg", "soptunn", "sopkärl",
                    "skrot", "grovsop", "bråte", "byggavfall", "big bag", "byggsäck",
                    "bajs", "människobajs", "avföring", "fekalier", "kiss", "piss", "hundbajs", "kattbajs",
                    "råttor", "blod", "kasta"],
    "vandalism/damages": ["klott", "klottra", "hatklott", "graffiti", "klistermärke", "skadegörelse", "vandalism",
                          "glas", "glassplitt", "glasbit", "glaskross",
                          "nedbrunn", "utbränd"],
    "maintenance": ["trasig", "reparera", "fixa", "laga", "saner", "åtgärd",
                    "slit", "underhåll", "misskött", "sönder", "lossna",
                    "städ", "röj", "klipp", "trimma", "beskär",
                    "vattenläck", "läck", "läckage"],
    "noise": ["ljud", "buller", "högljutt", "högljudd", "tyst", "hög musik", "oljud"],
    "nature/biodiversity": ["natur", "invasiv", "biodiersitet", "blomm", "parkslide", "träd", "busk",
                            "djur", "rådjur", "bäver", "räv", "fågel", "hare", "groddamm", "grod", "skabb"],
    "illumination": ["belysning", "mörk", "lyktstolp", "gatulamp", "lamp", "lys", "belysingsstolpe", "belysningsstolpar",
                     "armatur", "belysningsarmatur", "gatubelysning"],
    "socialising": ["umgås", "vänner", "familj"],
    "drugs/alcohol": ["kanyl", "drog", "missbruk", "alkohol", "droghandel", "knarkhandel", "marijuana", "joint"],
    "illegal parking": ["felparkering", "felparker", "stående", "övergiv", "parkeringsböt", "parkeringsförbud"],
    "praise": ["beröm", "underbar", "fantastisk"], # tog bort tack (folk skriver ju tack även i slutet på meddelanden)
    "traffic/transport planning": ["trafik", "cykelväg", "cykelbana", "körbana", "högtrafikerad"],
    "snow clearing": ["snö", "snöröj", "snöröjd", "plog", "oplog", "skotta", "snö", "sanda"]
}

# nämns också en del om tält-/boplatser i skogen, men har inte lagt till det någonstans
# båt-relaterat

# GÖR EN SÖKNING MED ORDEN I FRITEXT OCH EN I TOPIC_KEYWORDS

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
def find_themes_and_sources(fritext, keywords):
    """
    Returns:
        themes_str (str or None): "safety; cleanliness"
        sources_str (str or None): "clean_Fritext; topic_keywords"
    """

    fritext = str(fritext)
    keywords = str(keywords)

    themes_found = []
    sources = set()

    # Search both fields
    for theme, pattern in theme_patterns.items():
        found_in_fritext = bool(pattern.search(fritext))
        found_in_keywords = bool(pattern.search(keywords))

        if found_in_fritext or found_in_keywords:
            themes_found.append(theme)

            if found_in_fritext:
                sources.add("clean_Fritext")
            if found_in_keywords:
                sources.add("topic_keywords")

    themes_str = "; ".join(themes_found) if themes_found else None
    sources_str = "; ".join(sorted(sources)) if sources else None

    return themes_str, sources_str

grouped[["themes", "theme_sources"]] = grouped.apply(
    lambda row: pd.Series(find_themes_and_sources(row["clean_Fritext"], row["topic_keywords"])),
    axis=1
)

# === count theme occurences ===
themes_to_check = ["safety", "illumination", "praise"]

for theme in themes_to_check:
    # filter rows where the theme occurs
    mask = grouped["themes"].notna() & grouped["themes"].str.contains(rf"\b{theme}\b", case=False)
    subset = grouped[mask]

    print(f"\n=== Theme: {theme} ===")
    print(f"Rows with '{theme}' in themes: {len(subset)}")

    if len(subset) == 0:
        print("No rows for this theme.\n")
        continue

    # split and explode source_filter
    exploded = (
        subset
            .assign(source_filter=subset["source_filter"].str.split("; "))
            .explode("source_filter")
    )

    # pivot table
    table = (
        exploded
            .pivot_table(
            index="sentiment_label",
            columns="source_filter",
            aggfunc="size",
            fill_value=0
        )
            .reindex(columns=["by_BERTopic", "by_keyword", "pts_in_parks"], fill_value=0)
            .astype(int)
    )

    print(table)


# === save ===
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





# pts_in_parks: 78347 rows
# by_keyword: 26089 rows
# by_BERTopic: 56879 rows
#
# === Sentiment per layer ===
#                  pts_in_parks  by_keyword  by_BERTopic
# sentiment_label
# NEUTRAL                 51396       15260        40674
# NEGATIVE                26400       10536        15566
# POSITIVE                  551         293          639

# === ROW COUNTS PER LAYER BEFORE COMBINING ===
# pts_in_parks: 78347 rows
# by_keyword: 26089 rows
# by_BERTopic: 56879 rows
#
# === AFTER CONCATENATION ===
# Total rows (raw combined): 161315
#
# Rows per single-layer source_filter BEFORE grouping by Ärendenummer:
# source_filter
# pts_in_parks    78347
# by_BERTopic     56879
# by_keyword      26089
# Name: count, dtype: int64
#
# === AFTER GROUPING/DEDUPLICATION ===
# Total unique Ärendenummer: 114675
#
# Rows per source_filter combination AFTER grouping:
# source_filter
# pts_in_parks                             43920
# by_BERTopic                              27586
# by_BERTopic; pts_in_parks                17092
# by_BERTopic; by_keyword; pts_in_parks     9053
# by_keyword; pts_in_parks                  8254
# by_keyword                                5628
# by_BERTopic; by_keyword                   3142
# Name: count, dtype: int64
#
# Saved combined dataset with themes:
#  - data/tycktill_output/BERTopic_filtered\all_park_related_pts_with_themes.xlsx
#  - data/tycktill_output/BERTopic_filtered\tycktill_filtered.gpkg
#
# Theme counts:
#  themes
# cleanliness                   27041
# vandalism/damages             26010
# maintenance                   22001
# nature/biodiversity           17021
# illumination                   9144
# traffic/transport planning     7378
# safety                         5100
# illegal parking                4144
# snow clearing                  3481
# noise                           921
# accessibility                   604
# drugs/alcohol                   600
# praise                          423
# socialising                     201
# Name: count, dtype: int64