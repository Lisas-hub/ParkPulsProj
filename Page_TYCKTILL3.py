
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


def display_map(layer_type, gdf, column, label_text):
    """
    A single function that decides which map to draw
    based on layer_type.
    """
#    m = create_base_map()

    # You can add more map types here
#    if layer_type == "per_park":
#        add_polygon_layer(m, gdf, column, label_text)
#    elif layer_type == "prepped_normalized":
#        add_polygon_layer(m, gdf, column, label_text)

#    st_folium(m, width=900, height=600, key=layer_type)



# ===============
# === FIGURES ===

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

MONTH_LABELS_JUN_TO_MAY = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                           "Dec", "Jan", "Feb", "Mar", "Apr", "May"]

def add_month_label(df):
    df = df.copy()
    df["month_label"] = df["month"].apply(lambda m: MONTH_LABELS[m-1])
    return df

# ==================
# Variable over time

# sentiments or topics prep function
def prepare_for_chart(df, mode, group_top_n=5):
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

    # --- Always add month_label ---
    df = add_month_label(df).copy()

    # ==============================================================
    # SENTIMENTS MODE
    # ==============================================================

    if mode == "sentiment":

        if "sentiment_label" not in df.columns:
            return pd.DataFrame()

        # group_label = sentiment_label
        df["group_label"] = df["sentiment_label"]

        # aggregate counts
        agg = (
            df.groupby(["month", "month_label", "group_label"])
              .size()
              .reset_index(name="count")
        )

        # attach year_label using exact source rows
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

    # ==============================================================
    # TOPICS MODE
    # ==============================================================

    if mode == "topics":

        if "topic" not in df.columns:
            return pd.DataFrame()

        # Step 1: find top N topics globally
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

        # aggregate
        agg = (
            df_small.groupby(["month", "month_label", "group_label"])
                    .size()
                    .reset_index(name="count")
        )

        # attach year_label properly
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

# ------------------------------------------------------
# 2) Build one chart (one panel)
# ------------------------------------------------------
def chart_single_panel(df, title, months_order):
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


