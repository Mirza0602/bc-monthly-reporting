// Quelle: microsoft/analytics/v1.0, generalLedgerAccounts und generalLedgerAccountCategories. Zuordnung aus pRepoPfad und "\config\kpi_mapping.csv", Spalten bucket und vorzeichen.
// Filter: keiner.
// Schlüssel: Kontonr (accountNo).
// Erwartete Zeilenzahl: 221
// Abweichung von B2: die Mapping-Spalte heißt bucket, nicht KPI-Zeile. Konten ohne Zeile bekommen bucket NICHT_ZUGEORDNET. GuV ohne Zeile bekommt vorzeichen -1, Bilanz ohne Zeile lässt vorzeichen leer. Hierarchie flach, Ebene 1 bis 3, Wurzel zuerst.
let
    Inhalt = fnQuelle("microsoft/analytics/v1.0"),
    KontenRoh = Inhalt{[Name = "generalLedgerAccounts"]}[Data],
    KategorienRoh = Inhalt{[Name = "generalLedgerAccountCategories"]}[Data],
    KontoText = (wert as any) as text =>
        if wert = null then
            ""
        else if Value.Is(wert, type number) then
            if Number.Round(wert, 0) = wert then Text.From(Int64.From(wert)) else Text.From(wert)
        else
            Text.Trim(Text.From(wert)),
    KontoartText = (wert as any) as nullable text =>
        let
            Textwert = if wert = null then null else Text.Trim(Text.From(wert)),
            Map = [
                Posting = "Buchung",
                Heading = "Überschrift",
                Total = "Summe",
                #"Begin-Total" = "Von-Summe",
                #"End-Total" = "Bis-Summe",
                Begin_x002D_Total = "Von-Summe",
                End_x002D_Total = "Bis-Summe"
            ]
        in
            if Textwert = null or Textwert = "" then
                null
            else if Record.HasFields(Map, Textwert) then
                Record.Field(Map, Textwert)
            else
                Textwert,
    BilanzText = (wert as any) as nullable text =>
        let
            Textwert = if wert = null then null else Text.Trim(Text.From(wert)),
            Map = [#"Balance Sheet" = "Bilanz", #"Income Statement" = "GuV"]
        in
            if Textwert = null or Textwert = "" then
                null
            else if Record.HasFields(Map, Textwert) then
                Record.Field(Map, Textwert)
            else
                Textwert,
    Kategorien = Table.TransformColumns(
        Table.TransformColumnTypes(
            KategorienRoh,
            {{"entryNo", Int64.Type}, {"parentEntryNo", Int64.Type}}
        ),
        {{"description", each if _ = null then null else Text.From(_), type text}}
    ),
    Pfad = (start as any) as list =>
        let
            Schritt = (aktuell as any, rest as list, schutz as number) as list =>
                let
                    Nummer =
                        if aktuell = null then
                            0
                        else
                            try Int64.From(aktuell) otherwise 0,
                    Gefunden = Table.SelectRows(Kategorien, each [entryNo] = Nummer),
                    Weiter =
                        if schutz <= 0 or Nummer = 0 or Table.IsEmpty(Gefunden) then
                            rest
                        else
                            @Schritt(
                                Gefunden{0}[parentEntryNo],
                                {Gefunden{0}[description]} & rest,
                                schutz - 1
                            )
                in
                    Weiter
        in
            Schritt(start, {}, 8),
    Blatt = (start as any) as nullable record =>
        let
            Nummer = if start = null then 0 else try Int64.From(start) otherwise 0,
            Gefunden = Table.SelectRows(Kategorien, each [entryNo] = Nummer)
        in
            if Nummer = 0 or Table.IsEmpty(Gefunden) then null else Gefunden{0},
    Element = (liste as list, index as number) as nullable text =>
        if List.Count(liste) > index then liste{index} else null,
    Konten = Table.RenameColumns(
        Table.TransformColumns(
            KontenRoh,
            {{"accountNo", each KontoText(_), type text}}
        ),
        {{"accountNo", "Kontonr"}, {"accountName", "Kontoname"}}
    ),
    MitBlatt = Table.AddColumn(Konten, "Blatt", each Blatt([accountSubcategoryEntryNo])),
    MitPfad = Table.AddColumn(MitBlatt, "Pfad", each Pfad([accountSubcategoryEntryNo])),
    Geformt = Table.SelectColumns(
        Table.AddColumn(
            Table.AddColumn(
                Table.AddColumn(
                    Table.AddColumn(
                        Table.AddColumn(
                            Table.AddColumn(
                                Table.AddColumn(
                                    Table.AddColumn(
                                        MitPfad,
                                        "Kontoart",
                                        each KontoartText([accountType]),
                                        type text
                                    ),
                                    "BilanzGuV",
                                    each BilanzText([incomeBalance]),
                                    type text
                                ),
                                "Kategorie",
                                each if [Blatt] = null then null else Text.From([Blatt][accountCategory]),
                                type text
                            ),
                            "Unterkategorie",
                            each if [Blatt] = null then null else [Blatt][description],
                            type text
                        ),
                        "Ebene1",
                        each Element([Pfad], 0),
                        type text
                    ),
                    "Ebene2",
                    each Element([Pfad], 1),
                    type text
                ),
                "Ebene3",
                each Element([Pfad], 2),
                type text
            ),
            "Sortierung",
            each if [Blatt] = null then null else Text.From([Blatt][presentationOrder]),
            type text
        ),
        {
            "Kontonr",
            "Kontoname",
            "Kontoart",
            "BilanzGuV",
            "Kategorie",
            "Unterkategorie",
            "Ebene1",
            "Ebene2",
            "Ebene3",
            "Sortierung"
        }
    ),
    Csv = Csv.Document(
        File.Contents(pRepoPfad & "\config\kpi_mapping.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    MappingRoh = Table.PromoteHeaders(Csv, [PromoteAllScalars = true]),
    Mapping = Table.Distinct(
        Table.TransformColumns(
            Table.SelectColumns(MappingRoh, {"konto", "bucket", "vorzeichen"}),
            {
                {"konto", each KontoText(_), type text},
                {
                    "vorzeichen",
                    each if _ = null or Text.Trim(Text.From(_)) = "" then null else Number.From(_),
                    type number
                }
            }
        ),
        {"konto"}
    ),
    Verknuepft = Table.NestedJoin(
        Geformt,
        {"Kontonr"},
        Mapping,
        {"konto"},
        "Map",
        JoinKind.LeftOuter
    ),
    Erweitert = Table.ExpandTableColumn(Verknuepft, "Map", {"bucket", "vorzeichen"}),
    MitBucket = Table.AddColumn(
        Erweitert,
        "bucketNeu",
        each
            if [bucket] = null or Text.Trim(Text.From([bucket])) = "" then
                "NICHT_ZUGEORDNET"
            else
                Text.Trim(Text.From([bucket])),
        type text
    ),
    MitVorzeichen = Table.AddColumn(
        MitBucket,
        "vorzeichenNeu",
        each
            if [vorzeichen] = null then
                if [bucketNeu] = "NICHT_ZUGEORDNET" and [BilanzGuV] = "GuV" then -1 else null
            else
                [vorzeichen],
        type number
    ),
    OhneAlt = Table.RemoveColumns(MitVorzeichen, {"bucket", "vorzeichen"}),
    Ergebnis = Table.RenameColumns(
        OhneAlt,
        {{"bucketNeu", "bucket"}, {"vorzeichenNeu", "vorzeichen"}}
    )
in
    Ergebnis
