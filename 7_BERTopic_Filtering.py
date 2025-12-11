
import os
import pandas as pd
import geopandas as gpd
from bertopic import BERTopic
import numpy as np
import re

# =====
# paths

model_path = "data/tycktill_output/BERTopic/bertopic_model"
input_folder = os.path.join("data", "tycktill_output", "BERTopic")
output_folder = os.path.join("data", "tycktill_output", "BERTopic_filtered")
os.makedirs(output_folder, exist_ok=True)
output_folder_plots = os.path.join("data", "tycktill_output", "plots")

# ===================
# load model and data

topic_model = BERTopic.load(model_path)
all_comments = pd.read_excel(f"{input_folder}/tycktill_with_topics.xlsx")
probs = np.load(os.path.join(f"{input_folder}/topic_probabilities.npy"), allow_pickle=True)

# ==========================================
# === FILTER 1: by geographical location ===

parks = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base").to_crs(3006)

all_comments_gdf = gpd.GeoDataFrame(
    all_comments,
    geometry=gpd.points_from_xy(all_comments["Koordinater_x"], all_comments["Koordinater_Y"]),
    crs=4326
).to_crs(3006)

pts_in_parks = gpd.sjoin(all_comments_gdf, parks, predicate="within", how="inner")
print(f"Points inside parks: {len(pts_in_parks)} / {len(all_comments)} total")

pts_in_parks.to_file(
    os.path.join(output_folder, "tycktill_filtered.gpkg"),
    layer="pts_in_parks_with_topics",
    driver="GPKG",
    mode="w"
)
pts_in_parks.to_excel(f"{output_folder}/pts_in_parks_with_topics.xlsx", index=False)

# ========================
# get top5 topics per park (prepp for streamlit that just fitted well in this script)

topic_counts = (
    pts_in_parks.groupby(["group", "topic", "topic_keywords", "topic_keywords_weighted"])
    .size()
    .reset_index(name="count")
)

top5_topics_per_park = (
    topic_counts.sort_values(["group", "count"], ascending=[True, False])
    .groupby("group")
    .head(5)
)

def format_topic_list(df):
    lines = [
        f"{rank}. {row.topic_keywords} (Topic {row.topic}, n={row['count']})"
        for rank, (_, row) in enumerate(df.iterrows(), start=1)
    ]
    return "\n".join(lines)

top_topics_joined = (
    top5_topics_per_park
    .groupby("group")
        .apply(lambda df: pd.Series({
        "Top5_Topics": ", ".join(df.sort_values("count", ascending=False)["topic"].astype(str)),
        "Top5_Table": format_topic_list(df.sort_values("count", ascending=False))
    }))
        .reset_index()
)

parks_with_topics = parks.merge(top_topics_joined, on="group", how="left")

parks_with_topics.to_file(
    f"{output_folder}/tycktill_filtered.gpkg",
    layer="parks_with_top5_topics",
    driver="GPKG",
    mode="w"
)

# =========================================
# === prepp for filtering with keywords ===

keywords_file_path = 'data/keywords.xlsx'
selected_sheets = ['Sheet1', 'Sheet2', 'Sheet3', 'Sheet4']

park_keywords = []
for sheet in selected_sheets:
    df = pd.read_excel(keywords_file_path, sheet_name=sheet, usecols=[0])
    park_keywords.extend(df.iloc[:, 0].dropna().tolist())

park_keywords = list(set([w.strip().lower() for w in park_keywords]))

# match endings with keywords i the texts
swedish_endings = r'(en|et|ar|er|or|na|n|s|ens|ets|arnas|ernas|ornas|ens|ets|as)?'
pattern = re.compile(
    r'\b(' + '|'.join(
        rf"{re.escape(kw)}{swedish_endings}" for kw in park_keywords
    ) + r')\b',
    flags=re.IGNORECASE
)

# =======================================================
# === FILTER 2: by specific keywords in clean_Fritext ===

def contains_park_keyword(text):
    """ True if comment contains at least one park keyword"""
    return bool(pattern.search(str(text)))

def find_matched_keywords(text):
    """list of all keywords matched in a comment"""
    text = str(text)
    return [kw for kw in park_keywords if re.search(rf"\b{re.escape(kw)}{swedish_endings}\b", text, flags=re.IGNORECASE)]

