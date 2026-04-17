

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import geopandas as gpd
from matplotlib.ticker import MaxNLocator

tycktill_filtered_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg"

df = gpd.read_file(tycktill_filtered_GPKG, layer="pts_in_parks_with_topics")

outdir = Path(r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\plots\GRAPHS_FOR_ARTICLE")
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

#TOPIC_COLOR_MAP = {
#    topic: TOPIC_COLOR_SCHEME[i % len(TOPIC_COLOR_SCHEME)]
#    for i, topic in enumerate(ALL_TOPICS)
#}

TOPIC_COLOR_MAP = {
    # =================== TAB 20 ===================
    "bastu, bastun, sauna":                         "#4E79A7", # mid blue ***
    "blommor, tulpaner, påskliljor":                "#A0CBE8", # pastell blue ***
    "bänk, bänkar, brädor":                         "#F28E2B", # orange ***
    "cykelbanan, cykelbana, asfalteringen":         "#FFBE7D", # peachy orange  #FFBE7D i ppt
    "cyklisterna, cykelbanan, cykelbana":           "#59A14F", # green ***
    "fotbollsplanen, fotbollsplan, fotboll":        "#8CD17D", # pastell green ***
    "hastigheten, farthinder, hastighet":           "#B6992D", # army yellow/green ***
    "klotter, klotterrunda, rosa":                  "#F1CE63", # yellow ***
    "klotter, klotters, hammarbyklotter":           "#499894", # mid turqoise ***
    "köer, lindhagensgatan, trafiken":              "#86BCB6", # pastell turqoise ***
    "lekgatan, lekgata, barnen":                    "#E15759", # pastell red ***
    "lekplatsen, lekparken, gungor":                "#FF9D9A", # light pastell red/pink ***
    "lekplatsen, lekplats, lekredskap":             "#79706E", # mid grey/brown ***
    "lyktstolpe, staketstolpe, reservats":          "#BAB0AC", # light grey/brown  #B8AEAA i ppt
    "papperskorgar, lekplatsen, soptunnor":         "#D37295", # mid pink ***
    "parken, belysningen, lekparken":               "#FABFD2", # light pink***
    "parkeringsplatser, boendeparkering, parkerar": "#B07AA1", # mid purple ***
    "snöröjning, kartunderlag, snömodd":            "#D4A6C8", # light purple/pink ***
    "snöröjningen, beröm, tack":                    "#9D7660", # mid brown (orange undertone) ***
    "stockholm, stockholms, stockholmare":          "#D7B5A6", # light brown/orange ***
    # ================ EXTRA COLORS ================
    #"tack, beröm, städat":                         "#17BECF", # teal-cyan *** (distinct from Tableau blue/green)
    "tack, beröm, städat":                          "#14532D", # dark forest green ***
    "toaletten, toalett, toaletter":                "#BCBD22", # olive-lime *** (distinct from Tableau yellow/green)
    "övergångsställe, övergångsställen, korsar":    "#8C564B", # dark brown *** (distinct from orange/red)
    "översvämning, vattenansamling, vattensamling": "#AEC7E8", # pale blue-lavender *** (lighter than Tableau blues)
    "tags, räcke, pelare":                          "#C49C94", # dusty rose *** (distinct from Tableau pink/red)
    "felparkerade, parkerade, gågata":              "#1F3A8A" # deep blue (finns bara i error_complaints, compare 2 years?) har samma som bastu! #4E79A7
}

TOPIC_ALIASES = {
    "snöröjningen, beröm, tack": "snow ploughing, praise, thank you",
    "blommor, tulpaner, påskliljor": "flowers, daffodils",
    "bastu, bastun, sauna": "sauna",
    "cykelbanan, cykelbana, asfalteringen": "bicycle path, asphalt",
    "tack, beröm, städat": "thank you, praise, well maintained",
    "cyklisterna, cykelbanan, cykelbana": "cyclists, bicycle path",
    "stockholm, stockholms, stockholmare": "stockholm",
    "köer, lindhagensgatan, trafiken": "traffic jam, lindhagensgatan, traffic",
    "hastigheten, farthinder, hastighet": "speed, speedbump",
    "parkeringsplatser, boendeparkering, parkerar": "parkingspaces, residential parking",
    "översvämning, vattenansamling, vattensamling": "flooding",
    "klotter, klotters, hammarbyklotter": "graffiti",
    "bänk, bänkar, brädor": "bench, benches, planks",
    "lyktstolpe, staketstolpe, reservats": "lamppost, fencepost",
    "papperskorgar, lekplatsen, soptunnor": "wastepaper bins, playground",
}

TOPICS_TO_PLOT = {
    "praise": [
        "snöröjningen, beröm, tack",
        "blommor, tulpaner, påskliljor",
        "bastu, bastun, sauna",
        #"cykelbanan, cykelbana, asfalteringen",
    ],
    "idea": [
        "cyklisterna, cykelbanan, cykelbana",
        "köer, lindhagensgatan, trafiken",
        "parkeringsplatser, boendeparkering, parkerar", # alt "hastigheten, farthinder, hastighet"
    ],
    "error_complaint": [
        "klotter, klotters, hammarbyklotter",
        "översvämning, vattenansamling, vattensamling",
        #"lyktstolpe, staketstolpe, reservats",
    ],
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
          .reindex(MONTH_ORDER, fill_value=0)
    )
    return out

def aggregate_weekdays(df, topics):
    df = df[df["topic_keywords_short"].isin(topics)].copy()

    out = (
        df.groupby(["weekday_label", "topic_keywords_short"])
          .size()
          .unstack(fill_value=0)
          .reindex(WEEKDAY_ORDER, fill_value=0)
    )
    return out

def aggregate_hours(df, topics):
    df = df[df["topic_keywords_short"].isin(topics)].copy()

    out = (
        df.groupby(["hour", "topic_keywords_short"])
          .size()
          .unstack(fill_value=0)
          .reindex(range(24), fill_value=0)
    )
    return out

def aggregate_totals(df, topics):
    df = df[df["topic_keywords_short"].isin(topics)].copy()

    out = (
        df["topic_keywords_short"]
        .value_counts()
        .reindex(topics, fill_value=0)
    )

    return out

# ========
# PLOTTING

def plot_line_png(df_agg, title, xlabel, outfile):
    plt.figure(figsize=(6, 5))

    for i, col in enumerate(df_agg.columns):
        display_label = TOPIC_ALIASES.get(col, col)
        plt.plot(
            df_agg.index,
            df_agg[col],
            marker="o",
            linewidth=2,
            markersize=5,
            label=display_label,
            color=TOPIC_COLOR_MAP[col]
        )

    plt.title(title, fontsize=12)
    plt.xlabel(xlabel, fontsize=12)
    plt.ylabel("Tycktill entries", fontsize=12)
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=12)
    plt.legend(
        title="Topic",
        fontsize=11,
        title_fontsize=12,
        loc="upper left",
        bbox_to_anchor=(0.0, -0.28),
        frameon=False,
        ncol=1
    )
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True)) # force integer only y-axis (no decimals)
    plt.tight_layout(rect=[0, 0.12, 1, 1])
    plt.savefig(outfile, dpi=150)
    plt.close()

