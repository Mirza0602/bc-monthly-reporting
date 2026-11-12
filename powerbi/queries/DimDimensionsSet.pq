// Quelle: microsoft/analytics/v1.0, dynamicDimensions. Nicht dimensionSetEntries (0 Zeilen).
// Filter: keiner. Abteilung ist customDimensionCode ABTEILUNG, Debitorengruppe ist DEBITORENGRUPPE.
// Schlüssel: DimensionSetID.
// Erwartete Zeilenzahl: 37
// Abweichung von B2: eine Zeile je dimensionSetID aus dynamicDimensions, nicht dimensionSetEntries. Nur Abteilung und Debitorengruppe, jeweils Code und Name. 36 Sets im Snapshot, ID 0 fehlt dort und wird ergänzt. Fehlt eine Dimension am Set, steht "nicht zugeordnet".
let
    Inhalt = fnQuelle("microsoft/analytics/v1.0"),
    Roh = Inhalt{[Name = "dynamicDimensions"]}[Data],
    Schmal = Table.TransformColumns(
        Table.SelectColumns(
            Roh,
            {
                "dimensionSetID",
                "customDimensionCode",
                "customDimensionValueCode",
                "customDimensionValueName"
            }
        ),
        {
            {"dimensionSetID", each Int64.From(_), Int64.Type},
            {"customDimensionCode", each Text.Trim(Text.From(_)), type text}
        }
    ),
    IDs = Table.Distinct(Table.SelectColumns(Schmal, {"dimensionSetID"})),
    Abteilung = Table.Distinct(
        Table.SelectRows(Schmal, each [customDimensionCode] = "ABTEILUNG"),
        {"dimensionSetID"}
    ),
    Debitor = Table.Distinct(
        Table.SelectRows(Schmal, each [customDimensionCode] = "DEBITORENGRUPPE"),
        {"dimensionSetID"}
    ),
    MitAbteilung = Table.NestedJoin(
        IDs,
        {"dimensionSetID"},
        Abteilung,
        {"dimensionSetID"},
        "A",
        JoinKind.LeftOuter
    ),
    ExpandA = Table.ExpandTableColumn(
        MitAbteilung,
        "A",
        {"customDimensionValueCode", "customDimensionValueName"},
        {"AbteilungCode", "AbteilungName"}
    ),
    MitDebitor = Table.NestedJoin(
        ExpandA,
        {"dimensionSetID"},
        Debitor,
        {"dimensionSetID"},
        "D",
        JoinKind.LeftOuter
    ),
    ExpandD = Table.ExpandTableColumn(
        MitDebitor,
        "D",
        {"customDimensionValueCode", "customDimensionValueName"},
        {"DebitorengruppeCode", "DebitorengruppeName"}
    ),
    Umbenannt = Table.RenameColumns(ExpandD, {{"dimensionSetID", "DimensionSetID"}}),
    NullZeile = #table(
        type table [
            DimensionSetID = Int64.Type,
            AbteilungCode = text,
            AbteilungName = text,
            DebitorengruppeCode = text,
            DebitorengruppeName = text
        ],
        {{0, "nicht zugeordnet", "nicht zugeordnet", "nicht zugeordnet", "nicht zugeordnet"}}
    ),
    MitNull =
        if List.Contains(Umbenannt[DimensionSetID], 0) then
            Umbenannt
        else
            Table.Combine({NullZeile, Umbenannt}),
    Textspalten = {
        "AbteilungCode",
        "AbteilungName",
        "DebitorengruppeCode",
        "DebitorengruppeName"
    },
    Gefuellt = Table.ReplaceValue(
        MitNull,
        null,
        "nicht zugeordnet",
        Replacer.ReplaceValue,
        Textspalten
    ),
    Sortiert = Table.Sort(Gefuellt, {{"DimensionSetID", Order.Ascending}}),
    Ergebnis = Table.TransformColumnTypes(
        Sortiert,
        {
            {"DimensionSetID", Int64.Type},
            {"AbteilungCode", type text},
            {"AbteilungName", type text},
            {"DebitorengruppeCode", type text},
            {"DebitorengruppeName", type text}
        }
    )
in
    Ergebnis
