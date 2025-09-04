
import geopandas as gpd
import pandas as pd

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

# TO DO
# toilets are not within any park so change format of this variable to within XX m
# add more amenities

# AMENITIES
def THEME_amenities_to_layer2(layer2):

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

    return layer2
layer2 = THEME_amenities_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_amenities", driver="GPKG", mode="w")
