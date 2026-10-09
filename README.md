# Dock-to-Stock Bottleneck Analytics

**Week 1 of my monthly supply chain analytics projects.**

> **Please read this first: the data is simulated.**
> I can't share real timestamps from a workplace, so I generated 4,000 inbound receipts with a Python script. The patterns in the results (for example, that GRN is slow) exist because I built realistic delay behaviour into the generator. This project is a method: how to split a long wait into steps and decide which step to fix first. It says nothing about a real warehouse.

## The question

A truck can arrive at 10:15 AM and the stock may not be available in the system until 4:40 PM. Where did those six hours go?

I follow every receipt through nine segments:

```
Truck Arrival -> Gate Wait -> Dock Wait -> Unloading -> Unload-to-QC Wait -> QC
              -> QC-to-GRN Wait -> GRN Processing -> GRN-to-Putaway Wait -> Putaway -> Stock available
```

I split these into **waiting** (a receipt sitting between two steps) and **processing** (someone is actually working on it). Averages alone hide this, so each segment also gets a Bottleneck Score.

## Why I picked this one

My background is warehouse operations, and inbound receiving and GRN work is something I've seen from the floor. I wanted a first project where I already understand the process, so the analysis is the only new part.

## Result in one paragraph

A receipt takes about 315 minutes from truck arrival to stock available. About 46% of that is waiting, and about 72% happens after unloading. The two highest-scoring segments are **QC-to-GRN Wait** (83.8) and **GRN Processing** (76.3). Together they take about 41% of the total time, while unloading is only about 14%. A what-if model indicates that bringing just those two segments to their SLA could take about 68 minutes off the average receipt (about 34 minutes if only half of the excess is removed). SLA targets are my assumptions. Full tables, the decision model and the recommended SOP are in [`analysis/findings.md`](analysis/findings.md).

## How the Bottleneck Score works

```
Score = 0.4 x delay-share score + 0.3 x variability score + 0.3 x SLA-breach score
```

- **Delay-share score:** the segment's share of total time, scaled so the biggest segment = 100.
- **Variability score:** P90 divided by median, capped at 4 and scaled to 100. A step that is usually fine but sometimes terrible scores higher here.
- **SLA-breach score:** the % of receipts that took longer than the segment's SLA target.
- **Priority:** Critical at 70+, High at 50+, Medium at 35+, Low below that.

The weights, SLA targets and cut-offs are my own judgement calls. They are inputs on the `Assumptions` sheet, so you can change them and everything recalculates.

## Repo structure

```
dock-to-stock-bottleneck-analytics/
├── README.md
├── dock_to_stock_analysis.xlsx   the database + all analysis sheets (live formulas)
├── raw_inbound_data.csv          4,000 simulated receipts (raw columns only)
├── data/
│   └── generate_dataset.py       creates the data; all assumptions are at the top
├── powerbi/
│   ├── power_query.m             Power Query steps (Receipts, SLA, Segments)
│   └── measures.dax              KPI and Bottleneck Score measures
└── analysis/
    └── findings.md               results, decision model, SOP and limitations
```

### Workbook sheets

`README` | `Assumptions` | `Inbound_Data` | `Bottleneck_Score` | `Process_Timeline` | `Heatmap` | `Vendor_Analysis` | `Warehouse_Shift` | `GRN_Ageing` | `Dock_Utilisation` | `Root_Cause` | `Decision_Model` | `SOP`

## Use the Excel file

Open `dock_to_stock_analysis.xlsx`, click **Enable Editing**, and start at the `Bottleneck_Score` sheet. Change any SLA target or weight on `Assumptions` and the tables update.

## Connect Power BI

1. In Power BI Desktop, open **Transform Data > New Source > Blank Query** and paste each block from `powerbi/power_query.m` into its own query (`FilePath`, `Receipts`, `SLA`, `Segments`). Edit `FilePath` to point at the Excel file on your computer.
2. Close and apply. Create an empty table called `_Measures` and add each measure from `powerbi/measures.dax`.
3. Check: with no filters, QC-to-GRN Wait should score about 83.8 and GRN Processing about 76.3, the same as Excel.

## Regenerate the data (optional)

```bash
pip install pandas numpy
python data/generate_dataset.py     # writes raw_inbound_data.csv next to the script
```

The Excel workbook was built from that CSV with live formulas, so every table recalculates when an assumption on the `Assumptions` sheet changes.

## Limitations

- Simulated data, so the conclusions are demonstrations, not evidence about a real site.
- SLA targets and score weights are assumptions. A different weighting could reorder the middle of the table.
- Delay-cause codes are generated alongside the delays. Real logs are usually messier.
- Shift is based on truck arrival time, not on who processed the receipt.
- The SOP targets are proposals. I have not measured any improvement.
