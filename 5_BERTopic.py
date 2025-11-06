
import os
import pandas as pd
import geopandas as gpd
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from bertopic.representation import KeyBERTInspired, MaximalMarginalRelevance
from hdbscan import HDBSCAN
import umap
from sklearn.feature_extraction.text import CountVectorizer
#nltk.download('stopwords')
from nltk.corpus import stopwords
import numpy as np


# =====
# paths

input_directory = r"C:\Users\lisajos\QGIS_Projects"                        # <<< set your directory here <<<

input_folder = os.path.join("data", "tycktill_output")
output_folder = os.path.join("data", "tycktill_output", "BERTopic")

model_path = "data/tycktill_output/BERTopic/bertopic_model"
os.makedirs(os.path.dirname(model_path), exist_ok=True)


# ==================================================================================
# ================================ Topic Modelling =================================
# https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# load data
dfs = [
    pd.read_excel(f"{input_folder}\\tycktill_with_sentiment_Beröm.xlsx", parse_dates=["Inkommet datum"]),
    pd.read_excel(f"{input_folder}\\tycktill_with_sentiment_Idé.xlsx", parse_dates=["Inkommet datum"]),
    pd.read_excel(f"{input_folder}\\tycktill_with_sentiment_Klagomål.xlsx", parse_dates=["Inkommet datum"]),
    pd.read_excel(f"{input_folder}\\tycktill_with_sentiment_Felanmälan.xlsx", parse_dates=["Inkommet datum"])
    #pd.read_excel(f"{input_folder}\\tycktill_with_sentiment_Fråga.xlsx", parse_dates=["Inkommet datum"])
]

all_comments = pd.concat(dfs, ignore_index=True)
#all_comments = all_comments.sample(3000, random_state=42)        # *** REMOVE LINE TO RUN ON ALL ROWS, NOT JUST A SAMPLE ***

print("\n--- Rows before filtering ---")
print(f"Loaded {len(all_comments):,} rows before filtering.")

# filter too-short/empty rows
mask = all_comments["clean_Fritext"].astype(str).str.strip().str.len() >= 3
all_comments = all_comments[mask].copy()

print("\n--- Rows after filtering ---")
print(f"{len(all_comments):,} rows remain after filtering short/empty texts.")

# extract clean_Fritext and convert to string for the model
texts = all_comments["clean_Fritext"].astype(str).tolist()


# ============
# set up model

# === EMBEDDING ===
# "transforming our input documents into numerical representations" https://maartengr.github.io/BERTopic/getting_started/embeddings/embeddings.html

embedding_model = SentenceTransformer("KBLab/sentence-bert-swedish-cased")         # swedish alternative - better?
#embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")    # multiligual alternative

# === UMAP ===
# dimensionality reduction (compresses the meaning of comments while still keeping similar comments together)

umap_model = umap.UMAP(
    n_neighbors=100,       # smaller = more local structure (with a 3000 rows sample, lowering from 40 to 20 reduced -1 rows from 701 to 507)
    n_components=10,       # higher = more dimensions preserved
    min_dist=0.1,          # lower = tighter clusters
    metric='cosine',       # 'cosine', 'euclidean', 'manhattan'
    random_state=42
)

# === HDBSCAN ===
# cluster reduced embeddings (comments) into similar groups / topics

hdbscan_model = HDBSCAN(
    min_cluster_size=50,              # reduce to get smaller topics (with a 3000 rows sample, lowering from 40 to 20 reduced -1 rows from 507 to 488)
    min_samples=5,                    # controls strictness of clustering (higher = conservative, so lower to make less strict. None balances strictness automatically)
    metric='euclidean',               # other options: 'euclidean' or 'manhattan'
    cluster_selection_method='eom',   # tried 'leaf' instead of 'eom' but that increased -1 topics
    prediction_data=True
)

# === representation model ===
# extracts topic keywords that best represent the topics (MMR or BERTInspired, which is best?)

mmr = MaximalMarginalRelevance(diversity=0.3)
rep_model = KeyBERTInspired(top_n_words=10)      # with this i got some fuzzy topic_keywords, for example one topic that is clearly about potholes but the words pothål, grop, etc still did not occur in the label

# === vectorizer model ===
# removes stopwords from topic keywords

stop_words_SWE = list(stopwords.words("swedish"))               # this is stopwords from nltk (using this instead of manually writing out a list)

vectorizer_model = CountVectorizer(stop_words=stop_words_SWE)
#vectorizer_model = CountVectorizer(stop_words="english")       # this is the normal way but it does not have a list of swedish stopwords built in

# ===========
# topic model

topic_model = BERTopic(
    embedding_model=embedding_model,
    umap_model=umap_model,
    hdbscan_model=hdbscan_model,
    language="swedish",
    min_topic_size=50,                   # the higher the number the more general topics
    verbose=True,
    calculate_probabilities=True,        # if False, processing will be a lot quicker but it's need for .reduce_outliers() later
    representation_model=mmr,            # switched to try if MMR makes better topic_keywords than BERTInspired
    top_n_words=10,                      # number of keywords shown as summary of a topic
    vectorizer_model=vectorizer_model
)

# train model
topics, probs = topic_model.fit_transform(texts)

# reduce outliers (-1 topics are re-assigned to another topic based on topic probability)
topics = topic_model.reduce_outliers(
    texts, topics, strategy="probabilities", probabilities=probs
)

# assign topic and probability to each comment
assigned_probs = [row[topic] if topic != -1 else 0 for row, topic in zip(probs, topics)] # assign 0 for noise (topic -1)
all_comments['topic'] = topics
all_comments['topic_prob'] = assigned_probs

#  assign topic keywords
def get_top_words(topic_num, top_n=10):
    words = topic_model.get_topic(topic_num)
    return ', '.join([w for w, _ in words[:top_n]]) if words else ''
all_comments["topic_keywords"] = all_comments["topic"].apply(get_top_words)


# ======================
# save model and results

# save model
topic_model.save(model_path)

# save probabilities
np.save(os.path.join(output_folder, "topic_probabilities.npy"), probs)

# save excel file
excel_out = f"{output_folder}/tycktill_with_topics.xlsx"
all_comments.to_excel(excel_out, index=False)

# save geopackage
pts = gpd.GeoDataFrame(
    all_comments,
    geometry=gpd.points_from_xy(all_comments['Koordinater_x'], all_comments['Koordinater_Y']),
    crs=4326
).to_crs("EPSG:3006")
pts.to_file(f"{output_folder}/tycktill_with_topics.gpkg", layer="pts_with_topics", driver="GPKG", mode="w")


# With all rows:
#
# --- Rows before filtering ---
# Loaded 290,505 rows before filtering.
#
# --- Rows after filtering ---
# 290,005 rows remain after filtering short/empty texts.