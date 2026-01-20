
import geopandas as gpd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import numpy as np
import pandas as pd
from statsmodels.stats.outliers_influence import variance_inflation_factor
import seaborn as sns
import matplotlib.pyplot as plt


# TO DO
# inkludera sentiment på något sätt (MEN INTE som en variable brevid park_area etc!)


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
print(" ")
print(f"✓ Running model for: {dependent_var}")
print(" ")


# =============================
# === load and prepare data ===

gdf = gpd.read_file("data/regression_output/VARIABLES_regression.gpkg", layer="VARIABLES_regression")

# consider using log area instead of raw, if yes, change all park_area to log_area
gdf["log_area"] = np.log(gdf["park_area"])

USE_OFFSET = False  # set False to study park size effect

PREDICTORS_BASE = [
    # park_area is added directly into the formula later
]

ACCESSIBILITY = [
    # add different types- or total public transport count
    # add distance to city center?
]

AMENITIES = [
    # "toilet_per_ha",
    # "bench_per_ha",
    # "bbq_per_ha",
    # "drinking_fountain_per_ha",
    # "waste_paper_bin_per_ha",
    # "picnic_table_per_ha",
    "total_food_establishments",
    # add food_establishments_per_ha?
    #"park_per_ha",   # kolla upp vad detta är
    "dog_park_per_ha",
    # "outdoor_gym_per_ha",
    "play_ground_per_ha",
    # "school_yard_per_ha",
    # "sports_field_per_ha",
    # "skate_park_per_ha",
    # "garden_per_ha",
    # "religious_per_ha"
]

ENVIRONMENT = [
    # "Buskmark",
    # "Odlingsmark",
    # "Skogsmark/trädklädd mark",
    # "Urban gråstruktur",
    # "Urban grönstruktur",
    # "Vatten",
    # "Öppen mark",                              # vad är skillnaden mellan 'öppen mark' och 'öppen yta'?
    # "Skog-/buskmark",
    # "Urban gråstruktur, byggnader",
    # "Urban gråstruktur, infrastruktur",
    # "Urban grönstruktur, vegetation",
    # "Urban grönstruktur, öppen yta",
    # "Urban grönstruktur, övrigt",
    # "Öppen yta",                              # vad är skillnaden mellan 'öppen mark' och 'öppen yta'?
    # "Temp_max_lower",
    "Temp_max_upper",
    # "avg_weighted_mean_temp",
    # add different protected areas (count or area)
    # "40-45",
    # "45-50",
    # "50-55",
    # "55-60",
    # "60-65",
    # "65-70",
    # "70-75",
    # "<40",
    # ">75",
    # "min_noise",
    "max_noise",
    # "range_dba",
]

SAFETY = [
    "lighting_coverage",
    "avg_Unsafe_NBHD_density",       # which crime variable(s) to use?
    # "avg_Crime_victim_density",      # which crime variable(s) to use?
    # "avg_Unsafe_NBHD_density_LOG",   # which crime variable(s) to use?
    # "avg_Crime_victim_density_LOG",  # which crime variable(s) to use?
    # "avg_crime_density",             # which crime variable(s) to use?
    # "crime_per_hectare",             # which crime variable(s) to use?
]

SOCIOECONOMIC = [
    "AGG_Alder_0_6",
    # "AGG_Alder_7_15",
    # "AGG_Alder_16_1",
    # "AGG_Alder_20_2",
    # "AGG_Alder_25_4",
    # "AGG_Alder_45_6",
    # "AGG_Alder_65",
    #"AGG_Alder_Totalt",
    # "AGG_Sverige",
    # "AGG_Norden_uto",
    # "AGG_EU_utom_No",
    # "AGG_Ovriga_var",
    # #"AGG_birthp_Totalt",
    # "Inom",
    # "AGG_Till",
    # "AGG_Fran",
    # "AGG_Inv",
    # "AGG_Utv",
    # "AGG_Fodda",
    # "AGG_Doda",
    #"AGG_migr_Tot_Bef",
    #"intersect_area",      # kolla upp vad detta är, kanske intersect med deso?
    "TotPop_weighted",
    "MedianInk_weighted",
    # "MedianInk_weighted_avg"
]

QUESTIONS = {                      # Are there simply more comments because more people are around? - population, income, accessibility
    "Q1_baseline": PREDICTORS_BASE, # Do complaints vary even before we consider park characteristics? - use population, income, park size or offset
    "Q2_amenities": PREDICTORS_BASE + AMENITIES, # Do 'what parks offer' shape how people talk about them? - use toilets, benches, playgrounds, lighting, etc
    "Q3_environment": PREDICTORS_BASE + ENVIRONMENT, # Do environmental conditions shape complaints or praise? - use noise, temp, shade/greenery, water, etc
    "Q4_safety": PREDICTORS_BASE + SAFETY, # Do perceived or actual safety problems drive complaints? - use crime, lighting, LULC
}



# statsmodels uses Patsy which interprets for example / as a maths operator column need to be renamed
gdf = gdf.rename(columns=lambda c: (
    c.replace(" ", "_")
     .replace("/", "_")
     .replace("-", "_")
     .replace(",", "")
     .replace("<", "lt_")
     .replace(">", "gt_")
))


# NEW RUN LOGIC:
for question, predictors in QUESTIONS.items():
    formula = f"{y} ~ " + " + ".join(predictors)

    model = smf.glm(
        formula=formula,
        data=gdf,
        family=sm.families.NegativeBinomial(),
        offset=gdf["log_area"]   # or None
    ).fit()

    print(f"\n===== {question} =====")
    print(model.summary())


# BELOW IS OLD:

# ===================================================
# ====== correlation matrix + multicollinearity =====
# (because matrix can miss multivariate collinearity)

# printed matrix
corr = gdf[PREDICTORS].corr()
print(corr)
print(" ")

# seaborn matrix
sns.heatmap(corr, annot=True, cmap="coolwarm")
plt.show()

# VIF factor
X = gdf[PREDICTORS].dropna()
X = sm.add_constant(X)

vif_df = pd.DataFrame({
    "variable": X.columns,
    "VIF": [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
})

print(vif_df)
print(" ")
# VIF < 5 is ok
# VIF 5-10 is not ideal
# VIF > 10 is not good, do something about it


# ==================
# === REGRESSION ===

# check for overdispersion
print(gdf["error_complaint_count"].mean())   # 71.46395563770795
print(gdf["error_complaint_count"].var())    # 30636.724416530873
print(" ")

if USE_OFFSET:
    formula = f"{dependent_var} ~ " + " + ".join(PREDICTORS)
    offset = gdf["log_area"]
else:
    formula = f"{dependent_var} ~ park_area + " + " + ".join(PREDICTORS)
    offset = None

model = smf.glm(
    formula=formula,
    data=gdf,
    family=sm.families.NegativeBinomial(),   # negative binomial regression handels overdispersion (when variance is much larger than mean) https://bookdown.org/mike/data_analysis/sec-negative-binomial-regression.html
    offset=offset
).fit()

print(model.summary())




# interpretation: “Given park size, which characteristics generate more complaints?”

# Coefficient β = 0.3 means:     exp(0.3) ≈ 1.35 → 35% more expected comments

