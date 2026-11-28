"""``ask_manual``: keyword search (BM25) over the DE/EN maintenance handbook.

The handbook lives in ``data/manual/{de,en}.md``, one ``## [ID] Title`` section per
alarm code or procedure, with the same IDs in both languages. Each section is
indexed once with its German and English text together, so a German question
finds the section even through English words and the other way round; the
answer text is returned in the requested language.

Why BM25 and not embeddings: it is free, needs no extra model in RAM/VRAM next
to Whisper and the LLM, runs in well under a millisecond, and the handbook is
small. The search handles what STT actually produces:
* alarm codes in any spelling ("E-204", "E204", "e 2 0 4") match the section ID directly;
* German compounds the handbook doesn't contain ("Spindelüberhitzung") are split
  into known words;
* a light suffix stemmer folds plural/case endings ("Filter"/"Filters", "Druck"/"Drucks").
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANUAL_DIR = Path(__file__).parent / "data" / "manual"
LANGS = ("de", "en")

STOPWORDS = set("""
a an and are as at be by can do does for from has have how i if in is it me my of on or
should so that the this to was we what when where which who why will with you your
about after before do does please tell
aber als am an auch auf aus bei bin bis da das dass dem den der des die du ein eine
einem einen einer es für hat ich ihr im in ist ja kann mich mir mit muss nach nicht noch
oder soll und uns von vor was wenn wer wie wir wo zu zum zur bitte mal sag
""".split())
# STT often writes "Maschine 4"/"Linie 2" in questions; those words match everything.
STOPWORDS |= {"machine", "maschine", "line", "linie", "alarm", "alarms", "alarme", "code", "bedeutet", "mean", "means"}

_CODE_RE = re.compile(r"\b([ewi])[\s\-]*(\d)[\s\-]*(\d)[\s\-]*(\d)\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[a-z0-9äöüß]+(?:-[a-z0-9äöüß]+)*")
_SECTION_RE = re.compile(r"^## \[([A-Z0-9\-]+)\]\s*(.+)$")
_KEYWORDS_RE = re.compile(r"^(Keywords|Stichwörter):\s*(.*)$")
_SUFFIXES = ("ungen", "ung", "ern", "en", "er", "es", "e", "s", "n")


def normalize_codes(text: str) -> str:
    """'E 204', 'e-2-0-4', 'E204' -> 'E-204'."""
    return _CODE_RE.sub(lambda m: f"{m[1].upper()}-{m[2]}{m[3]}{m[4]}", text)


def _stem(tok: str) -> str:
    if len(tok) <= 4 or any(c.isdigit() for c in tok):
        return tok
    for suf in _SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 4:
            return tok[: -len(suf)]
    return tok


def tokenize(text: str) -> list[str]:
    text = normalize_codes(text).lower().replace("ß", "ss")
    out: list[str] = []
    for tok in _TOKEN_RE.findall(text):
        parts = [tok] if re.fullmatch(r"[ewi]-\d{3}", tok) else [tok, *tok.split("-")] if "-" in tok else [tok]
        out.extend(_stem(p) for p in parts if p not in STOPWORDS and len(p) > 1)
    return out


@dataclass
class Section:
    id: str
    title: dict[str, str]
    text: dict[str, str]
    keywords: dict[str, str]


def parse_manual(path: Path) -> dict[str, tuple[str, str, str]]:
    """``{id: (title, text, keywords)}`` for one handbook file."""
    sections: dict[str, tuple[str, str, str]] = {}
    sid = title = None
    body: list[str] = []
    keywords = ""

    def flush() -> None:
        if sid:
            sections[sid] = (title, " ".join(body).strip(), keywords)

    for line in path.read_text(encoding="utf-8").splitlines():
        if m := _SECTION_RE.match(line):
            flush()
            sid, title, body, keywords = m[1], m[2].strip(), [], ""
        elif sid and (k := _KEYWORDS_RE.match(line)):
            keywords = k[2]
        elif sid and line.strip():
            body.append(line.strip())
    flush()
    return sections


def load_sections(directory: Path = MANUAL_DIR) -> list[Section]:
    per_lang = {lang: parse_manual(directory / f"{lang}.md") for lang in LANGS}
    ids = list(per_lang["en"])
    if set(ids) != set(per_lang["de"]):
        raise ValueError(f"handbook sections differ between languages: {set(ids) ^ set(per_lang['de'])}")
    return [
        Section(
            id=sid,
            title={lang: per_lang[lang][sid][0] for lang in LANGS},
            text={lang: per_lang[lang][sid][1] for lang in LANGS},
            keywords={lang: per_lang[lang][sid][2] for lang in LANGS},
        )
        for sid in ids
    ]


class Manual:
    """BM25 (Okapi, k1=1.5, b=0.75) over handbook sections."""

    def __init__(self, sections: list[Section] | None = None, k1: float = 1.5, b: float = 0.75) -> None:
        self.sections = sections if sections is not None else load_sections()
        self.k1, self.b = k1, b
        self.docs: list[Counter[str]] = []
        for s in self.sections:
            # Title and keywords count twice: they say what the section is about.
            parts = [s.id] * 2
            for lang in LANGS:
                parts += [s.title[lang]] * 2 + [s.keywords[lang]] * 2 + [s.text[lang]]
            self.docs.append(Counter(tokenize(" ".join(parts))))
        self.avgdl = sum(sum(d.values()) for d in self.docs) / max(len(self.docs), 1)
        df = Counter(tok for d in self.docs for tok in d)
        n = len(self.docs)
        self.idf = {tok: math.log(1 + (n - f + 0.5) / (f + 0.5)) for tok, f in df.items()}
        self.vocab = set(self.idf)

    def _expand(self, tokens: list[str]) -> list[str]:
        """Split unknown German compounds into two known words ("spindelueberhitzung")."""
        out: list[str] = []
        for tok in tokens:
            if tok in self.vocab or len(tok) < 8:
                out.append(tok)
                continue
            split = None
            for i in range(4, len(tok) - 3):
                head, tail = tok[:i], tok[i:]
                for h in (head, head[:-1] if head.endswith("s") else None):  # Fugen-s
                    if h and _stem(h) in self.vocab and _stem(tail) in self.vocab:
                        split = [_stem(h), _stem(tail)]
                        break
                if split:
                    break
            out.extend(split or [tok])
        return out

    def scores(self, question: str) -> list[float]:
        q = self._expand(tokenize(question))
        result = []
        for d in self.docs:
            dl = sum(d.values())
            s = 0.0
            for tok in q:
                f = d.get(tok, 0)
                if f:
                    s += self.idf[tok] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            result.append(s)
        return result

    def search(self, question: str, language: str | None = None, top_k: int = 2) -> dict[str, Any]:
        question = (question or "").strip()
        if len(question) < 2:
            return {"error": "'question' must be a short text"}
        lang = language if language in LANGS else guess_language(question)

        codes = {f"{m[1].upper()}-{m[2]}{m[3]}{m[4]}" for m in _CODE_RE.finditer(question)}
        scored = sorted(
            ((s + (100.0 if sec.id in codes else 0.0), sec) for s, sec in zip(self.scores(question), self.sections)),
            key=lambda x: x[0], reverse=True,
        )
        best = scored[0][0] if scored else 0.0
        if best <= 0:
            unknown = sorted(codes - {s.id for s in self.sections})
            return {
                "found": False,
                "note": (f"The handbook has no section for {', '.join(unknown)}." if unknown
                         else "The handbook has no section that matches this question."),
            }
        # Keep the second hit only if it is nearly as relevant: less text = faster answer.
        hits = [sec for s, sec in scored[:top_k] if s > 0 and s >= 0.6 * best]
        return {
            "found": True,
            "language": lang,
            "sections": [
                {"source": f"handbook/{lang}.md#{sec.id}", "title": sec.title[lang], "text": sec.text[lang]}
                for sec in hits
            ],
        }


_DE_HINTS = set("der die das und ist wie was ich nicht mit für bei wenn muss soll bedeutet wen".split())
_EN_HINTS = set("the and is how what i not with for at when must should does mean who".split())


def guess_language(text: str) -> str:
    words = re.findall(r"[a-zäöüß]+", text.lower())
    if any(c in text.lower() for c in "äöüß"):
        return "de"
    de = sum(w in _DE_HINTS for w in words)
    en = sum(w in _EN_HINTS for w in words)
    return "de" if de > en else "en"


# Phrasings that ask for a procedure, an explanation or a safety rule, never for live
# plant data. A 3B model often answers these from general knowledge instead of calling
# ask_manual, so the Ollama backend runs the search up front when one matches.
_MANUAL_INTENT_RE = re.compile(
    r"\bhow (do|can|should|must) (i|we|you)\b|\bwhat (do|should|must) (i|we) (have to )?do\b"
    r"|\bwhat does .{0,30}\bmean\b|\bbefore (i|we|you) (open|start|touch|reach|work)"
    r"|\bwho (do|should|can) (i|we) call\b|\bsafety\b|\bprotective\b|\breset\b"
    r"|\bwie (kann|muss|soll|setze|sperre|wechsle|tausche|öffne|mache|starte|quittiere) (ich|man)\b"
    r"|\bwas (muss|soll|kann) (ich|man)\b|\bwas bedeutet\b|\bbevor ich\b"
    r"|\bwen (rufe|muss|soll|kann)\b|\bsicherheit|\bschutzausrüstung\b|\bzurücksetzen\b",
    re.IGNORECASE,
)


def manual_intent(text: str) -> bool:
    """True if the question is clearly a how-to / meaning / safety question for the handbook."""
    return bool(_MANUAL_INTENT_RE.search(text or ""))
