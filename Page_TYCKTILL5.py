
import streamlit as st
import geopandas as gpd
import pandas as pd
import altair as alt
import os
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
import h3
from shapely.geometry import Polygon
import branca.colormap as cm
from wordcloud import WordCloud
import base64
from io import BytesIO
from itertools import combinations
import itertools
from collections import Counter
from streamlit_folium import st_folium
import ast


# TO DO
# fix wordclouds (they should be the same for hexbins in the same park BUT words are placed in different spots with different colors)
# group similar topics (and use these instead of raw topics in topics matrix etc)
# (make a dropdown list for topics to choose and then make graphs or maps that are specific to the chosen topic)
# visa något i formatet streamlit table? de går att sortera tabellerna. https://discuss.streamlit.io/t/good-looking-table-for-a-streamlit-application-is-anyone-still-using-aggrid/63763/3


st.set_page_config(layout="wide")

tycktill_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\tycktill.gpkg"
tycktill_filtered_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg"
tycktill_filtered_with_lemmas_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\STANZA_for_word_cloud\STANZA_output.gpkg"

plots_folder_path = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\plots"

raster_paths = {                      # am I using the rasters? if not, remove
    "Praise+Ideas": {
        "Day": os.path.join(plots_folder_path, "kde_praise_ideas_comments_day.tif"),       # *** change to _per_1000_residents.tif later ***
        "Night": os.path.join(plots_folder_path, "kde_praise_ideas_comments_night.tif")
    },
    "Error+Complaints": {
        "Day": os.path.join(plots_folder_path, "kde_error_complaints_comments_day.tif"),
        "Night": os.path.join(plots_folder_path, "kde_error_complaints_comments_night.tif")
    }
}

# ========================
# === LOAD VECTOR DATA ===

@st.cache_data(show_spinner="Loading spatial data...")
def vector_layer(path: str, layer_name: str) -> gpd.GeoDataFrame:
    """load a GPKG layer and reproject to WGS84."""
    gdf = gpd.read_file(path, layer=layer_name)
    return gdf.to_crs(epsg=4326)

@st.cache_data(show_spinner="Loading layers…")
def load_all_VECTOR_data():
    data = {}
    data["stats_per_park"] = vector_layer(tycktill_GPKG, "stats_per_park")                                              # park polygons
    data["all_park_related_pts_with_themes"] = vector_layer(tycktill_filtered_GPKG, "all_park_related_pts_with_themes") # all datapoints with most(?) columns (including original columns, sentiment, topic and themes columns)
    data["pts_with_topics_by_location"] = vector_layer(tycktill_filtered_GPKG, "pts_in_parks_with_topics")              # filtered by park boundary output (includes original columns, sentiment, topic and themes columns)
    data["pts_with_topics_by_keywords_strictly"] = vector_layer(tycktill_filtered_GPKG, "park_comments_by_keyword")     # filtered by keywords (strictly) output (includes original columns, sentiment, topic and themes columns)
    data["pts_with_topics_by_keywords_similarity"] = vector_layer(tycktill_filtered_GPKG, "park_comments_by_BERTopic")  # filtered by keywords (similarity) output (includes original columns, sentiment, topic and themes columns)
    data["parks_with_top5_topics"] = vector_layer(tycktill_filtered_GPKG, "parks_with_top5_topics")                     # park polygons + columns for top 5 topics per park
    data["all_park_related_pts_with_themes_AND_STANZA"] = vector_layer(tycktill_filtered_with_lemmas_GPKG, "all_park_related_pts_with_themes_AND_STANZA") # basically same as all_park_related_pts_with_themes but with additional columns for word clouds
    return data

raw_vectors = load_all_VECTOR_data()

# =================
# === CONSTANTS ===

MONTH_ORDER_JAN_DEC = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
MONTH_ORDER_JUN_MAY = ["Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar","Apr","May"]

SENTIMENT_COLORS = alt.Scale(
    domain=["POSITIVE", "NEUTRAL", "NEGATIVE"],
    range=["#2ca02c", "#7f7f7f", "#d62728"]
)

CATEGORY_MAP = {
    "Praise": "praise",
    "Ideas": "idea",
    "Error + Complaints": "error_complaint"
}

category_map = {
    "praise": ["Beröm"],
    "idea": ["Idé"],
    "error_complaint": ["Felanmälan", "Klagomål"],
}

TOPIC_COLOR_SCHEME = "tableau20"

MIXED_SENTIMENT_REL_THRESHOLD = 0.3           # 30%

# ========================
# === DATA PREPARATION ===

def normalize_weekday(df):
    df = df.copy()
    full_to_num = {
        "Monday": 0, "Mon": 0,
        "Tuesday": 1, "Tue": 1,
        "Wednesday": 2, "Wed": 2,
        "Thursday": 3, "Thu": 3,
        "Friday": 4, "Fri": 4,
        "Saturday": 5, "Sat": 5,
        "Sunday": 6, "Sun": 6,
    }
    df["weekday_num"] = df["weekday"].map(full_to_num)
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    df["weekday_label"] = df["weekday_num"].map(
        lambda x: labels[x] if pd.notnull(x) else None
    )
    return df

def extract_topic_keyword_lists(df):
    """split topic_keywords string into lists + short/full versions"""
    df = df.copy()
    df["topic_keywords_list"] = df["topic_keywords"].str.split(", ")
    df["topic_keywords_full"] = df["topic_keywords_list"].str[:10].apply(", ".join)
    df["topic_keywords_short"] = df["topic_keywords_list"].str[:3].apply(", ".join)
    return df

