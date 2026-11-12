# Abstimmprotokoll August 2026

## Kopf

| Angabe | Wert |
| --- | --- |
| Firma | CRONUS DE |
| Umgebung | Production |
| Stichtag | 31.08.2026 |
| Zeitpunkt | 24.10.2026 18:45 |
| Datenstand | 24.10.2026, Snapshot 2026-10-24 |
| Toleranz | 0,00 EUR |

## Kennzahlen

| Prüfung | Kennzahl | Periode | Sachposten | Saldenliste | Differenz | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P4 | Umsatz | Monat | 54.759,64 | 54.759,64 | 0,00 | abgeglichen |
| P4 | Umsatz | YTD | 355.041,38 | 355.041,38 | 0,00 | abgeglichen |
| P5 | EBIT | Monat | 12.445,84 | 12.445,84 | 0,00 | abgeglichen |
| P5 | EBIT | YTD | 95.501,18 | 95.501,18 | 0,00 | abgeglichen |
| P6 | Offene Forderungen | Stichtag | 68.041,07 | 68.041,07 | 0,00 | abgeglichen |
| P7 | Verbindlichkeiten | Stichtag | 54.135,85 | 54.135,85 | 0,00 | abgeglichen |
| P8 | Bestandswert | Stichtag | 2.228.990,50 | 2.229.230,50 | -240,00 | erklärt |

Forderungskonten 1202, 1203. Quelle und Status: verifiziert (BC-Einrichtung). Debitorenbuchungsgruppen. Verbindlichkeitskonten 3301, 3302. Quelle und Status: verifiziert (BC-Einrichtung). Kreditorenbuchungsgruppen. Lagerkonten 1001, 1101, 1102. Quelle und Status: verifiziert (BC-Einrichtung). Lagerbuchung Einrichtung. Lagerkorrekturkonto der Buchungsmatrix HANDEL ist 5021. Erklärt die Habenbuchung des Anfangsbestands 2025 auf 5021 (Befund a). Prüfkonto 1085 Unf. Arbeiten Fertigung. Sachposten 0,00, Saldenliste 0,00, erwartet 0,00, Differenz 0,00. Quelle und Status: verifiziert (BC-Einrichtung).

Verbindlichkeiten stehen im Bericht positiv. Die Saldenliste führt sie im Haben, der Vergleich dreht das Vorzeichen auf beiden Seiten.

Hinweis Lagerregulierung: costAmountActual minus costPostedToGL ist 0,00.

## Überleitung Ergebnis

EBIT ist Umsatz minus Wareneinsatz minus Betriebsaufwand minus Abschreibung plus sonstiger Ertrag und Aufwand. Lagerzugang, Zins, Steuer und nicht zugeordnete Konten stehen darunter. Die Summe muss dem vorzeichenrichtigen Ergebnis aller GuV-Konten entsprechen.

| Position | Monat Sachposten | Monat Saldenliste | Monat Differenz | YTD Sachposten | YTD Saldenliste | YTD Differenz |
| --- | --- | --- | --- | --- | --- | --- |
| Umsatz | 54.759,64 | 54.759,64 | 0,00 | 355.041,38 | 355.041,38 | 0,00 |
| Wareneinsatz | 42.313,80 | 42.313,80 | 0,00 | 254.940,20 | 254.940,20 | 0,00 |
| Rohertrag | 12.445,84 | 12.445,84 | 0,00 | 100.101,18 | 100.101,18 | 0,00 |
| Betriebsaufwand | 0,00 | 0,00 | 0,00 | 4.600,00 | 4.600,00 | 0,00 |
| Abschreibung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| Sonstiger Ertrag und Aufwand | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| EBIT | 12.445,84 | 12.445,84 | 0,00 | 95.501,18 | 95.501,18 | 0,00 |
| Zins und Finanz | 0,00 | 0,00 | 0,00 | -26.244,83 | -26.244,83 | 0,00 |
| davon Fehlbuchung Kundenzahlungen auf 4201 | 0,00 | 0,00 | 0,00 | -26.244,83 | -26.244,83 | 0,00 |
| Steuer | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| Lagerzugang Verrechnung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| Nicht zugeordnet | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| Summe Überleitung | 12.445,84 | 12.445,84 | 0,00 | 69.256,35 | 69.256,35 | 0,00 |
| Ergebnis GuV | 12.445,84 | 12.445,84 | 0,00 | 69.256,35 | 69.256,35 | 0,00 |
| Differenz | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |

## Überleitung Wertposten

Verkaufsbetrag und Einstandsbetrag kommen aus den Verkaufswertposten. Der Einstandsbetrag ist costAmountActual und negativ. P5b stellt den Wareneinsatz gegen minus costPostedToGL.

| Position | Monat | YTD |
| --- | --- | --- |
| Verkaufsbetrag | 54.759,64 | 355.041,38 |
| Einstandsbetrag Verkauf | -42.313,80 | -254.940,20 |
| Umsatz FiBu | 54.759,64 | 355.041,38 |
| Wareneinsatz FiBu | 42.313,80 | 254.940,20 |
| Verkaufsbetrag minus Umsatz | 0,00 | 0,00 |
| Konto 4201 Soll minus Haben | 0,00 | 26.244,83 |
| Wareneinsatz plus Einstand | 0,00 | 0,00 |

## P5b Wareneinsatz gegen Verkaufswertposten

WARENEINSATZ aus der FiBu, nach Abzug der Lagerzugangsverrechnung, gegen minus Summe costPostedToGL der Verkaufswertposten. Je Monat und YTD, 2025 und 2026. Toleranz 0,00.

| Zeitraum | Wareneinsatz FiBu | Verkauf an FiBu | Differenz |
| --- | --- | --- | --- |
| 2025 YTD | 389.625,70 | 389.625,70 | 0,00 |
| 2026-08 | 42.313,80 | 42.313,80 | 0,00 |
| 2026 YTD | 254.940,20 | 254.940,20 | 0,00 |

Alle Monate und die YTD-Zeilen haben Differenz 0,00.

## Konten

P2 ist die Bewegung im Monat, P3 der Saldo zum Stichtag. Die Saldenliste ist die Änderung der Endsalden beziehungsweise der Endsaldo. Summen- und Überschriftenkonten stehen hier nicht. Die Saldenliste zählt sie zusätzlich zu den Buchungskonten.