# ------------------------------------------------------
# 3) Combine charts horizontally
# ------------------------------------------------------
def chart_multi_panel(dfs, titles, ordered_months, mode=None):

    if not dfs or all(len(df) == 0 for df in dfs):
        return None

    panels = []

    # Which month labels to show on axis
    month_labels = ordered_months
    month_order_map = {m: i for i, m in enumerate(ordered_months)}

    for df, title in zip(dfs, titles):

        if df.empty:
            continue

        df = df.copy()

        # ---------------------------------------------------------
        # Detect mode
        # ---------------------------------------------------------
        is_sentiment = set(df["group_label"].unique()).issubset(
            {"POSITIVE", "NEUTRAL", "NEGATIVE"}
        )

        # ---------------------------------------------------------
        # Palette + legend position
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # Month ordering
        # ---------------------------------------------------------
        df["month_order"] = df["month_label"].map(month_order_map)

        # ---------------------------------------------------------
        # FIX: Break the line between years (May → June)
        # ---------------------------------------------------------
        if len(dfs) == 2 and "year_label" in df.columns:
            def add_break(g):
                g = g.sort_values("month_order")
                last = g.iloc[-1]

                # Insert a null row → breaks Altair line path
                b = last.copy()
                b["month_order"] = None
                b["count"] = None
                b["month_label"] = None
                return pd.concat([g, pd.DataFrame([b])], ignore_index=True)

            df = (
                df.groupby(["group_label", "year_label"], group_keys=False)
                    .apply(add_break)
            )

        # ---------------------------------------------------------
        # Axis field (no need for complicated year index now)
        # ---------------------------------------------------------
        x_field = "month_order:O"

        # ---------------------------------------------------------
        # Chart
        # ---------------------------------------------------------
        chart = (
            alt.Chart(df)
                .mark_line(point=True, strokeWidth=2)
                .encode(
                x=alt.X(
                    x_field,
                    axis=alt.Axis(
                        title="Month",
                        labels=True,
                        labelExpr=f"""['{"','".join(month_labels)}'][datum.value]"""
                    ),
                    scale=alt.Scale(
                        domain=[i for i in range(len(month_labels))]  # only valid month indexes
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

    sentiment_question = st.radio(
        "Choose a question",
        ["Do sentiments vary over time?",
         "Other sentiment question"],
        key="sentiment_selection_1"
    )

    if sentiment_question in [
        "Do sentiments vary over time?",
        "Other sentiment question"
    ]:
        # pill buttons for category group
        category_group = st.pills(
            "Choose category group:",
            ["Praise + Ideas", "Error + Complaints"],
            selection_mode="single",
            default="Praise + Ideas",
            key="sentiment_selection_2"
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

    if sentiment_question == "Do sentiments vary over time?":

        mode = st.radio(
            "Choose view:",
            ["Two-year comparison", "Three park related filters comparison"],
            key="sentiment_selection_3"
        )

        st.subheader("Sentiments over time")

        filter_vals = ["Beröm", "Idé"] if category_group == "Praise + Ideas" else ["Felanmälan", "Klagomål"]

        df_base = raw["all_park_related_pts_with_themes"]
        df_base = df_base[df_base["Kategori"].isin(filter_vals)]

        # SENTIMENT MODE
        prepared = prepare_for_chart(df_base, mode="sentiment")

        if mode == "Two-year comparison":
            years = sorted(prepared["year_label"].unique())
            dfs = [prepared[prepared["year_label"] == y] for y in years]
            titles = [f"{y}" for y in years]
            # Two-year comparison → June–May
            month_order = MONTH_LABELS_JUN_TO_MAY
            chart = chart_multi_panel(dfs, titles, month_order, mode="sentiment")


        else:  # Three park related filters comparison

            # Prepare each source

            dfs = [
                prepare_for_chart(prepped["praise_idea_loc"], "sentiment") if category_group == "Praise + Ideas"
                else prepare_for_chart(prepped["error_complaint_loc"], "sentiment"),

                prepare_for_chart(prepped["praise_idea_key"], "sentiment") if category_group == "Praise + Ideas"
                else prepare_for_chart(prepped["error_complaint_key"], "sentiment"),

                prepare_for_chart(prepped["praise_idea_sim"], "sentiment") if category_group == "Praise + Ideas"
                else prepare_for_chart(prepped["error_complaint_sim"], "sentiment"),
            ]
            titles = ["By location", "By keywords (strict)", "By keywords (similarity)"]

            # Three park related filters comparison → Jan–Dec
            month_order = MONTH_LABELS
            chart = chart_multi_panel(dfs, titles, month_order, mode="topics")

        if chart:
            st.altair_chart(chart, use_container_width=True)


# ==============
# TAB 3: topics

with tab_topics:

    topic_question = st.radio(
        "Choose a question:",
        ["Do topics vary over time?",
         "What are the top topics?",
         "Map: Top 5 topics per park"],     # *** add more later ***
        key="topics_view_mode"
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

        mode = st.radio(
            "Choose view:",
            ["Two-year comparison", "Three park-related filters comparison"]
        )

        if mode == "Two-year comparison":
            df = prepare_for_chart(df_loc, "topics")
            dfs = [df[df["year_label"] == y] for y in sorted(df["year_label"].unique())]
            titles = [f"Year {y}" for y in sorted(df["year_label"].unique())]
            month_order = MONTH_LABELS_JUN_TO_MAY

        else:
            dfs = [
                prepare_for_chart(df_loc, "topics"),
                prepare_for_chart(df_key, "topics"),
                prepare_for_chart(df_sim, "topics"),
            ]
            titles = ["By location", "By keywords (strict)", "By keywords (similarity)"]
            month_order = MONTH_LABELS  # Three-sources uses Jan–Dec

        chart = chart_multi_panel(dfs, titles, month_order)
        if chart:
            st.altair_chart(chart, use_container_width=True)

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
