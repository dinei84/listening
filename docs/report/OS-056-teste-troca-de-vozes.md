# OS-056 — Teste de troca de vozes (amostra exigida pelo critério de aceite)

**Data:** 28/09/2026
**Executado por:** dono do projeto, com assistência
**Motivo:** o critério de aceite da OS-056 exigia "uma amostra de áudio de parágrafo real com roteamento ativo, antes de qualquer conclusão sobre o resultado". Ela não foi produzida na entrega original porque a conta da OpenAI ficou sem crédito durante toda a fase de testes.

## 1. Configuração do teste

| Parâmetro | Valor |
|---|---|
| `speaker` (base) | `kokoro` |
| `routing.enabled` | `true` |
| `routing.premium_speaker` | `openai` |
| `routing.min_expressive_sentences` | **5** (elevado de 3, a pedido do dono) |
| `OPENAI_TTS_MODEL` | `gpt-4o-mini-tts` |
| `OPENAI_TTS_VOICE` | `nova` |
| `OPENAI_INSTRUCTIONS` | variante **só-entonação** (ver seção 4) |

O limiar 5 foi escolhido de propósito: com ele, um texto de perfil misto produz chunks dos **dois** motores, que é o que o teste precisa exercitar.

## 2. Texto de teste

Três blocos, desenhados para cair em chunks distintos:

1. Denso em perguntas e exclamações
2. Prosa técnica corrida, sem nenhuma pontuação expressiva
3. Denso de novo

A divisão foi **verificada antes de gastar**, para garantir que os dois motores seriam exercidos. A primeira versão do texto falhou nesse ponto: o `chunk_text` agrupou o fim da prosa com o bloco final, e os dois chunks resultantes caíram na OpenAI. A prosa foi alongada até ocupar um chunk inteiro sozinha.

## 3. Resultado

```
chunk 0 |  932 chars |  8 frases expressivas -> OPENAI
chunk 1 |  979 chars |  0 frases expressivas -> kokoro
chunk 2 |  364 chars |  6 frases expressivas -> OPENAI
```

Saída real do pipeline:

```
seq 0 | motor openai  |  64.2s
seq 1 | motor kokoro  |  57.0s
seq 2 | motor openai  |  25.6s

audio contínuo: 146.7s
```

**Duas trocas de voz**, ambas em fronteira de chunk. Arquivo: `~/teste_troca_limiar5.wav`.

## 4. Instrução de estilo adotada

```
Faça a entonação subir claramente até o fim de cada pergunta, mesmo nas longas,
e dê ênfase real nas exclamações. Mantenha o ritmo natural de fala.
```

Escolhida após comparação de três variantes sobre o mesmo texto:

| Variante | Duração | Avaliação do dono |
|---|---|---|
| Kokoro (referência) | 13,6 s | — |
| OpenAI **sem** `instructions` | 14,8 s | cadência perfeita, entonação muito boa |
| OpenAI **só-entonação** | 15,8 s | **aprovada** |
| OpenAI **com ritmo + entonação** | 16,1 s | entonação levemente superior, **cadência carregada** |

A instrução original pedia "ritmo pausado", e isso **somava com as pausas que a OS-045 já insere no áudio depois da síntese** — pedir ao modelo para desacelerar num pipeline que já desacelera. Removida a parte de ritmo, a cadência voltou ao nível aprovado sem perder a entonação.

## 5. Custo

| Item | Chars | US$ |
|---|---|---|
| Teste de crédito (2 chamadas) | 114 | 0,0018 |
| A/B de instruções (3 variantes) | 615 | 0,0099 |
| **Este teste de troca de vozes** | 1.296 | **0,0208** |
| **Total da sessão** | | **≈ 0,033** |

Projeção para o "Programador Pragmático" completo (579.509 chars, 624 chunks):

| Limiar | Chunks pagos | % do livro | Trocas de voz | Custo |
|---|---|---|---|---|
| 2 | 106 | 17,3% | 142 | US$ 1,61 |
| 3 | 56 | 9,1% | 84 | US$ 0,85 |
| 4 | 32 | 5,2% | 58 | US$ 0,49 |
| **5** | 17 | 2,8% | 32 | US$ 0,26 |
| — | 624 | 100% | 0 | US$ 9,32 |

## 6. O que este teste NÃO responde

**Se a troca de voz incomoda na escuta longa.** A amostra tem 2,4 minutos e duas trocas. Um livro no limiar 5 teria 32 trocas ao longo de horas — a percepção pode ser diferente quando o ouvinte já se acostumou a uma voz.

**Se o ganho compensa em livro real.** No limiar 5, **97,2% do livro continua no Kokoro**. O ganho de entonação aparece em 17 chunks de 624.

## 7. Veredito

**Aprovado pelo dono em 28/09/2026.** A troca de vozes nas duas fronteiras foi considerada aceitável na escuta, com a configuração de instrução só-entonação. O critério de aceite da OS-056 que exigia esta amostra fica **cumprido**.

Observação do dono registrada na mesma escuta, que vira item de backlog: **o limiar é candidato natural a diferenciador de plano comercial** — o plano "plus" seria o que habilita o motor pago, e os planos se distinguiriam pelo limiar configurado (quanto menor, mais trechos com voz premium, maior o custo). Ver item 59 do `PROJECT_STATE.md`.
