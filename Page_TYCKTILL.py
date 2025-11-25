
import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import branca.colormap as cm
import numpy as np
import pandas as pd
import mapclassify   # OM PROBLM MED MAPCLASSIFY - kör streamlit run genom att här i pycharm gå till terminal > klicka på dropdown > välj command prompt. Testa sen om den hittar mapclassify genom att skriva python -c "import mapclassify; print(mapclassify.__version__)". Om det funkar kör vanliga streamlit run.
import altair as alt
from itertools import combinations
import rasterio
from rasterio.features import rasterize

# TO DO

# Add legend to maps
# Add colors and legend to top topics bars

st.set_page_config(layout="wide")

# ===================
# === load layers ===

@st.cache_data(show_spinner="Loading spatial data...")
def load_layer(path: str, layer_name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path, layer=layer_name)
    return gdf.to_crs(epsg=4326)

tycktill_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\tycktill.gpkg"
sentiments_per_park = load_layer(tycktill_GPKG, "sentiments_per_park")
stats_per_park = load_layer(tycktill_GPKG, "stats_per_park")

tycktill_filtered_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg"
themes_per_park = load_layer(tycktill_filtered_GPKG, "all_park_related_pts_with_themes")
pts_in_parks_with_topics = load_layer(tycktill_filtered_GPKG, "pts_in_parks_with_topics")   # by location
pts_in_parks_by_keywords = load_layer(tycktill_filtered_GPKG, "park_comments_by_keyword")   # by keywords (strictly)
pts_in_parks_by_BERTopic = load_layer(tycktill_filtered_GPKG, "park_comments_by_BERTopic")  # by keywords (similarity)
parks_with_top5_topics = load_layer(tycktill_filtered_GPKG, "parks_with_top5_topics")

DeSO = load_layer(r"C:\Users\lisajos\QGIS_Projects\Input\SCB\DeSO_2025.gpkg")
population_table = pd.read_excel(r"C:\Users\lisajos\QGIS_Projects\Input\SCB\SCB_population_by_gender_and_DESO_for_2024.xlsx")

