
# >>> PLOTS per kategori <<<

import pandas as pd
import numpy as np
from collections import Counter
import geopandas as gpd
import folium
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
import os



# =====================================
# set up for saving in the right folder

kategori_input = input("☆☆☆ Enter the Kategori used in the first script (e.g. Felanmälan): ")

if not kategori_input:
    print("❌ enter a valid kategori ❌")
    exit()

input_folder = os.path.join("data", "tycktill_output", "sentiments")

output_folder = os.path.join("data", "tycktill_output", "plots")


# ======================
# load processed dataset
df = pd.read_excel(f"{input_folder}\\tycktill_with_sentiment_{kategori_input}.xlsx", parse_dates=["Inkommet datum"])


# =======================================
# === lineplot (weekday vs sentiment) ===

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
fig.suptitle(f"Sentiment for TyckTill Comments ({kategori_input}) per Weekday", fontsize=16)

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
    ax.set_ylabel(f"TyckTill entries, {kategori_input} (count)")
    ax.set_xticklabels(weekday_order, rotation=0)
    ax.set_ylim(ymax=16000)                          # <<< set appropriate y axis maximum (16 000 for Felanmälan, 600 for the rest)
    ax.legend(title="Sentiment")

plt.tight_layout()
plt.savefig(f"{output_folder}/lineplot_weekday_vs_sentiment_{kategori_input}.png", dpi=300, bbox_inches="tight")
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
fig.suptitle(f"Sentiment for TyckTill Comments ({kategori_input}) per Month", fontsize=16)

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
    ax.set_ylabel(f"TyckTill entries, {kategori_input} (count)")
    ax.set_xticks(range(12))
    ax.set_xticklabels(month_labels, rotation=0)
    ax.set_ylim(ymax=12000)                          # <<< set appropriate y axis maximum (12 000 for Felanmälan, 600 for the rest
    ax.legend(title="Sentiment")

plt.tight_layout()
plt.savefig(f"{output_folder}/lineplot_month_vs_sentiment_{kategori_input}.png", dpi=300, bbox_inches="tight")
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
fig.suptitle(f"Sentiment for TyckTill Comments ({kategori_input}) Within, or Not Within Parks", fontsize=16)

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
    ax.set_ylim(ymax=120000)                    # <<< set appropriate y axis maximum (120 000 for Felanmälan, 4000 for the rest)
    axes[0].set_ylabel(f"TyckTill entries, ({kategori_input}) (count)")  # label only on left plot
    axes[1].set_ylabel("")
    ax.legend(title="Sentiment")

plt.tight_layout()
plt.savefig(f"{output_folder}/stacked_barplot_in_park_vs_sentiment_{kategori_input}.png", dpi=300, bbox_inches="tight")
plt.show()



