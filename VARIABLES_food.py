
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

    # *** TEMP FILE - remove when finished ***
    largest_overlap.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_stadsdelar_test1", driver="GPKG", mode="w")

    layer2 = layer2.merge(
        largest_overlap[["NAMN_combined", "NAMN"]],
        on="NAMN_combined",
        how="left"
    )

    layer2 = layer2.rename(columns={"NAMN": "stadsdelar"})

    return layer2
layer2 = stadsdelar_to_layer2(layer2)



# === THEME ===

def THEME_typology_to_layer2(layer2):

    # === bars / restaurants / etc ===
    cafe_pts = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_cafe_pts.gpkg").to_crs(
        layer2.crs)
    cafe_area = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_cafe.gpkg").to_crs(
        layer2.crs)
    restaurant_pts = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_restaurant_pts.gpkg").to_crs(layer2.crs)
    restaurant_area = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_restaurant.gpkg").to_crs(layer2.crs)
    ice_cream_pts = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_ice_cream_pts.gpkg").to_crs(layer2.crs)
    ice_cream_area = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_ice_cream.gpkg").to_crs(
        layer2.crs)

    # Add food establishment labels
    for gdf in [cafe_pts, cafe_area]: gdf['amenity_food'] = 'Cafe'
    for gdf in [restaurant_pts, restaurant_area]: gdf['amenity_food'] = 'Restaurant'
    for gdf in [ice_cream_pts, ice_cream_area]: gdf['amenity_food'] = 'Ice cream shop'

    # Combine all geometry versions into one GeoDataFrame
    cafe_all = gpd.GeoDataFrame(pd.concat([cafe_pts, cafe_area], ignore_index=True), crs=layer2.crs)
    restaurant_all = gpd.GeoDataFrame(pd.concat([restaurant_pts, restaurant_area], ignore_index=True), crs=layer2.crs)
    ice_cream_all = gpd.GeoDataFrame(pd.concat([ice_cream_pts, ice_cream_area], ignore_index=True), crs=layer2.crs)

    # Combine all amenity_food into one GeoDataFrame
    food_establishments = gpd.GeoDataFrame(
        pd.concat([cafe_all, restaurant_all, ice_cream_all], ignore_index=True),
        crs=layer2.crs
    )

    # *** temporary file - remove when finished ***
    food_establishments.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_food_establishments", driver="GPKG", mode="w")

    # buffer the park polygons
    layer2_buffered = layer2.copy()
    layer2_buffered['geometry'] = layer2_buffered.geometry.buffer(200)

    layer2_buffered.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_food_buffer", driver="GPKG", mode="w")

    # join
    joined_amenity_food = gpd.sjoin(
        food_establishments[['geometry', 'amenity_food']],
        layer2_buffered[['geometry']],
        how='inner',
        predicate='intersects'
    )

    # Group by polygon and list food establishment type type
    grouped_amenity_food = (
        joined_amenity_food.groupby('index_right')['amenity_food']
            .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
            .reset_index()
    )

    # == food establishment count ==

    # Count the number of food establishments per polygon
    food_counts = (
        joined_amenity_food.groupby('index_right')
            .size()
            .reset_index(name='total_food_establishments')
    )

    # Map the counts to layer2
    layer2['total_food_establishments'] = layer2.index.map(
        food_counts.set_index('index_right')['total_food_establishments']
    ).fillna(0).astype(int)


    layer2['variable_amenity_food'] = layer2.index.map(
        grouped_amenity_food.set_index('index_right')['amenity_food']
    ).fillna('None')



    return layer2
layer2 = THEME_typology_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_food", driver="GPKG", mode="w")
















