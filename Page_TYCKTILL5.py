
import streamlit as st
import geopandas as gpd
import pandas as pd
import altair as alt
import os
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
#from streamlit_plotly_events import plotly_events     # *** use plotly for a heatmap + clickable point for wordcloud ***
import h3
from shapely.geometry import Polygon
import json
import plotly.express as px
import branca.colormap as cm
from wordcloud import WordCloud
import base64
from io import BytesIO


st.set_page_config(layout="wide")

tycktill_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\tycktill.gpkg"
tycktill_filtered_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg"
tycktill_filtered_with_lemmas_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\STANZA_for_word_cloud\STANZA_output.gpkg"

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
    data["stats_per_park"] = vector_layer(tycktill_GPKG, "stats_per_park")
    data["all_park_related_pts_with_themes"] = vector_layer(tycktill_filtered_GPKG, "all_park_related_pts_with_themes")
    # topic sources
    data["pts_with_topics_by_location"] = vector_layer(tycktill_filtered_GPKG, "pts_in_parks_with_topics")
    data["pts_with_topics_by_keywords_strictly"] = vector_layer(tycktill_filtered_GPKG, "park_comments_by_keyword")
    data["pts_with_topics_by_keywords_similarity"] = vector_layer(tycktill_filtered_GPKG, "park_comments_by_BERTopic")
    data["parks_with_top5_topics"] = vector_layer(tycktill_filtered_GPKG, "parks_with_top5_topics")
    data["all_park_related_pts_with_themes_AND_STANZA"] = vector_layer(tycktill_filtered_with_lemmas_GPKG, "all_park_related_pts_with_themes_AND_STANZA")
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
    "Praise + Ideas": "praise_idea",
    "Error + Complaints": "error_complaint"
}

TOPIC_COLOR_SCHEME = "tableau20"

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

def add_day_night_columns(df):
    df = df.copy()
    df["is_day"] = df["hour"].between(6, 18)
    df["is_night"] = ~df["is_day"]

    return df

def split_by_category(df):
    """split into two subsets used by both sentiments & topics"""
    return {
        "praise_idea": df[df["Kategori"].isin(["Beröm", "Idé"])],
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

#def clean_lemmas(df):
#    df = df.copy()
#    df["lemmas"] = df["lemmas"].apply(
#        lambda lst: [w.strip("'\"") for w in lst] if isinstance(lst, list) else lst
#    )
#    return df

def add_lat_lon(df):
    # this step is for plotly
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
    """
    Returns:
      hex_df: one row per hexagon (for map)
      points_df: original points with hex_id (for word cloud filtering)
    """
    # explode keywords so wordcloud has frequency
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

    # geometry for plotting hexagons
    agg["geometry"] = agg["hex_id"].apply(
        lambda h: Polygon(
            [(lng, lat) for lat, lng in h3.cell_to_boundary(h)]
        )
    )

    hex_gdf = gpd.GeoDataFrame(agg, geometry="geometry", crs="EPSG:4326")
    return hex_gdf

def generate_wordcloud(text_list, width=300, height=200):
    """Create a word cloud image and return as base64 string."""
    if not text_list:
        text_list = ["No data"]
    wc = WordCloud(width=width, height=height, background_color="white").generate(" ".join(text_list))
    img_buffer = BytesIO()
    wc.to_image().save(img_buffer, format="PNG")
    img_buffer.seek(0)
    img_b64 = base64.b64encode(img_buffer.read()).decode()
    return img_b64

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
        prepped_vectors[f"praise_idea_{suffix}"] = split["praise_idea"]
        prepped_vectors[f"error_complaint_{suffix}"] = split["error_complaint"]

    # all_pts used for year comparisons
    all_pts = add_day_night_columns(raw_vectors["all_park_related_pts_with_themes"])
    all_pts = prepare_topic_df(all_pts)
    all_pts = fix_sentiment_column_type(all_pts)
    all_pts = fix_topic_column_type(all_pts)
    prepped_vectors["all_pts"] = all_pts

    # sentiment splits for heatmaps
    heat = split_by_category(all_pts)
    prepped_vectors["heat_praise_idea"] = heat["praise_idea"]
    prepped_vectors["heat_error_complaint"] = heat["error_complaint"]

    # hexbins
    hex_src = add_lat_lon(raw_vectors["all_park_related_pts_with_themes_AND_STANZA"])
    #hex_src = clean_lemmas(hex_src)
    #hex_src = add_lat_lon(hex_src)
    hex_src = prepare_topic_df(hex_src)
    hex_src = add_h3_hex_id(hex_src, resolution=9)

    split = split_by_category(hex_src)

    prepped_vectors["hex_bins_praise_idea"] = prepare_hexbins(split["praise_idea"])          # original points with hex_id (for filtering / word cloud)
    prepped_vectors["hex_bins_error_complaint"] = prepare_hexbins(split["error_complaint"])  # hex polygons (for map)
    prepped_vectors["hex_points_praise_idea"] = split["praise_idea"]
    prepped_vectors["hex_points_error_complaint"] = split["error_complaint"]

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
        "praise_idea_loc", "praise_idea_key", "praise_idea_sim",
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
    df = df[df["Kategori"].isin(["Beröm","Idé"])] if cat_key=="praise_idea" else df[df["Kategori"].isin(["Felanmälan","Klagomål"])]

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
        if cat_key == "praise_idea":
            df_all = df_all[df_all["Kategori"].isin(["Beröm", "Idé"])]
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

# ============
# === MAPS ===     *** remove all plotly hexbins if im using folium ***

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

def create_folium_hexbin_map(hex_gdf, color_col="count"):
    # Start map centered on Stockholm
    m = folium.Map(location=[59.33, 17.99], zoom_start=10.5, tiles=None)

    # Add a satellite basemap
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satellite',
        overlay=False,
        control=True
    ).add_to(m)

    # Add hexagons as GeoJson
    folium.GeoJson(
        hex_gdf,
        style_function=lambda feature: {
            'fillColor': colormap(feature['properties'][color_col]),
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.6
        }
    ).add_to(m)

    return m

