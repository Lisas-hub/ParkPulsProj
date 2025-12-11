
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
# by_keyword: 26302 rows
# by_BERTopic: 60877 rows
#
# === Sentiment per layer ===
#                  pts_in_parks  by_keyword  by_BERTopic
# sentiment_label
# NEUTRAL                 51603       15416        43400
# NEGATIVE                26316       10617        16903
# POSITIVE                  535         269          574
# === ROW COUNTS PER LAYER BEFORE COMBINING ===
# pts_in_parks: 78454 rows
# by_keyword: 26302 rows
# by_BERTopic: 60877 rows
#
# === AFTER CONCATENATION ===
# Total rows (raw combined): 165633
#
# Rows per single-layer source_filter BEFORE grouping by Ärendenummer:
# source_filter
# pts_in_parks    78454
# by_BERTopic     60877
# by_keyword      26302
# Name: count, dtype: int64
#
# === AFTER GROUPING/DEDUPLICATION ===
# Total unique Ärendenummer: 118572
#
# Rows per source_filter combination AFTER grouping:
# source_filter
# pts_in_parks                             43517
# by_BERTopic                              31602
# by_BERTopic; pts_in_parks                17159
# by_BERTopic; by_keyword; pts_in_parks     9071
# by_keyword; pts_in_parks                  8679
# by_keyword                                5511
# by_BERTopic; by_keyword                   3033
# Name: count, dtype: int64
#
# === Theme: safety ===
# Rows with 'safety' in themes: 5264
# source_filter    by_BERTopic  by_keyword  pts_in_parks
# sentiment_label
# NEGATIVE                1370        1400          2532
# NEUTRAL                  517         524          1197
# POSITIVE                  13           8            14
#
# === Theme: illumination ===
# Rows with 'illumination' in themes: 10029
# source_filter    by_BERTopic  by_keyword  pts_in_parks
# sentiment_label
# NEGATIVE                1027        1062          2872
# NEUTRAL                 1659        1506          5244
# POSITIVE                  34          28            45
#
# === Theme: praise ===
# Rows with 'praise' in themes: 382
# source_filter    by_BERTopic  by_keyword  pts_in_parks
# sentiment_label
# NEGATIVE                  39          45            64
# NEUTRAL                   35          46            69
# POSITIVE                  89          74           107
#
# Saved combined dataset with themes:
#  - data/tycktill_output/BERTopic_filtered\all_park_related_pts_with_themes.xlsx
#  - data/tycktill_output/BERTopic_filtered\tycktill_filtered.gpkg
#
# Theme counts:
#  themes
# maintenance                   28764
# cleanliness                   25876
# vandalism/damages             25835
# nature/biodiversity           14813
# illumination                  10029
# traffic/transport planning     6868
# safety                         5264
# illegal parking                5093
# snow clearing                  4441
# noise                           868
# accessibility                   622
# drugs/alcohol                   601
# praise                          382
# socialising                     199
# Name: count, dtype: int64
#
# Process finished with exit code 0