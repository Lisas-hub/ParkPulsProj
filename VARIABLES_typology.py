
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

# typology
def THEME_typology_to_layer2(layer2):

    # TYPOLOGY (from sociotop category TYP and OSM)
    joined_typ = gpd.sjoin(
        layer1[['geometry', 'TYP']],
        layer2[['geometry']],
        how='left',
        predicate='intersects'
    )

    grouped_typ = (
        joined_typ.groupby("index_right")["TYP"]
            .apply(lambda x: ", ".join(sorted(
            set(x.dropna()))))  # set(x) removes duplicate names, sorted() gives consistent order, dropna() prevents "nan" strings in the result
            .reset_index()
    )

    layer2["TYP_combined"] = layer2.index.map(grouped_typ.set_index("index_right")["TYP"])

    # TYPOLOGY (from OSM layers etc)
    # Import
    dog_park = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Hundrastgard_Yta.gpkg", layer="Hundrastgard_Yta").to_crs(layer2.crs)
    outdoor_gym = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\leisure_fitness_station.gpkg").to_crs(layer2.crs)
    OSM_play_ground = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\leisure_playground.gpkg").to_crs(layer2.crs)
    OSM_play_ground_pts = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\leisure_playground_pts.gpkg").to_crs(layer2.crs)
    play_ground = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'lek'].copy()
    park = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'park'].copy()
    # *** ADD OSM SCHOOLS OR OTHER? NOT ALL SCHOOLS ARE MAPPED IN _edit3 ***
    school_yard = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'skola/fritid'].copy()
    sports_field = layer1[layer1['TYP'].str.strip().str.lower().isin(['ip', 'bp', 'bollplan', 'bollplan/lekp'])].copy()
    skate_park = layer1[layer1['TYP'].str.strip().str.lower().isin(['skate', 'skatepark'])].copy()
    garden = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'odling'].copy()
    religious = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'kyrk-relaterat'].copy()

    # Add typology labels
    park['typology'] = 'Park'
    dog_park['typology'] = 'Dog park'
    outdoor_gym['typology'] = 'Outdoor gym'
    for gdf in [OSM_play_ground, OSM_play_ground_pts, play_ground]: gdf['typology'] = 'Play ground'
    school_yard['typology'] = 'School yard'
    sports_field['typology'] = 'Sports field'
    skate_park['typology'] = 'Skate park'
    garden['typology'] = 'Garden'
    religious['typology'] = 'Religious'

    # Combine all geometry versions into one GeoDataFrame
    play_ground_all = gpd.GeoDataFrame(pd.concat([OSM_play_ground, OSM_play_ground_pts, play_ground], ignore_index=True),
                                       crs=layer2.crs)

    # Combine all typologies into one GeoDataFrame
    typology_all = gpd.GeoDataFrame(
        pd.concat([park, dog_park, outdoor_gym, play_ground_all, school_yard, sports_field, skate_park, garden, religious],
                  ignore_index=True), crs=layer2.crs)

    # Spatial join with dissolved polygons
    joined_typology = gpd.sjoin(
        typology_all[['geometry', 'typology']],
        layer2[['geometry']],
        how='inner',
        predicate='intersects'
    )

    # Group by polygon and collect unique names
    grouped_typology = (
        joined_typology.groupby('index_right')['typology']
            .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
            .reset_index()
    )

    layer2['typology'] = layer2.index.map(grouped_typology.set_index('index_right')['typology']).fillna('None')

    return layer2
layer2 = THEME_typology_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_typology", driver="GPKG", mode="w")
