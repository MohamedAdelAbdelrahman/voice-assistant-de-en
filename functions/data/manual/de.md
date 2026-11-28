# Wartungshandbuch (DE)

Fiktives Handbuch für das Demo-Werk (Linien 1–5, Maschinen 1–12). Ein Abschnitt pro
Alarmcode oder Vorgehen. `en.md` hat dieselben Abschnitte mit denselben IDs.
Die Zeilen "Stichwörter" dienen nur der Suche und werden nicht vorgelesen.

## [E-204] Spindeltemperatur zu hoch
Bedeutung: Die Spindel einer CNC-Fräse (Maschine 3 und 4) ist über 70 °C. Die Maschine stoppt die Spindel selbst.
Vorgehen: Die Spindel mindestens 15 Minuten abkühlen lassen. Kühlmittelstand und Kühlmittelfilter prüfen. Prüfen, ob der Späneförderer blockiert ist. Kommt der Alarm innerhalb einer Stunde wieder, ist eventuell das Spindellager verschlissen: Ticket mit Priorität hoch anlegen.
Sicherheit: Spindel und Werkzeug nicht anfassen, solange sie heiß sind. Die Maschine erst nach dem Absperren öffnen (siehe LOTO).
Stichwörter: Spindel, Temperatur, Überhitzung, überhitzt, heiß, Kühlmittel, Kühlung, Lager, CNC, Fräse

## [W-118] Werkzeugverschleiß über 80 %
Bedeutung: Das Werkzeug hat 80 % seiner geplanten Standzeit erreicht. Die Maschine läuft weiter, aber die Oberflächenqualität sinkt.
Vorgehen: Den Werkzeugwechsel beim nächsten Teilewechsel oder am Ende des Auftrags einplanen. Nach dem Ablauf Werkzeugwechsel vorgehen (siehe TOOL-CHANGE). Nach dem Wechsel den Standzeitzähler am Bedienfeld zurücksetzen.
Stichwörter: Werkzeug, Verschleiß, verschlissen, abgenutzt, Fräser, Wechsel, Standzeit, Zähler

## [E-512] Schutzgas-Druck zu niedrig
Bedeutung: Der Schweißroboter bekommt weniger als 1,5 bar Schutzgas. Die Nähte würden porös, deshalb ist das Schweißen gesperrt.
Vorgehen: Prüfen, ob das Flaschenventil offen und die Gasflasche nicht leer ist (unter 10 bar gilt als leer). Flasche bei Bedarf wechseln. Den Gasschlauch auf Knicke und Undichtigkeiten prüfen. Danach den Alarm am Roboter-Bedienfeld quittieren.
Sicherheit: Gasflaschen mit der Kette sichern. Flaschen nur mit geschlossenem Ventil wechseln.
Stichwörter: Schweißen, Schweißroboter, Gas, Schutzgas, Argon, Druck, Flasche, Gasflasche, undicht, Leck, Roboter

## [E-513] Not-Aus ausgelöst
Bedeutung: Ein Not-Aus-Taster oder ein Schutztürschalter wurde ausgelöst. Alle Bewegungen in der Zelle sind gestoppt.
Vorgehen: Klären, warum der Not-Aus gedrückt wurde, und sicherstellen, dass niemand im Gefahrenbereich ist. Zuerst die Ursache beseitigen. Dann den Not-Aus-Taster ziehen oder drehen, alle Schutztüren schließen und am Bedienfeld Reset drücken. Die Maschine zuerst im Handbetrieb wieder anfahren.
Sicherheit: Einen Schutztürschalter nie überbrücken. Wenn jemand verletzt wurde, vor dem Wiederanlauf Ersthelfer und Schichtleitung rufen.
Stichwörter: Not-Aus, Notaus, Nothalt, Not-Halt, Taster, Schutztür, Reset, zurücksetzen, Wiederanlauf, Neustart

## [W-301] Wartezeit auf Material
Bedeutung: Die Maschine ist bereit, hat aber keine Teile im Zulauf. Das ist kein Fehler der Maschine.
Vorgehen: Den Puffer vor der Maschine und die vorgelagerte Station prüfen. Logistik anrufen, wenn die Materialversorgung leer ist. Steht die vorgelagerte Maschine, zuerst deren Alarm lösen.
Stichwörter: Material, warten, Wartezeit, Teile, Versorgung, Zulauf, Logistik, Puffer, Nachschub

