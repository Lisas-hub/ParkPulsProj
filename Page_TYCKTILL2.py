
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

st.set_page_config(layout="wide")

tycktill_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\tycktill.gpkg"
tycktill_filtered_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg"

# ===================
# === load layers ===

@st.cache_data(show_spinner="Loading spatial data...")
def load_layer(path: str, layer_name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path, layer=layer_name)
    return gdf.to_crs(epsg=4326)


@st.cache_data(show_spinner="Loading layers…")
def load_all_data():
    data = {}
    data["sentiments_per_park"] = load_layer(tycktill_GPKG, "sentiments_per_park")
    data["stats_per_park"] = load_layer(tycktill_GPKG, "stats_per_park")
    data["themes_per_park"] = load_layer(tycktill_filtered_GPKG, "all_park_related_pts_with_themes")
    data["pts_in_parks_with_topics"] = load_layer(tycktill_filtered_GPKG, "pts_in_parks_with_topics")   # by location
    data["pts_in_parks_by_keywords"] = load_layer(tycktill_filtered_GPKG, "park_comments_by_keyword")   # by keywords (strictly)
    data["pts_in_parks_by_BERTopic"] = load_layer(tycktill_filtered_GPKG, "park_comments_by_BERTopic")  # by keywords (similarity)
    data["parks_with_top5_topics"] = load_layer(tycktill_filtered_GPKG, "parks_with_top5_topics")
    return data


# ====================
# === prepp layers ===

@st.cache_data(show_spinner="Preparing data...")
def prepare_all_data(_data):

    # ======================================
    # praise+idea and error+complaint groups
    themes = _data["themes_per_park"]
    praise_idea = themes[themes["Kategori"].isin(["Beröm","Idé"])]
    error_complaint = themes[themes["Kategori"].isin(["Felanmälan","Klagomål"])]

    # ==========
    # sentiments
    sentiments = _data["sentiments_per_park"].dropna(subset=["sentiment_score_per_ha"])

    # ======
    # topics

    def prepare_keywords(df):
        df = df.copy()
        df["topic_keywords_list"] = df["topic_keywords"].str.split(", ")
        df["topic_keywords_full"] = df["topic_keywords_list"].apply(lambda x: ", ".join(x[:10]))
        df["topic_keywords_short"] = df["topic_keywords_list"].apply(lambda x: ", ".join(x[:3]))
        return df

    # apply shortened topic_keywords list
    topics_loc      = prepare_keywords(_data["pts_in_parks_with_topics"])
    topics_key      = prepare_keywords(_data["pts_in_parks_by_keywords"])
    topics_sim      = prepare_keywords(_data["pts_in_parks_by_BERTopic"])

    # ==============
    # prepped layers

    return {
        "praise_idea_loc": topics_loc[topics_loc["Kategori"].isin(["Beröm", "Idé"])],
        "praise_idea_key": topics_key[topics_key["Kategori"].isin(["Beröm", "Idé"])],
        "praise_idea_sim": topics_sim[topics_sim["Kategori"].isin(["Beröm", "Idé"])],
        "error_complaint_loc": topics_loc[topics_loc["Kategori"].isin(["Felanmälan", "Klagomål"])],
        "error_complaint_key": topics_key[topics_key["Kategori"].isin(["Felanmälan", "Klagomål"])],
        "error_complaint_sim": topics_sim[topics_sim["Kategori"].isin(["Felanmälan", "Klagomål"])],
        "sentiments": _data["sentiments_per_park"].dropna(subset=["sentiment_score_per_ha"]),
        "parks_with_top5_topics": _data["parks_with_top5_topics"],
    }

raw_data = load_all_data()
prepped_data = prepare_all_data(raw_data)

# ======================================================================================================================

# ==========
# page setup

st.title("Vad tycker besökarna om Stockholms parker?")
st.text("Här finner du sammanställd data från appen TyckTill! Välj bland alternativen nedan för att se resultat av vår analys.")

# ========================
# initialize session state

if "selection" not in st.session_state:
    st.session_state.selection = {
        "tab": None,
        "option": None,
        "suboption": None,
    }


# ============
#

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

def add_pts_per_park_praise_idea_layer(m, layer):        # *** check code ***
    st.header("Praise and ideas per park (normalized count)")
    col = st.session_state.get("layer_column", "_value")  # fallback

    # handle NaN rows
    layer["_is_missing"] = layer[col].isna()
    layer["_value"] = layer[col].fillna(0)

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

    layer["tooltip_text"] = layer.apply(lambda r: fmt(r["_value"], r["_is_missing"]), axis=1)

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




def show_overview_praise_map():
    pass

def show_overview_error_map():
    pass

def show_day_night_plot():
    pass


def show_sentiment_map():
    pass

