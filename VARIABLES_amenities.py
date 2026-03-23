
import geopandas as gpd
import pandas as pd


# *** THIS SCRIPT NOW CONTAINS 'AMENITIES' AND WHAT WAS PREVIOUSLY 'FOOD' AND 'TYPOLOGY' ***
# and amenity_diversity is based on all 3 which includes: Dog park, Outdoor gym, Play ground, School yard, Sports field,
# Skate park, Garden, Religious (like a church etc), Food establishment (incl café, restaurant, ice cream shop), Toilet,
# Bench, BBQ, Drinking fountain, Waste paper bin, Picnic table


input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

# ========================================================
# AMENITIES, previously "TYPOLOGY" (from sociotop and OSM)

def prepp_layer1():
    layer1 = gpd.read_file(
        f"{input_directory}\\Temp\\Sociotop_2024_edited.gpkg",
        layer="Sociotop_2024_edit3"
    )
    layer1 = layer1.drop(
        columns=['AREA', 'ANTAL', 'Inventering_2', 'change_made'],
        errors='ignore'
    )

    layer1["NAMN"] = layer1["NAMN"].str.title()
    return layer1
layer1 = prepp_layer1()

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
    dog_park = gpd.read_file(f"{input_directory}\\Input\\STHLM_stad\\Hundrastgard_Yta.gpkg", layer="Hundrastgard_Yta").to_crs(layer2.crs)
    outdoor_gym = gpd.read_file(
        f"{input_directory}\\Input\\OpenStreetMap\\leisure_fitness_station.gpkg").to_crs(layer2.crs)
    OSM_play_ground = gpd.read_file(
        f"{input_directory}\\Input\\OpenStreetMap\\leisure_playground.gpkg").to_crs(layer2.crs)
    OSM_play_ground_pts = gpd.read_file(
        f"{input_directory}\\Input\\OpenStreetMap\\leisure_playground_pts.gpkg").to_crs(layer2.crs)
    play_ground = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'lek'].copy()
    park = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'park'].copy()
    # *** ADD OSM SCHOOLS OR OTHER? NOT ALL SCHOOLS ARE MAPPED IN _edit3 ***
    school_yard = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'skola/fritid'].copy()
    sports_field = layer1[layer1['TYP'].str.strip().str.lower().isin(['ip', 'bp', 'bollplan', 'bollplan/lekp'])].copy()
    skate_park = layer1[layer1['TYP'].str.strip().str.lower().isin(['skate', 'skatepark'])].copy()
    garden = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'odling'].copy()
    religious = layer1[layer1['TYPE_2'].str.strip().str.lower() == 'kyrk-relaterat'].copy()

    park['typology'] = 'Park'
    dog_park['typology'] = 'Dog park'
    outdoor_gym['typology'] = 'Outdoor gym'
    for gdf in [OSM_play_ground, OSM_play_ground_pts, play_ground]: gdf['typology'] = 'Play ground'
    school_yard['typology'] = 'School yard'
    sports_field['typology'] = 'Sports field'
    skate_park['typology'] = 'Skate park'
    garden['typology'] = 'Garden'
    religious['typology'] = 'Religious'

    play_ground_all = gpd.GeoDataFrame(pd.concat([OSM_play_ground, OSM_play_ground_pts, play_ground], ignore_index=True),
                                       crs=layer2.crs)

    typology_all = gpd.GeoDataFrame(
        pd.concat([park, dog_park, outdoor_gym, play_ground_all, school_yard, sports_field, skate_park, garden, religious],
                  ignore_index=True), crs=layer2.crs)

    joined_typology = gpd.sjoin(
        typology_all[['geometry', 'typology']],
        layer2[['geometry']],
        how='inner',
        predicate='intersects'
    )

    # === typologies as amenities (for amenity diversity) ===
    typology_amenities = joined_typology[['index_right', 'typology']].copy()
    typology_amenities = typology_amenities.rename(columns={'typology': 'amenity'})
    # Exclude "Park" from amenity diversity
    typology_amenities = typology_amenities[typology_amenities['amenity'] != 'Park']

    grouped_typology = (
        joined_typology.groupby('index_right')['typology']
            .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
            .reset_index()
    )

    layer2['typology'] = layer2.index.map(grouped_typology.set_index('index_right')['typology']).fillna('None')

    # == total playgrounds per stadsdelsområde including outside of parks ==
    stadsdelsomraden = gpd.read_file(f"{input_directory}\\Output\\Stadsdelsomraden_Stadskartan.gpkg").to_crs(layer2.crs)
    # drop all columns except stadsdelsområden
    columns_to_keep_stadsdelsomraden = ["geometry", "Omrade"]
    stadsdelsomraden = stadsdelsomraden[columns_to_keep_stadsdelsomraden]

    playgrounds_per_stadsdelsomrade = gpd.sjoin(
        play_ground_all[['geometry']],
        stadsdelsomraden[['geometry', 'Omrade']],
        how='inner',
        predicate='intersects'
    )

    playground_counts = (
        playgrounds_per_stadsdelsomrade
            .groupby('Omrade')
            .size()
            .reset_index(name='playground_count')
    )

    stadsdelsomraden = stadsdelsomraden.merge(playground_counts, on='Omrade', how='left')
    stadsdelsomraden['playground_count'] = stadsdelsomraden['playground_count'].fillna(0).astype(int)

    stadsdelsomraden.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_typology_per_stadsdelsomrade", driver="GPKG", mode="w")

    # == density of typologies per park ==
    typologies = {
        "park": park,
        "dog_park": dog_park,
        "outdoor_gym": outdoor_gym,
        "play_ground": play_ground_all,
        "school_yard": school_yard,
        "sports_field": sports_field,
        "skate_park": skate_park,
        "garden": garden,
        "religious": religious,
    }

    for key in typologies:
        typologies[key] = typologies[key].to_crs(layer2.crs)

    # count
    for name, typology_all in typologies.items():
        joined = gpd.sjoin(typology_all, layer2, how="inner", predicate="intersects")
        counts = joined.groupby("group").size().rename(f"{name}_count")
        layer2 = layer2.join(counts, on="group")
    layer2.fillna({f"{name}_count": 0 for name in typologies}, inplace=True)

    # count per hectare
    for name in typologies:
        count_col = f"{name}_count"
        density_col = f"{name}_per_ha"
        layer2[density_col] = layer2[count_col] / (layer2["park_area"] / 10000)
        layer2[density_col] = layer2[density_col].fillna(0)

    return layer2, typology_amenities
