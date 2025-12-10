
import os
import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import pandas as pd
import mapclassify   # OM PROBLM MED MAPCLASSIFY - kör streamlit run genom att här i pycharm gå till terminal > klicka på dropdown > välj command prompt. Testa sen om den hittar mapclassify genom att skriva python -c "import mapclassify; print(mapclassify.__version__)". Om det funkar kör vanliga streamlit run.
import altair as alt
from itertools import combinations
import rasterio
import numpy as np

from matplotlib import pyplot as plt
import folium
import branca.colormap as cm
from folium.raster_layers import ImageOverlay
from matplotlib import cm as mpl_cm
from streamlit_folium import folium_static
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject, Resampling

from folium.plugins import HeatMap
from streamlit_folium import folium_static

import itertools

st.set_page_config(layout="wide")

tycktill_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\tycktill.gpkg"
tycktill_filtered_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg"

plots_folder_path = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\plots"

raster_paths = {
    "Praise+Ideas": {
        "Day": os.path.join(plots_folder_path, "kde_praise_ideas_comments_day.tif"),       # *** change to _per_1000_residents.tif later ***
        "Night": os.path.join(plots_folder_path, "kde_praise_ideas_comments_night.tif")
    },
    "Error+Complaints": {
        "Day": os.path.join(plots_folder_path, "kde_error_complaints_comments_day.tif"),
        "Night": os.path.join(plots_folder_path, "kde_error_complaints_comments_night.tif")
    }
}

# ===================
# === LOAD LAYERS ===

@st.cache_data(show_spinner="Loading spatial data...")
def vector_layer(path: str, layer_name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path, layer=layer_name)
    return gdf.to_crs(epsg=4326)

@st.cache_data(show_spinner="Loading layers…")
def load_all_VECTOR_data():
    data = {}
    data["stats_per_park"] = vector_layer(tycktill_GPKG, "stats_per_park")
    data["all_park_related_pts_with_themes"] = vector_layer(tycktill_filtered_GPKG, "all_park_related_pts_with_themes")
    data["pts_with_topics_by_location"] = vector_layer(tycktill_filtered_GPKG, "pts_in_parks_with_topics")              # by location
    data["pts_with_topics_by_keywords_strictly"] = vector_layer(tycktill_filtered_GPKG, "park_comments_by_keyword")     # by keywords (strictly)
    data["pts_with_topics_by_keywords_similarity"] = vector_layer(tycktill_filtered_GPKG, "park_comments_by_BERTopic")  # by keywords (similarity)
    data["parks_with_top5_topics"] = vector_layer(tycktill_filtered_GPKG, "parks_with_top5_topics")
    return data
raw_vectors = load_all_VECTOR_data()

def load_and_reproject_raster(path, dst_crs="EPSG:4326"):
    with rasterio.open(path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )
        dst_array = np.empty((height, width), dtype=src.read(1).dtype)

        reproject(
            source=src.read(1),
            destination=dst_array,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear
        )
    return {"array": dst_array, "transform": transform, "crs": dst_crs}

@st.cache_data(show_spinner="Loading rasters…")
def load_all_RASTER_data():
    rasters = {}
    rasters["kde_praise_ideas_day"] = load_and_reproject_raster(raster_paths["Praise+Ideas"]["Day"])
    rasters["kde_praise_ideas_night"] = load_and_reproject_raster(raster_paths["Praise+Ideas"]["Night"])
    rasters["kde_error_complaints_day"] = load_and_reproject_raster(raster_paths["Error+Complaints"]["Day"])
    rasters["kde_error_complaints_night"] = load_and_reproject_raster(raster_paths["Error+Complaints"]["Night"])
    return rasters
raw_rasters = load_all_RASTER_data()


# ==================
# === PREPP DATA ===

def normalize_weekday(df):
    df = df.copy()

    # convert full weekday names → weekday numbers 0–6
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

    # Create consistent short labels
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    df["weekday_label"] = df["weekday_num"].map(lambda x: labels[x] if pd.notnull(x) else None)

    return df

