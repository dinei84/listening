"""Validação do TextNormalizer com o provedor real (OS-038, seção 3).

NÃO faz parte da suíte de testes — faz chamada paga de verdade. Roda com a chave
do dono do projeto, lida de variável de ambiente (nunca de arquivo versionado).

    export LLM_API_KEY='sua-chave'
    venv/bin/python scripts/validate_normalizer.py \
        --base-url https://api.deepseek.com/v1 --model deepseek-chat

Confere as três coisas que a OS exige antes de confiar no normalizador:
  (a) 'R$ 50' vira "cinquenta reais" e não "cinquenta dólares";
  (b) nenhum conteúdo some;
  (c) a saída não vem com preâmbulo de conversa junto.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.normalizers.llm_normalizer import LLMNormalizer  # noqa: E402

# Casos difíceis reais, os mesmos que motivaram a OS.
CASOS = [
    ("moeda", "O plano custa R$ 50 por mês e o anual sai por R$ 480."),
    ("abreviação", "Ver pág. 42 e o cap. 7 para os detalhes do séc. XIX."),
    ("número", "Em 1984 havia 3 servidores e 128 GB de memória disponível."),
    (
        "prosa longa",
        "A engenharia de software trata de construir sistemas que permaneçam "
        "confiáveis diante da malícia, do erro ou do acaso, exigindo conhecimento "
        "interdisciplinar que abrange criptografia, psicologia e economia.",
    ),
    ("sigla", "O diagrama UML documenta a API REST usada no Docker."),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key-env", default="LLM_API_KEY")
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"ERRO: variável {args.api_key_env} não definida.", file=sys.stderr)
        print(f"  export {args.api_key_env}='sua-chave'", file=sys.stderr)
        return 1

    normalizer = LLMNormalizer(
        base_url=args.base_url, model=args.model, api_key=api_key
    )

    print(f"provedor: {args.base_url}  |  modelo: {args.model}\n")
    problemas = 0
    for nome, original in CASOS:
        try:
            bruto = normalizer._call_api(original)
        # Captura ampla: um provedor fora do ar não deve abortar a validação toda.
        except Exception as exc:  # noqa: BLE001
            print(f"[{nome}] FALHA na chamada: {exc}\n")
            problemas += 1
            continue

        aceito = normalizer._accept(original, bruto)
        descartado = aceito == original and bruto.strip() != original

        print(f"[{nome}]")
        print(f"  original: {original}")
        print(f"  bruto   : {bruto.strip()[:200]}")
        print(f"  aceito  : {'DESCARTADO pelo guarda-corpo' if descartado else 'sim'}")
        razao = len(bruto.strip()) / len(original)
        print(f"  razão de tamanho: {razao:.2f}")
        if descartado:
            problemas += 1
        print()

    print("=" * 60)
    print("Confira MANUALMENTE nas saídas acima:")
    print("  (a) 'R$ 50' virou 'cinquenta reais' (NÃO 'cinquenta dólares')")
    print("  (b) nenhuma informação sumiu do texto")
    print("  (c) nenhuma saída começa com 'Aqui está...' / 'Claro!' etc.")
    print(f"\nDescartes/falhas automáticas: {problemas} de {len(CASOS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
