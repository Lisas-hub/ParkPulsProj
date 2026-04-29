
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

plots_folder_path = r"/data/tycktill_output/plots"  # ^^^ OBS!

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
# === load layers ===

@st.cache_data(show_spinner="Loading spatial data...")
def load_layer(path: str, layer_name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path, layer=layer_name)
    return gdf.to_crs(epsg=4326)

@st.cache_data(show_spinner="Loading layers…")
def load_all_data():
    data = {}
    data["stats_per_park"] = load_layer(tycktill_GPKG, "stats_per_park")
    data["all_park_related_pts_with_themes"] = load_layer(tycktill_filtered_GPKG, "all_park_related_pts_with_themes")
    data["pts_with_topics_by_location"] = load_layer(tycktill_filtered_GPKG, "pts_in_parks_with_topics")              # by location
    data["pts_with_topics_by_keywords_strictly"] = load_layer(tycktill_filtered_GPKG, "park_comments_by_keyword")     # by keywords (strictly)
    data["pts_with_topics_by_keywords_similarity"] = load_layer(tycktill_filtered_GPKG, "park_comments_by_BERTopic")  # by keywords (similarity)
    data["parks_with_top5_topics"] = load_layer(tycktill_filtered_GPKG, "parks_with_top5_topics")
    return data
raw = load_all_data()

@st.cache_data(show_spinner="Loading raster...")
def load_raster(path: str):
    with rasterio.open(path) as src:
        data = src.read(1)  # single band
        transform = src.transform
        crs = src.crs
    return {"array": data, "transform": transform, "crs": crs}


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
def load_all_rasters():
    rasters = {}
    rasters["kde_praise_ideas_day"]   = load_and_reproject_raster(raster_paths["Praise+Ideas"]["Day"])
    rasters["kde_praise_ideas_night"] = load_and_reproject_raster(raster_paths["Praise+Ideas"]["Night"])
    rasters["kde_error_complaints_day"]   = load_and_reproject_raster(raster_paths["Error+Complaints"]["Day"])
    rasters["kde_error_complaints_night"] = load_and_reproject_raster(raster_paths["Error+Complaints"]["Night"])
    return rasters
rasters = load_all_rasters()

st.sidebar.button("Clear Cache", on_click=st.cache_data.clear)

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


def prepare_data(raw):

    prepped = {}

    # ======
    # topics

    def prepare_keywords(df):
        df = df.copy()
        df["topic_keywords_list"] = df["topic_keywords"].str.split(", ")                          # convert the comma-separated string to a list
        df["topic_keywords_full"] = df["topic_keywords_list"].str[:10].apply(lambda x: ", ".join(x))  # full list = all 10 keywords
        df["topic_keywords_short"] = df["topic_keywords_list"].str[:3].apply(lambda x: ", ".join(x))  # short list = first 3 keywords
        return df

    # apply list variants to all three filters
    topics_loc = prepare_keywords(raw["pts_with_topics_by_location"])
    topics_key = prepare_keywords(raw["pts_with_topics_by_keywords_strictly"])
    topics_sim = prepare_keywords(raw["pts_with_topics_by_keywords_similarity"])

    # apply weekday fix (from Monday, Tuesday, ... to 0, 1, ...)
    topics_loc = normalize_weekday(topics_loc)
    topics_key = normalize_weekday(topics_key)
    topics_sim = normalize_weekday(topics_sim)

    # create two groups based on Kategori
    prepped.update({
        # Praise / Idea
        "praise_idea_loc": topics_loc[topics_loc["Kategori"].isin(["Beröm", "Idé"])],
        "praise_idea_key": topics_key[topics_key["Kategori"].isin(["Beröm", "Idé"])],
        "praise_idea_sim": topics_sim[topics_sim["Kategori"].isin(["Beröm", "Idé"])],
        # Error / Complaint
        "error_complaint_loc": topics_loc[topics_loc["Kategori"].isin(["Felanmälan", "Klagomål"])],
        "error_complaint_key": topics_key[topics_key["Kategori"].isin(["Felanmälan", "Klagomål"])],
        "error_complaint_sim": topics_sim[topics_sim["Kategori"].isin(["Felanmälan", "Klagomål"])],
    })

    # prepp for heatmaps
    # add day/night boolean columns
    all_pts = raw["all_park_related_pts_with_themes"].copy()

    all_pts["is_day"] = all_pts["hour"].between(6, 18)
    all_pts["is_night"] = ~all_pts["is_day"]  # everything else

    prepped["all_pts"] = all_pts

    # kategrori subsets
    prepped["heat_praise_idea"] = all_pts[all_pts["Kategori"].isin(["Beröm", "Idé"])]
    prepped["heat_error_complaint"] = all_pts[all_pts["Kategori"].isin(["Felanmälan", "Klagomål"])]

    return prepped