def show_sentiments_months(category_group, sentiments_df): # *** fixa, ska jag ens anv nuvarande fil som input? (endast by location) ***
    st.subheader("Sentiments over time (months) in park-related comments")
    st.markdown("*Park-related* defined by location.")
    st.markdown("Categories included: Praise & Ideas.")
    st.text(" ")

    if category_group == "Beröm + Idé":
        df = sentiments_df[sentiments_df["Kategori"].isin(["Beröm", "Idé"])]
    else:
        df = sentiments_df[sentiments_df["Kategori"].isin(["Felanmälan", "Klagomål"])]

    df = df.copy()

    df["month_name"] = df["month"].map({
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov",
        12: "Dec"
    })

    agg = (
        df.groupby(["month", "month_name"])["sentiment_score"]
            .mean()
            .reset_index()
    )

    chart = (
        alt.Chart(agg)
            .mark_line(point=True)
            .encode(
            x=alt.X("month:O", sort=list(range(1, 13)), title="Month"),
            y=alt.Y("sentiment_score:Q", title="Avg sentiment"),
            tooltip=["month_name", "sentiment_score"]
        )
            .properties(width=700, height=350)
    )

    st.altair_chart(chart, use_container_width=True)

def show_topics_top():
    pass

def show_topics_over_time(category_group, data):
    st.subheader("Top 5 topics over time in Park-related comments")
    st.text(" ")
    st.markdown(
        "*Park related TyckTill comments* have been defined in 3 different ways: by geographical location, by keywords (strictly) and by keywords (similarity). **Strictly** means that a specified keyword was present in the comment while **similarity** means a keyword or similar word was present in the comment as defined by our model.")
    st.text(" ")

    if category_group == "Beröm + Idé":
        df_loc = data["praise_idea_loc"]
        df_key = data["praise_idea_key"]
        df_sim = data["praise_idea_sim"]
    else:
        df_loc = data["error_complaint_loc"]
        df_key = data["error_complaint_key"]
        df_sim = data["error_complaint_sim"]

    def get_global_max(*dfs):
        m = 0
        for df in dfs:
            c = df.groupby(["month", "topic"]).size().max()
            m = max(m, c)
        return m

    global_max = get_global_max(df_loc, df_key, df_sim)

    def topics_over_time_chart(df, title):

        month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        df = df.copy()
        df["month_labels"] = df["month"].apply(lambda m: month_labels[m - 1])

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
                x=alt.X("month:O", title="Month", sort=list(range(1,13)), axis=alt.Axis(labelAngle=0, labelExpr="datum.value - 1 >= 0 ? ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][datum.value - 1] : ''")),
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
                .properties(title=title, width=300, height=250)
        )
        return chart

    chart1 = topics_over_time_chart(df_loc, "By location")
    chart2 = topics_over_time_chart(df_key, "By keywords (strict)")
    chart3 = topics_over_time_chart(df_sim, "By keywords (similarity)")

    if chart1 and chart2 and chart3:
        st.altair_chart(chart1 | chart2 | chart3, use_container_width=True)

def show_topics_top5_parks():
    pass


# ==========
# tab layout

tab_overview, tab_sentiments, tab_topics, tab_themes = st.tabs(
    ["Overview", "Sentiments", "Topics", "Themes"]
)

with tab_overview:
    choice = st.radio(
        "Choose an overview plot/map:",
        ["Praise & Ideas", "Errors & Complaints", "Day/Night × Category"],
        index=None
    )

    st.session_state.selection["tab"] = "overview"
    st.session_state.selection["option"] = choice

with tab_sentiments:
    choice = st.radio(
        "Select a sentiment view:",
        [
            "Overall park sentiments",
            "Sentiments over months",
            "Sentiments over weekdays"
        ],
        index=None
    )

    st.session_state.selection["tab"] = "sentiments"
    st.session_state.selection["option"] = choice

with tab_topics:
    option = st.radio(
        "Select a topics view:",
        [
            "Top topics overall",
            "Topics over time",
            "Top 5 topics per park"
        ],
        index=None
    )

    st.session_state.selection["tab"] = "topics"
    st.session_state.selection["option"] = option

    # third-level selector appears only if needed
    if option == "Topics over time":
        suboption = st.pills(
            "Category group:",
            ["Beröm + Idé", "Felanmälan + Klagomål"],
            default="Beröm + Idé"
        )
        st.session_state.selection["suboption"] = suboption
    else:
        st.session_state.selection["suboption"] = None


# ======================================================================================================================

selection = st.session_state.selection

if selection["tab"] == "overview":
    if selection["option"] == "Praise & Ideas":
        show_overview_praise_map()
    elif selection["option"] == "Errors & Complaints":
        show_overview_error_map()
    elif selection["option"] == "Day/Night × Category":
        show_day_night_plot()

elif selection["tab"] == "sentiments":
    if selection["option"] == "Overall park sentiments":
        show_sentiments_map()
    elif selection["option"] == "Sentiments over months":
        show_sentiments_months(
            category_group=selection["suboption"],
            sentiments_df=prepped_data["sentiments"]
        )
    elif selection["option"] == "Sentiments over weekdays":
        show_sentiments_weekdays()

elif selection["tab"] == "topics":
    if selection["option"] == "Top topics overall":
        show_topics_top()

    elif selection["option"] == "Topics over time":
        show_topics_over_time(
            category_group=selection["suboption"],
            data=prepped_data
        )

    elif selection["option"] == "Top 5 topics per park":
        show_topics_top5_parks()

elif selection["tab"] == "themes":
    ...

