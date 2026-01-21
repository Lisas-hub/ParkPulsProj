
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import geopandas as gpd

tycktill_filtered_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg"

df = gpd.read_file(tycktill_filtered_GPKG, "pts_in_parks_with_topics")

outdir = Path(r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\plots\LINE_GRAPHS_FOR_ARTICLE")
outdir.mkdir(exist_ok=True)


MONTH_ORDER = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]

WEEKDAY_ORDER = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

TABLEAU20 = [
    "#4E79A7", "#A0CBE8",
    "#F28E2B", "#FFBE7D",
    "#59A14F", "#8CD17D",
    "#B6992D", "#F1CE63",
    "#499894", "#86BCB6",
    "#E15759", "#FF9D9A",
    "#79706E", "#BAB0AC",
    "#D37295", "#FABFD2",
    "#B07AA1", "#D4A6C8",
    "#9D7660", "#D7B5A6",
]

EXTRA_COLORS = [
    "#17BECF",  # teal-cyan (distinct from Tableau blue/green)
    "#BCBD22",  # olive-lime (distinct from Tableau yellow/green)
    "#8C564B",  # dark brown (distinct from orange/red)
    "#AEC7E8",  # pale blue-lavender (lighter than Tableau blues)
    "#C49C94",  # dusty rose (distinct from Tableau pink/red)
]

TOPIC_COLOR_SCHEME = TABLEAU20 + EXTRA_COLORS

ALL_TOPICS = (
    df["topic_keywords"]
    .str.split(", ")
    .str[:3]
    .apply(", ".join)
    .value_counts()
    .index
    .tolist()
)

TOPIC_COLOR_MAP = {
    topic: TOPIC_COLOR_SCHEME[i % len(TOPIC_COLOR_SCHEME)]
    for i, topic in enumerate(ALL_TOPICS)
}


# ===============
# PREPP FUNCTIONS

def extract_topic_keyword_lists(df):
    df = df.copy()
    df["topic_keywords_list"] = df["topic_keywords"].str.split(", ")
    df["topic_keywords_short"] = df["topic_keywords_list"].str[:3].apply(", ".join)
    return df


def normalize_weekday(df):
    full_to_num = {
        "Monday": 0, "Mon": 0,
        "Tuesday": 1, "Tue": 1,
        "Wednesday": 2, "Wed": 2,
        "Thursday": 3, "Thu": 3,
        "Friday": 4, "Fri": 4,
        "Saturday": 5, "Sat": 5,
        "Sunday": 6, "Sun": 6,
    }
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    df = df.copy()
    df["weekday_num"] = df["weekday"].map(full_to_num)
    df["weekday_label"] = df["weekday_num"].map(lambda x: labels[x])
    return df


def prepare_topic_df(df):
    df = extract_topic_keyword_lists(df)
    df = normalize_weekday(df)
    return df


def split_by_category(df):
    return {
        "praise": df[df["Kategori"].isin(["Beröm"])],
        "idea": df[df["Kategori"].isin(["Idé"])],
        "error_complaint": df[df["Kategori"].isin(["Felanmälan", "Klagomål"])]
    }


def get_top_n_topics(df, n=5):
    return (
        df["topic_keywords_short"]
        .value_counts()
        .head(n)
        .index
        .tolist()
    )

# =====================
# AGGREGATION FUNCTIONS

def aggregate_months(df, topics):
    month_map = {
        1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
        7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"
    }

    df = df[df["topic_keywords_short"].isin(topics)].copy()
    df["month_name"] = df["month"].map(month_map)

    out = (
        df.groupby(["month_name", "topic_keywords_short"])
          .size()
          .unstack(fill_value=0)
          .reindex(MONTH_ORDER)
    )
    return out


def aggregate_weekdays(df, topics):
    df = df[df["topic_keywords_short"].isin(topics)].copy()

    out = (
        df.groupby(["weekday_label", "topic_keywords_short"])
          .size()
          .unstack(fill_value=0)
          .reindex(WEEKDAY_ORDER)
    )
    return out


def aggregate_hours(df, topics):
    df = df[df["topic_keywords_short"].isin(topics)].copy()

    out = (
        df.groupby(["hour", "topic_keywords_short"])
          .size()
          .unstack(fill_value=0)
          .reindex(range(24))
    )
    return out

# ========
# PLOTTING

def plot_line_png(df_agg, title, xlabel, outfile):
    plt.figure(figsize=(10, 5))

    for i, col in enumerate(df_agg.columns):
        plt.plot(
            df_agg.index,
            df_agg[col],
            marker="o",
            label=col,
            color=TOPIC_COLOR_MAP[col]
        )

    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Tycktill entries")
    plt.legend(title="Topic", fontsize=9)
    plt.tight_layout()
    plt.savefig(outfile, dpi=150)
    plt.close()

# =====================
def main(df):

    # === DATASET: by location only ===
    df = prepare_topic_df(df)
    categories = split_by_category(df)

    for cat_name, df_cat in categories.items():
        top_topics = get_top_n_topics(df_cat, n=5)

        # MONTHS
        m = aggregate_months(df_cat, top_topics)
        plot_line_png(
            m,
            title=f"{cat_name.capitalize()} – Topics by Month",
            xlabel="Month",
            outfile=outdir / f"{cat_name}_topics_months.png"
        )

        # WEEKDAYS
        w = aggregate_weekdays(df_cat, top_topics)
        plot_line_png(
            w,
            title=f"{cat_name.capitalize()} – Topics by Weekday",
            xlabel="Weekday",
            outfile=outdir / f"{cat_name}_topics_weekdays.png"
        )

        # HOURS
        h = aggregate_hours(df_cat, top_topics)
        plot_line_png(
            h,
            title=f"{cat_name.capitalize()} – Topics by Hour",
            xlabel="Hour of day",
            outfile=outdir / f"{cat_name}_topics_hours.png"
        )

main(df)



