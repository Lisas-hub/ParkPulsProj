
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

# add more prepp steps here AND don't forget to also add it to def prepare_data(raw) ??


def prepare_vectors(raw_vectors):
    prepped_vectors = {}

    # === PREP TOPICS ===
    topics_loc = prepare_topic_df(raw_vectors["pts_with_topics_by_location"])
    topics_key = prepare_topic_df(raw_vectors["pts_with_topics_by_keywords_strictly"])
    topics_sim = prepare_topic_df(raw_vectors["pts_with_topics_by_keywords_similarity"])

    # === SPLIT BY SENTIMENT ===
    # Praise + Ideas
    prepped_vectors["praise_idea_loc"] = split_by_sentiment(topics_loc)["praise_idea"]
    prepped_vectors["praise_idea_key"] = split_by_sentiment(topics_key)["praise_idea"]
    prepped_vectors["praise_idea_sim"] = split_by_sentiment(topics_sim)["praise_idea"]
    # Error + Complaints
    prepped_vectors["error_complaint_loc"] = split_by_sentiment(topics_loc)["error_complaint"]
    prepped_vectors["error_complaint_key"] = split_by_sentiment(topics_key)["error_complaint"]
    prepped_vectors["error_complaint_sim"] = split_by_sentiment(topics_sim)["error_complaint"]

    # === PREP HEATMAP DATA ===
    all_pts = add_day_night_columns(raw_vectors["all_park_related_pts_with_themes"])
    prepped_vectors["all_pts"] = all_pts

    # === SPLIT HEATMAPS ===
    heat = split_by_sentiment(all_pts)
    prepped_vectors["heat_praise_idea"] = heat["praise_idea"]
    prepped_vectors["heat_error_complaint"] = heat["error_complaint"]

    return prepped_vectors

prepped_vectors = prepare_vectors(raw_vectors)

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

SENTIMENT_LINES = ["POSITIVE", "NEUTRAL", "NEGATIVE"]

TOPIC_LINES = {}

MONTH_ORDER_JAN_DEC = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

MONTH_ORDER_JUN_MAY = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                       "Dec", "Jan", "Feb", "Mar", "Apr", "May"]

SENTIMENT_COLORS = {
    "POSITIVE": "#4CAF50",
    "NEUTRAL": "#FFC107",
    "NEGATIVE": "#F44336",
}

TOPIC_COLORS = ["tab20"]


###########################
# CHECK ALL BELOW - need to be adapted to use the 3 filters and year_label properly. And so lines are per sentiment or topic, not filter or year!

CATEGORY_MAP = {
    "Praise + Ideas": "praise_idea",
    "Error + Complaints": "error_complaint"
}

def prepare_monthly(df):
    df = df.copy()
    df["month_name"] = df["timestamp"].dt.strftime("%b")
    df = df.groupby(["year", "month_name"]).size().reset_index(name="count")
    return df

def prepare_weekday(df):
    return df.groupby("weekday_label").size().reindex(
        ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], fill_value=0
    )

def plot_sentiments(data, view, temporal_scale):
    # choose which prep function to call
    if temporal_scale == "Months":
        df = prepare_monthly(data)
        month_order = MONTH_ORDER_JUN_MAY if view == "Compare 2 years" else MONTH_ORDER_JAN_DEC
        df["month_name"] = pd.Categorical(df["month_name"], categories=month_order, ordered=True)
        df = df.sort_values("month_name")

    elif temporal_scale == "Weekdays":
        df = prepare_weekday(data)

    elif temporal_scale == "24 Hours":
        st.info("to be added")
        #df = prepare_hourly(data)

    fig, ax = plt.subplots(figsize=(8, 4))
    for line in SENTIMENT_LINES:
        subset = df[df["sentiment"] == line]
        ax.plot(subset["x"], subset["count"], label=line, color=SENTIMENT_COLORS[line])

    ax.legend()
    return fig

def plot_topics(data, view, temporal_scale):
    topic_names = data["topic_keywords_short"].unique()[:5]  # dynamic

    if temporal_scale == "Months":
        df = prepare_monthly(data)
        month_order = MONTH_ORDER_JAN_DEC if view == "Compare 3 park filters" else MONTH_ORDER_JUN_MAY
        df["month_name"] = pd.Categorical(df["month_name"], categories=month_order, ordered=True)
        df = df.sort_values("month_name")

    elif temporal_scale == "Weekdays":
        df = prepare_weekday(data)

    elif temporal_scale == "24 Hours":
        st.info("to be added")
        #df = prepare_hourly(data)

    fig, ax = plt.subplots(figsize=(8, 4))
    for i, topic in enumerate(topic_names):
        subset = df[df["topic_keywords_short"] == topic]
        ax.plot(subset["x"], subset["count"], label=topic, color=TOPIC_COLORS[i])

    ax.legend()
    return fig

def make_plot(kind, tycktill_category, view, temporal_scale, prepped_vectors):
    if kind == "sentiment":
        data = prepped_vectors[f"{tycktill_category}_{view}_df"]   # or however you structure categories
        return plot_sentiments(data, view, temporal_scale)

    elif kind == "topic":
        data = prepped_vectors[f"{tycktill_category}_{view}_df"]
        return plot_topics(data, view, temporal_scale)

    else:
        raise ValueError("Unknown plot kind")


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
        st.sidebar.write("Specify what version of plot to show:")

        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            category_group = st.sidebar.pills(
                "Tyck till category:",
                ["Praise + Ideas", "Error + Complaints"],
                selection_mode="single",
                key="sentiment_selection_2",
                default="Praise + Ideas"
            )

        with col2:
            view_choice = st.sidebar.pills(
                "View:",
                ["Compare 2 years", "Compare 3 park filters"],
                selection_mode="single",
                key="sentiment_selection_3",
                default="Compare 2 years"
            )

        with col3:
            temporal_scale = st.sidebar.pills(
                "Temporal scale:",
                ["Months", "Weekdays", "24 Hours"],
                selection_mode="single",
                key="sentiment_selection_4",
                default="Months"
            )
        fig = make_plot(
            kind="sentiment",
            category=category_group,
            view=view_choice,
            temporal_scale=temporal_scale,
            prepped_vectors=prepped_vectors
        )
        st.pyplot(fig)

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
        st.info("to be added")

    elif topic_question == "Topic question 2":
        st.info("to be added")

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