with rasterio.open(r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\plots\kde_praise_ideas.tif") as src:
    heatmap = src.read(1)
    transform = src.transform
    width = src.width
    height = src.height
    crs = src.crs

# ====================
# === prepp layers ===

# ==================
# prepp for overview

all_park_praise_ideas = themes_per_park[themes_per_park['Kategori'].isin(["Beröm", "Idé"])]
all_park_error_complaint = themes_per_park[themes_per_park['Kategori'].isin(["Felanmälan", "Klagomål"])]

# prepp for population by DeSO x park-related comments (raster)              # **** flytta till separat script ****
DeSO_pop = DeSO.merge(population_table, on="desokod", how="left")

# rasterize DeSO_pop
population_raster = rasterize(
    [(geom, pop) for geom, pop in zip(DeSO_pop.geometry, DeSO_pop.Population)],
    out_shape=(height, width),
    transform=transform,
    fill=0,
    dtype="float32"
)



# ====================
# prepp for sentiments

# sentiment score
sentiments_per_park = sentiments_per_park.dropna(subset=["sentiment_score_per_ha"])

# sentiments over time
sentiments_for_praise_ideas = pts_in_parks_with_topics[pts_in_parks_with_topics['Kategori'].isin(["Beröm", "Idé"])]   # OBS! only using by location pts!!

# ================
# prepp for topics

def prepare_topic_keywords(df, top_n_full=10, top_n_short=3):
    # convert string → list
    df = df.copy()
    df["topic_keywords_list"] = df["topic_keywords"].apply(lambda s: s.split(", "))

    df["topic_keywords_full"] = df["topic_keywords_list"].apply(lambda lst: ", ".join(lst[:top_n_full]))

    df["topic_keywords_short"] = df["topic_keywords_list"].apply(lambda lst: ", ".join(lst[:top_n_short]))

    return df
# apply shortened topic_keywords list
pts_in_parks_with_topics = prepare_topic_keywords(pts_in_parks_with_topics)
pts_in_parks_by_keywords = prepare_topic_keywords(pts_in_parks_by_keywords)
pts_in_parks_by_BERTopic = prepare_topic_keywords(pts_in_parks_by_BERTopic)

# filter for Beröm and Idé in topic files
praise_idea_pts_in_parks = pts_in_parks_with_topics[pts_in_parks_with_topics['Kategori'].isin(["Beröm", "Idé"])]   # use [pts_in_parks_with_topics['Kategori'] == "Beröm"] for just one category
praise_idea_by_keywords = pts_in_parks_by_keywords[pts_in_parks_by_keywords['Kategori'].isin(["Beröm", "Idé"])]
praise_idea_by_BERTopic = pts_in_parks_by_BERTopic[pts_in_parks_by_BERTopic['Kategori'].isin(["Beröm", "Idé"])]

# =========================
# prepp for themes barchart

# explode columns
def prepare_themes_data(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    df = gdf[["source_filter", "themes"]].copy()

    # split on ';' and remove whitespace
    def split_list(x):
        return [s.strip() for s in str(x).split(";") if s.strip()]
    df["source_filter_list"] = df["source_filter"].apply(split_list)
    df["themes_list"] = df["themes"].apply(
        lambda x: [s.strip() for s in str(x).split(";") if s.strip()]
        if pd.notna(x) and str(x).strip() != ""
        else ["no theme"]
    )

    # explode both columns to get one combination per row
    df = df.explode("source_filter_list").explode("themes_list")

    # count occurrences
    counts = (
        df.groupby(["source_filter_list", "themes_list"])
            .size()
            .reset_index(name="count")
            .rename(columns={"source_filter_list": "source_filter", "themes_list": "themes"})
    )
    return counts

themes_counts = prepare_themes_data(themes_per_park)

# ====================================
# prepp for themes combinations matrix

def compute_theme_cooccurrence(gdf):
    df = gdf.dropna(subset=["themes"]).copy()
    df["themes_list"] = df["themes"].apply(
        lambda x: [s.strip() for s in str(x).split(";") if s.strip()]
    )

    pairs = []
    for themes in df["themes_list"]:
        if len(themes) > 1:
            for a, b in combinations(sorted(themes), 2):
                pairs.append((a, b))

    coocc = pd.DataFrame(pairs, columns=["theme_a", "theme_b"])
    coocc = coocc.value_counts().reset_index(name="count")
    return coocc


# ==========
# page setup

st.title("Vad tycker besökarna om Stockholms parker?")
st.text("Här finner du sammanställd data från appen TyckTill! Välj bland alternativen nedan för att se resultat av vår analys.")

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Sentiments", "Topics", "Themes"])          # *** new tab? UPDATE HERE ***

# ==================================
# ============== TABS ==============                                               # *** new tab/button? UPDATE HERE ***

# ===============
# TAB 1: overview
with tab1:
    overview_choice = st.radio(
        "Make a selection:",
        ["What parks get the most praise and idea suggestions?", "What parks get the most error reports and complaints?", "DAY/NIGHT x KATEGORI"],
        index=None,                   # None = no radio button pre-selected
        horizontal=True
    )

# =================
# TAB 2: sentiments
with tab2:
    sentiments_choice = st.radio(
        "Make a selection:",
        ["How do TyckTill users feel about parks?", "Sentiments over time (months) in park-related comments", "Sentiments over time (weekdays) in park-related comments"],
        horizontal=True,
        index=None
    )

# =============
# TAB 3: topics
with tab3:
    topics_choice = st.radio(
        "Make a selection:",
        ["What are the top topics?", "Do topics vary over time?", "Top 5 topics per park"],
        horizontal=True,
        index=None
    )

# =============
# TAB 4: themes
with tab4:
    plot_choice = st.radio(
        "Make a selection:",
        ["What themes are most common in parks?", "What themes occur in combination?"],
        horizontal=True,
        index=None
    )

#########################
if overview_choice:
    # If user made a selection in Overview tab
    sentiments_choice = None
    topics_choice = None
    plot_choice = None
    st.session_state.selected_plot = None   # clear plots if switching to map
elif sentiments_choice:
    # If user made a selection in Sentiments tab
    overview_choice = None
    topics_choice = None
    plot_choice = None
    st.session_state.selected_plot = None   # clear plots
elif topics_choice:
    # If user made a selection in Topics tab
    overview_choice = None
    sentiments_choice = None
    plot_choice = None
    st.session_state.selected_layer = None  # clear maps (so only plots or top5_topics)
elif plot_choice:
    # If user made a selection in Themes tab
    overview_choice = None
    sentiments_choice = None
    topics_choice = None
    st.session_state.selected_layer = None  # clear maps
#########################


# =============================
# determine selected map / plot

def select_layer(layer, layer_type, layer_column):
    st.session_state.selected_layer = layer
    st.session_state.layer_type = layer_type
    st.session_state.layer_column = layer_column
    st.session_state.selected_plot = None  # clear any plot selection

def select_plot(plot_type):
    st.session_state.selected_plot = plot_type
    st.session_state.selected_layer = None  # clear any map selection


# initialize selected layer variable
if "selected_layer" not in st.session_state:
    st.session_state.selected_layer = None
    st.session_state.layer_column = None
    st.session_state.layer_type = None
    st.session_state.selected_plot = None


# overview
if overview_choice == "What parks get the most praise and idea suggestions?":                        # *** new tab/button? UPDATE HERE ***
    select_layer(stats_per_park, "pts_per_park_praise_idea", "rel_pts_per_park_praise_idea")

elif overview_choice == "What parks get the most error reports and complaints?":
    select_layer(stats_per_park, "pts_per_park_error_complaint", "rel_pts_per_park_errorrep_complaint")

elif overview_choice == "DAY/NIGHT x KATEGORI":
    select_plot("DAY/NIGHT")

#elif overview_choice == "What parks inspire the most ideas?":
#    select_layer(stats_per_park, "ideas", "Idé_rel")

#elif overview_choice == "TEST":
#    select_layer(stats_per_park, "praise", "Beröm_rel")

# sentiments
elif sentiments_choice == "How do TyckTill users feel about parks?":
    select_layer(sentiments_per_park, "sentiment_score", "sentiment_score_per_ha")

elif sentiments_choice == "Sentiments over time (months) in park-related comments":
    select_plot("sentiments_over_time_months_praise_idea")

elif sentiments_choice == "Sentiments over time (weekdays) in park-related comments":
    select_plot("sentiments_over_time_weekdays_praise_idea")

# topics
elif topics_choice == "What are the top topics?":
    select_plot("top_topics")

elif topics_choice == "Do topics vary over time?":
    select_plot("topics_over_time")

elif topics_choice == "Top 5 topics per park":
    select_layer(parks_with_top5_topics, "top5_topics_per_park", "Top5_Table")

# themes
elif plot_choice == "What themes are most common in parks?":
    select_plot("common_themes")

elif plot_choice == "What themes occur in combination?":
    select_plot("mixed_themes")

else:
    st.session_state.selected_plot = None
    st.session_state.selected_layer = None


# ============================================
# ============== VISUALIZATIONS ==============

# ====
# maps

# basemap
def create_base_map():
    """Return a new folium Map with Esri basemap."""
    m = folium.Map(location=(59.33, 17.99), zoom_start=10.5, tiles=None)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satellite',
        overlay=False,
        control=True
    ).add_to(m)
    return m

# pts in parks map (praise + ideas / error report + complaint)
def add_pts_per_park_praise_idea_layer(m, layer):
    st.header("Praise and ideas per park (normalised count)")

    col = st.session_state.layer_column

    # handle NaN rows so jenks thing works later
    layer["_is_missing"] = layer[col].isna()
    layer["_value"] = layer[col].fillna(0)  # replace NaN with 0

    n_classes = 5
    values = layer["_value"].values
    classifier = mapclassify.NaturalBreaks(values, k=n_classes)
    breaks = classifier.bins

    colors = ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]
    missing_color = "#d9d9d9"

    def fmt(val, is_missing):
        if is_missing or val < 0.001:
            return "No praise or ideas in this park (value < 0,001)"
        return f"{val:.3f}"

    layer["tooltip_text"] = layer.apply(
        lambda r: fmt(r["_value"], r["_is_missing"]),
        axis=1
    )

    def choose_color(feature):
        if feature["properties"]["_is_missing"]:
            return missing_color
        v = feature["properties"]["_value"]
        for i, b in enumerate(breaks):
            if v <= b:
                return colors[i]
        return colors[-1]

    folium.GeoJson(
        layer,
        style_function=lambda feat: {
            "fillColor": choose_color(feat),
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.7,
        },
        tooltip=folium.features.GeoJsonTooltip(
            fields=["tooltip_text"],
            aliases=["Praise and ideas per park:"],
            sticky=True
        )
    ).add_to(m)

