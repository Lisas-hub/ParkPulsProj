import geopandas as gpd
import pandas as pd

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

# ==== OTHER STATS ====
def OTHER_STATS_park_coverage():

    # == park coverage in Stockholm ==
    municipality = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\Kommun_Stadskartan.gpkg").to_crs(layer2.crs)

    # union of parks and municipality
    park_coverage = gpd.overlay(municipality, layer2, how='union') # OBS! mismatch between parks and municipality boundary, small pieces of some parks are outside of the boundary and got group_temp null

    # remove polygons outside the municipality boundary
    park_coverage = gpd.clip(park_coverage, municipality)

    # drop all unnecessary columns by selecting only relevant columns
    park_coverage = park_coverage[["geometry"]]

    # calculate area
    park_coverage ['area'] = park_coverage.geometry.area

    park_coverage['group'] = 0  # default value
    park_coverage.loc[park_coverage['area'] > 100000000, 'group'] = 1 # assign 1 to the largest polygon, aka the one that is not a polygon

    # dissolve all polygons from layer2 into one single polygon
    #park_coverage = park_coverage.dissolve(by="group", as_index=False) # *** fix so that all group = 0 are not lost in this step




    return park_coverage
park_coverage = OTHER_STATS_park_coverage()
park_coverage.to_file("data/VARIABLES_NEW.gpkg", layer="park_coverage", driver="GPKG", mode="w")

# ==== PARK MAINTENANCE ====
def THEME_park_maintenance_to_layer2(layer2):

    # start here


    return layer2
layer2 = THEME_park_maintenance_to_layer2(layer2)



layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_temporary", driver="GPKG", mode="w")






# ================================
# rest från TyckTill_Processing1A.py

# =======================
# word count per Kategori
category_word_freq_all = {} # create a dictionary for storage

for category, group in subset_tycktill_df.groupby("Kategori"):
    lemmas_all = [lemma for lemmas_list in group["lemmas"] for lemma in lemmas_list]
    word_freq_all = Counter(lemmas_all)
    category_word_freq_all[category] = word_freq_all

for category, frequencies in category_word_freq_all.items():
    print(f"\nCategory: {category}")
    for word, count in frequencies.most_common(5):
        print(f"{word}: {count}")

# word frequency plots
# bar chart
for category, frequencies in category_word_freq_all.items():
    common = frequencies.most_common(10)
    words, counts = zip(*common)

    plt.figure(figsize=(10, 4))
    plt.bar(words, counts)
    plt.title(f"Top words in category: {category}")
    plt.xticks(rotation=45)
    plt.tight_layout()

    safe_category = category.replace(" ", "_").replace("/", "_")
    #plt.savefig(f"{output_folder}/barchart_{safe_category}.png", dpi=300, bbox_inches="tight")
    plt.show()

# word cloud
for category, frequencies in category_word_freq_all.items():
    wordcloud = WordCloud(width=800, height=400).generate_from_frequencies(frequencies)

    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis("off")
    plt.title(f"Word cloud for {category}")
    plt.tight_layout()

    safe_category = category.replace(" ", "_").replace("/", "_")
    #plt.savefig(f"{output_folder}/wordcloud_{safe_category}.png", dpi=300, bbox_inches="tight")
    plt.show()

# inside parks vs outside (1 june 2023 - 30 may 2024   vs   1 june 2024 - 30 may 2025)
grouped = subset_tycktill_df.groupby(["year_label", "in_park"])
word_freqs = {}
for (year_label, in_park), group in grouped:
    all_lemmas = [lemma for lemmas in group["lemmas"] for lemma in lemmas]
    freq = Counter(all_lemmas)
    label = ("In Park" if in_park else "Outside Park")
    word_freqs[(year_label, label)] = freq

year_labels = ["June 2023–May 2024", "June 2024–May 2025"]

for year_label in year_labels:
    in_freq = word_freqs.get((year_label, "In Park"), Counter())
    out_freq = word_freqs.get((year_label, "Outside Park"), Counter())

    combined = in_freq + out_freq
    top_words = [word for word, _ in combined.most_common(10)]

    total_in = sum(in_freq.values())
    total_out = sum(out_freq.values())
    normalized_freq_data = {
        "In Park": [in_freq.get(word, 0) / total_in * 100 for word in top_words],
        "Outside Park": [out_freq.get(word, 0) / total_out * 100 for word in top_words],
    }

    freq_df = pd.DataFrame(normalized_freq_data, index=top_words)

    freq_df.plot(kind="bar", figsize=(12, 6))
    plt.title(f"Top 10 Words in {year_label}: In Park vs Outside Park")
    plt.xlabel("Word")
    plt.ylabel("Frequency")
    plt.xticks(rotation=45)
    plt.legend(title="Location")
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    #plt.savefig(f"{output_folder}/word_freq_{year_label}.png", dpi=300, bbox_inches="tight")
    plt.show()

# =======================
# word count by date/time

monthly_counts = subset_tycktill_df.groupby("month").size()
print(monthly_counts)

weekday_counts = subset_tycktill_df["weekday"].value_counts()
print(weekday_counts)

# date/time plots
# entries per month for 2023 and 2024
month_order_nums = [6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5]
month_labels = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
               "Dec", "Jan", "Feb", "Mar", "Apr", "May"]
