
import pandas as pd
import numpy as np
from collections import Counter
import geopandas as gpd
from shapely.geometry import Point
import folium
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
import os

# ======================
# load processed dataset
df = pd.read_excel("data/tycktill_with_sentiment.xlsx", parse_dates=["Inkommet datum"])

# =====================================
# set up for saving in the right folder
n_points_input = input("☆☆☆ Enter the number of points (n_points) used most recently in the main script (e.g. 50): ")

try:
    n_points = int(n_points_input)
except ValueError:
    print("❌ enter a valid integer ❌")
    exit()

folder_name = f"sample_{n_points * 2}_points"
output_folder = os.path.join("data", "tyck_till_output", folder_name)


# =======================================
# === lineplot (weekday vs sentiment) ===   # abbreviate weekdays to Mon, Tue, etc + flip horizontal + rename sentiments to Negative/Neutral/Positive

df['sentiment_label'] = df['sentiment_label'].str.title()
sentiment_order = ['Negative', 'Neutral', 'Positive']
sentiment_palette = {
    'Negative': '#D73027',
    'Neutral':  '#FDC500',
    'Positive': '#1A9850'
}
df['sentiment_label'] = pd.Categorical(df['sentiment_label'], categories=sentiment_order, ordered=True)

day_abbr = {
    'Monday': 'Mon',
    'Tuesday': 'Tue',
    'Wednesday': 'Wed',
    'Thursday': 'Thu',
    'Friday': 'Fri',
    'Saturday': 'Sat',
    'Sunday': 'Sun'
}
df['weekday'] = df['weekday'].map(day_abbr)
weekday_order = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
df['weekday'] = pd.Categorical(df['weekday'], categories=weekday_order, ordered=True)

# count of sentiment_label per weekday per year
grouped_weekday = (
    df.groupby(['year_label', 'weekday', 'sentiment_label'])
    .size()
    .reset_index(name='count')
)

# plot setup
sns.set(style='whitegrid')
fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
fig.suptitle("Sentiment for TyckTill Comments per Weekday", fontsize=16)

years = df['year_label'].unique()

for ax, year in zip(axes, years):
    subset = grouped_weekday[grouped_weekday['year_label'] == year]
    sns.lineplot(
        data=subset,
        x='weekday',
        y='count',
        hue='sentiment_label',
        marker='o',
        palette=sentiment_palette,
        ax=ax
    )
    ax.set_title(f"{year}")
    ax.set_xlabel("Weekday")
    ax.set_ylabel("TyckTill entries (count)")
    ax.set_xticklabels(weekday_order, rotation=0)
    ax.legend(title="Sentiment")

plt.tight_layout()
plt.savefig(f"{output_folder}/lineplot_weekday_vs_sentiment.png", dpi=300, bbox_inches="tight")
plt.show()


# =====================================
# === lineplot (month vs sentiment) ===

month_order = [6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5]
month_labels = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
               "Dec", "Jan", "Feb", "Mar", "Apr", "May"]
month_to_custom_order = {month: i for i, month in enumerate(month_order)}

df['month'] = pd.Categorical(df['month'], categories=month_order, ordered=True)

# count of sentiment_label per month per year
grouped_month = (
    df.groupby(['year_label', 'month', 'sentiment_label'])
    .size()
    .reset_index(name='count')
)
grouped_month['month_order'] = grouped_month['month'].map(month_to_custom_order)

# plot setup
sns.set(style='whitegrid')
fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
fig.suptitle("Sentiment for TyckTill Comments per Month", fontsize=16)

years = df['year_label'].unique()

for ax, year in zip(axes, years):
    subset = grouped_month[grouped_month['year_label'] == year]
    sns.lineplot(
        data=subset.sort_values('month_order'),
        x='month_order',
        y='count',
        hue='sentiment_label',
        marker='o',
        palette=sentiment_palette,
        ax=ax
    )
    ax.set_title(f"{year}")
    ax.set_xlabel("Month")
    ax.set_ylabel("TyckTill entries (count)")
    ax.set_xticks(range(12))
    ax.set_xticklabels(month_labels, rotation=0)
    ax.legend(title="Sentiment")

plt.tight_layout()
plt.savefig(f"{output_folder}/lineplot_month_vs_sentiment.png", dpi=300, bbox_inches="tight")
plt.show()

# ==============================================
# === stacked barplot (in_park vs sentiment) ===

df['in_park_clean'] = df['in_park'].map({True: 'Yes', False: 'No'})
df['in_park_clean'] = pd.Categorical(df['in_park_clean'], categories=['Yes', 'No'], ordered=True)

df['sentiment_label'] = pd.Categorical(df['sentiment_label'], categories=sentiment_order, ordered=True)

grouped_in_park = (
    df.groupby(['year_label', 'in_park_clean', 'sentiment_label'])
    .size()
    .reset_index(name='count')
)

