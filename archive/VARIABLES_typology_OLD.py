
import geopandas as gpd
import pandas as pd

input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

def prepp_layer1():

    # ==== layer1: original park layer ====
    layer1 = gpd.read_file(f"{input_directory}\\Temp\\Sociotop_2024_edited.gpkg", layer="Sociotop_2024_edit3")
    layer1 = layer1.drop(columns=['AREA', 'ANTAL', 'Inventering_2', 'change_made'], errors='ignore')

    # Format the names to remove any capital letters in the middle of a name like Södra Rosendalsparken
    layer1["NAMN"] = layer1["NAMN"].str.title()

    return layer1
layer1 = prepp_layer1()

layer2 = gpd.read_file("../data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

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

    grouped_typology = (
        joined_typology.groupby('index_right')['typology']
            .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
            .reset_index()
    )

    layer2['typology'] = layer2.index.map(grouped_typology.set_index('index_right')['typology']).fillna('None')

    # == total playgrounds including outside of parks ==
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
    return layer2
layer2 = THEME_typology_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_typology", driver="GPKG", mode="w")
