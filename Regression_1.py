
import geopandas as gpd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import numpy as np
from sklearn.preprocessing import StandardScaler
import pandas as pd
import os


# ABOUT THE DATA
# PRAISE:       mean =  0.278   variance =     0.896   proportion of zeros = 84.8%   (lots of zeros -> zero-inflated -> Zero-Inflated Negative Binomial (ZINB))
# COMPLAINTS:   mean = 71.464   variance = 30608.41    proportion of zeros =  3.9%   (variance is higher than mean = overdispersion -> negative binomial regression)
# IDEAS:        mean =  0.766   variance =     3.815   proportion of zeros = 70.6%   (overdispersion + zero-inflated -> Negative Binomial, then Zero-Inflated NB as comparison)

OUTPUT_PATH = "data/regression_output/plots"
os.makedirs(OUTPUT_PATH, exist_ok=True)

# =================
# === load data ===

gdf = gpd.read_file("data/regression_output/VARIABLES_regression.gpkg", layer="VARIABLES_regression")

# ===========================
# === outcome diagnostics ===

OUTCOMES = {
    "complaints": "error_complaint_count",
    "ideas": "idea_count",
    "praise": "praise_count"
}

print("\n=== Count outcome diagnostics ===\n")

for name, col in OUTCOMES.items():
    y = gdf[col].dropna()

    mean_y = y.mean()
    var_y = y.var()
    prop_zero = (y == 0).mean()

    print(f"{name.upper()}")
    print(f"  N               : {len(y)}")
    print(f"  Mean            : {mean_y:.3f}")
    print(f"  Variance        : {var_y:.3f}")
    print(f"  Variance / Mean : {(var_y / mean_y) if mean_y > 0 else np.nan:.3f}")
    print(f"  Proportion zero : {prop_zero:.3f}\n")


# =================================
# === choose dependent variable ===

DEPENDENT_VARIABLE = {
    "complaints": "error_complaint_count",
    "ideas": "idea_count",
    "praise": "praise_count"
}

kategori_input = input("☆☆☆ Enter Kategori (complaints, ideas or praise): ").strip().lower()

if kategori_input not in DEPENDENT_VARIABLE:
    print("❌ Invalid category. Choose complaints, ideas, or praise. ❌")
    exit()

dependent_var = DEPENDENT_VARIABLE[kategori_input]
print(f"\n✓ Running model for: {dependent_var}\n")

# ========================
# === park area offset ===

USE_OFFSET = False  # set False to study park size effect for ideas

# =============================
# === model specification ===

BLOCK_1_base = [
    #"park_area",                    # offset park_area or not? ***
    "TotPop_weighted",
]

BLOCK_2_amenities = [
    "amenity_diversity",             # diversity instead of all individual per ha variables, OBS! does not include FOOD_ESTABLISHMENTS
    # "total_food_establishments"   # add food_establishments_per_ha instead? or include in amenity_diversity
]

BLOCK_3_environment = [
    "Temp_max_upper",
    "max_noise",
    # % impervious surface           # (or % tree coverage but i don't think i have great data for the latter)
    # % of park area protected
]

BLOCK_4_safety = [
    "crime_per_hectare",  # change to crimes per ha per year? or per 1000 nearby residents
    "avg_Unsafe_NBHD_density",  # change to mean safety survey score (standardized)?
    "lighting_coverage",  # same as % of park area within lit zones?
]

BLOCK_5_socioeconomic = [
    # use max 1-2 variables
    "MedianInk_weighted",    # or "MedianInk_weighted_avg" or otherwise median income (standardized)
    "AGG_Alder_0_15_per_ha",  # or get % children (0-15)?
    # "AGG_Alder_65_per_ha"  # or get % elderly (+65)?
]

BLOCK_6_accessibility = [
    # add this block last if at all
    "distance_to_city_center_km",  # change coordinates of city center? (in VARIABLES_accessibility)
    "transport_points_per_ha",  # points represent subway entrances and bus stops
    "transport_type_diversity",
    # output: 0 = no public transport nearby; 1 = only bus or only subway; 2 = both bus + subway
]

BLOCKS = [
    ("Base", BLOCK_1_base),
    ("Amenities", BLOCK_2_amenities),
    ("Environment", BLOCK_3_environment),
    ("Safety", BLOCK_4_safety),
    ("Socioeconomic", BLOCK_5_socioeconomic),
    ("Accessibility", BLOCK_6_accessibility)
]

# ===============
# === scaling ===

