
# natural language processing (NLP) packages
import nltk # has some swedish, use for stopwords and maybe more
import spacy # has swedish but maybe better suited for other types of projects than scentific ones?
import stanza # good for Swedish? uses Talbanken?

# additional/other packages
import pandas as pd
import numpy as np
from collections import Counter
import geopandas as gpd
from shapely.geometry import Point
import folium
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import os

from nltk.corpus import stopwords

# downloads
#nltk.download('punkt')
#nltk.download('stopwords')
#stanza.download('sv')

# ===============================
# === LOAD PRE-PROCESSED DATA ===

tycktill_df = pd.read_excel("data/cleaned_dataset.xlsx")

# ============================================
# === TOKENIZE / POS-TAG / LEMMATIZE / ETC ===

# ==============
# load stopwords
stop_words = set(stopwords.words("swedish"))

# ======================
# create geometry column

tycktill_df["geometry"] = tycktill_df.apply(lambda row: Point(row["Koordinater_x"], row["Koordinater_Y"]), axis=1)
tycktill_df_geo = gpd.GeoDataFrame(tycktill_df, geometry="geometry", crs="EPSG:4326").to_crs("EPSG:3006")

# =================================================
# prepp for filtering inside or outside parks later
print("Prepping for filtering...")
parks = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

#tycktill_df_geo["in_park"] = tycktill_df_geo.geometry.within(parks.geometry.union_all()) *super slow so use sjoin instead
subset_within_parks = gpd.sjoin(tycktill_df_geo, parks, how="inner", predicate="within")
tycktill_df_geo["in_park"] = tycktill_df_geo.index.isin(subset_within_parks.index)

# ============================================
# subset by parks and a limited number of rows

# subset tycktill dataset to begin with before committing to processing all 300000+ rows
#subset_tycktill_df = tycktill_df.head(50).copy() # uses 50 first rows (only from 2023)   * remove? old
#subset_tycktill_df = subset_within_parks.sample(n=50).copy() # uses 500 random rows      * remove? old
#subset_tycktill_df = tycktill_df.sample(n=50).copy()                                     * remove? old

n_points = 50

sample_in = tycktill_df_geo[tycktill_df_geo["in_park"]].sample(n=n_points, random_state=1) # in_park = true
sample_out = tycktill_df_geo[~tycktill_df_geo["in_park"]].sample(n=n_points, random_state=1) # in_park = false

subset_tycktill_df = pd.concat([sample_in, sample_out]).copy() # get an equal number from within and outside parks

# set up for saving figures based on number of points in the subset
output_folder = f"data/tyck_till_plots/sample_{n_points * 2}_points"
os.makedirs(output_folder, exist_ok=True)


# ============
# NLP pipeline
nlp = stanza.Pipeline("sv", processors="tokenize,pos,lemma")

lemmatized_rows = []
for i, row in subset_tycktill_df.iterrows():
    print(f"Processing row {i + 1} of {len(subset_tycktill_df)}", flush=True)

    text = row["clean_Fritext"]

    doc = nlp(text)
    lemmas = [
        word.lemma for sentence in doc.sentences for word in sentence.words
        if word.upos != "PUNCT" and word.text.casefold() not in stop_words
    ]

    lemmatized_rows.append(lemmas)

subset_tycktill_df["lemmas"] = lemmatized_rows

# ============================================
# separate between inside and outside of parks

lemmas_in = [lemma for row in subset_tycktill_df[subset_tycktill_df["in_park"]]["lemmas"] for lemma in row]
lemmas_out = [lemma for row in subset_tycktill_df[~subset_tycktill_df["in_park"]]["lemmas"] for lemma in row]

# ======================
# === WORD FREQUENCY ===

lemmas_all = [lemma for lemmas_list in subset_tycktill_df["lemmas"] for lemma in lemmas_list]
lemmas_in = [lemma for lemmas_list in subset_tycktill_df[subset_tycktill_df["in_park"]]["lemmas"] for lemma in lemmas_list]
lemmas_out = [lemma for lemmas_list in subset_tycktill_df[~subset_tycktill_df["in_park"]]["lemmas"] for lemma in lemmas_list]

# ================
# total word count
# (every occurence regardless of row, so if multiple per row they are all counted)
word_freq_all = Counter(lemmas_all)
word_freq_in = Counter(lemmas_in)
word_freq_out = Counter(lemmas_out)

print("\n--- Top Words All ---")
for word, freq in word_freq_all.most_common(10):
    print(f"{word}: {freq}")

print("\n--- Top Words Inside Parks ---")
for word, freq in word_freq_in.most_common(10):
    print(f"{word}: {freq}")

print("\n--- Top Words Outside Parks ---")
for word, freq in word_freq_out.most_common(10):
    print(f"{word}: {freq}")

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
    plt.savefig(f"{output_folder}/barchart_{safe_category}.png", dpi=300, bbox_inches="tight")
    #plt.show()

# word cloud
for category, frequencies in category_word_freq_all.items():
    wordcloud = WordCloud(width=800, height=400).generate_from_frequencies(frequencies)

    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis("off")
    plt.title(f"Word cloud for {category}")
    plt.tight_layout()

    safe_category = category.replace(" ", "_").replace("/", "_")
    plt.savefig(f"{output_folder}/wordcloud_{safe_category}.png", dpi=300, bbox_inches="tight")
    #plt.show()

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
    plt.savefig(f"{output_folder}/word_freq_{year_label}.png", dpi=300, bbox_inches="tight")
    #plt.show()

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
plt.savefig(f"{output_folder}/entries_per_month_plot.png", dpi=300, bbox_inches="tight")
#plt.show()

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
plt.savefig(f"{output_folder}/entries_per_weekday_plot.png", dpi=300, bbox_inches="tight")
#plt.show()


# ========



# =======================