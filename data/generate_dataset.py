"""
generate_dataset.py
-------------------
Builds a SIMULATED inbound-receipt dataset (4,000 receipts) for the
Dock-to-Stock project. No real company data is used anywhere.

Every stage duration is drawn from a lognormal distribution (a few slow
outliers, which is how real dock timings behave). The assumptions that
shape the data are written out in the config block below so anyone can
change them and re-run.

Run:  python generate_dataset.py
Out:  raw_inbound_data.csv (same folder)
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
N_TOTAL = 4000
N_PENDING = 100          # GRN not started yet (recent receipts)
N_ON_HOLD = 60           # GRN stuck (older receipts)
START = datetime(2026, 7, 1)
END = datetime(2026, 9, 30)
AS_OF = datetime(2026, 10, 2, 8, 0)   # report date, used for open-GRN ageing

# SLA targets per segment, in minutes. Same numbers go into the Excel
# Assumptions sheet. Used here only to tag the main delay stage / cause.
SLA = {
    "Gate Wait": 30, "Dock Wait": 15, "Unloading": 60,
    "Unload-to-QC Wait": 15, "QC": 45, "QC-to-GRN Wait": 30,
    "GRN Processing": 45, "GRN-to-Putaway Wait": 20, "Putaway": 40,
}

WAREHOUSES = {
    #  name           code   share  gate_f  grn_clerk_f
    "Bhiwandi DC": ("BHW", 0.40, 1.20, 1.00),
    "Kalyan DC":   ("KLN", 0.33, 1.00, 1.00),
    "Pimplas DC":  ("PMP", 0.27, 0.90, 1.35),   # short-staffed on GRN desk
}
DOCKS_PER_WH = 2

VENDORS = [f"Vendor {i:02d}" for i in range(1, 13)]
VENDOR_CATEGORY = {
    1: "Staples", 2: "Snacks", 3: "Beverages", 4: "Personal Care",
    5: "Home Care", 6: "Staples", 7: "Snacks", 8: "Dairy & Frozen",
    9: "Personal Care", 10: "Home Care", 11: "Beverages", 12: "Packaging",
}
CATEGORIES = sorted(set(VENDOR_CATEGORY.values()))
# probability that a receipt from this vendor has short / damaged stock
VENDOR_DISC = {v: 0.05 for v in range(1, 13)}
VENDOR_DISC.update({3: 0.30, 7: 0.30, 11: 0.28, 5: 0.12})
# vendors that tend to turn up without an appointment (longer gate wait)
VENDOR_GATE_F = {v: 1.0 for v in range(1, 13)}
VENDOR_GATE_F.update({3: 1.3, 7: 1.3, 11: 1.2})

HOUR_WEIGHTS = [1, 1, 1, 1, 1, 2, 4, 6, 8, 9, 10, 9, 7, 8, 9, 9, 8, 6, 4, 3, 2, 2, 1, 1]
SHIFT_WAIT_F = {"A": 1.0, "B": 1.2, "C": 1.8}    # QC-to-GRN queue
SHIFT_PROC_F = {"A": 1.0, "B": 1.1, "C": 1.3}    # GRN keying time


def shift_of(hour):
    if 6 <= hour < 14:
        return "A"
    if 14 <= hour < 22:
        return "B"
    return "C"


def gate_hour_factor(h):
    if 10 <= h <= 12:
        return 1.9
    if 13 <= h <= 17:
        return 1.5
    if 8 <= h <= 9:
        return 1.3
    if 6 <= h <= 7:
        return 1.0
    return 0.7


rng = np.random.default_rng(SEED)


def ln(median, sigma):
    """Lognormal draw with the given median."""
    return median * float(np.exp(rng.normal(0, sigma)))


def pick(options):
    keys, probs = zip(*options)
    return keys[rng.choice(len(keys), p=np.array(probs) / sum(probs))]


CAUSE_BY_STAGE = {
    "Gate Wait":           [("Space / Equipment", .6), ("Vendor", .3), ("Manpower", .1)],
    "Dock Wait":           [("Space / Equipment", .6), ("Manpower", .4)],
    "Unloading":           [("Manpower", .6), ("Vendor", .25), ("Space / Equipment", .15)],
    "Unload-to-QC Wait":   [("Manpower", .6), ("Space / Equipment", .4)],
    "QC":                  [("Vendor", .5), ("Manpower", .3), ("Documentation Mismatch", .2)],
    "QC-to-GRN Wait":      [("Manpower", .5), ("Documentation Mismatch", .3), ("System", .2)],
    "GRN Processing":      [("Documentation Mismatch", .45), ("System", .35), ("Manpower", .2)],
    "GRN-to-Putaway Wait": [("Manpower", .5), ("Space / Equipment", .5)],
    "Putaway":             [("Space / Equipment", .5), ("Manpower", .5)],
}


def random_arrival():
    while True:
        d = START + timedelta(days=int(rng.integers(0, (END - START).days + 1)))
        if d.weekday() == 6:        # no Sunday receiving
            continue
        h = int(rng.choice(24, p=np.array(HOUR_WEIGHTS) / sum(HOUR_WEIGHTS)))
        return d.replace(hour=h, minute=int(rng.integers(0, 60)))


def build_one(arrival, status_kind):
    """status_kind: 'done', 'pending' or 'hold'"""
    wh = pick([(k, v[1]) for k, v in WAREHOUSES.items()])
    code, _, gate_f, clerk_f = WAREHOUSES[wh]
    dock = f"{code}-D{int(rng.integers(1, DOCKS_PER_WH + 1))}"
    vnum = int(rng.integers(1, 13))
    cat = VENDOR_CATEGORY[vnum] if rng.random() < 0.8 else str(rng.choice(CATEGORIES))
    qty = int(np.clip(ln(400, 0.8), 40, 3000))

    disc_p = VENDOR_DISC[vnum] + (0.25 if status_kind == "hold" else 0)
    disc = rng.random() < disc_p
    short = damaged = 0
    if disc:
        if rng.random() < 0.6:
            short = max(1, int(qty * rng.uniform(0.01, 0.08)))
            if rng.random() < 0.25:
                damaged = max(1, int(qty * rng.uniform(0.005, 0.03)))
        else:
            damaged = max(1, int(qty * rng.uniform(0.005, 0.04)))
    elif rng.random() < 0.03:
        damaged = max(1, int(qty * rng.uniform(0.002, 0.01)))
        disc = False

    h = arrival.hour
    sh = shift_of(h)

    seg = {}
    seg["Gate Wait"] = ln(18 * gate_hour_factor(h) * gate_f * VENDOR_GATE_F[vnum], 0.7)
    seg["Dock Wait"] = ln(8, 0.6)
    seg["Unloading"] = ln(38 * (qty / 400) ** 0.35, 0.4)
    seg["Unload-to-QC Wait"] = ln(12, 0.6)
    seg["QC"] = ln(30 * (1.7 if disc else 1.0), 0.5)
    seg["QC-to-GRN Wait"] = ln(32 * SHIFT_WAIT_F[sh] * clerk_f * (1.5 if disc else 1.0), 0.9)
    seg["GRN Processing"] = ln(38 * (1.9 if disc else 1.0) * SHIFT_PROC_F[sh] * clerk_f, 0.75)
    seg["GRN-to-Putaway Wait"] = ln(16, 0.6)
    seg["Putaway"] = ln(24 * (qty / 400) ** 0.2, 0.5)
    seg = {k: max(1, int(round(v))) for k, v in seg.items()}

    t = {}
    t["Truck Arrival"] = arrival
    t["Dock Assigned"] = t["Truck Arrival"] + timedelta(minutes=seg["Gate Wait"])
    t["Unloading Start"] = t["Dock Assigned"] + timedelta(minutes=seg["Dock Wait"])
    t["Unloading End"] = t["Unloading Start"] + timedelta(minutes=seg["Unloading"])
    t["QC Start"] = t["Unloading End"] + timedelta(minutes=seg["Unload-to-QC Wait"])
    t["QC End"] = t["QC Start"] + timedelta(minutes=seg["QC"])
    t["GRN Start"] = t["QC End"] + timedelta(minutes=seg["QC-to-GRN Wait"])
    t["GRN Completed"] = t["GRN Start"] + timedelta(minutes=seg["GRN Processing"])
    t["Putaway Start"] = t["GRN Completed"] + timedelta(minutes=seg["GRN-to-Putaway Wait"])
    t["Putaway Completed"] = t["Putaway Start"] + timedelta(minutes=seg["Putaway"])

    # ----- work out the main delay stage + logged cause ---------------------
    if status_kind == "done":
        ratios = {k: seg[k] / SLA[k] for k in SLA}
        worst = max(ratios, key=ratios.get)
        if ratios[worst] <= 1:
            stage, cause = "Within SLA", "None"
        else:
            stage = worst
            cause = pick(CAUSE_BY_STAGE[stage])
            if disc and stage in ("QC", "QC-to-GRN Wait", "GRN Processing") and rng.random() < 0.6:
                cause = "Vendor" if rng.random() < 0.55 else "Documentation Mismatch"
        status = "Completed - Discrepancy" if (short + damaged) > 0 else "Completed"
    else:
        for k in ["GRN Start", "GRN Completed", "Putaway Start", "Putaway Completed"]:
            t[k] = None
        if status_kind == "pending":
            status = "Pending"
            cause = pick([("Manpower", .45), ("System", .25), ("Documentation Mismatch", .30)])
        else:
            status = "On Hold"
            cause = pick([("Documentation Mismatch", .5), ("Vendor", .35), ("System", .15)])

    row = {
        "Vendor": f"Vendor {vnum:02d}", "Warehouse": wh, "Dock ID": dock,
        "Category": cat, **t,
        "Quantity": qty, "Short Quantity": short, "Damaged Quantity": damaged,
        "GRN Status": status, "Delay Cause": cause,
    }
    return row


rows = []
# completed receipts
while len(rows) < N_TOTAL - N_PENDING - N_ON_HOLD:
    r = build_one(random_arrival(), "done")
    if r["Putaway Completed"] <= AS_OF:
        rows.append(r)
# pending: arrived in the 7-24 hours before the report time
while sum(1 for r in rows if r["GRN Status"] == "Pending") < N_PENDING:
    arr = AS_OF - timedelta(minutes=int(rng.integers(7 * 60, 24 * 60)))
    r = build_one(arr, "pending")
    if r["QC End"] <= AS_OF - timedelta(minutes=30):
        rows.append(r)
# on hold: receipts stuck for 2 to 21 days
while sum(1 for r in rows if r["GRN Status"] == "On Hold") < N_ON_HOLD:
    arr = AS_OF - timedelta(minutes=int(rng.integers(2 * 24 * 60, 21 * 24 * 60)))
    if arr.weekday() == 6:
        continue
    h = int(rng.choice(24, p=np.array(HOUR_WEIGHTS) / sum(HOUR_WEIGHTS)))
    arr = arr.replace(hour=h, minute=int(rng.integers(0, 60)))
    r = build_one(arr, "hold")
    if r["QC End"] <= AS_OF:
        rows.append(r)

df = pd.DataFrame(rows).sort_values("Truck Arrival").reset_index(drop=True)
df.insert(0, "Receipt ID", [f"RCPT-{i+1:05d}" for i in range(len(df))])
po = rng.choice(np.arange(10000, 99999), size=len(df), replace=False)
df.insert(1, "PO Number", [f"PO-26-{p}" for p in po])
sku_n = {c: i + 1 for i, c in enumerate(CATEGORIES)}
df.insert(4, "SKU", [f"SKU-{sku_n[c]:02d}-{int(rng.integers(100, 999))}" for c in df["Category"]])

order = ["Receipt ID", "PO Number", "Vendor", "Warehouse", "SKU", "Category", "Dock ID",
         "Truck Arrival", "Dock Assigned", "Unloading Start", "Unloading End",
         "QC Start", "QC End", "GRN Start", "GRN Completed",
         "Putaway Start", "Putaway Completed",
         "Quantity", "Short Quantity", "Damaged Quantity", "GRN Status", "Delay Cause"]
df = df[order]

out = Path(__file__).resolve().parent / "raw_inbound_data.csv"
df.to_csv(out, index=False, date_format="%Y-%m-%d %H:%M")
print(f"{len(df)} receipts -> {out}")
print(df["GRN Status"].value_counts().to_string())