def add_time_period_column(df):
    df = df.copy()
    #df["is_day"] = df["hour"].between(6, 18)
    #df["is_night"] = ~df["is_day"]

    def classify_hour(hour):
        if 0 <= hour <= 5:
            return "Night"        # 00-05
        elif 6 <= hour <= 9:
            return "Morning"      # 06-09
        elif 10 <= hour <= 15:
            return "Midday"       # 10-15
        else:  # 16–23
            return "Evening"      # 16-23

    df["time_period"] = df["hour"].apply(classify_hour)

    return df

def split_by_category(df):
    """split into two subsets used by both sentiments & topics"""
    return {
        "praise": df[df["Kategori"].isin(["Beröm"])],
        "idea": df[df["Kategori"].isin(["Idé"])],
        "error_complaint": df[df["Kategori"].isin(["Felanmälan", "Klagomål"])]
    }

def fix_sentiment_column_type(df):
    if "sentiment_label" in df.columns:
        df = df.copy()
        df["sentiment_label"] = df["sentiment_label"].astype(str)
        df["sentiment_label"] = pd.Categorical(
            df["sentiment_label"],
            categories=["POSITIVE", "NEUTRAL", "NEGATIVE"],
            ordered=False
        )
    return df

def fix_topic_column_type(df):
    if "topic_keywords_short" in df.columns:
        df = df.copy()
        df["topic_keywords_short"] = df["topic_keywords_short"].astype(str)
    return df

def prepare_topic_df(df):
    df = extract_topic_keyword_lists(df)
    df = normalize_weekday(df)
    return df

def add_lat_lon(df):
    df = df.copy()
    df["lon"] = df.geometry.x
    df["lat"] = df.geometry.y
    return df

def add_h3_hex_id(df, resolution=9):
    df = df.copy()
    df["hex_id"] = df.apply(
        lambda r: h3.latlng_to_cell(r["lat"], r["lon"], resolution),
        axis=1
    )
    return df

def prepare_hexbins(df, text_col="lemmas"):
    if text_col in df.columns:
        exploded = df.explode(text_col)
        agg = (
            exploded
            .groupby("hex_id")
            .agg(
                count=("hex_id", "size"),
                words=(text_col, lambda x: list(x.dropna()))
            )
            .reset_index()
        )
    else:
        agg = df[["hex_id"]].drop_duplicates()
        agg["count"] = 0
        agg["words"] = [[] for _ in range(len(agg))]

    # geometry for plotting hexagons
    agg["geometry"] = agg["hex_id"].apply(
        lambda h: Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(h)])
    )

    hex_gdf = gpd.GeoDataFrame(agg, geometry="geometry", crs="EPSG:4326")
    return hex_gdf

def assign_hexes_to_parks(hex_gdf, parks_gdf, group_col="group"):
    """
    Returns hex_gdf with a new column:
        - agg_id: group if hex is inside a park, else hex_id
        - group: group or None
    """
    # Use centroids for stable assignment
    hex_gdf = hex_gdf.copy()
    hex_gdf["centroid"] = hex_gdf.geometry.centroid

    hex_centroids = hex_gdf.set_geometry("centroid")

    # Spatial join: which hex centroid falls inside which park
    joined = gpd.sjoin(
        hex_centroids,
        parks_gdf[[group_col, "geometry"]],
        how="left",
        predicate="within"
    )

    # Restore geometry
    joined = joined.drop(columns="centroid").set_geometry("geometry")

    joined["group"] = joined[group_col]

    # Aggregation key:
    #   group if exists, else hex_id
    joined["agg_id"] = joined["group"].fillna(joined["hex_id"])

    return joined

def generate_wordcloud(text_list, width=300, height=200, max_words=50):
    """Create a word cloud image and return as base64 string."""
    if not text_list:
        text_list = ["No data"]
    wc = WordCloud(width=width, height=height, max_words=max_words, background_color="white").generate(" ".join(text_list))
    img_buffer = BytesIO()
    wc.to_image().save(img_buffer, format="PNG")
    img_buffer.seek(0)
    img_b64 = base64.b64encode(img_buffer.read()).decode()
    return img_b64

def compute_topic_cooccurrence_by_hex(hex_points_df, topic_col="topic_keywords_short", min_count=1, top_n=None):
    """
    hex_points_df: DataFrame with columns ['hex_id', topic_col] (one row per comment)
    Returns a DataFrame with columns ['topic_a', 'topic_b', 'count'],
    where count = number of hexbins where both topics appear.
    """
    # Filter top N topics if needed
    if top_n:
        all_topics = hex_points_df[topic_col].dropna().tolist()
        from collections import Counter
        top_topics = [t for t, _ in Counter(all_topics).most_common(top_n)]
        df = hex_points_df[hex_points_df[topic_col].isin(top_topics)]
    else:
        df = hex_points_df.copy()

    # Group by hex_id
    hex_groups = df.groupby("hex_id")[topic_col].apply(lambda x: set(x.dropna()))

    # Count co-occurrences across hexes
    counter = Counter()
    for topics in hex_groups:
        if len(topics) < 2:
            continue
        for a, b in combinations(sorted(topics), 2):
            counter[(a, b)] += 1

    # Convert to DataFrame and filter by min_count
    coocc_df = pd.DataFrame(
        [(a, b, c) for (a, b), c in counter.items() if c >= min_count],
        columns=["topic_a", "topic_b", "count"]
    ).sort_values("count", ascending=False).reset_index(drop=True)

    return coocc_df

def convert_sentiment_all(x):
    if isinstance(x, str):
        return ast.literal_eval(x)
    return x

def count_mixed_sentiment(sent_list, rel_threshold=MIXED_SENTIMENT_REL_THRESHOLD):
    """
    Counts how many sentiments are close to the max sentiment score in a single comment.
    Returns labels that are within rel_threshold of the max.
    """
    if not sent_list:
        return []
    max_score = max(s['score'] for s in sent_list)
    return [s['label'] for s in sent_list if s['score'] >= max_score * (1 - rel_threshold)]

