// Matemática da linha de tempo do LIVRO (OS-057).
//
// O player toca um chunk por vez (`audioPlayer.src = chunk.url`), então a régua
// nativa do <audio> cobria um trecho de ~53 s num livro de ~7,8 h — zerando 533
// vezes, sem responder "quanto falta". O dado para resolver isso já vinha do
// servidor: `duration_seconds` por chunk. Aqui é só a soma.
//
// Sem DOM e sem estado global de propósito: é o que torna este arquivo testável
// fora do navegador (`node --test tests/player/`).
(function (root) {
  "use strict";

  /** Converte para número finito, tratando null/undefined/NaN como 0. */
  function segundos(valor) {
    const numero = Number(valor);
    return Number.isFinite(numero) && numero > 0 ? numero : 0;
  }

  /**
   * Monta a linha de tempo a partir dos chunks ordenados por sequence.
   * Devolve { offsets, total, count } — offsets[i] é o segundo absoluto em que o
   * trecho i começa.
   */
  function build(chunks) {
    const lista = Array.isArray(chunks) ? chunks : [];
    const offsets = [];
    let acumulado = 0;
    for (const chunk of lista) {
      offsets.push(acumulado);
      // Duração inválida entra como 0: um NaN no acumulado apagaria a linha de
      // tempo inteira a partir dali, e a barra pararia de andar sem erro visível.
      acumulado += segundos(chunk && chunk.duration_seconds);
    }
    return { offsets: offsets, total: acumulado, count: offsets.length };
  }

  /** Duração do trecho `index`, derivada dos deslocamentos e do total. */
  function durationOf(timeline, index) {
    const fim =
      index + 1 < timeline.offsets.length
        ? timeline.offsets[index + 1]
        : timeline.total;
    return fim - timeline.offsets[index];
  }

  /**
   * Mapeia um segundo absoluto do livro para { index, offset } no trecho.
   * Satura nos dois extremos: negativo vira o início, além do total vira o fim
   * do último trecho — nunca um índice fora da faixa.
   */
  function locate(timeline, absolute) {
    if (timeline.count === 0) return { index: 0, offset: 0 };

    const alvo = segundos(absolute);
    if (alvo >= timeline.total) {
      const ultimo = timeline.count - 1;
      return { index: ultimo, offset: durationOf(timeline, ultimo) };
    }

    // Busca binária pelo último trecho que começa em ou antes do alvo. A
    // fronteira exata (alvo === offsets[i]) cai no trecho i, que é o que começa
    // ali: cair no anterior faria o áudio terminar na hora e pular um trecho.
    let baixo = 0;
    let alto = timeline.count - 1;
    while (baixo < alto) {
      const meio = Math.ceil((baixo + alto) / 2);
      if (timeline.offsets[meio] <= alvo) {
        baixo = meio;
      } else {
        alto = meio - 1;
      }
    }
    return { index: baixo, offset: alvo - timeline.offsets[baixo] };
  }

  /** Inverso de locate: posição absoluta no livro de um offset dentro do trecho. */
  function absolute(timeline, index, offsetInChunk) {
    const base =
      index >= 0 && index < timeline.offsets.length ? timeline.offsets[index] : 0;
    return base + segundos(offsetInChunk);
  }

  /** Segundos restantes até o fim do que a linha de tempo conhece; nunca negativo. */
  function remaining(timeline, absoluteSeconds) {
    return Math.max(0, timeline.total - segundos(absoluteSeconds));
  }

  /** Formata segundos como `mm:ss`, ou `h:mm:ss` a partir de uma hora. */
  function format(totalSeconds) {
    const inteiros = Math.floor(segundos(totalSeconds));
    const horas = Math.floor(inteiros / 3600);
    const minutos = Math.floor((inteiros % 3600) / 60);
    const sobra = inteiros % 60;
    const doisDigitos = (n) => String(n).padStart(2, "0");
    if (horas > 0) {
      return horas + ":" + doisDigitos(minutos) + ":" + doisDigitos(sobra);
    }
    return minutos + ":" + doisDigitos(sobra);
  }

  /**
   * Maior sequence que o cliente pode mandar como `?since=`, ou null para pedir
   * o payload cheio.
   *
   * Só devolve número quando as sequences conhecidas são contíguas desde 0. O
   * worker não impede buraco na faixa (`_resume_inconsistency` só compara a maior
   * sequence com o total), e pedir since=25 com 10..19 faltando perderia esses
   * trechos para sempre. Na dúvida, paga a banda e pede tudo.
   */
  function nextSince(chunks) {
    if (!Array.isArray(chunks) || chunks.length === 0) return null;
    const ultimo = chunks[chunks.length - 1];
    const maior = Number(ultimo && ultimo.sequence);
    if (!Number.isInteger(maior)) return null;
    return maior === chunks.length - 1 ? maior : null;
  }

  const api = {
    build: build,
    nextSince: nextSince,
    locate: locate,
    absolute: absolute,
    remaining: remaining,
    format: format,
    durationOf: durationOf,
  };

  // Funciona como módulo no Node (testes) e como global no navegador.
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.Timeline = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