# pts in parks map (praise + ideas / error report + complaint)
def add_pts_per_park_error_complaint_layer(m, layer):
    st.header("Error reports and complaints per park (normalised count)")

    col = st.session_state.layer_column

    # handle NaN rows so jenks thing works later
    layer["_is_missing"] = layer[col].isna()
    layer["_value"] = layer[col].fillna(0)  # replace NaN with 0

    n_classes = 5
    values = layer["_value"].values
    classifier = mapclassify.NaturalBreaks(values, k=n_classes)
    breaks = classifier.bins

    colors = ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]
    missing_color = "#d9d9d9"

    def fmt(val, is_missing):
        if is_missing or val < 0.001:
            return "No error reports or complaints in this park (value < 0,001)"
        return f"{val:.3f}"

    layer["tooltip_text"] = layer.apply(
        lambda r: fmt(r["_value"], r["_is_missing"]),
        axis=1
    )

    def choose_color(feature):
        if feature["properties"]["_is_missing"]:
            return missing_color
        v = feature["properties"]["_value"]
        for i, b in enumerate(breaks):
            if v <= b:
                return colors[i]
        return colors[-1]

    folium.GeoJson(
        layer,
        style_function=lambda feat: {
            "fillColor": choose_color(feat),
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.7,
        },
        tooltip=folium.features.GeoJsonTooltip(
            fields=["tooltip_text"],
            aliases=["Error reports and complaints per park:"],
            sticky=True
        )
    ).add_to(m)

