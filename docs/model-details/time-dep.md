# Time Dependence
---

The generalised baseline for time dependent assets in STEVFNs is modelled via
stock balance nodes. 

STEVFNs runs on **two nested timescales**:

1. **Hourly / operational timesteps**: sampled representative hours (e.g.
   representative days per year), used for dispatch, generation profiles,
   and demand balancing. Each case study can be set up by the user with 
   different sample sizes. The sample size in the network structure represents
   the total number of hours sampled across the entire project lifetime. If, for example,
   the sample size is 12 days per year in a 10-year project, the defined parameters in
   network structure should be a total of: $12 \cdot 24 \cdot 10 =\ 2,880\ hours$. Normally, this
   translates to a Start_Time = 0 and End_Time = 2,800. See additional guidance on [Case Study Setup](../setup/case-study-setup.md)

2. **Reinvestment periods**: multi-year capital-planning blocks (e.g. every
   5 years across a 30-year project life), used for capacity build/retire
   decisions and cost amortisation. The exact reinvestment period is defined by
   the user in system parameters.

This document covers how the two timescales relate, and how capital cost is
amortised and discounted to net present value (NPV).

## System-level time parameters

Set in `Network_STEVFNs.system_parameters_df` (defaults shown, these are user-set parameter per scenario in a case study):

| parameter             | default   | description                                |
|-----------------------|-----------|--------------------------------------------|
| `timestep`            | 1 h       | hours represented per sampled timestep     |
| `discount_rate`       | 5%        | system-wide NPV discount rate              |
| `project_life`        | 262800 h  | total modelled horizon (default 30y)       |
| `reinvestment_period` | 43800 h   | capital-planning block length (default 5y) |

`Asset_STEVFNs._compute_period_counts()` derives, per asset:

```python
num_years             = project_life_hours / 8760
reinvestment_period   = reinvestment_period_hours / 8760      # in years
num_periods           = ceil(num_years / reinvestment_period)
```

`_years_in_period(p)` returns how many modelled years actually fall in period
`p` — this is usually `reinvestment_period`, but the **final period is
truncated** if `project_life` isn't an exact multiple of `reinvestment_period`
(e.g. 27-year project life with 5-year periods ⇒ last period is only 2
years), so per-year-averaged results aren't inflated/deflated for that period.

### Mapping hourly samples to periods

Because only representative days are sampled (not every real hour),
`_get_period_change_indices()` figures out, from `number_of_edges` and
`num_years`, how many *sampled* hours represent one modelled year, then
multiplies by `reinvestment_period` to get the hourly sample index at which
each period starts. `_period_index_for_edge(edge_number)` then maps any
hourly edge back to its owning reinvestment period.

## Stock assets

Assets with installed capacity that persists and depreciates over time (PV,
fossil generators, etc.) subclass `Stock_Asset_STEVFNs`. Per period `p` they
introduce two period-indexed decision variables:

- `new_capacity[p]` — new capacity installed in period `p` (≥ 0)
- `carryover_out[p]` — capacity actually operating/available at the *end* of
  period `p`, which becomes available capacity for period `p+1`

Plus two parameters:

- `existing_capacity_vec[p]` — pre-existing (pre-model) capacity still
  present in period `p`
- `decom_mask_param[p, k]` — 1 if a cohort installed in period `k` is fully
  retired exactly in period `p` (hard lifetime), else 0

### Stock chain

For each period `p` a dedicated **stock node** `(location, stock_node_type,
p)` is created with `curtailment = False` (hard equality balance — nothing
can be silently dropped or invented). Edges attached to it:

| edge          | direction        | flow                                   |
|---------------|------------------|-----------------------------------------|
| install       | → stock node     | `new_capacity[p]`                       |
| existing      | → stock node     | `existing_capacity_vec[p]`              |
| carry-in      | prev stock → this stock (p>0) | `carryover_out[p-1]`      |
| decommission  | stock node →     | `decommission_out[p] = (decom_mask @ new_capacity)[p]` |
| carry-out     | stock node →     | `carryover_out[p]` (final period only, to close the balance) |

The `== 0` balance at each stock node forces:

```
carryover_out[p] + decommission_out[p]  =  carryover_out[p-1] + new_capacity[p] + existing_capacity_vec[p]
```

i.e. **operating capacity evolves as**: previous operating capacity, plus
new builds and any surviving pre-existing capacity, minus whatever
retires this period. `carryover_out[p]` is what downstream edges (e.g.
hourly generation in `pv_openfield.py`, or the dispatch cap in `pp_co2.py`)
are actually allowed to use.

### Retirement rules

