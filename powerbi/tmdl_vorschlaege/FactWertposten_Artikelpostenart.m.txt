// Quelle: microsoft/analytics/v1.0, salesValueEntries vereinigt mit itemValueEntries.
// Filter: keiner. pStichtag filtert keine Zeile.
// Schlüssel: Eintragsnr (entryNo), nach der Vereinigung eindeutig.
// Erwartete Zeilenzahl: 878
// AP-05 Stufe 2, neu: Spalte Artikelpostenart, Typ text, aus itemLedgerEntryType der Artikelwertposten. Verkaufswertposten-Zweig setzt null. Gruppierung weiter nur über Eintragsnr, Zeilenzahl bleibt 878.
// Abweichung von B2: Menge ist invoicedQuantity des Wertpostens. ArtikelpostenNr hängt nur an den Verkaufswertposten. Snapshot 24.10.2026: Verkauf 532, Artikel 878, Schnitt 532, nur Verkauf 0, nur Artikel 346. costAmountActual und invoicedQuantity stimmen auf den 532 gemeinsamen Nummern. Verkaufsbetrag und Kundennr kommen vom Verkauf, sonst leer. Einstandsbetrag bleibt wie in BC, negativ bei Verkauf.
let
    Inhalt = fnQuelle("microsoft/analytics/v1.0"),
    Erster = (liste as list) as any =>
        let
            Gefuellt = List.RemoveNulls(liste)
        in
            if List.IsEmpty(Gefuellt) then null else List.First(Gefuellt),
    Datum = (wert as any) as nullable date => if wert = null then null else Date.From(wert),
    Zahl = (wert as any) as nullable number => if wert = null then null else Number.From(wert),
    Ganz = (wert as any) as nullable number => if wert = null then null else Int64.From(wert),
    TextOderLeer = (wert as any) as nullable text =>
        let
            Textwert = if wert = null then null else Text.Trim(Text.From(wert))
        in
            if Textwert = null or Textwert = "" then null else Textwert,
    ArtikelBasis = Table.RenameColumns(
        Table.SelectColumns(
            Inhalt{[Name = "itemValueEntries"]}[Data],
            {
                "entryNo",
                "postingDate",
                "itemNo",
                "dimensionSetID",
                "locationCode",
                "invoicedQuantity",
                "costAmountActual",
                "costAmountExpected",
                "costPostedToGL",
                // AP-05 Stufe 2, neu: Artikelpostenart nur aus den Artikelwertposten.
                "itemLedgerEntryType"
            }
        ),
        {
            {"entryNo", "Eintragsnr"},
            {"postingDate", "Buchungsdatum"},
            {"itemNo", "Artikelnr"},
            {"dimensionSetID", "DimensionSetID"},
            {"locationCode", "Lagerort"},
            {"invoicedQuantity", "Menge"},
            {"costAmountActual", "EinstandsbetragTatsächlich"},
            {"costAmountExpected", "EinstandsbetragErwartet"},
            {"costPostedToGL", "KostenAnFibu"},
            // AP-05 Stufe 2, neu.
            {"itemLedgerEntryType", "Artikelpostenart"}
        }
    ),
    Artikel = Table.AddColumn(
        Table.AddColumn(
            Table.AddColumn(
                Table.AddColumn(ArtikelBasis, "Verkaufsbetrag", each null),
                "Kundennr",
                each null
            ),
            "Belegnr",
            each null
        ),
        "ArtikelpostenNr",
        each null
    ),
    VerkaufBasis = Table.RenameColumns(
        Table.SelectColumns(
            Inhalt{[Name = "salesValueEntries"]}[Data],
            {
                "entryNo",
                "postingDate",
                "itemNo",
                "dimensionSetID",
                "locationCode",
                "invoicedQuantity",
                "costAmountActual",
                "costPostedToGL",
                "salesAmountActual",
                "customerNo",
                "documentNo",
                "itemLedgerEntryNo"
            }
        ),
        {
            {"entryNo", "Eintragsnr"},
            {"postingDate", "Buchungsdatum"},
            {"itemNo", "Artikelnr"},
            {"dimensionSetID", "DimensionSetID"},
            {"locationCode", "Lagerort"},
            {"invoicedQuantity", "Menge"},
            {"costAmountActual", "EinstandsbetragTatsächlich"},
            {"costPostedToGL", "KostenAnFibu"},
            {"salesAmountActual", "Verkaufsbetrag"},
            {"customerNo", "Kundennr"},
            {"documentNo", "Belegnr"},
            {"itemLedgerEntryNo", "ArtikelpostenNr"}
        }
    ),
    // AP-05 Stufe 2, neu: Verkaufswertposten-Zweig setzt Artikelpostenart auf null, Typ text.
    Verkauf = Table.AddColumn(
        Table.AddColumn(VerkaufBasis, "EinstandsbetragErwartet", each null),
        "Artikelpostenart",
        each null,
        type text
    ),
    Spalten = {
        "Eintragsnr",
        "Buchungsdatum",
        "Artikelnr",
        "DimensionSetID",
        "Lagerort",
        "Menge",
        "EinstandsbetragTatsächlich",
        "EinstandsbetragErwartet",
        "KostenAnFibu",
        "Verkaufsbetrag",
        "Kundennr",
        "Belegnr",
        "ArtikelpostenNr",
        // AP-05 Stufe 2, neu.
        "Artikelpostenart"
    },
    ArtikelGleich = Table.TransformColumns(
        Table.SelectColumns(Artikel, Spalten),
        {{"Eintragsnr", each Int64.From(_), Int64.Type}}
    ),
    VerkaufGleich = Table.TransformColumns(
        Table.SelectColumns(Verkauf, Spalten),
        {{"Eintragsnr", each Int64.From(_), Int64.Type}}
    ),
    // Artikel zuerst. Gemeinsame Beträge stimmen überein, fehlende Verkaufsfelder bleiben null und fallen in Erster heraus.
    // AP-05 Stufe 2: Artikelpostenart kommt von den Artikelwertposten. Im Verkaufszweig ist sie null und fällt in Erster heraus.
    Vereinigt = Table.Combine({ArtikelGleich, VerkaufGleich}),
    Gruppiert = Table.Group(
        Vereinigt,
        {"Eintragsnr"},
        {
            {"Buchungsdatum", each Erster([Buchungsdatum]), type any},
            {"Artikelnr", each Erster([Artikelnr]), type any},
            {"DimensionSetID", each Erster([DimensionSetID]), type any},
            {"Lagerort", each Erster([Lagerort]), type any},
            {"Menge", each Erster([Menge]), type any},
            {"EinstandsbetragTatsächlich", each Erster([EinstandsbetragTatsächlich]), type any},
            {"EinstandsbetragErwartet", each Erster([EinstandsbetragErwartet]), type any},
            {"KostenAnFibu", each Erster([KostenAnFibu]), type any},
            {"Verkaufsbetrag", each Erster([Verkaufsbetrag]), type any},
            {"Kundennr", each Erster([Kundennr]), type any},
            {"Belegnr", each Erster([Belegnr]), type any},
            {"ArtikelpostenNr", each Erster([ArtikelpostenNr]), type any},
            // AP-05 Stufe 2, neu. Typ text.
            {"Artikelpostenart", each Erster([Artikelpostenart]), type text}
        }
    ),
    Ergebnis = Table.Sort(
        Table.TransformColumns(
            Gruppiert,
            {
                {"Eintragsnr", each Ganz(_), Int64.Type},
                {"Buchungsdatum", each Datum(_), type date},
                {"Artikelnr", each TextOderLeer(_), type text},
                {"DimensionSetID", each Ganz(_), Int64.Type},
                {"Lagerort", each TextOderLeer(_), type text},
                {"Menge", each Zahl(_), type number},
                {"EinstandsbetragTatsächlich", each Zahl(_), type number},
                {"EinstandsbetragErwartet", each Zahl(_), type number},
                {"KostenAnFibu", each Zahl(_), type number},
                {"Verkaufsbetrag", each Zahl(_), type number},
                {"Kundennr", each TextOderLeer(_), type text},
                {"Belegnr", each TextOderLeer(_), type text},
                {"ArtikelpostenNr", each Ganz(_), Int64.Type},
                // AP-05 Stufe 2, neu. Typ text.
                {"Artikelpostenart", each TextOderLeer(_), type text}
            }
        ),
        {{"Eintragsnr", Order.Ascending}}
    )
in
    Ergebnis
