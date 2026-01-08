
import pandas as pd
import geopandas as gpd
import seaborn as sns
import matplotlib.pyplot as plt
from bertopic import BERTopic

model_path = "data/tycktill_output/BERTopic/bertopic_model"
output_folder = "data/tycktill_output/BERTopic_filtered"
output_folder_plots = "data/tycktill_output/plots"

topic_model = BERTopic.load(model_path)

datasets = {
    "by_keyword": "park_comments_by_keyword",
    "by_BERTopic": "park_comments_by_BERTopic",
    "by_location": "pts_in_parks_with_topics"
}

for key, layer in datasets.items():
    gdf = gpd.read_file(f"{output_folder}/tycktill_filtered.gpkg", layer=layer)
    filtered_topics = gdf["topic"].dropna().unique().tolist()

    # barchart
    fig = topic_model.visualize_barchart(
        topics=filtered_topics, n_words=5, custom_labels=True
    )
    fig.write_html(f"{output_folder_plots}/barchart_{key}.html")

    # intertopic distance map
    fig = topic_model.visualize_topics(topics=filtered_topics, custom_labels=True)
    fig.write_html(f"{output_folder_plots}/intertopic_distance_{key}.html")

    # top 5 topics over time
    gdf["Inkommet datum"] = pd.to_datetime(gdf["Inkommet datum"], errors="coerce")
    gdf["month"] = gdf["Inkommet datum"].dt.month
    grouped = (
        gdf.groupby(["year_label", "month", "topic"])
        .size().reset_index(name="count")
    )
    top_topics = grouped.groupby("topic")["count"].sum().nlargest(5).index
    grouped = grouped[grouped["topic"].isin(top_topics)]

    sns.set(style="whitegrid")
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=grouped, x="month", y="count", hue="topic", marker="o")
    plt.title(f"Top 5 Topics Over Time – {key}")
    plt.xlabel("Month")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(f"{output_folder_plots}/topics_over_time_{key}.png", dpi=300)
    plt.close()