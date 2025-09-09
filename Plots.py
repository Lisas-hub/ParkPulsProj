
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt

variables_all = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_all")

# ======================================================
# === 'activities' from sociotop (mouseover_ column) ===

activity_col = "MOUSEOVER_combined"

variables_all[activity_col] = variables_all[activity_col].fillna("ingen information")

variables_all["activity_list"] = (
    variables_all[activity_col]
    .str.lower()
    .str.split(",")
    .apply(lambda lst: [item.strip() for item in lst])
)

park_activity = variables_all[["group", "activity_list"]].explode("activity_list").copy()

park_activity = park_activity.drop_duplicates(subset=["group", "activity_list"])

activity_counts = park_activity["activity_list"].value_counts()
activity_percent = (activity_counts / variables_all["group"].nunique()) * 100
print("\n--- activity_percentages ---")
print(activity_percent.head(32))

activity_percent = activity_percent[activity_percent.index != "ingen information"]

# plot all in one graph
plt.figure(figsize=(12, 6))
activity_percent.sort_values(ascending=False).plot(kind='bar')
plt.ylabel("Andel parker (%)")
plt.xlabel("Aktivitet")
plt.title("Andel parker som erbjuder olika aktiviteter")
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.show()

# plot multiple graphs with groupings of similar categories
activity_groups = {
    "sport_play": [
        "bollspel", "bollek", "utegym", "motionsspår", "cykling",
        "skate/bmxåkning", "löpträning", "lekplats", "naturlek",
        "pulkaåkning", "utomhusbad", "badanläggning", "parklek",
        "skridskoakning"
    ],
    "calm_nature": [
        "rofylldhet", "blomprakt", "utsikt", "naturupplevelse",
        "vattenkontakt", "grön oas", "odling", "promenad", "båtliv",
        "skogskänsla", "djurhallning"
    ],
    "social": [
        "picknick/solbad", "grillning", "uteservering", "folkliv",
        "evenemang", "torghandel"
    ]
}
# friidrott finns men ingen park har denna, sitt_i_sol och picknick verkar vara ihopslagna till picknick/solbad

activity_to_group = {}
for group, activities in activity_groups.items():
    for activity in activities:
        activity_to_group[activity] = group

activity_df = activity_percent.reset_index()
activity_df.columns = ["activity", "percent"]

activity_df["group"] = activity_df["activity"].map(lambda x: activity_to_group.get(x, "other"))

import matplotlib.pyplot as plt

for group_name in ["sport_play", "calm_nature", "social", "other"]:
    group_data = activity_df[activity_df["group"] == group_name].sort_values(by="percent", ascending=False)

    if group_data.empty:
        continue

    bar_count = len(group_data)
    plt.figure(figsize=(bar_count * 0.6, 5))
    plt.bar(group_data["activity"], group_data["percent"], color="skyblue", width=0.6)
    plt.title(f"Andel parker med aktiviteter i kategori: {group_name}")
    plt.ylabel("Andel parker (%)")
    plt.xlabel("Aktivitet")
    plt.ylim(0, 100)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.show()

# =====================