- **New capacity**: hard lifetime retirement via `decom_mask_param`. In
  `_update_new_capacity_decom_mask`, `lifetime_periods =
  round(asset_lifespan_years / reinvestment_period_years)` (min 1), and
  `decom_mask[p, p - lifetime_periods] = 1`. So a cohort installed in period
  `k` fully leaves `carryover_out` exactly `lifetime_periods` periods later
  — a step-function retirement, not gradual decay.
- **Existing (pre-model) capacity**: controlled by `decommission_mode`:
  - `"decay_rate"` — geometric decay, `existing_capacity[p] =
    existing_capacity_0 * (1 - decay_rate)^p`
  - `"profile"` — an explicit per-location, per-period retention-fraction
    CSV (`existing_capacity_profile_filename`), for cases where retirement
    isn't well described by a constant rate.

## Cost amortisation and NPV

Capital cost is built once as an `(num_periods, num_periods)` matrix `M`,
where `M[p, k]` is the NPV (discounted to year 0) of the payment due in
reporting period `p` for **one unit of capacity installed in period k**.
Total capital cost in the objective is then simply:

```
capital_cost = sum( M @ new_capacity )   # = Σ_p Σ_k M[p,k] * new_capacity[k]
```

This is built in two stages, using **two distinct rates**:

### Stage 1 — amortise capex into an annuity 

Each asset type has its own `interest_rate` in `parameters.csv` (its
financing/loan rate). The undiscounted capex-per-unit-capacity
(`sizing_constant`, possibly varying by install period `k` via a learning
curve, as in `pv_openfield.py`) is converted into a constant **annual
repayment** using the standard mortgage-style capital-recovery factor:

```
amort_factor      = i(1+i)^L / ((1+i)^L - 1)          # i = interest_rate, L = asset lifetime (years)
annual_payment[k] = sizing_constant[k] * amort_factor
```

This spreads one unit of installed capex into `L` equal nominal annual
payments over the asset's physical lifetime, starting at that cohort's
install year.

### Stage 2 — discount each payment to year 0

For a cohort installed in period `k` (absolute start year `install_year`,
retired by `payoff_year = install_year + asset_lifetime`), and for each
reporting period `p` (absolute year window
`[period_start_years[p], period_end_years[p])`):

1. Find the overlap between period `p`'s years and the cohort's active
   lifetime window `[install_year, payoff_year)`.
2. For every whole year `y` in that overlap, discount that year's annual
   payment back to year 0 using the **system** `discount_rate`:
   `discount_factor(y) = (1 + discount_rate)^(-y)`.
3. `M[p, k] = annual_payment[k] * Σ_y discount_factor(y)` over the years in
   that overlap.

Because the overlap is empty once `p`'s years are past `payoff_year`,
`M[p, k]` is naturally zero after the cohort retires — no separate
"end-of-life" bookkeeping is needed; retirement of the *cost* stream falls
out of the same lifetime window used to build the amortisation.

**Why two rates:** `interest_rate` only shapes *how a lump of capex is
spread into annual payments* (financing cost of that specific technology);
`discount_rate` is the *system's* time-value-of-money rate used to bring
every future cash flow (from every asset) back to a common year-0 NPV so
they can be summed into one objective.

### Usage / fuel cost

Dispatchable assets with real hourly flow (e.g. `PP_CO2_Asset`) additionally
carry an hourly `usage_constant` (fuel/variable O&M cost per unit flow).
`_update_usage_constant` takes the scalar `$/unit` rate from
`parameters.csv`, discounts it **year by year** (again with `discount_rate`,
not `interest_rate`), and scales by `simulation_factor = 365 /
sampled_days_per_year` to blow representative-day sampling back up to a
full year. Usage cost enters the same shared `cost_fun`:

```python
cost_fun(new_capacity, flows, params):
    capital_cost = sum(sizing_constant_matrix @ new_capacity)   # NPV, both rates as above
    usage_cost   = sum(usage_constant * flows)                   # NPV via discount_rate only
    return capital_cost + usage_cost
```

This single `cost_fun` (defined once in `Stock_Asset_STEVFNs`) is shared by
every stock asset — subclasses only change what `flows` and
`usage_constant` actually are (a real `Variable`/`Parameter` for dispatchable
assets like `PP_CO2_Asset`, or the `Constant(0)` default for assets with no
independent hourly dispatch decision, like PV).

### Per-period reporting 

For results output, `get_period_costs()` reads back:

```
period_capital[p] = (M @ new_capacity)[p]     # already NPV'd, all cohorts summed
period_usage[p]   = Σ_{hours in period p} usage_constant * flows
period_total[p]   = period_capital[p] + period_usage[p]
reported[p]       = period_total[p] / years_in_period(p)   # average annualised cost
```

so index `p` of the returned array is already "all NPV-discounted cost
recognised in period `p`, from every still-active install cohort" — no
further adjustment is needed by callers.