layer2, typology_amenities = THEME_typology_to_layer2(layer2)

# ============================
# AMENITIES, previously "FOOD"

def THEME_food_to_layer2(layer2):

    # === bars / restaurants / etc ===
    cafe_pts = gpd.read_file(f"{input_directory}\\Input\\OpenStreetMap\\amenity_cafe_pts.gpkg").to_crs(
        layer2.crs)
    cafe_area = gpd.read_file(f"{input_directory}\\Input\\OpenStreetMap\\amenity_cafe.gpkg").to_crs(
        layer2.crs)
    restaurant_pts = gpd.read_file(
        f"{input_directory}\\Input\\OpenStreetMap\\amenity_restaurant_pts.gpkg").to_crs(layer2.crs)
    restaurant_area = gpd.read_file(
        f"{input_directory}\\Input\\OpenStreetMap\\amenity_restaurant.gpkg").to_crs(layer2.crs)
    ice_cream_pts = gpd.read_file(
        f"{input_directory}\\Input\\OpenStreetMap\\amenity_ice_cream_pts.gpkg").to_crs(layer2.crs)
    ice_cream_area = gpd.read_file(f"{input_directory}\\Input\\OpenStreetMap\\amenity_ice_cream.gpkg").to_crs(
        layer2.crs)

    # convert areas to centroids
    cafe_area['geometry'] = ice_cream_area.geometry.centroid
    restaurant_area['geometry'] = ice_cream_area.geometry.centroid
    ice_cream_area['geometry'] = ice_cream_area.geometry.centroid

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

    # *** TEMP FILE - can be removed ***
    layer2_buffered.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_park_buffer200", driver="GPKG", mode="w")

    ##################
    # use service area of parks instead of buffered parks
    service_area_of_parks = gpd.read_file(r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\network_analysis\service_area_of_parks.gpkg")
    ##################

    # join
    joined_amenity_food = gpd.sjoin(
        food_establishments[['geometry', 'amenity_food']],
        #layer2_buffered[['geometry']],
        service_area_of_parks[['geometry']],
        how='inner',
        predicate='intersects'
    )

    # === food as a single amenity category ===
    food_amenities = joined_amenity_food[['index_right']].copy()
    food_amenities['amenity'] = 'Food'

    # group by polygon and list food establishment type
    grouped_amenity_food = (
        joined_amenity_food.groupby('index_right')['amenity_food']
            .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
            .reset_index()
    )

    # == food establishment count ==

    # Count the number of food establishments per park polygon
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

    # == extracting all ice cream places within park buffer ==
    layer2_buffer_dissolve = layer2_buffered.dissolve(as_index=False)

    # *** TEMP FILE - can be removed ***
    ice_cream_all.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_ice_cream_all", driver="GPKG", mode="w")

    ice_cream_within_buffer_join = gpd.sjoin(
        ice_cream_all[['geometry', 'amenity']],
        #layer2_buffer_dissolve,
        service_area_of_parks[['geometry']],
        how='inner',
        predicate='within'
    ) # the output (with buffered parks) results in 42 pts, 1 will be dropped later because here it is within the buffer layer but not within stadsdelsområden

    FINAL_ice_cream_pts = ice_cream_within_buffer_join
    FINAL_ice_cream_pts.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_ice_cream_within_buffer_pts", driver="GPKG", mode="w")

    # == ice cream shops per stadsdelsområde ==
    stadsdelsomraden = gpd.read_file(f"{input_directory}\\Output\\Stadsdelsomraden_Stadskartan.gpkg").to_crs(layer2.crs)

    # drop all columns except stadsdelsområden
    columns_to_keep_stadsdelsomraden = ["geometry", "Omrade"]
    stadsdelsomraden = stadsdelsomraden[columns_to_keep_stadsdelsomraden]

    ice_cream_stadsdelsomrade_join = gpd.sjoin(
        FINAL_ice_cream_pts[['geometry', 'amenity']],
        stadsdelsomraden,
        how='left',
        predicate='intersects'
    )

    # count number of ice cream shops per stadsdelsområde
    ice_cream_counts = (
        ice_cream_stadsdelsomrade_join.groupby('index_right')
            .size()
    )
    # add count column to stadsdelområden
    stadsdelsomraden["total_ice_cream_shops"] = stadsdelsomraden.index.map(ice_cream_counts).fillna(0).astype(int)

    stadsdelsomraden.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_ice_cream_shops_per_stadsdelsomrade", driver="GPKG", mode="w")

    food_amenities = joined_amenity_food[['index_right']].copy()
    food_amenities['amenity'] = 'Food'

    return layer2, food_amenities
layer2, food_amenities = THEME_food_to_layer2(layer2)

# ========================================
# AMENITIES (from OSM and Stockholms stad)

def THEME_amenities_to_layer2(layer2, typolgy_amenities, food_amenities):

    toilet = gpd.read_file(f"{input_directory}\\Input\\STHLM_stad\\Toalett_Punkt.gpkg",
                            layer="Toalett_Punkt").to_crs(layer2.crs)
    bench_pts = gpd.read_file(f"{input_directory}\\Input\\OpenStreetMap\\amenity_bench_pts.gpkg").to_crs(
        layer2.crs)
    bench_line = gpd.read_file(f"{input_directory}\\Input\\OpenStreetMap\\amenity_bench_line.gpkg").to_crs(
        layer2.crs)
    bench_area = gpd.read_file(f"{input_directory}\\Input\\OpenStreetMap\\amenity_bench.gpkg").to_crs(
        layer2.crs)
    bbq_pts = gpd.read_file(f"{input_directory}\\Input\\OpenStreetMap\\amenity_bbq_pts.gpkg").to_crs(
        layer2.crs)
    bbq_area = gpd.read_file(f"{input_directory}\\Input\\OpenStreetMap\\amenity_bbq.gpkg").to_crs(layer2.crs)
    drinking_fountain = gpd.read_file(
        f"{input_directory}\\Input\\STHLM_stad\\Dricksvattenfont%C3%A4ner\\Dricksvattenfontäner.shp").to_crs(
        layer2.crs)  # not so many in stockholm at all, let alone in parks...
    waste_paper_bin = gpd.read_file(
        f"{input_directory}\\Input\\STHLM_stad\\Skrapkorg_Punkt.gpkg").to_crs(layer2.crs)
    picnic_table = gpd.read_file(f"{input_directory}\\Input\\OpenStreetMap\\leisure_picnic_table_pts.gpkg").to_crs(layer2.crs)

    toilet['amenity'] = 'WC'
    for gdf in [bench_pts, bench_line, bench_area]: gdf['amenity'] = 'bench'
    for gdf in [bbq_pts, bbq_area]: gdf['amenity'] = 'BBQ area'
    drinking_fountain['amenity'] = 'drinking fountain'
    waste_paper_bin['amenity'] = 'waste paper bin'
    picnic_table['amenity'] = 'picnic table'

    bench_all = gpd.GeoDataFrame(pd.concat([bench_pts, bench_line, bench_area], ignore_index=True),crs=layer2.crs)
    bbq_all = gpd.GeoDataFrame(pd.concat([bbq_pts, bbq_area], ignore_index=True), crs=layer2.crs)
    amenities_all = gpd.GeoDataFrame(pd.concat([bench_all, bbq_all, drinking_fountain, waste_paper_bin, picnic_table], ignore_index=True), crs=layer2.crs)
    # toilet not in ^ameneties_all^, using layer2_buffered for toilets below

    joined_amenities = gpd.sjoin(
        amenities_all[['geometry', 'amenity']],
        layer2[['geometry']],
        how='inner',
        predicate='intersects'
    )

    # === buffered WC ===

    #layer2_buffered = layer2.copy()
    #layer2_buffered['geometry'] = layer2_buffered.geometry.buffer(50)

    ##################
    # use service area of parks instead of buffered parks
    service_area_of_parks = gpd.read_file(
        r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\network_analysis\service_area_of_parks.gpkg")
    ##################

    joined_buffered_WC = gpd.sjoin(
        toilet[['geometry', 'amenity']],
        #layer2_buffered[['geometry']],
        service_area_of_parks[['geometry']],
        how='inner',
        predicate='intersects'
    )
    # ===================

    # combine toilets with other amenities
    combined_amenities = pd.concat([joined_amenities, joined_buffered_WC], ignore_index=True)

    # === combine ALL amenity-like things ===
    all_amenities_for_diversity = pd.concat(
        [
            combined_amenities[['index_right', 'amenity']],
            typology_amenities,
            food_amenities
        ],
        ignore_index=True
    )

    amenity_diversity = (
        all_amenities_for_diversity
            .groupby('index_right')['amenity']
            .nunique()
            .rename('amenity_diversity')
    )

    layer2 = layer2.join(amenity_diversity, how='left')
    layer2['amenity_diversity'] = layer2['amenity_diversity'].fillna(0)

    grouped_amenities = (
        combined_amenities.groupby('index_right')['amenity']
            .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
            .reset_index()
    )

    layer2['amenities'] = layer2.index.map(grouped_amenities.set_index('index_right')['amenity']).fillna('None')

    # == density of amenities per park ==
    amenities = {
        "toilet": toilet,
        "bench": bench_all,
        "bbq": bbq_all,
        "drinking_fountain": drinking_fountain,
        "waste_paper_bin": waste_paper_bin,
        "picnic_table": picnic_table
    }

    for key in amenities:
        amenities[key] = amenities[key].to_crs(layer2.crs)

    # count
    for name, amenities_all in amenities.items():
        joined = gpd.sjoin(amenities_all, layer2, how="inner", predicate="intersects")
        counts = joined.groupby("group").size().rename(f"{name}_count")
        layer2 = layer2.join(counts, on="group")
    layer2.fillna({f"{name}_count": 0 for name in amenities}, inplace=True)

    # count per hectare
    for name in amenities:
        count_col = f"{name}_count"
        density_col = f"{name}_per_ha"
        layer2[density_col] = layer2[count_col] / (layer2["park_area"] / 10000)
        layer2[density_col] = layer2[density_col].fillna(0)

    return layer2
layer2 = THEME_amenities_to_layer2(layer2, typology_amenities, food_amenities)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_amenities_NEW", driver="GPKG", mode="w")
