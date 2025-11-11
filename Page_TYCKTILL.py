
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

# ===========
# general tab
with tab1:
    general_choice = st.radio(
        "",
        ["What parks inspire the most ideas?"],  # <<< add more layers here
        index=None,
        horizontal=True
    )

    if general_choice == "What parks inspire the most ideas?":
        st.session_state.selected_layer = stats_per_park
        st.session_state.layer_column = "Idé_rel"
        st.session_state.layer_type = "stats"

# ==============
# sentiments tab
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


# ==========
# topics tab
#with tab3:


# ==============
# themes tab
with tab4:
    plot_choice = st.radio(
        "Make a selection:",
        [
            "What themes are most common in parks?",
            "What themes occur in combination?"
        ],
        horizontal=True,
        index=None  # None = nothing pre-selected
    )

    if plot_choice == "What themes are most common in parks?":
        st.session_state.selected_plot = "faceted_bar"
    elif plot_choice == "What themes occur in combination?":
        st.session_state.selected_plot = "mixed_themes"
    else:
        st.session_state.selected_plot = None

# ============
# display plot

# barchart - theme count per park filter
if st.session_state.selected_plot == "faceted_bar":
    st.subheader("Themes in Park-related comments (3 definitions)")
    st.markdown("Park related TyckTill comments have been defined in 3 different ways: by geographical location, by keywords (strictly) and by keywords (similarity). **Strictly** means that a specified keyword was present in the comment while **Similarity** means a keyword or similar word was present in the comment as defined by or model.")
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
        theme_order = [t for t in themes_order if t != "No theme"] + ["No theme"]

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


# ===========
# display map

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
else:
    st.info("Select a layer using the buttons above to display the visualisation.")