prepped = prepare_data(raw)


# ============
# === MAPS ===

def create_base_map():
    m = folium.Map(location=(59.33, 17.99), zoom_start=10.5, tiles=None)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satellite',
        overlay=False,
        control=True
    ).add_to(m)
    return m

def add_top5_topics_layer(m, gdf, column):

    for _, row in gdf.iterrows():

        popup_val = row.get(column, "")

        if isinstance(popup_val, str) and popup_val.strip():
            rows = [r.strip() for r in popup_val.split("\n") if r.strip()]
            topic_lines = "".join([f"<div>{r}</div>" for r in rows])
            popup_html = f"""
            <div style="font-size:13px; line-height:1.4;">
                <b>Top 5 Topics in this Park:</b><br>
                {topic_lines}
            </div>
            """
        else:
            popup_html = """
            <div style="font-size:13px;">
                <i>No topics in this park</i>
            </div>
            """

        folium.GeoJson(
            row["geometry"],
            popup=folium.Popup(popup_html, max_width=500),
            style_function=lambda feature: {
                "fillColor": "#4e79a7",
                "color": "black",
                "weight": 0.8,
                "fillOpacity": 0.45,
            }
        ).add_to(m)

# remove this map? or make prettier
def overlay_raster_on_map(base_map, raster_array, transform, vmax=None, colormap='magma', upscale_factor=2):   # ⬅️ Increase to 3 or 4 for smoother rendered maps
    """
    Overlays a raster on a Folium map using bilinear upscaling to avoid blockiness.

    - NoData (-9999) is transparent
    - Values = 0 are transparent
    - Raster is upscaled for smooth display
    """

    # --- 1. Mask nodata and zeros ---
    masked = raster_array.astype(float)
    masked[(masked == -9999) | (masked == 0)] = np.nan

    # --- 2. Determine max for normalization ---
    if vmax is None:
        vmax = np.nanmax(masked)

    norm = masked / vmax

    # --- 3. Upscale for smoother visualization ---
    if upscale_factor > 1:
        from scipy.ndimage import zoom
        norm = zoom(norm, upscale_factor, order=1)  # bilinear resampling

    # --- 4. Convert to RGBA ---
    cmap = mpl_cm.get_cmap(colormap)
    rgba_img = cmap(norm)
    rgba_img = (rgba_img * 255).astype(np.uint8)

    # Transparent where NaN
    alpha = np.where(np.isnan(norm), 0, 255).astype(np.uint8)
    rgba_img[..., 3] = alpha

    # --- 5. Recompute bounds (they do NOT change with upscaling!) ---
    minx = transform[2]
    maxy = transform[5]
    pixel_size_x = transform[0]
    pixel_size_y = -transform[4]

    height, width = raster_array.shape
    maxx = minx + width * pixel_size_x
    miny = maxy - height * pixel_size_y

    bounds = [[miny, minx], [maxy, maxx]]

    # --- 6. Add to map ---
    img_overlay = ImageOverlay(
        image=rgba_img,
        bounds=bounds,
        opacity=1,
        interactive=True,
        origin='upper'
    )

    img_overlay.add_to(base_map)
    return base_map

def add_heatmap(m, gdf, radius=15, blur=10, max_zoom=13):
    # Extract [lat, lon] from geometry
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


# ===============
# === FIGURES ===

# ==================
# Variable over time

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

MONTH_LABELS_JUN_TO_MAY = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                           "Dec", "Jan", "Feb", "Mar", "Apr", "May"]

def add_month_label(df):
    df = df.copy()
    df["month_label"] = df["month"].apply(lambda m: MONTH_LABELS[m-1])
    return df

#WEEKDAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_ORDER = list(range(7))  # 0–6

def prepare_for_chart(df, mode, temporal_scale, group_top_n=5):
    if temporal_scale == "Months":
        return prepare_for_chart_by_month(df, mode, group_top_n)
    elif temporal_scale == "Weekdays":
        return prepare_for_chart_by_weekday(df, mode, group_top_n)
    elif temporal_scale == "24 Hours":
        return pd.DataFrame()