pivoted = grouped_in_park.pivot_table(
    index=['year_label', 'in_park_clean'],
    columns='sentiment_label',
    values='count',
    fill_value=0
).reset_index()

# plot
fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
years = df['year_label'].unique()
fig.suptitle("Sentiment for TyckTill Comments Within, or Not Within Parks", fontsize=16)

for ax, year in zip(axes, years):
    subset = pivoted[pivoted['year_label'] == year]
    bottom = None
    for sentiment in sentiment_order:
        ax.bar(
            subset['in_park_clean'],
            subset[sentiment],
            bottom=bottom,
            label=sentiment.capitalize(),
            color=sentiment_palette[sentiment],
            width=0.8
        )
        if bottom is None:
            bottom = subset[sentiment]
        else:
            bottom += subset[sentiment]
    ax.set_title(f"{year}")
    ax.set_xlabel("In a park?")
    axes[0].set_ylabel("TyckTill entries (count)")  # label only on left plot
    axes[1].set_ylabel("")
    ax.legend(title="Sentiment")

plt.tight_layout()
plt.savefig(f"{output_folder}/stacked_barplot_in_park_vs_sentiment.png", dpi=300, bbox_inches="tight")
plt.show()


# ============================================
# === barplots (common words vs sentiment) ===

import ast
df['lemmas'] = df['lemmas'].apply(ast.literal_eval)

# get top n lemmas for both years and different sentiments
def get_top_lemmas(df, year, sentiment, n=5):
    subset = df[(df['year_label'] == year) & (df['sentiment_label'] == sentiment)]
    all_lemmas = [lemma for row in subset['lemmas'] if isinstance(row, list) for lemma in row]
    counter = Counter(all_lemmas)
    return counter.most_common(n)

years = sorted(df['year_label'].unique())

# make all x-axis be the same
max_count = 0
top_words_data = {}

for sentiment in sentiment_order:
    for year in years:
        top_words = get_top_lemmas(df, year, sentiment)
        top_words_data[(sentiment, year)] = top_words
        if top_words:
            max_count = max(max_count, max(count for word, count in top_words))

# setup the figure with 3 rows (sentiments), 2 columns (years)
fig = plt.figure(figsize=(12, 10))
axes = fig.subplots(3, 2)
fig.subplots_adjust(hspace=0.5)
fig.suptitle("Most Common Words and Sentiment by Park Presence", x=0.3, fontsize=16) # x=0.0 means aligned to the left
# *** kan inte plotta så?? eftersom orden kan räknas flera gånger per kommentar (Fritext cell) medan sentiment bara finns en gång per kommentar..

# plot
for row_idx, sentiment in enumerate(sentiment_order):
    for col_idx, year in enumerate(years):
        ax = axes[row_idx, col_idx]
        top_words = get_top_lemmas(df, year, sentiment)

        if top_words:
            words, counts = zip(*top_words)
            sns.barplot(
                x=list(counts),
                y=list(words),
                ax=ax,
                color=sentiment_palette[sentiment]
            )
            ax.set_xlim(0, max_count * 1.1)  # set consistent x-axis limit
            ax.set_title(f"{year}")
            ax.set_xlabel("Count")
            ax.set_ylabel("")
        else:
            ax.set_title(f"{year}")
            ax.text(0.5, 0.5, "No data", ha='center', va='center')
            ax.set_xticks([])
            ax.set_yticks([])

# add legend
handles = [plt.Rectangle((0,0),1,1, color=sentiment_palette[s]) for s in sentiment_order]
labels = [s.title() for s in sentiment_order]
fig.legend(handles, labels, title="Sentiment", loc='upper right', ncol=1)

plt.tight_layout(rect=[0, 0.05, 1, 0.95]) # leave space at top (0.95) and bottom (0.05)
plt.savefig(f"{output_folder}/barplot_common_words_vs_sentiment.png", dpi=300, bbox_inches="tight")
plt.show()

# ==========================================
# === barplots (common words vs in_park) ===

df['in_park_clean'] = df['in_park'].map({True: 'Yes', False: 'No'})
in_park_order = ['Yes', 'No']
df['in_park_clean'] = pd.Categorical(df['in_park_clean'], categories=in_park_order, ordered=True)

in_park_colors = {
    'Yes': '#1A9850',  # green
    'No': '#999999'    # gray
}

def get_top_lemmas_in_park(df, year, in_park_value, n=5):
    subset = df[(df['year_label'] == year) & (df['in_park_clean'] == in_park_value)]
    all_lemmas = [lemma for row in subset['lemmas'] if isinstance(row, list) for lemma in row]
    counter = Counter(all_lemmas)
    return counter.most_common(n)

years = sorted(df['year_label'].unique())

max_count = 0
top_words_data = {}

for in_park_value in in_park_order:
    for year in years:
        top_words = get_top_lemmas_in_park(df, year, in_park_value)
        top_words_data[(in_park_value, year)] = top_words
        if top_words:
            max_count = max(max_count, max(count for word, count in top_words))

