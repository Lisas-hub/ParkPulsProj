
import geopandas as gpd
import pandas as pd
import numpy as np
from scipy.stats import chisquare, friedmanchisquare
import matplotlib.pyplot as plt
from scipy.stats import wilcoxon

# =========
# load data

TYCKTILL_FILTERED_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg"
points_layername = "pts_in_parks_with_topics"

points = gpd.read_file(TYCKTILL_FILTERED_GPKG, layer=points_layername)

points["Inkommet datum"] = pd.to_datetime(
    points["Inkommet datum"],
    format="mixed",
    errors="coerce"
)

#points = points.drop("index_right")

# =========
# groupings

categories = {
    "Praise": ["Beröm"],
    "Ideas": ["Idé"],
    "Error_Complaints": ["Felanmälan", "Klagomål"]
}

seasons = {
    "Winter": [12, 1, 2],
    "Spring": [3, 4, 5],
    "Summer": [6, 7, 8],
    "Autumn": [9, 10, 11]
}

week_groups = {
    #"Weekday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], # Normaliseringen eller whatever som gör att man kan köra 2 och 5 dagar är fortfarande kvar
    "Weekday": ["Tuesday", "Wednesday", "Thursday"],
    #"Weekend": ["Saturday", "Sunday"]
    "Weekend": ["Friday", "Saturday", "Sunday"]
}

hour_groups = {
    "Night": list(range(0, 5)),        # 00 01 02 03 04 05
    "Morning": list(range(6, 11)),     # 06 07 08 09 10 11
    "Midday": list(range(12, 17)),     # 12 13 14 15 16 17
    "Evening": list(range(18, 23))     # 18 19 20 21 22 23
}

park_id = "group"

# ==========
# prepp data

def assign_group(value, groups_dict):
    for grp_name, grp_values in groups_dict.items():
        if value in grp_values:
            return grp_name

temporal_dims = {
    "Season": seasons,
    "Weekday": week_groups,
    "Hour": hour_groups
}

# For hours, we’ll apply assign_group to 'hour' column
# For weekdays, to 'weekday' column
# For seasons, to 'month' column

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import chisquare, friedmanchisquare

categories_dict = {
    "Praise": ["Beröm"],
    "Ideas": ["Idé"],
    "Error_Complaints": ["Felanmälan", "Klagomål"]
}

results = []

