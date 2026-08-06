"""Lightweight language detection via stopword heuristics."""

import re

_STOPWORDS: dict[str, set[str]] = {
    "en": {
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
        "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
        "this", "but", "his", "by", "from", "they", "we", "say", "her",
        "she", "or", "an", "will", "my", "one", "all", "would", "there",
        "their", "what", "so", "up", "out", "if", "about", "who", "get",
        "which", "go", "me", "when", "make", "can", "like", "time", "no",
        "just", "him", "know", "take", "people", "into", "year", "your",
        "good", "some", "could", "them", "see", "other", "than", "then",
        "now", "look", "only", "come", "its", "over", "think", "also",
        "back", "after", "use", "two", "how", "our", "work", "first",
        "well", "way", "even", "new", "want", "because", "any", "these",
        "give", "day", "most", "us", "is", "are", "was", "were", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall", "hi", "where",
        "order", "please", "tracking", "my",
    },
    "nl": {
        "de", "het", "een", "van", "en", "in", "is", "dat", "op", "te",
        "voor", "met", "zijn", "er", "maar", "om", "ook", "aan", "deze",
        "die", "bij", "naar", "over", "ze", "zich", "dan", "nog", "wel",
        "geen", "mijn", "uw", "jouw", "ons", "hun", "haar", "hem", "ik",
        "jij", "wij", "zij", "u", "je", "me", "mij", "jou", "ons", "jullie",
        "niet", "was", "worden", "kan", "hebben", "had", "deze", "dit",
        "beste", "wil", "bestelling", "annuleren", "groetjes", "hallo",
        "dank", "graag", "vraag", "helpen", "klant", "lever", "bezorg",
    },
    "de": {
        "der", "die", "das", "und", "in", "den", "von", "zu", "mit", "sich",
        "des", "auf", "für", "ist", "im", "dem", "nicht", "ein", "eine",
        "als", "auch", "es", "an", "werden", "aus", "er", "hat", "dass",
        "sie", "nach", "wird", "bei", "einer", "um", "am", "noch", "wie",
        "einem", "über", "einen", "so", "zum", "war", "haben", "nur", "oder",
        "aber", "vor", "zur", "bis", "mehr", "durch", "man", "sein", "wurde",
        "ich", "mein", "dein", "ihr", "wir", "ihr", "bestellung", "bitte",
        "hallo", "danke", "frage", "hilfe", "lieferung", "versand",
    },
    "fr": {
        "le", "la", "les", "de", "des", "un", "une", "et", "est", "en",
        "que", "qui", "dans", "ce", "il", "elle", "on", "nous", "vous",
        "ils", "elles", "ne", "pas", "plus", "pour", "par", "sur", "avec",
        "son", "sa", "ses", "mon", "ma", "mes", "ton", "ta", "tes", "notre",
        "votre", "leur", "leurs", "je", "tu", "il", "nous", "vous", "ils",
        "a", "ont", "ai", "as", "avons", "avez", "sont", "été", "être",
        "bonjour", "merci", "commande", "livraison", "question", "aide",
    },
    "es": {
        "el", "la", "los", "las", "de", "del", "un", "una", "y", "en",
        "que", "es", "por", "con", "no", "una", "su", "para", "como",
        "pero", "sus", "le", "ya", "o", "este", "sí", "porque", "esta",
        "entre", "cuando", "muy", "sin", "sobre", "también", "me", "hasta",
        "hay", "donde", "quien", "desde", "todo", "nos", "durante", "todos",
        "uno", "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos",
        "e", "esto", "mí", "antes", "algunos", "qué", "unos", "yo", "otro",
        "otras", "otra", "él", "tanto", "esa", "estos", "mucho", "quienes",
        "nada", "muchos", "cual", "poco", "ella", "estar", "estas", "algunas",
        "hola", "gracias", "pedido", "envío", "pregunta", "ayuda",
    },
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ÿ]+", text.lower())


def detect_language(text: str) -> str:
    """Return ISO-ish language code: en, nl, de, fr, es, or other."""
    tokens = _tokenize(text)
    if not tokens:
        return "other"

    scores = {lang: 0 for lang in _STOPWORDS}
    for token in tokens:
        for lang, words in _STOPWORDS.items():
            if token in words:
                scores[lang] += 1

    best_lang, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score == 0:
        return "other"

    # Require a clear winner when multiple languages score
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) > 1 and sorted_scores[0] == sorted_scores[1]:
        return "other"

    return best_lang
