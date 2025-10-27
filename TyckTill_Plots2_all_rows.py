
# >>> rasters, vector layers, figures for all rows in one <<<

import geopandas as gpd
import pandas as pd
import numpy as np
import os
import rasterio
from rasterio.transform import from_origin
from rasterio.features import rasterize
from rasterio.enums import MergeAlg
from collections import defaultdict, Counter


input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

# =====================================
# set up for saving in the right folder

output_folder = os.path.join("data", "tycktill_output", "per_kategori")
output_folder_plots = os.path.join("data", "tycktill_output", "per_kategori", "plots")


# =======================================
# === make a raster for point density ===

municipality = gpd.read_file(f"{input_directory}\\Output\\Kommun_Stadskartan_SWEREF99TM.gpkg").to_crs("EPSG:3006")

target_crs = 3857 # a projected crs is required, 3857

if municipality.crs.to_epsg() != target_crs:
    municipality = municipality.to_crs(target_crs)

# set up for raster
pixel_size = 100                                       # <<< used 500 previously (before error report was added)
minx, miny, maxx, maxy = municipality.total_bounds
width = int((maxx - minx) / pixel_size)
height = int((maxy - miny) / pixel_size)
transform = from_origin(minx, maxy, pixel_size, pixel_size)
nodata_value = -9999

# rasterize mask
municipality_mask = rasterize(
    shapes=[(geom, 0) for geom in municipality.geometry],
    out_shape=(height, width),
    transform=transform,
    fill=nodata_value,
    dtype='int16'
)

# load point layers per cateory
categories = {
    "Klagomål": gpd.read_file("data/tycktill_output/per_kategori/tycktill_Klagomål.gpkg"),
    "Beröm": gpd.read_file("data/tycktill_output/per_kategori/tycktill_Beröm.gpkg"),
    "Idé": gpd.read_file("data/tycktill_output/per_kategori/tycktill_Idé.gpkg"),
    "Felanmälan": gpd.read_file("data/tycktill_output/per_kategori/tycktill_Felanmälan.gpkg"),
    #"Fråga": gpd.read_file("data/tycktill_output/per_kategori/tycktill_Fråga.gpkg"),
}

for key in categories:
    if not categories[key].crs.is_projected:
        categories[key] = categories[key].to_crs(epsg=target_crs)
    elif categories[key].crs.to_epsg() != target_crs:
        categories[key] = categories[key].to_crs(epsg=target_crs)

# create point density rasters
def rasterize_points(gdf):
    shapes = ((geom, 1) for geom in gdf.geometry)
    return rasterize(
        shapes=shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype='uint16',
        merge_alg=MergeAlg.add
    )

density_rasters = {} # store for later use in ratio calculation

for name, gdf in categories.items():
    density_data = rasterize_points(gdf)
    masked_density = np.where(municipality_mask == 0, density_data, nodata_value).astype('int16')

    output_path = os.path.join(output_folder_plots, f"point_density_{name}.tif")
    with rasterio.open(
        output_path,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=1,
        dtype='int16',
        crs=municipality.crs,
        transform=transform,
        nodata=nodata_value
    ) as dst:
        dst.write(masked_density, 1)

    density_rasters[name] = density_data  # store for ratios


# ============================
# === complaint/idea ratio ===

complaints = density_rasters["Klagomål"]
ideas = density_rasters["Idé"]
praise = density_rasters["Beröm"]
errorreport = density_rasters["Felanmälan"]
total = complaints + ideas + praise + errorreport
complaints_errorreport = complaints + errorreport

# avoid division by 0
with np.errstate(divide='ignore', invalid='ignore'):
    ratio = np.true_divide(complaints_errorreport, total)
    ratio[total == 0] = nodata_value

masked_ratio = np.where(municipality_mask == 0, ratio, nodata_value)

# save
with rasterio.open(
    f"{output_folder_plots}/complaints_errorreport_idea_praise_ratio.tif",
    'w',
    driver='GTiff',
    height=height,
    width=width,
    count=1,
    dtype='float32',
    crs=municipality.crs,
    transform=transform,
    nodata=nodata_value
) as dst:
    dst.write(masked_ratio.astype('float32'), 1)

# ==================================================================
# === sentiment positive/negative ratio + sentiment score raster ===

