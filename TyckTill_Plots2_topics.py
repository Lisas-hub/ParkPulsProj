
import os
import pandas as pd
import geopandas as gpd
from bertopic import BERTopic
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import re

# =====
# paths

output_folder = os.path.join("data", "tycktill_output")

model_path = "data/tycktill_output/bertopic_model"

data_path = f"{output_folder}/tycktill_with_topics.xlsx"

# ===================
# load model and data

topic_model = BERTopic.load(model_path)
all_comments = pd.read_excel(data_path)
probs = np.load(os.path.join(output_folder, "topic_probabilities.npy"), allow_pickle=True)

# ==============
# visualizations

# === topic barcharts ===
fig = topic_model.visualize_barchart(top_n_topics=20)
fig.write_html(f"{output_folder}/topic_barchart.html")

# === intertopic distance map ===
fig = topic_model.visualize_topics()
fig.write_html(f"{output_folder}/intertopic_distance_map.html")

# === topics over time ===
#all_comments["Inkommet datum"] = pd.to_datetime(all_comments["Inkommet datum"])        # *** remove section? it's not working properly because Inkommet datum has issues ***

#topics_over_time_df = topic_model.topics_over_time(
#    docs=all_comments["clean_Fritext"].tolist(),
#    timestamps=all_comments["Inkommet datum"],
#    global_tuning=True
#)

#fig = topic_model.visualize_topics_over_time(topics_over_time_df, top_n_topics=20)
#fig.write_html(f"{output_folder}/topics_over_time_all.html")

#for year_label, subset in all_comments.groupby("custom_year"):
#    topics_over_time_df = topic_model.topics_over_time(
#        docs=subset["clean_Fritext"].tolist(),
#        timestamps=subset["Inkommet datum"],
#        global_tuning=True
#    )
#    fig = topic_model.visualize_topics_over_time(topics_over_time_df, top_n_topics=20)
#    fig.write_html(f"{output_folder}/topics_over_time_{year_label}.html")


# === alt to BERTopics own topics over time ===
# BERTopic topics over time requires the format that is in Inkommet datum but it causes error so using seaborn is an alternative way BUT it's not dynamic like BERTopic visualisations

tycktill_with_topics = pd.read_excel(f"{output_folder}\\tycktill_with_topics.xlsx", parse_dates=["Inkommet datum"])

# group topic counts per month per custom year
grouped_topics = (
    all_comments.groupby(['year_label', 'month', 'topic'])
    .size()
    .reset_index(name='count')
)

top_topics = (
    grouped_topics.groupby('topic')['count']
    .sum()
    .nlargest(5)
    .index
)

grouped_topics = grouped_topics[grouped_topics['topic'].isin(top_topics)]
grouped_topics['topic'] = grouped_topics['topic'].astype(str)

month_order = [6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5]
month_labels = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
               "Dec", "Jan", "Feb", "Mar", "Apr", "May"]
month_to_custom_order = {month: i for i, month in enumerate(month_order)}

grouped_topics['month_order'] = grouped_topics['month'].map(month_to_custom_order)

# plot
sns.set(style='whitegrid')
fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
fig.suptitle("Topic Frequency per Month for Top 5 Topics", fontsize=16)

years = grouped_topics['year_label'].unique()
for ax, year in zip(axes, years):
    subset = grouped_topics[grouped_topics['year_label'] == year]
    sns.lineplot(
        data=subset.sort_values('month_order'),
        x='month_order',
        y='count',
        hue='topic',
        marker='o',
        ax=ax,
        legend=True
    )
    ax.set_title(f"{year}")
    ax.set_xlabel("Month")
    ax.set_ylabel("Comment Count")
    ax.set_xticks(range(12))
    ax.set_xticklabels(month_labels, rotation=0)
plt.tight_layout()
plt.show()


# === topic probability ===

topic_model = BERTopic.load(model_path)
all_comments = pd.read_excel(f"{output_folder}/tycktill_with_topics.xlsx")
probs = np.load(f"{output_folder}/topic_probabilities.npy", allow_pickle=True)

fig = topic_model.visualize_distribution(probs[0], min_probability=0.001)
fig.write_html(f"{output_folder}/topic_distribution_doc0.html")
# loop through a few to inspect more
for i in range(5):
    fig = topic_model.visualize_distribution(probs[i], min_probability=0.001)
    fig.write_html(f"{output_folder}/topic_distribution_doc{i}.html")


# =========
# filtering

# === by specific keywords ("supervised") ===
keywords_file_path = 'data/keywords.xlsx'
selected_sheets = ['Sheet1', 'Sheet2', 'Sheet3', 'Sheet4']

park_keywords = []
for sheet in selected_sheets:
    df = pd.read_excel(keywords_file_path, sheet_name=sheet, usecols=[0])
    park_keywords.extend(df.iloc[:, 0].dropna().tolist())

