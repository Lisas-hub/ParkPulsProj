
import geopandas as gpd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import numpy as np
from sklearn.preprocessing import StandardScaler
import pandas as pd
import os
import matplotlib.pyplot as plt
from statsmodels.stats.outliers_influence import variance_inflation_factor
import seaborn as sns
from libpysal.weights import DistanceBand, W, KNN, lag_spatial
from esda.moran import Moran
import warnings

warnings.filterwarnings(
    "ignore",
    message="The weights matrix is not fully connected"
)

warnings.filterwarnings(
    "ignore",
    message="Negative binomial dispersion parameter alpha not set"
) # this happens because the use of GLM (smf.glm) for them NB regression and it is acceptable to have a set alpha. Also, fixing this error requires smf.negativebinomial instead which estimates alpha but is more unstable and in this case it blew up everything to use it.

# ====================
# === OUTPUT PATHS ===

OUTPUT_PATH_PLOTS = "data/regression_output/plots"
OUTPUT_PATH_GPKG = "data/regression_output"

os.makedirs(OUTPUT_PATH_PLOTS, exist_ok=True)
os.makedirs(OUTPUT_PATH_GPKG, exist_ok=True)

# =======================
# === VARIABLE LABELS ===

VAR_LABELS = {
    "amenity_diversity": "Amenity diversity",
    "max_noise": "Max noise",
    "avg_soc_coh_density": "Social cohesion",
    "crime_per_hectare": "Crime per ha",
    "avg_Unsafe_NBHD_density": "Unsafe neighborhood density",
    "lighting_coverage": "Lighting coverage",
    "MedianInk_weighted": "Median income",
    "TotPop_weighted": "Population density",
    "AGG_Alder_0_15_per_ha": "Children aged 0-15y density",
    "distance_to_city_center_km": "Distance to city centre",
    "transport_type_diversity": "Transport diversity",
    "park_area": "Park area"
}

# =================
# === LOAD DATA ===

gdf = gpd.read_file(
    "data/regression_output/VARIABLES_regression.gpkg",
    layer="VARIABLES_regression"
)

gdf["total_count"] = (
    gdf["error_complaint_count"]
    + gdf["idea_count"]
    + gdf["praise_count"]
)

if gdf.crs.is_geographic:
    gdf = gdf.to_crs(epsg=3006)

# =======================
# === VARIABLES SETUP ===

OUTCOMES = {
    "complaints": "error_complaint_count",
    "ideas": "idea_count",
    "praise": "praise_count",
    "total": "total_count"
}

BASE_VARS = [
    "amenity_diversity",
    "max_noise",
    "avg_soc_coh_density",
    "crime_per_hectare",
    "avg_Unsafe_NBHD_density",
    "lighting_coverage",
    "MedianInk_weighted",
    "AGG_Alder_0_15_per_ha",
    "distance_to_city_center_km",
    "transport_type_diversity",
    "park_area"
]

# ==============
# === BLOCKS ===

BLOCKS = [
    ("Amenities", ["amenity_diversity"]),
    ("Environment", ["max_noise"]),
    ("Safety", [
        "lighting_coverage",
        "crime_per_hectare",
        "avg_Unsafe_NBHD_density",
        "avg_soc_coh_density"
    ]),
    ("Socioeconomic", [
        "MedianInk_weighted",
        "TotPop_weighted",
        "AGG_Alder_0_15_per_ha"
    ]),
    ("Accessibility", [
        "distance_to_city_center_km",
        "transport_type_diversity"
    ])
]

# =============================
# === CONDITION NUMBER FUNC ===

def condition_number(X):
    """Compute condition number of design matrix"""
    X = np.asarray(X)
    _, s, _ = np.linalg.svd(X, full_matrices=False)
    return s[0] / s[-1]

# ==============================
# === SPATIAL WEIGHTS HELPER ===

def fix_islands(w, gdf, k=3):
    if len(w.islands) == 0:
        return w
    print(f"⚠️ Found {len(w.islands)} islands → fixing")
    knn = KNN.from_dataframe(gdf, k=k)
    for island in w.islands:
        neighbors = knn.neighbors[island]
        w.neighbors[island] = neighbors
        w.weights[island] = [1] * len(neighbors)
    return w

# ==========================
# === CORRELATION MATRIX ===

