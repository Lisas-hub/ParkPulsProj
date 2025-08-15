
import geopandas as gpd
import pandas as pd
from shapely.strtree import STRtree
import networkx as nx

# ===== LAYERS =======

def prepp_layer1():

    # ==== layer1: original park layer ====

    layer1 = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Temp\Sociotop_2024_edited.gpkg", layer="Sociotop_2024_edit3")
    layer1 = layer1.drop(columns=['AREA', 'ANTAL', 'Inventering_2', 'change_made'], errors='ignore')

    # Format the names to remove any capital letters in the middle of a name like SÖdra Rosendalsparken
    layer1["NAMN"] = layer1["NAMN"].str.title()

    return layer1
layer1 = prepp_layer1()

def create_layer2():

    # ==== layer2: created by dissolving layer1 ====

    layer2 = layer1.copy()  # this step prevents edits to layer1 which will be important later in the script

    # == fix geometries ==
    layer2['geometry'] = layer2['geometry'].buffer(0)
    # Remove tiny slivers between polygons that should be touching
    layer2['geometry'] = layer2['geometry'].buffer(0.1)

    # == group intersecting polygons then dissolve ==
    # list geometries
    geoms = list(layer2.geometry)
    tree = STRtree(geoms)

    # build a graph of touching/intersecting geometries
    edges = []
    for i, geom in enumerate(geoms):
        for j in tree.query(geom):
            if i < j and geom.intersects(geoms[j]):
                edges.append((i, j))

    # build graph and get connected components
    G = nx.Graph()
    G.add_edges_from(edges)
    components = list(nx.connected_components(G))

    # create column group
    layer2["group"] = -1  # temp placeholder

    # add group value to intersecting polygons
    for group_id, component in enumerate(components, 1):
        for idx in component:
            layer2.at[idx, "group"] = group_id

    # add unique group values to remaining ungrouped polygons
    next_group_id = len(components) + 1
    for idx in layer2[layer2["group"] == -1].index:
        layer2.at[idx, "group"] = next_group_id
        next_group_id += 1

    # dissolve geometries by group
    layer2 = layer2.dissolve(by="group", as_index=False)

    # reduce buffer to go back to original size again (after fix slivers earlier)
    layer2['geometry'] = layer2['geometry'].buffer(-0.1)

    # == organise columns in the attribute table of layer2 ==
    # drop most of the columns except a selected the relevant ones
    columns_to_keep = ["group",
                       "geometry"]  # *** OBS! there is also a fid column created but this does not correspont to previous fid or New_ID

    layer2 = layer2[columns_to_keep]

    return layer2
layer2 = create_layer2()


# ============ PREP ==============

def NAMN_XXX_to_layer2(layer2):

    # NAMN_combined: lists all occurences of NAMN from layer1 when polyons have dissolved in layer2
    joined_namn = gpd.sjoin(
        layer1[['geometry', 'NAMN']],
        layer2[['geometry']],
        how='left',
        predicate='intersects'
    )

    grouped_namn = (
        joined_namn.groupby("index_right")["NAMN"]
            .apply(lambda x: ", ".join(sorted(
            set(x.dropna()))))  # set(x) removes duplicate names, sorted() gives consistent order, dropna() prevents "nan" strings in the result
            .reset_index()
    )

    layer2["NAMN_combined"] = layer2.index.map(grouped_namn.set_index("index_right")["NAMN"])

    # NAMN_top5: same as NAMN_combined except the list only contains a maximum of 5 names (from the largest polygons)

    # Add area to layer1
    layer1["layer1_area"] = layer1.geometry.area

    joined_5namn = gpd.sjoin(
        layer1[["geometry", "NAMN", "layer1_area"]],
        layer2[["geometry"]],
        how="left",
        predicate="intersects"
    )

    def summarize_names(df):
        unique_names = df[["NAMN", "layer1_area"]].dropna().drop_duplicates()
        sorted_names = unique_names.sort_values(by="layer1_area", ascending=False)["NAMN"]
        top_names = sorted_names.head(5).tolist()
        if len(sorted_names) > 5:
            top_names.append("m.fl.")
        return ", ".join(top_names)

    summarized_namn = (
        joined_5namn.groupby("index_right")
            .apply(
            summarize_names)  # *** address the warning? "DeprecationWarning: DataFrameGroupBy.apply operated on the grouping columns. This behavior is deprecated, and in a future version of pandas the grouping columns will be excluded from the operation. Either pass `include_groups=False` to exclude the groupings or explicitly select the grouping columns after groupby to silence this warning."
            .reset_index(name="NAMN_top5")
    )

    layer2["NAMN_top5"] = layer2.index.map(summarized_namn.set_index("index_right")["NAMN_top5"])

    return layer2
layer2 = NAMN_XXX_to_layer2(layer2)

def stadsdelar_to_layer2(layer2):

    # == add stadsdelar ==
    stadsdelar = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\Stadsdelar_Stadskartan.gpkg").to_crs(layer2.crs)
    # drop all columns except NAMN (på stadsdelar)
    columns_to_keep_stadsdelar = ["geometry", "NAMN"]
    stadsdelar = stadsdelar[columns_to_keep_stadsdelar]

    intersection_stadsdelar = gpd.overlay(layer2, stadsdelar, how='intersection')
    intersection_stadsdelar["overlap_area"] = intersection_stadsdelar.geometry.area

    largest_overlap = intersection_stadsdelar.sort_values("overlap_area", ascending=False).drop_duplicates("NAMN_combined")

    layer2 = layer2.merge(
        largest_overlap[["NAMN_combined", "NAMN"]],
        on="NAMN_combined",
        how="left"
    )

    layer2 = layer2.rename(columns={"NAMN": "stadsdelar"})

    return layer2