| Konto | Name | P2 Sachposten | P2 Saldenliste | P2 Differenz | P3 Sachposten | P3 Saldenliste | P3 Differenz |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0148 | Aufwand für Entwicklung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0150 | Goodwill | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0170 | Anzahlungen für immaterielle Anlagen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0200 | Land | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0210 | Abgänge während des Jahres | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0220 | Miet- und Pachtverhältnisse sowie ähnliche Rechte | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0260 | Gebäude | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0280 | Zugänge während des Jahres | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0290 | Kosten für Verbesserungen an gemieteten Liegenschaften | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0400 | Geräte und Werkzeuge | 0,00 | 0,00 | 0,00 | 59.693,00 | 59.693,00 | 0,00 |
| 0490 | Kumulierte Abschreibungen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0510 | Leasingobjekte | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0520 | Autos und sonstige Transportmittel | 0,00 | 0,00 | 0,00 | 117.168,00 | 117.168,00 | 0,00 |
| 0635 | Computer | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0750 | Voraus bezahlte Miete | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0804 | Beteiligung an Konzernunternehmen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0814 | Ausleihe an Partner oder zugehörige Parteien | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0920 | Wertpapiere | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 0940 | Wandelschuldverschreibungen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1001 | Rohstoffe | 0,00 | 0,00 | 0,00 | 14.115,50 | 14.115,50 | 0,00 |
| 1002 | Hilfs- und Betriebsstoffe | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1051 | Produkte in Bearbeitung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1081 | WIP-Projektumsätze | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1082 | WIP-Projektkosten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1083 | RIF, Aufgelaufene Kosten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1084 | RIF, fakturierte Verkäufe | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1085 | Unf. Arbeiten Fertigung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1101 | Fertigerzeugnisse | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1102 | Waren für Wiederverkauf | -42.313,80 | -42.313,80 | 0,00 | 2.215.115,00 | 2.215.115,00 | 0,00 |
| 1178 | Sonstige Lagerartikel | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1180 | Anzahlungen für Waren und Dienstleistungen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1202 | Forderungen, Inland | 0,00 | 0,00 | 0,00 | 13.427,37 | 13.427,37 | 0,00 |
| 1203 | Forderungen, Ausland | 0,00 | 0,00 | 0,00 | 54.613,70 | 54.613,70 | 0,00 |
| 1225 | Langfristige Forderungen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1260 | Kurzfristige Forderungen gegenüber Konzernunternehmen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1340 | Kurzfristige Forderungen gegen Personal | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1375 | Forderungen aus Verträgen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1400 | Sonst. Umsatzsteuerforderungen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1403 | Einkauf zu reduziertem MwSt.-Satz | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1406 | Einkauf zu normalem MwSt.-Satz | 0,00 | 0,00 | 0,00 | 127.506,05 | 127.506,05 | 0,00 |
| 1410 | Steueransprüche | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1480 | Verrechnungskonten für Steuern und Abgaben | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1610 | Bar | 61.513,28 | 61.513,28 | 0,00 | -208.195,92 | -208.195,92 | 0,00 |
| 1810 | Geschäftskonto, Betrieb, Inland | 0,00 | 0,00 | 0,00 | 11.573,18 | 11.573,18 | 0,00 |
| 1820 | Geschäftskonto, Betrieb, Ausland | 0,00 | 0,00 | 0,00 | -11.573,18 | -11.573,18 | 0,00 |
| 1830 | Sonstige Bankkonten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1900 | Aktiva in Form von vorausbezahlten Aufwendungen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1950 | Aktive latente Steuern | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 1990 | Einlagenzertifikat | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 2000 | Eigenkapitalpartner | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 2010 | Grundkapital | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 2100 | Verteilungen an Anteilseigner | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 2720 | Gewinne und Verluste | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 2970 | Gewinn oder Verlust aus dem Vorjahr | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3011 | Geschätzte Lohnsteuer auf Pensionskosten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3040 | Geschätzte Einkommensteuer | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3079 | Fonds für Urlaubsgeld | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3100 | Anleihen und Schuldverschreibungen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3120 | Wandeldarlehen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3150 | Sonstige langfristige Verbindlichkeiten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3151 | Banküberziehungskredite | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3181 | Kurzfristige Banküberziehung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3250 | Anzahlungen von Debitoren | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3301 | Verbindlichkeiten, Inland | 0,00 | 0,00 | 0,00 | -45.551,65 | -45.551,65 | 0,00 |
| 3302 | Verbindlichkeiten, Ausland | 0,00 | 0,00 | 0,00 | -8.584,20 | -8.584,20 | 0,00 |
| 3500 | Sonstige Verbindlichkeiten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3510 | Firmenkreditkarten-Verrechnungskonto | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3560 | Laufende Darlehen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3700 | Geschuldete Steuern | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3720 | Quellensteuern Mitarbeitende | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3721 | Kurzfristige Verbindlichkeiten gegenüber Mitarbeitern | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3725 | Lohn-/Gehaltspfändungen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3740 | Gesetzliche Sozialabgaben | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3800 | Sonstige MwSt.-Verbindlichkeiten | 0,00 | 0,00 | 0,00 | -31.149,12 | -31.149,12 | 0,00 |
| 3801 | Verkäufe zum reduzierten MwSt.-Satz | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3806 | Verkauf zum normalen MwSt.-Satz | -6.753,64 | -6.753,64 | 0,00 | -88.075,18 | -88.075,18 | 0,00 |
| 3900 | Abgegrenzte Umsätze | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 3990 | Sonstige antizipative Aufwendungen und Rechnungsabgrenzungsposten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4091 | Direkte Kosten verrech., Kapazität | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4092 | Gemeinkosten verrechnet, Kapazität | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4093 | Einkaufsabweichung, Handel | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4150 | Mitarbeiterzahlungen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4201 | Erträge aus Wertpapieren | 0,00 | 0,00 | 0,00 | 26.244,83 | 26.244,83 | 0,00 |
| 4202 | Ertrag aus Managementgebühren | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4203 | Zinseinnahmen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4401 | Verkauf von Fertigerzeugnissen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4402 | Umsatz von Rohmaterialien | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4403 | Wiederverkauf von Waren | -55.258,70 | -55.258,70 | 0,00 | -855.522,20 | -855.522,20 | 0,00 |
| 4411 | Umsatz von Ressource | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4412 | Fremdarbeitsumsatz | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4415 | Projektumsätze | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4416 | Projektverkaufsausgleich | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4417 | Umsätze aus Serviceverträgen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4418 | Umsätze aus Servicearbeiten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4730 | Verkaufsrabatte | 499,06 | 499,06 | 0,00 | 955,42 | 955,42 | 0,00 |
| 4770 | Retouren | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4830 | Sonstige Nebeneinnahmen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4840 | Währungsgewinne | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 4985 | Sonstiges | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5021 | Materialaufwand | 42.313,80 | 42.313,80 | 0,00 | -1.540.999,60 | -1.540.999,60 | 0,00 |
| 5022 | Materialkosten, Projekte | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5031 | Einkaufsabweichung, Bearb. | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5032 | Materialabweichung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5033 | Material - Abweichung von Nicht-Lagerbest. | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5034 | Kapazitätsabweichung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5035 | Abweichung Fremdarbeit | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5036 | Abw. Kapazitätsgemeinkosten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5037 | Prod.-Gemeinkostenabweichung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5039 | Kosten für Abweichungen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5041 | Projektkosten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5042 | Projektkosten, ausgeglichen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5901 | Arbeitskosten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5902 | Arbeitskosten, Projekte | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5903 | Arbeitskosten, Garantie/Vertrag | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 5904 | Fremdarbeit | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6010 | Stundenlöhne | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6011 | Überstundenvergütung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6012 | Bezahlte Provisionen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6020 | Gehälter | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6029 | Boni | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6100 | Arbeitgeberbeiträge | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6150 | Rentenbeiträge und wiederkehrende Kosten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6160 | Krankenversicherung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6220 | Abschreibung, Anlagevermögen | 0,00 | 0,00 | 0,00 | 144.639,00 | 144.639,00 | 0,00 |
| 6221 | Abschreibung, Land und Liegenschaften | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6300 | Sonstige externe Ausgaben | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6303 | Sonstige externe Leistungen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6310 | Miete/Pacht | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6320 | Heizung für Mietobjekte | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6325 | Strom für Mietobjekte | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6326 | Wasser und Abwasser für Mietobjekte | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6330 | Reinigung und Abfallentsorgung für Mietobjekte | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6335 | Reparaturen und Instandhaltung für Miete | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6340 | Versicherungen, Miete | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6345 | Sonstige Mieten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6400 | Unternehmensversicherung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6500 | Pkw-Kosten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6520 | LKW-Kosten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6595 | Sonstige Kfz-Kosten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6600 | Anzeigenentwicklung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6601 | Außen- und Verkehrswerbung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6602 | Anzeigenmaterial und Direktwerbung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6603 | Konferenz-/Ausstellungsförderung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6604 | Film-, TV-, Radio-, Internetwerbung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6605 | Proben, Wettbewerbe, Geschenke | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6640 | Bewirtungskosten, abzugsfähig | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6644 | Bewirtungskosten, nicht abzugsfähig | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6650 | Sonstige Reisespesen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6658 | Kilometergeld für Reisekosten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6660 | Kost und Logis | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6662 | Verpflegungsausgaben, nicht abzugsfähig | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6663 | Tickets | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6664 | Reisekosten-Tagespauschale | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6668 | Mietfahrzeuge | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6690 | Kreditkartenkosten | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6740 | Frachtkosten für Waren | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6760 | Zoll und Versand | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6780 | Frachtkosten, Projekte | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6800 | Postgebühren | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6805 | Telefondienste | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6810 | Datendienste | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6815 | Bürobedarf | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6825 | Rechtskosten und Anwaltsleistungen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6827 | Jahres-/Zwischenberichte | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6830 | Buchhaltung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6836 | Vermietung von Maschinen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6837 | Software und Abonnementgebühren | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6840 | Verleih von Computern | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6845 | Vermietung anderer Anlagevermögen | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6850 | Verbrauchsmaterial/Erweiterbare Hardware | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6880 | Währungsverluste | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 6930 | Forderungsverluste | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 7130 | Einkaufsrabatte | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 7400 | Fällige Rechnungen, Rundung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 7500 | Verkaufsrechnungsrundung | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| 60410 | Versorgungsaufwand - Kraftwerk | 0,00 | 0,00 | 0,00 | 4.600,00 | 4.600,00 | 0,00 |