def create_folium_hexbin_map_with_wc(hex_gdf, points_df, text_col="lemmas", color_col="count"):
    m = folium.Map(location=[59.33, 17.99], zoom_start=10.5, tiles=None)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',  # *** USE EXISTING BASEMAP INSTEAD ***
        attr='Esri', name='Esri Satellite', overlay=False, control=True
    ).add_to(m)

    for _, row in hex_gdf.iterrows():
        # points in this hex
        pts_in_hex = points_df[points_df["hex_id"] == row["hex_id"]]
        texts = pts_in_hex[text_col].dropna().tolist()
        img_b64 = generate_wordcloud(texts)

        popup_html = f'<img src="data:image/png;base64,{img_b64}" width="300" height="200">'

        folium.GeoJson(
            row["geometry"],
            style_function=lambda f, color=row[color_col]: {
                'fillColor': colormap(color),
                'color': 'black',
                'weight': 1,
                'fillOpacity': 0.6
            },
            tooltip=folium.Tooltip(f"Count: {row[color_col]}"),
            popup=folium.Popup(popup_html, max_width=320)
        ).add_to(m)

    return m

def create_plotly_hexbin_map(hex_gdf):
    # Convert GeoDataFrame to GeoJSON
    geojson = json.loads(hex_gdf.to_json())

    hex_gdf = hex_gdf.reset_index(drop=False).rename(columns={"index": "bin_index"})    # simplify hex_id for display purposes

    # Simple choropleth map
    fig = px.choropleth_mapbox(
        hex_gdf,
        geojson=geojson,
        locations="hex_id",
        featureidkey="properties.hex_id",  # matches hex_id in GeoJSON
        color="count",                     # color ramp based on count
        color_continuous_scale="Viridis",
        mapbox_style="open-street-map",    # simplest basemap
        center={"lat": 59.33, "lon": 17.99},
        zoom=10,
        opacity=0.4,
        hover_data={'bin_index': True, 'count': True, 'hex_id':False}

    )

    # Remove extra margins
    #fig.update_layout(margin={"r":0, "t":0, "l":0, "b":0})
    fig.update_layout(
        dragmode='pan',  # makes it possible to zoom by scrolling (not just using +/- buttons)  *** not working ***
        mapbox=dict(
            # style='satellite',
            center={'lat': 59.33, 'lon': 17.99},
            zoom=10
        ),
        height=700,
        margin=dict(l=0, r=0, t=0, b=0)
    )

    return fig

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
# === OVERVIEW ===