def extract_topic_keyword_lists(df):
    df = df.copy()
    df["topic_keywords_list"] = df["topic_keywords"].str.split(", ")
    df["topic_keywords_full"] = df["topic_keywords_list"].str[:10].apply(", ".join)
    df["topic_keywords_short"] = df["topic_keywords_list"].str[:3].apply(", ".join)
    return df

def add_day_night_columns(df):
    df = df.copy()
    df["is_day"] = df["hour"].between(6, 18)
    df["is_night"] = ~df["is_day"]
    return df

def split_by_sentiment(df):
    return {
        "praise_idea": df[df["Kategori"].isin(["Beröm", "Idé"])],
        "error_complaint": df[df["Kategori"].isin(["Felanmälan", "Klagomål"])]
    }

def prepare_topic_df(df):
    df = extract_topic_keyword_lists(df)
    df = normalize_weekday(df)
    return df

def fix_sentiment_column_type(df):
    """Ensure the sentiment column is string/categorical for plotting."""
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
    """Ensure the topic column is string for plotting."""
    if "topic_keywords_short" in df.columns:
        df = df.copy()
        df["topic_keywords_short"] = df["topic_keywords_short"].astype(str)
    return df

def keep_top_n_topics(df, n=5):
    """Keep only the top N topics (by frequency) in topic_keywords_short."""
    df = df.copy()
    top_topics = df['topic_keywords_short'].value_counts().head(n).index.tolist()
    df = df[df['topic_keywords_short'].isin(top_topics)]
    return df


# add more prepp steps here AND don't forget to also add it to def prepare_data(raw) ??


def prepare_vectors(raw_vectors):
    prepped_vectors = {}

    # Prepare topic dataframes
    topics_map = {
        "pts_with_topics_by_location": "loc",
        "pts_with_topics_by_keywords_strictly": "key",
        "pts_with_topics_by_keywords_similarity": "sim"
    }

    for raw_name, suffix in topics_map.items():
        df = prepare_topic_df(raw_vectors[raw_name])
        df = fix_sentiment_column_type(df)
        df = fix_topic_column_type(df)

        prepped_vectors[f"praise_idea_{suffix}"] = split_by_sentiment(df)["praise_idea"]
        prepped_vectors[f"error_complaint_{suffix}"] = split_by_sentiment(df)["error_complaint"]

    # Prepare all_pts for heatmaps
    all_pts = add_day_night_columns(raw_vectors["all_park_related_pts_with_themes"])
    all_pts = prepare_topic_df(all_pts)
    all_pts = fix_sentiment_column_type(all_pts)
    all_pts = fix_topic_column_type(all_pts)
    prepped_vectors["all_pts"] = all_pts

    # Split heatmap datasets
    heat = split_by_sentiment(all_pts)
    prepped_vectors["heat_praise_idea"] = heat["praise_idea"]
    prepped_vectors["heat_error_complaint"] = heat["error_complaint"]

    return prepped_vectors

prepped_vectors = prepare_vectors(raw_vectors)


with st.expander("🔍 Debug preprocessing steps (column checks)"):

    st.write("## Required columns check")
    REQUIRED = ["month", "weekday", "hour", "year_label"]

    # ---- Check raw data ----
    st.write("### Raw vectors")
    for name, df in raw_vectors.items():
        st.write(f"**{name}**")
        missing = [c for c in REQUIRED if c not in df.columns]
        if missing:
            st.error(f"❌ Missing columns: {missing}")
        else:
            st.success("✔ All required columns present")

    # ---- Check each prep stage ----
    st.write("---")
    st.write("## Step-by-step preprocessing for each dataset")

    topics_map = {
        "pts_with_topics_by_location": "loc",
        "pts_with_topics_by_keywords_strictly": "key",
        "pts_with_topics_by_keywords_similarity": "sim"
    }

    for raw_name, suffix in topics_map.items():
        st.write(f"### Dataset: {raw_name}")

        df0 = raw_vectors[raw_name]
        st.write("Before:", df0.columns)

        df1 = prepare_topic_df(df0)
        st.write("After prepare_topic_df:", df1.columns)

        df2 = fix_sentiment_column_type(df1)
        st.write("After fix_sentiment_column_type:", df2.columns)

        df3 = fix_topic_column_type(df2)
        st.write("After fix_topic_column_type:", df3.columns)

        # inspect the two splits
        split = split_by_sentiment(df3)
        st.write("➡ praise_idea columns:", split["praise_idea"].columns)
        st.write("➡ error_complaint columns:", split["error_complaint"].columns)

        # explicit check for missing important fields
        for key, df_tmp in split.items():
            st.write(f"Checking {key}:")
            missing = [c for c in REQUIRED if c not in df_tmp.columns]
            if missing:
                st.error(f"❌ Missing: {missing}")
            else:
                st.success("✔ All temporal columns present")



