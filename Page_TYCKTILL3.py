
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
    data["stats_per_park"] = load_layer(tycktill_GPKG, "stats_per_park")
    data["all_park_related_pts_with_themes"] = load_layer(tycktill_filtered_GPKG, "all_park_related_pts_with_themes")
    data["pts_with_topics_by_location"] = load_layer(tycktill_filtered_GPKG, "pts_in_parks_with_topics")   # by location
    data["pts_with_topics_by_keywords_strictly"] = load_layer(tycktill_filtered_GPKG, "park_comments_by_keyword")   # by keywords (strictly)
    data["pts_with_topics_by_keywords_similarity"] = load_layer(tycktill_filtered_GPKG, "park_comments_by_BERTopic")  # by keywords (similarity)
    data["parks_with_top5_topics"] = load_layer(tycktill_filtered_GPKG, "parks_with_top5_topics")
    return data
raw = load_all_data()

def prepare_data(raw):

    prepped = {}

    # ======
    # topics

    def prepare_keywords(df):
        df = df.copy()
        df["topic_keywords_list"] = df["topic_keywords"].str.split(", ")                          # convert the comma-separated string to a list
        df["topic_keywords_full"] = df["topic_keywords_list"].apply(lambda x: ", ".join(x[:10]))  # full list = first 10 keywords
        df["topic_keywords_short"] = df["topic_keywords_list"].apply(lambda x: ", ".join(x[:3]))  # short list = first 3 keywords
        return df

    # apply list variants to all three filters
    topics_loc = prepare_keywords(raw["pts_with_topics_by_location"])
    topics_key = prepare_keywords(raw["pts_with_topics_by_keywords_strictly"])
    topics_sim = prepare_keywords(raw["pts_with_topics_by_keywords_similarity"])

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


    # *** more prepp ***

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

def add_polygon_layer(m, gdf, column, label_text):
    """
    Generic polygon shading map.
    Replace with your own style rules if needed.
    """

    values = gdf[column].fillna(0)
    classifier = mapclassify.NaturalBreaks(values, k=5)
    breaks = classifier.bins

    colors = ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"]

    def pick_color(val):
        for i, b in enumerate(breaks):
            if val <= b:
                return colors[i]
        return colors[-1]

    folium.GeoJson(
        gdf,
        style_function=lambda feature: {
            "fillColor": pick_color(feature["properties"][column]),
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[column],
            aliases=[label_text + ":"]
        )
    ).add_to(m)

def display_map(layer_type, gdf, column, label_text):
    """
    A single function that decides which map to draw
    based on layer_type.
    """
    m = create_base_map()

    # You can add more map types here
    if layer_type == "per_park":
        add_polygon_layer(m, gdf, column, label_text)
    elif layer_type == "prepped_normalized":
        add_polygon_layer(m, gdf, column, label_text)

    st_folium(m, width=900, height=600, key=layer_type)

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

# ===============
# === FIGURES ===

def show_simple_linechart(df):
    """Dummy graph."""
    chart = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x="month:O",
            y="value:Q"
        )
        .properties(width=700, height=350)
    )
    st.altair_chart(chart, use_container_width=True)

# ==========================
# === TABS, BUTTONS, ETC ===

st.title("Vad tycker besökarna om Stockholms parker?")
st.text("Här finner du sammanställd data från appen TyckTill! Välj bland alternativen nedan för att se resultat av vår analys.")

tab_overview, tab_sentiments, tab_topics, tab_mixed = st.tabs(["Overview", "Sentiments", "Topics", "Mixed"])

# ===============
# TAB 1: overview

with tab_overview:

    overview_choice = st.radio(
        "Choose a map to show:",
        ["Raw layer 1", "Prepped normalized"],
        index=None
    )

    #if overview_choice == "Raw layer 1":
    #    # USER MUST SET THESE:
    #    selected_layer = raw["raw_layer1"]        # your dataset
    #    layer_type = "per_park"                   # logic switch
    #    column = "column1"                        # CHANGE to your real column
    #    label = "Label for tooltip"               # your label

    #    display_map(layer_type, selected_layer, column, label)

    #elif overview_choice == "Prepped normalized":
    #    selected_layer = prepped["normalized_map"]
    #    layer_type = "prepped_normalized"
    #    column = "value_normalized"
    #    label = "Normalized value"

    #    display_map(layer_type, selected_layer, column, label)

