// Nome humano do motor que narrou cada trecho (OS-059).
//
// `engine_used` é gravado como "kokoro"/"openai" — nomes de encanamento. O que
// interessa ao ouvinte é "voz local" (não custa nada) ou "voz premium" (custa),
// e é essa a pergunta que o dono não conseguia responder olhando a tela:
// "não consegui investigar se realmente está consumindo da API key" (13/08/2026).
(function (root) {
  "use strict";

  const NOMES = {
    kokoro: "voz local",
    openai: "voz premium",
  };

  // Motores que cobram. Só o Kokoro roda local e é de graça; qualquer outro
  // Speaker registrado no futuro é remoto até prova em contrário.
  const GRATUITOS = ["kokoro"];

  const DESCONHECIDO = "voz não identificada";

  function normaliza(engine) {
    if (engine === null || engine === undefined) return null;
    const limpo = String(engine).trim();
    return limpo.length > 0 ? limpo : null;
  }

  /** Nome humano do motor; para um motor não mapeado, devolve o próprio nome. */
  function label(engine) {
    const chave = normaliza(engine);
    if (chave === null) return DESCONHECIDO;
    return NOMES[chave] || chave;
  }

  /**
   * True quando o motor cobra.
   *
   * Motor desconhecido conta como PAGO de propósito: dizer "não custa nada"
   * sobre algo que cobra é o mais caro dos dois erros possíveis aqui.
   */
  function isPaid(engine) {
    const chave = normaliza(engine);
    if (chave === null) return false;
    return GRATUITOS.indexOf(chave) === -1;
  }

  /**
   * Conta os trechos por motor, do mais frequente para o menos.
   * Trecho sem `engine_used` é ignorado — chunk antigo não pode virar uma linha
   * "undefined: 1" no resumo.
   */
  function summarize(chunks) {
    if (!Array.isArray(chunks)) return [];
    const contagem = new Map();
    for (const chunk of chunks) {
      const chave = normaliza(chunk && chunk.engine_used);
      if (chave === null) continue;
      contagem.set(chave, (contagem.get(chave) || 0) + 1);
    }
    return [...contagem.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([engine, count]) => ({
        engine: engine,
        label: label(engine),
        count: count,
        paid: isPaid(engine),
      }));
  }

  const api = { label: label, isPaid: isPaid, summarize: summarize };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.Engines = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
