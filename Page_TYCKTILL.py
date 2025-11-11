
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

# TO DO

# Make clicked buttons highlighted
# Make buttons align to the left
# Make visualisations disappear if another tab is clicked
# Add legend to maps


st.set_page_config(layout="wide")

# ===========
# load layers

@st.cache_data(show_spinner="Loading spatial data...")
def load_layer(path: str, layer_name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path, layer=layer_name)
    return gdf.to_crs(epsg=4326)

sentiments_per_park = load_layer(
    r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\tycktill.gpkg",
    "sentiments_per_park"
) # column to use is called "sentiment_score_per_ha"
stats_per_park = load_layer(
    r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\tycktill.gpkg",
    "stats_per_park"
) # column to use is called "Idé_rel" which shows ideas per park (normalised count)
themes_per_park = load_layer(
    r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg",
    "all_park_related_pts_with_themes"
) # columns to use are themes and source_filter with pts_in_park (for location filter), by BERTopic (for similarity filter), by_keyword (for strict filter) AND combinations of multiple
pts_in_parks_with_topics = load_layer(
    r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg",
    "pts_in_parks_with_topics"
)
pts_in_parks_by_keywords = load_layer(
    r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg",
    "park_comments_by_keyword"
)
pts_in_parks_by_BERTopic = load_layer(
    r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg",
    "park_comments_by_BERTopic"
)

# filter for Beröm in topic files
berom_pts_in_parks = pts_in_parks_with_topics[pts_in_parks_with_topics['Kategori'] == "Beröm"]
berom_by_keywords = pts_in_parks_by_keywords[pts_in_parks_by_keywords['Kategori'] == "Beröm"]
berom_by_BERTopic = pts_in_parks_by_BERTopic[pts_in_parks_by_BERTopic['Kategori'] == "Beröm"]

sentiments_per_park = sentiments_per_park.dropna(subset=["sentiment_score_per_ha"])

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

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Sentiments", "Topics", "Themes"])

# initialize selected layer variable
if "selected_layer" not in st.session_state:
    st.session_state.selected_layer = None
    st.session_state.layer_column = None
    st.session_state.layer_type = None
    st.session_state.selected_plot = None


# ==================================
# ============== TABS ==============

# ==============
# TAB 1: general
with tab1:
    general_choice = st.radio(
        "Make a selection:",
        ["What parks inspire the most ideas?"],  # <<< add more layers here
        index=None,
        horizontal=True
    )

    if general_choice == "What parks inspire the most ideas?":
        st.session_state.selected_layer = stats_per_park
        st.session_state.layer_column = "Idé_rel"
        st.session_state.layer_type = "stats"

# =================
# TAB 2: sentiments
with tab2:
    sentiments_choice = st.radio(
        "Make a selection:",
        ["How do TyckTill users feel about parks?"],    # <<< add more layers here
        horizontal=True,
        index=None  # None = nothing pre-selected
    )

    if sentiments_choice == "How do TyckTill users feel about parks?":
        st.session_state.selected_layer = sentiments_per_park
        st.session_state.layer_column = "sentiment_score_per_ha"
        st.session_state.layer_type = "sentiments"


# =============
# TAB 3: topics
with tab3:
    topics_choice = st.radio(
        "Make a selection:",
        ["What are the top topics?", "Do topics vary over time?"],
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
        index=None  # None = nothing pre-selected
    )

# THESE HAVE TO BE AFTER ANY with tabX: BLOCK! Otherwise it does not work
    if topics_choice == "What are the top topics?":
        st.session_state.selected_plot = "top_topics"
    elif topics_choice == "Do topics vary over time?":
        st.session_state.selected_plot = "topics_over_time"
    elif plot_choice == "What themes are most common in parks?":
        st.session_state.selected_plot = "common_themes"
    elif plot_choice == "What themes occur in combination?":
        st.session_state.selected_plot = "mixed_themes"
    else:
        st.session_state.selected_plot = None


# ============================================
# ============== VISUALIZATIONS ==============

# ============
# display maps

if st.session_state.selected_layer is not None:
    m = folium.Map(location=(59.33, 17.99), zoom_start=10.5, tiles=None)

    # satellite basemap from ESRI
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satellite',
        overlay=False,
        control=True
    ).add_to(m)

    # --- sentiments layer with quantile-based coloring ---
    if st.session_state.layer_type == "sentiments":
        st.subheader("Sentiment score per ha and park")
        st.markdown("Sentiment score was calculated by assigning values to comments by sentiment (positive=1, neutral=0, negative=-1) and then calculating total score per ha.")
        st.text("")

        n_classes = 5
        values = st.session_state.selected_layer[st.session_state.layer_column].values
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
            st.session_state.selected_layer,
            style_function=style_function,
            tooltip=folium.features.GeoJsonTooltip(
                fields=[st.session_state.layer_column],
                aliases=["Sentiment score per ha:"],
                localize=True
            )
        ).add_to(m)

    # --- stats layer (optional linear coloring) ---
    elif st.session_state.layer_type == "stats":
        st.header("Ideas per park (normalised count)")
        n_classes = 5
        values = st.session_state.selected_layer[st.session_state.layer_column].values
        classifier = mapclassify.NaturalBreaks(values, k=n_classes)                      # <<< mapclassify is incompatible with another packge or something which is why it is not working
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
            st.session_state.selected_layer,
            style_function=style_function,
            tooltip=folium.features.GeoJsonTooltip(
                fields=[st.session_state.layer_column],
                aliases=["Ideas per park:"],
                localize=True
            )
        ).add_to(m)

    st_folium(m, width=1200, height=800)


