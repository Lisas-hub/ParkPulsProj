
import geopandas as gpd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import numpy as np
from sklearn.preprocessing import StandardScaler
import pandas as pd
import os
from statsmodels.stats.outliers_influence import variance_inflation_factor

# TO DO
# change some variables normalized by area (_per_ha) to be standardized too or instead?
# what exactly is in amenity_diversity? just pts within parks or are some (like toilets) with X m of parks also included?


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

# =============================
# === model specification ===

#BLOCK_1_base = [
#    #"park_area",                   # offset park_area instead to avoid modelling park use
#    "TotPop_weighted",              # moved to block socioeconomic
#]

BLOCK_2_amenities = [
    "amenity_diversity",             # diversity instead of all individual amenity_X per ha
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
    "MedianInk_weighted",     # or "MedianInk_weighted_avg" or otherwise median income (standardized)
    "AGG_Alder_0_15_per_ha",  # or get % children (0-15)?
    # "AGG_Alder_65_per_ha"   # or get % elderly (+65)?
    #"TotPop_weighted",
]

BLOCK_6_accessibility = [
    "distance_to_city_center_km",  # change coordinates of city center? (in VARIABLES_accessibility)
    "transport_points_per_ha",     # points represent subway entrances and bus stops
    "transport_type_diversity",    # output: 0 = no public transport nearby; 1 = only bus or only subway; 2 = both bus + subway
]

# BLOCKS = [
#     #("Base", BLOCK_1_base),
#     ("Amenities", BLOCK_2_amenities),
#     ("Environment", BLOCK_3_environment),
#     ("Safety", BLOCK_4_safety),
#     ("Socioeconomic", BLOCK_5_socioeconomic),
#     ("Accessibility", BLOCK_6_accessibility)
# ]

BLOCKS_BY_CATEGORY = {
    "praise": [
        ("Amenities", BLOCK_2_amenities),
        ("Socioeconomic", BLOCK_5_socioeconomic),
        #("Socioeconomic", ["MedianInk_weighted"]),  # PS! såhär kan man även lägga till enstaka variable från ett block om man inte vill inkludera alla!
    ],
    "complaints": [
        ("Amenities", BLOCK_2_amenities),
        ("Safety", BLOCK_4_safety),
        ("Environment", BLOCK_3_environment),
    ],
    "ideas": [
        #("Accessibility", BLOCK_6_accessibility),
        ("Socioeconomic", BLOCK_5_socioeconomic),
        #("Amenities", BLOCK_2_amenities)
    ]
}

# ===============
# === scaling ===

continuous_vars = [
    #"park_area",
    "amenity_diversity",
    "Temp_max_upper",
    "max_noise",
    "crime_per_hectare",
    "avg_Unsafe_NBHD_density",
    "lighting_coverage",
    "MedianInk_weighted",
    "AGG_Alder_0_15_per_ha",
    #"TotPop_weighted",         # removed because it correlates with income
    #"AGG_Alder_65_per_ha",
    "distance_to_city_center_km",
    "transport_points_per_ha"
]

scale_cols = [v for v in continuous_vars if v in gdf.columns]

scaler = StandardScaler()
gdf[scale_cols] = scaler.fit_transform(gdf[scale_cols])

# ==========================================
# === VIF diagnostics per block (pre-model)
# ==========================================

from statsmodels.stats.outliers_influence import variance_inflation_factor

print("\n=== Pre-model VIF diagnostics per block ===\n")