for cat_name, cat_values in categories_dict.items():
    # Filter data
    df_cat = points[points["Kategori"].isin(cat_values)].copy()

    # Add month/week/hour columns if not already
    df_cat["month"] = df_cat["Inkommet datum"].dt.month
    df_cat["weekday"] = df_cat["Inkommet datum"].dt.day_name()
    df_cat["hour"] = df_cat["Inkommet datum"].dt.hour

    for temp_name, temp_groups in temporal_dims.items():
        # Decide which column to map
        if temp_name == "Season":
            col = "month"
        elif temp_name == "Weekday":
            col = "weekday"
        elif temp_name == "Hour":
            col = "hour"

        # Assign group
        df_cat[temp_name] = df_cat[col].apply(lambda x: assign_group(x, temp_groups))

        # -------- χ² test --------
        obs_counts = df_cat[temp_name].value_counts().sort_index()

        # Optionally adjust for exposure if Season
        if temp_name == "Season":
            # Count unique days per season for exposure adjustment
            days_df = pd.DataFrame({"date": pd.to_datetime(points["Inkommet datum"].dt.date)})
            days_df["month"] = days_df["date"].dt.month
            days_df[temp_name] = days_df["month"].apply(lambda x: assign_group(x, temp_groups))
            season_day_counts = days_df[temp_name].value_counts().sort_index()
            total_days = season_day_counts.sum()
            expected_counts = (season_day_counts / total_days) * obs_counts.sum()
        else:
            # Equal expected counts for other dimensions
            expected_counts = np.repeat(obs_counts.sum() / len(obs_counts), len(obs_counts))

        chi2_stat, chi2_p = chisquare(obs_counts, f_exp=expected_counts)
        df = len(obs_counts) - 1
        N = obs_counts.sum()

        print(f"\nCategory: {cat_name}, Temporal: {temp_name} - χ² Test")
        print(f"Chi-square statistic: {chi2_stat:.2f}, df = {df}, N = {N}, p = {chi2_p:.4f}")
        print("Observed counts per group:")
        print(obs_counts)
        print("Expected counts per group:")
        print(expected_counts)

        print("Observed percentages per group:")
        print((obs_counts / N * 100).round(1))

        # Optional: Plot observed vs expected
        x = np.arange(len(obs_counts))
        plt.bar(x - 0.2, obs_counts, width=0.4, label="Observed")
        plt.bar(x + 0.2, expected_counts, width=0.4, label="Expected")
        plt.xticks(x, obs_counts.index)
        plt.ylabel("Count")
        plt.title(f"{cat_name} - {temp_name} distribution")
        plt.legend()
        plt.show()

        # -------- Friedman test --------
        # Only makes sense for groupable units, e.g., park_id
        park_id = "group"
        park_grouped = (
            df_cat.groupby([park_id, temp_name])
                .size()
                .unstack(fill_value=0)
        )


        for grp in temp_groups.keys():
            if grp not in park_grouped.columns:
                park_grouped[grp] = 0
        park_grouped = park_grouped[list(temp_groups.keys())]

        # Remove parks with zero across all groups
        park_grouped = park_grouped.loc[park_grouped.sum(axis=1) > 0]

        # Only run test if there is more than 1 park and more than 1 group
        if park_grouped.shape[0] > 0 and park_grouped.shape[1] > 1:

            N = park_grouped.shape[0]  # number of parks
            k = park_grouped.shape[1]  # number of groups
            n_groups = k

            if n_groups == 2:
                # -----------------------------
                # Wilcoxon signed-rank test
                # -----------------------------
                col1, col2 = park_grouped.columns
                stat, p = wilcoxon(park_grouped[col1], park_grouped[col2])

                # Simple effect size (rank-biserial style approximation)
                r = stat / (N * (N + 1) / 2)

                print(f"\n{cat_name} - {temp_name} Wilcoxon test")
                print(f"W = {stat:.2f}, N = {N}, p = {p:.4f}, r = {r:.3f}")

                # Optional: boxplot
                park_grouped.boxplot()
                plt.ylabel("Count per park")
                plt.title(f"{cat_name} - {temp_name} per park (Wilcoxon)")
                plt.show()

            elif n_groups >= 3:
                # -----------------------------
                # Friedman test
                # -----------------------------
                friedman_stat, friedman_p = friedmanchisquare(
                    *[park_grouped[col] for col in park_grouped.columns]
                )

                df = k - 1

                # Kendall's W effect size
                kendalls_W = friedman_stat / (N * df)

                print(f"\n{cat_name} - {temp_name} Friedman test")
                print(f"χ²({df}) = {friedman_stat:.2f}, N = {N}, p = {friedman_p:.4f}, W = {kendalls_W:.3f}")

                # Optional: boxplot
                park_grouped.boxplot()
                plt.ylabel("Count per park")
                plt.title(f"{cat_name} - {temp_name} per park (Friedman)")
                plt.show()

            # if n_groups == 2:
            #     # Wilcoxon signed-rank test for 2 paired groups
            #     col1, col2 = park_grouped.columns
            #     stat, p = wilcoxon(park_grouped[col1], park_grouped[col2])
            #     print(f"{cat_name} - {temp_name} Wilcoxon signed-rank test")
            #     print("Statistic:", stat, "p-value:", p)
            #
            #     # Optional: boxplot
            #     park_grouped.boxplot()
            #     plt.ylabel("Count per park")
            #     plt.title(f"{cat_name} - {temp_name} per park (Wilcoxon)")
            #     plt.show()
            #
            # elif n_groups >= 3:
            #     # Friedman test for 3 or more groups
            #     friedman_stat, friedman_p = friedmanchisquare(*[park_grouped[grp] for grp in park_grouped.columns])
            #     print(f"{cat_name} - {temp_name} Friedman test")
            #     print("Statistic:", friedman_stat, "p-value:", friedman_p)
            #
            #     # Optional: boxplot
            #     park_grouped.boxplot()
            #     plt.ylabel("Count per park")
            #     plt.title(f"{cat_name} - {temp_name} per park (Friedman)")
            #     plt.show()

