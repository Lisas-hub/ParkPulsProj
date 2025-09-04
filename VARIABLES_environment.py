
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

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
        r"C:\Users\lisajos\QGIS_Projects\Input\STHLM_stad\Temperaturkartering\Temperaturkurvor_uppmatt_stralningstemp.gpkg").to_crs(
        layer2.crs)
    temperature_polygons = gpd.read_file(
        r"C:\Users\lisajos\QGIS_Projects\Output\Uppmatt_stralningstemp_prepped.gpkg").to_crs(layer2.crs)

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

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_environment", driver="GPKG", mode="w")