def prepare_for_chart_by_month(df, mode, group_top_n=5):

    """
    mode = 'sentiment' or 'topics'

    Returns dataframe with:
        month (1-12)
        month_label ("Jan"…)
        group_label (sentiment_label OR topic_keywords_short)
        count
        year_label (if exists in df)
    """

    if df.empty:
        return pd.DataFrame()

    df = add_month_label(df).copy()

    if mode == "sentiment":

        if "sentiment_label" not in df.columns:
            return pd.DataFrame()

        df["group_label"] = df["sentiment_label"]

        agg = (
            df.groupby(["month", "month_label", "group_label"])
              .size()
              .reset_index(name="count")
        )

        # attach year_label
        if "year_label" in df.columns:
            year_map = (
                df[["month", "month_label", "group_label", "year_label"]]
                .drop_duplicates()
            )
            agg = agg.merge(
                year_map,
                on=["month", "month_label", "group_label"],
                how="left"
            )

        return agg

    if mode == "topics":

        if "topic" not in df.columns:
            return pd.DataFrame()

        topic_counts = (
            df.groupby("topic")
              .size()
              .reset_index(name="total_count")
              .sort_values("total_count", ascending=False)
        )

        top_topics = topic_counts.head(group_top_n)["topic"].tolist()

        df_small = df[df["topic"].isin(top_topics)].copy()

        if df_small.empty:
            return pd.DataFrame()

        df_small = add_month_label(df_small)

        # group_label = topic_keywords_short
        df_small["group_label"] = df_small["topic_keywords_short"]

        agg = (
            df_small.groupby(["month", "month_label", "group_label"])
                    .size()
                    .reset_index(name="count")
        )

        # attach year_label
        if "year_label" in df_small.columns:
            year_map = (
                df_small[["month", "month_label", "group_label", "year_label"]]
                .drop_duplicates()
            )
            agg = agg.merge(
                year_map,
                on=["month", "month_label", "group_label"],
                how="left"
            )

        return agg

    return pd.DataFrame()

def prepare_for_chart_by_weekday(df, mode, group_top_n=5):
    """
    mode = 'sentiment' or 'topics'
    Returns: weekday (0-6), weekday_label, group_label, count, year_label (optional)
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()

    # --- Ensure weekday exists and is numeric 0–6 ---
    if "weekday_num" in df.columns:
        df["weekday"] = df["weekday_num"].astype(int)
    else:
        if "weekday" in df.columns:
            df["weekday"] = df["weekday"].map({
                "Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6,
                "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6
            }).astype(int)
        elif "created_at" in df.columns:
            df["weekday"] = df["created_at"].dt.weekday
        else:
            raise ValueError("No weekday info available")

    # --- Use weekday_label from normalized data ---
    if "weekday_label" not in df.columns:
        df["weekday_label"] = df["weekday"].map(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])

    # --- Ensure year_label exists ---
    if "year_label" not in df.columns:
        if "created_at" in df.columns:
            df["year_label"] = df["created_at"].dt.year.astype(str)
        else:
            df["year_label"] = "All years"

    # ========================
    #   SENTIMENT MODE
    # ========================
    if mode == "sentiment":
        if "sentiment_label" not in df.columns:
            return pd.DataFrame()

        df["group_label"] = df["sentiment_label"]

        agg = (
            df.groupby(["weekday", "weekday_label", "group_label", "year_label"])
              .size()
              .reset_index(name="count")
        )
        return agg

    # ========================
    #   TOPIC MODE
    # ========================
    if mode == "topics":

        topic_col = (
            "topic_keywords_short"
            if "topic_keywords_short" in df.columns
            else "topic"
        )
        if topic_col not in df.columns:
            return pd.DataFrame()

        # top-N per year:
        top_topics = (
            df.groupby(["year_label", topic_col])
              .size()
              .reset_index(name="total")
        )

        top_topics["rank"] = (
            top_topics.groupby("year_label")["total"].rank(method="first", ascending=False)
        )
        top_topics = top_topics[top_topics["rank"] <= group_top_n]

        df = df.merge(top_topics[[topic_col, "year_label"]], on=["year_label", topic_col], how="inner")

        df["group_label"] = df[topic_col]

        agg = (
            df.groupby(["weekday", "weekday_label", "group_label", "year_label"])
              .size()
              .reset_index(name="count")
        )

        return agg

    return pd.DataFrame()

def prepare_for_chart_by_hour(df, mode, group_top_n=5):
    """
    mode = 'sentiment' or 'topics'
    Returns: hour (0–23), group_label, count, year_label (if exists)
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()

    # Ensure hour exists and is int
    if "hour" not in df.columns:
        return pd.DataFrame()
    df["hour"] = df["hour"].astype(int)

    if mode == "sentiment":
        if "sentiment_label" not in df.columns:
            return pd.DataFrame()

        df["group_label"] = df["sentiment_label"]

        agg = (
            df.groupby(["hour", "group_label"])
              .size()
              .reset_index(name="count")
        )

        if "year_label" in df.columns:
            year_map = df[["hour", "group_label", "year_label"]].drop_duplicates()
            agg = agg.merge(year_map, on=["hour", "group_label"], how="left")

        return agg

    if mode == "topics":
        if "topic" not in df.columns:
            return pd.DataFrame()

        # Find top N topics globally
        topic_counts = (
            df.groupby("topic")
              .size()
              .reset_index(name="total_count")
              .sort_values("total_count", ascending=False)
        )
        top_topics = topic_counts.head(group_top_n)["topic"].tolist()

        df_small = df[df["topic"].isin(top_topics)].copy()

        if df_small.empty:
            return pd.DataFrame()

        df_small["group_label"] = df_small["topic_keywords_short"]

        agg = (
            df_small.groupby(["hour", "group_label"])
                    .size()
                    .reset_index(name="count")
        )

        if "year_label" in df_small.columns:
            year_map = (
                df_small[["hour", "group_label", "year_label"]]
                .drop_duplicates()
            )
            agg = agg.merge(
                year_map,
                on=["hour", "group_label"],
                how="left"
            )

        return agg

    return pd.DataFrame()