# ideas map    TA BORT
def add_ideas_layer(m, layer):
    st.header("Ideas per park (normalised count)")
    n_classes = 5
    values = layer[st.session_state.layer_column].values
    classifier = mapclassify.NaturalBreaks(values, k=n_classes)
    breaks = classifier.bins
    colors = ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]

    def get_color(value):
        for i, b in enumerate(breaks):
            if value <= b:
                return colors[i]
        return colors[-1]

    def style_function(feature):
        value = feature["properties"][st.session_state.layer_column]
        return {
            "fillColor": get_color(value),
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.7
        }

    folium.GeoJson(
        layer,
        style_function=style_function,
        tooltip=folium.features.GeoJsonTooltip(
            fields=[st.session_state.layer_column],
            aliases=["Ideas per park:"],
            localize=True
        )
    ).add_to(m)

# TEST     TA BORT
def add_TEST_layer(m,layer):
    st.header("TEST")
    n_classes = 5
    values = layer[st.session_state.layer_column].values
    classifier = mapclassify.NaturalBreaks(values, k=n_classes)
    breaks = classifier.bins
    colors = ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]

    def get_color(value):
        for i, b in enumerate(breaks):
            if value <= b:
                return colors[i]
        return colors[-1]

    def style_function(feature):
        value = feature["properties"][st.session_state.layer_column]
        return {
            "fillColor": get_color(value),
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.7
        }

    folium.GeoJson(
        layer,
        style_function=style_function,
        tooltip=folium.features.GeoJsonTooltip(
            fields=[st.session_state.layer_column],
            aliases=["Beröm per park:"],
            localize=True
        )
    ).add_to(m)

# sentiments map
def add_sentiments_layer(m, layer):
    st.subheader("Sentiment score per ha")
    st.markdown("Sentiment score was calculated by assigning values to comments by sentiment (positive=1, neutral=0, negative=-1) and then calculating total score per ha.")
    st.text("")

    n_classes = 5
    values = layer[st.session_state.layer_column].values
    quantiles = np.quantile(values, np.linspace(0, 1, n_classes + 1))
    colors = ["#d73027", "#f4a582", "#f7f7f7", "#a6dba0", "#1b7837"]

    def get_color(value):
        for i in range(n_classes):
            if quantiles[i] <= value <= quantiles[i + 1]:
                return colors[i]
        return colors[-1]

    def style_function(feature):
        value = feature["properties"][st.session_state.layer_column]
        return {
            "fillColor": get_color(value),
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.6
        }

    folium.GeoJson(
        layer,
        style_function=style_function,
        tooltip=folium.features.GeoJsonTooltip(
            fields=[st.session_state.layer_column],
            aliases=["Sentiment score per ha:"],
            localize=True
        )
    ).add_to(m)

