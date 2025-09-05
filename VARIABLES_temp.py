import geopandas as gpd
import pandas as pd

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

# ==== OTHER STATS ====
def OTHER_STATS_park_coverage():

    # == park coverage in Stockholm ==
    municipality = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Output\Kommun_Stadskartan.gpkg").to_crs(layer2.crs)

    # union of parks and municipality
    park_coverage = gpd.overlay(municipality, layer2, how='union') # OBS! mismatch between parks and municipality boundary, small pieces of some parks are outside of the boundary and got group_temp null

    # remove polygons outside the municipality boundary
    park_coverage = gpd.clip(park_coverage, municipality)

    # drop all unnecessary columns by selecting only relevant columns
    park_coverage = park_coverage[["geometry"]]

    # calculate area
    park_coverage ['area'] = park_coverage.geometry.area

    park_coverage['group'] = 0  # default value
    park_coverage.loc[park_coverage['area'] > 100000000, 'group'] = 1 # assign 1 to the largest polygon, aka the one that is not a polygon

    # dissolve all polygons from layer2 into one single polygon
    #park_coverage = park_coverage.dissolve(by="group", as_index=False) # *** fix so that all group = 0 are not lost in this step




    return park_coverage
park_coverage = OTHER_STATS_park_coverage()
park_coverage.to_file("data/VARIABLES_NEW.gpkg", layer="park_coverage", driver="GPKG", mode="w")

# ==== PARK MAINTENANCE ====
def THEME_park_maintenance_to_layer2(layer2):

    # start here


    return layer2
layer2 = THEME_park_maintenance_to_layer2(layer2)



layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_temporary", driver="GPKG", mode="w")








