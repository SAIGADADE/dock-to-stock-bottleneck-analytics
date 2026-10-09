# Findings

> **The data is simulated.** I generated 4,000 inbound receipts with `data/generate_dataset.py`. The patterns below exist because I built realistic delay behaviour into the generator. These findings show how the method works. They are not findings about a real warehouse.

## Setup

- 4,000 receipts, 1 July to 2 October 2026, three warehouses (Bhiwandi DC, Kalyan DC, Pimplas DC), 12 vendors, six docks.
- 3,840 receipts are completed. 160 are still open (100 Pending, 60 On Hold).
- Each receipt is split into nine segments. Five are **waiting** (time between steps) and four are **processing** (someone is working on it).
- SLA targets, score weights and priority cut-offs are my own assumptions. They are inputs on the `Assumptions` sheet in the workbook.

## Bottleneck Score

```
Score = 0.4 x delay-share score + 0.3 x variability score + 0.3 x SLA-breach score
```

| Segment | Type | Avg (min) | % of total time | P90 (min) | % over SLA | Score | Priority |
|---|---|---|---|---|---|---|---|
| QC-to-GRN Wait | Waiting | 64 | 20% | 139 | 63% | 83.8 | Critical |
| GRN Processing | Processing | 65 | 21% | 131 | 51% | 76.3 | Critical |
| Gate Wait | Waiting | 36 | 11% | 74 | 42% | 56.2 | High |
| Unloading | Processing | 43 | 14% | 70 | 16% | 45.0 | Medium |
| QC | Processing | 36 | 11% | 62 | 23% | 44.1 | Medium |
| GRN-to-Putaway Wait | Waiting | 19 | 6% | 34 | 34% | 38.0 | Medium |
| Putaway | Processing | 27 | 9% | 47 | 16% | 36.9 | Medium |
| Unload-to-QC Wait | Waiting | 14 | 5% | 26 | 34% | 35.3 | Medium |
| Dock Wait | Waiting | 10 | 3% | 17 | 14% | 26.1 | Low |

## Main finding

The simulated warehouse does not mainly have an unloading problem. Unloading is about 14% of the total time. The biggest delay to stock availability builds up **after** unloading, between QC and GRN and during GRN processing. Together those two segments take about 41% of the total time.

- The average receipt takes about **315 minutes (5.2 hours)** from truck arrival to stock available. The median is 291 minutes.
- About **46%** of that time is waiting, not work.
- About **72%** of it happens after unloading finishes.

## Other results

**Shift.** Shift C (22:00 to 06:00, based on truck arrival) has the longest QC-to-GRN wait, about 101 minutes against 55 on Shift A. Shift B is in between at 69.

**Warehouse.** Pimplas DC is slowest at GRN processing (about 82 minutes against 59 at the other two) and has the highest share of receipts over the 300-minute total target (53%, against 45% at Bhiwandi and 41% at Kalyan).

**Vendors.** Vendors 03, 07 and 11 deliver short or damaged stock on about 31% of receipts. The other nine average about 8%. Their receipts take about 27 minutes longer on average (335 against 308).

**Docks.** Dock utilisation is 20% to 30% per dock and about 49% in the busiest hour. Gate waits peak between 10:00 and 12:00 (about 48 to 56 minutes) because arrivals bunch up, not because there are too few docks.

**GRN ageing.** About 91% of receipts have a GRN age under 6 hours. Of the 160 open receipts, the 60 On Hold ones average about 11 days old and the oldest is about 21 days.

**Root cause (logged cause codes).** QC-to-GRN Wait is the primary delay stage for 35% of receipts and GRN Processing for 19%. Manpower is the top logged cause for QC-to-GRN Wait. Documentation Mismatch is the top cause for GRN Processing.

## Decision model

The `Decision_Model` sheet asks: if a segment met its SLA, how many minutes would come off the average receipt? Receipts that went over the SLA are brought down to the SLA. Receipts already inside it stay as they are. I also added a cautious setting: only half of the excess time is removed.

| Segment | Minutes saved per receipt (all excess removed) | Minutes saved (half of excess removed) |
|---|---|---|
| QC-to-GRN Wait | 38.8 | 19.4 |
| GRN Processing | 28.8 | 14.4 |
| Gate Wait | 13.6 | 6.8 |
| QC | 4.8 | 2.4 |
| GRN-to-Putaway Wait | 4.1 | 2.1 |
| Unloading | 3.6 | 1.8 |
| Unload-to-QC Wait | 3.2 | 1.6 |
| Putaway | 2.5 | 1.3 |
| Dock Wait | 1.0 | 0.5 |

- Bringing every segment to its SLA would take about 100 minutes off the average receipt. About two-thirds of that sits in just two segments: QC-to-GRN Wait and GRN Processing (about 68 of the 100 minutes).
- At the cautious setting, fixing only those two segments would take about 34 minutes off the 315-minute average (about 11%). Over the 3,840 completed receipts that is roughly 2,160 receipt-hours of earlier stock availability.
- Unloading ranks sixth. Speeding up unloading would help much less than fixing the wait before GRN and the GRN step itself.

The model indicates where effort is worth spending first. It is not a measured saving. It assumes the SLAs are achievable, that fixing one segment does not push work into another, and that the effect is the same across warehouses and shifts.

## Business impact (what this could mean for a warehouse team)

- The proposed approach could help a team decide where to put people first. In this simulated data the answer is the GRN desk, especially on the night shift and at Pimplas DC, not extra unloading labour.
- Stock that is physically in the building but not yet in the system cannot be picked or promised to customers. Cutting QC-to-GRN wait and GRN time would make that stock available sooner.
- A daily dock-to-stock report split by segment, shift and warehouse would show whether the bottleneck moves after changes are made.
- No improvement has actually happened. All numbers come from synthetic data and my own SLA assumptions.

## Recommended SOP

| # | Rule | Target |
|---|---|---|
| 1 | Start GRN as soon as QC is released. No holding receipts for end-of-shift batches. | QC-to-GRN wait 30 min or less |
| 2 | Check PO, invoice and ASN against the gate sheet before unloading starts. | Mismatches flagged before unloading |
| 3 | At least one GRN clerk on every shift in every warehouse, with breaks covered in turns. | GRN processing 45 min or less |
| 4 | For short or damaged receipts, post GRN for the accepted quantity and raise the discrepancy separately. | Discrepancy GRNs open under 24 hrs |
| 5 | Escalate open GRNs: over 6 hrs to the supervisor, over 24 hrs to the manager. Review On Hold weekly. | No GRN open over 72 hrs without an owner |
| 6 | Appointment slots for vendors with the most short or damaged receipts. | Gate wait 30 min or less |
| 7 | Daily report: average, P90 and slowest segment by warehouse and shift. | Reviewed every morning |

The targets are proposals. I have not measured any improvement.

## Limitations

- Simulated data, so the conclusions demonstrate a method, not a real site.
- SLA targets and score weights are assumptions. A different weighting could reorder the middle of the table.
- Delay-cause codes were generated alongside the delays. Real logs are usually messier and often incomplete.
- Shift is based on truck arrival time, not on who processed the receipt.
- I have not modelled dock appointments, weather, festival peaks or equipment breakdowns.

## Next steps

- Try the same method on an anonymised real receipt log, if I can get one.
- Re-run the decision model with different SLA targets to see how sensitive the ranking is.
- Finish the Power BI dashboard and add screenshots.