# ============================
# === PREPARED VECTOR DATA ===

def prepare_vectors(raw_vectors):

    prepped_vectors = {}

    topics_map = {
        "pts_with_topics_by_location": "loc",
        "pts_with_topics_by_keywords_strictly": "key",
        "pts_with_topics_by_keywords_similarity": "sim"
    }

    # topic datasets for loc/key/sim
    for raw_name, suffix in topics_map.items():
        df = prepare_topic_df(raw_vectors[raw_name])
        df = fix_sentiment_column_type(df)
        df = fix_topic_column_type(df)

        split = split_by_category(df)
        prepped_vectors[f"praise_{suffix}"] = split["praise"]
        prepped_vectors[f"idea_{suffix}"] = split["idea"]
        prepped_vectors[f"error_complaint_{suffix}"] = split["error_complaint"]

    # all_pts used for year comparisons
    all_pts = add_time_period_column(raw_vectors["all_park_related_pts_with_themes"])
    all_pts = prepare_topic_df(all_pts)
    all_pts = fix_sentiment_column_type(all_pts)
    all_pts = fix_topic_column_type(all_pts)
    prepped_vectors["all_pts"] = all_pts

    # sentiment splits for heatmaps
    heat = split_by_category(all_pts)
    prepped_vectors["heat_praise"] = heat["praise"]
    prepped_vectors["heat_idea"] = heat["idea"]
    prepped_vectors["heat_error_complaint"] = heat["error_complaint"]

    # mixed sentiments - convert sentiment_all to list
    all_pts['sentiment_all'] = all_pts['sentiment_all'].apply(convert_sentiment_all)

    # mixed sentiments (mixed_count = 1 is clear dominant sentiment, mixed_count > 1 is mixed sentiment)
    all_pts['mixed_sent_labels'] = all_pts['sentiment_all'].apply(count_mixed_sentiment)
    all_pts['mixed_count'] = all_pts['mixed_sent_labels'].apply(len)

    prepped_vectors["all_pts"] = all_pts

    # hexbins
    hex_src = add_lat_lon(raw_vectors["all_park_related_pts_with_themes_AND_STANZA"])
    hex_src = prepare_topic_df(hex_src)
    hex_src = add_h3_hex_id(hex_src, resolution=9)
    split = split_by_category(hex_src)

    # ---- create hex -> group lookup (ONCE) ----
    parks_gdf = raw_vectors["stats_per_park"]

    # Prepare hex geometries and assign to parks
    hex_geom_lookup = prepare_hexbins(hex_src[["hex_id"]].drop_duplicates())
    hex_geom_lookup = assign_hexes_to_parks(hex_geom_lookup, parks_gdf)
    hex_lookup = hex_geom_lookup[["hex_id", "group", "agg_id"]]

    # ---- Hex bins with aggregation ----
    hex_bins_praise = prepare_hexbins(split["praise"]).merge(hex_lookup, on="hex_id", how="left")
    hex_bins_idea = prepare_hexbins(split["idea"]).merge(hex_lookup, on="hex_id", how="left")
    hex_bins_error = prepare_hexbins(split["error_complaint"]).merge(hex_lookup, on="hex_id", how="left")

    prepped_vectors["hex_bins_praise"] = hex_bins_praise
    prepped_vectors["hex_bins_idea"] = hex_bins_idea
    prepped_vectors["hex_bins_error_complaint"] = hex_bins_error

    # ---- Hex points with same aggregation info ----
    prepped_vectors["hex_points_praise"] = split["praise"].merge(hex_lookup, on="hex_id", how="left")
    prepped_vectors["hex_points_idea"] = split["idea"].merge(hex_lookup, on="hex_id", how="left")
    prepped_vectors["hex_points_error_complaint"] = split["error_complaint"].merge(hex_lookup, on="hex_id", how="left")

    # ---- Topic co-occurrence ----
    prepped_vectors["hex_topic_cooccurrence_praise"] = compute_topic_cooccurrence_by_hex(
        prepped_vectors["hex_points_praise"], topic_col="topic_keywords_short", min_count=1, top_n=50
    )
    prepped_vectors["hex_topic_cooccurrence_idea"] = compute_topic_cooccurrence_by_hex(
        prepped_vectors["hex_points_idea"], topic_col="topic_keywords_short", min_count=1, top_n=50
    )
    prepped_vectors["hex_topic_cooccurrence_error_complaint"] = compute_topic_cooccurrence_by_hex(
        prepped_vectors["hex_points_error_complaint"], topic_col="topic_keywords_short", min_count=1, top_n=50
    )

    return prepped_vectors

prepped_vectors = prepare_vectors(raw_vectors)

# ====================================
# === TEMPORAL AGGREGATION HELPERS ===

def get_top_n_topics(df, n=5):
    return df['topic_keywords_short'].value_counts().head(n).index.tolist()

def prepare_monthly(df, line_field, top_topics=None, month_order=None):
    df = df.copy()
    month_map = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                 7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    df["month_name"] = df["month"].map(month_map)

    # restrict to top_topics if provided
    if top_topics is not None:
        df = df[df[line_field].isin(top_topics)]

    # use provided month_order or default Jan→Dec
    if month_order is None:
        month_order = MONTH_ORDER_JAN_DEC

    # zero-filling: make sure all months exist per topic
    all_index = pd.MultiIndex.from_product(
        [month_order, df[line_field].unique()],
        names=["month_name", line_field]
    )

    out = (
        df.groupby(["month_name", line_field])
          .size()
          .reindex(all_index, fill_value=0)
          .reset_index(name="count")
    )
    out = out.rename(columns={"month_name": "x"})

    # ensure categorical with proper ordering
    out["x"] = pd.Categorical(out["x"], categories=month_order, ordered=True)

    return out