# # filter to complaints
# complaints = points[points["Kategori"].isin(categories["Error_Complaints"])].copy()
#
# # Extract unique calendar days (for exposure adjustment)
# points["date"] = points["Inkommet datum"].dt.date
# days_df = pd.DataFrame({"date": pd.to_datetime(points["date"].dropna())})
#
# # Assign month and season
# days_df["month"] = days_df["date"].dt.month
#
# # assign season
# def assign_season(month):
#     for season, months in seasons.items():
#         if month in months:
#             return season
#
# days_df["Season"] = days_df["month"].apply(assign_season)
#
# # Count number of unique days per season
# season_day_counts = days_df["Season"].value_counts().sort_index()
# print("Unique days per season (exposure):")
# print(season_day_counts)
#
# complaints["Season"] = complaints["month"].apply(assign_season)
#
# ########
# print(complaints["Inkommet datum"].min())
# print(complaints["Inkommet datum"].max())
# ########
#
# # =======================================================
# # === (1) Are total complaints uneven across seasons? ===
#
# # Chi-Square test - compares total distribution across seasons (individual parks not involved)
#
# # Observed counts per season (instead of assuming 25% per season)
# season_counts = complaints["Season"].value_counts().sort_index()
# print("\nObserved complaints per season:")
# print(season_counts)
#
# # Expected counts based on exposure
# total_days = season_day_counts.sum()
# expected_counts = (season_day_counts / total_days) * season_counts.sum()
# print("\nExpected counts based on days observed per season:")
# print(expected_counts)
#
# # Chi-square test
# chi2_stat, p_value = chisquare(season_counts, f_exp=expected_counts)
# print("\nCHI_SQUARE")
# print("Chi-square statistic:", chi2_stat)
# print("p-value:", p_value)
#
# # plot
# x = np.arange(len(season_counts))
# plt.bar(x - 0.2, season_counts.values, width=0.4, label="Observed")
# plt.bar(x + 0.2, expected_counts.values, width=0.4, label="Expected")
# plt.xticks(x, season_counts.index)
# plt.ylabel("Number of complaints")
# plt.title("Observed vs Expected Complaints by Season")
# plt.legend()
# plt.show()
#
#
# # ==========================================================
# # === (2) Do parks differ in seasonal complaint levels?  ===
#
# # Friedman test
#
# park_season = (
#     complaints
#     .groupby([park_id, "Season"])
#     .size()
#     .unstack(fill_value=0)
# )
#
# for s in seasons.keys():
#     if s not in park_season.columns:
#         park_season[s] = 0
#
# park_season = park_season[["Winter", "Spring", "Summer", "Autumn"]]
#
# friedman_stat, friedman_p = friedmanchisquare(
#     park_season["Winter"],
#     park_season["Spring"],
#     park_season["Summer"],
#     park_season["Autumn"]
# )
#
# print("\nFRIEDMAN")
# print("Friedman statistic:", friedman_stat)
# print("p-value:", friedman_p)
#
# # optionally remove parks with zero complaints across all seasons to clean up the boxplot
# #park_season = park_season.loc[park_season.sum(axis=1) > 0]
#
# # plot
# park_season.boxplot()
# plt.ylabel("Complaint count per park")
# plt.title("Seasonal distribution of complaints per park")
# plt.show()


