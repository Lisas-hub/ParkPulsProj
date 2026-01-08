
import os
import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering

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
n_meta = 30  # or whatever makes sense
clustering = AgglomerativeClustering(n_clusters=n_meta)
meta_labels = clustering.fit_predict(topic_embeddings)

# map topic ID → meta-topic
topic_to_meta = pd.DataFrame({
    "topic": topic_info["Topic"],   # topic ID
    "meta_topic": meta_labels
})

# assign meta-topic to documents
all_comments = all_comments.merge(topic_to_meta, on="topic", how="left")

# now all_comments has a 'meta_topic' column ready for co-occurrence

