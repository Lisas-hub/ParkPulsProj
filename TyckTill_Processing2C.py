
# >>> topic model and some model visualisations <<<

import geopandas as gpd
import pandas as pd
import numpy as np
import os

from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
import ast
from bertopic.representation import MaximalMarginalRelevance
from hdbscan import HDBSCAN
import umap
from bertopic.representation import KeyBERTInspired


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
#for i in range(len(dfs)):
#    dfs[i] = dfs[i].drop(columns=['topic', 'topic_prob', 'topic_keywords'], errors='ignore')

all_comments = pd.concat(dfs, ignore_index=True)
all_comments = all_comments.sample(30000, random_state=42)        # *** REMOVE LINE TO RUN ON ALL ROWS, NOT JUST A SAMPLE ***

#texts = all_comments['clean_Fritext'].apply(lambda words: ' '.join(w.strip() for w in words)).tolist()  # *** used lemmas before but
mask = all_comments["clean_Fritext"].astype(str).str.strip().str.len() >= 3
all_comments_filtered = all_comments[mask].copy()    # filter rows where text is too short/empty
texts = all_comments["clean_Fritext"].astype(str).tolist()

# set up embedding ("transforming our input documents into numerical representations" - https://maartengr.github.io/BERTopic/getting_started/embeddings/embeddings.html)
embedding_model = SentenceTransformer("KBLab/sentence-bert-swedish-cased")        # better with a swedish specific model?
#embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# set up UMAP
umap_model = umap.UMAP(
    n_neighbors=40,        # smaller = more local structure
    n_components=10,       # higher = more dimensions preserved
    min_dist=0.0,          # lower = tighter clusters
    metric='cosine',       # 'cosine', 'euclidean', 'manhattan'
    random_state=42
)

# set up HDBSCAN (cluster into groups of similar embeddings)
hdbscan_model = HDBSCAN(
    min_cluster_size=40,          # reduce to get smaller topics
    min_samples=1,                # controls strictness of clustering (higher = conservative, so lower to make less strict. None balances strictness automatically)
    metric='euclidean',           # other options: 'euclidean' or 'manhattan'
    cluster_selection_method='eom',
    prediction_data=True
)

# set up representation model
mmr = MaximalMarginalRelevance(diversity=0.5)
rep_model = KeyBERTInspired(top_n_words=10)    # use mmr or BERTInspired - which is best?

# create topic model
topic_model = BERTopic(
    embedding_model=embedding_model,
    umap_model=umap_model,
    hdbscan_model=hdbscan_model,
    language="swedish",
    min_topic_size=50,                   # the higher the number the more general topics
    verbose=True,
    calculate_probabilities=True,
    representation_model=rep_model,
    top_n_words=10                       # number of keywords shown as summary of a topic
)

topics, probs = topic_model.fit_transform(texts)
assigned_probs = [row[topic] if topic != -1 else 0 for row, topic in zip(probs, topics)] # assign 0 for noise (topic -1)
all_comments['topic'] = topics
all_comments['topic_prob'] = assigned_probs

topic_info = topic_model.get_topic_info()
topic_words = topic_model.get_topic(0)
#print(topic_info)
#print(topic_words)

def get_top_words(topic_num, top_n=10):
    words = topic_model.get_topic(topic_num)
    return ', '.join([word for word, _ in words[:top_n]]) if words else ''
all_comments['topic_keywords'] = all_comments['topic'].apply(get_top_words)

# save as excel
all_comments.to_excel(f"{output_folder}/tycktill_with_topics.xlsx", index=False)

# save as points gpkg
pts_with_topics = gpd.GeoDataFrame(
    all_comments, geometry=gpd.points_from_xy(
        all_comments['Koordinater_x'],
        all_comments['Koordinater_Y']
    ),
    crs=4326)
pts_with_topics = pts_with_topics.to_crs("EPSG:3006")