def chart_month_panel(df, title, months_order):
    if df.empty:
        return None

    chart = (
        alt.Chart(df)
            .mark_line(point=True)
            .encode(
                x=alt.X("month_label:N",
                        sort=months_order,
                        title="Month"),
                y=alt.Y("count:Q",
                        title="Number of comments"),
                color=alt.Color("group_label:N",
                                title=""),
                tooltip=["month_label", "group_label", "count"]
            )
            .properties(title=title, width=300, height=250)
    )
    return chart

def chart_weekday_panel(df, title):
    if df.empty:
        return None

    is_sentiment = set(df["group_label"].unique()).issubset({"POSITIVE", "NEUTRAL", "NEGATIVE"})

    if is_sentiment:
        color_scale = alt.Scale(
            domain=["POSITIVE", "NEUTRAL", "NEGATIVE"],
            range=["#2ca02c", "#7f7f7f", "#d62728"]
        )
        legend = alt.Legend(orient="right", direction="vertical")
    else:
        color_scale = alt.Scale(scheme="tableau20")
        legend = alt.Legend(orient="bottom", direction="vertical", labelLimit=500)

    chart = (
        alt.Chart(df)
            .mark_line(point=True, strokeWidth=2)
            .encode(
            x=alt.X(
                "weekday_label:N",
                sort=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                title="Weekday"
            ),
            y=alt.Y("count:Q", title="Number of comments"),
            color=alt.Color("group_label:N", scale=color_scale, title="", legend=legend),
            tooltip=["weekday_label", "group_label", "count"],
        )
            .properties(title=title, width=300, height=250)
    )
    return chart

def chart_hour_panel(df, title):
    if df.empty:
        return None

    is_sentiment = set(df["group_label"].unique()).issubset(
        {"POSITIVE", "NEUTRAL", "NEGATIVE"}
    )

    if is_sentiment:
        color_scale = alt.Scale(
            domain=["POSITIVE", "NEUTRAL", "NEGATIVE"],
            range=["#2ca02c", "#7f7f7f", "#d62728"]
        )
        legend = alt.Legend(orient="right", direction="vertical")
    else:
        color_scale = alt.Scale(scheme="tableau20")
        legend = alt.Legend(orient="bottom", direction="vertical", labelLimit=600)

    chart = (
        alt.Chart(df)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X(
                "hour:O",
                sort=list(range(24)),
                title="Hour of day (0–23)"
            ),
            y=alt.Y("count:Q", title="Number of comments"),
            color=alt.Color("group_label:N", scale=color_scale, title="", legend=legend),
            tooltip=["hour", "group_label", "count"]
        )
        .properties(title=title, width=300, height=250)
    )
    return chart


# combine charts horizontally
def chart_multi_panel(dfs, titles, ordered_months, mode=None):

    if not dfs or all(len(df) == 0 for df in dfs):
        return None

    panels = []

    # which month labels to show on axis
    month_labels = ordered_months
    month_order_map = {m: i for i, m in enumerate(ordered_months)}

    for df, title in zip(dfs, titles):

        if df.empty:
            continue

        df = df.copy()

        is_sentiment = set(df["group_label"].unique()).issubset({"POSITIVE", "NEUTRAL", "NEGATIVE"})

        if is_sentiment:
            color_scale = alt.Scale(
                domain=["POSITIVE", "NEUTRAL", "NEGATIVE"],
                range=["#2ca02c",   # green
                       "#7f7f7f",   # grey
                       "#d62728"]   # red
            )
            legend = alt.Legend(orient="right", direction="vertical")
        else:
            color_scale = alt.Scale(scheme="tableau20")
            legend = alt.Legend(orient="bottom", direction="vertical", labelLimit=500)

        # month ordering
        df["month_order"] = df["month_label"].map(month_order_map)

        # force break of the line between years May-June
        if len(dfs) == 2 and "year_label" in df.columns:
            def add_break(g):
                g = g.sort_values("month_order")
                last = g.iloc[-1]

                # insert a null row breaks altair line path
                b = last.copy()
                b["month_order"] = None
                b["count"] = None
                b["month_label"] = None
                return pd.concat([g, pd.DataFrame([b])], ignore_index=True)

            df = (
                df.groupby(["group_label", "year_label"], group_keys=False)
                    .apply(add_break)
            )

        x_field = "month_order:O"

        chart = (
            alt.Chart(df)
                .mark_line(point=True, strokeWidth=2)
                .encode(
                x=alt.X(
                    x_field,
                    axis=alt.Axis(
                        title="Month",
                        labels=True,
                        labelExpr=f"""['{"','".join(month_labels)}'][datum.value]"""    # Change?
                    ),
                    scale=alt.Scale(
                        domain=[i for i in range(len(month_labels))]
                    )
                ),
                y=alt.Y("count:Q", title="Number of comments"),
                color=alt.Color(
                    "group_label:N",
                    scale=color_scale,
                    title="Sentiment" if is_sentiment else "Topic",
                    legend=legend
                ),
                tooltip=["month_label", "group_label", "count"]
            )
                .properties(title=title, width=300, height=250)
        )

        panels.append(chart)

    return alt.hconcat(*panels).resolve_scale(color="shared", y="shared")


