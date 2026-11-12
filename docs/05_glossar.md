# Glossar Monatsreporting Business Central

Stand: 25.10.2026 (Thema 1 und 2)

Zweck: Jeder Begriff mit Alltagsbild, technischer Erklärung und einem Satz, wie man ihn dem Kunden sagt.

Leitbild: Business Central ist ein Lager. Bei BC online steht das Lager bei Microsoft, niemand von außen darf hinein. Es gibt eine Warenausgabe mit festem Katalog (die API). Wer abholen will, braucht einen Ausweis, und auf dem Ausweis steht, welche Regale er sehen darf.

## Thema 1: Anbindung und Zugriff

| Begriff | Alltagsbild | Technisch | Kundensatz |
| --- | --- | --- | --- |
| API | Warenausgabe mit festem Katalog | Schnittstelle, über die Business Central Daten nach festen Regeln herausgibt (REST, OData v4) | "Business Central hat eine offizielle Ausgabe für Daten. Dort bestelle ich, statt selbst in der Datenbank zu suchen." |
| Entität | ein Artikel im Katalog der Warenausgabe | einzelner Endpunkt der API, z. B. Sachposten, Debitorenposten, Konten | "Ich hole gezielt die Tabellen, die das Reporting braucht, zum Beispiel Sachposten und offene Posten." |
| API v2.0 | der Standardkatalog | Microsofts Standard-API, hier für Konten, Stammdaten und die Saldenliste (trialBalances) | "Das ist Microsofts Standardschnittstelle für Konten, Stammdaten und die Saldenliste." |
| Analytics API | ein Spezialkatalog für Auswertungen | Microsoft-API unter api/microsoft/analytics/v1.0, liefert z. B. GuV- und Bilanzsachposten, offene Posten, Wertposten | "Für Auswertungen gibt es eine eigene Microsoft-Schnittstelle, auf der auch Microsofts Power-BI-Apps für Business Central aufbauen." |
| Power-BI-Connector | Power BI hat das Bestellformular schon eingebaut | eingebauter Connector "Dynamics 365 Business Central" in Power BI Desktop und im Service | "Power BI hat den Anschluss an Business Central schon eingebaut, ohne Zusatzsoftware." |
| Schreibgeschützte Replik | die Ausgabe holt aus einem Zweitlager, damit das Hauptlager nicht gestört wird | Power BI liest bei BC online seit Februar 2022 aus einer schreibgeschützten Kopie der Datenbank | "Das Reporting liest aus einer Kopie, Ihre Buchhaltung wird dadurch nicht langsamer." |
| Gateway | ein Bote, der nur nötig ist, wenn die Ware im eigenen Keller des Kunden liegt | Software beim Kunden, die Power BI mit Datenquellen verbindet, die nicht direkt über das Internet erreichbar sind, auch auf VMs | "Bei BC online brauchen Sie kein Gateway, weil beides in der Microsoft-Cloud liegt." |
| BC online | das Lager steht bei Microsoft | Business Central als Cloud-Dienst, von Microsoft betrieben, Daten nur über APIs lesbar | "Microsoft betreibt das System. Deshalb gibt es keinen direkten Datenbankzugriff mehr, nur die offizielle Schnittstelle." |
| BC on-premises | das eigene Lager, auch in einer gemieteten Halle | Business Central auf eigenen Servern oder einer selbst betriebenen VM, mit eigener SQL-Datenbank | "Wenn Sie Business Central selbst betreiben, auch auf einer Azure-VM, ist direkter Datenbankzugriff möglich, und Power BI braucht ein Gateway." |
| App-Registrierung (Microsoft Entra) | der Ausweis, den der Kunde selbst ausstellt | Anwendung im Entra des Kunden, meldet sich ohne Benutzer an (Client Credentials) | "Den Zugang stellen Sie selbst aus, in Ihrem eigenen Microsoft Entra." |
| Client-ID und Client Secret | Ausweisnummer und Geheimzahl | Kennung und Geheimnis der App-Registrierung, kein Benutzerkonto, keine BC-Lizenz | "Ich bekomme eine Kennung und ein Geheimnis, kein Benutzerkonto." |
| Seite "Microsoft Entra-Anwendungen" | der Schalter, an dem der Ausweis freigeschaltet oder gesperrt wird | Seite in Business Central, auf der die App mit Status Aktiviert oder Deaktiviert und mit Berechtigungssätzen eingetragen wird | "Mit einem Klick auf Deaktiviert ist der Zugang sofort gesperrt." |
| Berechtigungssatz D365 READ | auf dem Ausweis steht: nur abholen, nichts zurückstellen | Berechtigungssatz in Business Central mit Leserechten | "In Business Central legen Sie fest, dass der Zugang nur lesen darf." |
| API.ReadWrite.All | die Eingangstür zur Warenausgabe | Berechtigung in Entra, öffnet nur den Zugang zur API; was erlaubt ist, entscheidet der Berechtigungssatz in BC | "Entra öffnet nur die Tür. Was erlaubt ist, entscheidet der Berechtigungssatz in Business Central, und der erlaubt nur Lesen." |
| Least Privilege | nur die Regale freigeben, die gebraucht werden | Prinzip minimaler Rechte; Apps dürfen in BC kein SUPER erhalten | "Der Zugang bekommt nur die Rechte, die das Reporting braucht." |
| OData-Web-Service | ein Nebeneingang, der sich bei Umbauten verschiebt | ältere Veröffentlichungsform von BC-Seiten; Microsoft empfiehlt API-Seiten, weil UI-Seiten sich bei Updates ändern können | "Ich nutze die API-Seiten, weil sie bei Updates stabil bleiben." |
| Custom API | ein Sonderkatalog, den man selbst druckt | eigene API-Seite als BC-Erweiterung, nur nötig, wenn die Standard-APIs ein Feld nicht liefern | "Eine eigene Schnittstelle baue ich nur, wenn Microsofts Standard ein benötigtes Feld nicht liefert." |
| Data Lake | ein großes Außenlager, in das man Kisten unsortiert stellt | großer Dateispeicher in der Cloud, z. B. Azure Data Lake Storage (ADLS) oder OneLake | "Ein Data Lake lohnt sich, wenn viele Quellen zusammenkommen. Für ein Monatsreporting aus einem System ist er nicht nötig." |
| bc2adls | ein selbstgebautes Förderband ins Außenlager | Erweiterung, die BC-Tabellen nach ADLS oder Fabric kopiert; von Microsoft als Code-Beispiel bereitgestellt, nicht unterstützt | "bc2adls ist ein Code-Beispiel, das Microsoft selbst nicht unterstützt. Darauf baue ich kein Kundenreporting." |
| Spiegelung nach Fabric | das offizielle Förderband von Microsoft | Data Mirroring: BC online kopiert ausgewählte Tabellen zuerst vollständig, danach nur Änderungen, nach OneLake; laut Doku Preview ab Oktober 2026 geplant | "Wenn Sie später Fabric einführen, gibt es dafür einen offiziellen Weg von Microsoft. Ihre Kennzahlenlogik nehmen Sie mit." |
| Fabric-Kapazität | Miete für eine Halle, die man laufend bezahlt | F-SKU in Azure, sekundengenau abgerechnet, pausierbar; Lakehouses und Warehouses brauchen sie | "Fabric kostet laufend Rechenleistung. Für ein Monatsreporting aus Business Central brauchen Sie das nicht." |
| Gold-Schicht | die fertig gepackte Lieferung, die nur noch ausgegeben wird | letzte Datenschicht mit fertiger Berechnungslogik, auf die der Bericht direkt zugreift | "Die Berechnungslogik liegt in den Daten statt im Bericht. Dadurch ist sie prüfbar und unabhängig vom Berichtswerkzeug." |