pts_with_topics.to_file("data/tyck_till_output/tycktill.gpkg", layer="pts_with_topics", driver="GPKG", mode="w")

# ============================
# === topic visualisations ===

# topic frequency bar chart
fig = topic_model.visualize_barchart(top_n_topics=20)
fig.write_html(f"{output_folder}/topic_barchart.html")

# intertopic distance map
#fig = topic_model.visualize_topics()
#fig.write_html(f"{output_folder}/intertopic_distance_map.html")

# topic probability
fig = topic_model.visualize_distribution(probs[0], min_probability=0.001)  # example for one document
fig.write_html(f"{output_folder}/topic_distribution_doc0.html")
# loop through a few to inspect more
for i in range(5):
    fig = topic_model.visualize_distribution(probs[i], min_probability=0.001)
    fig.write_html(f"{output_folder}/topic_distribution_doc{i}.html")

# check and potentially filter out noise (topic -1)
print(all_comments[all_comments['topic'] == -1]['clean_Fritext'].sample(5))
#noise_comments = all_comments[all_comments['topic'] == -1]s
#print(f"Noise documents: {len(noise_comments)} / {len(all_comments)}")

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
# save 3 versions

# all park related topics based on keywords (this includes comments that don't necessarily have a keyword but it is the same topic as at least one other comment that DOES include a keyword)
#park_comments_by_topic = all_comments[all_comments['topic'].isin(park_related_topics_manual)]
#park_comments_by_topic.to_excel(f"{output_folder}/park_comments_by_topic1.xlsx", index=False)

#pts_with_topics1 = gpd.GeoDataFrame(
#    park_comments_by_topic, geometry=gpd.points_from_xy(
#        park_comments_by_topic['Koordinater_x'],
#        park_comments_by_topic['Koordinater_Y']
#    ),
#    crs=4326)
#pts_with_topics1 = pts_with_topics1.to_crs("EPSG:3006")

#pts_with_topics1.to_file("data/tyck_till_output/tycktill.gpkg", layer="pts_with_park_comments_by_topic1", driver="GPKG", mode="w")

# all rows where a keyword exists in the comment
#def contains_park_keyword(comments):
#    return any(kw.lower() in [word.lower() for word in comments] for kw in park_keywords)
#park_comments_by_keyword = all_comments[all_comments['clean_Fritext'].apply(contains_park_keyword)]
#park_comments_by_keyword.to_excel(f"{output_folder}/park_comments_by_keyword1.xlsx", index=False)

#pts_with_topics1 = gpd.GeoDataFrame(
#    park_comments_by_keyword, geometry=gpd.points_from_xy(
#        park_comments_by_keyword['Koordinater_x'],
#        park_comments_by_keyword['Koordinater_Y']
#    ),
#    crs=4326)
#pts_with_topics1 = pts_with_topics1.to_crs("EPSG:3006")

#pts_with_topics1.to_file("data/tyck_till_output/tycktill.gpkg", layer="pts_with_park_comments_by_keyword1", driver="GPKG", mode="w")

# park related topics but ONLY rows where a keyword exists in the comment
#park_comments_by_topic_and_keyword = park_comments_by_topic[park_comments_by_topic['clean_Fritext'].apply(contains_park_keyword)]
#park_comments_by_topic_and_keyword.to_excel(f"{output_folder}/park_comments_by_topic_and_keyword1.xlsx", index=False)

#pts_with_topics1 = gpd.GeoDataFrame(
#    park_comments_by_topic_and_keyword, geometry=gpd.points_from_xy(
#        park_comments_by_topic_and_keyword['Koordinater_x'],
#        park_comments_by_topic_and_keyword['Koordinater_Y']
#    ),
#    crs=4326)
#pts_with_topics1 = pts_with_topics1.to_crs("EPSG:3006")

#pts_with_topics1.to_file("data/tyck_till_output/tycktill.gpkg", layer="pts_with_park_comments_by_topic_and_keyword1", driver="GPKG", mode="w")



# ====================