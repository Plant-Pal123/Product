"""Canonical crop list and synthetic agronomic ranges shared by both training
scripts (scripts/train_classifier.py, scripts/train_regressor.py) and by
SoilRegressor at inference time (app/ml/regressor.py).

CROP_NAMES's order is the contract: the regressor encodes "which crop" as that
crop's index in this list, so training and inference must use the same list.
It also matches the insertion order of sql/seed.sql's crops table, but nothing
here depends on database ids - looking a crop up by name (`CROP_NAMES.index(name)`)
is deliberate so this stays correct even if crop rows are added, removed or
reordered in the database.

Ranges are illustrative agronomic ranges authored for bootstrapping the
pipeline, not a verified dataset - see requirements.md §7 ("Where will crop
training data come from?"), still an open decision.

Each crop also carries an "ndvi" range. This used to be one single
`NDVI_RANGE` shared by every crop - since every crop then drew NDVI from the
*same* distribution, the feature carried zero class-discriminating signal by
construction, and the trained models correctly learned to ignore it entirely
(see design.md's "Crop recommendation / soil targets" note: sweeping real
NDVI across its full range produced an identical top prediction every time).

A first attempt just bucketed crops loosely by canopy density (orchards
higher, legumes/melons lower), but several crops ended up sharing the exact
same bucket - and those happen to be exactly the crops whose other seven
features already overlap heavily (this dataset's n/p/k/ph/temperature/
humidity/rainfall ranges reuse the same values across several unrelated
crops), so the classifier still couldn't tell them apart: 0.000 ndvi_mean
importance and 0%-recall on coffee/lentil/rice. Assigning each crop its own
non-overlapping 0.025-wide slice of [0.30, 0.85] (still roughly ordered by
canopy density, sparsest first) fixes that - see the classifier's printed
feature importances after `scripts/train_classifier.py`. Real NDVI won't
separate 22 crops this cleanly; this is a synthetic-data workaround for a
demonstrated bug, not a claim about real vegetation indices.
"""

