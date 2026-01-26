
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

# TO DO
# fix input road layers so that fill in areas between roads that shouldn't be filled in are removed?
# fix dissolved so that unconnected polygons are not being removed? or keep it that way?

# accessibility
def THEME_accessibility_to_layer2(layer2):

    # == accessibility ==

    # public transport
    bus_stops = gpd.read_file(f"{input_directory}\\Input\\OpenStreetMap\\highway_bus_stop_pts.gpkg").to_crs(
        layer2.crs)  # no need to add bus_stations (only 2, one overlaps w bus_stops and the other is not in STHLM) or bus_stations_pts (6/9 by a sea port and 3/9 by cityterminal/liljeholmen, these are transfer bus stations)
    subway_entrances = gpd.read_file(
        f"{input_directory}\\Input\\OpenStreetMap\\railway_subway_entrance.gpkg").to_crs(
        layer2.crs)  # no need to add railway_subway.gpkg (it's a line layer)

    bus_stops['transport_type'] = 'Bus'
    subway_entrances['transport_type'] = 'Subway'

    # Combine all transportation into one GeoDataFrame
    transport_points = gpd.GeoDataFrame(
        pd.concat([bus_stops, subway_entrances], ignore_index=True),
        crs=layer2.crs
    )

    # buffer the park polygons
    layer2_buffered = layer2.copy()
    layer2_buffered['geometry'] = layer2_buffered.geometry.buffer(200)

    # join
    joined_transport = gpd.sjoin(
        transport_points[['geometry', 'transport_type']],
        layer2_buffered[['geometry']],
        how='inner',
        predicate='intersects'
    )

    ########
    # transport type diversity (output: 0 = no public transport nearby; 1 = only bus or only subway; 2 = both bus + subway)
    transport_type_diversity = (
        joined_transport
            .groupby('index_right')['transport_type']
            .nunique()
            .rename('transport_type_diversity')
    )

    layer2 = layer2.join(transport_type_diversity, how='left')
    layer2['transport_type_diversity'] = layer2['transport_type_diversity'].fillna(0)

    # transport points per park
    transport_point_counts = (
        joined_transport
            .groupby('index_right')
            .size()
            .rename('transport_points_count')
    )

    layer2 = layer2.join(transport_point_counts, how='left')
    layer2['transport_points_count'] = layer2['transport_points_count'].fillna(0)

    # transport points per hectare
    layer2['transport_points_per_ha'] = (
            layer2['transport_points_count'] / (layer2['park_area'] / 10000)
    )
    layer2['transport_points_per_ha'] = layer2['transport_points_per_ha'].fillna(0)
    ########

    # Group by polygon and list transport type
    grouped_transport = (
        joined_transport.groupby('index_right')['transport_type']
            .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
            .reset_index()
    )

    layer2['variable_public_transport'] = layer2.index.map(
        grouped_transport.set_index('index_right')['transport_type']
    ).fillna('None')

    # walking distance by road
    road1 = gpd.read_file(
        f"{input_directory}\\Input\\STHLM_stad\\Stadskarta_Stockholm_SHP\\Vaegutbredning_area.shp").to_crs(layer2.crs)
    road2 = gpd.read_file(
        f"{input_directory}\\Input\\STHLM_stad\\Stadskarta_Stockholm_SHP\\Trafik_area.shp").to_crs(layer2.crs)

    merged = road1.overlay(road2, how="union") # see dropped beometries by adding `keep_geom_type=True`, but dropped geometries have attribute info but don't show up when using zoom to location,

    merged["area"] = merged.geometry.area
    merged = merged[merged.area >=1] # drop slivers

    # roads from sthlm stad
    merged.to_file("data/VARIABLES_NEW.gpkg", layer="roads_from_sthlm_stad", driver="GPKG", mode="w")

    # fix geometries
    #merged['geometry'] = merged['geometry'].buffer(0)
    #merged['geometry'] = merged['geometry'].buffer(0.1)

    dissolved = merged.dissolve(by=None, as_index=False)

    # Reduce buffer to go back to original size again (after fix earlier)
    #dissolved['geometry'] = dissolved['geometry'].buffer(-0.1)

    # *** TEMP FILE - can be removed ***
    dissolved.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_roads2", driver="GPKG", mode="w")

    # Save
    #dissolved.to_file("data/VARIABLES_NEW.gpkg", layer="TEMP_FILE_roads3", driver="GPKG", mode="w")

    ##########
    # distance to city center (Euclidean)

    # Stockholm Central Station (city center)
    city_center_wgs84 = gpd.GeoSeries(
        [Point(18.0589, 59.3303)],
        crs="EPSG:4326"
    )

    # project to same CRS as layer2
    city_center = city_center_wgs84.to_crs(layer2.crs).iloc[0]

    # distance in meters
    layer2['distance_to_city_center_m'] = (layer2.geometry.centroid.distance(city_center))

    # optional: distance in km (often nicer for regression coefficients)
    layer2['distance_to_city_center_km'] = layer2['distance_to_city_center_m'] / 1000
    ##########

    return layer2
layer2 = THEME_accessibility_to_layer2(layer2)



layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_accessibility", driver="GPKG", mode="w")



# roads from OSM *** bättre än sthlm stads? i osm finns väl stigar och sånt ju?? vilket ju är toppen om man ska kolla på gångavstånd
