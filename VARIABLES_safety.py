
import geopandas as gpd
import numpy as np

input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

# TO DO
# LIGHTING - filter out underground lighting (tunnels)??
# LIGHTING - calculate point density of street lights?
# SAFETY SURVEY - use buffered parks? to catch the area next to parks too?

# lighting
def THEME_lighting_to_layer2(layer2):

    street_lighting = gpd.read_file(f"{input_directory}\\Input\\STHLM_stad\\Belysningsmontage_Punkt.gpkg").to_crs(layer2.crs)
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

    stadsdelsomrade = gpd.read_file(f"{input_directory}\\Output\\Stadsdelsomraden_Stadskartan.gpkg")
    stadsdelsomrade['area'] = stadsdelsomrade.geometry.area
    stadsdelsomrade.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_stadsdelsomrade_area", driver="GPKG", mode="w")

    # ==========================
    # === safety survey data ===
    safety_survey = gpd.read_file(f"{input_directory}\\Input\\Safety\\Survey_CrimeFear_Basomr_2024_08-29\\Survey_CrimeFear_Basomr_2024_08-29.shp").to_crs(layer2.crs)
    # data description:
    # Crimevictim = Share that has been previously victimized the past 12 years (any crime)
    # Unsafe_NBHD = Share that feel unsafe/very unsafe in their neighborhood/residential area
    # Unsafe_Residential = Share that feel unsafe in one or more places in their residential building

    parks_and_safety = gpd.overlay(layer2, safety_survey, how='intersection')
    parks_and_safety['intersect_area'] = parks_and_safety.geometry.area

    parks_and_safety = parks_and_safety.dropna(subset=['CrimVictim', 'UnsafeNBHD']) # dropping nulls because otherwise these become 0 in the weighing section

    parks_and_safety['Unsafe_NBHD_weighted_density'] = parks_and_safety['UnsafeNBHD'] * parks_and_safety['intersect_area']
    parks_and_safety['Crime_victim_weighted_density'] = parks_and_safety['CrimVictim'] * parks_and_safety['intersect_area']

    safety_weighted = parks_and_safety.groupby('group').agg({
        'Unsafe_NBHD_weighted_density': 'sum',
        'Crime_victim_weighted_density': 'sum',
        'intersect_area': 'sum'
    }).reset_index()

    safety_weighted['avg_Unsafe_NBHD_density'] = safety_weighted['Unsafe_NBHD_weighted_density'] / safety_weighted['intersect_area']
    safety_weighted['avg_Crime_victim_density'] = safety_weighted['Crime_victim_weighted_density'] / safety_weighted['intersect_area']

    layer2 = layer2.merge(safety_weighted[['group', 'avg_Unsafe_NBHD_density', 'avg_Crime_victim_density']], on='group', how='left')

    layer2['avg_Unsafe_NBHD_density_LOG'] = np.log(layer2['avg_Unsafe_NBHD_density'])
    layer2['avg_Unsafe_NBHD_density_LOG'] = np.log(layer2['avg_Unsafe_NBHD_density'].replace(0, np.nan)) # to avoid -inf in some rows
    layer2['avg_Crime_victim_density_LOG'] = np.log(layer2['avg_Crime_victim_density'])
    layer2['avg_Crime_victim_density_LOG'] = np.log(layer2['avg_Crime_victim_density'].replace(0, np.nan))

    # =================================
    # === safety - committed crimes ===
    crimes = gpd.read_file(f"{input_directory}\\Input\\Safety\\Basemap_CrimeSocEcon\\Basemap_Lisa.shp").to_crs(layer2.crs)
    # data description:
    # (outdoor) crime data from 2019-2020, socioeconomic data from 2021
    # Total_stre: Total Street crime (all crime columns summarized except Res_crime which is Residential crime)

    crimes['basomrade_area'] = crimes.geometry.area
    crimes['crime_density'] = crimes['Total_stre'] / crimes['basomrade_area']

    parks_and_crimes = gpd.overlay(layer2, crimes, how='intersection')
    parks_and_crimes['intersect_area1'] = parks_and_crimes.geometry.area

    parks_and_crimes['weighted_crime_density'] = parks_and_crimes['crime_density'] * parks_and_crimes['intersect_area1']

    crimes_weighted = parks_and_crimes.groupby('group').agg({
        'weighted_crime_density': 'sum',
        'intersect_area1': 'sum'
    }).reset_index()

    crimes_weighted['avg_crime_density'] = crimes_weighted['weighted_crime_density'] / crimes_weighted['intersect_area1']

    layer2 = layer2.merge(crimes_weighted[['group', 'avg_crime_density']], on='group', how='left')

    layer2['crime_per_hectare'] = layer2['avg_crime_density'] * 10000

    return layer2
layer2 = THEME_safety_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_safety", driver="GPKG", mode="w")