# ====================
# === INSPECT DATA ===

# *** hide these before publishing! ***

with st.expander("🔍 Inspect raw data"):
    for name, gdf in raw_vectors.items():
        st.write(f"### {name}")
        st.write(gdf.head())
        st.write(gdf.dtypes)
        st.write(gdf.crs)

with st.expander("🔍 Inspect raster metadata"):
    for name, r in raw_rasters.items():
        st.write(f"### {name}")
        st.write("CRS:", r["crs"])
        st.write("Array shape:", r["array"].shape)

with st.expander("🔍 Inspect prepared dataframes"):
    for name, df in prepped_vectors.items():
        st.write(f"### {name}")
        st.write(df.head())
        st.write(df.dtypes)
        st.write(f"Rows: {len(df)}")

# ========================
# === PREPARE FOR MAPS ===




# =========================
# === PREPARE FOR PLOTS ===

MONTH_ORDER_JAN_DEC = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

MONTH_ORDER_JUN_MAY = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                       "Dec", "Jan", "Feb", "Mar", "Apr", "May"]

SENTIMENT_COLORS = alt.Scale(
    domain=["POSITIVE", "NEUTRAL", "NEGATIVE"],
    range=["#2ca02c", "#7f7f7f", "#d62728"]      # green, grey, red
)
TOPIC_COLORS = alt.Scale(
    scheme="tableau20"
)

CATEGORY_MAP = {
    "Praise + Ideas": "praise_idea",
    "Error + Complaints": "error_complaint"
}

# ===============================
# === TEMPORAL PREP FUNCTIONS ===

def prepare_monthly(df, kind):
    df = df.copy()
    month_map = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                 7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}

    df["month_name"] = df["month"].map(month_map)
    line_field = "sentiment_label" if kind=="sentiment" else "topic_keywords_short"

    # all combinations for zero-filling
    all_index = pd.MultiIndex.from_product(
        [df["year_label"].unique(),
         list(MONTH_ORDER_JAN_DEC),
         df[line_field].unique()],
        names=["year_label", "month_name", line_field]
    )

    out = (
        df.groupby(["year_label", "month_name", line_field])
            .size()
            .reindex(all_index, fill_value=0)
            .reset_index(name="count")
    )
    out = out.rename(columns={"month_name": "x"})
    return out

