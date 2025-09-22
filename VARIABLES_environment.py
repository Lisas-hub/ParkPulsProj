
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

def THEME_biotop_to_layer2(layer2):

    layer_biotop_klass = gpd.read_file(f"{input_directory}\\Input\\STHLM_stad\\Biotopkartan_2019\\Biotopkartan_2019_Klass.gpkg", layer="Klass").to_crs(layer2.crs)

    # make a column of custom categories
    def classify_row(row):
        general = row['h_klass']
        detailed = row['klass']

        if general in ["Buskmark", "Skogsmark/trädklädd mark"]:
            return "Skog-/buskmark"

        elif general in ["Vatten", "Öppen mark", "Odlingsmark"]:
            return "Öppen yta" # Odling here is mostly  crop fields which is why they are put as open but it does also include a few fruit/berry plots

        elif general == "Urban gråstruktur":
            if detailed == "Urban gråstruktur, byggnader":
                return "Urban gråstruktur, byggnader"
            elif detailed == "Grå infrastruktur":
                return "Urban gråstruktur, infrastruktur"
            else:
                return "okänd"  # There should not be any of these

        elif general == "Urban grönstruktur":
            if detailed in ["Urban grönstruktur av grå karaktär", "Urban grönstruktur, gröna tak"]:
                return "Urban grönstruktur, övrigt"
            elif detailed in ["Urban grönstruktur av lummig karaktär", "Urban grönstruktur av naturtomtskaraktär",
                              "Urban grönstruktur av trädkaraktär", "Odlingslott eller fruktträdgård"]:
                return "Urban grönstruktur, vegetation" # Odlingslotter is not set to open since they tend to be closed off and with a lot of vegetation
            elif detailed in ["Urban grönstruktur av öppen karaktär"]:
                return "Urban grönstruktur, öppen yta"
            else:
                return "okänd"  # There should not be any of these

        else:
            return "okänd"

    layer_biotop_klass["BIOTOP_custom"] = layer_biotop_klass.apply(classify_row, axis=1)

    # *** TEMP FILE - can be removed ***
    layer_biotop_klass.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_biotop1", driver="GPKG", mode="w")

    # intersect with layer2
    intersected = gpd.overlay(
        layer_biotop_klass[["geometry", "h_klass", "klass", "BIOTOP_custom"]],
        layer2[["geometry", "group"]],
        how="intersection"
    )

    intersected["intersected_area"] = intersected.geometry.area

    # combine unique categories per polygon in layer2
    def combine_unique(series):
        return ", ".join(sorted(set(series.dropna())))

    combined_grouped = (
        intersected.groupby("group").agg({
            "h_klass": combine_unique,
            "klass": combine_unique,
            "BIOTOP_custom": combine_unique
        })
    )

    # merge with layer2
    layer2 = layer2.merge(
        combined_grouped.rename(columns={
            "h_klass": "BIOTOP_hklass_combined",
            "klass": "BIOTOP_klass_combined",
            "BIOTOP_custom": "BIOTOP_custom_combined"
        }),
        on="group",
        how="left"
    )

    # calculate area per h_klass
    h_klass_area_summary = (
        intersected.groupby(["group", "h_klass"])["intersected_area"]
            .sum()
            .unstack(fill_value=0)
    )

    custom_area_summary = (
        intersected.groupby(["group", "BIOTOP_custom"])["intersected_area"]
            .sum()
            .unstack(fill_value=0)
    )

    # merge area columns into layer2
    layer2 = layer2.merge(h_klass_area_summary, on="group", how="left")
    layer2 = layer2.merge(custom_area_summary, on="group", how="left")

    layer2 = layer2.fillna(0)


    return layer2
layer2 = THEME_biotop_to_layer2(layer2)