# top5 topics map with popup
def add_top5_topics_layer(m, layer):
    st.header("Top 5 topics per park")
    st.text("")
    st.markdown("Click a park to view the most common topics.")
    st.text("")

    layer_column = st.session_state.layer_column

    for _, row in layer.iterrows():
        popup_val = row.get(layer_column, "")

        if isinstance(popup_val, str) and popup_val.strip():
            rows = [r.strip() for r in popup_val.split("\n") if r.strip()]
            topic_lines = "".join([f"<div>{r}</div>" for r in rows])
            popup_text = f"""
            <div style="font-size:13px; line-height:1.4;">
                <b>Top 5 Topics in this Park:</b><br>
                {topic_lines}
            </div>
            """
        else:
            popup_text = """
            <div style="font-size:13px;">
                <i>No topics in this park</i>
            </div>
            """

        folium.GeoJson(
            row["geometry"],
            popup=folium.Popup(popup_text, max_width=600),
            style_function=lambda feature: {
                "fillColor": "#4287f5",
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.5
            }
        ).add_to(m)


# =====
# plots

def show_DAY_NIGHT():
    st.subheader("Park-related TyckTill entries over time (24 hours)")
    st.markdown("Beskrivning")
    st.text("")

    all_hours = pd.DataFrame({"hour": list(range(24))})

    # praise/ideas
    praise_idea = (
        all_park_praise_ideas.groupby("hour")
            .size()
            .reset_index(name="count")
    )
    praise_idea = all_hours.merge(praise_idea, on="hour", how="left").fillna({"count": 0})
    praise_idea["hour_str"] = praise_idea["hour"].astype(str)

    # errors/complaints
    error_complaint = (
        all_park_error_complaint.groupby("hour")
            .size()
            .reset_index(name="count")
    )
    error_complaint = all_hours.merge(error_complaint, on="hour", how="left").fillna({"count": 0})
    error_complaint["hour_str"] = error_complaint["hour"].astype(str)

    colors = {
        "Praise/Idea": "#009E73",
        "Error/Complaint": "#D55E00"
    }

    chart_praise = (
        alt.Chart(praise_idea)
            .mark_line(color=colors["Praise/Idea"])
            .encode(
            x=alt.X(
                "hour_str:N",
                sort=[str(i) for i in range(24)],
                axis=alt.Axis(values=[str(i) for i in range(24)], labelAngle=0),
                title="Hour of day"
            ),
            y=alt.Y("count:Q", title="Count", scale=alt.Scale(domain=[0, 200])),
            tooltip=["hour", "count"]
        )
            .properties(width=350, height=300, title="Praise & Ideas")
    )

    chart_error = (
        alt.Chart(error_complaint)
            .mark_line(color=colors["Error/Complaint"])
            .encode(
            x=alt.X(
                "hour_str:N",
                sort=[str(i) for i in range(24)],
                axis=alt.Axis(values=[str(i) for i in range(24)], labelAngle=0),
                title="Hour of day"
            ),
            y=alt.Y("count:Q", title="Count"),
            tooltip=["hour", "count"]
        )
            .properties(width=350, height=300, title="Errors & Complaints")
    )

    final_chart = alt.hconcat(chart_praise, chart_error)

    st.altair_chart(final_chart, use_container_width=True)