# filter for comments with at least one park keyword
mask = all_comments["clean_Fritext"].astype(str).apply(contains_park_keyword)
park_comments_by_keyword = all_comments.loc[mask].copy()
park_comments_by_keyword["matched_keywords"] = park_comments_by_keyword["clean_Fritext"].apply(find_matched_keywords)

# save
park_comments_by_keyword.to_excel(f"{output_folder}/park_comments_by_keywords.xlsx", index=False)
park_comments_by_keyword_gdf = gpd.GeoDataFrame(
    park_comments_by_keyword,
    geometry=gpd.points_from_xy(park_comments_by_keyword["Koordinater_x"], park_comments_by_keyword["Koordinater_Y"]),
    crs=4326
)
park_comments_by_keyword_gdf.to_file(f"{output_folder}/tycktill_filtered.gpkg", layer="park_comments_by_keyword", driver="GPKG", mode="w")

print(f"Saved {len(park_comments_by_keyword)} comments containing park keywords.")


# ==================================================
# === FILTER 3: by BERTopic using topic_keywords ===

similar_topics_all = []
similarity_all = []

for kw in park_keywords:
    try:
        topics, sims = topic_model.find_topics(kw, top_n=5)
        similar_topics_all.extend(topics)
        similarity_all.extend(sims)
    except Exception as e:
        print(f"Skipping keyword '{kw}' due to error: {e}")

topic_similarity_df = pd.DataFrame({
    "topic": similar_topics_all,
    "similarity": similarity_all
}).drop_duplicates(subset=["topic"])

# keep only topics with similarity > 0.3
topic_similarity_df = topic_similarity_df[topic_similarity_df["similarity"] > 0.3]   # *** höj threshold? ELLER ta bort keywords som sandlåda etc ***

# filter comments with these topics
park_comments_by_BERTopic = all_comments[all_comments["topic"].isin(topic_similarity_df["topic"])].copy()
park_comments_by_BERTopic = park_comments_by_BERTopic.merge(topic_similarity_df, on="topic", how="left")

# save
park_comments_by_BERTopic_gdf = gpd.GeoDataFrame(
    park_comments_by_BERTopic,
    geometry=gpd.points_from_xy(park_comments_by_BERTopic["Koordinater_x"], park_comments_by_BERTopic["Koordinater_Y"]),
    crs=4326
)
park_comments_by_BERTopic_gdf.to_file(f"{output_folder}/tycktill_filtered.gpkg", layer="park_comments_by_BERTopic", driver="GPKG", mode="w")

print(f"Saved {len(park_comments_by_BERTopic)} comments from park-similar topics.")


# Points inside parks: 78454 / 290448 total
# Saved 26302 comments containing park keywords.
# Saved 60877 comments from park-similar topics.


# OLD:
# Points inside parks: 78454 / 290448 total
# Saved 25574 comments containing park keywords.
# Saved 58809 comments from park-similar topics.


##########################################
# old
# === comparing output of both filters ===

id_col = "Ärendenummer"

ids_1 = set(park_comments_by_keyword[id_col])
ids_2 = set(park_comments_by_BERTopic[id_col])

overlap_ids = ids_1 & ids_2
only_filter1_ids = ids_1 - ids_2
only_filter2_ids = ids_2 - ids_1

gdf_overlap = park_comments_by_keyword[park_comments_by_keyword[id_col].isin(overlap_ids)].copy()
gdf_only_filter1 = park_comments_by_keyword[park_comments_by_keyword[id_col].isin(only_filter1_ids)].copy()
gdf_only_filter2 = park_comments_by_BERTopic[park_comments_by_BERTopic[id_col].isin(only_filter2_ids)].copy()

output_gpkg = f"{output_folder}/tycktill_filtered.gpkg"

#gdf_overlap.to_file(output_gpkg, layer="park_overlap", driver="GPKG", mode="w")
#gdf_only_filter1.to_file(output_gpkg, layer="park_only_keywords", driver="GPKG", mode="w")
#gdf_only_filter2.to_file(output_gpkg, layer="park_only_topics", driver="GPKG", mode="w")



