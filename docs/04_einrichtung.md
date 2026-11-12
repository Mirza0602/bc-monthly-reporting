# Einrichtung

Stand 12.11.2026

Die Befehle sind dieselben wie in der [README](../README.md). Quelle für die App-Registrierung und die Freigabe in Business Central: [Service-to-Service-Authentifizierung](https://learn.microsoft.com/dynamics365/business-central/dev-itpro/administration/automation-apis-using-s2s-authentication).

## 1. Business Central Trial

Business Central Trial starten, Land Deutschland. Die Demofirma ist CRONUS DE.

## 2. Entra-App

Eine App-Registrierung anlegen. Ein Client Secret erzeugen und sofort kopieren.

API-Berechtigung Dynamics 365 Business Central, Application permissions, API.ReadWrite.All. Admin-Zustimmung erteilen. Diese Berechtigung öffnet nur die Tür zur API. Was die Anwendung lesen darf, entscheidet der Berechtigungssatz in Business Central. Microsoft empfiehlt für den Produktivbetrieb keine Anmeldung per Client Secret. Für diese Demo reicht es.

## 3. Anwendung in Business Central

Die Seite "Microsoft Entra applications" öffnen. Im deutschen Client heißt sie "Microsoft Entra-Anwendungen". New, die Client ID eintragen, State auf Enabled, Berechtigungssatz D365 READ zuweisen.

SUPER kann einer Anwendung nicht zugewiesen werden. Nur die nötigen Rechte vergeben. D365 READ erlaubt das Lesen.

## 4. Python

Die virtuelle Umgebung anlegen und die Pakete installieren:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e .
```

`.env.example` nach `.env` kopieren und ausfüllen: `BC_TENANT_ID`, `BC_CLIENT_ID`, `BC_CLIENT_SECRET`, `BC_ENVIRONMENT` (Production). Die Datei nicht einchecken.

Die Firmen-ID schreibt der Probe nach `.env.local`. Der Extrakt liest sie von dort. Der Probe wählt die Firma, deren Name CRONUS DE enthält.

```powershell
.\.venv\Scripts\python -m src.inventory --probe
```

## 5. Extrakt und Abstimmung

Der Stichtag muss gesetzt sein. Ohne `--stichtag` nimmt der Extrakt das Ende des Vormonats. Die Saldenliste kommt mit dem Extrakt, inklusive Jahresanker 01.01.2024 bis 31.12.2024. Fehlt der Anker in einem vorhandenen Snapshot, ist der Sonderfall `.\.venv\Scripts\python -m src.trial_balance --fetch-anchor`. Der Aufruf braucht den Zugang zu Business Central. `--month 2026-09` schreibt das Protokoll für September nach `docs/abstimmung`. Ohne `--month` schreibt das Programm zusätzlich den Vormonat.

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m src.extract --stichtag 2026-09-30
.\.venv\Scripts\python -m src.reconcile --month 2026-09
```

Der Snapshot liegt im Repo unter `data/snapshots/2026-10-24`. Die Abstimmung darauf läuft ohne Zugang zu Business Central:

```powershell
.\.venv\Scripts\python -m src.reconcile --snapshot data/snapshots/2026-10-24 --month 2026-09
```

Ein neuer Extrakt legt einen eigenen Ordner zum Lauftag an und ändert diesen Snapshot nicht.

## 6. Power BI Desktop

Wer powerbi/bc-monthly-reporting.pbip öffnet, hat alle Abfragen schon im Modell und setzt nur die Parameter. Die folgende Reihenfolge gilt für den Neuaufbau aus den Vorlagen.

Die Vorlagen stehen in [Power-Query-Vorlagen](../powerbi/queries/README.md). Abfragename gleich Dateiname.

Reihenfolge:

1. Parameter: `pUmgebung`, `pMandant`, `pStichtag`, `pRepoPfad`.
2. Hilfsabfragen: `fnQuelle`, `fnBetrag`.
3. Dimensionen: `DimDatum`, `DimKonto`, `DimDimensionsSet`, `DimKunde`, `DimLieferant`, `DimArtikel`.
4. Fakten: `FactSachposten`, `FactDebitorenposten`, `FactKreditorenposten`, `FactWertposten`, `FactSaldenliste`.

Einfügen als leere Abfrage. Wird ein Parameter nicht als Parameter erkannt: Rechtsklick, in Parameter konvertieren. Standardwerte: `pUmgebung` Production, `pMandant` CRONUS DE, `pStichtag` 30.09.2026, `pRepoPfad` der Ordner des Repos. Die Vorlage enthält `C:\git\bc-monthly-reporting`.

Optionen, CURRENT FILE, Data Load:

- Background Data aus.
- Parallel loading auf One.
- Auto date/time aus.
- Autodetect relationships aus.

Enable load aus für `pUmgebung`, `pMandant`, `pRepoPfad`, `fnQuelle` und `fnBetrag`. `pStichtag` bleibt geladen.

Datenschutzebenen für Business Central und den Repo-Ordner auf Organizational setzen. Sonst blockiert Power BI die Kombination aus Konten und `config/kpi_mapping.csv` in DimKonto.

Anmeldung am Connector mit dem Organisationskonto, derselbe Benutzer wie in Business Central.

Das Gateway für die Cloudquelle und die lokale Zuordnungsdatei steht in der [Architektur](00_architektur.md).

## 7. Häufige Fehler

Antwortet die Analytics-Route beim Probe nicht, bricht das Programm mit einer Fehlermeldung ab. Beide Routen müssen eine Firmenliste liefern, bevor der Extrakt läuft.

`python -m src.reconcile --month 2025-09` endet mit einem Fehler. Die Saldenliste hat keinen Kalendermonat 2025-01-31. Vorhanden sind der 31.12.2024, der 31.08.2025 und der 30.09.2025. Es entsteht keine Protokolldatei. Das Vorjahr im Bericht kommt aus den Sachposten.

Zwei Fehler aus dem Laden der Vorlagen. Die direkte Parameterübergabe an ApiContentsWithOptions hat am 25.10.2026 die Meldung "Verbindung vom Remotehost geschlossen" erzeugt. fnQuelle ruft den Connector deshalb ohne Parameter auf und wählt die Umgebung mit Text.Upper. Ein Join gegen die OData-Quelle wurde am 26.10.2026 nicht an Business Central weitergegeben und hat die Verbindung geschlossen. FactSachposten puffert die Listen und prüft sie lokal.