def THEME_temperature_to_layer2(layer2):

    temperature_lines = gpd.read_file(
        f"{input_directory}\\Input\\STHLM_stad\\Temperaturkartering\\Temperaturkurvor_uppmatt_stralningstemp.gpkg").to_crs(
        layer2.crs)
    temperature_polygons = gpd.read_file(
        f"{input_directory}\\Output\\Uppmatt_stralningstemp_prepped.gpkg").to_crs(layer2.crs)

    # the original layer was a polyline layer and the extent did not fully align with the municipality boundary so the data had to be pepped outside of this script (some manual editing)

    # assign lower/upper temperature from intersecting lines per temperature_polygon
    def get_temperature_range(geometry):
        intersecting = temperature_lines[temperature_lines.intersects(geometry)]
        temps = intersecting["Max_temp"].unique()
        if len(temps) == 0:
            return pd.Series([None, None])
        return pd.Series([int(min(temps)), int(max(temps))])

    temperature_polygons[["Temp_max_lower", "Temp_max_upper"]] = temperature_polygons["geometry"].apply(
        get_temperature_range)

    # drop slivers
    sliver_threshold = 0.01
    temperature_polygons["area"] = temperature_polygons.geometry.area
    temperature_polygons = temperature_polygons[temperature_polygons["area"] >= sliver_threshold].copy()

    # fill missing temp polygons using neighboring ones (issue arises from temperature lines not fully covering the municipality area)
    null_polys = temperature_polygons[temperature_polygons["Temp_max_lower"].isna()]
    valid_polys = temperature_polygons[temperature_polygons["Temp_max_lower"].notna()]
    sindex = valid_polys.sindex

    def get_best_neighbor_temps(geometry):
        possible_matches_index = list(sindex.intersection(geometry.bounds))
        candidates = valid_polys.iloc[possible_matches_index]

        max_shared = 0
        best_temps = (None, None)

        for _, row in candidates.iterrows():
            shared = geometry.boundary.intersection(row.geometry.boundary)
            length = 0
            if isinstance(shared, LineString):
                length = shared.length
            elif shared.geom_type.startswith("Multi"):
                length = sum(g.length for g in shared.geoms if isinstance(g, LineString))

            if length > max_shared:
                max_shared = length
                best_temps = (row["Temp_max_lower"], row["Temp_max_upper"])

        return pd.Series(best_temps)

    temperature_polygons.loc[null_polys.index, ["Temp_max_lower", "Temp_max_upper"]] = null_polys["geometry"].apply(
        get_best_neighbor_temps)

    # add mean temp to each temperature polygon
    temperature_polygons["Temp_mean"] = (temperature_polygons["Temp_max_lower"] + temperature_polygons[
        "Temp_max_upper"]) / 2

    # intersect parks with temperature polygons
    parks_temp = gpd.overlay(layer2, temperature_polygons, how="intersection")
    parks_temp["overlap_area"] = parks_temp.geometry.area

    # weighted mean calculation
    parks_temp["weighted_mean"] = parks_temp["Temp_mean"] * parks_temp["overlap_area"]

    # group by park
    grouped = parks_temp.groupby("group").agg({
        "Temp_max_lower": "min",  # the lowest isotherm touching any part of the park
        "Temp_max_upper": "max",  # the highest isotherm touching any part of the park
        "weighted_mean": "sum",
        "overlap_area": "sum"
    }).reset_index()

    # final weighted mean temp for each park
    grouped["avg_weighted_mean_temp"] = grouped["weighted_mean"] / grouped["overlap_area"]

    # merge back to parks
    layer2 = layer2.merge(grouped[["group", "Temp_max_lower", "Temp_max_upper", "avg_weighted_mean_temp"]], on="group",
                          how="left")

    return layer2
layer2 = THEME_temperature_to_layer2(layer2)

