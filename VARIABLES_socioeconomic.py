
import geopandas as gpd

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

# TO DO (optional)
# add a column in population_aggregated that lists all values in column DESO (IDs) that were included in the aggregation?
# remove sections for aggregated variables and only keep weighted variables?

# socioeconomic
def THEME_socioeconomic_to_layer2(layer2):

    # == socioeconomic ==

    deso_befolkning_age = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\SLU_GET\SCB_13juni\Befolkning\Tab1_DeSO_2023_region.shp").to_crs(layer2.crs)
    deso_befolkning_birthplace = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\SLU_GET\SCB_13juni\Befolkning\Tab4_DeSO_2023_region.shp").to_crs(layer2.crs)
    deso_befolkning_migration = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\SLU_GET\SCB_13juni\Befolkning\Tab5_DeSO_2023_region.shp").to_crs(layer2.crs)
    deso_inkomster = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\SLU_GET\SCB_13juni\Inkomster\Tab11_DeSO_2023_region.shp").to_crs(layer2.crs)

    municipality = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\Kommun_Stadskartan.gpkg").to_crs(layer2.crs)

    deso_befolkning_age = gpd.clip(deso_befolkning_age, municipality)
    deso_befolkning_birthplace = gpd.clip(deso_befolkning_birthplace, municipality)
    deso_befolkning_migration = gpd.clip(deso_befolkning_migration, municipality)
    deso_inkomster = gpd.clip(deso_inkomster, municipality)

    deso_befolkning_age.to_file("data/VARIABLES_NEW.gpkg", layer="DeSo_befolkning_age", driver="GPKG", mode="w")
    deso_befolkning_birthplace.to_file("data/VARIABLES_NEW.gpkg", layer="DeSo_befolkning_birthplace", driver="GPKG", mode="w")
    deso_befolkning_migration.to_file("data/VARIABLES_NEW.gpkg", layer="DeSo_befolkning_migration", driver="GPKG", mode="w")
    deso_inkomster.to_file("data/VARIABLES_NEW.gpkg", layer="DeSo_inkomster", driver="GPKG", mode="w")

    deso_all = deso_befolkning_age.merge(deso_befolkning_birthplace.drop(columns='geometry'), on='DESO') \
             .merge(deso_befolkning_migration.drop(columns='geometry'), on='DESO') \
             .merge(deso_inkomster.drop(columns='geometry'), on='DESO')

    # check the features that look like lines in QGIS, ex DESO IDs that starts with 0126C
    # deso_all['area'] = deso_all.geometry.area
    # small_polygons = deso_all[deso_all["area"] < 400]  # the smallest real deso area = 231123 but there is one large sliver area = 333
    # print(small_polygons)
    # drop slivers
    deso_all = deso_all[deso_all.area >= 400].reset_index(drop=True)
    # *** TEMP FILE - can be removed ***
    deso_all.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_deso_all", driver="GPKG", mode="w")

    # prepp layer 2
    layer2_buffered = layer2.copy()
    layer2_buffered['geometry'] = layer2_buffered.geometry.buffer(500)
    # *** TEMP FILE - can be removed ***
    layer2_buffered.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_park_buffer500", driver="GPKG", mode="w")

    # == aggregated columns ==
    parks_and_deso = gpd.sjoin(layer2_buffered, deso_all, how='left', predicate='intersects')

    agg_columns = ['Alder_0_6', # from deso_befolning_age
                   'Alder_7_15',
                   'Alder_16_1',
                   'Alder_20_2',
                   'Alder_25_4',
                   'Alder_45_6',
                   'Alder_65',
                   'Totalt_x',
                   'Sverige', # from deso_befolkning_birthplace
                   'Norden_uto',
                   'EU_utom_No',
                   'Ovriga_var',
                   'Totalt_y',
                   'Inom', # from deso_befolkning_migration
                   'Till',
                   'Fran',
                   'Inv',
                   'Utv',
                   'Fodda',
                   'Doda',
                   'Tot_Bef']

    deso_aggregated = parks_and_deso.groupby(['group'])[agg_columns].sum().reset_index()
    layer2 = layer2.merge(deso_aggregated, on='group', how='right')
    layer2 = layer2.rename(
        columns={"Alder_0_6": "AGG_Alder_0_6",
                 "Alder_7_15": "AGG_Alder_7_15",
                 "Alder_16_1": "AGG_Alder_16_1",
                 "Alder_20_2": "AGG_Alder_20_2",
                 "Alder_25_4": "AGG_Alder_25_4",
                 "Alder_45_6": "AGG_Alder_45_6",
                 "Alder_65": "AGG_Alder_65",
                 "Totalt_x": "AGG_Alder_Totalt",
                 'Sverige': "AGG_Sverige",
                 'Norden_uto': "AGG_Norden_uto",
                 'EU_utom_No': "AGG_EU_utom_No",
                 'Ovriga_var': "AGG_Ovriga_var",
                 'Totalt_y': "AGG_birthp_Totalt",
                 'Till': "AGG_Till",
                 'Fran': "AGG_Fran",
                 'Inv': "AGG_Inv",
                 'Utv': "AGG_Utv",
                 'Fodda': "AGG_Fodda",
                 'Doda': "AGG_Doda",
                 'Tot_Bef': "AGG_migr_Tot_Bef"
                 })

    # == weighted columns ==
    deso_all['deso_area'] = deso_all.geometry.area

    parks_deso_intersection = gpd.overlay(layer2_buffered, deso_all, how='intersection')
    parks_deso_intersection['intersect_area'] = parks_deso_intersection.geometry.area
    parks_deso_intersection['MedianInk_weighted'] = (
            parks_deso_intersection['MedianInk'] *
            (parks_deso_intersection['intersect_area'] / parks_deso_intersection['deso_area'])
    )
    parks_deso_intersection['TotPop_weighted'] = (
            parks_deso_intersection['Totalt_x'] *
            (parks_deso_intersection['intersect_area'] / parks_deso_intersection['deso_area'])
    )
    # group parks as usual (by column group)
    deso_weighted = parks_deso_intersection.groupby('group').agg({
        'intersect_area': 'sum',
        'TotPop_weighted': 'sum',
        'MedianInk_weighted': 'sum'
    }).reset_index()

    # final MedianInk_weighted
    deso_weighted['MedianInk_weighted_avg'] = (
            deso_weighted['MedianInk_weighted'] / deso_weighted['intersect_area']
    )

    # add to layer2
    layer2 = layer2.merge(deso_weighted, on='group', how='left')

    return layer2
layer2 = THEME_socioeconomic_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_socioeconomic", driver="GPKG", mode="w")
