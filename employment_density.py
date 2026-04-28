import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt

# ----------------------------
# 1. LOAD DATA
# ----------------------------

# Census sections (sezioni di censimento)
sections = gpd.read_file("Localita_11_WGS84.shp")

# SLL mapping (municipality -> SLL)
sll = pd.read_csv("RACCORDO COMUNI2011_SLL2011.csv")

# Origin-destination matrix 
# column specs: (start, end) in Python indexing (0-based, end-exclusive)
colspecs = [
    (0, 1),    # record type
    (2, 3),    # residence type
    (4, 7),    # province of residence
    (8, 11),   # municipality of residence
    (15, 16),  # reason for travel
    (17, 18),  # workplace location type
    (19, 22),  # province of work
    (23, 26),  # municipality of work
    (50, 60),  # number of individuals
]

columns = [
    "record_type",
    "residence_type",
    "prov_res",
    "com_res",
    "reason",
    "work_loc_type",
    "prov_work",
    "com_work",
    "n_individuals"
]

odmatrix = pd.read_fwf(
    "matrix_pendo2011_10112014.txt",
    colspecs=colspecs,
    names=columns,
    dtype=str  # keep raw first
)

# ----------------------------
# 2. CLEAN KEY COLUMNS
# ----------------------------

# Ensure municipality codes are strings (important!)
sections["PRO_COM"] = sections["PRO_COM"].astype(str)
sll["PRO_COM"] = sll["PRO_COM"].astype(str)
odmatrix["COMUNE_LAVORO"] = odmatrix["COMUNE_LAVORO"].astype(str)
odmatrix["COMUNE_RESIDENZA"] = odmatrix["COMUNE_RESIDENZA"].astype(str)

# ----------------------------
# 3. FILTER TO MILAN SLL
# ----------------------------

# Find Milan SLL code manually. Milan = 313, Florence = 915
MILAN_SLL_CODE = "313"  # <-- replace with actual code

milan_municipalities = sll.loc[
    sll["COD_SLL"] == MILAN_SLL_CODE, "PRO_COM"
]

# Filter census sections
sections = sections[
    sections["PRO_COM"].isin(milan_municipalities)
].copy()

# Filter OD matrix (jobs located in Milan SLL)
odmatrix = odmatrix[
    odmatrix["COMUNE_LAVORO"].isin(milan_municipalities)
].copy()

# ----------------------------
# 4. COMPUTE JOBS BY MUNICIPALITY (WORKPLACE-BASED)
# ----------------------------

jobs_by_municipality = (
    odmatrix.groupby("COMUNE_LAVORO")["FLUSSO"]
    .sum()
    .rename("jobs_municipality")
)

# ----------------------------
# 5. MERGE JOBS INTO SECTIONS
# ----------------------------

sections = sections.merge(
    jobs_by_municipality,
    left_on="PRO_COM",
    right_index=True,
    how="left"
)

# Fill missing values (municipalities with no incoming commuters)
sections["jobs_municipality"] = sections["jobs_municipality"].fillna(0)

# ----------------------------
# 6. CREATE WEIGHTS (POPULATION-BASED)
# ----------------------------

POP_COLUMN = "POP_RES"  # adjust if your file uses a different name

# Total population per municipality
sections["municipality_population"] = (
    sections.groupby("PRO_COM")[POP_COLUMN]
    .transform("sum")
)

# Weight of each section within its municipality
sections["weight"] = (
    sections[POP_COLUMN] / sections["municipality_population"]
)

# ----------------------------
# 7. ALLOCATE JOBS TO SECTIONS
# ----------------------------

sections["estimated_jobs"] = (
    sections["jobs_municipality"] * sections["weight"]
)

# ----------------------------
# 8. COMPUTE AREA AND DENSITY
# ----------------------------

# Reproject to a metric CRS (Europe-wide projection)
sections = sections.to_crs(epsg=3035)

# Area in km²
sections["area_km2"] = sections.geometry.area / 1_000_000

# Employment density (jobs per km²)
sections["employment_density"] = (
    sections["estimated_jobs"] / sections["area_km2"]
)

# ----------------------------
# 9. SAVE OUTPUT
# ----------------------------

sections.to_file("milan_employment_density.shp")

# ----------------------------
# 10. QUICK VISUALIZATION
# ----------------------------

fig, ax = plt.subplots(figsize=(10, 10))

sections.plot(
    column="employment_density",
    scheme="quantiles",
    k=5,
    legend=True,
    ax=ax
)

ax.set_title("Estimated Employment Density - Milan SLL")
ax.axis("off")

plt.show()