# prepp
gdfs = [
    gpd.read_file(f"{output_folder}\\tycktill_Klagomål.gpkg"),
    gpd.read_file(f"{output_folder}\\tycktill_Beröm.gpkg"),
    gpd.read_file(f"{output_folder}\\tycktill_Idé.gpkg"),
    gpd.read_file(f"{output_folder}\\tycktill_Felanmälan.gpkg")
    #gpd.read_file(f"{output_folder}\\tycktill_Fråga.gpkg")
]

all_points = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs=gdfs[0].crs)

positive_gdf = all_points[all_points["sentiment_label"] == "POSITIVE"]
neutral_gdf = all_points[all_points["sentiment_label"] == "NEUTRAL"]
negative_gdf = all_points[all_points["sentiment_label"] == "NEGATIVE"]

if not positive_gdf.crs.is_projected:
    positive_gdf = positive_gdf.to_crs(epsg=target_crs)
    neutral_gdf = neutral_gdf.to_crs(epsg=target_crs)
    negative_gdf = negative_gdf.to_crs(epsg=target_crs)

# rasterize
positive_raster = rasterize_points(positive_gdf)
neutral_raster = rasterize_points(neutral_gdf)
negative_raster = rasterize_points(negative_gdf)

# =============
# compute ratio
total_sentiment = positive_raster + neutral_raster + negative_raster

with np.errstate(divide='ignore', invalid='ignore'):
    sentiment_ratio = np.true_divide(negative_raster, total_sentiment)
    sentiment_ratio[total_sentiment == 0] = nodata_value

masked_sentiment_ratio = np.where(municipality_mask == 0, sentiment_ratio, nodata_value)

# save
output_path = os.path.join(output_folder_plots, "sentiment_ratio_neg_vs_pos_neu.tif")
with rasterio.open(
    output_path,
    'w',
    driver='GTiff',
    height=height,
    width=width,
    count=1,
    dtype='float32',
    crs=municipality.crs,
    transform=transform,
    nodata=nodata_value
) as dst:
    dst.write(masked_sentiment_ratio.astype('float32'), 1)

# ==============
# compute scores
score_raster = (
    positive_raster.astype('int16') * 1 +
    neutral_raster.astype('int16') * 0 +
    negative_raster.astype('int16') * -1
)
masked_score = np.where(municipality_mask == 0, score_raster, nodata_value)

# save
output_path = os.path.join(output_folder_plots, "sentiment_score.tif")
with rasterio.open(
    output_path,
    'w',
    driver='GTiff',
    height=height,
    width=width,
    count=1,
    dtype='int16',
    crs=municipality.crs,
    transform=transform,
    nodata=nodata_value
) as dst:
    dst.write(masked_score.astype('int16'), 1)

# ====================================================================
# === sentiment positive/negative ratio + sentiment score PER PARK ===

parks = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base").to_crs(target_crs)
if parks.crs.to_epsg() != target_crs:
    parks = parks.to_crs(target_crs)

# filter only points inside parks
park_points = all_points[all_points["in_park"]].copy()
if park_points.crs.to_epsg() != target_crs:
    park_points = park_points.to_crs(target_crs)

# add group value to each point
park_points = gpd.sjoin(
    park_points,
    parks[["group", "geometry"]],
    how="inner",
    predicate="within"
)

# ========================
# sentiment ratio per park

# group by park and count each sentiment type
sentiment_counts = (
    park_points.groupby("group")["sentiment_label"]
    .value_counts()
    .unstack(fill_value=0)
)

for col in ["POSITIVE", "NEUTRAL", "NEGATIVE"]:
    if col not in sentiment_counts.columns:
        sentiment_counts[col] = 0

sentiment_counts["total"] = (
    sentiment_counts["POSITIVE"] + sentiment_counts["NEUTRAL"] + sentiment_counts["NEGATIVE"]
)
sentiment_counts["negative_ratio"] = (
    sentiment_counts["NEGATIVE"] / sentiment_counts["total"]
)

# ========================
# sentiment score per park

park_points["score"] = park_points["sentiment_label"].map({
    "POSITIVE": 1,
    "NEUTRAL": 0,
    "NEGATIVE": -1
})
park_scores = park_points.groupby("group")["score"].sum()

# merge back and save
parks = parks.merge(sentiment_counts[["negative_ratio"]], on="group", how="left")
parks = parks.merge(park_scores.rename("sentiment_score"), on="group", how="left")

# normalise by park area
parks["park_area"] = parks["park_area"].replace(0, np.nan)
parks["sentiment_score_per_ha"] = parks["sentiment_score"] / (parks["park_area"]/10000)