gdf_base = gdf.dropna(subset=BASE_VARS).copy()

corr_df = gdf_base[BASE_VARS].corr()

# rename for plotting
corr_df.rename(index=VAR_LABELS, columns=VAR_LABELS, inplace=True)

plt.figure(figsize=(10, 8))
sns.heatmap(corr_df, annot=True, cmap="coolwarm", center=0)
plt.title("Correlation Matrix (Predictors)")
plt.tight_layout()
plt.savefig(f"{OUTPUT_PATH_PLOTS}/correlation_matrix.png", dpi=300)
plt.close()

# =======================
# === SPATIAL WEIGHTS ===

gdf_base = gdf.dropna(subset=BASE_VARS).copy()
gdf_base = gdf_base.reset_index(drop=True)

# ====================
# === MORAN ON RAW ===

print("\n=== Moran's I (RAW) ===")

for name, col in OUTCOMES.items():

    df_moran = gdf_base.dropna(subset=[col]).copy()
    df_moran = df_moran.reset_index(drop=True)

    w_moran = DistanceBand.from_dataframe(
        df_moran,
        threshold=1000,
        binary=True,
        silence_warnings=True
    )

    w_moran = fix_islands(w_moran, df_moran)
    w_moran.transform = "R"

    y = df_moran[col].values

    mi = Moran(y, w_moran)

    print(f"{name}: I={mi.I:.3f}, p={mi.p_sim:.4f}")

# ===============================
# === COUNT MODEL DIAGNOSTICS ===

print("\n=== Poisson vs NB vs ZINB diagnostics ===")

for kategori, col in OUTCOMES.items():

    print(f"\n--- {kategori.upper()} ---")

    formula = f"{col} ~ 1"

    # --- Poisson ---
    poisson_model = smf.glm(
        formula=formula,
        data=gdf,
        family=sm.families.Poisson(),
        offset=np.log(gdf["park_area"] + 1)
    ).fit()

    dispersion = poisson_model.pearson_chi2 / poisson_model.df_resid

    mu_pois = poisson_model.predict()
    pred_zero_pois = np.exp(-mu_pois).mean()

    # --- NB ---
    nb_model = smf.glm(
        formula=formula,
        data=gdf,
        family=sm.families.NegativeBinomial(),
        offset=np.log(gdf["park_area"] + 1)
    ).fit()

    mu_nb = nb_model.predict()
    alpha = nb_model.scale if hasattr(nb_model, "scale") else 1
    pred_zero_nb = (1 / (1 + alpha * mu_nb)) ** (1 / alpha)
    pred_zero_nb = pred_zero_nb.mean()

    observed_zero = (gdf[col] == 0).mean()

    print(f"Observed zeros     : {observed_zero:.3f}")
    print(f"Pred zeros Poisson : {pred_zero_pois:.3f}")
    print(f"Pred zeros NB      : {pred_zero_nb:.3f}")
    print(f"Dispersion         : {dispersion:.2f}")

    print("\nAIC:")
    print(f"Poisson : {poisson_model.aic:.2f}")
    print(f"NB      : {nb_model.aic:.2f}")

    # --- ZINB ---
    if observed_zero > pred_zero_nb + 0.1:

        zinb_model = sm.ZeroInflatedNegativeBinomialP.from_formula(
            formula,
            gdf,
            inflation="logit"
        ).fit(method="bfgs", maxiter=200, disp=False)

        print(f"ZINB    : {zinb_model.aic:.2f}")

        if zinb_model.aic < nb_model.aic:
            print("→ ZINB preferred")
        else:
            print("→ NB adequate")

    else:
        print("→ No strong zero inflation")

# ==============================
# === MAIN LOOP (ALL MODELS) ===

