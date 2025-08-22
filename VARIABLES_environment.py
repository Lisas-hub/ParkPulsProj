
import geopandas as gpd
import pandas as pd
from shapely.strtree import STRtree
import networkx as nx

# ===== LAYERS =======

def prepp_layer1():

    # ==== layer1: original park layer ====

    layer1 = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Temp\Sociotop_2024_edited.gpkg", layer="Sociotop_2024_edit3")
    layer1 = layer1.drop(columns=['AREA', 'ANTAL', 'Inventering_2', 'change_made'], errors='ignore')

    # Format the names to remove any capital letters in the middle of a name like SÖdra Rosendalsparken
    layer1["NAMN"] = layer1["NAMN"].str.title()

    return layer1
layer1 = prepp_layer1()

def create_layer2():

    # ==== layer2: created by dissolving layer1 ====

    layer2 = layer1.copy()  # this step prevents edits to layer1 which will be important later in the script

    # == fix geometries ==
    layer2['geometry'] = layer2['geometry'].buffer(0)
    # Remove tiny slivers between polygons that should be touching
    layer2['geometry'] = layer2['geometry'].buffer(0.1)

    # == group intersecting polygons then dissolve ==
    # list geometries
    geoms = list(layer2.geometry)
    tree = STRtree(geoms)

    # build a graph of touching/intersecting geometries
    edges = []
    for i, geom in enumerate(geoms):
        for j in tree.query(geom):
            if i < j and geom.intersects(geoms[j]):
                edges.append((i, j))

    # build graph and get connected components
    G = nx.Graph()
    G.add_edges_from(edges)
    components = list(nx.connected_components(G))

    # create column group
    layer2["group"] = -1  # temp placeholder

    # add group value to intersecting polygons
    for group_id, component in enumerate(components, 1):
        for idx in component:
            layer2.at[idx, "group"] = group_id

    # add unique group values to remaining ungrouped polygons
    next_group_id = len(components) + 1
    for idx in layer2[layer2["group"] == -1].index:
        layer2.at[idx, "group"] = next_group_id
        next_group_id += 1

    # dissolve geometries by group
    layer2 = layer2.dissolve(by="group", as_index=False)

    # reduce buffer to go back to original size again (after fix slivers earlier)
    layer2['geometry'] = layer2['geometry'].buffer(-0.1)

    # == organise columns in the attribute table of layer2 ==
    # drop most of the columns except a selected the relevant ones
    columns_to_keep = ["group",
                       "geometry"]  # *** OBS! there is also a fid column created but this does not correspont to previous fid or New_ID

    layer2 = layer2[columns_to_keep]

    return layer2
layer2 = create_layer2()


# ============ PREP ==============

def NAMN_XXX_to_layer2(layer2):

    # NAMN_combined: lists all occurences of NAMN from layer1 when polyons have dissolved in layer2
    joined_namn = gpd.sjoin(
        layer1[['geometry', 'NAMN']],
        layer2[['geometry']],
        how='left',
        predicate='intersects'
    )

    grouped_namn = (
        joined_namn.groupby("index_right")["NAMN"]
            .apply(lambda x: ", ".join(sorted(
            set(x.dropna()))))  # set(x) removes duplicate names, sorted() gives consistent order, dropna() prevents "nan" strings in the result
            .reset_index()
    )

    layer2["NAMN_combined"] = layer2.index.map(grouped_namn.set_index("index_right")["NAMN"])

    # NAMN_top5: same as NAMN_combined except the list only contains a maximum of 5 names (from the largest polygons)

    # Add area to layer1
    layer1["layer1_area"] = layer1.geometry.area

    joined_5namn = gpd.sjoin(
        layer1[["geometry", "NAMN", "layer1_area"]],
        layer2[["geometry"]],
        how="left",
        predicate="intersects"
    )

    def summarize_names(df):
        unique_names = df[["NAMN", "layer1_area"]].dropna().drop_duplicates()
        sorted_names = unique_names.sort_values(by="layer1_area", ascending=False)["NAMN"]
        top_names = sorted_names.head(5).tolist()
        if len(sorted_names) > 5:
            top_names.append("m.fl.")
        return ", ".join(top_names)

    summarized_namn = (
        joined_5namn.groupby("index_right")
            .apply(
            summarize_names)  # *** address the warning? "DeprecationWarning: DataFrameGroupBy.apply operated on the grouping columns. This behavior is deprecated, and in a future version of pandas the grouping columns will be excluded from the operation. Either pass `include_groups=False` to exclude the groupings or explicitly select the grouping columns after groupby to silence this warning."
            .reset_index(name="NAMN_top5")
    )

    layer2["NAMN_top5"] = layer2.index.map(summarized_namn.set_index("index_right")["NAMN_top5"])

    return layer2