park_keywords = list(set([w.strip().lower() for w in park_keywords]))

swedish_endings = r'(en|et|ar|er|or|na|n|s)?'
pattern = re.compile(
    r'\b(' + '|'.join(
        rf"{re.escape(kw)}{swedish_endings}" for kw in park_keywords
    ) + r')\b',
    flags=re.IGNORECASE
)

# function to check if a comment contains any keyword
def contains_park_keyword(text):
    return bool(pattern.search(str(text)))

#pattern = re.compile(r'\b(' + '|'.join(re.escape(kw) for kw in park_keywords) + r')\b')
#def contains_park_keyword(text):
#    return bool(pattern.search(str(text).lower()))   # <<< this works but requires the keyword to be exact, so kronoberkspark will not catch kronobergsparken

#def contains_park_keyword(text):
#    text_lower = str(text).lower()
#    return any(kw in text_lower for kw in park_keywords)     # <<< this included too much, like 'park' could catch 'sparkcykel' because in has 'park' in it

# find topics that are park-related (based on topic keywords)
park_related_topics = []
for topic_id in topic_model.get_topics().keys():
    if topic_id == -1:
        continue
    topic_words = [w.lower() for w, _ in topic_model.get_topic(topic_id)]
    topic_text = " ".join(topic_words)
    # if any park keyword (with endings) matches the topic words
    if pattern.search(topic_text):
        park_related_topics.append(topic_id)

# print what keywords got picked up in park topics
matched_keywords = [kw for kw in park_keywords if re.search(rf"\b{re.escape(kw)}{swedish_endings}\b", topic_text, flags=re.IGNORECASE)]
if matched_keywords:
    park_related_topics.append(topic_id)
    print(f"Topic {topic_id} matched with: {matched_keywords}")

# save all comments that contain a park keyword (regardless of topic)
park_comments_by_keyword = all_comments[all_comments["clean_Fritext"].apply(contains_park_keyword)]
park_comments_by_keyword.to_excel(f"{output_folder}/park_comments_by_park_keywords.xlsx", index=False)
park_comments_by_keyword = gpd.GeoDataFrame(
    park_comments_by_keyword, geometry=gpd.points_from_xy(
        park_comments_by_keyword['Koordinater_x'],
        park_comments_by_keyword['Koordinater_Y']
    ),
    crs=4326)
park_comments_by_topic_and_keyword = park_comments_by_keyword.to_crs("EPSG:3006")
park_comments_by_keyword.to_file("data/tycktill_output/tycktill.gpkg", layer="park_comments_by_keyword", driver="GPKG", mode="w")

# save all comments belonging to a park topic (regardless of keyword presence in individual comments)
park_comments_by_topic = all_comments[all_comments["topic"].isin(park_related_topics)]
park_comments_by_topic.to_excel(f"{output_folder}/park_comments_by_park_topics.xlsx", index=False)
park_comments_by_topic = gpd.GeoDataFrame(
    park_comments_by_topic, geometry=gpd.points_from_xy(
        park_comments_by_topic['Koordinater_x'],
        park_comments_by_topic['Koordinater_Y']
    ),
    crs=4326)
park_comments_by_topic = park_comments_by_topic.to_crs("EPSG:3006")
park_comments_by_topic.to_file("data/tycktill_output/tycktill.gpkg", layer="park_comments_by_topic", driver="GPKG", mode="w")

# save comments that BOTH contain a keyword AND belong to a park topic
park_comments_by_topic_and_keyword = park_comments_by_topic[
    park_comments_by_topic["clean_Fritext"].apply(contains_park_keyword)
]
park_comments_by_topic_and_keyword.to_excel(f"{output_folder}/park_comments_by_topic_and_keyword.xlsx", index=False)
park_comments_by_topic_and_keyword = gpd.GeoDataFrame(
    park_comments_by_topic_and_keyword, geometry=gpd.points_from_xy(
        park_comments_by_topic_and_keyword['Koordinater_x'],
        park_comments_by_topic_and_keyword['Koordinater_Y']
    ),
    crs=4326)
park_comments_by_topic_and_keyword = park_comments_by_topic_and_keyword.to_crs("EPSG:3006")
park_comments_by_topic_and_keyword.to_file("data/tycktill_output/tycktill.gpkg", layer="park_comments_by_topic_and_keyword", driver="GPKG", mode="w")

# === topic barcharts ===
filtered_topic_ids = park_comments_by_topic_and_keyword["topic"].unique().tolist()
fig = topic_model.visualize_barchart(
    topics=filtered_topic_ids,
    top_n_topics=len(filtered_topic_ids),
    n_words=5,
    custom_labels=True
)
fig.write_html(f"{output_folder}/topic_barchart_parks_by_topic_and_keyword.html")

