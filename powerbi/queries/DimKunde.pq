// Quelle: microsoft/analytics/v1.0, customers.
// Filter: keiner.
// Schlüssel: Kundennr (customerNo).
// Erwartete Zeilenzahl: 5
// Abweichung von B2: Zahlungsbedingung steht nicht an analytics customers und entfällt. Kundengruppe ist customerPriceGroup, Debitorenbuchungsgruppe ist customerPostingGroup.
let
    Inhalt = fnQuelle("microsoft/analytics/v1.0"),
    Roh = Inhalt{[Name = "customers"]}[Data],
    Ergebnis = Table.TransformColumnTypes(
        Table.RenameColumns(
            Table.SelectColumns(
                Roh,
                {
                    "customerNo",
                    "customerName",
                    "customerPriceGroup",
                    "countryRegionCode",
                    "customerPostingGroup"
                }
            ),
            {
                {"customerNo", "Kundennr"},
                {"customerName", "Name"},
                {"customerPriceGroup", "Kundengruppe"},
                {"countryRegionCode", "Land"},
                {"customerPostingGroup", "Debitorenbuchungsgruppe"}
            }
        ),
        {
            {"Kundennr", type text},
            {"Name", type text},
            {"Kundengruppe", type text},
            {"Land", type text},
            {"Debitorenbuchungsgruppe", type text}
        }
    )
in
    Ergebnis