def THEME_protected_areas_to_layer2(layer2):

    # protected areas
    nature_reserve = gpd.read_file(f"{input_directory}\\Input\\Naturvardsverket\\Skyddade_omraden_naturvardsregistret\\Naturreservat\\PS.protectedSites.NR.gml").to_crs(layer2.crs)
    culture_reserve = gpd.read_file(f"{input_directory}\\Input\\Naturvardsverket\\Skyddade_omraden_naturvardsregistret\\Kulturreservat\\PS.protectedSites.KR.gml").to_crs(layer2.crs)
    natural_monument = gpd.read_file(f"{input_directory}\\Input\\Naturvardsverket\\Skyddade_omraden_naturvardsregistret\\Naturminnen\\PS.protectedSites.NM.gml").to_crs(layer2.crs)
    water_reserve = gpd.read_file(f"{input_directory}\\Input\\Naturvardsverket\\Omraden_med_sarskilda_restriktioner\\Vattenskyddsomraden\\am_drinkingWaterProtectionArea.gml").to_crs(layer2.crs)
    entry_forbidden = gpd.read_file(f"{input_directory}\\Input\\Naturvardsverket\\Omraden_med_sarskilda_restriktioner\\Foreskriftsomraden\\am_regulatoryAreas.gml").to_crs(layer2.crs)

    municipality = gpd.read_file(f"{input_directory}\\Output\\Kommun_Stadskartan.gpkg").to_crs(layer2.crs)

    nature_reserve = gpd.clip(nature_reserve, municipality)
    culture_reserve = gpd.clip(culture_reserve, municipality)
    natural_monument = gpd.clip(natural_monument, municipality)
    water_reserve = gpd.clip(water_reserve, municipality)
    entry_forbidden = gpd.clip(entry_forbidden, municipality)

    nature_reserve["Protected_Type"] = "Naturreservat"
    culture_reserve["Protected_Type"] = "Kulturreservat"
    natural_monument["Protected_Type"] = "Naturminne"
    water_reserve["Protected_Type"] = "Vattenskyddsområde"
    entry_forbidden["Protected_Type"] = "Tillträdesförbud under särskilda perioder"

    # checking polygons, only 11/18 are actual reserves, the rest are slivers
    nature_reserve["area"] = nature_reserve.geometry.area
    print(nature_reserve.head(20))

    nature_reserve.to_file("data/VARIABLES_NEW.gpkg", layer="nature_reserve_STHLM", driver="GPKG", mode="w")
    culture_reserve.to_file("data/VARIABLES_NEW.gpkg", layer="culture_reserve_STHLM", driver="GPKG", mode="w")
    natural_monument.to_file("data/VARIABLES_NEW.gpkg", layer="natural_monument_STHLM", driver="GPKG", mode="w")
    water_reserve.to_file("data/VARIABLES_NEW.gpkg", layer="water_reserve_STHLM", driver="GPKG", mode="w")
    entry_forbidden.to_file("data/VARIABLES_NEW.gpkg", layer="entry_forbidden_STHLM", driver="GPKG", mode="w")

    protected_areas_all = gpd.GeoDataFrame(
        pd.concat([
            nature_reserve[["geometry", "Protected_Type"]],
            culture_reserve[["geometry", "Protected_Type"]],
            natural_monument[["geometry", "Protected_Type"]],
            water_reserve[["geometry", "Protected_Type"]],
            entry_forbidden[["geometry", "Protected_Type"]]
        ], ignore_index=True),
        crs=layer2.crs
    )

    joined_protected = gpd.sjoin(
        protected_areas_all,
        layer2[['geometry']],
        how='inner',
        predicate='intersects'
    )

    grouped_protected = (
        joined_protected.groupby("index_right")["Protected_Type"]
            .apply(lambda x: ", ".join(sorted(set(x))))
            .reset_index()
    )

    layer2["Protected_areas_combined"] = layer2.index.map(grouped_protected.set_index("index_right")["Protected_Type"])
    layer2["Protected_areas_combined"] = layer2["Protected_areas_combined"].fillna("Inga")

    # point layer for monuments
    natural_monument_points = natural_monument[natural_monument.geometry.type == "Point"].copy()
    natural_monument_polygons = natural_monument[
        natural_monument.geometry.type.isin(["Polygon", "MultiPolygon"])
    ].copy()

    natural_monument_polygons["geometry"] = natural_monument_polygons.geometry.representative_point()

    common_cols = list(set(natural_monument_points.columns) & set(natural_monument_polygons.columns))
    natural_monument_points = natural_monument_points[common_cols]
    natural_monument_polygons = natural_monument_polygons[common_cols]

    natural_monument_combined_points = gpd.GeoDataFrame(
        pd.concat([natural_monument_points, natural_monument_polygons], ignore_index=True),
        crs=natural_monument_points.crs
    )

    natural_monument_combined_points.to_file("data/VARIABLES_NEW.gpkg", layer="natural_monuments_pts", driver="GPKG")

    return layer2
layer2 = THEME_protected_areas_to_layer2(layer2)