def prepare_weekday(df, kind):
    """
    Aggregate dataframe by weekday, keeping either sentiment_label or topic_keywords_short.
    Ensures all weekdays are included and counts for missing combinations are zero.
    """
    df = df.copy()
    line_field = "sentiment_label" if kind == "sentiment" else "topic_keywords_short"

    # all possible combinations of weekdays and line_field
    all_index = pd.MultiIndex.from_product(
        [["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
         df[line_field].unique()],
        names=["weekday_label", line_field]
    )

    out = (
        df.groupby(["weekday_label", line_field])
            .size()
            .reindex(all_index, fill_value=0)
            .reset_index(name="count")
    )
    out["x"] = out["weekday_label"]

    return out

def prepare_hourly(df, kind):
    """
    Aggregate dataframe by hour, keeping either sentiment_label or topic_keywords_short.
    Ensures all hours (0–23) are included and counts for missing combinations are zero.
    """
    df = df.copy()
    line_field = "sentiment_label" if kind == "sentiment" else "topic_keywords_short"

    all_index = pd.MultiIndex.from_product(
        [range(24), df[line_field].unique()],
        names=["hour", line_field]
    )

    out = (
        df.groupby(["hour", line_field])
            .size()
            .reindex(all_index, fill_value=0)
            .reset_index(name="count")
    )
    out["x"] = out["hour"]

    return out

def get_top_n_topics(df, n=5):
    """
    Return list of top N topics in a dataframe.
    """
    return df['topic_keywords_short'].value_counts().head(n).index.tolist()

def prepare_for_temporal_scale(df, temporal_scale, view, kind, top_n=5):
    df = df.copy()
    line_field = "sentiment_label" if kind == "sentiment" else "topic_keywords_short"

    if kind == "topic":
        top_topics = get_top_n_topics(df, n=top_n)
        df = df[df[line_field].isin(top_topics)]

    if temporal_scale == "Months":
        out = prepare_monthly(df, kind=kind)
        month_order = MONTH_ORDER_JAN_DEC if view == "Compare 3 park filters" else MONTH_ORDER_JUN_MAY
        out["x"] = pd.Categorical(out["x"], categories=month_order, ordered=True)

        return out

    elif temporal_scale == "Weekdays":
        out = prepare_weekday(df, kind=kind)
        weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        out["x"] = pd.Categorical(out["x"], categories=weekday_order, ordered=True)

        return out

    elif temporal_scale == "24 Hours":
        out = prepare_hourly(df, kind=kind)
        out["x"] = pd.Categorical(out["x"], categories=range(24), ordered=True)

        return out

    else:
        raise ValueError("Bad temporal scale")

def plot_single_filter_altair(df, kind, temporal_scale, title, view, color_scale=None, already_prepared=False):

    if not already_prepared:
        df_prep = prepare_for_temporal_scale(df, temporal_scale, view, kind=kind)
    else:
        df_prep = df.copy()

    #df_prep = prepare_for_temporal_scale(df, temporal_scale, view, kind=kind)
    line_field = "sentiment_label" if kind == "sentiment" else "topic_keywords_short"

    #if kind == "sentiment":
    #    line_field = "sentiment_label"
    #    color_scale = SENTIMENT_COLORS
    #elif kind == "topic":
    #    line_field = "topic_keywords_short"
    #    color_scale = TOPIC_COLORS

    chart = (
        alt.Chart(df_prep, title=title)
            .mark_line(point=True)
            .encode(
            x=alt.X(
                "x:N",
                sort=list(df_prep["x"].cat.categories),
                title="Months",
                axis=alt.Axis(labelAngle=0)
            ),
            y="count:Q",
            color=alt.Color(line_field, scale=color_scale),
            tooltip=[line_field, "count", "x"]
        )
            .properties(height=250)
    )

    return chart

def plot_compare_years(df, kind, temporal_scale, view):
    df_prep = prepare_for_temporal_scale(df, temporal_scale, view, kind=kind)

    line_field = "sentiment_label" if kind == "sentiment" else "topic_keywords_short"
    color_scale = SENTIMENT_COLORS if kind == "sentiment" else TOPIC_COLORS

    chart = (
        alt.Chart(df_prep)
            .mark_line(point=True)
            .encode(
            x=alt.X(
                "x:N",
                sort=list(df_prep["x"].cat.categories),
                title="Months",
                axis=alt.Axis(labelAngle=0)
            ),
            y=alt.Y("count:Q", title="Count"),
            color=alt.Color(line_field, scale=color_scale),
            tooltip=["year_label:N", line_field + ":N", "count:Q"]
        )
            .properties(height=300, title=f"Year {df['year_label'].iloc[0]}")
    )

    return chart

def plot_compare_filters(datasets, kind, temporal_scale, view, top_n=5):

    line_field = "sentiment_label" if kind == "sentiment" else "topic_keywords_short"

    if kind == "topic":
        # Collect top topics across all datasets
        all_top_topics = set()
        for df in datasets.values():
            all_top_topics.update(get_top_n_topics(df, n=top_n))
        all_top_topics = list(all_top_topics)
        color_scale = alt.Scale(domain=all_top_topics, scheme="tableau20")
    else:
        color_scale = SENTIMENT_COLORS

    plots = []

    # process each dataset
    for title, df in datasets.items():
        df = df.copy()
        df["filter"] = title

        # Keep only top topics if needed
        if kind == "topic":
            df = df[df[line_field].isin(all_top_topics)]

        # --- Fill zeros and remove duplicates ---
        df_prep = prepare_for_temporal_scale(df, temporal_scale, view, kind=kind)



        # --------------------------------------------------
        # FIX FOR MONTH TOPIC COMPARE-3-FILTERS
        # (second prep removed)
        # --------------------------------------------------
        if kind == "topic" and temporal_scale == "Months" and view == "Compare 3 park filters":
            # For months x topics, group first to remove duplicates
            df_prep = (
                df_prep.groupby(["x", line_field], as_index=False)["count"]
                .sum()
            )
            # Then reindex to ensure all month × topic combinations exist
            all_index = pd.MultiIndex.from_product(
                [MONTH_ORDER_JAN_DEC, all_top_topics],
                names=["x", line_field]
            )
            df_prep = (
                df_prep.set_index(["x", line_field])
                .reindex(all_index, fill_value=0)
                .reset_index()
            )
            df_prep["x"] = pd.Categorical(
                df_prep["x"],
                categories=MONTH_ORDER_JAN_DEC,
                ordered=True
            )

        # --- Ensure categorical ordering for months ---
        if temporal_scale == "Months":
            month_order = MONTH_ORDER_JAN_DEC if view == "Compare 3 park filters" else MONTH_ORDER_JUN_MAY
            df_prep["x"] = pd.Categorical(df_prep["x"], categories=month_order, ordered=True)
        elif temporal_scale == "Weekdays":
            weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            df_prep["x"] = pd.Categorical(df_prep["x"], categories=weekday_order, ordered=True)
        elif temporal_scale == "24 Hours":
            df_prep["x"] = pd.Categorical(df_prep["x"], categories=range(24), ordered=True)

        chart = (
            alt.Chart(df_prep, title=title)
                .mark_line(point=True)
                .encode(
                x=alt.X("x:N", sort=list(df_prep["x"].cat.categories)),
                y="count:Q",
                color=alt.Color(line_field, scale=color_scale),
                strokeDash=alt.StrokeDash("filter:N"),  # <-- FIX duplicated lines
                tooltip=["filter:N", line_field, "count", "x"]
            )
                .properties(height=250)
        )

        plots.append(chart)

    return plots

def make_plot(kind, category, view, temporal_scale, prepped_vectors):
    cat_key = CATEGORY_MAP[category]

    if view == "Compare 3 park filters":
        datasets = {
            "Location filter (loc)": prepped_vectors[f"{cat_key}_loc"],
            "Keyword filter (key)": prepped_vectors[f"{cat_key}_key"],
            "Similarity filter (sim)": prepped_vectors[f"{cat_key}_sim"]
        }
        return plot_compare_filters(
            datasets=datasets,
            kind=kind,
            temporal_scale=temporal_scale,
            view=view
        )

    if view == "Compare 2 years":
        df = prepped_vectors["all_pts"]
        charts = []

        for year in sorted(df["year_label"].unique()):
            df_year = df[df["year_label"] == year]
            chart = plot_compare_years(
                df=df_year,
                kind=kind,
                temporal_scale=temporal_scale,
                view=view
            )
            charts.append(chart)

        return charts

    raise ValueError("Unknown view")


with st.expander("🔍 Debug prepped_vectors content"):
    for name, df in prepped_vectors.items():
        st.write(f"### {name}")
        st.write("Columns:", df.columns.tolist())
        st.write("Rows:", len(df))
        missing = [c for c in ["month","weekday","hour","year_label"] if c not in df.columns]
        if missing:
            st.error(f"Missing: {missing}")
        else:
            st.success("✔ All temporal columns present")


# =================
# === PAGE HEAD ===

st.title("Vad tycker besökarna om Stockholms parker?")
st.text("Här finner du sammanställd data från appen TyckTill! Välj bland alternativen nedan för att se resultat av vår analys.")

st.sidebar.button("Clear Cache", on_click=st.cache_data.clear)

# =================================
# === SELECTIONS IN THE SIDEBAR ===

section = st.sidebar.pills(
    "Make a selection:",
    ["Overview", "Sentiments", "Topics", "Themes"]
)

# ================
# === OVERVIEW ===

if section == "Overview":
    overview_question = st.sidebar.radio(
        "Choose a question:",
        ["Where is Tyck till being used? (html heatmap)", "Where is Tyck till being used? (raw raster)"]
    )

    if overview_question == "Where is Tyck till being used? (html heatmap)":
        st.info("to be added")

        #if st.checkbox("Show filtered data"):
        #    st.write(filtered_df.head())
        #    st.write(filtered_df.columns)   # add this to all selections?

    elif overview_question == "Where is Tyck till being used? (raw raster)":
        st.info("to be added")

# ==================
# === SENTIMENTS ===

if section == "Sentiments":
    sentiment_question = st.sidebar.radio(
        "Choose a question:",
        ["Do sentiments vary over time?", "Sentiment question 2"]
    )

    if sentiment_question == "Do sentiments vary over time?":

        st.sidebar.divider()

        category_group = st.sidebar.pills(
            "Tyck till category:",
            ["Praise + Ideas", "Error + Complaints"],
            selection_mode="single",
            key="sent_cat",
            default="Praise + Ideas"
        )

        view_choice = st.sidebar.pills(
            "View:",
            ["Compare 2 years", "Compare 3 park filters"],
            selection_mode="single",
            key="sent_view",
            default="Compare 2 years"
        )

        temporal_scale = st.sidebar.pills(
            "Temporal scale:",
            ["Months", "Weekdays", "24 Hours"],
            selection_mode="single",
            key="sent_temp",
            default="Months"
        )

        charts = make_plot(
            kind="sentiment",
            category=category_group,
            view=view_choice,
            temporal_scale=temporal_scale,
            prepped_vectors=prepped_vectors
        )

        for chart in charts:
            st.altair_chart(chart, use_container_width=True)

        # add separate tabs for figure and for data inspection (the latter so that visibility can be turned on or off?)
        #if st.checkbox("Show filtered data"):
        #    st.write(filtered_df.head())
        #    st.write(filtered_df.columns)   # add this to all selections?

    elif sentiment_question == "Sentiment question 2":
        st.info("to be added")

# ==================
# === TOPICS ===

if section == "Topics":
    topic_question = st.sidebar.radio(
        "Choose a question:",
        ["Do topics vary over time?", "Topic question 2"]
    )

    if topic_question == "Do topics vary over time?":

        category_group = st.sidebar.pills(
            "Tyck till category:",
            ["Praise + Ideas", "Error + Complaints"],
            selection_mode="single",
            key="topic_cat",
            default="Praise + Ideas"
        )

        view_choice = st.sidebar.pills(
            "View:",
            ["Compare 2 years", "Compare 3 park filters"],
            selection_mode="single",
            key="topic_view",
            default="Compare 2 years"
        )

        temporal_scale = st.sidebar.pills(
            "Temporal scale:",
            ["Months", "Weekdays", "24 Hours"],
            selection_mode="single",
            key="topic_temp",
            default="Months"
        )

        charts = make_plot(
            kind="topic",
            category=category_group,
            view=view_choice,
            temporal_scale=temporal_scale,
            prepped_vectors=prepped_vectors
        )

        for chart in charts:
            st.altair_chart(chart, use_container_width=True)

# ==================
# === THEMES ===

if section == "Themes":
    theme_question = st.sidebar.radio(
        "Choose a question:",
        ["Theme question 1", "Theme question 2"]
    )

    if theme_question == "Theme question 1":
        st.info("to be added")

    elif theme_question == "Theme question 2":
        st.info("to be added")