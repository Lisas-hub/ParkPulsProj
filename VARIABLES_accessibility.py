
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
# fix input road layers so that fill in areas between roads that shouldn't be filled in are removed?
# fix dissolved so that unconnected polygons are not being removed? or keep it that way?

# accessibility
def THEME_accessibility_to_layer2(layer2):

    # == accessibility ==

    # public transport
    bus_stops = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\highway_bus_stop_pts.gpkg").to_crs(
        layer2.crs)  # no need to add bus_stations (only 2, one overlaps w bus_stops and the other is not in STHLM) or bus_stations_pts (6/9 by a sea port and 3/9 by cityterminal/liljeholmen, these are transfer bus stations)
    subway_entrances = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\railway_subway_entrance.gpkg").to_crs(
        layer2.crs)  # no need to add railway_subway.gpkg (it's a line layer)

    bus_stops['transport_type'] = 'Bus'
    subway_entrances['transport_type'] = 'Subway'

    # Combine all transportation into one GeoDataFrame
    transport_points = gpd.GeoDataFrame(
        pd.concat([bus_stops, subway_entrances], ignore_index=True),
        crs=layer2.crs
    )

    # buffer the park polygons
    layer2_buffered = layer2.copy()
    layer2_buffered['geometry'] = layer2_buffered.geometry.buffer(200)

    # join
    joined_transport = gpd.sjoin(
        transport_points[['geometry', 'transport_type']],
        layer2_buffered[['geometry']],
        how='inner',
        predicate='intersects'
    )

    # Group by polygon and list transport type
    grouped_transport = (
        joined_transport.groupby('index_right')['transport_type']
            .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
            .reset_index()
    )

    layer2['variable_public_transport'] = layer2.index.map(
        grouped_transport.set_index('index_right')['transport_type']
    ).fillna('None')

    # walking distance by road
    gdf_road1 = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Stadskarta_Stockholm_SHP\Vaegutbredning_area.shp").to_crs(layer2.crs)
    gdf_road2 = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Stadskarta_Stockholm_SHP\Trafik_area.shp").to_crs(layer2.crs)

    # roads from sthlm stad
    #roads = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_roads1")

    # merge
    merged = gpd.GeoDataFrame(pd.concat([gdf_road1, gdf_road2], ignore_index=True), crs=layer2.crs)

    # fix geometry
    merged['geometry'] = merged['geometry'].buffer(0)

    # remove tiny slivers between polygons that should be touching
    merged['geometry'] = merged['geometry'].buffer(0.1)

    # dissolve (group intersecting polygons first, then dissolve)
    from shapely.strtree import STRtree
    import networkx as nx

    geoms = list(merged.geometry)
    tree = STRtree(geoms)

    edges = []
    for i, geom in enumerate(geoms):
        for j in tree.query(geom):
            if i < j and geom.intersects(geoms[j]):
                edges.append((i, j))

    G = nx.Graph()
    G.add_edges_from(edges)
    components = list(nx.connected_components(G))

    # Assign group ID to each connected set
    group_map = {}
    for group_id, component in enumerate(components, 1):
        for idx in component:
            group_map[idx] = group_id

    merged["group"] = merged.index.map(group_map)

    # Dissolve geometries by group
    dissolved = merged.dissolve(by="group", as_index=False)

    # Reduce buffer to go back to original size again (after fix slivers earlier)
    dissolved['geometry'] = dissolved['geometry'].buffer(-0.1)

    # **** remove this step after checking ****
    dissolved.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_roads2", driver="GPKG",
                      mode="w")  # *** Enstaka polygoner är borttagna i detta lager, behåll det så eller inte? ***

    # Save
    dissolved.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_roads3", driver="GPKG", mode="w")

    return layer2
layer2 = THEME_accessibility_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_accessibility", driver="GPKG", mode="w")



# roads from OSM *** bättre än sthlm stads? i osm finns väl stigar och sånt ju?? vilket ju är toppen om man ska kolla på gångavstånd