def prepare_weekday(df, line_field):
    df = df.copy()
    weekdays = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

    all_index = pd.MultiIndex.from_product(
        [weekdays, df[line_field].unique()],
        names=["weekday_label", line_field]
    )
    out = (
        df.groupby(["weekday_label",line_field])
          .size()
          .reindex(all_index, fill_value=0)
          .reset_index(name="count")
    )
    out["x"] = out["weekday_label"]
    return out

def prepare_hourly(df, line_field):
    df = df.copy()
    all_index = pd.MultiIndex.from_product(
        [range(24), df[line_field].unique()],
        names=["hour", line_field]
    )
    out = (
        df.groupby(["hour",line_field])
          .size()
          .reindex(all_index, fill_value=0)
          .reset_index(name="count")
    )
    out["x"] = out["hour"]
    return out

def prepare_for_temporal_scale(df, temporal_scale, kind, month_order=None, top_topics=None):
    df = df.copy()
    line_field = "sentiment_label" if kind=="sentiment" else "topic_keywords_short"

    if temporal_scale == "Months":
        out = prepare_monthly(df, line_field=line_field, top_topics=top_topics, month_order=month_order)
        return out

    if temporal_scale == "Weekdays":
        out = prepare_weekday(df, line_field=line_field)
        weekdays = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        out["x"] = pd.Categorical(out["x"], categories=weekdays, ordered=True)
        return out

    if temporal_scale == "24 Hours":
        out = prepare_hourly(df, line_field=line_field)
        out["x"] = pd.Categorical(out["x"], categories=range(24), ordered=True)
        return out

    raise ValueError("Invalid temporal scale")

# ======================
# === UNIFIED COLORS ===

def get_global_topic_domain(prepped_vectors, top_n=5):
    all_topics = []

    topic_keys = [
        "praise_loc", "praise_key", "praise_sim",
        "idea_loc", "idea_key", "idea_sim",
        "error_complaint_loc", "error_complaint_key", "error_complaint_sim",
        "all_pts"
    ]

    for key in topic_keys:
        if key in prepped_vectors:
            df = prepped_vectors[key]
            all_topics.extend(get_top_n_topics(df, top_n))

    return sorted(set(all_topics))

GLOBAL_TOPIC_DOMAIN = get_global_topic_domain(prepped_vectors, top_n=5)

missing_topic = "felparkerade, parkerade, gågata"  # this topic only occurs in one single plot and goes transparent if not appended
if missing_topic not in GLOBAL_TOPIC_DOMAIN:
    GLOBAL_TOPIC_DOMAIN.append(missing_topic)

GLOBAL_TOPIC_COLOR_SCALE = alt.Scale(domain=GLOBAL_TOPIC_DOMAIN, scheme="tableau20")

def get_shared_color_scale(kind, datasets, n=5):

    if kind == "sentiment":
        return SENTIMENT_COLORS, SENTIMENT_COLORS.domain

    # topics: build global domain across all datasets
    all_topics = []
    for df in datasets:
        all_topics.extend(get_top_n_topics(df, n=n))

    global_domain = sorted(set(all_topics))
    return alt.Scale(domain=global_domain, scheme=TOPIC_COLOR_SCHEME), global_domain

def get_visible_topics(df, line_field):
    # return only topics that actually occur in this subset for each subpage
    return sorted(df[line_field].dropna().unique().tolist())

# ==========================================
# === UNIFIED PLOTTER FOR ANY ONE SUBSET ===

def build_single_chart(df, title, kind, temporal_scale, month_order, color_scale, top_topics=None):
    df_prep = prepare_for_temporal_scale(df, temporal_scale, kind, month_order, top_topics=top_topics)

    line_field = "sentiment_label" if kind=="sentiment" else "topic_keywords_short"

    chart = (
        alt.Chart(df_prep, title=title)
           .mark_line(point=True)
           .encode(
            x=alt.X("x:N", sort=list(df_prep["x"].cat.categories)),
            y="count:Q",
            color=alt.Color(line_field, scale=color_scale),
            tooltip=[line_field, "count", "x"]
           )
           .properties(height=250)
    )
    return chart

# ===========================================
# === HIGH-LEVEL PLOT MAKERS (VIEW LOGIC) ===

def make_plot_compare_2_years(prepped_vectors, kind, category, temporal_scale):
    df = prepped_vectors["all_pts"]
    cat_key = CATEGORY_MAP[category]
    df = df[df["Kategori"].isin(category_map[cat_key])]

    # separate per year
    years = sorted(df["year_label"].unique())
    datasets = [df[df["year_label"]==y] for y in years]

    # shared topic colors
    color_scale, _ = get_shared_color_scale(kind, datasets)

    month_order = MONTH_ORDER_JUN_MAY
    charts = []
    for y, df_year in zip(years, datasets):
        charts.append(
            build_single_chart(df_year, f"Year {y}", kind, temporal_scale, month_order, color_scale)
        )
    return charts

