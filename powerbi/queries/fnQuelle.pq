// Quelle: Dynamics365BusinessCentral.ApiContentsWithOptions ohne Parameter, danach Umgebung, Firma und Route.
// Filter: keiner. Die aufrufende Abfrage filtert, diese Funktion nicht.
// Schlüssel: keiner. Das ist eine Funktion und wird nicht geladen.
// Erwartete Zeilenzahl: keine. Zweiter Schritt in der Abfrage: {[Name="Entität"]}[Data].
// Abweichung von B2: Connector ohne Parameter wie der Navigator. Umgebung über Text.Upper(pUmgebung), der Navigator zeigt PRODUCTION. v2.0 liegt direkt unter der Firma, die Analytics API unter "Advanced". Route je Abfrage "microsoft/analytics/v1.0" oder "v2.0".
// Die direkte Parameterübergabe an ApiContentsWithOptions hat beim Laden zu "Verbindung vom Remotehost geschlossen" geführt (getestet 25.10.2026).
(apiRoute as text) as table =>
let
    Quelle   = Dynamics365BusinessCentral.ApiContentsWithOptions(null, null, null, null),
    Umgebung = Quelle{[Name = Text.Upper(pUmgebung)]}[Data],
    Firma    = Umgebung{[Name = pMandant]}[Data],
    Route    =
        if apiRoute = "v2.0" then
            Firma{[Name = "v2.0"]}[Data]
        else
            Firma{[Name = "Advanced"]}[Data]{[Name = apiRoute]}[Data]
in
    Route
