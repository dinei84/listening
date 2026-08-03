def test_pydantic_is_importable():
    import pydantic

    assert pydantic.__version__ is not None


def test_pymupdf_is_importable():
    import fitz

    assert fitz.__version__ is not None


def test_pytesseract_is_importable():
    import pytesseract

    assert pytesseract is not None


def test_kokoro_is_importable():
    import kokoro

    assert kokoro.__version__ is not None


def test_fastapi_is_importable():
    import fastapi

    assert fastapi.__version__ is not None


def test_config_yaml_loads_and_has_required_keys():
    import yaml

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    assert "extractor" in config
    assert "speaker" in config
    assert config["extractor"] == "pymupdf"
    assert config["speaker"] == "kokoro"
