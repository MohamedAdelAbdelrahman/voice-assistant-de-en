import pytest

from functions.manual import LANGS, Manual, guess_language, load_sections, normalize_codes, tokenize
from functions.tools import ShopFloor


@pytest.fixture(scope="module")
def manual():
    return Manual()


def top(manual, q, lang=None):
    r = manual.search(q, lang)
    assert r["found"], r
    return r["sections"][0]["source"].split("#")[1]


def test_both_languages_have_the_same_sections():
    sections = load_sections()
    assert len(sections) >= 10
    for s in sections:
        for lang in LANGS:
            assert s.title[lang] and len(s.text[lang]) > 40 and s.keywords[lang], (s.id, lang)
            assert "Keywords" not in s.text[lang] and "Stichwörter" not in s.text[lang]


def test_every_alarm_code_in_the_mock_data_has_a_section():
    ids = {s.id for s in load_sections()}
    codes = {a["code"] for a in ShopFloor().data["alarms"]}
    assert codes <= ids


@pytest.mark.parametrize("spoken", ["E-204", "E204", "e 204", "E-2-0-4", "e 2 0 4"])
def test_alarm_code_spellings_from_stt(spoken):
    assert normalize_codes(f"Was bedeutet {spoken}?") == "Was bedeutet E-204?"


@pytest.mark.parametrize("question,expected", [
    ("Was bedeutet E 204?", "E-204"),
    ("what does alarm e513 mean", "E-513"),
    ("Wie sperre ich eine Maschine ab, bevor ich sie öffne?", "LOTO"),
    ("What do I have to do before I open a machine?", "LOTO"),
    ("How do I change the tool on the CNC mill?", "TOOL-CHANGE"),
    ("Die Gasflasche am Schweißroboter ist leer, was tun?", "E-512"),
    ("Spindelüberhitzung an Maschine 4", "E-204"),  # compound not in the handbook
    ("Welche Schutzausrüstung brauche ich an der Presse?", "PPE"),
    ("How do I reset the emergency stop?", "E-513"),
    ("Who do I call if someone is injured?", "ESCALATION"),
    ("Hydrauliköl zu heiß", "W-150"),
])
def test_finds_the_right_section(manual, question, expected):
    assert top(manual, question) == expected


def test_answer_comes_back_in_the_requested_language(manual):
    de = manual.search("What does E-204 mean?", "de")
    assert de["language"] == "de" and de["sections"][0]["source"] == "handbook/de.md#E-204"
    assert "Spindel" in de["sections"][0]["text"]
    en = manual.search("Was bedeutet E-204?", "en")
    assert en["sections"][0]["title"] == "Spindle temperature too high"


def test_language_guess_without_hint(manual):
    assert manual.search("Wie sperre ich die Maschine ab?")["language"] == "de"
    assert manual.search("How do I lock out the machine?")["language"] == "en"
    assert guess_language("Schutztür öffnen") == "de"


def test_no_match(manual):
    r = manual.search("What is the weather tomorrow?")
    assert r["found"] is False and "no section" in r["note"]
    r = manual.search("What does E-999 mean?")
    assert r["found"] is False and "E-999" in r["note"]


def test_bad_input(manual):
    assert "error" in manual.search("")
    assert "error" in manual.search(" ")


def test_tokenize_drops_stopwords_and_folds_endings():
    assert tokenize("Wie wechsle ich die Filter?") == tokenize("wechsle Filtern")
    assert "e-204" in tokenize("Alarm E 204")


def test_ask_manual_through_dispatch():
    shop = ShopFloor()
    r = shop.call("ask_manual", {"question": "Was bedeutet W-118?", "language": "de"})
    assert r["found"] and r["sections"][0]["source"] == "handbook/de.md#W-118"
    assert "error" in shop.call("ask_manual", {"question": "x", "language": "fr"})
    assert "error" in shop.call("ask_manual", {"question": 42})
    assert "error" in shop.call("ask_manual", {})


@pytest.mark.parametrize("text,expected", [
    ("What do I have to do before I open a machine?", True),
    ("How do I reset the emergency stop?", True),
    ("Was bedeutet der Alarm E204?", True),
    ("Wie setze ich den Not-Aus zurück?", True),
    ("Wen rufe ich bei einer Verletzung an?", True),
    ("What is the status of line 4?", False),
    ("Wie ist der Status von Linie 2?", False),
    ("Create a maintenance ticket for machine 7.", False),
    ("Welche Alarme sind gerade auf Linie 3 aktiv?", False),
])
def test_manual_intent(text, expected):
    from functions.manual import manual_intent
    assert manual_intent(text) is expected
