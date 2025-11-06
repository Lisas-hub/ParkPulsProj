
import os
import pandas as pd
import geopandas as gpd
from bertopic import BERTopic
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import re



# lägg till pts_in_parks här för just nu saknar test3 similarity och matched_topic_?? columner
# utöver "park_overlap", "park_only_keywords", "park_only_topics" spara park_keywords, och park_topics (att ha som input i 8. Themes)




# =====
# paths

model_path = "../data/tycktill_output/BERTopic/bertopic_model"
input_folder = os.path.join("../data", "tycktill_output", "BERTopic")
output_folder = os.path.join("../data", "tycktill_output", "BERTopic_filtered")
output_folder_plots = os.path.join("../data", "tycktill_output", "plots")

# ===================
# load model and data

topic_model = BERTopic.load(model_path)
all_comments = pd.read_excel(f"{input_folder}/tycktill_with_topics.xlsx")
probs = np.load(os.path.join(f"{input_folder}/topic_probabilities.npy"), allow_pickle=True)

# =========
# filtering

keywords_file_path = '../data/keywords.xlsx'
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

# === by geographical location ===

parks = gpd.read_file("../data/VARIABLES_NEW.gpkg", layer="VARIABLES_base").to_crs(3006)

# filter out only points in parks



# === by specific keywords ("supervised") ===      uses clean_Fritext

# function to check if a comment contains any keyword
def find_matched_keywords(text):
    """list of all keywords matched in a comment"""
    text = str(text)
    return [kw for kw in park_keywords if re.search(rf"\b{re.escape(kw)}{swedish_endings}\b", text, flags=re.IGNORECASE)]
def contains_park_keyword(text):
    """if comment contains at least one park keyword"""
    return bool(pattern.search(str(text)))

#pattern = re.compile(r'\b(' + '|'.join(re.escape(kw) for kw in park_keywords) + r')\b')
#def contains_park_keyword(text):
#    return bool(pattern.search(str(text).lower()))   # <<< this works but requires the keyword to be exact, so kronoberkspark will not catch kronobergsparken

#def contains_park_keyword(text):
#    text_lower = str(text).lower()
#    return any(kw in text_lower for kw in park_keywords)     # <<< this included too much, like 'park' could catch 'sparkcykel' because in has 'park' in it

# add new column listing matched keywords
park_comments_by_keyword = all_comments[all_comments["clean_Fritext"].apply(contains_park_keyword)].copy()
park_comments_by_keyword["matched_keywords"] = park_comments_by_keyword["clean_Fritext"].apply(find_matched_keywords)

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
        matched_keywords = [
            kw for kw in park_keywords
            if re.search(rf"\b{re.escape(kw)}{swedish_endings}\b", topic_text, flags=re.IGNORECASE)
        ]
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
park_comments_by_keyword.to_file(f"{output_folder}/tycktill_filtered.gpkg", layer="park_comments_by_keyword", driver="GPKG", mode="w")

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
park_comments_by_topic.to_file(f"{output_folder}/tycktill_filtered.gpkg", layer="park_comments_by_topic", driver="GPKG", mode="w")

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
park_comments_by_topic_and_keyword.to_file(f"{output_folder}/tycktill_filtered.gpkg", layer="park_comments_by_topic_and_keyword", driver="GPKG", mode="w")

# === topic barcharts ===
filtered_topic_ids = park_comments_by_keyword["topic"].unique().tolist()
fig = topic_model.visualize_barchart(
    topics=filtered_topic_ids,
    top_n_topics=len(filtered_topic_ids),
    n_words=5,
    custom_labels=True
)
fig.write_html(f"{output_folder_plots}/topic_barchart_parks_by_keyword.html")

# === intertopic distance map ===
fig = topic_model.visualize_topics(topics=filtered_topic_ids, custom_labels=True)
fig.write_html(f"{output_folder_plots}/intertopic_distance_map_parks_by_keyword.html")

print("\n--- Park related topics by specific words ---")
print(f"Found {len(park_related_topics)} park-related topics.")
print(f"Saved {len(park_comments_by_keyword):,} comments containing park keywords.")
print(f"Saved {len(park_comments_by_topic):,} comments in park-related topics.")
print(f"Saved {len(park_comments_by_topic_and_keyword):,} comments in park_topics AND with keywords.")