def noise_to_layer2(layer2):

    noise = gpd.read_file(f"{input_directory}\\Input\\STHLM_stad\\Bullerkartan_2022_Vag_Tag_och_Flyg.gpkg").to_crs(layer2.crs)

    noise['area'] = noise.geometry.area

    parks_noise = gpd.overlay(layer2, noise, how='intersection')
    parks_noise['overlap_area'] = parks_noise.geometry.area

    parks_noise = parks_noise.merge(layer2, on='group')

    category_table = parks_noise.pivot_table(
        index='group',
        columns='LEQ_DBA',
        values='overlap_area',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    noise_stats = parks_noise.groupby('group').agg(
        min_noise=('ISOV1', 'min'),
        max_noise=('ISOV2', 'max')
    ).reset_index()

    noise_stats['range_dba'] = noise_stats['max_noise'] - noise_stats['min_noise']

    final = pd.merge(category_table, noise_stats, on='group')

    layer2 = layer2.merge(final, on='group')

    return layer2
layer2 = noise_to_layer2(layer2)

def noiseXbiotop_to_layer2(layer2):

    noise_cols = [
        '<40', '40-45', '45-50', '50-55',
        '55-60', '60-65', '65-70', '70-75', '>75'
    ]

    landcover_cols = [
        'Skog-/buskmark',
        'Urban gråstruktur, byggnader',
        'Urban gråstruktur, infrastruktur',
        'Urban grönstruktur, vegetation',
        'Urban grönstruktur, öppen yta',
        'Urban grönstruktur, övrigt',
        'Öppen yta'
    ]

    # Initialize an empty list to collect records
    records = []

    for idx, row in layer2.iterrows():
        park_area = row['park_area']

        for noise_bin in noise_cols:
            noise_area = row[noise_bin]

            for lc in landcover_cols:
                lc_area = row[lc]
                proportion = lc_area / park_area if park_area > 0 else 0
                estimated_lc_area_in_bin = proportion * noise_area

                records.append({
                    'Noise_Bin': noise_bin.replace('noise_', ''),
                    'Land_Cover': lc,
                    'Estimated_Area': estimated_lc_area_in_bin
                })

    # Create a new dataframe
    df_long = pd.DataFrame(records)

    noise_group_map = {
        '<40': 'Låg (<45 dBA)',
        '40-45': 'Låg (<45 dBA)',
        '45-50': 'Medel (45-60 dBA)',
        '50-55': 'Medel (45-60 dBA)',
        '55-60': 'Medel (45-60 dBA)',
        '60-65': 'Hög (>60 dBA)',
        '65-70': 'Hög (>60 dBA)',
        '70-75': 'Hög (>60 dBA)',
        '>75': 'Hög (>60 dBA)'
    }
    # Apply grouping
    df_long['Noise_Group'] = df_long['Noise_Bin'].map(noise_group_map)

    # Group by Noise_Group and Land_Cover
    df_grouped = df_long.groupby(['Noise_Group', 'Land_Cover'])['Estimated_Area'].sum().reset_index()

    total_per_group = df_grouped.groupby('Noise_Group')['Estimated_Area'].sum().reset_index()
    total_per_group.rename(columns={'Estimated_Area': 'Total_Area'}, inplace=True)

    df_grouped = df_grouped.merge(total_per_group, on='Noise_Group')
    df_grouped['Proportion'] = (df_grouped['Estimated_Area'] / df_grouped['Total_Area']) * 100

    #df_grouped.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_noiseXbiotop1", driver="GPKG", mode="w")
    df_grouped.to_csv(r"C:\Users\lisajos\PycharmProjects\landcover_by_noise_group.csv", index=False)

    # Pivot to get land cover types as columns
    df_pivot = df_grouped.pivot(index='Noise_Group', columns='Land_Cover', values='Proportion')
    df_pivot = df_pivot.fillna(0)

    # Ensure correct order of noise bins (optional)
    noise_group_order = ['Låg (<45 dBA)', 'Medel (45-60 dBA)', 'Hög (>60 dBA)']
    df_pivot = df_pivot.reindex(noise_group_order)

    import matplotlib.pyplot as plt

    # Plot
    custom_colors = {
        'Skog-/buskmark': '#086120', # green
        'Urban gråstruktur, byggnader': '#450202', # dark red
        'Urban gråstruktur, infrastruktur': '#a6a6a6', # grey
        'Urban grönstruktur, vegetation': '#8ccc81', # light green
        'Urban grönstruktur, öppen yta': '#d3eda8', # pale warm green
        'Urban grönstruktur, övrigt': '#2accd1', # turqoise because the category should be aggregated with something else
        'Öppen yta': '#f2eed0', # pale yellow
    }

    df_pivot.plot(
        kind='bar',
        stacked=True,
        figsize=(12, 8),
        color=[custom_colors[col] for col in df_pivot.columns],
        width=0.7 # at 1, bars tough eachothers sides
    )
    plt.ylabel('Andel parkarea (%)', fontsize=16)
    plt.xlabel('Bullernivå', fontsize=16)
    plt.title('Andel markanvändning per bullernivå', fontsize=16)
    plt.yticks(fontsize=14)
    plt.xticks(rotation=0, ha='center', fontsize=14) # rotation=45 for diagonal, if diagonal, use ha='right'
    plt.legend(
        title=False,
        bbox_to_anchor=(1.05, 1),
        loc='upper left',
        frameon=False,
        fontsize=16,
        title_fontsize=18
    )
    plt.tight_layout()
    plt.show()

    return layer2
layer2 = noiseXbiotop_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_environment", driver="GPKG", mode="w")