def compute_vif(df, variables):
    X = df[variables].dropna()
    if X.shape[1] < 2:
        return None
    vif_data = pd.DataFrame({
        "variable": X.columns,
        "VIF": [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
    })
    return vif_data.sort_values("VIF", ascending=False)

BLOCKS = BLOCKS_BY_CATEGORY[kategori_input]
for block_name, block_vars in BLOCKS:
    print(f"\n--- {block_name} block ---")

    # only keep variables that exist in the dataframe
    vars_existing = [v for v in block_vars if v in gdf.columns]

    if len(vars_existing) < 2:
        print("Not enough variables for VIF.")
        continue

    vif_df = compute_vif(gdf, vars_existing)

    if vif_df is not None:
        print(vif_df)
    else:
        print("VIF not computed.")

# ========================
# === park area offset ===

gdf["log_park_area"] = np.log(gdf["park_area"] + 1)
#offset = gdf["log_park_area"]
gdf["park_area_exposure"] = gdf["park_area"] + 1


# ====================================
# === block-by-block model fitting ===

results = []
current_vars = []

for block_name, block_vars in BLOCKS:

    current_vars += block_vars

    vars_for_formula = current_vars.copy()

    formula = dependent_var + " ~ " + " + ".join(vars_for_formula)
    #formula_glm = dependent_var + " ~ " + " + ".join(vars_for_formula) + " + offset(log_park_area)"
    #formula_zinb = (dependent_var + " ~ " + " + ".join(vars_for_formula))

    print(f"\n--- Fitting model with blocks: {current_vars} ---")

    # ==========
    # complaints

    if kategori_input == "complaints":
        #model = sm.NegativeBinomial.from_formula(    # sm. indicates that it is MLE   but   this does not work anymore, the model breaks so use glm instead
        model = smf.glm(
            formula=formula,
            data=gdf,
            family=sm.families.NegativeBinomial(),
            offset=gdf["log_park_area"]
        ).fit(maxiter=200, disp=False)

    # =====
    # ideas

    elif kategori_input == "ideas":
        model = smf.glm(                        # smf.glm indicates that it is GLM
            formula=formula,
            data=gdf,
            family=sm.families.NegativeBinomial(),
            offset=gdf["log_park_area"]
        ).fit()

    # ======
    # praise

    elif kategori_input == "praise":
        # model = sm.ZeroInflatedNegativeBinomialP.from_formula(
        #     formula=formula,
        #     data=gdf,
        #     #exposure=gdf["park_area_exposure"],
        #     inflation="logit",  # intercept-only zero process
        #     #offset=offset
        # ).fit(method="bfgs", maxiter=200, disp=False)

        zinb_model = sm.ZeroInflatedNegativeBinomialP.from_formula(
            formula=formula,
            data=gdf,
            inflation="logit"
        )

        # align exposure to rows actually used by the model
        exposure_aligned = gdf.loc[
            zinb_model.data.row_labels, "park_area_exposure"
        ]

        model = zinb_model.fit(
            method="bfgs",
            maxiter=200,
            disp=False,
            exposure=exposure_aligned
        )

    print(f"AIC: {model.aic:.2f}")

    results.append({
        "block": block_name,
        "n_vars": len(current_vars),
        "AIC": model.aic,
        "model": model
    })

# ============================
# === compare models (AIC) ===

aic_table = pd.DataFrame(results)[["block", "n_vars", "AIC"]]
print("\nAIC comparison:")
print(aic_table)

# ==================================
# === select and show best model ===

valid_results = [r for r in results if np.isfinite(r["AIC"])]
best = min(results, key=lambda x: x["AIC"])

print("\n✓ Best model:")
print(f"Block: {best['block']}")
print(f"AIC: {best['AIC']:.2f}\n")

print(best["model"].summary())

# ===================================
# === check collinearity with VIF ===

print("\n=== VIF diagnostics (final model) ===\n")

# Get names of regressors from the fitted model
exog_names = best["model"].model.exog_names

# Remove intercept and model-specific parameters
exclude_terms = ["Intercept", "inflate_const", "alpha"]
vif_vars = [v for v in exog_names if v not in exclude_terms]

# Build design matrix from gdf
X = gdf[vif_vars].dropna()

# Compute VIF
vif_df = pd.DataFrame({
    "variable": X.columns,
    "VIF": [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
})

print(vif_df.sort_values("VIF", ascending=False))


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






