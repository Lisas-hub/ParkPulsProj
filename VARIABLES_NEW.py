
import geopandas as gpd
import pandas as pd
from shapely.strtree import STRtree
import networkx as nx
from shapely.geometry import Polygon, MultiPolygon
#import fiona


# TO DO LIST
# clean up columns like NAME_combined? shorten the list and fix special characters (like Ö in the middle of some names)
# add more amenities
# LIGHTING - filter out underground lighting (tunnels)??
# LIGHTING - calculate point density of street lights?
# ACCESSIBILITY - fix input road layers so that fill in areas between roads that shouldn't be filled in are removed?
# ACCESSIBILITY - fix dissolved so that unconnected polygons are not being removed? or keep it that way?
# AMENITIES - toilets are not within any park so change format of this variable to within XXX m
# TYPOLOGY - add park to the list, so you can see if a polygon only has play ground for example - good for the infograph stats

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

    largest_overlap = intersection_stadsdelar.sort_values("overlap_area", ascending=False).drop_duplicates(
        "NAMN_combined")

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

# ============== THEMES ================

# typology
def THEME_typology_to_layer2(layer2):

    # TYPOLOGY (from sociotop category TYP)
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
    dog_park = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Hundrastgard_Yta.gpkg",
                             layer="Hundrastgard_Yta").to_crs(layer2.crs)
    outdoor_gym = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\leisure_fitness_station.gpkg").to_crs(layer2.crs)
    OSM_play_ground = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\leisure_playground.gpkg").to_crs(layer2.crs)
    OSM_play_ground_pts = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\leisure_playground_pts.gpkg").to_crs(layer2.crs)
    play_ground = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'lek'].copy()
    # *** ADD OSM SCHOOLS OR OTHER? NOT ALL SCHOOLS ARE MAPPED IN _edit3 ***
    school_yard = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'skola/fritid'].copy()
    sports_field = layer1[layer1['TYP'].str.strip().str.lower().isin(['ip', 'bp', 'bollplan', 'bollplan/lekp'])].copy()
    skate_park = layer1[layer1['TYP'].str.strip().str.lower().isin(['skate', 'skatepark'])].copy()
    garden = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'odling'].copy()

    # Add typology labels
    dog_park['typology'] = 'Dog park'
    outdoor_gym['typology'] = 'Outdoor gym'
    for gdf in [OSM_play_ground, OSM_play_ground_pts, play_ground]: gdf['typology'] = 'Play ground'
    school_yard['typology'] = 'School yard'
    sports_field['typology'] = 'Sports field'
    skate_park['typology'] = 'Skate park'
    garden['typology'] = 'Garden'

    # Combine all geometry versions into one GeoDataFrame
    play_ground_all = gpd.GeoDataFrame(pd.concat([OSM_play_ground, OSM_play_ground_pts], ignore_index=True),
                                       crs=layer2.crs)

    # Combine all typologies into one GeoDataFrame
    typology_all = gpd.GeoDataFrame(
        pd.concat([dog_park, outdoor_gym, play_ground_all, school_yard, sports_field, skate_park, garden],
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

    # AMENITIES
    toilets = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Toalett_Punkt.gpkg",
                            layer="Toalett_Punkt").to_crs(layer2.crs)
    benches_pts = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_bench_pts.gpkg").to_crs(
        layer2.crs)
    benches_line = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_bench_line.gpkg").to_crs(
        layer2.crs)
    benches_area = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_bench.gpkg").to_crs(
        layer2.crs)
    bbq_pts = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_bbq_pts.gpkg").to_crs(
        layer2.crs)
    bbq_area = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_bbq.gpkg").to_crs(layer2.crs)
    drinking_fountain = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Dricksvattenfont%C3%A4ner\Dricksvattenfontäner.shp").to_crs(
        layer2.crs)  # not so many in stockholm at all, let alone in parks...

    # Add amenity labels
    toilets['amenity'] = 'WC'
    for gdf in [benches_pts, benches_line, benches_area]: gdf['amenity'] = 'bench'
    for gdf in [bbq_pts, bbq_area]: gdf['amenity'] = 'BBQ area'
    toilets['amenity'] = 'drinking fountain'
    # *** ADD PICKNICK TABLES ETC ***

    # Combine all geometry versions into one GeoDataFrame
    benches_all = gpd.GeoDataFrame(pd.concat([benches_pts, benches_line, benches_area], ignore_index=True),
                                   crs=layer2.crs)
    bbq_all = gpd.GeoDataFrame(pd.concat([bbq_pts, bbq_area], ignore_index=True), crs=layer2.crs)

    # Combine all amenities into one GeoDataFrame
    amenities_all = gpd.GeoDataFrame(pd.concat([toilets, benches_all, bbq_all, drinking_fountain], ignore_index=True),
                                     crs=layer2.crs)

    # Spatial join amenities with dissolved polygons
    joined_amenities = gpd.sjoin(
        amenities_all[['geometry', 'amenity']],
        layer2[['geometry']],
        how='inner',
        predicate='intersects'
    )

    # Group by polygon and collect unique amenity names
    grouped_amenities = (
        joined_amenities.groupby('index_right')['amenity']
            .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
            .reset_index()
    )

    # Map to layer2
    layer2['amenities'] = layer2.index.map(grouped_amenities.set_index('index_right')['amenity']).fillna('None')

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

    # buffer the park polygons
    layer2_buffered = layer2.copy()
    layer2_buffered['geometry'] = layer2_buffered.geometry.buffer(200)

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

    layer2['variable_amenity_food'] = layer2.index.map(
        grouped_amenity_food.set_index('index_right')['amenity_food']
    ).fillna('None')



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

    return layer2