def show_common_themes():
    st.subheader("Themes in Park-related comments (3 definitions)")
    st.text(" ")
    st.markdown(
        "*Park related TyckTill comments* have been defined in 3 different ways: by geographical location, by keywords (strictly) and by keywords (similarity). **Strictly** means that a specified keyword was present in the comment while **similarity** means a keyword or similar word was present in the comment as defined by our model.")
    st.text(" ")
    st.markdown("*Themes* are defined by precence of theme keywords in comments.")
    st.text(" ")  # creates more of space between text and plot

    themes_counts = prepare_themes_data(themes_per_park)

    themes_order = (
        themes_counts.groupby("themes")["count"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
    )

    okabe_ito_12 = [
        "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2",
        "#D55E00", "#CC79A7", "#999999", "#66C2A5", "#FC8D62",
        "#8DA0CB", "#E78AC3", "#BBBBBB"
    ]

    if "No theme" in themes_order:
        themes_order = [t for t in themes_order if t != "No theme"] + ["No theme"]

    base = (
        alt.Chart(themes_counts)
            .mark_bar()
            .encode(
            x=alt.X("themes:N", sort=themes_order, title="Themes"),
            y=alt.Y("count:Q", title="Count"),
            color=alt.Color(
                "themes:N",
                title="Themes",
                scale=alt.Scale(range=okabe_ito_12),
                sort=themes_order,
                legend=alt.Legend(
                    orient="bottom",
                    columns=7,
                    labelFontSize=14,
                    titleFontSize=16,
                    symbolSize=100,
                    padding=10
                )
            ),
            tooltip=["themes", "count"],
        )
            .properties(width=300, height=250)
    )

    chart = base.facet(
        column=alt.Column(
            "source_filter:N",
            title=None,
            header=alt.Header(labelOrient="top", labelAngle=0)
        )
    )
    #).resolve_scale(y="independent")

    st.altair_chart(chart, use_container_width=True)

def show_mixed_themes():
    st.subheader("Combinations of Themes")
    st.markdown("Some themes are more frequently detected together in TyckTill comments.")
    st.text(" ")

    coocc = compute_theme_cooccurrence(themes_per_park)

    chart = (
        alt.Chart(coocc)
        .mark_rect()
        .encode(
            x=alt.X("theme_a:N", title="Theme A", axis=alt.Axis(labelAngle=45)),
            y=alt.Y("theme_b:N", title="Theme B"),
            color=alt.Color("count:Q", scale=alt.Scale(scheme="viridis"), title="Co-occurrence count"),
            tooltip=["theme_a", "theme_b", "count"]
        )
        .properties(width=600, height=600)
    )

    st.altair_chart(chart, use_container_width=True)

def show_top_topics():
    st.subheader("Top topics in Park-related comments")
    st.text(" ")
    st.markdown(
        "*Park related TyckTill comments* have been defined in 3 different ways: by geographical location, by keywords (strictly) and by keywords (similarity). **Strictly** means that a specified keyword was present in the comment while **similarity** means a keyword or similar word was present in the comment as defined by our model.")
    st.text(" ")

    # compute a shared x-axis scale across all 3 datasets
    def get_global_max(*dfs):
        max_count = 0
        for df in dfs:
            c = (
                df.groupby("topic")
                    .size()
                    .reset_index(name="count")["count"]
                    .max()
            )
            if c > max_count:
                max_count = c
        return max_count

    global_max = get_global_max(
        praise_idea_pts_in_parks,
        praise_idea_by_keywords,
        praise_idea_by_BERTopic
    )

    def top_topics_chart(df, layer_label):
        # count per topic
        counts = (
            df.groupby(["topic", "topic_keywords", "topic_keywords_full", "topic_keywords_short"])
                .size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
                .head(15)
        )

        chart = (
            alt.Chart(counts)
                .mark_bar()
                .encode(
                x=alt.X("count:Q", title="Number of comments", scale=alt.Scale(domain=[0, global_max])),
                y=alt.Y("topic:O", sort="-x", title="Topic number"),
                tooltip=["topic", "topic_keywords_full", "count"],
                color=alt.Color('topic_keywords_short:N',
                                title="Topic keywords",
                                scale=alt.Scale(scheme='tableau20', type='ordinal', interpolate='rgb'),
                                legend=alt.Legend(orient="bottom",
                                                  title="Topic keywords",
                                                  columns=3,        # ← two columns
                                                  labelLimit=500,   # ← allows longer labels
                                                  symbolLimit=200))
            )
                .properties(title=layer_label, width=300, height=250)
        )
        return chart

    chart1 = top_topics_chart(praise_idea_pts_in_parks, "By location")
    chart2 = top_topics_chart(praise_idea_by_keywords, "By Keywords (strictly)")
    chart3 = top_topics_chart(praise_idea_by_BERTopic, "By keywords (similarity)")

    st.altair_chart(chart1 | chart2 | chart3, use_container_width=True)

def show_topics_over_time():
    st.subheader("Top 5 topics over time in Park-related comments")
    st.text(" ")
    st.markdown(
        "*Park related TyckTill comments* have been defined in 3 different ways: by geographical location, by keywords (strictly) and by keywords (similarity). **Strictly** means that a specified keyword was present in the comment while **similarity** means a keyword or similar word was present in the comment as defined by our model.")
    st.text(" ")

    # compute shared Y-axis max across datasets
    def get_global_max(*dfs):
        m = 0
        for df in dfs:
            c = (
                df.groupby(["month", "topic"])
                    .size()
                    .max()
            )
            if c > m:
                m = c
        return m

    global_max = get_global_max(
        praise_idea_pts_in_parks,
        praise_idea_by_keywords,
        praise_idea_by_BERTopic
    )

    def topics_over_time_chart(df, layer_label):
        df = df.copy()

        month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        df["month_labels"] = df["month"].apply(lambda m: month_labels[m - 1])

        month_order = list(range(1, 13))

        # aggregate by month and topic
        topic_counts = (
            df.groupby(["month", "month_labels", "topic", "topic_keywords_full", "topic_keywords_short"])
                .size()
                .reset_index(name="count")
        )

        # get top 5 topics overall
        top_topics = (
            topic_counts.groupby("topic_keywords_full")["count"].sum()
                .sort_values(ascending=False)
                .head(5)
                .index
        )
        topic_counts = topic_counts[topic_counts["topic_keywords_full"].isin(top_topics)]

        chart = (
            alt.Chart(topic_counts)
                .mark_line(point=True)
                .encode(
                x=alt.X("month:O", title="Month", sort=month_order, axis=alt.Axis(labelAngle=0, labelExpr="datum.value - 1 >= 0 ? ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][datum.value - 1] : ''")),
                y=alt.Y("count:Q", title="Comment count", scale=alt.Scale(domain=[0, global_max])),
                color=alt.Color(
                    "topic_keywords_short:N",
                    title="Topic (shortened)",
                    scale=alt.Scale(scheme='category20'), # alt tableau20
                    legend=alt.Legend(orient="bottom",
                                      title="Topic keywords",
                                      columns=3,        # ← two columns
                                      labelLimit=500,   # ← allows longer labels
                                      symbolLimit=200)
                ),
                tooltip=[
                    alt.Tooltip("month_labels:N", title="Month"),
                    alt.Tooltip("topic_keywords_full:N", title="Full keywords"),
                    alt.Tooltip("count:Q", title="Count")
                ]
            )
                .properties(title=layer_label, width=300, height=250)
        )
        return chart

    chart1 = topics_over_time_chart(praise_idea_pts_in_parks, "By location")
    chart2 = topics_over_time_chart(praise_idea_by_keywords, "By keywords (strictly)")
    chart3 = topics_over_time_chart(praise_idea_by_BERTopic, "By keywords (similarity)")

    if chart1 and chart2 and chart3:
        st.altair_chart(chart1 | chart2 | chart3, use_container_width=True)

def show_sentiments_over_time_months_praise_idea():
    st.subheader("Sentiments over time (months) in park-related comments")
    st.markdown("*Park-related* defined by location.")
    st.markdown("Categories included: Praise & Ideas.")
    st.text(" ")

    df = sentiments_for_praise_ideas.copy()

    month_order = [6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5]
    month_labels = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
                    "Jan", "Feb", "Mar", "Apr", "May"]

    # map month numbers to short names
    month_map = dict(zip(month_order, month_labels))
    month_to_order = {m: i for i, m in enumerate(month_order)}  # 0–11 order index

    monthly_sentiments = (
        df.groupby(["year_label", "month", "sentiment_label"])
            .size()
            .reset_index(name="count")
    )

    monthly_sentiments["month_name"] = monthly_sentiments["month"].map(month_map)
    monthly_sentiments["month_order_index"] = monthly_sentiments["month"].map(month_to_order)

    def add_break_rows(g):
        g = g.sort_values("month_order_index")
        last_row = g.iloc[-1]
        # Add a break row (month_order_index=None breaks the line)
        break_row = last_row.copy()
        break_row["month_name"] = None
        break_row["count"] = None
        return pd.concat([g, pd.DataFrame([break_row])], ignore_index=True)

    monthly_sentiments = (
        monthly_sentiments
        .groupby(["year_label", "sentiment_label"], group_keys=False)
        .apply(add_break_rows)
    )

    base = (
        alt.Chart(monthly_sentiments)
        .mark_line(point=True)
        .encode(
            x=alt.X("month_name:N", title="Month", sort=month_labels, axis=alt.Axis(labelAngle=0), scale=alt.Scale(domain=month_labels)),
            y=alt.Y("count:Q", title="Number of comments"),
            color=alt.Color(
                "sentiment_label:N",
                scale=alt.Scale(domain=["POSITIVE", "NEUTRAL", "NEGATIVE"],
                                range=["#009E73", "#999999", "#D55E00"]),
                title="Sentiment"
            ),
            tooltip=["year_label", "month_name", "sentiment_label", "count"]
        )
        .properties(width=500, height=300)
    )

    chart = base.facet(column=alt.Column("year_label:N",header=alt.Header(labelOrient="top", labelAngle=0))
    ).resolve_scale(y="independent")

    st.altair_chart(chart, use_container_width=True)

