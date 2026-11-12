# Power-Query-Vorlagen

Stand 26.10.2026. Die Daten laufen über den Standard-Connector von Microsoft in Power BI, ohne zusätzliche Infrastruktur.

Abfragename in Power BI Desktop = Dateiname. Sonst finden `pUmgebung`, `fnQuelle` und `fnBetrag` einander nicht.

## Reihenfolge

1. Parameter: `pUmgebung`, `pMandant`, `pStichtag`, `pRepoPfad`.
2. Hilfsabfragen: `fnQuelle`, `fnBetrag`. Beides Funktionen.
3. Dimensionen: `DimDatum`, `DimKonto`, `DimDimensionsSet`, `DimKunde`, `DimLieferant`, `DimArtikel`.
4. Fakten: `FactSachposten`, `FactDebitorenposten`, `FactKreditorenposten`, `FactWertposten`, `FactSaldenliste`.

Einfügen: Leere Abfrage, erweiterter Editor, Inhalt der `.pq`-Datei einfügen, Abfrage wie die Datei benennen. Wird ein Parameter nicht als Parameter erkannt: Rechtsklick, in Parameter konvertieren. Typ und Standardwert stehen in der Datei.

`pStichtag` filtert in keiner Abfrage eine Zeile. `DimDatum` setzt damit nur `IstAktuellerMonat`. Die Zeilenzahl bleibt 1.461.

`DimKonto` liest zusätzlich `pRepoPfad` und `\config\kpi_mapping.csv`. Der Ordner muss das Repo sein.

Keine Abfrage `FactBudget`. Ein Budget ist nicht vorhanden. Der Demo-Plan ist ein Measure im Modell.

## Einrichtung in Power BI Desktop

Optionen, CURRENT FILE, Data Load:

- Background Data aus. Die Datenvorschau lädt sonst im Hintergrund und öffnet neben der Aktualisierung weitere Verbindungen zu Business Central.
- Parallel loading auf One. Die Tabellen kommen nacheinander von Business Central, nicht mehrere gleichzeitig.
- Auto date/time aus. DimDatum ist die Datumstabelle, sonst legt Power BI je Datumsspalte eine eigene Tabelle an.
- Autodetect relationships aus. Gleichnamige Spalten würden sonst Beziehungen erzeugen. Die Beziehungen sind im Modell gesetzt.

Datenschutzebenen: Business Central und `c:\git\bc-monthly-reporting` auf Organizational, sonst blockiert Power BI die Kombination aus Konten und `config\kpi_mapping.csv` in DimKonto.

Enable load aus für `pUmgebung`, `pMandant`, `pRepoPfad`, `fnQuelle`, `fnBetrag`. `pStichtag` bleibt geladen, das Measure Stichtag liest die Spalte.

### Abnahme

Beide Blöcke nacheinander im DAX-Abfragefenster ausführen.

DAX-Abfrage P9, Zeilen je Tabelle gegen `erwartete_zeilen.csv`:

```dax
// P9: Zeilen im Modell gegen Snapshot 24.10.2026
EVALUATE
VAR T =
    UNION (
        ROW ( "Tabelle", "DimDatum",             "Ist", COUNTROWS ( DimDatum ),             "Erwartet", 1461 ),
        ROW ( "Tabelle", "DimKonto",             "Ist", COUNTROWS ( DimKonto ),             "Erwartet", 221 ),
        ROW ( "Tabelle", "DimDimensionsSet",     "Ist", COUNTROWS ( DimDimensionsSet ),     "Erwartet", 37 ),
        ROW ( "Tabelle", "DimKunde",             "Ist", COUNTROWS ( DimKunde ),             "Erwartet", 5 ),
        ROW ( "Tabelle", "DimLieferant",         "Ist", COUNTROWS ( DimLieferant ),         "Erwartet", 8 ),
        ROW ( "Tabelle", "DimArtikel",           "Ist", COUNTROWS ( DimArtikel ),           "Erwartet", 80 ),
        ROW ( "Tabelle", "FactSachposten",       "Ist", COUNTROWS ( FactSachposten ),       "Erwartet", 4384 ),
        ROW ( "Tabelle", "FactDebitorenposten",  "Ist", COUNTROWS ( FactDebitorenposten ),  "Erwartet", 1145 ),
        ROW ( "Tabelle", "FactKreditorenposten", "Ist", COUNTROWS ( FactKreditorenposten ), "Erwartet", 869 ),
        ROW ( "Tabelle", "FactWertposten",       "Ist", COUNTROWS ( FactWertposten ),       "Erwartet", 878 ),
        ROW ( "Tabelle", "FactSaldenliste",      "Ist", COUNTROWS ( FactSaldenliste ),      "Erwartet", 3315 )
    )
RETURN
    ADDCOLUMNS ( T, "Differenz", [Ist] - [Erwartet] )
ORDER BY [Differenz] DESC
```

Ladetest Saldenliste:

```dax
// Ladetest Saldenliste: muss 2.253.031,00 ergeben
EVALUATE
ROW (
    "Saldo 1102 zum 30.09.2026",
    CALCULATE (
        SUM ( FactSaldenliste[SaldoSoll] ) - SUM ( FactSaldenliste[SaldoHaben] ),
        FactSaldenliste[Kontonr] = "1102",
        FactSaldenliste[periodEnd] = DATE ( 2026, 9, 30 )
    )
)
```

Ergebnis 26.10.2026: alle Differenzen 0, Saldo 1102 = 2.253.031,00.

## Bekannte Fallstricke

Die direkte Parameterübergabe an ApiContentsWithOptions hat beim Laden die Meldung "Verbindung vom Remotehost geschlossen" erzeugt, getestet am 25.10.2026. fnQuelle ruft den Connector deshalb ohne Parameter auf, wie der Navigator, und wählt die Umgebung mit Text.Upper(pUmgebung), weil der Navigator PRODUCTION zeigt. v2.0 liegt direkt unter der Firma, die Analytics API liegt unter "Advanced".

FactSachposten verwendet kein Table.NestedJoin gegen eine OData-Quelle. Der Join wurde nicht an Business Central weitergegeben und erzeugte Einzelanfragen je Zeile, worauf Business Central die Verbindung geschlossen hat (26.10.2026). Die Abschlussnummern holt die Abfrage einmal mit List.Buffer, je Zeile prüft List.Contains.

## Anmeldung

Organisationskonto, derselbe Benutzer wie in Business Central. Kein Gateway. Im Dienst später derselbe Kontotyp, kein lokales Datengateway.

## Ladetest Saldenliste

Ladetest am 26.10.2026 bestanden, Konto 1102 zum 30.09.2026 = 2.253.031,00, der Connector gibt den dateFilter an BC weiter.

Nach dem Aktualisieren von `FactSaldenliste`: Konto 1102, `periodEnd` 30.09.2026, `SaldoSoll` minus `SaldoHaben` = 2.253.031,00.

Die Vorschau im Editor faltet Filter nicht. Das steht so auf der Leistungsseite von Microsoft. Der Ladetest gilt für Aktualisieren, nicht für die Vorschau.

Native Abfrage: Rechtsklick auf den Schritt `F_M202609`. Steht dort `dateFilter ge 2026-09-01` und `dateFilter le 2026-09-30`, hat der Connector den Filter übergeben.

Zeilenzahlen der übrigen Abfragen stehen in `erwartete_zeilen.csv`.

## Abweichungen vom ursprünglichen Konzept

| Thema | B2 | diese Vorlagen |
| --- | --- | --- |
| DimDimensionsSet | `dimensionSetEntries`, sechs Dimensionen, ID 0 ohne Dimension | `dynamicDimensions`, nur Abteilung und Debitorengruppe, Code und Name. `dimensionSetEntries` hat 0 Zeilen. ID 0 mit "nicht zugeordnet". 37 Zeilen. |
| Kontonr | ein Kontofeld | GuV `accountNo` und Bilanz `glAccountNo` auf `Kontonr` |
| Abschlussbuchungen | `IstAbschlussbuchung` aus Closing oder C-Datum | Flag nur aus `closingGeneralLedgerEntries`. 0 Zeilen, überall false. |
| FactBudget | Budgetposten | keine Abfrage. Der Demo-Plan ist ein Measure im Modell. |
| Saldenliste | letzte 13 Monatsenden | 15 Zeiträume wie der Snapshot. 3.315 Zeilen. |
| Geschäftsjahr | `dateSetup` oder Buchungsperioden | Kalenderjahr. `DimDatum` vom 01.01.2024 bis zum 31.12.2027. |

## Vorzeichen Wertposten

DB I ist `Verkaufsbetrag` plus `EinstandsbetragTatsächlich`. Der Einstand der Verkaufswertposten ist negativ. Der Wareneinsatz im Bericht ist positiv. Die Regeln stehen in `docs\02_datenmodell.md`.

`FactWertposten` hat 878 Zeilen: 532 Verkaufswertposten liegen alle in den 878 Artikelwertposten, 346 Zeilen nur dort.

Nachtrag 01.11.2026. Die Prüfabfrage Stufe 2 ist bestanden. Monat und YTD 09/2026 liegen gegen die Sollwerte auf 0.
Bestandswert bleibt bei -240,00, Status erklärt.
Fehlerbehebung PLACEHOLDER: In Bewegung Sachposten und Lagerzugang Verrechnung steht der Stichtag als KEEPFILTERS ( FILTER ( ALL ( DimDatum[Datum] ), DimDatum[Datum] <= [Stichtag] ) ). Ein Measure darf nicht in einem einfachen Boolean-Filter stehen.
FactWertposten.pq enthält die Spalte Artikelpostenart wie das Modell. Die Zeilenzahl bleibt 878.
Repo und Modell sind damit deckungsgleich.