# =================
# TAB 2: sentiments

with tab_sentiments:

    st.write("Example graph from raw data")
    #df = raw["raw_layer2"].copy()   # MUST contain columns 'month' and 'value'
    #show_simple_linechart(df)


# ==============
# TAB 3: topics

with tab_topics:

    topic_question = st.radio(
        "Choose a question:",
        ["Do topics vary over time?",
         "What are the top topics?",
         "Map: Top 5 topics per park"],     # *** add more later ***
    )

    if topic_question in [
        "Do topics vary over time?",
        "What are the top topics?"
    ]:
        # pill buttons for category group
        category_group = st.pills(
            "Choose category group:",
            ["Praise + Ideas", "Error + Complaints"],
            selection_mode="single",
            default="Praise + Ideas"
        )

        # select the correct dataset based on group
        if category_group == "Praise + Ideas":
            df_loc = prepped["praise_idea_loc"]
            df_key = prepped["praise_idea_key"]
            df_sim = prepped["praise_idea_sim"]
        else:
            df_loc = prepped["error_complaint_loc"]
            df_key = prepped["error_complaint_key"]
            df_sim = prepped["error_complaint_sim"]

    # ==================================
    # CHART: "Do topics vary over time?"

    if topic_question == "Do topics vary over time?":

        def get_global_max(*dfs):
            m = 0
            for df in dfs:
                if df.empty:
                    continue
                c = df.groupby(["month", "topic"]).size().max()
                m = max(m, c)
            return m

        global_max = get_global_max(df_loc, df_key, df_sim)

        def topics_over_time_chart(df, label):
            if df.empty:
                return None
            df = df.copy()
            month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            df["month_labels"] = df["month"].apply(lambda m: month_labels[m - 1])

            topic_counts = (
                df.groupby(["month", "month_labels", "topic",
                            "topic_keywords_full", "topic_keywords_short"])
                  .size()
                  .reset_index(name="count")
            )

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
                    x=alt.X("month_labels:N", title="Month", sort=month_labels, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("count:Q", title="Comment count",
                            scale=alt.Scale(domain=[0, global_max])),
                    color=alt.Color(
                        "topic_keywords_short:N",
                        title="Topic (shortened)",
                        scale=alt.Scale(scheme='category20'),
                        legend=alt.Legend(
                            orient="bottom",
                            title="Topic keywords",
                            columns=3,
                            labelLimit=500,
                            symbolLimit=200
                        )
                    ),
                    tooltip=[
                        alt.Tooltip("month_labels:N", title="Month"),
                        alt.Tooltip("topic_keywords_full:N", title="Full keywords"),
                        alt.Tooltip("count:Q", title="Count")
                    ]
                )
                    .properties(title=label, width=300, height=250)
            )
            return chart


        chart1 = topics_over_time_chart(df_loc, "By location")
        chart2 = topics_over_time_chart(df_key, "By keywords (strict)")
        chart3 = topics_over_time_chart(df_sim, "By keywords (similarity)")

        charts = [c for c in [chart1, chart2, chart3] if c is not None]
        if charts:
            st.altair_chart(charts[0] | charts[1] | charts[2], use_container_width=True)

    elif topic_question == "What are the top topics?":

        # --- Shared X-axis (max bar length) ---
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


        # --- Chart builder ---
        def top_topics_chart(df, label):
            if df.empty:
                return None

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
                    .head(15)
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
                    ),
                    tooltip=[
                        "topic",
                        "topic_keywords_full",
                        "count",
                    ],
                )
                    .properties(title=label, width=300, height=250)
            )


        # Create the three charts
        chart1 = top_topics_chart(df_loc, "By location")
        chart2 = top_topics_chart(df_key, "By keywords (strict)")
        chart3 = top_topics_chart(df_sim, "By keywords (similarity)")

        # Display them side by side
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

# =====
# TAB X

with tab_mixed:

    option = st.radio(
        "Choose:",
        ["Map A", "Map B", "Graph C"],
        index=None
    )

    #if option == "Map A":
    #    selected_layer = raw["raw_layer3"]
    #    display_map("per_park", selected_layer, "columnX", "Some label")

    #elif option == "Map B":
    #    selected_layer = prepped["subset_A"]
    #    display_map("per_park", selected_layer, "columnY", "Category A")

    #elif option == "Graph C":
    #    df = prepped["subset_B"]
    #    show_simple_linechart(df)