// Quelle: microsoft/analytics/v1.0, items und itemCategories. Join über itemCategoryCode = code.
// Filter: keiner.
// Schlüssel: Artikelnr (itemNo).
// Erwartete Zeilenzahl: 80
// Abweichung von B2: keine bei der Zeilenzahl. Zusätzlich ArtikelkategorieCode und ÜbergeordneteKategorie aus itemCategories.parentCategory. Artikelkategorie kommt aus itemCategories.description, sonst aus itemCategoryDescription.
let
    Inhalt = fnQuelle("microsoft/analytics/v1.0"),
    ArtikelRoh = Inhalt{[Name = "items"]}[Data],
    KategorieRoh = Inhalt{[Name = "itemCategories"]}[Data],
    Kategorien = Table.Distinct(
        Table.TransformColumns(
            Table.SelectColumns(KategorieRoh, {"code", "description", "parentCategory"}),
            {{"code", each if _ = null then "" else Text.Trim(Text.From(_)), type text}}
        ),
        {"code"}
    ),
    Artikel = Table.TransformColumns(
        ArtikelRoh,
        {{"itemCategoryCode", each if _ = null then "" else Text.Trim(Text.From(_)), type text}}
    ),
    Verknuepft = Table.NestedJoin(
        Artikel,
        {"itemCategoryCode"},
        Kategorien,
        {"code"},
        "Kategorie",
        JoinKind.LeftOuter
    ),
    Erweitert = Table.ExpandTableColumn(
        Verknuepft,
        "Kategorie",
        {"description", "parentCategory"},
        {"KategorieName", "ÜbergeordneteKategorie"}
    ),
    MitName = Table.AddColumn(
        Erweitert,
        "Artikelkategorie",
        each
            if [KategorieName] <> null and Text.Trim(Text.From([KategorieName])) <> "" then
                Text.From([KategorieName])
            else if [itemCategoryDescription] = null then
                null
            else
                Text.From([itemCategoryDescription]),
        type text
    ),
    Ergebnis = Table.TransformColumnTypes(
        Table.RenameColumns(
            Table.SelectColumns(
                MitName,
                {
                    "itemNo",
                    "itemDescription",
                    "Artikelkategorie",
                    "itemCategoryCode",
                    "ÜbergeordneteKategorie",
                    "baseUnitofMeasure",
                    "inventoryPostingGroup"
                }
            ),
            {
                {"itemNo", "Artikelnr"},
                {"itemDescription", "Beschreibung"},
                {"itemCategoryCode", "ArtikelkategorieCode"},
                {"baseUnitofMeasure", "Basiseinheit"},
                {"inventoryPostingGroup", "Lagerbuchungsgruppe"}
            }
        ),
        {
            {"Artikelnr", type text},
            {"Beschreibung", type text},
            {"Artikelkategorie", type text},
            {"ArtikelkategorieCode", type text},
            {"ÜbergeordneteKategorie", type text},
            {"Basiseinheit", type text},
            {"Lagerbuchungsgruppe", type text}
        }
    )
in
    Ergebnis