layer2 = NAMN_XXX_to_layer2(layer2)

def stadsdelar_to_layer2(layer2):

    # == add stadsdelar ==
    stadsdelar = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\Stadsdelar_Stadskartan.gpkg").to_crs(layer2.crs)
    # drop all columns except NAMN (på stadsdelar)
    columns_to_keep_stadsdelar = ["geometry", "NAMN"]
    stadsdelar = stadsdelar[columns_to_keep_stadsdelar]

    intersection_stadsdelar = gpd.overlay(layer2, stadsdelar, how='intersection')
    intersection_stadsdelar["overlap_area"] = intersection_stadsdelar.geometry.area

    largest_overlap = intersection_stadsdelar.sort_values("overlap_area", ascending=False).drop_duplicates("NAMN_combined")

    layer2 = layer2.merge(
        largest_overlap[["NAMN_combined", "NAMN"]],
        on="NAMN_combined",
        how="left"
    )

    layer2 = layer2.rename(columns={"NAMN": "stadsdelar"})

    return layer2
layer2 = stadsdelar_to_layer2(layer2)

def stadsdelsomraden_to_layer2(layer2):

    # == add stadsdelsomraden ==
    stadsdelsomraden = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\Stadsdelsomraden_Stadskartan.gpkg").to_crs(layer2.crs)
    # drop all columns except stadsdelsområden
    columns_to_keep_stadsdelsomraden = ["geometry", "Omrade"]
    stadsdelsomraden = stadsdelsomraden[columns_to_keep_stadsdelsomraden]

    intersection_stadsdelsomraden = gpd.overlay(layer2, stadsdelsomraden, how='intersection')
    intersection_stadsdelsomraden["overlap_area"] = intersection_stadsdelsomraden.geometry.area

    largest_overlap = intersection_stadsdelsomraden.sort_values("overlap_area", ascending=False).drop_duplicates("NAMN_combined")

    layer2 = layer2.merge(
        largest_overlap[["NAMN_combined", "Omrade"]],
        on="NAMN_combined",
        how="left"
    )

    layer2 = layer2.rename(columns={"Omrade": "stadsdelsomraden"})

    return layer2
layer2 = stadsdelsomraden_to_layer2(layer2)


# === THEME ===

def THEME_biotop_to_layer2(layer2):

    layer_biotop_klass = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Biotopkartan_2019\Biotopkartan_2019_Klass.gpkg", layer="Klass").to_crs(layer2.crs)

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
                return "Urban grönstruktur, vegetation" # Odlingslotter is not set to open since they tend to be closed of and with a lot of vegetation
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

    # Optional: fill NaNs after merge (e.g., no intersecting categories)
    layer2 = layer2.fillna(0)






    return layer2
layer2 = THEME_biotop_to_layer2(layer2)

