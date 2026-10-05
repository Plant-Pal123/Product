# Requirements - Crop Recommendation & Soil Health Dashboard

> Working title. Status: **Draft v0.1** - derived from whiteboard session. Items marked **[TBD]** need a team decision.

## 1. Overview

A web application that combines **soil data**, **weather data**, and **satellite data** to:

1. Recommend **which crop to grow** on a given piece of land (classification model - Random Forest).
2. Recommend **how to optimise the soil** for that crop (regression model - numerical targets such as nutrient/pH adjustments).
3. Present results in a **dashboard** that lets the user monitor the health of their soil and plants over time and plan ahead.

### 1.1 Problem statement

Growers often choose crops based on habit or incomplete information. Soil conditions, local weather and land observations from satellites are available but scattered and hard to interpret together. This product brings them into one place and turns them into a clear recommendation and plan.

### 1.2 Target users

| User | Needs |
|---|---|
| Small–medium farmer / grower | Know what to plant, what it will cost, what it might earn |
| Hobby / market gardener | Simple crop suggestion and soil advice |
| Agronomist / advisor **[TBD - in scope?]** | Detailed data views and exportable plans for clients |

### 1.3 Goals

- Give a clear, explainable crop recommendation for a specific location.
- Show the user what the soil needs to support that crop.
- Produce a forward-looking plan (timeline, cost, yield, finances) that can be exported.
- Let users monitor soil and plant health over time.

### 1.4 Non-goals (for MVP)

- Controlling farm hardware (irrigation, IoT actuators).
- Guaranteed yield predictions - outputs are estimates.
- Pest detection / management (listed under Future Ideas, §6).

## 2. Definitions

| Term | Meaning |
|---|---|
| **P** / Preferences | User-defined constraints and priorities (e.g. budget, timeframe, crop types to include/exclude) set via the Preference Manager |
| Plot | A user-defined area of land (location + boundary) that analysis runs on |
| Suggested crop | Output of the classification model, ranked |
| Future plan | Generated plan for growing the suggested crop (§3.4) |

## 3. Functional Requirements

Priority key: **M** = Must (MVP), **S** = Should, **C** = Could.

### 3.1 Data input & ingestion

| ID | Requirement | Priority |
|---|---|---|
| FR-1.1 | The system shall let a user define a plot by location (map pin or boundary drawing) | M |
| FR-1.2 | The system shall retrieve **soil data** for the plot (e.g. pH, N, P, K, organic matter, texture, moisture) | M |
| FR-1.3 | The system shall retrieve **weather data** for the plot (historical + forecast: temperature, rainfall, humidity) | M |
| FR-1.4 | The system shall retrieve **satellite data** for the plot (e.g. vegetation indices such as NDVI, land cover) | M |
| FR-1.5 | The user shall be able to manually enter or override soil values (e.g. from a lab soil test) | S |
| FR-1.6 | The system shall validate inputs and flag missing or out-of-range values | M |
| FR-1.7 | The system shall refresh weather and satellite data on a schedule **[TBD: interval]** | S |

### 3.2 Crop recommendation (classification)

| ID | Requirement | Priority |
|---|---|---|
| FR-2.1 | The system shall use a **Random Forest classifier** to predict suitable crops from soil, weather and satellite features | M |
| FR-2.2 | The system shall return a **ranked list** of crops with a confidence score for each | M |
| FR-2.3 | The system shall filter/re-rank recommendations according to user preferences (**P**) - e.g. cost, timeframe, excluded crops | M |
| FR-2.4 | The system shall show the main factors driving each recommendation (feature importance) | S |

### 3.3 Soil optimisation (regression)

| ID | Requirement | Priority |
|---|---|---|
| FR-3.1 | The system shall use a **regression model** to estimate numerical soil targets for the chosen crop (e.g. required N/P/K, pH adjustment) | M |
| FR-3.2 | The system shall compare current soil values to targets and show the gap | M |
| FR-3.3 | The system shall suggest actions to close the gap (e.g. fertiliser/lime quantities) with an estimated cost | S |

