// Quelle: microsoft/analytics/v1.0, customerLedgerEntries (Detailed).
// Filter: keiner. Das Filterfeld der Entität ist dclePostingDate und wird hier nicht angewendet. pStichtag filtert keine Zeile.
// Schlüssel: Eintragsnr (dcleEntryNo).
// Erwartete Zeilenzahl: 1145
// Abweichung von B2: Restbetrag und Offen zum Stichtag rechnet das Modell aus diesen Detailposten. OffenKennzeichen ist das Quellflag cleOpen und gilt nicht als Stichtagswert.
let
    Inhalt = fnQuelle("microsoft/analytics/v1.0"),
    Roh = Inhalt{[Name = "customerLedgerEntries"]}[Data],
    TextOderLeer = (wert as any) as nullable text =>
        let
            Textwert = if wert = null then null else Text.Trim(Text.From(wert))
        in
            if Textwert = null or Textwert = "" then null else Textwert,
    Datum = (wert as any) as nullable date => if wert = null then null else Date.From(wert),
    Umbenannt = Table.RenameColumns(
        Table.SelectColumns(
            Roh,
            {
                "dcleEntryNo",
                "cleEntryNo",
                "dclePostingDate",
                "cleDueDate",
                "dcleInitialEntryDueDate",
                "dcleAmountLCY",
                "dcleCustomerNo",
                "dcleDocumentNo",
                "dcleDocumentType",
                "dcleEntryType",
                "cleDimensionSetID",
                "cleOpen",
                "salesInvHeaderDocumentNo",
                "salesInvHeaderPaymentTermsCode"
            }
        ),
        {
            {"dcleEntryNo", "Eintragsnr"},
            {"cleEntryNo", "Postennr"},
            {"dclePostingDate", "Buchungsdatum"},
            {"cleDueDate", "Fälligkeit"},
            {"dcleInitialEntryDueDate", "Ursprungsfälligkeit"},
            {"dcleAmountLCY", "Betrag"},
            {"dcleCustomerNo", "Kundennr"},
            {"dcleDocumentNo", "Belegnr"},
            {"dcleDocumentType", "Belegart"},
            {"dcleEntryType", "Postenart"},
            {"cleDimensionSetID", "DimensionSetID"},
            {"cleOpen", "OffenKennzeichen"},
            {"salesInvHeaderDocumentNo", "Rechnungsnr"},
            {"salesInvHeaderPaymentTermsCode", "Zahlungsbedingung"}
        }
    ),
    Ergebnis = Table.TransformColumns(
        Umbenannt,
        {
            {"Eintragsnr", each Int64.From(_), Int64.Type},
            {"Postennr", each Int64.From(_), Int64.Type},
            {"Buchungsdatum", each Datum(_), type date},
            {"Fälligkeit", each Datum(_), type date},
            {"Ursprungsfälligkeit", each Datum(_), type date},
            {"Betrag", each if _ = null then null else Number.From(_), type number},
            {"Kundennr", each TextOderLeer(_), type text},
            {"Belegnr", each TextOderLeer(_), type text},
            {"Belegart", each TextOderLeer(_), type text},
            {"Postenart", each TextOderLeer(_), type text},
            {"DimensionSetID", each if _ = null then null else Int64.From(_), Int64.Type},
            {"Rechnungsnr", each TextOderLeer(_), type text},
            {"Zahlungsbedingung", each TextOderLeer(_), type text}
        }
    )
in
    Ergebnis
