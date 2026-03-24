
import geopandas as gpd
import pandas as pd
import os

# TO DO
# add topic/sentiment columns?
# add protected areas columns that are count or area
# add public transport count or similar
# add distance to city center

###########
# might need to join other layers to this one to get like meta topics, themes or whatever
# calculate number or proportion of pts within the park polygons (VARIABLES_) per sentiment, kategori, ...
# spara ett lager med en rad för varje park och ett lager med en rad för varje punkt? (i den senare kan alltså park id förekomma mer än en gång)
###########

VARIABLES_GPKG_PATH = "data/VARIABLES_NEW.gpkg"
TYCKTILL_FILTERED_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg"

POINT_LAYER = "pts_in_parks_with_topics" # (has sentiment and topic columns and kategori (Beröm, Idé, Felanmälan, Klagomål)

POLYGON_LAYERS = [
    "VARIABLES_base",
    "VARIABLES_accessibility_NEW",
    "VARIABLES_amenities_NEW",
    "VARIABLES_environment",
    #"VARIABLES_food",               # not relevant anymore, handled within VARIABLES_amenities
    #"VARIABLES_noise_pollution",    # not relevant anymore, handled within VARIABLES_environment
    "VARIABLES_safety_NEW",
    "VARIABLES_socioeconomic_NEW",
    #"VARIABLES_typology"            # not relevant anymore, handled within VARIABLES_amenities
]

ID_COL = "group"

OUTPUT_PATH = "data/regression_output"
os.makedirs(OUTPUT_PATH, exist_ok=True)

OUTPUT_FILE = f"{OUTPUT_PATH}/VARIABLES_regression.gpkg"

SHARED_COLS = [ID_COL, "NAMN_combined", "NAMN_top5", "stadsdelar", "stadsdelsomraden", "park_area", "MOUSEOVER_combined"]

category_map = {
    "praise": ["Beröm"],
    "idea": ["Idé"],
    "error_complaint": ["Felanmälan", "Klagomål"]
}

# ========
# POLYGONS

# load polygon layers

parks = gpd.read_file(VARIABLES_GPKG_PATH, layer=POLYGON_LAYERS[0])
parks = parks[SHARED_COLS + ["geometry"]]   # keep only needed shared columns + geometry
merged = parks.copy()

for layer in POLYGON_LAYERS[1:]:
    gdf = gpd.read_file(VARIABLES_GPKG_PATH, layer=layer)

    # drop geometry
    gdf = gdf.drop(columns="geometry")

    # drop shared columns except ID
    cols_to_drop = [c for c in SHARED_COLS if c != ID_COL and c in gdf.columns]
    gdf = gdf.drop(columns=cols_to_drop)

    # temporarily rename ID to avoid duplicates
    gdf = gdf.rename(columns={ID_COL: f"{ID_COL}_tmp"})

    # merge
    merged = pd.merge(
        merged,
        gdf,
        left_on=ID_COL,
        right_on=f"{ID_COL}_tmp",
        how="left",
        validate="one_to_one"
    ).drop(columns=f"{ID_COL}_tmp")

merged = gpd.GeoDataFrame(merged, geometry="geometry", crs=parks.crs)

# ======
# POINTS

points = gpd.read_file(TYCKTILL_FILTERED_GPKG, layer=POINT_LAYER)
points = points.to_crs(merged.crs)

# map original Kategori to grouped categories
def map_category(kategori):
    for group, originals in category_map.items():
        if kategori in originals:
            return group
    return "other"  # optional fallback

points["category_group"] = points["Kategori"].apply(map_category)

# ============
# SPATIAL JOIN

# drop conflicting columns
for col in ["index_left", "index_right"]:
    if col in points.columns:
        points = points.drop(columns=col)

points = points.reset_index(drop=True)
merged = merged.reset_index(drop=True)

park_lookup = merged[[ID_COL]].reset_index()

if ID_COL in points.columns:
    points = points.drop(columns=ID_COL)

# spatial join (geometry only)
points_in_parks = gpd.sjoin(
    points,
    merged[["geometry"]],
    predicate="within",
    how="inner"
)

# attach group ID via index_right
points_in_parks = points_in_parks.merge(
    park_lookup,
    left_on="index_right",
    right_on="index",
    how="left"
).drop(columns="index")


print("COLUMNS AFTER SPATIAL JOIN + MERGE:")
print(points_in_parks.columns.tolist())


# =========================
# COUNT PTS FOR NEW COLUMNS

# count points per category per park
counts = points_in_parks.groupby([ID_COL, "category_group"]).size().unstack(fill_value=0)

# ensure all expected categories exist (important for parks with no points)
for col in ["praise", "idea", "error_complaint"]:
    if col not in counts.columns:
        counts[col] = 0

# get count per park
counts = counts.rename(columns={
    "praise": "praise_count",
    "idea": "idea_count",
    "error_complaint": "error_complaint_count"
})

counts["total_comments"] = (
    counts["praise_count"]
    + counts["idea_count"]
    + counts["error_complaint_count"]
)

# ====================
# calculate proportion

counts["praise_prop"] = counts["praise_count"] / counts["total_comments"]
counts["idea_prop"] = counts["idea_count"] / counts["total_comments"]
counts["error_complaint_prop"] = (
    counts["error_complaint_count"] / counts["total_comments"]
)

# replace NaN (parks with zero comments) with 0
counts = counts.fillna(0)

# reset index so ID_COL becomes a column again
counts = counts.reset_index()


# # calculate proportion for each category
# for col in counts.columns:
#     if col != "total_points":
#         counts[col + "_prop"] = counts[col] / counts["total_points"]
#
# # keep only proportion columns
# proportions = counts[[c for c in counts.columns if c.endswith("_prop")]].reset_index()


# ==================
# MERGE PTS TO PARKS

merged = merged.merge(counts, on=ID_COL, how="left")

# parks with no comments at all
count_cols = [
    "praise_count",
    "idea_count",
    "error_complaint_count",
    "total_comments",
    "praise_prop",
    "idea_prop",
    "error_complaint_prop"
]

# change empty Kategori rows from NaN to 0
#prop_cols = [c for c in merged.columns if c.endswith("_prop")]
#merged[prop_cols] = merged[prop_cols].fillna(0)

merged[count_cols] = merged[count_cols].fillna(0)

# ====
# SAVE

merged.to_excel(f"{OUTPUT_PATH}/VARIABLES_regression.xlsx", index=False)

merged.to_file(
    OUTPUT_FILE,
    layer="VARIABLES_regression",
    driver="GPKG"
)