if kategori_input == "praise":
    print("→ Scaling continuous predictors (required for ZINB)")

    scale_cols = [
        "park_area", "TotPop_weighted",
        "Temp_max_upper", "max_noise",
        "crime_per_hectare", "avg_Unsafe_NBHD_density",
        "lighting_coverage",
        "MedianInk_weighted",
        "AGG_Alder_0_15_per_ha",
        "AGG_Alder_65_per_ha",
        "distance_to_city_center_km",
        "transport_points_per_ha"
    ]

    scaler = StandardScaler()
    gdf[scale_cols] = scaler.fit_transform(gdf[scale_cols])

if kategori_input == "complaints":
    scale_cols = [
        "TotPop_weighted",
        "amenity_diversity",
        "Temp_max_upper",
        "max_noise",
        "crime_per_hectare",
        "avg_Unsafe_NBHD_density",
        "lighting_coverage",
        "MedianInk_weighted",
        "AGG_Alder_0_15_per_ha",
        "distance_to_city_center_km",
        "transport_points_per_ha",
    ]

    scaler = StandardScaler()
    gdf[scale_cols] = scaler.fit_transform(gdf[scale_cols])


# =========================================
# === offset (optional, OFF by default) ===

if USE_OFFSET:
    gdf["log_park_area"] = np.log(gdf["park_area_raw"] + 1)
    offset = gdf["log_park_area"]
else:
    offset = None

# ====================================
# === block-by-block model fitting ===

results = []
current_vars = []

for block_name, block_vars in BLOCKS:

    current_vars += block_vars

    vars_for_formula = current_vars.copy()

    if kategori_input in ["ideas", "praise"]:
        vars_for_formula = ["park_area"] + vars_for_formula # this includes park_area as a regular variable for praise and ideas (but for complaints it is used as exposure)

    formula = dependent_var + " ~ " + " + ".join(vars_for_formula)

    print(f"\n--- Fitting model with blocks: {current_vars} ---")

    # -------------------------
    # complaints
    # -------------------------
    if kategori_input == "complaints":

        exposure = gdf["park_area"] + 1  # must be > 0

        model=sm.NegativeBinomial.from_formula(     # to fix issue with fixed alpha to default = 1
            formula=formula,
            data=gdf,
            exposure = exposure
        ).fit(maxiter=200, disp=False)

    # -------------------------
    # ideas
    # -------------------------
    elif kategori_input == "ideas":
        model = smf.glm(
            formula=formula,
            data=gdf,
            family=sm.families.NegativeBinomial(),
            offset=offset
        ).fit()

    # -------------------------
    # praise
    # -------------------------
    elif kategori_input == "praise":
        model = sm.ZeroInflatedNegativeBinomialP.from_formula(
            formula=formula,
            data=gdf,
            inflation="logit"  # intercept-only zero process
        ).fit(method="bfgs", maxiter=200, disp=False)

    print(f"AIC: {model.aic:.2f}")

    results.append({
        "block": block_name,
        "n_vars": len(current_vars),
        "AIC": model.aic,
        "model": model
    })

# =============================
# === compare models (AIC) ===
# =============================

aic_table = pd.DataFrame(results)[["block", "n_vars", "AIC"]]
print("\nAIC comparison:")
print(aic_table)

# =============================
# === select and show best model ===
# =============================

best = min(results, key=lambda x: x["AIC"])

print("\n✓ Best model:")
print(f"Block: {best['block']}")
print(f"AIC: {best['AIC']:.2f}\n")

print(best["model"].summary())




# ================================
# === Plot significant predictors (robust) ===
# ================================

import matplotlib.pyplot as plt
import seaborn as sns

# Get coefficients and p-values depending on model type
coefs = best["model"].params
pvals = best["model"].pvalues

# Remove intercept and alpha
coefs = coefs.drop(["Intercept", "alpha"], errors="ignore")
pvals = pvals.drop(["Intercept", "alpha"], errors="ignore")

# Filter significant predictors
sig_predictors = pvals[pvals < 0.05].index

if len(sig_predictors) == 0:
    print("No significant predictors to plot.")
else:
    print("\n✓ Significant predictors to plot:")
    print(sig_predictors)

    for var in sig_predictors:
        plt.figure(figsize=(6,4))
        sns.scatterplot(
            x=gdf[var],
            y=gdf[dependent_var],
            alpha=0.6
        )
        sns.regplot(
            x=gdf[var],
            y=gdf[dependent_var],
            scatter=False,
            color="red"
        )
        plt.xlabel(var)
        plt.ylabel(dependent_var)
        plt.title(f"{dependent_var} vs {var} (significant)")
        plt.tight_layout()
        plt.savefig(f"{OUTPUT_PATH}/{kategori_input}_{var}.png", dpi=300, bbox_inches="tight")
        plt.show()






