# Model Architecture
---

The core architecture is designed so for any one case study, the network structure (which
assets are available to install, where, and how many time steps should be sampled) is built once.
After it is built, scenarios with the same structure can be re-run by changing parameter values.

In other words, each row of `Network_Structure.csv` becomes an asset instance, which defines its hourly time grid and wires
itself into the shared node/edge graph, contributing one term to the total
system cost.

The `update()` method occurs once per scenario: parameter values (costs, profiles,
budgets) are pushed into the existing `cp.Parameter` objects — the graph structure itself doesn't change, so the same `Problem` can be re-solved
cheaply (computationally) scenario after scenario.

Finally, results for analysis are pulled back out per asset after solving, then compiled
into the long-format output CSVs. This current implementation follows result extraction formatted
for processing in the GMPA webtool for visualization. Tailored result extraction may be scripted
and applied for other pruposes.

```mermaid
flowchart TD
    subgraph Inputs["Input CSVs (per case study / scenario)"]
        NS["Network_Structure.csv<br/>(Asset_Class, locations, time range)"]
        AP["Asset_Parameters.csv<br/>(asset_type per asset)"]
        LP["Location_Parameters.csv<br/>(lat, lon, location_name)"]
        SP["System_Parameters.csv<br/>(discount_rate, project_life,<br/>reinvestment_period, timestep)"]
    end

    subgraph Build["Network_STEVFNs.build()"]
        GEN["generate_asset()<br/>ASSET_DICT[Asset_Class]()"]
        DEF["asset.define_structure()<br/>hourly time grid + node locations"]
        GEN --> DEF
    end

    subgraph Assets["Assets (Base_Assets / Stock_Assets subclasses)"]
        A1["Asset[i]"]
    end

    subgraph Graph["Node / Edge Graph"]
        NODES["Nodes: (location, type, time)<br/>balance constraints (<=0 or ==0)"]
        EDGES["Edges: flow variables/expressions<br/>+ conversion_fun"]
        EDGES -->|attach to| NODES
    end

    subgraph Problem["cvxpy Problem"]
        COST["cost = sum(asset costs)"]
        CONS["constraints = node balances"]
        SOLVE["problem.solve()<br/>solver of choice <br/> (default clarabel)"]
        COST --> SOLVE
        CONS --> SOLVE
    end

    subgraph Update["Network_STEVFNs.update() (per scenario)"]
        UPD["asset.update(asset_type)<br/>parameters.csv row -> cp.Parameter values"]
    end

    subgraph Results["Results"]
        REC["asset.get_results_records()<br/>get_period_costs / emissions / capacity"]
        COMP["compile_results.py<br/>compile_scenario_results()"]
        OUT["costs-over-time.csv<br/>emissions-over-time.csv<br/>emissions-over-time-by-country.csv"]
        REC --> COMP --> OUT
    end

    NS --> GEN
    AP --> UPD
    LP --> UPD
    SP --> UPD

    DEF --> A1
    A1  -->|build_edges| EDGES
    A1  -->|build_cost| COST
    NODES --> CONS

    UPD -.->|mutates cp.Parameter values, re-solve next<br/>scenario without rebuild| SOLVE

    SOLVE --> REC
```