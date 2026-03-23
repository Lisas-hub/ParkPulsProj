
import geopandas as gpd


#accessibility = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_accessibility")    # with 200 m park buffer
accessibility = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_accessibility_NEW") # with service_area_of_parks

#amenities = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_amenities")            # with 200 m and 20 m buffers
amenities = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_amenities_NEW")         # with service_area_of_parks

environment = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_environment")

food = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_food")                       # this one is old-ish? (not used in regressions?)

#noise_pollution = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_noise_pollution") - added to environment instead

# safety = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_safety")                 # with no buffer
safety = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_safety_NEW")               # with service_area_of_parks

#socioeconomic = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_socioeconomic")    # with 500 m park buffer
socioeconomic = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_socioeconomic_NEW") # with service_area_of_parks

typology = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_typology")               # this one is old-ish? (not used in regressions?)

layers = [accessibility, amenities, environment, food, safety, socioeconomic, typology] # noise pollution borttagen

# set up with geometry from the first layer
base = layers[0].copy()
used_columns = set(base.columns) - {'geometry'}

for gdf in layers[1:]:
    # drop geometry of remaining layers to avoid duplicate columns
    gdf_no_geom = gdf.drop(columns='geometry')

    # drop columns already in base (except 'group')
    new_cols = [col for col in gdf_no_geom.columns if col not in used_columns and col != 'group']

    if new_cols:
        gdf_trimmed = gdf_no_geom[['group'] + new_cols]
        base = base.merge(gdf_trimmed, on='group', how='left')
        used_columns.update(new_cols)

base.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_all", driver="GPKG", mode="w")

# ***** select only columns to show in streamlit ********
#layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_for_streamlit", driver="GPKG", mode="w")
base.to_file("data/VARIABLES_for_streamlit.gpkg", layer="VARIABLES_for_streamlit", driver="GPKG", mode="w")