## [I-020] Filterwechsel fällig
Bedeutung: Der Luftfilter des Trockenofens erreicht bald sein Wechselintervall. Der Ofen arbeitet weiter.
Vorgehen: Den Filterwechsel im nächsten geplanten Stopp einplanen. Filtertyp F7, zwei Stück. Den Ofen unter 40 °C abkühlen lassen, dann öffnen, und danach den Filterzähler zurücksetzen.
Stichwörter: Filter, Luftfilter, Filterwechsel, Ofen, Trockenofen, Trockner, Wechsel, Intervall, fällig

## [W-150] Hydrauliköl-Temperatur erhöht
Bedeutung: Das Hydrauliköl einer Presse ist über 55 °C. Über 65 °C stoppt die Presse.
Vorgehen: Den Lüfter des Ölkühlers prüfen und die Kühlerlamellen reinigen. Den Ölstand im Schauglas prüfen. Die Hubzahl reduzieren, bis die Temperatur sinkt. Ist das Öl dunkel oder riecht verbrannt, ein Ticket für einen Ölwechsel anlegen.
Sicherheit: Hydraulikleitungen können auch bei stehender Presse unter hohem Druck stehen. Vor dem Öffnen einer Leitung den Druck ablassen.
Stichwörter: Hydraulik, Hydrauliköl, Öl, Temperatur, Presse, Kühler, Ölkühler, heiß, Druck

## [I-001] Geplante Wartung läuft
Bedeutung: Die Instandhaltung hat die Maschine in geplanter Wartung. Die Produktion darf sie nicht starten.
Vorgehen: Die Instandhaltung nach dem geplanten Ende fragen. Nur die Instandhaltung entfernt die Absperrung und gibt die Maschine frei.
Stichwörter: Wartung, geplant, Instandhaltung, Service, Freigabe, freigeben, gesperrt

## [LOTO] Absperren vor dem Öffnen einer Maschine
Bevor du eine Maschine öffnest, hineingreifst oder an ihr arbeitest, muss sie abgesperrt sein (Lockout/Tagout).
Vorgehen: Erstens, die Maschine normal stoppen. Zweitens, den Hauptschalter ausschalten. Drittens, dein persönliches Schloss an den Hauptschalter hängen und dein Schild anbringen. Viertens, gespeicherte Energie abbauen: Druck, Federn, heiße Teile. Fünftens, mit dem Start-Taster prüfen, dass die Maschine nicht anläuft. Erst dann die Schutzabdeckungen öffnen. Jede Person, die an der Maschine arbeitet, benutzt ihr eigenes Schloss.
Stichwörter: Absperren, absperren, sperren, Lockout, Tagout, LOTO, Schloss, Vorhängeschloss, öffnen, Schutzabdeckung, Tür, Sicherheit, sicher, Hauptschalter, Energie, an der Maschine arbeiten

## [PPE] Persönliche Schutzausrüstung
In der ganzen Halle: Sicherheitsschuhe und Schutzbrille. Gehörschutz an den Pressen auf Linie 1. An den Schweißrobotern: Schweißvorhang geschlossen, nie ohne Schweißschild in den Lichtbogen sehen. Bei Kühlmittel und Öl: Schutzhandschuhe.
Stichwörter: Schutzausrüstung, PSA, Schuhe, Sicherheitsschuhe, Brille, Schutzbrille, Gehörschutz, Handschuhe, Schweißschild, Sicherheit

## [TOOL-CHANGE] Werkzeugwechsel an einer CNC-Fräse
Vorgehen: Das Programm am Ende eines Zyklus anhalten. Die Spindel in die Werkzeugwechselposition fahren. Vor dem Hineingreifen in den Arbeitsraum die Maschine absperren (siehe LOTO). Schnittschutzhandschuhe tragen. Den Werkzeughalter lösen, das neue Werkzeug einsetzen und die Werkzeugnummer prüfen. Die Werkzeuglänge in der Steuerung eintragen, dann das erste Teil im Einzelsatz fahren und seine Maße prüfen.
Stichwörter: Werkzeugwechsel, Werkzeug wechseln, Fräser, einsetzen, CNC, Fräse, Werkzeughalter, Korrektur, Länge

## [ESCALATION] Wen anrufen
Maschinenstörung, die du nicht innerhalb von 15 Minuten lösen kannst: Instandhaltungs-Hotline, Durchwahl 2400. Sicherheitsproblem oder Verletzung: Schichtleitung und Ersthelfer, Durchwahl 112 am Werkstelefon. Qualitätsproblem: Qualitätsprüfer der Linie. Für jede Störung, die einen Techniker braucht, ein Ticket anlegen.
Stichwörter: anrufen, Kontakt, Telefon, Hotline, Hilfe, Schichtleitung, Schichtleiter, Ersthelfer, Verletzung, verletzt, Unfall, Instandhaltung, eskalieren, wen, wer