def THEME_temperature_to_layer2(layer2):

    temperature_lines = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Temperaturkartering\Temperaturkurvor_uppmatt_stralningstemp.gpkg").to_crs(layer2.crs)
    temperature_polygons = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\Uppmatt_stralningstemp_prepped.gpkg").to_crs(layer2.crs)
    # the original layer was a polyline layer and the extent did not fully align with the municipality boundary so the data had to be pepped outside of this script (some manual editing)

    # ADD TEMP INFO BACK TO POLYGON LAYER FROM LINE LAYER
    # determine temperature range for each polygon
    def assign_temperature_band(temperature_polygons, temperature_lines):

        intersecting_lines = temperature_lines[temperature_lines.intersects(temperature_polygons)]

        temps = intersecting_lines["Max_temp"].unique()

        if len(temps) == 0:
            return None  # no intersection
        elif len(temps) == 1:
            return str(int(temps[0]))  # just one temperature value
        else:
            sorted_temps = sorted(temps)
            return f"{int(sorted_temps[0])}-{int(sorted_temps[-1])}"  # range of temperature values

    # apply function to each polygon
    temperature_polygons["Temp_band"] = temperature_polygons["geometry"].apply(lambda geom: assign_temperature_band(geom, temperature_lines))

    # *** TEMP FILE - can be removed ***
    temperature_polygons['area'] = temperature_polygons.geometry.area
    # check for appropriate sliver threshold
    temperature_polygons.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_temperature1", driver="GPKG", mode="w")

    # FIX SLIVERS
    # set sliver threshold, filter and drop them
    slivers_threshold = 0.01
    #is_sliver = (temperature_polygons.area < slivers_threshold) & (temperature_polygons["Temp_band"].isna())
    #temperature_polygons = temperature_polygons[~is_sliver].copy()
    temperature_polygons = temperature_polygons[temperature_polygons.area >= slivers_threshold].copy()

    # *** TEMP FILE - can be removed ***
    temperature_polygons.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_temperature2", driver="GPKG", mode="w")

    # add upper and lower max temp columns
    def get_temperature_range(geometry, temperature_lines):
        intersecting_lines = temperature_lines[temperature_lines.intersects(geometry)]
        temps = intersecting_lines["Max_temp"].unique()

        if len(temps) == 0:
            return (None, None)
        else:
            lower_max_temp = int(min(temps))
            upper_max_temp = int(max(temps))
            return (lower_max_temp, upper_max_temp)

    # Apply and expand the result into two new columns
    temperature_polygons[["Temp_max_lower", "Temp_max_upper"]] = temperature_polygons["geometry"].apply(
        lambda geom: pd.Series(get_temperature_range(geom, temperature_lines))
    )

    # fix polygons resulting from extend line during prepp that lacks attribute information aout temperature
    from shapely.geometry import LineString

    # separate polygons that need to be fixed (Temp_band = Null) from those that don't
    null_polys = temperature_polygons[temperature_polygons["Temp_band"].isna()].copy()
    non_null_polys = temperature_polygons[temperature_polygons["Temp_band"].notna()].copy()

    # build spatial index
    sindex = non_null_polys.sindex

    def find_best_neighbor(null_geom):
        possible_matches_index = list(sindex.intersection(null_geom.bounds))
        candidates = non_null_polys.iloc[possible_matches_index]

        max_shared_length = 0
        best_neighbor_idx = None

        for idx, row in candidates.iterrows():
            shared = null_geom.boundary.intersection(row.geometry.boundary)
            if isinstance(shared, LineString):
                shared_length = shared.length
            elif shared.geom_type.startswith('Multi'):
                shared_length = sum(g.length for g in shared.geoms if isinstance(g, LineString))
            else:
                shared_length = 0

            if shared_length > max_shared_length:
                max_shared_length = shared_length
                best_neighbor_idx = idx

        return best_neighbor_idx

    # Assign upper and lower from best neighbor
    for idx, null_row in null_polys.iterrows():
        best_idx = find_best_neighbor(null_row.geometry)
        if best_idx is not None:
            best_neighbor = non_null_polys.loc[best_idx]
            temperature_polygons.at[idx, "Temp_max_lower"] = best_neighbor["Temp_max_lower"]
            temperature_polygons.at[idx, "Temp_max_upper"] = best_neighbor["Temp_max_upper"]
        else:
            print(f"⚠️ No neighbor found for polygon {idx}")
    # there was a warning for polygon 325 but it has the correct Temp_band in the output anyways so ignor the warning. Polygon 280 however has Temp_band null, but this can be ignored since this does npt overlap with a park

    # *** TEMP FILE - can be removed ***
    temperature_polygons.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_temperature3", driver="GPKG", mode="w")


    # WEIGHTED OVERLAP - LAYER2 AND TEMP
    parks_temp_intersection = gpd.overlay(layer2, temperature_polygons, how='intersection')
    parks_temp_intersection['overlap_area'] = parks_temp_intersection.geometry.area

    layer2['park_area'] = layer2.geometry.area

    # multiply temp values by overlap area
    parks_temp_intersection['weighted_lower_max_temp'] = parks_temp_intersection['Temp_max_lower'] * parks_temp_intersection['overlap_area']
    parks_temp_intersection['weighted_upper_max_temp'] = parks_temp_intersection['Temp_max_upper'] * parks_temp_intersection['overlap_area']


    weighted_temps = parks_temp_intersection.groupby('group').agg({
        'weighted_lower_max_temp': 'sum',
        'weighted_upper_max_temp': 'sum',
        'overlap_area': 'sum'
    }).reset_index()

    # calculate weighted average
    weighted_temps['avg_lower_max_temp'] = weighted_temps['weighted_lower_max_temp'] / weighted_temps['overlap_area']
    weighted_temps['avg_upper_max_temp'] = weighted_temps['weighted_upper_max_temp'] / weighted_temps['overlap_area']

    # merge back to layer2
    layer2 = layer2.merge(weighted_temps[['group', 'avg_lower_max_temp', 'avg_upper_max_temp']], on='group', how='left')

    return layer2

layer2 = THEME_temperature_to_layer2(layer2)

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_environment", driver="GPKG", mode="w")