for kategori, dep in OUTCOMES.items():

    print(f"\n\n===== {kategori.upper()} =====")

    gdf_model = gdf.dropna(subset=[dep] + BASE_VARS).copy()
    gdf_model.reset_index(drop=True, inplace=True)

    # ===============
    # === SCALING ===

    scaler = StandardScaler()
    gdf_model[BASE_VARS] = scaler.fit_transform(gdf_model[BASE_VARS])

    # ===============
    # === w_model ===

    w_model = DistanceBand.from_dataframe(
        gdf_model,
        threshold=1000,
        binary=True,
        silence_warnings=True
    )

    w_model = fix_islands(w_model, gdf_model)
    w_model = W(w_model.neighbors, w_model.weights)  # rebuild clean
    w_model.transform = "R"

    # ============================
    # === SPATIAL LAG VARIABLE ===

    gdf_model["spatial_lag_y"] = lag_spatial(
        w_model,
        gdf_model[dep].fillna(0)
    )

    # scaled
    gdf_model["spatial_lag_y"] = StandardScaler().fit_transform(
        gdf_model[["spatial_lag_y"]]
    )

    # ==============
    # === OFFSET ===

    gdf_model["log_park_area"] = np.log(gdf_model["park_area"] + 1)

    # ==================
    # === MODEL RUNS ===

    results = []
    current_vars = []

    for block_name, block_vars in BLOCKS:

        current_vars += block_vars

        print(f"\n--- {block_name} ---")

        # condition number
        cn = condition_number(gdf_model[current_vars])
        print(f"Condition number: {cn:.2f}")

        ####################
        X_block = gdf_model[block_vars]
        cn = condition_number(X_block)
        print(f"{block_name} condition number: {cn:.2f}")

        # if high (> 1000), print correlations and VIF
        if cn > 1000:
            print(f"⚠️ High condition number detected in {block_name}")
            # correlation matrix
            corr_sub = X_block.corr()

            # save figure
            plt.figure(figsize=(8, 6))
            sns.heatmap(corr_sub, annot=True, cmap='coolwarm', center=0)
            plt.title(f'Correlation Matrix: {block_name}')
            plt.tight_layout()
            plt.savefig(f"{OUTPUT_PATH_PLOTS}/corr_matrix_{kategori}_{block_name}.png", dpi=300)
            plt.close()

            # print variable pairs with |r| > 0.7
            strong_corrs = [(i, j, corr_sub.loc[i, j])
                            for i in block_vars
                            for j in block_vars
                            if i < j and abs(corr_sub.loc[i, j]) > 0.7]
            if strong_corrs:
                print("Strong correlations (|r|>0.7):")
                for var1, var2, r in strong_corrs:
                    print(f"  {var1} ↔ {var2}: r = {r:.2f}")
            else:
                print("No strong correlations (|r|>0.7) in this block.")

            # VIF as before
            vif_data = pd.DataFrame({
                'Variable': block_vars,
                'VIF': [variance_inflation_factor(X_block.values, i) for i in range(X_block.shape[1])]
            })
            print(f"VIF for {block_name}:\n", vif_data)
        ####################

        for spatial in [False, True]:

            label = "SPATIAL" if spatial else "NO_SPATIAL"

            vars_used = current_vars.copy()
            if spatial:
                vars_used = ["spatial_lag_y"] + vars_used

            formula = dep + " ~ " + " + ".join(vars_used)

            # === use glm and fixed alpha (acceptable) ===
            try:
                model = smf.glm(
                    formula=formula,
                    data=gdf_model,
                    family=sm.families.NegativeBinomial(),
                    offset=gdf_model["log_park_area"]
                ).fit(maxiter=200, disp=False)

                # store results only if fit succeeds
                results.append({
                    "block": block_name,
                    "spatial": spatial,
                    "AIC": model.aic,
                    "model": model
                })

            except Exception as e:
                print(f"{label} model for {block_name} failed: {e}")

            # === use maximum likelihood, smf.negativebinomial, estimate alpha rather than glm and fixed alpha (blows everything up) ===
            # try:
            #     model = smf.negativebinomial(
            #         formula=formula,
            #         data=gdf_model,
            #         offset=gdf_model["log_park_area"]
            #     ).fit(maxiter=200, disp=False)
            #
            #     if not np.isfinite(model.aic):
            #         raise ValueError("Invalid AIC")
            #
            #     print(f"{label} AIC: {model.aic:.2f}")
            #
            #     results.append({
            #         "block": block_name,
            #         "AIC": model.aic,
            #         "model": model,
            #         "spatial": spatial
            #     })
            # except Exception as e:
            #     print(f"{label} FAILED: {e}")

        # ==== safely select best model ====
        if results:
            best = min(results, key=lambda x: x["AIC"])
        else:
            print("No valid models found!")
            best = None

    # ==================
    # === BEST MODEL ===

    # AIC table
    if results:  # check for valid models
        aic_table = pd.DataFrame(results)
        aic_table['spatial'] = aic_table['spatial'].map({True: 'Spatial', False: 'No_Spatial'})

        # pivot for nicer view
        aic_pivot = aic_table.pivot(index='block', columns='spatial', values='AIC')
        aic_pivot = aic_pivot.reindex([b[0] for b in BLOCKS])
        print(f"\nAIC table for {kategori.upper()}:\n", aic_pivot)

        # # save CSV
        # aic_pivot.to_csv(f"{PATH}/AIC_table_{kategori}.csv")

    # summary of best model
    best = min(results, key=lambda x: x["AIC"])
    print(f"\nBEST: {best['block']} ({'spatial' if best['spatial'] else 'no spatial'})")

    model = best["model"]

    # print regression table for best model
    print(f"\nBest model for {kategori.upper()}: {best['block']} ({'Spatial' if best['spatial'] else 'No Spatial'})\n")
    print(best['model'].summary())

    # # optionally save text summary to file
    # with open(f"{PATH}/regression_summary_{kategori}.txt", "w") as f:
    #     f.write(str(best['model'].summary()))

    # ==========================
    # === MORAN ON RESIDUALS ===

    resid = pd.Series(model.resid_response, index=gdf_model.index)
    df_resid = gdf_model.loc[~np.isnan(resid)].copy()
    df_resid = df_resid.reset_index(drop=True)

    w_resid = DistanceBand.from_dataframe(
        df_resid,
        threshold=1000,
        binary=True,
        silence_warnings=True
    )

    w_resid = fix_islands(w_resid, df_resid)
    w_resid.transform = "R"

    resid_clean = df_resid["std_resid"] if "std_resid" in df_resid else resid.loc[df_resid.index]
    mi = Moran(resid_clean.values, w_resid)

    print(f"Moran residuals: I={mi.I:.3f}, p={mi.p_sim:.4f}")

    # =========================
    # === SIGNIFICANT PLOTS ===

    coefs = model.params
    pvals = model.pvalues

    sig = pvals[pvals < 0.05].index.tolist()
    sig = [v for v in sig if v not in ["Intercept","spatial_lag_y"]]

    for var in sig:

        x_vals = np.linspace(
            gdf_model[var].min(),
            gdf_model[var].max(),
            100
        )

        pred_df = pd.DataFrame({
            v: (x_vals if v==var else gdf_model[v].mean())
            for v in model.model.exog_names
            if v not in ["Intercept", "alpha"]
        })

        preds = model.predict(pred_df,
                              offset=np.full(100, gdf_model["log_park_area"].mean()))

        plt.figure()

        sns.scatterplot(
            x=gdf_model[var],
            y=gdf_model[dep],
            alpha=0.3
        )

        plt.plot(x_vals, preds, color="red")

        plt.xlabel(VAR_LABELS.get(var, var))
        plt.ylabel(dep)

        plt.savefig(f"{OUTPUT_PATH_PLOTS}/{kategori}_{var}.png")
        plt.close()

    # ===========================
    # === OBS VS PRED SCATtER ===

    y_obs = gdf_model[dep]
    y_pred = model.predict(offset=gdf_model["log_park_area"])

    plt.figure()
    sns.scatterplot(x=y_obs, y=y_pred)

    m = max(y_obs.max(), y_pred.max())
    plt.plot([0,m],[0,m],'r--')

    plt.xlabel("Observed")
    plt.ylabel("Predicted")

    plt.savefig(f"{OUTPUT_PATH_PLOTS}/{kategori}_obs_pred.png")
    plt.close()

    # ================
    # === OUTLIERS ===

    resid = y_obs - y_pred

    gdf_model["std_resid"] = (resid - resid.mean()) / resid.std()
    gdf_model["outlier"] = np.abs(gdf_model["std_resid"]) > 2

    print(f"Outliers: {gdf_model['outlier'].sum()}")

    gdf_output = gdf.merge(
        gdf_model[["group","outlier"]],
        on="group",
        how="left"
    )

    gdf_output.to_file(
        f"{OUTPUT_PATH_GPKG}/output_{kategori}.gpkg",
        layer="outliers",
        driver="GPKG"
    )