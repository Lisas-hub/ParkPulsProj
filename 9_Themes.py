
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



# pts_in_parks: 78454 rows
# by_keyword: 26118 rows
# by_BERTopic: 60011 rows
#
# === Sentiment per layer ===
#                  pts_in_parks  by_keyword  by_BERTopic
# sentiment_label
# NEUTRAL                 51603       15306        42887
# NEGATIVE                26316       10544        16544
# POSITIVE                  535         268          580
# === ROW COUNTS PER LAYER BEFORE COMBINING ===
# pts_in_parks: 78454 rows
# by_keyword: 26118 rows
# by_BERTopic: 60011 rows
#
# === AFTER CONCATENATION ===
# Total rows (raw combined): 164583
#
# Rows per single-layer source_filter BEFORE grouping by Ärendenummer:
# source_filter
# pts_in_parks    78454
# by_BERTopic     60011
# by_keyword      26118
# Name: count, dtype: int64
#
# === AFTER GROUPING/DEDUPLICATION ===
# Total unique Ärendenummer: 118115
#
# Rows per source_filter combination AFTER grouping:
# source_filter
# pts_in_parks                             43764
# by_BERTopic                              31204
# by_BERTopic; pts_in_parks                17037
# by_BERTopic; by_keyword; pts_in_parks     8824
# by_keyword; pts_in_parks                  8801
# by_keyword                                5551
# by_BERTopic; by_keyword                   2934
# Name: count, dtype: int64
#
# === Theme: safety ===
# Rows with 'safety' in themes: 5222
# source_filter    by_BERTopic  by_keyword  pts_in_parks
# sentiment_label
# NEGATIVE                1301        1393          2532
# NEUTRAL                  504         523          1197
# POSITIVE                  12           8            14
#
# === Theme: illumination ===
# Rows with 'illumination' in themes: 9638
# source_filter    by_BERTopic  by_keyword  pts_in_parks
# sentiment_label
# NEGATIVE                 889        1059          2872
# NEUTRAL                 1195        1498          5244
# POSITIVE                  29          28            45
#
# === Theme: praise ===
# Rows with 'praise' in themes: 383
# source_filter    by_BERTopic  by_keyword  pts_in_parks
# sentiment_label
# NEGATIVE                  40          45            64
# NEUTRAL                   35          44            69
# POSITIVE                  90          74           107
#
# Saved combined dataset with themes:
#  - data/tycktill_output/BERTopic_filtered\all_park_related_pts_with_themes.xlsx
#  - data/tycktill_output/BERTopic_filtered\tycktill_filtered.gpkg
#
# Theme counts:
#  themes
# maintenance                   28577
# cleanliness                   25824
# vandalism/damages             25803
# nature/biodiversity           15014
# illumination                   9638
# traffic/transport planning     6851
# safety                         5222
# illegal parking                5076
# snow clearing                  4444
# noise                           865
# accessibility                   620
# drugs/alcohol                   598
# praise                          383
# socialising                     199
# Name: count, dtype: int64
#
# Process finished with exit code 0


# OLD:
# pts_in_parks: 78454 rows
# by_keyword: 25574 rows
# by_BERTopic: 58809 rows
#
# === Sentiment per layer ===
#                  pts_in_parks  by_keyword  by_BERTopic
# sentiment_label
# NEUTRAL                 51603       15004        42156
# NEGATIVE                26316       10306        16098
# POSITIVE                  535         264          555
# === ROW COUNTS PER LAYER BEFORE COMBINING ===
# pts_in_parks: 78454 rows
# by_keyword: 25574 rows
# by_BERTopic: 58809 rows
#
# === AFTER CONCATENATION ===
# Total rows (raw combined): 162837
#
# Rows per single-layer source_filter BEFORE grouping by Ärendenummer:
# source_filter
# pts_in_parks    78454
# by_BERTopic     58809
# by_keyword      25574
# Name: count, dtype: int64
#
# === AFTER GROUPING/DEDUPLICATION ===
# Total unique Ärendenummer: 117217
#
# Rows per source_filter combination AFTER grouping:
# source_filter
# pts_in_parks                             44286
# by_BERTopic                              30475
# by_BERTopic; pts_in_parks                16890
# by_keyword; pts_in_parks                  8665
# by_BERTopic; by_keyword; pts_in_parks     8585
# by_keyword                                5469
# by_BERTopic; by_keyword                   2847
# Name: count, dtype: int64
#
# === Theme: safety ===
# Rows with 'safety' in themes: 5179
# source_filter    by_BERTopic  by_keyword  pts_in_parks
# sentiment_label
# NEGATIVE                1259        1364          2532
# NEUTRAL                  493         512          1197
# POSITIVE                  12           8            14
#
# === Theme: illumination ===
# Rows with 'illumination' in themes: 8204
# source_filter    by_BERTopic  by_keyword  pts_in_parks
# sentiment_label
# NEGATIVE                 871        1047          2841
# NEUTRAL                 1189        1481          3863
# POSITIVE                  29          28            44
#
# === Theme: praise ===
# Rows with 'praise' in themes: 376
# source_filter    by_BERTopic  by_keyword  pts_in_parks
# sentiment_label
# NEGATIVE                  37          43            64
# NEUTRAL                   33          42            69
# POSITIVE                  88          73           107
#
# Saved combined dataset with themes:
#  - data/tycktill_output/BERTopic_filtered\all_park_related_pts_with_themes.xlsx
#  - data/tycktill_output/BERTopic_filtered\tycktill_filtered.gpkg
#
# Theme counts:
#  themes
# maintenance                   27547
# cleanliness                   24892
# vandalism/damages             24425
# nature/biodiversity           13748
# illumination                   8204
# traffic/transport planning     6744
# safety                         5179
# illegal parking                4768
# snow clearing                  4422
# noise                           858
# accessibility                   614
# drugs/alcohol                   595
# praise                          376
# socialising                     196
# Name: count, dtype: int64
#
# Process finished with exit code 0