# === intertopic distance map ===
fig = topic_model.visualize_topics(topics=filtered_topic_ids, custom_labels=True)
fig.write_html(f"{output_folder}/intertopic_distance_map_parks_by_topic_and_keyword.html")

print("\n--- Park related topics by specific words ---")
print(f"Found {len(park_related_topics)} park-related topics.")
print(f"Saved {len(park_comments_by_keyword):,} comments containing park keywords.")
print(f"Saved {len(park_comments_by_topic):,} comments in park-related topics.")
print(f"Saved {len(park_comments_by_topic_and_keyword):,} comments in park_topics AND with keywords.")

# With all rows:
#
# --- Park related topics by specific words ---
# Found 76 park-related topics.
# Saved 25,204 comments containing park keywords.
# Saved 32,238 comments in park-related topics.
# Saved 11,996 comments in park_topics AND with keywords.
#
# --- Park related topics by BERTopic ---
# Saved 1431 park-related comments


# === by the model ("unsupervised") ===

similar_topics, similarity = topic_model.find_topics("park", top_n=5)

topic_similarity_df = pd.DataFrame({
    "topic": similar_topics,
    "park_similarity": similarity
})

filtered_comments = tycktill_with_topics[tycktill_with_topics["topic"].isin(similar_topics)].copy()

filtered_comments = filtered_comments.merge(topic_similarity_df, on="topic", how="left")

park_comments_by_BERTopic = gpd.GeoDataFrame(
    filtered_comments,
    geometry=gpd.points_from_xy(
        filtered_comments["Koordinater_x"],
        filtered_comments["Koordinater_Y"]
    ),
    crs=4326
)
park_comments_by_BERTopic.to_file("data/tycktill_output/tycktill.gpkg", layer="park_comments_by_BERTopic", driver="GPKG", mode="w")

print("\n--- Park related topics by BERTopic ---")
print(f"Saved {len(filtered_comments)} park-related comments")

# === topic barcharts ===
fig = topic_model.visualize_barchart(
    topics=similar_topics,
    top_n_topics=len(similar_topics),
    n_words=5,
    custom_labels=True
)
fig.write_html(f"{output_folder}/topic_barchart_parks_by_BERTopic.html")

# === intertopic distance map ===
fig = topic_model.visualize_topics(topics=similar_topics, custom_labels=True)
fig.write_html(f"{output_folder}/intertopic_distance_map_parks_by_BERTopic.html")


# === topics over time for filtered park comments ===

def plot_topics_over_time(df, title, output_path):

    df["Inkommet datum"] = pd.to_datetime(df["Inkommet datum"], errors="coerce")
    df = df.dropna(subset=["Inkommet datum", "topic", "year_label"])

    df["month"] = df["Inkommet datum"].dt.month

    grouped = (
        df.groupby(["year_label", "month", "topic"])
        .size()
        .reset_index(name="count")
    )

    # --- pick top topics within this filtered dataset ---
    top_topics = (
        grouped.groupby("topic")["count"]
        .sum()
        .nlargest(5)
        .index
    )
    grouped = grouped[grouped["topic"].isin(top_topics)]
    grouped["topic"] = grouped["topic"].astype(str)

    # --- Custom month order (June–May) ---
    month_order = [6,7,8,9,10,11,12,1,2,3,4,5]
    month_labels = ["Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar","Apr","May"]
    month_to_custom_order = {m: i for i, m in enumerate(month_order)}
    grouped["month_order"] = grouped["month"].map(month_to_custom_order)

    # --- plot ---
    sns.set(style="whitegrid")
    year_labels = sorted(grouped["year_label"].unique())
    fig, axes = plt.subplots(1, len(year_labels), figsize=(7 * len(year_labels), 5), sharey=True)
    if len(year_labels) == 1:
        axes = [axes]

    fig.suptitle(title, fontsize=16)
    for ax, yl in zip(axes, year_labels):
        subset = grouped[grouped["year_label"] == yl]
        sns.lineplot(
            data=subset.sort_values("month_order"),
            x="month_order",
            y="count",
            hue="topic",
            marker="o",
            ax=ax
        )
        ax.set_title(yl)
        ax.set_xlabel("Month")
        ax.set_ylabel("Comment Count")
        ax.set_xticks(range(12))
        ax.set_xticklabels(month_labels)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.show()


# --- apply to filtered datasets ---
plot_topics_over_time(
    park_comments_by_BERTopic,
    "Topic Frequency per Month – Park-related Topics (BERTopic Similarity)",
    f"{output_folder}/topics_over_time_park_by_BERTopic.png"
)

plot_topics_over_time(
    park_comments_by_topic_and_keyword,
    "Topic Frequency per Month – Park Topics + Keywords",
    f"{output_folder}/topics_over_time_park_by_topic_and_keyword.png"
)
