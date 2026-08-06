from app.language import detect_language


def test_detect_dutch():
    assert detect_language("Beste, ik wil mijn bestelling annuleren. Groetjes") == "nl"


def test_detect_english():
    assert detect_language("Hi, where is my order #12345 tracking please?") == "en"