# ==========================
# === TABS, BUTTONS, ETC ===

st.title("Vad tycker besökarna om Stockholms parker?")
st.text("Här finner du sammanställd data från appen TyckTill! Välj bland alternativen nedan för att se resultat av vår analys.")

tab_overview, tab_sentiments, tab_topics, tab_themes, tab_temp_test = st.tabs(["Overview", "Sentiments", "Topics", "Themes", "TEMP TEST"])

# ===============
# TAB 1: overview

with tab_overview:

    overview_question = st.radio(
        "Choose a map to show:",
        ["Overview question 1", "Tyck till entries map"],
        key="overview_selection_1",
        index=None
    )
    st.divider()

    if overview_question == "Overview question 1":

        category = st.pills("Tyck till category:",
                            ["Praise + Ideas",
                             "Error + Complaints"],
                            default="Praise + Ideas"
                            )

        if category == "Praise + Ideas":
            day_raster = rasters["kde_praise_ideas_day"]["array"]
            night_raster = rasters["kde_praise_ideas_night"]["array"]
            day_transform = rasters["kde_praise_ideas_day"]["transform"]
            night_transform = rasters["kde_praise_ideas_night"]["transform"]
        else:
            day_raster = rasters["kde_error_complaints_day"]["array"]
            night_raster = rasters["kde_error_complaints_night"]["array"]
            day_transform = rasters["kde_error_complaints_day"]["transform"]
            night_transform = rasters["kde_error_complaints_night"]["transform"]

        vmax = max(np.nanmax(day_raster), np.nanmax(night_raster))

        col1, col2 = st.columns(2)

        with col1:
            m_day = create_base_map()
            overlay_raster_on_map(m_day, day_raster, day_transform, vmax=vmax, colormap='magma')
            folium_static(m_day, width=600, height=500)  # use streamlit_folium

        with col2:
            m_night = create_base_map()
            overlay_raster_on_map(m_night, night_raster, night_transform, vmax=vmax, colormap='magma')
            folium_static(m_night, width=600, height=500)


    elif overview_question == "Tyck till entries map":

        col1, col2 = st.columns(2)

        with col1:
            category = st.pills("Tyck till category:",
                                ["Praise + Ideas",
                                 "Error + Complaints"],
                                selection_mode="single",
                                key="overview_selection_2",
                                default="Praise + Ideas"
                                )
        with col2:
            time_filter = st.pills("Time of day:",
                                   ["Day 06.00-18.00",
                                    "Night 18.00-06.00"],
                                   selection_mode="single",
                                   key="overview_selection_3",
                                   default="Day 06.00-18.00"
                                   )

        if category == "Praise + Ideas":
            pts = prepped["heat_praise_idea"]
        else:
            pts = prepped["heat_error_complaint"]

            # Time filter
        if time_filter == "Day":
            pts = pts[pts["is_day"]]
        else:
            pts = pts[pts["is_night"]]

        m = create_base_map()
        add_heatmap(m, pts)
        folium_static(m, width=1100, height=650)

# =================
# TAB 2: sentiments