# With all rows (OLD):
#
# --- Park related topics by specific words ---
# Found 76 park-related topics.
# Saved 25,204 comments containing park keywords.   <<< USE THIS ONE
# Saved 32,238 comments in park-related topics.
# Saved 11,996 comments in park_topics AND with keywords.
#
# --- Park related topics by BERTopic ---
# Saved 1431 park-related comments                  <<< used only "park" for this one instead of all keywords from excel

# With all rows:
#
#--- Park related topics by specific words ---
#Found 77 park-related topics.
#Saved 26,089 comments containing park keywords.     <<< USE THIS ONE
#Saved 32,311 comments in park-related topics.
#Saved 12,220 comments in park_topics AND with keywords.
#
#--- Park related topics by BERTopic ---
#Saved 56879 park-related comments


# === by the model ("unsupervised") ===       uses topic_keywords

similar_topics_all = []
similarity_all = []

for kw in park_keywords:
    try:
        similar_topics, similarity = topic_model.find_topics(kw, top_n=5)
        similar_topics_all.extend(similar_topics)
        similarity_all.extend(similarity)
    except Exception as e:
        print(f"Skipping keyword '{kw}' due to error: {e}")

topic_similarity_df = pd.DataFrame({
    "topic": similar_topics_all,
    "similarity": similarity_all
}).drop_duplicates(subset=["topic"])

# keep only topics with similarity > 0.3
topic_similarity_df = topic_similarity_df[topic_similarity_df["similarity"] > 0.3]   # *** höj threshold? ELLER ta bort keywords som sandlåda etc ***

# find which Excel keywords matched each topic label
topic_matches = []
for topic_id in topic_similarity_df["topic"]:
    topic_words = [w.lower() for w, _ in topic_model.get_topic(topic_id)]
    topic_text = " ".join(topic_words)
    matched_topic_keywords = [
        kw for kw in park_keywords
        if re.search(rf"\b{re.escape(kw)}{swedish_endings}\b", topic_text, flags=re.IGNORECASE)
    ]
    topic_matches.append({
        "topic": topic_id,
        "matched_topic_keywords": matched_topic_keywords
    })

topic_matches_df = pd.DataFrame(topic_matches)

topic_similarity_df = topic_similarity_df.merge(topic_matches_df, on="topic", how="left")

# filter comments belonging to these topics
park_comments_by_BERTopic = all_comments[
    all_comments["topic"].isin(topic_similarity_df["topic"])
].copy()

park_comments_by_BERTopic = park_comments_by_BERTopic.merge(topic_similarity_df, on="topic", how="left")

park_comments_by_BERTopic = gpd.GeoDataFrame(
    park_comments_by_BERTopic,
    geometry=gpd.points_from_xy(
        park_comments_by_BERTopic["Koordinater_x"],
        park_comments_by_BERTopic["Koordinater_Y"]
    ),
    crs=4326
)
park_comments_by_BERTopic.to_file(f"{output_folder}/tycktill_filtered.gpkg", layer="park_comments_by_BERTopic", driver="GPKG", mode="w")

print("\n--- Park related topics by BERTopic ---")
print(f"Saved {len(park_comments_by_BERTopic)} park-related comments")

# === topic barcharts ===
fig = topic_model.visualize_barchart(
    topics=similar_topics_all,
    top_n_topics=len(similar_topics_all),
    n_words=5,
    custom_labels=True
)
fig.write_html(f"{output_folder_plots}/topic_barchart_parks_by_BERTopic.html")

# === intertopic distance map ===
fig = topic_model.visualize_topics(topics=similar_topics_all, custom_labels=True)
fig.write_html(f"{output_folder_plots}/intertopic_distance_map_parks_by_BERTopic.html")


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
    "Topic Frequency per Month – Park-related Topics (BERTopic similarity)",
    f"{output_folder_plots}/topics_over_time_park_by_BERTopic.png"
)

plot_topics_over_time(
    park_comments_by_keyword,
    "Topic Frequency per Month – Park-related Topics (by keywords)",
    f"{output_folder_plots}/topics_over_time_park_by_keyword.png"
)


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

gdf_overlap.to_file(output_gpkg, layer="park_overlap", driver="GPKG", mode="w")
gdf_only_filter1.to_file(output_gpkg, layer="park_only_keywords", driver="GPKG", mode="w")
gdf_only_filter2.to_file(output_gpkg, layer="park_only_topics", driver="GPKG", mode="w")




# =================================================================
# === adding in points in parks with by_keyword and by_BERTopic ===



