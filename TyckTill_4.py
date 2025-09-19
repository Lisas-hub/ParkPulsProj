
# natural language processing (NLP) packages
import nltk # has some swedish, use for stopwords and maybe more
import spacy # has swedish but maybe better suited for other types of projects than scentific ones?
import stanza # good for Swedish? uses Talbanken?

# other packages
import pandas as pd
import numpy as np
from collections import Counter
import geopandas as gpd
from shapely.geometry import Point
import folium
import matplotlib.pyplot as plt
from wordcloud import WordCloud

from nltk.corpus import stopwords

# downloads
#nltk.download('punkt')
#nltk.download('stopwords')
#stanza.download('sv')


tycktill_df = pd.read_excel(r'C:\Users\lisajos\QGIS_Projects\TyckTill\NEW\TyckTill_2023-01-01_2024-12-31.xlsx')

# ============================================
# === PRE PROCESSING OF ADDITIONAL COLUMNS ===

# =========
# Kategori

# nothing to fix

# =====================================
# date and time column (Inkommet datum)

# convert to appropriate datetime format
tycktill_df["Inkommet datum"] = pd.to_datetime(tycktill_df["Inkommet datum"], errors="coerce")

# extract date (or time) only
tycktill_df["year"] = tycktill_df["Inkommet datum"].dt.year
tycktill_df["month"] = tycktill_df["Inkommet datum"].dt.month
tycktill_df["day"] = tycktill_df["Inkommet datum"].dt.day
tycktill_df["weekday"] = tycktill_df["Inkommet datum"].dt.day_name()
tycktill_df["hour"] = tycktill_df["Inkommet datum"].dt.hour

# ===========
# coordinates

# handle 0 and null
tycktill_df["Koordinater_x"] = tycktill_df["Koordinater_x"].replace(0, np.nan)
tycktill_df["Koordinater_Y"] = tycktill_df["Koordinater_Y"].replace(0, np.nan)

# =================================
# === PRE PROCESSING OF FRITEXT ===

# FILTERING (removing rows that don't need to be included)

# keep rows that have something in them + remove empty space in the beginning or end of cells and remove any rows that don't have anything left after this
tycktill_df = tycktill_df[tycktill_df["Fritext"].notna() & tycktill_df["Fritext"].str.strip().ne("")]

# remove rows with numbers or symbols (incl emojis) and no text, in other words remove all rows without at least one letter
import re
tycktill_df = tycktill_df[tycktill_df["Fritext"].apply(lambda x: re.search(r"[a-zA-ZåäöÅÄÖ]", str(x)) is not None)]

# make all text lowercase
tycktill_df["clean_Fritext"] = tycktill_df["Fritext"].str.lower()

# clean up text that includes certain symbols or emojis by removing them but keeping the text
tycktill_df["clean_Fritext"] = tycktill_df["clean_Fritext"].str.replace(r"[^a-zA-ZåäöÅÄÖ0-9\s]", "", regex=True)

tycktill_df.to_excel("data/cleaned_dataset.xlsx")

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

sample_in = tycktill_df_geo[tycktill_df_geo["in_park"]].sample(n=50, random_state=1) # in_park = true
sample_out = tycktill_df_geo[~tycktill_df_geo["in_park"]].sample(n=50, random_state=1) # in_park = false

subset_tycktill_df = pd.concat([sample_in, sample_out]).copy() # get an equal number from within and outside parks

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
    #plt.savefig(f"data/subset5000_random_inParks/barchart_{safe_category}.png", dpi=300, bbox_inches="tight")
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
    #plt.savefig(f"data/subset5000_random_inParks/wordcloud_{safe_category}.png", dpi=300, bbox_inches="tight")
    plt.show()

# inside parks vs outside (2023 vs 2024)
grouped = subset_tycktill_df.groupby(["year", "in_park"])
word_freqs = {}
for (year, in_park), group in grouped:
    all_lemmas = [lemma for lemmas in group["lemmas"] for lemma in lemmas]
    freq = Counter(all_lemmas)
    label = ("In Park" if in_park else "Outside Park")
    word_freqs[(year, label)] = freq

years = [2023, 2024]

for year in years:
    in_freq = word_freqs.get((year, "In Park"), Counter())
    out_freq = word_freqs.get((year, "Outside Park"), Counter())

    combined = in_freq + out_freq
    top_words = [word for word, _ in combined.most_common(10)]

    freq_data = {
        "In Park": [in_freq.get(word, 0) for word in top_words],
        "Outside Park": [out_freq.get(word, 0) for word in top_words],
    }

    freq_df = pd.DataFrame(freq_data, index=top_words)

    freq_df.plot(kind="bar", figsize=(12, 6))
    plt.title(f"Top 10 Words in {year}: In Park vs Outside Park")
    plt.xlabel("Word")
    plt.ylabel("Frequency")
    plt.xticks(rotation=45)
    plt.legend(title="Location")
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    #plt.savefig()
    plt.show()

# =======================
# word count by date/time

monthly_counts = subset_tycktill_df.groupby("month").size()
print(monthly_counts)

weekday_counts = subset_tycktill_df["weekday"].value_counts()
print(weekday_counts)

# date/time plots
# entries per month for 2023 and 2024
monthly_counts = subset_tycktill_df.groupby(["year", "month"]).size().reset_index(name="count")

plt.figure(figsize=(10, 5))
for year in monthly_counts["year"].unique():
    year_data = monthly_counts[monthly_counts["year"] == year]                      # get only that year's data
    plt.plot(year_data["month"], year_data["count"], label=str(year), marker='o')   # use month numbers to keep order correct

plt.xticks(ticks=range(1, 13), labels=[
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
])
plt.title("Entries per Month (by Year)")
plt.xlabel("Month")
plt.ylabel("Count")
plt.legend()
plt.grid(True)
plt.tight_layout()
#plt.savefig("data/subset5000_random_inParks/entries_per_month_plot.png", dpi=300, bbox_inches="tight")
plt.show()

# entries per weekday for 2023 and 2024
weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
weekday_to_num = {day: i for i, day in enumerate(weekday_order)}

subset_tycktill_df["weekday_num"] = subset_tycktill_df["weekday"].map(weekday_to_num)

weekday_counts = subset_tycktill_df.groupby(["year", "weekday"]).size().reset_index(name="count")

weekday_counts["weekday_num"] = weekday_counts["weekday"].map(weekday_to_num)

weekday_counts = weekday_counts.sort_values(["year", "weekday_num"])

plt.figure(figsize=(10, 5))
for year in weekday_counts["year"].unique():
    year_data = weekday_counts[weekday_counts["year"] == year]
    year_data = year_data.sort_values("weekday_num")
    plt.plot(year_data["weekday"], year_data["count"], label=str(year), marker='o')

plt.xticks(ticks=range(7), labels=weekday_order)

plt.title("Entries per Weekday (by Year)")
plt.xlabel("Weekday")
plt.ylabel("Count")
plt.legend()
plt.grid(True)
plt.tight_layout()
#plt.savefig("data/")
plt.show()


# ========
# testa jämnför i och utanför parker?


# =======================