## Konten mit Bewegung

Bis zum Stichtag des Snapshots. Die Zuordnung ist der Vorschlag aus Kontoname und Kategorie und wird fachlich geprüft. Konto 5021 hat eine Zeile. Die Zerlegung steht in der Überleitung.

| Konto | Name | Bucket | Regel |
| --- | --- | --- | --- |
| 4201 | Erträge aus Wertpapieren | ZINS_FINANZ | NETTO |
| 4403 | Wiederverkauf von Waren | UMSATZ | NETTO |
| 4730 | Verkaufsrabatte | UMSATZ | NETTO |
| 5021 | Materialaufwand | WARENEINSATZ | NETTO |
| 6220 | Abschreibung, Anlagevermögen | ABSCHREIBUNG | NETTO |
| 6740 | Frachtkosten für Waren | BETRIEBSAUFWAND | NETTO |
| 6825 | Rechtskosten und Anwaltsleistungen | BETRIEBSAUFWAND | NETTO |
| 6837 | Software und Abonnementgebühren | BETRIEBSAUFWAND | NETTO |
| 60410 | Versorgungsaufwand - Kraftwerk | BETRIEBSAUFWAND | NETTO |

## Abweichungskonten

Konten 5032, 5033, 5034, 5035, 5036, 5037. Bucket WARENEINSATZ. Bewegung laut AP-01: keine. Im Snapshot bis zum Stichtag ebenfalls keine Bewegung.

