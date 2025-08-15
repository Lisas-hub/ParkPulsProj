
import geopandas as gpd


#accessibility = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_accessibility", driver="GPKG", mode="w")
amenities = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_amenities", driver="GPKG", mode="w")
environment = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_environment", driver="GPKG", mode="w")
food = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_food", driver="GPKG", mode="w")
noise_pollution = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_noise_pollution", driver="GPKG", mode="w")
safety = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_safety", driver="GPKG", mode="w")
socioeconomic = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_socioeconomic", driver="GPKG", mode="w")
typology = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_typology", driver="GPKG", mode="w")

layers = [amenities, environment, food, noise_pollution, safety, socioeconomic, typology] # *** add accessibility ***

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




