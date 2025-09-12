
import geopandas as gpd


accessibility = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_accessibility")
amenities = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_amenities")
environment = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_environment")
food = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_food")
#noise_pollution = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_noise_pollution") - added to environment instead
safety = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_safety")
socioeconomic = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_socioeconomic")
typology = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_typology")

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