| Konto | Name | Soll | Haben |
| --- | --- | --- | --- |
| 5032 | Materialabweichung | 0,00 | 0,00 |
| 5033 | Material - Abweichung von Nicht-Lagerbest. | 0,00 | 0,00 |
| 5034 | Kapazitätsabweichung | 0,00 | 0,00 |
| 5035 | Abweichung Fremdarbeit | 0,00 | 0,00 |
| 5036 | Abw. Kapazitätsgemeinkosten | 0,00 | 0,00 |
| 5037 | Prod.-Gemeinkostenabweichung | 0,00 | 0,00 |

## Befunde und Ursachen

a) Konto 5021 hat 2025 im Haben 2.185.565,50. Davon stehen 2.185.565,50 auf 35 Sachposten mit Beleg STANDARD, Quellcode LWERTBUCH, Buchungsdatum 01.06.2025. Die Beschreibung in der FiBu lautet Direkte Kosten. Artikelwertposten 2025 mit Betrag: Positive Adjmt. / (leer): 41 Posten, Einstand 2.185.565,50, an FiBu 2.185.565,50, Purchase / Purchase Invoice: 210 Posten, Einstand 423.603,00, an FiBu 423.603,00, Sale / Sales Invoice: 347 Posten, Einstand -389.625,70, an FiBu -389.625,70. Die API der Artikelwertposten hat in diesem Katalog kein Feld Eintragsart und keine Belegnummer. Die Artikelposten dazu: Positive Adjmt. Beleg STANDARD: 41 Posten, Einstand 2.185.565,50. Positive Adjmt. mit Beleg STANDARD ist ein Artikelbuchblatt, keine Einkaufsrechnung, und costPostedToGL trifft den Einstand. Die Lagerzugangsverrechnung 2025 aus costPostedToGL trifft diese Habenseite. Das Lagerkorrekturkonto der Buchungsmatrix HANDEL ist 5021. Das erklärt die Habenbuchung des Anfangsbestands 2025 auf 5021.
b) Erlöse FiBu gegen Verkaufsbetrag, YTD. Verkaufsbetrag 355.041,38, Umsatz 355.041,38, Differenz 0,00. 4201 liegt im Finanzergebnis, nicht im Umsatz. Soll minus Haben auf 4201 ist 26.244,83. Die Posten sind Kundenzahlungen, Belegart Payment, Quellcode FIBUBUCHBL, Herkunft Customer. Belegnummern 103199 bis 103214, Beschreibung 102206 bis 102221. Fehlbuchung der Demodaten. Sie wird nicht im Umsatz korrigiert. Der Kontoname (Erträge aus Wertpapieren) passt nicht zur Buchung.
c) Dimensionen auf GuV-Posten. Abteilung 8,1 % (83 von 1.022), Debitorengruppe 87,2 % (891 von 1.022). Nicht zugeordnet heißt: das Dimensionsset des Postens trägt die Dimension nicht. Umsatz YTD ohne Abteilung: 100,0 % (144 von 144), Betrag 100,0 %. Wareneinsatz YTD ohne Abteilung: 100,0 % (169 von 169), Betrag 100,0 %. Betriebsaufwand YTD ohne Abteilung: 100,0 % (1 von 1), Betrag 100,0 %. Abschreibung YTD: keine Posten.
d) Kategorienlücken in BC. 1102 Waren für Wiederverkauf steht in der Hierarchie unter Anlagen. Die Kategorie Lagerbestand ist das nicht. 1001 Rohstoffe steht unter Lagerbestand. 0210 Abgänge während des Jahres hat die v2-Kategorie Assets und keine Unterkategorie (Hierarchieeintrag 0). 0280 Zugänge während des Jahres hat die v2-Kategorie Assets und keine Unterkategorie (Hierarchieeintrag 0). 1085 Unf. Arbeiten Fertigung hat die v2-Kategorie Assets und keine Unterkategorie (Hierarchieeintrag 0). 2720 Gewinne und Verluste hat die v2-Kategorie Expense und keine Unterkategorie (Hierarchieeintrag 0). 4091 Direkte Kosten verrech., Kapazität hat die v2-Kategorie Cost of Goods Sold und keine Unterkategorie (Hierarchieeintrag 0). 60410 Versorgungsaufwand - Kraftwerk hat die v2-Kategorie Expense und keine Unterkategorie (Hierarchieeintrag 0). 60410 hat Bewegung und liegt deshalb im Betriebsaufwand, die fünf Konten ohne Bewegung bleiben ohne Bucket-Wirkung.
e) Konto 5021 hat 2026 bis 31.08.2026 im Haben 297,80. Kein Sachposten hat Haben 297,80. Die Habenseite: 01.04.2026 Beleg 108001 Soll 0,00 Haben 148,90, Direkte Kosten am 01.04.26, LWERTBUCH; 01.04.2026 Beleg 109001 Soll 0,00 Haben 148,90, Direkte Kosten am 01.04.26, LWERTBUCH. Soll auf denselben Belegen: 01.04.2026 Beleg 108001 Soll 148,90 Haben 0,00, Direkte Kosten am 01.04.26, LWERTBUCH; 01.04.2026 Beleg 109001 Soll 148,90 Haben 0,00, Direkte Kosten am 01.04.26, LWERTBUCH. Auf jedem dieser Belege ist das Soll auf 5021 gleich dem Haben. Die Posten heben sich belegweise auf. Ein einzelnes Soll-Haben-Paar über den Summenbetrag gibt es nicht. Sollposten über 297,80 auf anderen Belegen: 16.01.2026 Beleg 103162 Soll 297,80 Haben 0,00, Direkte Kosten 50000 am 16.01.26, LWERTBUCH; 18.01.2026 Beleg 103165 Soll 297,80 Haben 0,00, Direkte Kosten 10000 am 18.01.26, LWERTBUCH; 16.02.2026 Beleg 103178 Soll 297,80 Haben 0,00, Direkte Kosten 10000 am 16.02.26, LWERTBUCH; 17.02.2026 Beleg 103179 Soll 297,80 Haben 0,00, Direkte Kosten 50000 am 17.02.26, LWERTBUCH; 15.03.2026 Beleg 103188 Soll 297,80 Haben 0,00, Direkte Kosten 50000 am 15.03.26, LWERTBUCH; 20.05.2026 Beleg 103235 Soll 297,80 Haben 0,00, Direkte Kosten 40000 am 20.05.26, LWERTBUCH; 09.07.2026 Beleg 103267 Soll 297,80 Haben 0,00, Direkte Kosten 10000 am 09.07.26, LWERTBUCH. Das sind nicht die Gegenbuchungen der Habenseite. Diese Habenposten sind keine Zugänge der Art Positive Adjmt. oder Output. Sie bleiben in der Nettobewegung. Der Lagerzugang aus den Wertposten ist davon getrennt.
Posten nach dem Stichtag dieses Protokolls: 103, 01.09.2026 bis 01.09.2027. Posten nach dem Stichtag des Snapshots: 48, 01.10.2026 bis 01.09.2027. Sie fließen in keinen Periodenwert. Differenzen werden nicht gegengerechnet.
P8 Differenz -240,00. costAmountActual minus costPostedToGL ist 0,00, eine nicht gebuchte Lagerregulierung ist das damit nicht. Belegweise weichen 999 Belege ab. 998 davon heben sich in der Summe auf (0,00). Artikelposten und FiBu führen für dieselbe Rechnung unterschiedliche Belegnummern, Verkauf 102 gegen 103, Einkauf 107 gegen 108. Übrig bleibt Beleg 108210 am 06.04.2026, FiBu 240,00, Artikelposten 0,00, Artikel CC-1000, Eintragsart Direct Cost, Artikelpostenart Purchase. Beleg 108210. Sachposten: Konto 1102 Soll 240,00 Haben 0,00, Rechnung 107213, EINKAUF; Konto 1406 Soll 45,60 Haben 0,00, Rechnung 107213, EINKAUF; Konto 3800 Soll 0,00 Haben 45,60, Rechnung 107213, EINKAUF; Konto 3302 Soll 0,00 Haben 240,00, Rechnung 107213, EINKAUF; Konto 1610 Soll 0,00 Haben 240,00, Rechnung 107213, EINKAUF; Konto 3302 Soll 240,00 Haben 0,00, Rechnung 107213, EINKAUF. Wertposten: Einkaufswertposten 307 Artikel CC-1000 Direct Cost costAmountActual 0,00 Artikelposten 307; Artikelwertposten 307 Artikel CC-1000 Purchase Einstand 0,00 an FiBu 0,00. Artikelposten: Artikelposten 307 Beleg 107216 Purchase Purchase Receipt Artikel CC-1000 Menge 1,00 Einstand 0,00. Artikel CC-1000 Kohlenstoffgutschrift 3 Tonnen CO₂-Äquivalent, Typ Non-Inventory, Produktbuchungsgruppe HANDEL, Lagerbuchungsgruppe leer. Die Differenz sitzt auf dem Bestandskonto des Belegs. Der zugehörige Wertposten und der Artikelposten haben Einstand 0,00. Der Artikel ist kein Lagerartikel. Warum die FiBu das Bestandskonto belastet, steht in der Buchungsmatrix. Die liegt nicht im Snapshot. Die Ursache ist damit nicht eindeutig. Beleg 107213 aus der Beschreibung ist Artikelposten 305, Artikel 2000-S, Purchase. Ursache: Allgemeine Buchungsmatrix, Produktbuchungsgruppe HANDEL: Wareneinkaufskonto 1102 (EU, EXPORT, INLAND), Direkte Kosten Verrech.-Konto 1102. Bei Lagerartikeln hebt die Lagerbuchung den Einkauf auf 1102 auf. CC-1000 ist ein Nicht-Lagerartikel ohne Lagerbuchung, daher bleibt der Einkauf auf 1102 stehen. Einrichtungsfehler der Demofirma. Quelle: BC Seite 314 Buchungsmatrix Einrichtung, geprüft von Mirza am 24.10.2026. Beleg 108210, Artikel CC-1000. Status: erklärt. Der Betrag bleibt stehen und wird nicht verrechnet.

