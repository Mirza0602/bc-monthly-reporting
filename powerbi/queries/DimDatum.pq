// Quelle: generiert, kein API-Abruf.
// Filter: keiner. pStichtag filtert keine Zeile. IstAktuellerMonat vergleicht nur den Monat.
// Schlüssel: Datum.
// Erwartete Zeilenzahl: 1461
// Abweichung von B2: fester Bereich 01.01.2024 bis 31.12.2027, nicht ab dem ersten Posten bis Ende Folgejahr. Geschäftsjahr ist das Kalenderjahr, dateSetup ist nicht im Katalog.
let
    Start = #date(2024, 1, 1),
    Ende = #date(2027, 12, 31),
    Tage = List.Dates(Start, Duration.Days(Ende - Start) + 1, #duration(1, 0, 0, 0)),
    Basis = Table.FromList(Tage, Splitter.SplitByNothing(), {"Datum"}, null, ExtraValues.Error),
    Monatsnamen = {
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember"
    },
    MitJahr = Table.AddColumn(Basis, "Jahr", each Date.Year([Datum]), Int64.Type),
    MitMonat = Table.AddColumn(MitJahr, "Monat", each Date.Month([Datum]), Int64.Type),
    MitName = Table.AddColumn(
        MitMonat,
        "Monatsname",
        each Monatsnamen{Date.Month([Datum]) - 1},
        type text
    ),
    MitQuartal = Table.AddColumn(
        MitName,
        "Quartal",
        each Date.QuarterOfYear([Datum]),
        Int64.Type
    ),
    MitGeschaeftsjahr = Table.AddColumn(
        MitQuartal,
        "Geschäftsjahr",
        each Date.Year([Datum]),
        Int64.Type
    ),
    MitAktuell = Table.AddColumn(
        MitGeschaeftsjahr,
        "IstAktuellerMonat",
        each Date.Year([Datum]) = Date.Year(pStichtag) and Date.Month([Datum]) = Date.Month(pStichtag),
        type logical
    ),
    MitVorjahr = Table.AddColumn(
        MitAktuell,
        "Vorjahresdatum",
        each Date.AddYears([Datum], -1),
        type date
    ),
    Typisiert = Table.TransformColumnTypes(MitVorjahr, {{"Datum", type date}})
in
    Typisiert