### 3.4 Dashboard

| ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | **Suggested crop** panel showing the top recommendation(s) and why | M |
| FR-4.2 | **Future plan** panel (see FR-5.x) | M |
| FR-4.3 | **Soil / Land / Weather display** showing current conditions, maps and trends | M |
| FR-4.4 | **Preference Manager** where the user sets up their preferences (**P**) | M |
| FR-4.5 | **Health monitoring** view tracking soil and plant health over time (e.g. NDVI trend, soil values over time) | S |
| FR-4.6 | Fifth dashboard component **[TBD - left blank on whiteboard]** | - |

### 3.5 Future plan

Inputs to the plan:

| ID | Input | Priority |
|---|---|---|
| FR-5.1 | **Cost** (budget; set from preferences **P**) | M |
| FR-5.2 | **Input data** (soil, weather, satellite for the plot) | M |
| FR-5.3 | **Plant timeframes** (sowing window, time to harvest) | M |
| FR-5.4 | Additional input **[TBD - item (d) blank]** | - |

Plan contents:

| ID | Output | Priority |
|---|---|---|
| FR-5.5 | **Heuristics** - rule-based guidance (e.g. planting windows, rotation advice) | M |
| FR-5.6 | **Graphs** - visual timeline and projections | M |
| FR-5.7 | **Effect on soil** - projected impact of growing the crop on soil nutrients | S |
| FR-5.8 | **Potential yields / finances** - estimated yield, revenue, cost and margin | S |
| FR-5.9 | Additional outputs **[TBD - items (e) and (f) blank]** | - |
| FR-5.10 | The user shall be able to **export the future plan as a PDF** | M |

### 3.6 Preferences (P)

| ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | The user shall be able to set a budget / cost limit | M |
| FR-6.2 | The user shall be able to set a preferred growing timeframe | M |
| FR-6.3 | The user shall be able to include/exclude crop types | S |
| FR-6.4 | Preferences shall persist per user and apply to all recommendations and plans | M |

### 3.7 Accounts

| ID | Requirement | Priority |
|---|---|---|
| FR-7.1 | Users shall be able to sign up, log in and log out | S **[TBD: needed for MVP?]** |
| FR-7.2 | Users shall be able to save multiple plots | S |

## 4. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Performance | A recommendation for a plot should return within **[TBD, e.g. 5 s]** when data is cached |
| NFR-2 | Accuracy | Crop classifier should reach **[TBD, e.g. ≥ 85%]** accuracy on a held-out test set; regression reported with MAE/RMSE |
| NFR-3 | Explainability | Every recommendation shows its key drivers and a confidence score |
| NFR-4 | Usability | Usable by non-technical growers; works on desktop and tablet |
| NFR-5 | Reliability | If an external data source is unavailable, the system uses the last cached data and tells the user |
| NFR-6 | Security & privacy | Plot locations and user data are private to the user; passwords hashed; HTTPS only |
| NFR-7 | Maintainability | Models can be retrained and redeployed without changing the app code |
| NFR-8 | Transparency | Outputs are labelled as estimates, not guarantees |

## 5. Constraints & Assumptions

- External data sources (soil, weather, satellite) are available via free or low-cost APIs **[TBD: final choices]**.
- A labelled training dataset linking soil/climate features to crops is available **[TBD: source]**.
- Satellite imagery resolution limits how small a plot can be meaningfully analysed.
- Project timeline and team size **[TBD]**.

## 6. Future Ideas (post-MVP)

1. **Pests** - pest risk prediction and alerts based on crop, weather and region.
2. *(space for further ideas)*

## 7. Open Questions

- What is the 5th dashboard component?
- What are the remaining future-plan inputs (d) and outputs (e, f)?
- Which data sources will we use, and do they cover our target region?
- Where will crop training data come from?
- Are user accounts required for the MVP, or is a single-session demo acceptable?
