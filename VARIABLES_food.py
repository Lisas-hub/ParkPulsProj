
import geopandas as gpd
import pandas as pd

input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

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

    # join
    joined_amenity_food = gpd.sjoin(
        food_establishments[['geometry', 'amenity_food']],
        layer2_buffered[['geometry']],
        how='inner',
        predicate='intersects'
    )

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
        layer2_buffer_dissolve,
        how='inner',
        predicate='within'
    ) # this output results in 42 pts, 1 will be dropped later because here it is within the buffer layer but not within stadsdelsområden

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

    return layer2
layer2 = THEME_food_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_food", driver="GPKG", mode="w")
















