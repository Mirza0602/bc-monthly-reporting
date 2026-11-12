// Quelle: microsoft/analytics/v1.0, vendors.
// Filter: keiner.
// Schlüssel: Lieferantennr (vendorNo).
// Erwartete Zeilenzahl: 8
// Abweichung von B2: Zahlungsbedingung steht nicht an analytics vendors und entfällt. Kreditorenbuchungsgruppe ist vendorPostingGroup.
let
    Inhalt = fnQuelle("microsoft/analytics/v1.0"),
    Roh = Inhalt{[Name = "vendors"]}[Data],
    Ergebnis = Table.TransformColumnTypes(
        Table.RenameColumns(
            Table.SelectColumns(
                Roh,
                {"vendorNo", "vendorName", "countryRegionCode", "vendorPostingGroup"}
            ),
            {
                {"vendorNo", "Lieferantennr"},
                {"vendorName", "Name"},
                {"countryRegionCode", "Land"},
                {"vendorPostingGroup", "Kreditorenbuchungsgruppe"}
            }
        ),
        {
            {"Lieferantennr", type text},
            {"Name", type text},
            {"Land", type text},
            {"Kreditorenbuchungsgruppe", type text}
        }
    )
in
    Ergebnis
