
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


# === THEME ===

# TO DO (optional)
# add a column in population_aggregated that lists all values in column DESO (IDs) that were included in the aggregation?
# remove sections for aggregated variables and only keep weighted variables?


# socioeconomic
def THEME_socioeconomic_to_layer2(layer2):

    # == socioeconomic ==

    deso_inkomster = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\SLU_GET\SCB_13juni\Inkomster\Tab11_DeSO_2023_region.shp").to_crs(layer2.crs)
    deso_befolkning_age = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\SLU_GET\SCB_13juni\Befolkning\Tab1_DeSO_2023_region.shp").to_crs(
        layer2.crs)
    deso_befolkning_birthplace = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\SLU_GET\SCB_13juni\Befolkning\Tab4_DeSO_2023_region.shp").to_crs(
        layer2.crs)
    deso_befolkning_migration = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\SLU_GET\SCB_13juni\Befolkning\Tab5_DeSO_2023_region.shp").to_crs(
        layer2.crs)

    municipality = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\Kommun_Stadskartan.gpkg").to_crs(layer2.crs)

    deso_inkomster = gpd.clip(deso_inkomster, municipality)
    deso_befolkning_age = gpd.clip(deso_befolkning_age, municipality)
    deso_befolkning_birthplace = gpd.clip(deso_befolkning_birthplace, municipality)
    deso_befolkning_migration = gpd.clip(deso_befolkning_migration, municipality)

    deso_inkomster.to_file("data/VARIABLES_NEW.gpkg", layer="DeSo_inkomster", driver="GPKG", mode="w")
    deso_befolkning_age.to_file("data/VARIABLES_NEW.gpkg", layer="DeSo_befolkning_age", driver="GPKG", mode="w")
    deso_befolkning_birthplace.to_file("data/VARIABLES_NEW.gpkg", layer="DeSo_befolkning_birthplace", driver="GPKG", mode="w")
    deso_befolkning_migration.to_file("data/VARIABLES_NEW.gpkg", layer="DeSo_befolkning_migration", driver="GPKG", mode="w")

    # check the features that look like lines in QGIS, ex DESO IDs that starts with 0126C
    # deso_inkomster['area'] = deso_inkomster.geometry.area
    # small_polygons = deso_inkomster[deso_inkomster["area"] < 400]  # the smallest real deso area = 231123 but there is one large sliver area = 333
    # print(small_polygons)

    # drop slivers
    deso_inkomster = deso_inkomster[deso_inkomster.area >= 400].reset_index(drop=True)
    deso_befolkning_age = deso_befolkning_age[deso_befolkning_age.area >= 400].reset_index(drop=True)
    deso_befolkning_birthplace = deso_befolkning_birthplace[deso_befolkning_birthplace.area >= 400].reset_index(drop=True)
    deso_befolkning_migration = deso_befolkning_migration[deso_befolkning_migration.area >= 400].reset_index(drop=True)

    # buffer the park polygons
    layer2_buffered = layer2.copy()
    layer2_buffered['geometry'] = layer2_buffered.geometry.buffer(500)
    # *** TEMP FILE - can be removed ***
    layer2_buffered.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_park_buffer500", driver="GPKG", mode="w")

    layer2['park_area'] = layer2.geometry.area

    # == aggregated resident population near parks ==

    # join parks and population layer (multiple polygons per "group", aka park, that will be aggregated in the next step)
    parks_and_population = gpd.sjoin(layer2_buffered, deso_befolkning_age, how='left', predicate='intersects')

    # aggregate kid population counts per park
    population_columns = ['Alder_0_6', 'Alder_7_15', 'Alder_16_1', 'Alder_20_2', 'Alder_25_4', 'Alder_45_6', 'Alder_65', 'Totalt']
    population_aggregated = parks_and_population.groupby(['group'])[population_columns].sum().reset_index()
    layer2 = layer2.merge(population_aggregated, on='group', how='right')
    layer2 = layer2.rename(columns={"Alder_0_6": "AGG_Alder_0_6", "Alder_7_15": "AGG_Alder_7_15", "Alder_16_1": "AGG_Alder_16_1", "Alder_20_2": "AGG_Alder_20_2", "Alder_25_4": "AGG_Alder_25_4", "Alder_45_6": "AGG_Alder_45_6", "Alder_65": "AGG_Alder_65", "Totalt": "AGG_Totalt"})

    # == aggregated income of the population near parks ==

    # join parks and income
    parks_and_income = gpd.sjoin(layer2_buffered, deso_inkomster, how='left', predicate='intersects')

    #aggregate
    income_columns = ['Kvartil1', 'Kvartil2', 'Kvartil3', 'Kvartil4', 'Totalt', 'MedianInk']
    income_aggregated = parks_and_income.groupby(['group'])[income_columns].sum().reset_index()
    layer2 = layer2.merge(income_aggregated, on='group', how='right')
    layer2 = layer2.rename(
        columns={"Kvartil1": "AGG_Kvartil1", "Kvartil2": "AGG_Kvartil2", "Kvartil3": "AGG_Kvartil3",
                 "Kvartil4": "AGG_Kvartil4", "Totalt": "AGG_Totalt_1",
                 "MedianInk": "AGG_MedianInk"})

    # == weighted joins for income and population for more accuracy ==

    # INCOME
    # area of deso polygons
    deso_inkomster['deso_area'] = deso_inkomster.geometry.area

    # intersect buffered parks and income
    parks_income_intersection = gpd.overlay(layer2_buffered, deso_inkomster, how='intersection')
    # calculate intersection area
    parks_income_intersection['intersect_area'] = parks_income_intersection.geometry.area
    # calculate income weighted by intersect area
    parks_income_intersection['income_weighted'] = (parks_income_intersection['MedianInk'] * parks_income_intersection['intersect_area'])

    # group parks as usual (by column group)
    income_weighted_agg = parks_income_intersection.groupby('group').agg({
        'income_weighted': 'sum',
        'intersect_area': 'sum'
    }).reset_index()

    # calculate final area-weighted median income
    income_weighted_agg['area_weighted_income'] = income_weighted_agg['income_weighted'] / income_weighted_agg['intersect_area']

    # add to layer2
    layer2 = layer2.merge(income_weighted_agg[['group', 'area_weighted_income']], on='group', how='left')

    # POPULATION
    # area of deso polygons
    deso_befolkning_age['deso_area'] = deso_befolkning_age.geometry.area

    # intersect buffered parks and pop
    parks_pop_intersection = gpd.overlay(layer2_buffered, deso_befolkning_age, how='intersection')
    # calculate intersection area
    parks_pop_intersection['intersect_area'] = parks_pop_intersection.geometry.area
    # calculate pop weighted by intersect area
    parks_pop_intersection['pop_weighted'] = (parks_pop_intersection['Totalt'] * (parks_pop_intersection['intersect_area']/ parks_pop_intersection['deso_area']))

    # group parks as usual (by column group)
    pop_weighted_agg = parks_pop_intersection.groupby('group').agg({
        'pop_weighted': 'sum'
    }).reset_index()

    # add to layer2
    layer2 = layer2.merge(pop_weighted_agg, on='group', how='left')

    return layer2
layer2 = THEME_socioeconomic_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_socioeconomic", driver="GPKG", mode="w")
