
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

# ============================================
# subset by parks and a limited number of rows

# subset tycktill dataset to begin with before committing to processing all 300000+ rows
#tycktill_df_subset = tycktill_df.head(50).copy() # uses 50 first rows (only from 2023)
#tycktill_df_subset = tycktill_df.sample(n=500).copy() # uses 50 random rows

# extract only the points in parks
parks = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

tycktill_df["geometry"] = tycktill_df.apply(lambda row: Point(row["Koordinater_x"], row["Koordinater_Y"]), axis=1)
geo_tycktill_df = gpd.GeoDataFrame(tycktill_df, geometry="geometry", crs="EPSG:4326")
geo_tycktill_df = geo_tycktill_df.to_crs("EPSG:3006")

subset_within_parks = gpd.sjoin(geo_tycktill_df, parks, how="inner", predicate="within")

#  n=X rows
tycktill_df_subset = subset_within_parks.sample(n=5000).copy() # uses 500 random rows

# ============
# NLP pipeline
nlp = stanza.Pipeline("sv", processors="tokenize,pos,lemma")

lemmatized_rows = []
for i, row in tycktill_df_subset.iterrows():
    print(f"Processing row {i + 1} of {len(tycktill_df_subset)}", flush=True)

    text = row["clean_Fritext"]

    doc = nlp(text)
    lemmas = [
        word.lemma for sentence in doc.sentences for word in sentence.words
        if word.upos != "PUNCT" and word.text.casefold() not in stop_words
    ]

    lemmatized_rows.append(lemmas)

tycktill_df_subset["lemmas"] = lemmatized_rows

print(tycktill_df_subset.head(5))

# ======================
# === WORD FREQUENCY ===

all_lemmas = [lemma for lemmas_list in tycktill_df_subset["lemmas"] for lemma in lemmas_list]

# ================
# total word count
# (every occurence regardless of row, so if multiple per row they are all counted)
word_frequencies = Counter(all_lemmas)
most_common_words = word_frequencies.most_common(10)
for word, frequency in most_common_words:
    print(f"{word}: {frequency}") # ger detta en output? Tror nått är fel

# =======================
# word count per Kategori
category_word_frequencies = {} # create a dictionary for storage

for category, group in tycktill_df_subset.groupby("Kategori"):                       # group by
    all_lemmas = [lemma for lemmas_list in group["lemmas"] for lemma in lemmas_list] # combine lemmas per Kategori
    word_frequencies = Counter(all_lemmas)
    category_word_frequencies[category] = word_frequencies                           # store in dictionary

for category, frequencies in category_word_frequencies.items():
    print(f"\nCategory: {category}")
    for word, count in frequencies.most_common(5):
        print(f"{word}: {count}")

# word frequency plots
# bar chart
for category, frequencies in category_word_frequencies.items():
    common = frequencies.most_common(10)
    words, counts = zip(*common)

    plt.figure(figsize=(10, 4))
    plt.bar(words, counts)
    plt.title(f"Top words in category: {category}")
    plt.xticks(rotation=45)
    plt.tight_layout()

    safe_category = category.replace(" ", "_").replace("/", "_")
    plt.savefig(f"data/subset5000_random_inParks/barchart_{safe_category}.png", dpi=300, bbox_inches="tight")
    plt.show()

# word cloud
for category, frequencies in category_word_frequencies.items():
    wordcloud = WordCloud(width=800, height=400).generate_from_frequencies(frequencies)

    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis("off")
    plt.title(f"Word cloud for {category}")
    plt.tight_layout()

    safe_category = category.replace(" ", "_").replace("/", "_")
    plt.savefig(f"data/subset5000_random_inParks/wordcloud_{safe_category}.png", dpi=300, bbox_inches="tight")
    plt.show()

# =======================
# word count by date/time

monthly_counts = tycktill_df_subset.groupby("month").size()
print(monthly_counts)

weekday_counts = tycktill_df_subset["weekday"].value_counts()
print(weekday_counts)

# date/time plots
# entries per month for 2023 and 2024
monthly_counts = tycktill_df_subset.groupby(["year", "month"]).size().reset_index(name="count")

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
plt.savefig("data/subset5000_random_inParks/entries_per_month_plot.png", dpi=300, bbox_inches="tight")
plt.show()

# entries per weekday for 2023 and 2024
weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
weekday_to_num = {day: i for i, day in enumerate(weekday_order)}

tycktill_df_subset["weekday_num"] = tycktill_df_subset["weekday"].map(weekday_to_num)

weekday_counts = tycktill_df_subset.groupby(["year", "weekday"]).size().reset_index(name="count")

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
plt.savefig("data/subset5000_random_inParks/entries_per_weekday_plot.png", dpi=300, bbox_inches="tight")
plt.show()

# =======================