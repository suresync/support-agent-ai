from app.auto_reply import is_generic_auto_reply


def test_flags_hi_autoresponder():
    text = 'Did you mean to check the status of your order?\nIf this auto-response did not answer your question, just reply to this email with a "hi".'
    assert is_generic_auto_reply(text) is True


def test_allows_real_agent_reply():
    text = "Hi Saila,\nIâ€™m sorry the cotton cloth was missing. Weâ€™ll reship it today."
    assert is_generic_auto_reply(text) is False