# setup the figure with 2 rows (in_park), 2 columns (years)
fig, axes = plt.subplots(2, 2, figsize=(12, 8))
fig.subplots_adjust(hspace=0.5)
fig.suptitle("Most Common Words Within, or Not Within Parks", x=0.3, fontsize=16)

for row_idx, in_park_value in enumerate(in_park_order):
    for col_idx, year in enumerate(years):
        ax = axes[row_idx, col_idx]
        top_words = top_words_data[(in_park_value, year)]

        if top_words:
            words, counts = zip(*top_words)
            sns.barplot(
                x=list(counts),
                y=list(words),
                ax=ax,
                color=in_park_colors[in_park_value]
            )
            ax.set_xlim(0, max_count * 1.1)
            ax.set_title(f"{year}")
            ax.set_xlabel("Word count")
            ax.set_ylabel("")
        else:
            ax.set_title(f"{year}")
            ax.text(0.5, 0.5, "No data", ha='center', va='center')
            ax.set_xticks([])
            ax.set_yticks([])

# add custom legend
handles = [plt.Rectangle((0,0),1,1, color=in_park_colors[val]) for val in in_park_order]
labels = [f"{val}" for val in in_park_order]
fig.legend(handles, labels, title="In a Park?", loc='upper right', ncol=1) # chage to ncol=2 if yes and no should be next to eachother instead of stacked in the legend

plt.tight_layout(rect=[0, 0, 1, 0.95])  # adjust layout for legend
plt.savefig(f"{output_folder}/barplot_common_words_vs_in_park.png", dpi=300, bbox_inches="tight")
plt.show()

# =======================================
# === heatmap (Kategori vs sentiment) ===

#sentiment_order = ['NEGATIVE', 'NEUTRAL', 'POSITIVE']
#df['sentiment_label'] = pd.Categorical(df['sentiment_label'], categories=sentiment_order, ordered=True)

# Optional: clean Kategori if needed (e.g. strip spaces)
#df['Kategori'] = df['Kategori'].str.strip()

years = sorted(df['year_label'].unique())

# setup the figure with 2 subplots
fig, axes = plt.subplots(1, 2, figsize=(14, 8), sharey=False) # sharey=False important if number of categories differ between subplots
fig.suptitle("Relationship between Kategori and Sentiment", fontsize=16)

# find the global max count (for shared color scale)
all_heatmap_data = []
for year in years:
    subset = df[df['year_label'] == year]
    heatmap_data = (
        subset.groupby(['Kategori', 'sentiment_label'])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=sentiment_order)
    )
    all_heatmap_data.append(heatmap_data)

vmax = max(h.values.max() for h in all_heatmap_data)

# plot each heatmap
for i, (ax, year, heatmap_data) in enumerate(zip(axes, years, all_heatmap_data)):
    sns.heatmap(
        heatmap_data,
        annot=True,
        fmt='d',
        cmap='YlGnBu',
        linewidths=0.5,
        cbar=True,  # use cbar=(i == 1) for only one colorbar (on right)
        vmin=0,
        vmax=vmax,
        ax=ax
    )
    ax.set_title(f"{year}")
    ax.set_xlabel("Sentiment")
    ax.set_ylabel("Kategori")
    ax.tick_params(axis='x', bottom=True, labelbottom=True)

plt.tight_layout()
plt.savefig(f"{output_folder}/heatmap_kategori_vs_sentiment.png", dpi=300, bbox_inches="tight")
plt.show()





# =========================
# === MOST COMMON WORDS ===    *** remove? ***

# separate between inside and outside of parks
lemmas_in = [lemma for row in df[df["in_park"]]["lemmas"] for lemma in row]
lemmas_out = [lemma for row in df[~df["in_park"]]["lemmas"] for lemma in row]

# word frequency
lemmas_all = [lemma for lemmas_list in df["lemmas"] for lemma in lemmas_list]
lemmas_in = [lemma for lemmas_list in df[df["in_park"]]["lemmas"] for lemma in lemmas_list]
lemmas_out = [lemma for lemmas_list in df[~df["in_park"]]["lemmas"] for lemma in lemmas_list]

# total word count (every occurence regardless of row, so if multiple per row they are all counted)
word_freq_all = Counter(lemmas_all)
word_freq_in = Counter(lemmas_in)
word_freq_out = Counter(lemmas_out)

print("\n--- Top Words All ---")
for word, freq in word_freq_all.most_common(10):
    print(f"{word}: {freq}")                        # remove? just keep barplot?

print("\n--- Top Words Inside Parks ---")
for word, freq in word_freq_in.most_common(10):
    print(f"{word}: {freq}")                        # remove? just keep barplot?

print("\n--- Top Words Outside Parks ---")
for word, freq in word_freq_out.most_common(10):
    print(f"{word}: {freq}")                        # remove? just keep barplot?






