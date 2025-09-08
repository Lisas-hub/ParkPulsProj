
import geopandas as gpd
import pandas as pd

layer2 = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

# MOVED TO VARIABLES_environment

layer2.to_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_noise_pollution", driver="GPKG", mode="w")