if section == "Overview":
    overview_question = st.sidebar.radio(
        "Choose a question:",
        ["Where is Tyck till being used? (heatmap, day/night)", "*What* is talked about *where*? (PLOTLY)", "*What* is talked about *where*? (FOLIUM)"]
    )

    if overview_question == "Where is Tyck till being used? (heatmap, day/night)":

        st.subheader("Tycktill entries")

        category_choice = st.sidebar.pills("Tyck till category:",
            ["Praise + Ideas", "Error + Complaints"],
            selection_mode="single",
            default="Praise + Ideas",
            key="sent_cat")

        if category_choice == "Praise + Ideas":
            pts_category = prepped_vectors["heat_praise_idea"]
        else:
            pts_category = prepped_vectors["heat_error_complaint"]

        pts_day = pts_category[pts_category["is_day"]]
        pts_night = pts_category[pts_category["is_night"]]

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Daytime (06:00-18:00)**")
            m_day = create_folium_basemap()
            add_folium_heatmap(m_day, pts_day)
            folium_static(m_day, width=550, height=550)

        with col2:
            st.markdown("**Nighttime (18:00-06:00)**")
            m_night = create_folium_basemap()
            add_folium_heatmap(m_night, pts_night)
            folium_static(m_night, width=550, height=550)

    elif overview_question == "*What* is talked about *where*? (PLOTLY)":

        st.subheader("Where are park-related comments concentrated?")

        st.caption(
            "Hexagon density map. Click a hexagon to explore dominant topics."
        )

        category_choice = st.sidebar.pills(
            "Choose Category:",
            ["Praise + Ideas", "Error + Complaints"],
            selection_mode="single",
            default="Praise + Ideas",
            key="category_choice"
        )

        # Get the data for the selected category
        if category_choice == "Praise + Ideas":
            selected_data = prepped_vectors["heat_praise_idea"]
        else:
            selected_data = prepped_vectors["heat_error_complaint"]

        hex_src = selected_data
        hex_src = add_lat_lon(hex_src)
        hex_src = add_h3_hex_id(hex_src, resolution=9)  # make sure the resolution is correct

        hex_gdf = prepare_hexbins(hex_src, text_col="topic_keywords_list")
        fig = create_plotly_hexbin_map(hex_gdf)

        #fig = create_plotly_hexbin_map(prepped_vectors["hex_bins"])
        st.plotly_chart(fig, use_container_width=True)

    elif overview_question == "*What* is talked about *where*? (FOLIUM)":
        category_choice = st.sidebar.pills(
            "Select category:",
            ["Praise + Ideas", "Error + Complaints"],
            selection_mode="single",
            default="Praise + Ideas"
        )

        if category_choice == "Praise + Ideas":
            hex_gdf = prepped_vectors["hex_bins_praise_idea"]
            points_df = prepped_vectors["hex_points_praise_idea"]

            #st.write(points_df.iloc[0]["lemmas"])  # just a check, can be removed when all is working

        else:
            hex_gdf = prepped_vectors["hex_bins_error_complaint"]
            points_df = prepped_vectors["hex_points_error_complaint"]

        max_count = hex_gdf["count"].max()
        colormap = cm.LinearColormap(['#440154', '#fde725'], vmin=0, vmax=max_count)

        m = create_folium_hexbin_map_with_wc(hex_gdf, points_df, text_col="lemmas")
        folium_static(m, width=700, height=500)

# ==================
# === SENTIMENTS ===

if section == "Sentiments":
    sentiment_question = st.sidebar.radio(
        "Choose a question:",
        ["Do sentiments vary over time?", "Sentiment question 2"]
    )

    if sentiment_question == "Do sentiments vary over time?":
        category_group = st.sidebar.pills(
            "Tyck till category:",
            ["Praise + Ideas", "Error + Complaints"],
            selection_mode="single",
            default="Praise + Ideas",
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

# ==============
# === TOPICS ===   *** lägg till en subpage med en dropdown lista över typ top 20 eller 50 topics och så kan man välja en och få lite olika grafer? ***

if section == "Topics":
    topic_question = st.sidebar.radio(
        "Choose a question:",
        ["Do topics vary over time?", "What are the top 5 topics per park (by location)?", "What are the top topics?"]
    )

    if topic_question == "Do topics vary over time?":
        category_group = st.sidebar.pills(
            "Tyck till category:",
            ["Praise + Ideas", "Error + Complaints"],
            selection_mode="single",
            default="Praise + Ideas",
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


