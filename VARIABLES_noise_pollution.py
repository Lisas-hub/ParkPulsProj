
import geopandas as gpd
import pandas as pd

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

def noise_to_layer2(layer2):

    # noise pollution
    noise = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Bullerkartan_2022_Vag_Tag_och_Flyg.gpkg").to_crs(layer2.crs)

    noise['area'] = noise.geometry.area

    parks_noise = gpd.overlay(layer2, noise, how='intersection')
    parks_noise['overlap_area'] = parks_noise.geometry.area

    # merge back park area
    parks_noise = parks_noise.merge(layer2, on='group')

    # calculate propotion
    #parks_noise['prop_area'] = parks_noise['overlap_area'] / parks_noise['park_area']

    category_table = parks_noise.pivot_table(
        index='group',
        columns='LEQ_DBA',
        values='overlap_area', # use either proportion or overlap here
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    # Group by park and get min, max, range
    noise_stats = parks_noise.groupby('group').agg(
        min_noise=('ISOV1', 'min'),
        max_noise=('ISOV2', 'max')
    ).reset_index()

    noise_stats['range_dba'] = noise_stats['max_noise'] - noise_stats['min_noise']

    final = pd.merge(category_table, noise_stats, on='group')

    layer2 = layer2.merge(final, on='group')

    return layer2
layer2 = noise_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_noise_pollution", driver="GPKG", mode="w")


