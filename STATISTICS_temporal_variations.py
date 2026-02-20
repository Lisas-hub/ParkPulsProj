
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


        ##############
        # ----- Assumption checks: Chi-square -----

        # 1. Minimum expected count
        min_expected = np.min(expected_counts)
        small_expected = np.sum(expected_counts < 5)
        percent_small = small_expected / len(expected_counts) * 100

        print("\nChi-square assumption checks:")
        print(f"Minimum expected count: {min_expected:.2f}")
        print(f"Cells with expected < 5: {small_expected} "
              f"({percent_small:.1f}%)")

        if min_expected < 1:
            print("⚠️ WARNING: Some expected counts < 1. Chi-square invalid.")

        if percent_small > 20:
            print("⚠️ WARNING: More than 20% of cells have expected < 5.")
        ##############


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


                ##################
                differences = park_grouped[col1] - park_grouped[col2]

                differences_nonzero = differences[differences != 0]

                # remove Zero Differences (Wilcoxon requirement)
                if len(differences_nonzero) < 5:
                    print("⚠️ Very few non-zero differences. Wilcoxon may be unstable.")

                # check symmetry
                skewness = differences_nonzero.skew()
                print(f"Skewness of differences: {skewness:.2f}")

                if abs(skewness) > 1:
                    print("⚠️ Differences are strongly skewed. "
                          "Wilcoxon assumption of symmetry may be violated.")

                # visually check symmetry
                plt.hist(differences_nonzero, bins=10)
                plt.axvline(0, color='red', linestyle='--')
                plt.title("Distribution of Paired Differences")
                plt.show()
                ##################


                # Simple effect size (rank-biserial style approximation)
                z = (stat - (N * (N + 1) / 4)) / np.sqrt(N * (N + 1) * (2 * N + 1) / 24)
                r = z / np.sqrt(N)

                print(f"Effect size r = {r:.3f}")
                print(f"\n{cat_name} - {temp_name} Wilcoxon test")
                print(f"W = {stat:.2f}, N = {N}, p = {p:.4f}, r = {r:.3f}")

                # Optional: boxplot
                park_grouped.boxplot()
                plt.ylabel("Count per park")
                plt.title(f"{cat_name} - {temp_name} per park (Wilcoxon)")
                plt.show()

            elif n_groups >= 3:


                ################
                if N < 5:
                    print("⚠️ Very small number of parks (N < 5). "
                          "Friedman test may lack power.")

                zero_variance_rows = (park_grouped.var(axis=1) == 0).sum()

                if zero_variance_rows > 0:
                    print(f"⚠️ {zero_variance_rows} parks show no variation "
                          "across groups (may weaken Friedman test).")

                z_scores = (park_grouped - park_grouped.mean()) / park_grouped.std()

                if (np.abs(z_scores) > 3).any().any():
                    print("⚠️ Potential extreme outliers detected (|z| > 3).")
                ################


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