## Prüfweg

P1 Summe Soll minus Summe Haben über alle Sachposten: 0,00.
P2 je Buchungskonto: Summe der Sachposten im Monat gegen Endsaldo Monatsende minus Endsaldo Vormonatsende.
P3 je Buchungskonto: Summe der Sachposten bis zum Stichtag gegen balanceAtDateDebit minus balanceAtDateCredit.
P4 Umsatz ist minus die Nettobewegung des Buckets UMSATZ. 4730 und 4770 bleiben als Erlösminderung im Umsatz. 4201 liegt im Finanzergebnis.
P5 EBIT aus den GuV-Buckets ohne Zins, Steuer, Lagerzugang Verrechnung und Nicht zugeordnet. Die Überleitung oben muss 0,00 ergeben.
Konto 5021 hat eine Zeile NETTO. Wareneinsatz ist die Nettobewegung plus costPostedToGL der Artikelwertposten mit Artikelpostenart Positive Adjmt. oder Output. Das ist die Nettobewegung minus denselben Betrag mit Habenvorzeichen. Im Bericht steht der Lagerzugang positiv. Derselbe Betrag wird auf Sachposten und Saldenliste angesetzt, damit P5 die beiden Wege vergleicht.
P5b stellt diesen Wareneinsatz gegen minus Summe costPostedToGL der Verkaufswertposten, je Monat und YTD, für 2025 und 2026. Toleranz 0,00.
YTD ist Endsaldo Stichtag minus Endsaldo 31.12. des Vorjahres. Der Jahresanker 01.01.2024 bis 31.12.2024 liegt in derselben Saldenliste.
P6 offene Forderungen aus dcleAmountLCY mit dclePostingDate bis zum Stichtag, je cleEntryNo, offen ab 0,01. Gegen Saldo der Forderungskonten.
P7 analog mit dvleAmountLCY. Im Bericht positiv.
P8 Summe costAmountActual der Artikelwertposten mit Buchungsdatum bis zum Stichtag gegen den Saldo der Lagerkonten. Eine bekannte Differenz bleibt stehen. Stimmt sie exakt mit einem Eintrag in bekannte_differenzen, ist der Status erklärt. Weicht sie ab, ist der Status Differenz. Die Toleranz bleibt 0,00, der Betrag wird nicht verrechnet.
P9 Zeilen im Snapshot minus Zeilen in manifest.json. Summe der absoluten Abweichungen 0. Die Spalte Modell ist leer und kommt mit AP-04.

