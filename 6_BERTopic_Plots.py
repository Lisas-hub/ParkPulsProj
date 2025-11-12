
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

model_path = "data/tycktill_output/BERTopic/bertopic_model"
input_folder = os.path.join("data", "tycktill_output", "BERTopic")
output_folder = os.path.join("data", "tycktill_output", "plots")

# ===================
# load model and data

topic_model = BERTopic.load(model_path)
all_comments = pd.read_excel(os.path.join(input_folder, "tycktill_with_topics.xlsx"))
probs = np.load(os.path.join(input_folder, "topic_probabilities.npy"), allow_pickle=True)


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
plt.savefig(f"{output_folder}/top5_topics_over_time_months.png", dpi=300, bbox_inches="tight")
plt.show()


# === topic probability ===

fig = topic_model.visualize_distribution(probs[0], min_probability=0.001)
fig.write_html(f"{output_folder}/topic_distribution_doc0.html")
# loop through a few to inspect more
for i in range(5):
    fig = topic_model.visualize_distribution(probs[i], min_probability=0.001)
    fig.write_html(f"{output_folder}/topic_distribution_doc{i}.html")


# === top 5 topics in park polygons ===


