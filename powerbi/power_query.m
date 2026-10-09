// =====================================================================
// power_query.m  |  Dock-to-Stock Bottleneck Analytics
// Paste each block below into its own blank query (Home > New Source >
// Blank Query > Advanced Editor). Names matter: FilePath, Receipts, SLA, Segments.
// Source = the Excel workbook in /excel (Inbound_Data sheet).
// =====================================================================


// ---------------------------------------------------------------------
// QUERY 1: FilePath   (a text parameter; change it to your own path)
// ---------------------------------------------------------------------
"C:\Projects\dock-to-stock-bottleneck-analytics\excel\dock_to_stock_analysis.xlsx"


// ---------------------------------------------------------------------
// QUERY 2: Receipts   (one row per inbound receipt)
// ---------------------------------------------------------------------
let
    Source   = Excel.Workbook(File.Contents(FilePath), null, true),
    Data     = Source{[Item = "Inbound_Data", Kind = "Sheet"]}[Data],
    Promoted = Table.PromoteHeaders(Data, [PromoteAllScalars = true]),

    // Open receipts leave some formula cells as empty text. Turn them into real nulls.
    NoBlanks = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, Table.ColumnNames(Promoted)),

    Typed = Table.TransformColumnTypes(NoBlanks, {
        {"Truck Arrival", type datetime}, {"Dock Assigned", type datetime},
        {"Unloading Start", type datetime}, {"Unloading End", type datetime},
        {"QC Start", type datetime}, {"QC End", type datetime},
        {"GRN Start", type datetime}, {"GRN Completed", type datetime},
        {"Putaway Start", type datetime}, {"Putaway Completed", type datetime},
        {"Quantity", Int64.Type}, {"Short Quantity", Int64.Type}, {"Damaged Quantity", Int64.Type},
        {"Arrival Hour", Int64.Type},
        {"Gate Wait (min)", type number}, {"Dock Wait (min)", type number},
        {"Unloading (min)", type number}, {"Unload-to-QC Wait (min)", type number},
        {"QC (min)", type number}, {"QC-to-GRN Wait (min)", type number},
        {"GRN Processing (min)", type number}, {"GRN-to-Putaway Wait (min)", type number},
        {"Putaway (min)", type number}, {"Total Dock-to-Stock (min)", type number},
        {"GRN Age (hrs)", type number}, {"Worst SLA Ratio", type number}
    }, "en-US"),

    AddDate = Table.AddColumn(Typed, "Truck Arrival Date", each DateTime.Date([Truck Arrival]), type date),

    AddBucket = Table.AddColumn(AddDate, "GRN Age Bucket", each
        if [#"GRN Age (hrs)"] < 2  then "0-2 hrs"
        else if [#"GRN Age (hrs)"] < 6  then "2-6 hrs"
        else if [#"GRN Age (hrs)"] < 24 then "6-24 hrs"
        else if [#"GRN Age (hrs)"] < 72 then "24-72 hrs"
        else "72+ hrs", type text),

    AddBucketOrder = Table.AddColumn(AddBucket, "GRN Age Bucket Order", each
        if [GRN Age Bucket] = "0-2 hrs" then 1
        else if [GRN Age Bucket] = "2-6 hrs" then 2
        else if [GRN Age Bucket] = "6-24 hrs" then 3
        else if [GRN Age Bucket] = "24-72 hrs" then 4
        else 5, Int64.Type)
in
    AddBucketOrder


// ---------------------------------------------------------------------
// QUERY 3: SLA   (segment names, type and SLA targets; same as Assumptions sheet)
// ---------------------------------------------------------------------
let
    Source = #table(
        type table [Segment = text, Type = text, #"SLA Minutes" = number, Order = Int64.Type],
        {
            {"Gate Wait",           "Waiting",     30, 1},
            {"Dock Wait",           "Waiting",     15, 2},
            {"Unloading",           "Processing",  60, 3},
            {"Unload-to-QC Wait",   "Waiting",     15, 4},
            {"QC",                  "Processing",  45, 5},
            {"QC-to-GRN Wait",      "Waiting",     30, 6},
            {"GRN Processing",      "Processing",  45, 7},
            {"GRN-to-Putaway Wait", "Waiting",     20, 8},
            {"Putaway",             "Processing",  40, 9}
        })
in
    Source


// ---------------------------------------------------------------------
// QUERY 4: Segments   (one row per receipt per segment; feeds the Bottleneck Score)
// ---------------------------------------------------------------------
let
    Source = Receipts,
    Keep = Table.SelectColumns(Source, {
        "Receipt ID", "Vendor", "Warehouse", "Shift", "Dock ID", "Arrival Hour",
        "Gate Wait (min)", "Dock Wait (min)", "Unloading (min)", "Unload-to-QC Wait (min)",
        "QC (min)", "QC-to-GRN Wait (min)", "GRN Processing (min)",
        "GRN-to-Putaway Wait (min)", "Putaway (min)"}),
    Unpivoted = Table.UnpivotOtherColumns(Keep,
        {"Receipt ID", "Vendor", "Warehouse", "Shift", "Dock ID", "Arrival Hour"},
        "Segment Raw", "Minutes"),
    // Receipts that never reached a step have null minutes. Drop them.
    HasValue = Table.SelectRows(Unpivoted, each [Minutes] <> null),
    AddSegment = Table.AddColumn(HasValue, "Segment", each Text.Replace([Segment Raw], " (min)", ""), type text),
    Joined = Table.NestedJoin(AddSegment, {"Segment"}, SLA, {"Segment"}, "SLA", JoinKind.LeftOuter),
    Expanded = Table.ExpandTableColumn(Joined, "SLA", {"Type", "SLA Minutes", "Order"})
in
    Expanded
