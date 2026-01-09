
import os
import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
import re
import geopandas as gpd

input_folder = os.path.join("data", "tycktill_output", "BERTopic")
output_folder = os.path.join("data", "tycktill_output", "BERTopic_reduce_topics")

os.makedirs(output_folder, exist_ok=True)

# load document assignments
all_comments = pd.read_excel(f"{input_folder}/tycktill_with_topics.xlsx")



# load topic embeddings
topic_embeddings = np.load(f"{input_folder}/topic_embeddings.npy")

# load topic info for labels
topic_info = pd.read_csv(f"{input_folder}/topic_info.csv")

# cluster topics into meta-topics
n_meta = 100  # or whatever makes sense
clustering = AgglomerativeClustering(n_clusters=n_meta)
meta_labels = clustering.fit_predict(topic_embeddings)

topic_info["meta_topic"] = meta_labels

def normalize_representation(rep, top_n=3):
    if not isinstance(rep, str):
        return ""

    # remove brackets and quotes
    cleaned = re.sub(r"[\[\]']", "", rep)

    # split on whitespace
    words = cleaned.split()

    return " ".join(words[:top_n])

def make_meta_label(group, n_topics=3, words_per_topic=3):
    labels = []
    for rep in (
        group
        .sort_values("Count", ascending=False)
        .head(n_topics)["Representation"]
    ):
        labels.append(normalize_representation(rep, words_per_topic))
    return " | ".join(labels)


meta_sizes = (
    topic_info
    .groupby("meta_topic")
    .size()
    .rename("meta_topic_size")
)

#meta_labels = {}
meta_labels = {
    meta_id: make_meta_label(group)
    for meta_id, group in topic_info.groupby("meta_topic")
}

# add labels to topic_info
topic_info["meta_topic_label"] = topic_info["meta_topic"].map(meta_labels)

topic_info = topic_info.merge(
    meta_sizes,
    left_on="meta_topic",
    right_index=True
)

# merge meta-topics onto documents
df = all_comments.merge(
    topic_info[["Topic", "meta_topic", "meta_topic_label", "meta_topic_size"]],
    left_on="topic",
    right_on="Topic",
    how="left"
).drop(columns="Topic")

# save enriched xlsx file
df.to_excel(f"{output_folder}/tycktill_with_topics_and_meta_topics.xlsx", index=False)

# save gpkg
gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["Koordinater_x"], df["Koordinater_Y"]),
    crs=4326
).to_crs(3006)

gdf.to_file(f"{output_folder}/tycktill_reduced_topics.gpkg",
    layer="tycktill_with_topics_and_meta_topics",
    driver="GPKG",
    mode="w"
)

# **** OM DET INTE BLIR BRA - höj till fler grupper här och visa sen endast matrix av top 20 meta-topics? ****
# **** i streamlit, lägg in expander eller nått så man får en lista med vilka topics som ingår i meta topic ****