# save
parks.to_file("data/tycktill_output_tycktill.gpkg", layer="sentiments_per_park", driver="GPKG", mode="w")



# ==============================================
# dominant topic raster + topic diversity raster
#pts_with_topics = gpd.read_file(f"{output_folder}/ons_8_okt_all_rows/tycktill.gpkg", layer="pts_with_topics") # *** remove this row if doing a new subset ***

pts_with_topics = gpd.read_file("data/tycktill_output/tycktill.gpkg", layer="pts_with_topics")

target_crs = 3857
if pts_with_topics.crs.to_epsg() != target_crs:
    pts_with_topics = pts_with_topics.to_crs(target_crs)

cols = ((pts_with_topics.geometry.x - minx) // pixel_size).astype(int)
rows = ((maxy - pts_with_topics.geometry.y) // pixel_size).astype(int)

topic_bins = defaultdict(list)     # for dominant topic
topic_sets = defaultdict(set)      # for topic diversity

# get topics per cell
for row, col, topic in zip(rows, cols, pts_with_topics['topic']):
    if 0 <= row < height and 0 <= col < width:
        topic_bins[(row, col)].append(topic)
        topic_sets[(row, col)].add(topic)

dominant_topic = np.full((height, width), nodata_value, dtype=np.int16)
topic_count = np.full((height, width), nodata_value, dtype=np.int16)

# fill dominant topic raster
for (row, col), topics in topic_bins.items():
    dominant = Counter(topics).most_common(1)[0][0]
    dominant_topic[row, col] = dominant

# fill topic diversity raster
for (row, col), topic_set in topic_sets.items():
    topic_count[row, col] = len(topic_set)

# save
with rasterio.open(
    f"{output_folder_plots}/dominant_topic.tif",
    "w",
    driver="GTiff",
    height=height,
    width=width,
    count=1,
    dtype=dominant_topic.dtype,
    crs=gdf.crs,
    transform=transform,
    nodata=nodata_value
) as dst:
    dst.write(dominant_topic, 1)

with rasterio.open(
    f"{output_folder_plots}/topic_diversity.tif",
    "w",
    driver="GTiff",
    height=height,
    width=width,
    count=1,
    dtype=topic_count.dtype,
    crs=pts_with_topics.crs,
    transform=transform,
    nodata=nodata_value
) as dst:
    dst.write(topic_count, 1)

# ========================
# topic diversity per park

park_points2 = gpd.sjoin(
    pts_with_topics,
    parks[["group", "geometry"]],
    how="left",
    predicate="intersects"
)

# count unique topics per park
topic_diversity_in_park = (
    park_points2.groupby("group")["topic"]
    .nunique(dropna=True)
)

# join back with parks
parks_with_topic_diversity = parks.merge(
    topic_diversity_in_park,
    on="group",
    how="left"
)

parks_with_topic_diversity["topic_diversity"] = parks_with_topic_diversity["topic"].fillna(0).astype(int)

parks_with_topic_diversity["topic_diversity_per_ha"] = (
    parks_with_topic_diversity["topic_diversity"] / (parks_with_topic_diversity["park_area"] / 10000)
)

parks_with_topic_diversity.to_file("data/tycktill_output/tycktill.gpkg", layer="parks_with_topic_diversity", driver="GPKG", mode="w")

# =====================
# top 5 topics per park

# group by park and list top 5 topics
topics_per_park = park_points2.groupby("group")["topic"].apply(list)

# get top 5 topics
def get_top_n_topics(topic_list, n=5):
    return [topic for topic, _ in Counter(topic_list).most_common(n)]

top_topics = topics_per_park.apply(get_top_n_topics)

# convert list of top topics into a dataframe with 5 columns
top_topics_df = pd.DataFrame(top_topics.tolist(),
                             index=top_topics.index,
                             columns=[f"top_topic_{i+1}" for i in range(5)])

parks_with_top5_topics = parks.merge(top_topics_df, on="group", how="left")

# print general top 5 for all parks
for i in range(1, 6):
    col = f"top_topic_{i}"
    print(f"Most common in {col}:")
    print(parks_with_top5_topics[col].value_counts().head(5), end="\n\n")

parks_with_top5_topics.to_file("data/tycktill_output/tycktill.gpkg", layer="parks_with_top5_topics", driver="GPKG", mode="w")

# =====================
#