def show_sentiments_over_time_weekdays_praise_idea():
    st.subheader("Sentiments over time (weekday) in park-related comments")
    st.markdown("*Park-related* defined by location.")
    st.markdown("Categories included: Praise & Ideas.")
    st.text(" ")

    df = sentiments_for_praise_ideas.copy()

    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_abbr = dict(zip(weekday_order, weekday_labels))

    weekday_sentiments = (
        df.groupby(["year_label", "weekday", "sentiment_label"])
            .size()
            .reset_index(name="count")
    )

    weekday_sentiments["weekday_name"] = weekday_sentiments["weekday"].map(weekday_abbr)

    weekday_sentiments["weekday_name"] = pd.Categorical(
        weekday_sentiments["weekday_name"], categories=weekday_labels, ordered=True
    )

    weekday_sentiments = weekday_sentiments.sort_values(
        ["year_label", "sentiment_label", "weekday_name"]
    )

    base = (
        alt.Chart(weekday_sentiments)
            .mark_line(point=True)
            .encode(
            x=alt.X(
                "weekday_name:N",
                title="Weekday",
                sort=weekday_labels,
                axis=alt.Axis(labelAngle=0),
                scale=alt.Scale(domain=weekday_labels)  # show all days
            ),
            y=alt.Y("count:Q", title="Number of comments"),
            color=alt.Color(
                "sentiment_label:N",
                scale=alt.Scale(
                    domain=["POSITIVE", "NEUTRAL", "NEGATIVE"],
                    range=["#009E73", "#999999", "#D55E00"]
                ),
                title="Sentiment"
            ),
            tooltip=["year_label", "weekday_name", "sentiment_label", "count"]
        )
            .properties(width=500, height=300)
    )

    chart = base.facet(
        column=alt.Column(
            "year_label:N",
            header=alt.Header(labelOrient="top", labelAngle=0)
        )
    ).resolve_scale(y="independent")

    st.altair_chart(chart, use_container_width=True)