| Entität | Route | Snapshot | manifest | Modell | Differenz |
| --- | --- | --- | --- | --- | --- |
| generalLedgerEntries | v2.0 | 4384 | 4384 |  | 0 |
| accounts | v2.0 | 221 | 221 |  | 0 |
| dimensions | v2.0 | 7 | 7 |  | 0 |
| dimensionValues | v2.0 | 29 | 29 |  | 0 |
| customers | v2.0 | 5 | 5 |  | 0 |
| vendors | v2.0 | 8 | 8 |  | 0 |
| items | v2.0 | 80 | 80 |  | 0 |
| itemCategories | v2.0 | 16 | 16 |  | 0 |
| incomeStatementGeneralLedgerEntries | microsoft/analytics/v1.0 | 1022 | 1022 |  | 0 |
| balanceSheetGeneralLedgerEntries | microsoft/analytics/v1.0 | 3362 | 3362 |  | 0 |
| closingGeneralLedgerEntries | microsoft/analytics/v1.0 | 0 | 0 |  | 0 |
| customerLedgerEntries | microsoft/analytics/v1.0 | 1145 | 1145 |  | 0 |
| vendorLedgerEntries | microsoft/analytics/v1.0 | 869 | 869 |  | 0 |
| salesValueEntries | microsoft/analytics/v1.0 | 532 | 532 |  | 0 |
| purchaseValueEntries | microsoft/analytics/v1.0 | 285 | 285 |  | 0 |
| itemValueEntries | microsoft/analytics/v1.0 | 878 | 878 |  | 0 |
| itemLedgerEntries | microsoft/analytics/v1.0 | 826 | 826 |  | 0 |
| generalLedgerAccounts | microsoft/analytics/v1.0 | 221 | 221 |  | 0 |
| generalLedgerAccountCategories | microsoft/analytics/v1.0 | 46 | 46 |  | 0 |
| accountCategories | microsoft/analytics/v1.0 | 26 | 26 |  | 0 |
| dimensions | microsoft/analytics/v1.0 | 1 | 1 |  | 0 |
| generalLedgerBudgets | microsoft/analytics/v1.0 | 0 | 0 |  | 0 |
| generalLedgerBudgetEntries | microsoft/analytics/v1.0 | 0 | 0 |  | 0 |
| customers | microsoft/analytics/v1.0 | 5 | 5 |  | 0 |
| vendors | microsoft/analytics/v1.0 | 8 | 8 |  | 0 |
| items | microsoft/analytics/v1.0 | 80 | 80 |  | 0 |
| itemCategories | microsoft/analytics/v1.0 | 16 | 16 |  | 0 |
| salespersonPurchasers | microsoft/analytics/v1.0 | 7 | 7 |  | 0 |
| locations | microsoft/analytics/v1.0 | 10 | 10 |  | 0 |
| dynamicDimensions | microsoft/analytics/v1.0 | 103 | 103 |  | 0 |
| trialBalances | v2.0 | 3315 | 3315 |  | 0 |

Quellen: v2.0 generalLedgerEntries, accounts, trialBalances. Analytics incomeStatementGeneralLedgerEntries, balanceSheetGeneralLedgerEntries, customerLedgerEntries, vendorLedgerEntries, salesValueEntries, itemValueEntries, itemLedgerEntries, purchaseValueEntries, generalLedgerAccounts, generalLedgerAccountCategories, dynamicDimensions. Kein Aufruf während dieses Laufs.
Abschlussbuchungen: closingGeneralLedgerEntries hat 0 Zeilen. GuV-Salden werden nicht als Periodenwert gelesen, weil keine Abschlussbuchungen die Salden auf null setzen.
