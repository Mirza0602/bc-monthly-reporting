# Kennzahlen

Stand 12.11.2026

Berichtsmonat September 2026, Stichtag 30.09.2026. Die Beträge stehen im [Abstimmprotokoll September 2026](abstimmung/Abstimmprotokoll_2026-09.md). Vorzeichen und Buckets stehen im [Datenmodell](02_datenmodell.md).

## 1. Fünf Kennzahlen von Seite 01

| Kennzahl | Basis-Measure | Quelltabelle | Vorzeichen | Prüfung | September 2026 | YTD | Differenz |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Umsatz | Umsatz | FactSachposten, Bucket UMSATZ | -1, Haben wird im Bericht positiv | P4 | 6.966,00 | 362.007,38 | 0,00 |
| Rohertrag | Rohertrag | FactSachposten und FactWertposten | steckt in Umsatz und Wareneinsatz | Überleitung zu P5 | 1.532,00 | 101.633,18 | 0,00 |
| EBIT | EBIT | FactSachposten | steckt in den Bausteinen | P5 | -8.528,00 | 86.973,18 | 0,00 |
| Offene Forderungen | Offene Forderungen | FactDebitorenposten | wie in den Posten, Soll bleibt positiv | P6 | 68.041,07 |  | 0,00 |
| Bestandswert | Bestandswert | FactWertposten | wie in den Wertposten, Soll bleibt positiv | P8 | 2.266.906,50 |  | -240,00, erklärt |

Umsatz ist die Bewegung der Konten im Bucket UMSATZ. Erlösminderungen 4730 und 4770 bleiben darin. Konto 4201 nicht. Abstimmquelle ist die Saldenliste.

Rohertrag ist Umsatz minus Wareneinsatz. Der Wareneinsatz ist die Nettobewegung der Wareneinsatzkonten minus den Lagerzugang mit Habenvorzeichen. Abstimmquelle ist die Überleitung, beide Seiten Differenz 0,00. Die Marge ist Rohertrag geteilt durch Umsatz: 1.532,00 / 6.966,00 ergibt 22,0 %, 101.633,18 / 362.007,38 ergibt 28,1 %. Das Basis-Measure der Marge heißt Rohertragsmarge.

EBIT ist Umsatz plus sonstiger Ertrag und Aufwand minus Wareneinsatz minus Betriebsaufwand minus Abschreibung. Zins, Steuer, Lagerzugang und nicht zugeordnete Konten stehen darunter. Abstimmquelle ist die Saldenliste.

Offene Forderungen sind die Summe FactDebitorenposten[Betrag] je Postennr, Buchungsdatum bis zum Berichtsende, offen ab 0,01. Abstimmquelle ist der Saldo der Konten 1202 und 1203. Der Wert gilt zum Stichtag.

Bestandswert ist die Summe FactWertposten[EinstandsbetragTatsächlich] mit Buchungsdatum bis zum Berichtsende. Abstimmquelle ist der Saldo der Konten 1001, 1101 und 1102. Die Differenz -240,00 bleibt stehen, Status erklärt.

## 2. Zeitvarianten

YTD, Vorjahr und Plan entstehen aus dem Basis-Measure über die Berechnungsgruppe Zeitauswahl. Es gibt dafür keine zweite Definition.

YTD ist dasselbe Measure vom 1. Januar bis zum Berichtsende.

Vorjahr Monat ist dasselbe Measure im Monat vor einem Jahr. Vorjahr YTD ist das Fenster vom 1. Januar bis zum Berichtsende, ein Jahr früher. Das Vorjahr kommt aus den Sachposten. Die Saldenliste hat nur 15 Zeiträume und enthält die Kalendermonate vor August 2025 nicht.

Plan (Demo) ist das Vorjahr mal den Planfaktor 1,05. Ein Budget in Business Central ist nicht vorhanden, generalLedgerBudgets und generalLedgerBudgetEntries haben 0 Zeilen. Bestand, Verbindlichkeiten, offene Forderungen und die Abstimmung bleiben im Plan leer. Die Rohertragsmarge im Plan bleibt die Vorjahresmarge, ohne den Faktor.