layer2 = stadsdelar_to_layer2(layer2)

def stadsdelsomraden_to_layer2(layer2):

    # == add stadsdelsomraden ==
    stadsdelsomraden = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\Stadsdelsomraden_Stadskartan.gpkg").to_crs(layer2.crs)
    # drop all columns except stadsdelsområden
    columns_to_keep_stadsdelsomraden = ["geometry", "Omrade"]
    stadsdelsomraden = stadsdelsomraden[columns_to_keep_stadsdelsomraden]

    intersection_stadsdelsomraden = gpd.overlay(layer2, stadsdelsomraden, how='intersection')
    intersection_stadsdelsomraden["overlap_area"] = intersection_stadsdelsomraden.geometry.area

    largest_overlap = intersection_stadsdelsomraden.sort_values("overlap_area", ascending=False).drop_duplicates("NAMN_combined")

    layer2 = layer2.merge(
        largest_overlap[["NAMN_combined", "Omrade"]],
        on="NAMN_combined",
        how="left"
    )

    layer2 = layer2.rename(columns={"Omrade": "stadsdelsomraden"})

    return layer2
layer2 = stadsdelsomraden_to_layer2(layer2)


# === THEMES ===

# TO DO
# LIGHTING - filter out underground lighting (tunnels)??
# LIGHTING - calculate point density of street lights?
# SAFETY SURVEY - use buffered parks? to catch the area next to parks too?

# lighting
def THEME_lighting_to_layer2(layer2):

    # street lighting

    street_lighting = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Belysningsmontage_Punkt.gpkg").to_crs(layer2.crs)
    layer2["temp_ID"] = layer2.index  # create a column to be used in the merge later

    # buffer the lighting points
    street_lighting['geometry'] = street_lighting['geometry'].buffer(30)

    # *** temporary file - can be removed ***
    street_lighting.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_street_lighting_buffer30", driver="GPKG", mode="w")

    # dissolve buffers to get accurate area calculations later
    dissolve_lights = street_lighting.dissolve()

    # calculate area
    layer2['area'] = layer2.geometry.area

    # intersect and calculate intersected area
    intersection_lights = gpd.overlay(layer2, dissolve_lights, how='intersection')
    intersection_lights['intersect_area'] = intersection_lights.geometry.area

    # sum intersected area by polygon
    intersect_sum = intersection_lights.groupby('temp_ID')['intersect_area'].sum().reset_index()

    # merge back with original layer2
    layer2 = layer2.merge(intersect_sum, on='temp_ID', how='left')

    # fill NaNs (polygons with no intersection) with 0
    layer2['intersect_area'] = layer2['intersect_area'].fillna(0)

    # Calculate lighting coverage %
    layer2['lighting_coverage'] = (layer2['intersect_area'] / layer2['area']) # OBS! some polygons have lighting coverage 100,00000000000003 but that slight excess is some type of discrepance caused by python

    # Drop irrelevant columns
    layer2 = layer2.drop(columns=['area', 'intersect_area', 'temp_ID'])

    return layer2
layer2 = THEME_lighting_to_layer2(layer2)

# safety
def THEME_safety_to_layer2(layer2):

    safety_survey = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\Safety\Survey_CrimeFear_Basomr_2024_08-29\Survey_CrimeFear_Basomr_2024_08-29.shp").to_crs(layer2.crs)
    # data description:
    # Crimevictim = Share that has been previously victimized the past 12 years (any crime)
    # Unsafe_NBHD = Share that feel unsafe/very unsafe in their neighborhood/residential area
    # Unsafe_Residential = Share that feel unsafe in one or more places in their residential building

    #parks_and_safety = gpd.sjoin(layer2, safety_survey, how='left', predicate='intersects')
    # *** OBS! many to many join (multiple 'group' rows) - summarize per park ***
    # use variable Unsafe_NBHD ?? intersect and area-weighted column ??

    safety_survey['basomrade_area'] = safety_survey.geometry.area

    # intersect parks and pop
    parks_and_safety = gpd.overlay(layer2, safety_survey, how='intersection')
    # calculate intersection area
    parks_and_safety['intersect_area'] = parks_and_safety.geometry.area
    # calculate safety weighted by intersect area
    parks_and_safety['Unsafe_NBHD_weighted'] = (parks_and_safety['UnsafeNBHD'] * (
                parks_and_safety['intersect_area'] / parks_and_safety['basomrade_area']))

    # group parks as usual (by column group)
    Unsafe_NBHD_weighted = parks_and_safety.groupby('group').agg({
        'Unsafe_NBHD_weighted': 'sum'
    }).reset_index()

    layer2 = layer2.merge(Unsafe_NBHD_weighted, on='group', how='left')

    return layer2
layer2 = THEME_safety_to_layer2(layer2)


layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_safety", driver="GPKG", mode="w")


