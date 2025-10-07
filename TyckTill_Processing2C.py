
# >>> point density rasters <<<

import geopandas as gpd
import pandas as pd
import numpy as np
import os
import rasterio
from rasterio.transform import from_origin
from rasterio.features import rasterize
from rasterio.enums import MergeAlg

input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

# =====================================
# set up for saving in the right folder

output_folder = os.path.join("data", "tyck_till_output", "per_kategori")

# =======================================
# === make a raster for point density ===

municipality = gpd.read_file(f"{input_directory}\\Output\\Kommun_Stadskartan_SWEREF99TM.gpkg").to_crs("EPSG:3006")

target_crs = 3857 # a projected crs is required, 3857

if municipality.crs.to_epsg() != target_crs:
    municipality = municipality.to_crs(target_crs)

# set up for raster
pixel_size = 250                                       # <<< used 500 previously (before error report was added)
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
    "Klagomål": gpd.read_file("data/tyck_till_output/per_kategori/tycktill_Klagomål.gpkg"),
    "Beröm": gpd.read_file("data/tyck_till_output/per_kategori/tycktill_Beröm.gpkg"),
    "Idé": gpd.read_file("data/tyck_till_output/per_kategori/tycktill_Idé.gpkg"),
    "Felanmälan": gpd.read_file("data/tyck_till_output/per_kategori/tycktill_Felanmälan.gpkg"),
    #"Fråga": gpd.read_file("data/tyck_till_output/per_kategori/tycktill_Fråga.gpkg"),
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

    output_path = os.path.join(output_folder, f"point_density_{name}.tif")
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
    f"{output_folder}/complaints_errorreport_idea_praise_ratio.tif",
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
output_path = os.path.join(output_folder, "sentiment_ratio_neg_vs_pos_neu.tif")
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
output_path = os.path.join(output_folder, "sentiment_score.tif")
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
parks.to_file("data/tycktill.gpkg", layer="sentiments_per_park", driver="GPKG", mode="w")


# ==================================================================================
# ================================ Topic Modelling =================================
# https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
import ast

# prepp
dfs = [
    pd.read_excel(f"{output_folder}\\tycktill_with_sentiment_Beröm.xlsx", parse_dates=["Inkommet datum"]),
    pd.read_excel(f"{output_folder}\\tycktill_with_sentiment_Idé.xlsx", parse_dates=["Inkommet datum"]),
    pd.read_excel(f"{output_folder}\\tycktill_with_sentiment_Klagomål.xlsx", parse_dates=["Inkommet datum"]),
    pd.read_excel(f"{output_folder}\\tycktill_with_sentiment_Felanmälan.xlsx", parse_dates=["Inkommet datum"])
    #pd.read_excel(f"{output_folder}\\tycktill_with_sentiment_Fråga.xlsx", parse_dates=["Inkommet datum"])
]

# convert lemmas column from stringified lists to actual lists
for i in range(len(dfs)):
    if isinstance(dfs[i]['lemmas'].iloc[0], str):  # only if it's a string, not a real list
        dfs[i]['lemmas'] = dfs[i]['lemmas'].apply(ast.literal_eval)

# drop old topic model columns from when topic model was in tycktill_with_lemmas{}_.xlsx
for i in range(len(dfs)):
    dfs[i] = dfs[i].drop(columns=['topic', 'topic_prob', 'topic_keywords'], errors='ignore')

all_lemmas = pd.concat(dfs, ignore_index=True)
all_lemmas = all_lemmas.sample(10000, random_state=42) # *** REMOVE LINE TO RUN ON ALL ROWS, NOT JUST A SAMPLE ***
#print(all_lemmas['lemmas'].head())

#texts = all_lemmas['lemmas'].apply(lambda words: ' '.join(words)).tolist()
#print(texts[:10])
texts = all_lemmas['lemmas'].apply(lambda words: ' '.join(w.strip() for w in words)).tolist()
print(texts[:10])

embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# create topic model
topic_model = BERTopic(
    embedding_model=embedding_model,
    language="swedish",
    min_topic_size=50,            # can try 100 for very general topics
    verbose=True
)

topics, probs = topic_model.fit_transform(texts)
all_lemmas['topic'] = topics
all_lemmas['topic_prob'] = probs

topic_info = topic_model.get_topic_info()
topic_words = topic_model.get_topic(0)
print(topic_info)
print(topic_words)

def get_top_words(topic_num, top_n=5): # reduce from default 10 top words to 5
    words = topic_model.get_topic(topic_num)
    #return ', '.join([word for word, _ in words]) if words else ''
    return ', '.join([word for word, _ in words[:top_n]]) if words else ''

all_lemmas['topic_keywords'] = all_lemmas['topic'].apply(get_top_words)

all_lemmas.to_excel(f"{output_folder}/tycktill_with_topics.xlsx", index=False)

# ====================
# topic visualisations

# topic frequency bar chart
topic_model.visualize_barchart(top_n_topics=20)
fig = topic_model.visualize_barchart(top_n_topics=20)
fig.write_html(f"{output_folder}/topic_barchart.html")

# UMAP
topic_model.visualize_topics()
fig = topic_model.visualize_topics()
fig.write_html(f"{output_folder}/topic_visualization.html")

# importance of individual words for topics
topic_model.visualize_barchart(top_n_topics=10)
#topic_model.visualize_barchart(top_n_topics=1, topics=[5]) # use this for one chosen topic
fig = topic_model.visualize_barchart()
fig.write_html(f"{output_folder}/topic_visualization_barchart.html")

# heatmap
topic_model.visualize_heatmap()
fig = topic_model.visualize_heatmap()
fig.write_html(f"{output_folder}/topic_heatmap.html")

# ====================