with tab_sentiments:

    sentiment_question = st.radio(
        "Choose a question",
        ["Do sentiments vary over time?",
         "Sentiment question 2"],
        key="sentiment_selection_1"
    )
    st.divider()

    if sentiment_question == "Do sentiments vary over time?":
        chart = None

        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            category_group = st.pills(
                "Tyck till category:",
                ["Praise + Ideas", "Error + Complaints"],
                selection_mode="single",
                key="sentiment_selection_2",
                default="Praise + Ideas"
            )

        with col2:
            view_choice = st.pills(
                "View:",
                ["Compare 2 years", "Compare 3 park filters"],
                selection_mode="single",
                key="sentiment_selection_3",
                default="Compare 2 years"
            )

        with col3:
            temporal_scale = st.pills(
                "Temporal scale:",
                ["Months", "Weekdays", "24 Hours"],
                selection_mode="single",
                key="sentiment_selection_4",
                default="Months"
            )

        filter_vals = ["Beröm", "Idé"] if category_group == "Praise + Ideas" else ["Felanmälan", "Klagomål"]
        df_base = raw["all_park_related_pts_with_themes"]
        df_base = df_base[df_base["Kategori"].isin(filter_vals)]

        if category_group == "Praise + Ideas":
            df_loc = prepped["praise_idea_loc"]
            df_key = prepped["praise_idea_key"]
            df_sim = prepped["praise_idea_sim"]
        else:
            df_loc = prepped["error_complaint_loc"]
            df_key = prepped["error_complaint_key"]
            df_sim = prepped["error_complaint_sim"]

        st.subheader("Sentiments over time")

        if temporal_scale == "Months":
            prepared = prepare_for_chart_by_month(df_base, "sentiment")

            if view_choice == "Compare 2 years":
                years = sorted(prepared["year_label"].unique())
                dfs = [prepared[prepared["year_label"] == y] for y in years]
                titles = [str(y) for y in years]
                month_order = MONTH_LABELS_JUN_TO_MAY
                chart = chart_multi_panel(dfs, titles, month_order)

            else:  # 3 filters view
                dfs = [
                    prepare_for_chart_by_month(df_loc, "sentiment"),
                    prepare_for_chart_by_month(df_key, "sentiment"),
                    prepare_for_chart_by_month(df_sim, "sentiment"),
                ]
                titles = ["By location", "By keywords (strict)", "By keywords (similarity)"]
                chart = chart_multi_panel(dfs, titles, MONTH_LABELS)

        elif temporal_scale == "Weekdays":

            if view_choice == "Compare 2 years":
                prepared = prepare_for_chart_by_weekday(df_base, "sentiment")
                if "year_label" in prepared.columns:
                    years = sorted(prepared["year_label"].unique())
                    dfs = [prepared[prepared["year_label"] == y] for y in years]
                    titles = [str(y) for y in years]

                charts = []
                for df_year, title in zip(dfs, titles):
                    if df_year.empty:
                        continue
                    chart = chart_weekday_panel(df_year, title)
                    charts.append(chart)

                chart = alt.hconcat(*charts).resolve_scale(color="shared", y="shared") if charts else None

            # ------------------------------
            # COMPARE 3 PARK-RELATED FILTERS
            # ------------------------------
            else:

                # Prepare each source
                dfs = [
                    prepare_for_chart_by_weekday(df_loc, "sentiment"),
                    prepare_for_chart_by_weekday(df_key, "sentiment"),
                    prepare_for_chart_by_weekday(df_sim, "sentiment"),
                ]
                titles = ["By location", "By keywords (strict)", "By keywords (similarity)"]

                charts = []
                for df_sub, title in zip(dfs, titles):
                    if df_sub.empty:
                        continue
                    chart = chart_weekday_panel(df_sub, title)
                    charts.append(chart)

                chart = alt.hconcat(*charts).resolve_scale(color="shared", y="shared") if charts else None

        # chart by hours
        else:
            chart = None

            prepared = prepare_for_chart_by_hour(df_base, "sentiment")

            if view_choice == "Compare 2 years":
                if "year_label" in prepared.columns:
                    years = sorted(prepared["year_label"].unique())
                    dfs = [prepared[prepared["year_label"] == y] for y in years]
                    titles = [str(y) for y in years]
                else:
                    dfs = [prepared]
                    titles = ["All data"]

                charts = []
                for df_sub, title in zip(dfs, titles):
                    c = chart_hour_panel(df_sub, title)
                    if c:
                        charts.append(c)

                chart = alt.hconcat(*charts).resolve_scale(color="shared", y="shared") if charts else None

            else:  # compare 3 filters
                dfs = [
                    prepare_for_chart_by_hour(df_loc, "sentiment"),
                    prepare_for_chart_by_hour(df_key, "sentiment"),
                    prepare_for_chart_by_hour(df_sim, "sentiment"),
                ]
                titles = ["By location", "By keywords (strict)", "By keywords (similarity)"]

                charts = []
                for df_sub, title in zip(dfs, titles):
                    c = chart_hour_panel(df_sub, title)
                    if c:
                        charts.append(c)

                chart = alt.hconcat(*charts).resolve_scale(color="shared", y="shared") if charts else None

        if chart:
            st.altair_chart(chart, use_container_width=True)

    elif sentiment_question == "Sentiment question 2":
        st.info("Add sentiments per park and ha map")

# ==============
# TAB 3: topics

