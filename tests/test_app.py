from streamlit.testing.v1 import AppTest


def test_app_starts_without_streamlit_exceptions() -> None:
    app = AppTest.from_file("app.py").run(timeout=20)
    assert not app.exception
    assert app.title[0].value == "YouTube → GPT Research Prompt"
    assert [item.label for item in app.button] == ["Scan channel", "Clear"]
    assert any(item.label == "Preferred transcript languages" for item in app.text_input)
