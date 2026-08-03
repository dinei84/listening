from __future__ import annotations

from pathlib import Path
import json

from PIL import Image
import pytesseract


def run_fixture(image_path: Path) -> dict:
    image = Image.open(image_path)
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    rows = []
    confidences = []
    for i in range(len(data["text"])):
        text = (data["text"][i] or "").strip()
        conf_raw = data["conf"][i]
        try:
            conf = float(conf_raw)
        except Exception:
            continue
        row = {
            "idx": i,
            "level": data["level"][i],
            "page_num": data["page_num"][i],
            "block_num": data["block_num"][i],
            "par_num": data["par_num"][i],
            "line_num": data["line_num"][i],
            "word_num": data["word_num"][i],
            "left": data["left"][i],
            "top": data["top"][i],
            "width": data["width"][i],
            "height": data["height"][i],
            "conf": conf,
            "text": text,
        }
        rows.append(row)
        if text and conf >= 0:
            confidences.append(conf)

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return {
        "fixture": str(image_path),
        "words_counted": len(confidences),
        "avg_confidence_words": avg_conf,
        "rows": rows,
    }


def main() -> None:
    fixtures = [
        Path("tests/fixtures/ocr/clear_text.png"),
        Path("tests/fixtures/ocr/degraded_text.png"),
        Path("tests/fixtures/ocr/very_degraded_text.png"),
        Path("tests/fixtures/ocr/native_pdf_rendered.png"),
    ]

    print("# Tesseract confidence experiment")
    print("tesseract_version:")
    print(pytesseract.get_tesseract_version())

    all_results = []
    for fixture in fixtures:
        result = run_fixture(fixture)
        all_results.append(result)
        print("\n## Fixture")
        print(result["fixture"])
        print("words_counted:", result["words_counted"])
        print("avg_confidence_words:", result["avg_confidence_words"])
        print("rows_json:")
        print(json.dumps(result["rows"], ensure_ascii=True, indent=2))

    print("\n# Summary")
    summary = [
        {
            "fixture": r["fixture"],
            "words_counted": r["words_counted"],
            "avg_confidence_words": r["avg_confidence_words"],
        }
        for r in all_results
    ]
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