with tab_topics:

    topic_question = st.radio(
        "Choose a question:",
        ["Do topics vary over time?",
         "What are the top topics?",
         "Map: Top 5 topics per park"],
        key="topics_view_mode"
    )
    st.divider()

    if topic_question == "Do topics vary over time?":

        chart = None

        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            category_group = st.pills(
                "Tyck till category:",
                ["Praise + Ideas", "Error + Complaints"],
                default="Praise + Ideas",
                selection_mode="single",
                key="topics_category"
            )

        with col2:
            view_choice = st.pills(
                "View:",
                ["Compare 2 years", "Compare 3 park filters"],
                default="Compare 2 years",
                selection_mode="single",
                key="topics_view"
            )

        with col3:
            temporal_scale = st.pills(
                "Temporal scale:",
                ["Months", "Weekdays", "24 Hours"],
                default="Months",
                selection_mode="single",
                key="topics_temporal"
            )

        if category_group == "Praise + Ideas":
            df_loc = prepped["praise_idea_loc"]
            df_key = prepped["praise_idea_key"]
            df_sim = prepped["praise_idea_sim"]
        else:
            df_loc = prepped["error_complaint_loc"]
            df_key = prepped["error_complaint_key"]
            df_sim = prepped["error_complaint_sim"]

        st.subheader("Topics over time")

        if temporal_scale == "Months":

            prepared_loc = prepare_for_chart_by_month(df_loc, "topics")
            prepared_key = prepare_for_chart_by_month(df_key, "topics")
            prepared_sim = prepare_for_chart_by_month(df_sim, "topics")

            if view_choice == "Compare 2 years":
                years = sorted(prepared_loc["year_label"].unique())
                dfs = [prepared_loc[prepared_loc["year_label"] == y] for y in years]
                titles = [str(y) for y in years]
                chart = chart_multi_panel(dfs, titles, MONTH_LABELS_JUN_TO_MAY, mode="topics")

            else:  # 3 dataset comparison
                dfs = [prepared_loc, prepared_key, prepared_sim]
                titles = ["By location", "By keywords (strict)", "By keywords (similarity)"]
                chart = chart_multi_panel(dfs, titles, MONTH_LABELS, mode="topics")

        elif temporal_scale == "Weekdays":

            def prepare_weekday(df, top_n=5):

                df = df.copy()

                # --- Ensure weekday exists ---
                if "weekday" not in df.columns:
                    if "created_at" in df.columns:
                        df["weekday"] = df["created_at"].dt.weekday
                    else:
                        return pd.DataFrame()

                # --- Ensure year_label exists ---
                if "year_label" not in df.columns:
                    if "created_at" in df.columns:
                        df["year_label"] = df["created_at"].dt.year.astype(str)
                    else:
                        df["year_label"] = "All years"

                # --- Topic column ---
                topic_col = "topic_keywords_short" if "topic_keywords_short" in df.columns else "topic"

                # --- Group counts ---
                wc = df.groupby(["weekday", topic_col, "year_label"]).size().reset_index(name="count")

                # --- Top N topics ---
                top_topics = (
                    wc.groupby(["year_label", topic_col])["count"]
                        .sum()
                        .reset_index()
                )
                top_topics["rank"] = top_topics.groupby("year_label")["count"].rank(method="first", ascending=False)
                top_topics = top_topics[top_topics["rank"] <= top_n]

                wc = wc.merge(top_topics[["year_label", topic_col]], on=["year_label", topic_col], how="inner")

                # --- Fill missing weekdays for each topic ---
                WEEKDAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

                all_combinations = pd.DataFrame(
                    list(itertools.product(WEEKDAY_LABELS, wc[topic_col].unique(), wc["year_label"].unique())),
                    columns=["weekday_label", topic_col, "year_label"]
                )

                wc["weekday_label"] = wc["weekday"].apply(
                    lambda x: WEEKDAY_LABELS[int(x)] if isinstance(x, (int, float)) else x)
                wc_filled = all_combinations.merge(wc, on=["weekday_label", topic_col, "year_label"], how="left")
                wc_filled["count"] = wc_filled["count"].fillna(0)

                # --- Sort weekdays ---
                wc_filled["weekday_label"] = pd.Categorical(
                    wc_filled["weekday_label"], categories=WEEKDAY_LABELS, ordered=True
                )

                return wc_filled


            # Plotting function
            def chart_weekday_topics(df, title):
                if df.empty:
                    return None
                topic_col = "topic_keywords_short" if "topic_keywords_short" in df.columns else "topic"

                WEEKDAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

                return (
                    alt.Chart(df)
                        .mark_line(point=True)
                        .encode(
                        x=alt.X("weekday_label:N", title="Weekday", sort=WEEKDAY_LABELS),
                        y=alt.Y("count:Q", title="Number of comments"),
                        color=alt.Color(f"{topic_col}:N",
                                        title="Topic",
                                        legend=alt.Legend(
                                            orient="bottom",
                                            title="Topic keywords",
                                            columns=3,
                                            labelLimit=500,
                                            symbolLimit=200
                                        ),
                        ),
                        tooltip=["weekday_label", topic_col, "count"]
                    )
                        .properties(title=title, width=300, height=250)
                )


            # ------------- Compare 2 years ----------------
            if view_choice == "Compare 2 years":

                # Combine so that top-N topics are consistent across years
                df_all = pd.concat([df_loc, df_key, df_sim])
                prepared = prepare_weekday(df_all, top_n=5)

                if "year_label" in df_all.columns:
                    years = sorted(df_all["year_label"].unique())
                    dfs = [prepared[prepared["year_label"] == y] for y in years]
                    titles = [str(y) for y in years]
                else:
                    dfs = [prepared]
                    titles = ["All data"]

                charts = []
                for df_sub, title in zip(dfs, titles):
                    ch = chart_weekday_topics(df_sub, title)
                    if ch is not None:
                        charts.append(ch)

                if charts:
                    st.altair_chart(alt.hconcat(*charts).resolve_scale(color="shared", y="shared"),
                                    use_container_width=True)

            # ------------- Compare 3 datasets ----------------
            else:
                dfs = [prepare_weekday(df_loc, top_n=5),
                       prepare_weekday(df_key, top_n=5),
                       prepare_weekday(df_sim, top_n=5)]
                titles = ["By location", "By keywords (strict)", "By keywords (similarity)"]

                charts = []
                for df_sub, title in zip(dfs, titles):
                    ch = chart_weekday_topics(df_sub, title)
                    if ch is not None:
                        charts.append(ch)

                if charts:
                    st.altair_chart(alt.hconcat(*charts).resolve_scale(color="shared", y="shared"),
                                    use_container_width=True)

        else:
            st.info("24-hour view to be added") # *** maybe don't add? might look ugly just like topics over weekdays per park filter ***
            chart = None

        if chart:
            st.altair_chart(chart, use_container_width=True)

    elif topic_question == "What are the top topics?":
        chart = None

        # shared X-axis (max bar length)
        def get_global_max(*dfs):
            max_count = 0
            for df in dfs:
                if df.empty:
                    continue
                c = (
                    df.groupby("topic")
                        .size()
                        .reset_index(name="count")["count"]
                        .max()
                )
                max_count = max(max_count, c)
            return max_count

        global_max = get_global_max(df_loc, df_key, df_sim)

        def top_topics_chart(df, label):
            if df.empty: return None

            counts = (
                df.groupby([
                    "topic",
                    "topic_keywords",
                    "topic_keywords_full",
                    "topic_keywords_short",
                ])
                    .size()
                    .reset_index(name="count")
                    .sort_values("count", ascending=False)
                    .head(10)
            )
            return (
                alt.Chart(counts)
                    .mark_bar()
                    .encode(
                    x=alt.X(
                        "count:Q",
                        title="Number of comments",
                        scale=alt.Scale(domain=[0, global_max]),
                    ),
                    y=alt.Y("topic:O", sort="-x", title="Topic number"),
                    color=alt.Color(
                        "topic_keywords_short:N",
                        title="Topic keywords",
                        scale=alt.Scale(scheme="tableau20"),
                        legend=alt.Legend(
                            orient="bottom",
                            title="Topic keywords",
                            columns=3,
                            labelLimit=500,
                            symbolLimit=200,
                        ),
                    ), tooltip=[
                        "topic",
                        "topic_keywords_full",
                        "count",
                    ],
                )
                    .properties(title=label, width=300, height=250)
            )

        # create the three charts
        chart1 = top_topics_chart(df_loc, "By location")
        chart2 = top_topics_chart(df_key, "By keywords (strict)")
        chart3 = top_topics_chart(df_sim, "By keywords (similarity)")
        # display them side by side
        charts = [c for c in [chart1, chart2, chart3] if c is not None]
        if charts:
            st.altair_chart(charts[0] | charts[1] | charts[2], use_container_width=True)

    elif topic_question == "Map: Top 5 topics per park":

        st.subheader("Top 5 Topics per Park")
        st.write("Click on a park to see the most common topics.")

        gdf = raw["parks_with_top5_topics"]
        column = "top5_topics"

        m = create_base_map()
        add_top5_topics_layer(m, gdf, column)

        st_folium(m, width=900, height=600)

# ==============
# TAB 4: themes

with tab_themes:

    themes_question = st.radio(
        "Choose a question:",
        ["Themes question 1",
         "Themes question 2"],
        key="themes_view_mode"
    )

    if themes_question == "Themes question 1":
        st.info("Add most common themes bar chart")

    elif themes_question == "Themes question 2":
        st.info("Add co-occurence matrix")





###############
# TEMP TEST TAB

with tab_temp_test:
    st.title("Test: Topics over Weekdays")

    df = raw["all_park_related_pts_with_themes"].copy()