## 3. Abweichung und Signalfarbe

Signalfarbe gibt es nur, wenn die Abweichung zum Vorjahr Monat oder zum Plan ungleich 0 ist und mal der Signalrichtung größer als 0 ist. Null, ein leerer Wert, eine Zeile ohne Richtung und die Abweichung zum Vorjahr YTD bleiben in der Textfarbe.

Aufwand, also Wareneinsatz, Betriebsaufwand und Abschreibung, hat die Richtung 1. Ein Anstieg ist ungünstig. Ertrag, also Umsatz, Rohertrag, EBIT und sonstiger Ertrag und Aufwand, hat die Richtung -1. Ein Rückgang ist ungünstig. Die Measures heißen GuV Signalrichtung, GuV Farbe VJ und GuV Farbe Plan.

## 4. Kennzahlen der Seiten 02 bis 04

GuV Monat zeigt die Zeile der Abstimmzeile im Berichtsmonat, GuV YTD seit Jahresanfang, GuV Vorjahr Monat im Vorjahresmonat. GuV Δ VJ ist die Abweichung zum Vorjahr Monat, GuV Δ VJ YTD die Abweichung zum Vorjahr seit Jahresanfang, GuV Plan (Demo) Monat den Demo-Plan, GuV Δ Plan die Abweichung zum Plan. Kostenart Δ VJ ist die Abweichung einer Kostenart zum Vorjahr Monat.

Forderungen Klasse und Verbindlichkeiten Klasse teilen die offenen Posten nach Faelligkeitsklasse. Die Grenzen sind inklusive: nicht fällig von -99999 bis 0 Tage, 1 bis 30 Tage, 31 bis 60 Tage, 61 bis 90 Tage, über 90 Tage von 91 bis 99999. Die Tage sind der Stichtag minus die Fälligkeit.

DB I ist Verkauf Umsatz minus Verkauf Einstand. DB I Marge ist DB I geteilt durch Verkauf Umsatz. Verkauf Umsatz YTD, DB I YTD und DB I Marge YTD setzen dieselbe Definition auf das Jahr.

Bestandswert je Kategorie filtert das Measure Bestandswert über DimArtikel[Artikelkategorie]. Bestandswert je Lagerort filtert dasselbe Measure über FactWertposten[Lagerort].

## 5. Abstimmung

Ergebnis September 2026. Sammelkonten, verifiziert aus der BC-Einrichtung: Forderungen 1202 und 1203, Verbindlichkeiten 3301 und 3302, Lager 1001, 1101 und 1102. Prüfkonto 1085 hat den Saldo 0,00. Das Lagerkorrekturkonto der Buchungsmatrix HANDEL ist 5021. Verbindlichkeiten stehen im Bericht positiv.

| Prüfung | Inhalt | Ergebnis September 2026 |
| --- | --- | --- |
| P1 | Summe Soll gleich Summe Haben über alle Sachposten | 0,00 |
| P2 | Bewegung im Monat je Buchungskonto gegen die Änderung der Endsalden | 0,00 |
| P3 | Saldo zum Stichtag je Buchungskonto gegen die Saldenliste | 0,00 |
| P4 | Umsatz | 0,00, Monat und YTD |
| P5 | EBIT. Die Überleitung ergibt 0,00 | 0,00, Monat und YTD |
| P5b | Wareneinsatz gegen minus costPostedToGL der Verkaufswertposten | 0,00 |
| P6 | Offene Forderungen gegen 1202 und 1203 | 0,00 |
| P7 | Verbindlichkeiten gegen 3301 und 3302 | 0,00 |
| P8 | Bestandswert gegen 1001, 1101 und 1102. Eine bekannte Differenz bleibt stehen | -240,00, erklärt |
| P9 | Zeilenzahl im Snapshot gegen manifest.json | Summe der absoluten Abweichungen 0 |

[Abstimmprotokoll August 2026](abstimmung/Abstimmprotokoll_2026-08.md). [Abstimmprotokoll September 2026](abstimmung/Abstimmprotokoll_2026-09.md).