def display_plot(plot_name):                                                       # *** new tab/button? UPDATE HERE ***
    if plot_name == "DAY/NIGHT":
        show_DAY_NIGHT()
    elif plot_name == "common_themes":
        show_common_themes()
    elif plot_name == "mixed_themes":
        show_mixed_themes()
    elif plot_name == "top_topics":
        show_top_topics()
    elif plot_name == "topics_over_time":
        show_topics_over_time()
    elif plot_name == "sentiments_over_time_months_praise_idea":
        show_sentiments_over_time_months_praise_idea()
    elif plot_name == "sentiments_over_time_weekdays_praise_idea":
        show_sentiments_over_time_weekdays_praise_idea()

# =========
# container

viz_container = st.container()
#viz_container.empty()
with viz_container:

    if st.session_state.selected_layer is not None:
        # Map section
        m = create_base_map()
        layer_type = st.session_state.layer_type
        layer = st.session_state.selected_layer

        if layer_type == "sentiment_score":                                        # *** new tab/button? UPDATE HERE ***
            add_sentiments_layer(m, layer)
        elif layer_type == "pts_per_park_praise_idea":
            add_pts_per_park_praise_idea_layer(m, layer)
        elif layer_type == "pts_per_park_error_complaint":
            add_pts_per_park_error_complaint_layer(m, layer)
        #elif layer_type == "ideas":
        #    add_ideas_layer(m, layer)
        #elif layer_type == "praise":
        #    add_TEST_layer(m, layer)
        elif layer_type == "top5_topics_per_park":
            add_top5_topics_layer(m, layer)

        st_folium(m, width=1200, height=800, key=st.session_state.layer_type)

    elif st.session_state.selected_plot is not None:
        display_plot(st.session_state.selected_plot)

    else:
        st.info("Select a layer or a plot using the buttons above to display the visualisation.")

