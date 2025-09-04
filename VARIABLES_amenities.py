
import geopandas as gpd
import pandas as pd

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

# TO DO
# toilets are not within any park so change format of this variable to within XX m
# add more amenities?

# AMENITIES
def THEME_amenities_to_layer2(layer2):

    toilet = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Toalett_Punkt.gpkg",
                            layer="Toalett_Punkt").to_crs(layer2.crs)
    bench_pts = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_bench_pts.gpkg").to_crs(
        layer2.crs)
    bench_line = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_bench_line.gpkg").to_crs(
        layer2.crs)
    bench_area = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_bench.gpkg").to_crs(
        layer2.crs)
    bbq_pts = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_bbq_pts.gpkg").to_crs(
        layer2.crs)
    bbq_area = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\amenity_bbq.gpkg").to_crs(layer2.crs)
    drinking_fountain = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Dricksvattenfont%C3%A4ner\Dricksvattenfontäner.shp").to_crs(
        layer2.crs)  # not so many in stockholm at all, let alone in parks...
    waste_paper_bin = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Skrapkorg_Punkt.gpkg").to_crs(layer2.crs)
    picnic_table = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\OpenStreetMap\leisure_picnic_table_pts.gpkg").to_crs(layer2.crs)

    toilet['amenity'] = 'WC'
    for gdf in [bench_pts, bench_line, bench_area]: gdf['amenity'] = 'bench'
    for gdf in [bbq_pts, bbq_area]: gdf['amenity'] = 'BBQ area'
    drinking_fountain['amenity'] = 'drinking fountain'
    waste_paper_bin['amenity'] = 'waste paper bin'
    picnic_table['amenity'] = 'picnic table'

    bench_all = gpd.GeoDataFrame(pd.concat([bench_pts, bench_line, bench_area], ignore_index=True),crs=layer2.crs)
    bbq_all = gpd.GeoDataFrame(pd.concat([bbq_pts, bbq_area], ignore_index=True), crs=layer2.crs)
    amenities_all = gpd.GeoDataFrame(pd.concat([toilet, bench_all, bbq_all, drinking_fountain, waste_paper_bin, picnic_table], ignore_index=True), crs=layer2.crs)

    joined_amenities = gpd.sjoin(
        amenities_all[['geometry', 'amenity']],
        layer2[['geometry']],
        how='inner',
        predicate='intersects'
    )

    grouped_amenities = (
        joined_amenities.groupby('index_right')['amenity']
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
layer2 = THEME_amenities_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_amenities", driver="GPKG", mode="w")