CROP_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "rice":        {"n": (80, 120), "p": (35, 60),  "k": (35, 45),  "ph": (5.0, 6.5), "temperature": (22, 32), "humidity": (75, 90), "rainfall": (180, 300), "ndvi": (0.775, 0.800)},
    "maize":       {"n": (60, 100), "p": (35, 60),  "k": (15, 25),  "ph": (5.5, 7.0), "temperature": (18, 27), "humidity": (55, 75), "rainfall": (60, 110),  "ndvi": (0.600, 0.625)},
    "chickpea":    {"n": (20, 60),  "p": (55, 80),  "k": (75, 85),  "ph": (6.0, 8.0), "temperature": (17, 25), "humidity": (14, 25), "rainfall": (65, 95),   "ndvi": (0.325, 0.350)},
    "kidneybeans": {"n": (0, 40),   "p": (55, 80),  "k": (15, 25),  "ph": (5.5, 6.0), "temperature": (15, 25), "humidity": (18, 25), "rainfall": (60, 150),  "ndvi": (0.350, 0.375)},
    "pigeonpeas":  {"n": (0, 40),   "p": (55, 80),  "k": (15, 25),  "ph": (4.5, 7.5), "temperature": (18, 37), "humidity": (30, 70), "rainfall": (90, 200),  "ndvi": (0.500, 0.525)},
    "mothbeans":   {"n": (0, 40),   "p": (35, 60),  "k": (15, 25),  "ph": (3.5, 10.0),"temperature": (24, 32), "humidity": (30, 65), "rainfall": (25, 65),   "ndvi": (0.300, 0.325)},
    "mungbean":    {"n": (0, 40),   "p": (30, 60),  "k": (15, 25),  "ph": (6.0, 7.5), "temperature": (27, 32), "humidity": (75, 90), "rainfall": (45, 65),   "ndvi": (0.375, 0.400)},
    "blackgram":   {"n": (0, 40),   "p": (55, 80),  "k": (15, 25),  "ph": (6.5, 7.5), "temperature": (25, 35), "humidity": (60, 75), "rainfall": (55, 75),   "ndvi": (0.400, 0.425)},
    "lentil":      {"n": (0, 40),   "p": (55, 80),  "k": (15, 25),  "ph": (6.0, 7.5), "temperature": (18, 30), "humidity": (60, 70), "rainfall": (40, 60),   "ndvi": (0.425, 0.450)},
    "pomegranate": {"n": (0, 40),   "p": (5, 20),   "k": (30, 45),  "ph": (6.0, 7.0), "temperature": (18, 25), "humidity": (85, 95), "rainfall": (100, 115), "ndvi": (0.675, 0.700)},
    "banana":      {"n": (80, 120), "p": (70, 95),  "k": (45, 55),  "ph": (5.5, 6.5), "temperature": (25, 30), "humidity": (75, 85), "rainfall": (95, 115),  "ndvi": (0.825, 0.850)},
    "mango":       {"n": (0, 40),   "p": (15, 40),  "k": (25, 35),  "ph": (4.5, 7.0), "temperature": (27, 37), "humidity": (45, 55), "rainfall": (85, 105),  "ndvi": (0.700, 0.725)},
    "grapes":      {"n": (0, 40),   "p": (110, 140),"k": (190, 210),"ph": (5.5, 6.5), "temperature": (8, 42),  "humidity": (80, 85), "rainfall": (65, 75),   "ndvi": (0.550, 0.575)},
    "watermelon":  {"n": (80, 120), "p": (5, 20),   "k": (45, 55),  "ph": (6.0, 7.0), "temperature": (24, 27), "humidity": (80, 90), "rainfall": (40, 55),   "ndvi": (0.450, 0.475)},
    "muskmelon":   {"n": (80, 120), "p": (5, 20),   "k": (45, 55),  "ph": (6.0, 7.0), "temperature": (27, 30), "humidity": (90, 95), "rainfall": (20, 30),   "ndvi": (0.475, 0.500)},
    "apple":       {"n": (0, 40),   "p": (120, 145),"k": (195, 205),"ph": (5.5, 6.5), "temperature": (21, 24), "humidity": (90, 95), "rainfall": (100, 120), "ndvi": (0.650, 0.675)},
    "orange":      {"n": (0, 40),   "p": (5, 20),   "k": (5, 15),   "ph": (6.0, 8.0), "temperature": (10, 35), "humidity": (90, 95), "rainfall": (100, 120), "ndvi": (0.625, 0.650)},
    "papaya":      {"n": (30, 70),  "p": (45, 70),  "k": (45, 55),  "ph": (6.5, 7.0), "temperature": (23, 44), "humidity": (90, 95), "rainfall": (40, 250),  "ndvi": (0.575, 0.600)},
    "coconut":     {"n": (0, 40),   "p": (5, 30),   "k": (25, 35),  "ph": (5.0, 6.0), "temperature": (25, 30), "humidity": (90, 100),"rainfall": (140, 230), "ndvi": (0.800, 0.825)},
    "cotton":      {"n": (100, 140),"p": (35, 60),  "k": (15, 25),  "ph": (5.5, 8.5), "temperature": (22, 26), "humidity": (75, 85), "rainfall": (60, 100),  "ndvi": (0.525, 0.550)},
    "jute":        {"n": (60, 100), "p": (35, 60),  "k": (35, 45),  "ph": (6.0, 7.5), "temperature": (23, 27), "humidity": (70, 90), "rainfall": (150, 200), "ndvi": (0.725, 0.750)},
    "coffee":      {"n": (80, 120), "p": (15, 40),  "k": (25, 35),  "ph": (6.0, 7.5), "temperature": (23, 28), "humidity": (50, 70), "rainfall": (150, 200), "ndvi": (0.750, 0.775)},
}

CROP_NAMES: list[str] = list(CROP_RANGES.keys())
