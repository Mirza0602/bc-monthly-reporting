// Quelle: keine. Lokale Funktion für Saldenlisten-Texte.
// Filter: keiner.
// Schlüssel: keiner. Das ist eine Funktion und wird nicht geladen.
// Erwartete Zeilenzahl: keine.
// Abweichung von B2: keine. Dieselben Regeln wie parse_amount in src\datenbestand.py.
// Dieselben Fälle wie tests\test_parser.py:
// "72,893.84" wird 72893.84
// "72.893,84" wird 72893.84
// "(1.234,56)" wird -1234.56
// "" wird 0
// null wird 0
// "  " wird 0
// Steht Komma und Punkt im Text, ist das weiter rechts stehende Zeichen das Dezimaltrennzeichen.
// Nur ein Komma: drei Ziffern dahinter und Ziffern davor bedeuten einen Tausenderpunkt, sonst Dezimaltrennzeichen.
// Klammern, führendes Minus und nachgestelltes Minus machen den Betrag negativ. Leerer Text wird 0.
(wert as any) as number =>
let
    Zeichen = (text as text) as number =>
        let
            Klammer = Text.StartsWith(text, "(") and Text.EndsWith(text, ")"),
            OhneKlammer =
                if Klammer then Text.Middle(text, 1, Text.Length(text) - 2) else text,
            EndeMinus = Text.EndsWith(OhneKlammer, "-"),
            OhneEnde =
                if EndeMinus
                then Text.Start(OhneKlammer, Text.Length(OhneKlammer) - 1)
                else OhneKlammer,
            Plus = Text.StartsWith(OhneEnde, "+"),
            OhnePlus = if Plus then Text.Middle(OhneEnde, 1) else OhneEnde,
            AnfangMinus = Text.StartsWith(OhnePlus, "-"),
            Kern = if AnfangMinus then Text.Middle(OhnePlus, 1) else OhnePlus,
            OhneWaehrung = Text.Replace(Text.Replace(Kern, "EUR", ""), "€", ""),
            Negativ = Klammer or EndeMinus or AnfangMinus,
            Normal = Normalisiere(OhneWaehrung),
            Zahl = if Normal = "" then 0 else Number.FromText(Normal, "en-US")
        in
            if Normal = "" then 0 else if Negativ then -Zahl else Zahl,
    Normalisiere = (text as text) as text =>
        let
            HatKomma = Text.Contains(text, ","),
            HatPunkt = Text.Contains(text, "."),
            LetztesKomma = Text.PositionOf(text, ",", Occurrence.Last),
            LetzterPunkt = Text.PositionOf(text, ".", Occurrence.Last),
            NurKomma =
                let
                    Pos = Text.PositionOf(text, ","),
                    Links = Text.Start(text, Pos),
                    Rechts = Text.Middle(text, Pos + 1),
                    LinksOhnePunkt = Text.Replace(Links, ".", ""),
                    LinksOk =
                        LinksOhnePunkt <> ""
                        and Text.Select(LinksOhnePunkt, {"0".."9"}) = LinksOhnePunkt,
                    RechtsOk =
                        Text.Length(Rechts) = 3
                        and Text.Select(Rechts, {"0".."9"}) = Rechts
                in
                    if LinksOk and RechtsOk then
                        LinksOhnePunkt & Rechts
                    else
                        LinksOhnePunkt & "." & Rechts
        in
            if text = "" then
                ""
            else if HatKomma and HatPunkt then
                if LetztesKomma > LetzterPunkt then
                    Text.Replace(Text.Replace(text, ".", ""), ",", ".")
                else
                    Text.Replace(text, ",", "")
            else if HatKomma then
                NurKomma
            else if Text.Length(Text.Select(text, {"."})) > 1 then
                Text.Replace(text, ".", "")
            else
                text,
    Roh =
        if wert = null then
            ""
        else if Value.Is(wert, type number) or Value.Is(wert, type logical) then
            ""
        else
            Text.Trim(
                Text.Replace(
                    Text.Replace(Text.From(wert), Character.FromNumber(160), ""),
                    " ",
                    ""
                )
            ),
    Ergebnis =
        if wert = null then
            0
        else if Value.Is(wert, type number) then
            wert
        else if Value.Is(wert, type logical) then
            error "Betrag ist ein Wahrheitswert."
        else if Roh = "" then
            0
        else
            Zeichen(Roh)
in
    Ergebnis