# =============
# display plots

# barchart - theme count per park filter
if st.session_state.selected_plot == "common_themes":
    st.subheader("Themes in Park-related comments (3 definitions)")
    st.text(" ")
    st.markdown("*Park related TyckTill comments* have been defined in 3 different ways: by geographical location, by keywords (strictly) and by keywords (similarity). **Strictly** means that a specified keyword was present in the comment while **Similarity** means a keyword or similar word was present in the comment as defined by our model.")
    st.text(" ")
    st.markdown("*Themes* are defined by precence of theme keywords in comments.")
    st.text(" ") # creates more of space between text and plot

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
    ).resolve_scale(y="independent")

    st.altair_chart(chart, use_container_width=True)

# combinations of themes
elif st.session_state.selected_plot == "mixed_themes":
    st.subheader("Combinations of Themes")
    st.markdown("Some themes are more frequently detected together in TyckTill comments.")
    st.text(" ")

    coocc = compute_theme_cooccurrence(themes_per_park)

    chart = (
        alt.Chart(coocc)
            .mark_rect()
            .encode(
            x=alt.X("theme_a:N", title="Theme A"),
            y=alt.Y("theme_b:N", title="Theme B"),
            color=alt.Color("count:Q", scale=alt.Scale(scheme="viridis"), title="Co-occurrence count"),
            tooltip=["theme_a", "theme_b", "count"]
        )
            .properties(width=600, height=600)
    )

    st.altair_chart(chart, use_container_width=True)

# topics
elif st.session_state.selected_plot == "top_topics":
    st.subheader("Topics in Park-related comments (Beröm)")
    st.text(" ")
    st.markdown("beskrivning")
    st.text(" ")

    def top_topics_chart(df, layer_label):
        # count per topic
        counts = (
            df.groupby(["topic", "topic_keywords"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(15)
        )

        chart = (
            alt.Chart(counts)
            .mark_bar()
            .encode(
                x=alt.X("count:Q", title="Number of comments"),
                y=alt.Y("topic_keywords:N", sort="-x", title="Topic keywords"),
                tooltip=["topic", "topic_keywords", "count"],
                color=alt.value("#1f77b4")
            )
            .properties(title=layer_label, width=300, height=250)
        )
        return chart

    chart1 = top_topics_chart(berom_pts_in_parks, "Pts in Parks with Topics")
    chart2 = top_topics_chart(berom_by_keywords, "By Keywords")
    chart3 = top_topics_chart(berom_by_BERTopic, "By BERTopic")

    st.altair_chart(chart1 | chart2 | chart3, use_container_width=True)


elif st.session_state.selected_plot == "topics_over_time":
    st.subheader("Topics over time in Park-related comments (Beröm)")
    st.text(" ")
    st.markdown("beskrivning")
    st.text(" ")

    def topics_over_time_chart(df, layer_label):
        df = df.copy()

        # use month column
        if "month" not in df.columns:
            st.warning(f"{layer_label} has no 'month' column — skipping.")
            return None

        if np.issubdtype(df["month"].dtype, np.number):
            df["month"] = df["month"].astype(int).clip(1, 12)
            month_order = list(range(1, 13))

        # aggregate by month and topic
        topic_counts = (
            df.groupby(["month", "topic", "topic_keywords"])
                .size()
                .reset_index(name="count")
        )

        # get top 5 topics overall
        top_topics = (
            topic_counts.groupby("topic_keywords")["count"].sum()
                .sort_values(ascending=False)
                .head(5)
                .index
        )
        topic_counts = topic_counts[topic_counts["topic_keywords"].isin(top_topics)]

        chart = (
            alt.Chart(topic_counts)
                .mark_line(point=True)
                .encode(
                x=alt.X("month:O", title="Month", sort=month_order),
                y=alt.Y("count:Q", title="Comment count"),
                color=alt.Color("topic_keywords:N", title="Topic"),
                tooltip=["month", "topic_keywords", "count"]
            )
                .properties(title=layer_label, width=300, height=250)
        )
        return chart

    chart1 = topics_over_time_chart(berom_pts_in_parks, "Pts in Parks with Topics")
    chart2 = topics_over_time_chart(berom_by_keywords, "By Keywords")
    chart3 = topics_over_time_chart(berom_by_BERTopic, "By BERTopic")

    if chart1 and chart2 and chart3:
        st.altair_chart(chart1 | chart2 | chart3, use_container_width=True)

else:
    st.info("Select a layer using the buttons above to display the visualisation.")

# sentiments over time