### Quellen Thema 1 (Microsoft Learn, geprüft am 25.10.2026)

- [Extract data from Business Central (APIs einzige unterstützte Leseoption bei BC online, bc2adls unsupported)](https://learn.microsoft.com/dynamics365/business-central/dev-itpro/developer/devenv-extract-data)
- [Enabling Power BI integration with Business Central (Standard-APIs ohne Einrichtung, Read-only-Replik, API-Seiten vs. OData)](https://learn.microsoft.com/dynamics365/business-central/admin-powerbi-setup)
- [Using service-to-service (S2S) authentication (Seite Microsoft Entra-Anwendungen, Status, Berechtigungssätze, kein SUPER)](https://learn.microsoft.com/dynamics365/business-central/dev-itpro/administration/automation-apis-using-s2s-authentication)
- [On-premises data gateways in Power BI](https://learn.microsoft.com/power-bi/connect-data/service-gateway-onprem)
- [Connect to Power BI from Business Central on-premises](https://learn.microsoft.com/dynamics365/business-central/across-working-with-business-central-in-powerbi)
- [Data mirroring to Microsoft Fabric from Business Central (Vorabdoku)](https://learn.microsoft.com/dynamics365/business-central/admin-fabric)
- [Understand Microsoft Fabric licenses and capacity](https://learn.microsoft.com/fabric/enterprise/licenses)

## Thema 2: Datenbestand und Stichtag

| Begriff | Alltagsbild | Technisch | Kundensatz |
| --- | --- | --- | --- |
| Berichtsmonat | der Monat auf dem Kontoauszug | Zeitraum, dessen Bewegungen gezeigt werden (Umsatz, Kosten), z. B. 01.09.2026 bis 30.09.2026 | "Der Bericht zeigt alle Bewegungen vom 01.09. bis 30.09.2026." |
| Stichtag | der Kontostand an einem bestimmten Tag | Datum, bis zu dem Salden gerechnet werden (offene Forderungen, Bestand); ein Parameter, identisch in Extraktor, Modell und Abstimmung | "Alle Salden gelten zum 30.09.2026, und dieser Stichtag ist überall derselbe." |
| Datenstand | wann der Kontoauszug gedruckt wurde | Zeitpunkt des Abrufs aus Business Central; Nachbuchungen danach erscheinen erst beim nächsten Abruf | "Im Bericht steht, wann die Daten abgeholt wurden. Spätere Nachbuchungen sind beim nächsten Abruf drin." |
| Buchungsdatum | das Datum auf jeder Zeile des Kontoauszugs | Datum je Sachposten, entscheidet, in welche Periode eine Buchung fällt | "Maßgeblich ist das Buchungsdatum, nicht der Tag, an dem gebucht wurde." |
| Zukunftsbuchung | ein Dauerauftrag, der schon mit späterem Datum eingetragen ist | Sachposten mit Buchungsdatum nach dem Stichtag, z. B. aus Abgrenzungen oder wiederkehrenden Buchungen; in CRONUS bis 01.09.2027 | "Zukunftsbuchungen sind normal. Sie tragen ein späteres Datum und fallen durch den Stichtag heraus." |
| Abgrenzung | eine Jahresrechnung, die auf zwölf Monate verteilt wird | Abgrenzungsvorlage in Business Central verteilt Erlöse oder Kosten automatisch auf spätere Buchungsperioden | "Abgrenzungen sorgen dafür, dass Kosten und Erlöse in dem Monat erscheinen, zu dem sie gehören." |
| Saldenliste | alle Kontostände auf einen Blick | Bericht in Business Central mit Bewegung und Saldo je Sachkonto für einen Datumsfilter | "Ihre Buchhalterin ruft die Saldenliste zum selben Stichtag auf und kann den Bericht selbst prüfen." |
| Nettoveränderung | was sich im Monat auf einem Konto bewegt hat | Soll minus Haben eines Kontos im gewählten Zeitraum | "Ich vergleiche je Konto die Bewegung im Monat mit der Saldenliste." |
| Sachkontenbudget | die Planliste neben dem Kontoauszug | Budget je Sachkonto und Periode in Business Central; Export und Import mit Excel, kopierbar | "Ihr Controller plant weiter in Excel und importiert das Ergebnis in Business Central." |
| Demo-Plan | ein Beispielplan, deutlich als Beispiel markiert | in CRONUS aus dem Vorjahr mal Faktor abgeleitet, offen im README und im Berichtsfuß ausgewiesen | "Im Demoprojekt ist der Plan abgeleitet und als Demo gekennzeichnet. Beim Kunden kommt der Plan immer vom Kunden." |
| Saldenübernahme | ein Umzug nur mit dem Kontostand, ohne die alten Kontoauszüge | Migration nur mit Eröffnungssalden und offenen Posten; historische Buchungen fehlen in Business Central | "Wenn nur Salden übernommen wurden, gibt es in Business Central kein Vorjahr. Ich mache die Lücke sichtbar, statt sie zu füllen." |
| Historientabelle | die alten Kontoauszüge als Kopie im Ordner | einmaliger Export je Konto und Monat aus dem Altsystem, fest in Power BI geladen, einmal gegen die alte Saldenliste abgestimmt; kein Drillthrough bis zum Beleg | "Ich lade Ihre Vorjahreszahlen einmalig aus dem Altsystem und stimme sie gegen die alte Saldenliste ab." |

### Quellen Thema 2 (Microsoft Learn, geprüft am 25.10.2026)

- [Defer revenues and expenses](https://learn.microsoft.com/dynamics365/business-central/finance-how-defer-revenue-expenses)
- [Create G/L budgets (Export und Import mit Excel, Budget kopieren)](https://learn.microsoft.com/dynamics365/business-central/finance-how-create-budgets)

Saldenübernahme und Historientabelle sind Fachlogik ohne eigene Microsoft-Vorgabe.

## Thema 3: Abstimmung gegen die FiBu

Folgt nach dem Kundentraining zu Thema 3.

## Pflegeregel

Neue Begriffe kommen nur mit geprüfter Quelle hinzu, Inhalte liefert Claude, Cursor formatiert.
