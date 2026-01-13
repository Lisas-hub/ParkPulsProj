
import geopandas as gpd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import numpy as np

gdf = gpd.read_file("data/regression_output/VARIABLES_regression.gpkg", layer="VARIABLES_regression")

PREDICTORS = [
    "park_area",
    "Temp_max_upper",
    "play_ground_per_ha"
]

formula = """
error_complaint_count ~ park_area + Temp_max_upper + play_ground_per_ha
"""

model = smf.glm(
    formula=formula,
    data=gdf,
    family=sm.families.NegativeBinomial()
).fit()

print(model.summary())


# addition
gdf["log_area"] = np.log(gdf["park_area"])

model = smf.glm(
    formula=formula,
    data=gdf,
    family=sm.families.NegativeBinomial(),
    offset=gdf["log_area"]
).fit()

# interpretation: “Given park size, which characteristics generate more complaints?”

# Coefficient β = 0.3 means:     exp(0.3) ≈ 1.35 → 35% more expected comments

