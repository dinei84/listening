from collections import Counter


def clean_text(pages: list[str]) -> str:
    """Recebe o texto de cada página e devolve um único texto limpo, sem headers/footers repetidos e com hifenização de quebra de linha corrigida."""
    if not pages or all(not page.strip() for page in pages):
        return ""

    page_lines = [page.split("\n") for page in pages]
    repeated_lines = _find_repeated_lines(page_lines)

    filtered_lines: list[str] = []
    for lines in page_lines:
        filtered_lines.extend(
            line for line in lines if line.strip() not in repeated_lines
        )

    merged_lines = _fix_hyphenation(filtered_lines)
    return "\n".join(merged_lines).strip("\n")


def _find_repeated_lines(page_lines: list[list[str]]) -> set[str]:
    """Retorna o conjunto de linhas (sem espaços nas pontas) que aparecem em duas ou mais páginas."""
    counts: Counter[str] = Counter()
    for lines in page_lines:
        unique_lines = {line.strip() for line in lines if line.strip()}
        counts.update(unique_lines)
    return {line for line, count in counts.items() if count >= 2}


def _fix_hyphenation(lines: list[str]) -> list[str]:
    """Junta uma linha terminada em '-' com a próxima quando esta começa em minúscula, removendo o hífen e a quebra de linha."""
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()
        next_starts_lowercase = (
            i + 1 < len(lines) and lines[i + 1].strip()[:1].islower()
        )
        if stripped.endswith("-") and next_starts_lowercase:
            lines[i + 1] = stripped[:-1] + lines[i + 1].lstrip()
            i += 1
            continue
        result.append(line)
        i += 1
    return result