month_to_custom_order = {month: i for i, month in enumerate(month_order_nums)}

monthly_counts = subset_tycktill_df.groupby(["year_label", "month"]).size().reset_index(name="count")
monthly_counts["month_order"] = monthly_counts["month"].map(month_to_custom_order)

monthly_counts = monthly_counts.sort_values(["year_label", "month_order"])

plt.figure(figsize=(10, 5))
for year in monthly_counts["year_label"].unique():
    year_data = monthly_counts[monthly_counts["year_label"] == year]     # get only that year's data
    year_data = year_data.sort_values("month_order")

    plt.plot(
        year_data["month_order"],
        year_data["count"],
        label=str(year),
        marker='o'
    )

plt.xticks(ticks=range(12), labels=month_labels)
plt.title("Entries per Month (by Year)")
plt.xlabel("Month")
plt.ylabel("Count")
plt.legend()
plt.grid(True)
plt.tight_layout()
#plt.savefig(f"{output_folder}/entries_per_month_plot.png", dpi=300, bbox_inches="tight")
plt.show()

# entries per weekday for 2023 and 2024
weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
weekday_to_num = {day: i for i, day in enumerate(weekday_order)}

subset_tycktill_df["weekday_num"] = subset_tycktill_df["weekday"].map(weekday_to_num)                   # map weekday names to numbers
weekday_counts = subset_tycktill_df.groupby(["year_label", "weekday"]).size().reset_index(name="count") # group weekday counts to year
weekday_counts["weekday_num"] = weekday_counts["weekday"].map(weekday_to_num)
weekday_counts = weekday_counts.sort_values(["year_label", "weekday_num"])

plt.figure(figsize=(10, 5))
for year in weekday_counts["year_label"].unique():
    year_data = weekday_counts[weekday_counts["year_label"] == year]
    year_data = year_data.sort_values("weekday_num")
    plt.plot(year_data["weekday"], year_data["count"], label=str(year), marker='o')

plt.xticks(ticks=range(7), labels=weekday_order)

plt.title("Entries per Weekday (by Year)")
plt.xlabel("Weekday")
plt.ylabel("Count")
plt.legend()
plt.grid(True)
plt.tight_layout()
#plt.savefig(f"{output_folder}/entries_per_weekday_plot.png", dpi=300, bbox_inches="tight")
plt.show()


# stacked bar chart of number of entries per Kategori inside and outside parks for each time period
grouped = (
    subset_tycktill_df.groupby(['year_label', 'in_park', 'Kategori'])
      .size()
      .reset_index(name='count')
)

pivoted = grouped.pivot_table(
    index=['year_label', 'in_park'],
    columns='Kategori',
    values='count',
    fill_value=0
)

pivoted.index = pivoted.index.map(lambda x: f"{x[0]}\nIn park: {x[1]}")

pivoted.plot(
    kind='bar',
    stacked=True,
    figsize=(10, 6),
    colormap='tab20'
)

plt.title('Stacked Category Counts by Period and In-Park Status')
plt.xlabel('Period and In-Park Status')
plt.ylabel('Count')
plt.xticks(rotation=45, ha='right')
plt.legend(title='Category', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()
#plt.savefig(f"{output_folder}/entries_per_year_stacked_bar_plot.png", dpi=300, bbox_inches="tight")
plt.show()




# ===============
# sentiment plots

# bar chart inside vs outside parks for sentiment labels
plt.figure(figsize=(8, 5))
sns.countplot(data=subset_tycktill_df, x="sentiment_label", hue="in_park")
plt.title("Sentiment inside vs outside parks")
#plt.savefig(f"{output_folder}/sentiment_inside_vs_outside_parks.png", dpi=300, bbox_inches="tight")
plt.show()

# line chart of sentiment labels, time period, weekday
weekday_order = [1, 2, 3, 4, 5, 6, 7]
df_23_24 = subset_tycktill_df[subset_tycktill_df["year_label"] == "June 2023–May 2024"]
df_24_25 = subset_tycktill_df[subset_tycktill_df["year_label"] == "June 2024–May 2025"]

grouped_23_24 = (
    df_23_24.groupby(["weekday_num", "sentiment_label"])
    .size()
    .unstack()
    .reindex(weekday_order)
    .fillna(0)
)

grouped_24_25 = (
    df_24_25.groupby(["weekday_num", "sentiment_label"])
    .size()
    .unstack()
    .reindex(weekday_order)
    .fillna(0)
)

fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)

grouped_23_24.plot(ax=axes[0], marker="o")
axes[0].set_title("Sentiment by Weekday (2023–2024)")
axes[0].set_xlabel("Weekday (1 = Monday)")
axes[0].set_ylabel("Count")
axes[0].set_xticks(ticks=range(7), labels=weekday_order)
axes[0].legend(title="Sentiment")

grouped_24_25.plot(ax=axes[1], marker="o")
axes[1].set_title("Sentiment by Weekday (2024–2025)")
axes[1].set_xlabel("Weekday (1 = Monday)")
axes[1].set_xticks(ticks=range(7), labels=weekday_order)
axes[1].legend(title="Sentiment")

plt.tight_layout()
plt.show()


# =======================








