
import geopandas as gpd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import numpy as np
from sklearn.preprocessing import StandardScaler
import pandas as pd


# ABOUT THE DATA
# PRAISE:       mean =  0.278   variance =     0.896   proportion of zeros = 84.8%   (lots of zeros -> zero-inflated -> Zero-Inflated Negative Binomial (ZINB))
# COMPLAINTS:   mean = 71.464   variance = 30608.41    proportion of zeros =  3.9%   (variance is higher than mean = overdispersion -> negative binomial regression)
# IDEAS:        mean =  0.766   variance =     3.815   proportion of zeros = 70.6%   (overdispersion + zero-inflated -> Negative Binomial, then Zero-Inflated NB as comparison)

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

USE_OFFSET = False  # set False to study park size effect

# =============================
# === load and prepare data ===

gdf = gpd.read_file("data/regression_output/VARIABLES_regression.gpkg", layer="VARIABLES_regression")

# drop missing outcome
#gdf = gdf.dropna(subset=[dependent_var])

gdf["park_area_raw"] = gdf["park_area"]


# =============================
# === model specification ===

BLOCK_1_base = [
    "park_area",                    # offset park_area or not? ***
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
    formula = dependent_var + " ~ " + " + ".join(current_vars)

    print(f"\n--- Fitting model with blocks: {current_vars} ---")

    # -------------------------
    # complaints & ideas
    # -------------------------
    if kategori_input in ["complaints", "ideas"]:
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



# formula = dependent_var + " ~ " + " + ".join(BLOCK_1_base)
#
# # =============================
# # === fit model by category ===
#
# if kategori_input == "complaints":
#     print("→ Using Negative Binomial regression")
#
#     model = smf.glm(
#         formula=formula,
#         data=gdf,
#         family=sm.families.NegativeBinomial(),
#         offset=offset
#     ).fit()
#
# elif kategori_input == "ideas":
#     print("→ Using Negative Binomial regression (compare with ZINB later)")
#
#     model = smf.glm(
#         formula=formula,
#         data=gdf,
#         family=sm.families.NegativeBinomial(),
#         offset=offset
#     ).fit()
#
# elif kategori_input == "praise":
#     print("→ Using Zero-Inflated Negative Binomial regression")
#
#     # scaling, aka transform predictors to fix issues with nan in the output, formula used is xscaled = X-mean(x)/sd(x)
#     #for col in ["park_area", "Temp_max_upper", "TotPop_weighted"]:
#     #    gdf[col] = (gdf[col] - gdf[col].mean()) / gdf[col].std()
#
#     model = sm.ZeroInflatedNegativeBinomialP.from_formula(
#         formula=formula,
#         data=gdf,
#         inflation="logit"   # models zero vs non-zero process
#     ).fit(method="bfgs", maxiter=200)
#
# # =============================
# # === output ===
#
# print(model.summary())




# COMPLAINTS
#                    Generalized Linear Model Regression Results
# =================================================================================
# Dep. Variable:     error_complaint_count   No. Observations:                 1082
# Model:                               GLM   Df Residuals:                     1078
# Model Family:           NegativeBinomial   Df Model:                            3
# Link Function:                       Log   Scale:                          1.0000
# Method:                             IRLS   Log-Likelihood:                -5154.1
# Date:                   Mon, 26 Jan 2026   Deviance:                       1616.6
# Time:                           10:51:58   Pearson chi2:                 1.57e+03
# No. Iterations:                       71   Pseudo R-squ. (CS):             0.6413 <- Very strong model (pseudo R² ≈ 0.64)
# Covariance Type:               nonrobust
# ===================================================================================
#                       coef    std err          z      P>|z|      [0.025      0.975]
# -----------------------------------------------------------------------------------
# Intercept          -0.9738      0.676     -1.441      0.150      -2.299       0.351   Intercept not significant but this is not necessarily important in this model
# park_area        2.588e-06   1.04e-07     24.926      0.000    2.38e-06    2.79e-06   Park area           (coef = 2.59e-06, p < 0.001): Larger parks       → more complaints (likely an exposure effect: more space, more things that can go wrong)
# Temp_max_upper      0.1126      0.020      5.537      0.000       0.073       0.152   Maximum temperature (coef = 0.113,    p < 0.001): Hotter conditions  → more complaints
# TotPop_weighted   9.26e-05   5.27e-06     17.567      0.000    8.23e-05       0.000   Population          (coef = 9.26e-05, p < 0.001): More people nearby → more complaints (strongly supports a usage/exposure story)
# ===================================================================================


# IDEAS
#                 Generalized Linear Model Regression Results
# ==============================================================================
# Dep. Variable:             idea_count   No. Observations:                 1082
# Model:                            GLM   Df Residuals:                     1078
# Model Family:        NegativeBinomial   Df Model:                            3
# Link Function:                    Log   Scale:                          1.0000
# Method:                          IRLS   Log-Likelihood:                -1093.9
# Date:                Mon, 26 Jan 2026   Deviance:                       990.60
# Time:                        10:50:35   Pearson chi2:                 1.70e+03
# No. Iterations:                    31   Pseudo R-squ. (CS):             0.3266 <- Moderate fit (pseudo R² ≈ 0.33), expected: idea submission is a rarer and more discretionary behavior
# Covariance Type:            nonrobust
# ===================================================================================
#                       coef    std err          z      P>|z|      [0.025      0.975]
# -----------------------------------------------------------------------------------
# Intercept          -3.0443      1.172     -2.597      0.009      -5.342      -0.747  Intercept (significant and negative)
# park_area        1.274e-06    1.1e-07     11.544      0.000    1.06e-06    1.49e-06  Park area (coef = 1.27e-06, p < 0.001): Larger parks → more ideas (same exposure logic, but effect is weaker than for complaints)
# Temp_max_upper      0.0467      0.035      1.334      0.182      -0.022       0.115  Maximum temperature (not significant): Temperature does not meaningfully affect idea submissions
# TotPop_weighted  8.866e-05   7.28e-06     12.178      0.000    7.44e-05       0.000  Nearby population (coef = 8.87e-05, p < 0.001): Strong positive effect -> More people = more potential idea contributors
# ===================================================================================


# PRAISE (after scaling)
# Optimization terminated successfully.
#          Current function value: 0.539499
#          Iterations: 45
#          Function evaluations: 46
#          Gradient evaluations: 46
#                      ZeroInflatedNegativeBinomialP Regression Results
# =========================================================================================
# Dep. Variable:                      praise_count   No. Observations:                 1082
# Model:             ZeroInflatedNegativeBinomialP   Df Residuals:                     1078
# Method:                                      MLE   Df Model:                            3
# Date:                           Mon, 26 Jan 2026   Pseudo R-squ.:                  0.1179
# Time:                                   11:25:32   Log-Likelihood:                -583.74
# converged:                                  True   LL-Null:                       -661.74
# Covariance Type:                       nonrobust   LLR p-value:                 1.333e-33
# ===================================================================================
#                       coef    std err          z      P>|z|      [0.025      0.975]
# -----------------------------------------------------------------------------------
# inflate_const     -12.2683    121.909     -0.101      0.920    -251.205     226.669
# Intercept          -1.7586      0.091    -19.407      0.000      -1.936      -1.581
# park_area           0.2956      0.099      2.995      0.003       0.102       0.489
# Temp_max_upper      0.0334      0.089      0.375      0.708      -0.142       0.208
# TotPop_weighted     0.6786      0.074      9.167      0.000       0.534       0.824
# alpha               2.1231      0.398      5.335      0.000       1.343       2.903
# ===================================================================================

# PRAISE (original outout)
# C:\Users\lisajos\.conda\envs\park_proj_env\Lib\site-packages\statsmodels\discrete\discrete_model.py:1567: RuntimeWarning: overflow encountered in exp
#   L = np.exp(np.dot(X,params) + exposure + offset)
# C:\Users\lisajos\.conda\envs\park_proj_env\Lib\site-packages\statsmodels\discrete\discrete_model.py:1568: RuntimeWarning: overflow encountered in multiply
#   return -np.dot(L*X.T, X)
# C:\Users\lisajos\.conda\envs\park_proj_env\Lib\site-packages\statsmodels\discrete\discrete_model.py:1478: RuntimeWarning: overflow encountered in exp
#   L = np.exp(np.dot(X,params) + offset + exposure)
# → Using Zero-Inflated Negative Binomial regression
# C:\Users\lisajos\.conda\envs\park_proj_env\Lib\site-packages\statsmodels\base\model.py:595: HessianInversionWarning: Inverting hessian failed, no bse or cov_params available
#   warnings.warn('Inverting hessian failed, no bse or cov_params '
# C:\Users\lisajos\.conda\envs\park_proj_env\Lib\site-packages\scipy\optimize\_optimize.py:1330: OptimizeWarning: NaN result encountered.
#   res = _minimize_bfgs(f, x0, args, fprime, callback=callback, **opts)
# C:\Users\lisajos\.conda\envs\park_proj_env\Lib\site-packages\statsmodels\base\model.py:595: HessianInversionWarning: Inverting hessian failed, no bse or cov_params available
#          Current function value: nan
#          Iterations: 0
#          Function evaluations: 2
#          Gradient evaluations: 2
#   warnings.warn('Inverting hessian failed, no bse or cov_params '
# C:\Users\lisajos\.conda\envs\park_proj_env\Lib\site-packages\statsmodels\base\model.py:607: ConvergenceWarning: Maximum Likelihood optimization failed to converge. Check mle_retvals
#   warnings.warn("Maximum Likelihood optimization failed to "
#                      ZeroInflatedNegativeBinomialP Regression Results
# =========================================================================================
# Dep. Variable:                      praise_count   No. Observations:                 1082
# Model:             ZeroInflatedNegativeBinomialP   Df Residuals:                     1078
# Method:                                      MLE   Df Model:                            3
# Date:                           Mon, 26 Jan 2026   Pseudo R-squ.:                     nan
# Time:                                   11:09:02   Log-Likelihood:                    nan
# converged:                                 False   LL-Null:                       -661.74
# Covariance Type:                       nonrobust   LLR p-value:                       nan
# ===================================================================================
#                       coef    std err          z      P>|z|      [0.025      0.975]
# -----------------------------------------------------------------------------------
# inflate_const            0        nan        nan        nan         nan         nan
# Intercept              nan        nan        nan        nan         nan         nan
# park_area              nan        nan        nan        nan         nan         nan
# Temp_max_upper         nan        nan        nan        nan         nan         nan
# TotPop_weighted        nan        nan        nan        nan         nan         nan
# alpha               0.0500        nan        nan        nan         nan         nan
# ===================================================================================