def make_plot_compare_3_filters(datasets_dict, kind, temporal_scale, view, top_n=5):

    line_field = "sentiment_label" if kind == "sentiment" else "topic_keywords_short"

    if kind == "topic":
        # top topics per dataset
        dataset_top_topics = {
            name: get_top_n_topics(df, n=top_n) for name, df in datasets_dict.items()
        }
        # collect visible topics
        all_visible_topics = set()
        for name, df in datasets_dict.items():
            df_plot = df[df[line_field].isin(dataset_top_topics[name])]
            df_prep = prepare_for_temporal_scale(
                df_plot, temporal_scale, kind,
                MONTH_ORDER_JAN_DEC,
                top_topics=dataset_top_topics[name]
            )
            all_visible_topics.update(df_prep[line_field].dropna().unique())
        page_visible_topics = sorted(all_visible_topics)

        color_scale = GLOBAL_TOPIC_COLOR_SCALE
    else:
        page_visible_topics = None
        color_scale = SENTIMENT_COLORS

    plots = []

    # plot each dataset
    for title, df in datasets_dict.items():
        df_plot = df.copy()

        # keep only dataset-specific top topics
        if kind == "topic":
            df_plot = df_plot[df_plot[line_field].isin(dataset_top_topics[title])]

        # prepare for temporal scale
        month_order = MONTH_ORDER_JAN_DEC  # compare 3 park filters always uses JAN-DEC
        df_prep = prepare_for_temporal_scale(
            df_plot,
            temporal_scale,
            kind,
            month_order,
            top_topics=dataset_top_topics[title] if kind == "topic" else None
        )

        # ensure categorical ordering for months, weekdays, or hours
        if temporal_scale == "Months":
            month_order = MONTH_ORDER_JAN_DEC if view == "Compare 3 park filters" else MONTH_ORDER_JUN_MAY
            df_prep["x"] = pd.Categorical(df_prep["x"], categories=month_order, ordered=True)
        elif temporal_scale == "Weekdays":
            df_prep["x"] = pd.Categorical(df_prep["x"], categories=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"], ordered=True)
        elif temporal_scale == "24 Hours":
            df_prep["x"] = pd.Categorical(df_prep["x"], categories=range(24), ordered=True)

        legend_title = "Sentiment" if kind == "sentiment" else "Topic label"
        axis_title = {
            "Months": "Month",
            "Weekdays": "Weekday",
            "24 Hours": "Hour"
        }[temporal_scale]

        chart = (
            alt.Chart(df_prep, title=title)
            .mark_line(point=True)
            .encode(
                x=alt.X("x:N", sort=list(df_prep["x"].cat.categories), axis=alt.Axis(title=axis_title, labelAngle=0)),
                y=alt.Y("count:Q", title='Tycktill entries'),
                color=alt.Color(
                    line_field,
                    scale=color_scale,
                    legend=alt.Legend(
                        orient="bottom",
                        direction="vertical",
                        labelLimit=500,
                        title=legend_title,
                        **({"values": page_visible_topics} if page_visible_topics is not None else {})
                    )
                    ),
                tooltip=["filter:N", line_field, "count", "x"] if "filter" in df_prep.columns else [line_field, "count", "x"]
            )
            .properties(height=200, width=300)
        )

        plots.append(chart)

    return plots

def make_plot(kind, category, view, temporal_scale, prepped_vectors, top_n=5):

    cat_key = CATEGORY_MAP[category]

    # ======================
    # compare 3 park filters

    if view == "Compare 3 park filters":
        datasets_dict = {
            "By location": prepped_vectors[f"{cat_key}_loc"],
            "By keyword (strictly)": prepped_vectors[f"{cat_key}_key"],
            "By keyword (similarity)": prepped_vectors[f"{cat_key}_sim"]
        }

        charts = make_plot_compare_3_filters(
            datasets_dict=datasets_dict,
            kind=kind,
            temporal_scale=temporal_scale,
            view=view,
            top_n=top_n
        )

    # ===============
    # compare 2 years

    elif view == "Compare 2 years":
        df_all = prepped_vectors["all_pts"]

        cat_key = CATEGORY_MAP[category]
        if cat_key == "praise":
            df_all = df_all[df_all["Kategori"].isin(["Beröm"])]
        elif cat_key == "idea":
            df_all = df_all[df_all["Kategori"].isin(["Idé"])]
        elif cat_key == "error_complaint":
            df_all = df_all[df_all["Kategori"].isin(["Felanmälan", "Klagomål"])]

        charts = []

        # collect top topics per year if kind is "topic"
        if kind == "topic":
            # get top N topics per year separately
            year_top_topics = {
                year: get_top_n_topics(df_all[df_all["year_label"] == year], n=top_n)
                for year in df_all["year_label"].unique()
            }
            # collect visible topics across ALL years
            all_visible_topics = set()
            for year in df_all["year_label"].unique():
                df_year = df_all[df_all["year_label"] == year]
                df_plot = df_year[df_year["topic_keywords_short"].isin(year_top_topics[year])]
                df_prep_tmp = prepare_for_temporal_scale(df_plot, temporal_scale, kind, MONTH_ORDER_JUN_MAY)
                all_visible_topics.update(df_prep_tmp["topic_keywords_short"].dropna().unique())
            page_visible_topics = sorted(all_visible_topics)

            color_scale = GLOBAL_TOPIC_COLOR_SCALE

        else:
            page_visible_topics = None
            color_scale = SENTIMENT_COLORS

        # create a chart per year
        for year in sorted(df_all["year_label"].unique()):
            df_year = df_all[df_all["year_label"] == year].copy()

            if kind == "topic":
                df_year = df_year[df_year["topic_keywords_short"].isin(year_top_topics[year])]

            month_order = MONTH_ORDER_JUN_MAY  # ensure Jun-May order for Compare 2 years
            df_prep = prepare_for_temporal_scale(df_year, temporal_scale, kind, month_order)

            # ensure proper ordering for months
            if temporal_scale == "Months":
                df_prep["x"] = pd.Categorical(df_prep["x"], categories=MONTH_ORDER_JUN_MAY, ordered=True)
            elif temporal_scale == "Weekdays":
                df_prep["x"] = pd.Categorical(df_prep["x"],
                                              categories=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                                              ordered=True)
            elif temporal_scale == "24 Hours":
                df_prep["x"] = pd.Categorical(df_prep["x"], categories=range(24), ordered=True)

            line_field = "sentiment_label" if kind == "sentiment" else "topic_keywords_short"
            legend_title = "Sentiment" if kind == "sentiment" else "Topic label"
            axis_title = {
                "Months": "Month",
                "Weekdays": "Weekday",
                "24 Hours": "Hour"
            }[temporal_scale]

            chart = (
                alt.Chart(df_prep, title=f"{year}")
                    .mark_line(point=True)
                    .encode(
                    x=alt.X("x:N", sort=list(df_prep["x"].cat.categories), axis=alt.Axis(title=axis_title, labelAngle=0)),
                    y=alt.Y("count:Q", title='Tycktill entries'),
                    color=alt.Color(
                        line_field,
                        scale=color_scale,
                        legend=alt.Legend(
                            orient="bottom",
                            direction="vertical",
                            labelLimit=500,
                            title=legend_title,
                            **({"values": page_visible_topics} if page_visible_topics is not None else {})
                        )
                    ),
                    tooltip=[line_field, "count", "x"]
                )
                    .properties(height=200, width=400)
            )

            charts.append(chart)

        return charts

    else:
        raise ValueError("Unknown view")

    return charts

# =====================
# plot mixed sentiments

def get_mixed_sentiment_summary(df, category_name):
    category_map = {
        "Praise": ["Beröm"],
        "Ideas": ["Idé"],
        "Error + Complaints": ["Felanmälan", "Klagomål"]
    }
    # Filter by category
    df_filtered = df[df["Kategori"].isin(category_map[category_name])]
    # Map mixed_count to single/mixed
    summary = df_filtered['mixed_count'].apply(lambda x: "Single sentiment" if x == 1 else "Mixed sentiment").value_counts().reset_index()
    summary.columns = ["Sentiment type", "Count"]
    return summary

def plot_mixed_sentiment_bar(summary):
    return alt.Chart(summary).mark_bar(color="#aecad6").encode(
        x=alt.X("Sentiment type:N", title="Sentiment type", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Count:Q", title="Number of comments"),
        tooltip=["Sentiment type", "Count"]
    )

def compute_sentiment_cooccurrence_matrix(df):
    """
    Builds a normalized lower-triangle co-occurrence matrix
    for mixed-sentiment comments only.
    """

    # Keep only mixed comments
    df_mixed = df[df["mixed_count"] > 1]

    # Count sentiment pair occurrences
    pair_counts = {}

    for labels in df_mixed["mixed_sent_labels"]:
        unique_labels = sorted(set(labels))
        for i in range(len(unique_labels)):
            for j in range(i):  # LOWER TRIANGLE ONLY
                pair = (unique_labels[i], unique_labels[j])
                pair_counts[pair] = pair_counts.get(pair, 0) + 1

    if not pair_counts:
        return pd.DataFrame(columns=["sent_a", "sent_b", "count", "percent"])

    cooc_df = (
        pd.DataFrame(
            [(a, b, c) for (a, b), c in pair_counts.items()],
            columns=["sent_a", "sent_b", "count"]
        )
    )

    # Normalize by total mixed comments
    total_mixed = len(df_mixed)
    cooc_df["percent"] = cooc_df["count"] / total_mixed * 100

    return cooc_df

def plot_sentiment_cooccurrence_matrix(cooc_df):
    if cooc_df.empty:
        return alt.Chart(pd.DataFrame({"msg": ["No mixed sentiments found"]})).mark_text().encode(text="msg")

    chart = (
        alt.Chart(cooc_df)
        .mark_rect()
        .encode(
            x=alt.X(
                "sent_b:N",
                title="Sentiment",
                sort=["NEGATIVE", "NEUTRAL", "POSITIVE"],
                axis=alt.Axis(labelAngle=0)
            ),
            y=alt.Y(
                "sent_a:N",
                title="Sentiment",
                sort=["NEGATIVE", "NEUTRAL", "POSITIVE"]
            ),
            color=alt.Color(
                "percent:Q",
                title="Share of mixed comments (%)",
                scale=alt.Scale(scheme="viridis")
            ),
            tooltip=[
                alt.Tooltip("sent_a:N", title="Sentiment A"),
                alt.Tooltip("sent_b:N", title="Sentiment B"),
                alt.Tooltip("count:Q", title="Number of comments"),
                alt.Tooltip("percent:Q", title="Share (%)", format=".2f")
            ]
        )
        .properties(
            title="Sentiment co-occurrence in mixed comments",
            width=300,
            height=300
        )
    )

    return chart

# ============
# === MAPS ===

def create_folium_basemap():
    m = folium.Map(location=(59.33, 17.99), zoom_start=10.5, tiles=None)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satellite',
        overlay=False,
        control=True
    ).add_to(m)
    return m

def add_folium_heatmap(m, gdf, radius=15, blur=10, max_zoom=13):
    # extract [lat, lon] from geometry
    heat_points = [
        [geom.y, geom.x]
        for geom in gdf.geometry
        if geom is not None
    ]

    viridis_gradient = {
        0.0: '#fde725',  # bright yellow
        0.25: '#5ec962',
        0.5: '#21918c',
        0.75: '#3b528b',
        1.0: '#440154'  # dark purple
    }

    HeatMap(
        heat_points,
        radius=radius,
        blur=blur,
        max_zoom=max_zoom,
        min_opacity=0.4,
        gradient=viridis_gradient,
    ).add_to(m)

    return m

def create_folium_hexbin_map_with_wc(hex_gdf, points_df, text_col="lemmas", color_col="count"):

    m = create_folium_basemap()

    for _, row in hex_gdf.iterrows():
        #pts_in_hex = points_df[points_df["hex_id"] == row["hex_id"]]
        #################
        # get pts per hex or per aggregated hexes if overlapping with the same park
        agg_id = row["agg_id"]

        pts_in_hex = points_df[points_df["agg_id"] == agg_id]
        #################

        texts = pts_in_hex[text_col].dropna().tolist()

        # make hexbins if > 10 comments in the bin
        #if len(texts) < 10:
        #    popup_html = "<b>Too few comments to display</b>"
        #else:
        #    img_b64 = generate_wordcloud(texts)
        #    popup_html = (
        #        f'<img src="data:image/png;base64,{img_b64}" '
        #        f'width="300" height="200">'
        #    )

        n_hexes = hex_gdf.loc[hex_gdf["agg_id"] == agg_id, "hex_id"].nunique()

        if len(texts) < 10:
            popup_html = (
                "<b>Too few comments to display</b><br>"
                f"<i>Based on {n_hexes} hexbin{'s' if n_hexes > 1 else ''}</i>"
            )
        else:
            img_b64 = generate_wordcloud(texts)
            popup_html = (
                f"<b>Word cloud</b><br>"
                f"<i>Based on {n_hexes} hexbin{'s' if n_hexes > 1 else ''}</i><br>"
                f'<img src="data:image/png;base64,{img_b64}" '
                f'width="300" height="200">'
            )

        #folium.GeoJson(
        #    row["geometry"],
        #    style_function=lambda f, color=row[color_col]: {
        #        'fillColor': colormap(color),
        #        'color': 'black',
        #        'weight': 1,
        #        'fillOpacity': 0.6
        #    },
        #    tooltip=folium.Tooltip(f"Count: {row[color_col]}"),
        #    popup=folium.Popup(popup_html, max_width=320)
        #).add_to(m)

        # Tooltip text
        in_park = pd.notna(row["group"])
        if not in_park:
            tooltip_text = "Single hexbin"
        elif n_hexes == 1:
            tooltip_text = "Hexbin overlaps with a park"
        else:
            tooltip_text = "Aggregated across multiple hexbins (park)"

        # Border weight
        border_weight = 3 if in_park else 1
        border_color = "black"

        folium.GeoJson(
            row["geometry"],
            style_function=lambda f, color=row[color_col], weight=border_weight, border_color=border_color: {
                "fillColor": colormap(color),
                "color": border_color,
                "weight": weight,
                "fillOpacity": 0.6,
            },
            tooltip=folium.Tooltip(tooltip_text),
            popup=folium.Popup(popup_html, max_width=340),
        ).add_to(m)

    return m

# =================
# === STREAMLIT ===

st.title("Vad tycker besökarna om Stockholms parker?")
st.text("Här finner du sammanställd data från appen TyckTill!")

st.sidebar.button("Clear Cache", on_click=st.cache_data.clear)

section = st.sidebar.pills(
    "Make a selection:",
    ["Overview", "Sentiments", "Topics", "Themes"]
)

# ================
# === OVERVIEW ===    *** add another st.pills level, options: Word Cloud; co-occurence between topics within a hexagon?; ...

if section == "Overview":
    overview_question = st.sidebar.radio(
        "Choose a question:",
        ["*Where* and *when* is Tyck till being used?", "*What* is talked about *where*?"]
    )

    if overview_question == "*Where* and *when* is Tyck till being used?":            # *** change to slider + weekday vs weekend?? ***

        st.subheader("Tycktill entries")

        category_choice = st.sidebar.pills("Tyck till category:",
            ["Praise", "Ideas", "Error + Complaints"],
            selection_mode="single",
            default="Praise",
            key="sent_cat")

        if category_choice == "Praise":
            pts_category = prepped_vectors["heat_praise"]
        elif category_choice == "Ideas":
            pts_category = prepped_vectors["heat_idea"]
        else:
            pts_category = prepped_vectors["heat_error_complaint"]

        TIME_PERIODS = [
            ("Night", "Night (00:00–05:59)"),
            ("Morning", "Morning (06:00–09:59)"),
            ("Midday", "Midday (10:00–15:59)"),
            ("Evening", "Evening (16:00–23:59)")
        ]

        cols = st.columns(2)
        rows = [cols, st.columns(2)]

        period_dfs = {
            period: pts_category[pts_category["time_period"] == period]
            for period, _ in TIME_PERIODS
        }

        i = 0
        for row in rows:
            for col in row:
                period, label = TIME_PERIODS[i]
                with col:
                    st.markdown(f"**{label}**")
                    m = create_folium_basemap()
                    add_folium_heatmap(m, period_dfs[period])
                    folium_static(m, width=500, height=500)
                i += 1

    elif overview_question == "*What* is talked about *where*?":
        category_choice = st.sidebar.pills(
            "Select category:",
            ["Praise", "Ideas", "Error + Complaints"],
            selection_mode="single",
            default="Praise",
            key="overview_cat"
        )

        hex_choice = st.sidebar.pills(
            "Select analysis:",
            ["Word clouds", "Topic co-occurence"],
            selection_mode="single",
            default="Word clouds",
            key="overview_hex"
        )

        if category_choice == "Praise":
            hex_gdf = prepped_vectors["hex_bins_praise"]
            points_df = prepped_vectors["hex_points_praise"]
        elif category_choice == "Ideas":
            hex_gdf = prepped_vectors["hex_bins_idea"]
            points_df = prepped_vectors["hex_points_idea"]
        else:
            hex_gdf = prepped_vectors["hex_bins_error_complaint"]
            points_df = prepped_vectors["hex_points_error_complaint"]

        max_count = hex_gdf["count"].max()
        colormap = cm.LinearColormap(['#440154', '#fde725'], vmin=0, vmax=max_count)

        if hex_choice == "Word clouds":
            m = create_folium_hexbin_map_with_wc(
                hex_gdf,
                points_df,
                text_col="lemmas"
            )
            folium_static(m, width=700, height=500)

        elif hex_choice == "Topic co-occurence":
            st.info("remove this choice if no topic co-occurence in relation to hexbins??")

# ==================
# === SENTIMENTS ===

if section == "Sentiments":
    sentiment_question = st.sidebar.radio(
        "Choose a question:",
        ["Do sentiments vary over time?", "What sentiment dominates in what park (by location)?", "Do sentiments mix within comments?"]
    )

    if sentiment_question == "Do sentiments vary over time?":
        category_group = st.sidebar.pills(
            "Tyck till category:",
            ["Praise", "Ideas", "Error + Complaints"],
            selection_mode="single",
            default="Praise",
            key="sent_cat"
        )

        view_choice = st.sidebar.pills(
            "View:",
            ["Compare 2 years", "Compare 3 park filters"],
            selection_mode="single",
            default="Compare 2 years",
            key="sent_view"
        )

        temporal_scale = st.sidebar.pills(
            "Temporal scale:",
            ["Months", "Weekdays", "24 Hours"],
            selection_mode="single",
            default="Months",
            key="sent_temp"
        )

        charts = make_plot(
            kind="sentiment",
            category=category_group,
            view=view_choice,
            temporal_scale=temporal_scale,
            prepped_vectors=prepped_vectors
        )

        st.altair_chart(alt.hconcat(*charts).resolve_scale(y='shared'), use_container_width=True)

    elif sentiment_question == "What sentiment dominates in what park (by location)?":
        "add sentiment per park normalised by ha?"

    elif sentiment_question == "Do sentiments mix within comments?":

        chart_type = st.sidebar.pills(
            "Choose chart type:",
            ["Bar chart", "Co-occurence matrix"],
            selection_mode="single",
            default="Bar chart",
            key="mixed_chart_type"
        )

        if chart_type == "Bar chart":

            category_group = st.sidebar.pills(
                "Tyck till category:",
                ["Praise", "Ideas", "Error + Complaints"],
                selection_mode="single",
                default="Praise",
                key="sent_mixed_cat"
            )

            st.subheader(f"Mixed vs Single Sentiment: {category_group}")

            summary = get_mixed_sentiment_summary(prepped_vectors["all_pts"], category_group)
            bar_chart = plot_mixed_sentiment_bar(summary)
            #st.altair_chart(bar_chart, use_container_width=True)
            st.altair_chart(bar_chart, width=600)

        elif chart_type == "Co-occurence matrix":
            st.subheader("How sentiments combine within individual comments")

            cooc_df = compute_sentiment_cooccurrence_matrix(prepped_vectors["all_pts"])
            matrix_chart = plot_sentiment_cooccurrence_matrix(cooc_df)

            st.altair_chart(matrix_chart, use_container_width=True)

            st.caption(
                "Matrix shows how often sentiment pairs co-occur within the same comment. "
                "Values are normalized by the total number of mixed-sentiment comments."
            )


# ==============
# === TOPICS ===   *** lägg till en subpage med en dropdown lista över typ top 20 eller 50 topics och så kan man välja en och få lite olika grafer? ***

if section == "Topics":
    topic_question = st.sidebar.radio(
        "Choose a question:",
        ["Do topics vary over time?", "What are the top 5 topics per park (by location)?", "What are the top topics?","Topic co-occurence"]
    )

    if topic_question == "Do topics vary over time?":
        category_group = st.sidebar.pills(
            "Tyck till category:",
            ["Praise", "Ideas", "Error + Complaints"],
            selection_mode="single",
            default="Praise",
            key="topic_cat"
        )

        view_choice = st.sidebar.pills(
            "View:",
            ["Compare 2 years", "Compare 3 park filters"],
            selection_mode="single",
            default="Compare 2 years",
            key="topic_view"
        )

        temporal_scale = st.sidebar.pills(
            "Temporal scale:",
            ["Months", "Weekdays", "24 Hours"],
            selection_mode="single",
            default="Months",
            key="topic_temp"
        )

        charts = make_plot(
            kind="topic",
            category=category_group,
            view=view_choice,
            temporal_scale=temporal_scale,
            prepped_vectors=prepped_vectors
        )

        st.altair_chart(alt.hconcat(*charts).resolve_scale(y='shared'), use_container_width=True)

    elif topic_question == "What are the top 5 topics per park (by location)?":
        st.info("to be added")

    elif topic_question == "What are the top topics?":
        st.info("to be added")

    elif topic_question == "Topic co-occurence":
        st.subheader("Topic co-occurrence matrix")

        category_choice = st.sidebar.pills(
            "Select category:",
            ["Praise", "Ideas", "Error + Complaints"],
            selection_mode="single",
            default="Praise"
        )

        if category_choice == "Praise":
            coocc_df = prepped_vectors["hex_topic_cooccurrence_praise"]
        elif category_choice == "Ideas":
            coocc_df = prepped_vectors["hex_topic_cooccurrence_idea"]
        else:
            coocc_df = prepped_vectors["hex_topic_cooccurrence_error_complaint"]

        if coocc_df.empty:
            st.warning("Not enough data to show co-occurrences.")
        else:
            # Altair heatmap
            chart = (
                alt.Chart(coocc_df)
                    .mark_rect()
                    .encode(
                    x=alt.X("topic_a:N", title="Topic A", axis=alt.Axis(labelAngle=45)),
                    y=alt.Y("topic_b:N", title="Topic B"),
                    color=alt.Color("count:Q", scale=alt.Scale(scheme="viridis"), title="Co-occurrence count"),
                    tooltip=["topic_a", "topic_b", "count"]
                )
                    .properties(width=700, height=700)
            )
            st.altair_chart(chart, use_container_width=True)

# ==============
# === THEMES ===

if section == "Themes":
    theme_question = st.sidebar.radio(
        "Choose a question:",
        ["Theme question 1", "Theme question 2"]
    )

    if theme_question == "Theme question 1":
        st.info("add top themes bar chart")

    elif theme_question == "Theme question 2":
        st.info("add co-occurence matrix")