layer2 = THEME_typology_to_layer2(layer2)

# environment
def THEME_environment_to_layer2(layer2):

    # == environment ==

    # BIOTOPES
    layer_biotop = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Biotopkartan_2019\Biotopkartan_2019_Huvudklass.gpkg",
        layer="Huvudklass").to_crs(
        "EPSG:3006")  # some warning about gpkg version for this file + warning of timestamp column

    joined_biotop = gpd.sjoin(
        layer_biotop[['geometry', 'h_klass']],
        layer2[['geometry']],
        how='left',
        predicate='intersects'
    )

    grouped_biotop = (
        joined_biotop.groupby("index_right")["h_klass"]
            .apply(lambda x: ", ".join(sorted(
            set(x.dropna()))))  # set(x) removes duplicate names, sorted() gives consistent order, dropna() prevents "nan" strings in the result
            .reset_index()
    )

    # Map to layer2
    layer2["BIOTOP_combined"] = layer2.index.map(grouped_biotop.set_index("index_right")["h_klass"])

    return layer2
layer2 = THEME_environment_to_layer2(layer2)

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
        r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Stadskarta_Stockholm_SHP\Vaegutbredning_area.shp")
    gdf_road2 = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Stadskarta_Stockholm_SHP\Trafik_area.shp")

    # reproject
    target_crs = "EPSG:3006"
    gdf_road1 = gdf_road1.to_crs(target_crs)
    gdf_road2 = gdf_road2.to_crs(target_crs)

    # merge
    merged = gpd.GeoDataFrame(pd.concat([gdf_road1, gdf_road2], ignore_index=True), crs=target_crs)

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
    dissolved.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_accessibility_dissolve_step1", driver="GPKG",
                      mode="w")  # *** Enstaka polygoner är borttagna i detta lager, behåll det så eller inte? ***

    # Save
    dissolved.to_file("data/VARIABLES_NEW.gpkg", layer="accessibility_roads", driver="GPKG",
                      mode="w")  # mode="w" (write) replaces the layer in the GeoPackage cleanly, better to use than OVERWRITE='YES'

    return layer2
layer2 = THEME_accessibility_to_layer2(layer2)

# safety
def THEME_safety_to_layer2(layer2):

    # == safety ==

    # ==== Street lighting ====

    street_lighting = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Belysningsmontage_Punkt.gpkg").to_crs(layer2.crs)
    layer2["temp_ID"] = layer2.index  # create a column to be used in the merge later

    # buffer the lighting points
    street_lighting['geometry'] = street_lighting['geometry'].buffer(30)

    # *** temporary file - can be removed ***
    street_lighting.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_street_lighting_buffer", driver="GPKG", mode="w")

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
    layer2['lighting_coverage'] = (layer2['intersect_area'] / layer2[
        'area']) # OBS! some polygons have lighting coverage 100,00000000000003 but that slight excess is some type of discrepance caused by python

    layer2['lighting_coverage2'] = (layer2['intersect_area'] / layer2[
        'area'])*100

    # Drop irrelevant columns
    layer2 = layer2.drop(columns=['area', 'intersect_area', 'temp_ID'])

    return layer2
layer2 = THEME_safety_to_layer2(layer2)

# socioeconomic
def THEME_socioeconomic_to_layer2(layer2):

    # == socioeconomic ==

    # start here
    return layer2
layer2 = THEME_socioeconomic_to_layer2(layer2)

# park maintenance
def THEME_park_maintenance_to_layer2(layer2):

    # start here

    # papperskorgar = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Skrapkorg_Punkt.gpkg", layer="Skrapkorg_Punkt")

    return layer2
layer2 = THEME_park_maintenance_to_layer2(layer2)





# ===== SAVE =====

# Check gpkg layers
#fiona.listlayers("VARIABLES_NEW.gpkg")

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_NEW", driver="GPKG", mode="w")


# ==== OTHER STATS ====
def OTHER_STATS_park_coverage():

    # park coverage in Stockholm
    municipality = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\Kommun_Stadskartan.gpkg").to_crs(layer2.crs)

    # union of parks and municipality
    park_coverage = gpd.overlay(municipality, layer2, how='union') # OBS! mismatch between parks and municipality boundary, small pieces of some parks are outside of the boundary and got group_temp null

    # remove polygons outside the municipality boundary
    park_coverage = gpd.clip(park_coverage, municipality)

    # drop all unnecessary columns by selecting only relevant columns
    park_coverage = park_coverage[["geometry"]]

    # calculate area
    park_coverage ['area'] = park_coverage.geometry.area

    park_coverage['group'] = 0  # default value
    park_coverage.loc[park_coverage['area'] > 100000000, 'group'] = 1 # assign 1 to the largest polygon, aka the one that is not a polygon

    # dissolve all polygons from layer2 into one single polygon
    #park_coverage = park_coverage.dissolve(by="group", as_index=False) # *** fix so that all group = 0 are not lost in this step

    return park_coverage
park_coverage = OTHER_STATS_park_coverage()

park_coverage.to_file("data/VARIABLES_NEW.gpkg", layer="park_coverage", driver="GPKG", mode="w")