from core.config import load_config


def test_config_loads_extractor_and_speaker_from_yaml():
    config = load_config()
    assert config.extractor == "pymupdf"
    assert config.speaker == "kokoro"


def test_config_loads_queue_from_yaml():
    config = load_config()
    assert config.queue == "sqlite"
