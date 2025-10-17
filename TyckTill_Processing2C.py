
# >>> topic model and some model visualisations <<<

import geopandas as gpd
import pandas as pd
import numpy as np
import os

from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
import ast

input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

# =====================================
# set up for saving in the right folder

output_folder = os.path.join("data", "tyck_till_output", "per_kategori")


# ==================================================================================
# ================================ Topic Modelling =================================
# https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

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
#all_lemmas = all_lemmas.sample(10000, random_state=42)        # *** REMOVE LINE TO RUN ON ALL ROWS, NOT JUST A SAMPLE ***

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

# save as excel
all_lemmas.to_excel(f"{output_folder}/tycktill_with_topics.xlsx", index=False)

# save as points gpkg
pts_with_topics = gpd.GeoDataFrame(
    all_lemmas, geometry=gpd.points_from_xy(
        all_lemmas['Koordinater_x'],
        all_lemmas['Koordinater_Y']
    ),
    crs=4326)
pts_with_topics = pts_with_topics.to_crs("EPSG:3006")

pts_with_topics.to_file("data/tyck_till_output/tycktill.gpkg", layer="pts_with_topics", driver="GPKG", mode="w")

# ============================
# === topic visualisations ===

# topic frequency bar chart
topic_model.visualize_barchart(top_n_topics=20)
fig = topic_model.visualize_barchart(top_n_topics=20)
fig.write_html(f"{output_folder}/topic_barchart.html")

# intertopic distance map
# *** add ***
fig = topic_model.visualize_topics()
fig.write_html(f"{output_folder}/intertopic_distance_map.html")

# ================================================
# === find park topics based on selected words ===

keywords_file_path = 'data/keywords.xlsx'
selected_sheets = ['Sheet1', 'Sheet2', 'Sheet3', 'Sheet4']

park_keywords = []

for sheet in selected_sheets:
    keywords_df = pd.read_excel(keywords_file_path, sheet_name=sheet, usecols=[0])
    words = keywords_df.iloc[:, 0].dropna().tolist()
    park_keywords.extend(words)

park_keywords = list(set(word.strip() for word in park_keywords)) # remove duplicates and whitespace

park_related_topics_manual = []

for topic in topic_model.get_topics().keys():
    topic_id = int(topic)
    if topic == -1:
        continue
    topic_words = [word for word, _ in topic_model.get_topic(topic_id)]
    if any(kw in topic_words for kw in park_keywords):
        park_related_topics_manual.append(topic)

# create DataFrame with all topic IDs
all_topic_ids = [t for t in topic_model.get_topics().keys() if t != -1]
topic_flags_df = pd.DataFrame({
    "topic_IDs": all_topic_ids,
    "is_park_related_manual": [t in park_related_topics_manual for t in all_topic_ids]
})

# ===============
# save 2 versions

# all park related topics based on keywords (this includes comments that don't necessarily have a keyword but it is the same topic as at least one other comment that DOES include a keyword)
park_comments_by_topic = all_lemmas[all_lemmas['topic'].isin(park_related_topics_manual)]
park_comments_by_topic.to_excel(f"{output_folder}/park_comments_by_topic1.xlsx", index=False)

pts_with_topics1 = gpd.GeoDataFrame(
    park_comments_by_topic, geometry=gpd.points_from_xy(
        park_comments_by_topic['Koordinater_x'],
        park_comments_by_topic['Koordinater_Y']
    ),
    crs=4326)
pts_with_topics1 = pts_with_topics1.to_crs("EPSG:3006")

pts_with_topics1.to_file("data/tyck_till_output/tycktill.gpkg", layer="pts_with_park_comments_by_topic1", driver="GPKG", mode="w")

# all rows where a keyword exists in the comment
def contains_park_keyword(lemmas):
    return any(kw.lower() in [word.lower() for word in lemmas] for kw in park_keywords)
park_comments_by_keyword = all_lemmas[all_lemmas['lemmas'].apply(contains_park_keyword)]
park_comments_by_keyword.to_excel(f"{output_folder}/park_comments_by_keyword1.xlsx", index=False)

pts_with_topics1 = gpd.GeoDataFrame(
    park_comments_by_keyword, geometry=gpd.points_from_xy(
        park_comments_by_keyword['Koordinater_x'],
        park_comments_by_keyword['Koordinater_Y']
    ),
    crs=4326)
pts_with_topics1 = pts_with_topics1.to_crs("EPSG:3006")

pts_with_topics1.to_file("data/tyck_till_output/tycktill.gpkg", layer="pts_with_park_comments_by_keyword1", driver="GPKG", mode="w")

# park related topics but ONLY rows where a keyword exists in the comment
park_comments_by_topic_and_keyword = park_comments_by_topic[park_comments_by_topic['lemmas'].apply(contains_park_keyword)]
park_comments_by_topic_and_keyword.to_excel(f"{output_folder}/park_comments_by_topic_and_keyword1.xlsx", index=False)

pts_with_topics1 = gpd.GeoDataFrame(
    park_comments_by_topic_and_keyword, geometry=gpd.points_from_xy(
        park_comments_by_topic_and_keyword['Koordinater_x'],
        park_comments_by_topic_and_keyword['Koordinater_Y']
    ),
    crs=4326)
pts_with_topics1 = pts_with_topics1.to_crs("EPSG:3006")

pts_with_topics1.to_file("data/tyck_till_output/tycktill.gpkg", layer="pts_with_park_comments_by_topic_and_keyword1", driver="GPKG", mode="w")



# ====================