def plot_bar_totals_png(series, title, outfile):
    plt.figure(figsize=(4, 5))

    topics = series.index.tolist()
    values = series.values.tolist()

    display_labels = [TOPIC_ALIASES.get(t, t) for t in topics]
    #colors = [TOPIC_COLOR_MAP[t] for t in topics]
    colors = [TOPIC_COLOR_MAP.get(t, "#999999") for t in topics]

    plt.bar(display_labels, values, color=colors, width=0.8)

    plt.title(title, fontsize=12)
    plt.ylabel("Tycktill entries", fontsize=12)
    plt.xticks(rotation=40, ha="right", fontsize=11)
    plt.yticks(fontsize=12)

    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.tight_layout()

    plt.savefig(outfile, dpi=150)
    plt.close()

# =====================
def main(df):

    # === DATASET: by location only ===
    df = prepare_topic_df(df)

    # BAR CHART: TOP 5 TOTALS (ALL CATEGORIES COMBINED)
    top5_all_topics = get_top_n_topics(df, n=5)
    totals_all = aggregate_totals(df, top5_all_topics)

    plot_bar_totals_png(
        totals_all,
        title="Top 5 topics within park boundaries\n (Total count)",
        outfile=outdir / "all_categories_top5_totals.png"
    )

    categories = split_by_category(df)

    # ========= CATEGORY DISTRIBUTION (PERCENTAGES) =========
    total_n = len(df)

    category_counts = {
        "praise": len(categories["praise"]),
        "idea": len(categories["idea"]),
        "error_complaint": len(categories["error_complaint"]),
    }

    print("\nCATEGORY DISTRIBUTION (%)")
    for cat, count in category_counts.items():
        pct = (count / total_n) * 100 if total_n > 0 else 0
        print(f"{cat}: {pct:.1f}%")



    for cat_name, df_cat in categories.items():

        # ========= SENTIMENT DISTRIBUTION (PERCENTAGES) =========
        sentiment_pct = (
            df_cat["sentiment_label"]
            .value_counts(normalize=True)
            .reindex(["POSITIVE", "NEUTRAL", "NEGATIVE"], fill_value=0)
            * 100
        )

        print(f"\n{cat_name.upper()} – Sentiment distribution (%)")
        for sentiment, pct in sentiment_pct.items():
            print(f"{sentiment}: {pct:.1f}%")

        # ========= BAR CHART: TOP 5 TOTALS =========
        top5_topics = get_top_n_topics(df_cat, n=5)
        totals = aggregate_totals(df_cat, top5_topics)

        title_map = {
            "praise": "Top 5 topics within park boundaries\n (Praise)",
            "idea": "Top 5 topics within park boundaries\n (Ideas)",
            "error_complaint": "Top 5 topics within park boundaries\n (Maintenance requests/Complaints)"
        }

        plot_bar_totals_png(
            totals,
            title=title_map[cat_name],
            outfile=outdir / f"{cat_name}_top5_totals.png"
        )

        # ========= LINE PLOTS =========
        topics = TOPICS_TO_PLOT[cat_name]

        # MONTHS
        m = aggregate_months(df_cat, topics)
        plot_line_png(
            m,
            title=f"{cat_name.capitalize()} – Topics by Month",
            xlabel="Month",
            outfile=outdir / f"{cat_name}_topics_months.png"
        )

        # WEEKDAYS
        w = aggregate_weekdays(df_cat, topics)
        plot_line_png(
            w,
            title=f"{cat_name.capitalize()} – Topics by Weekday",
            xlabel="Weekday",
            outfile=outdir / f"{cat_name}_topics_weekdays.png"
        )

        # HOURS
        h = aggregate_hours(df_cat, topics)
        plot_line_png(
            h,
            title=f"{cat_name.capitalize()} – Topics by Hour",
            xlabel="Hour of day",
            outfile=outdir / f"{cat_name}_topics_hours.png"
        )
main(df)




