// O que aparece na tela bloqueada do celular (OS-058).
//
// Separado do app.js pelo mesmo motivo do timeline.js: é lógica pura, e os
// fallbacks são o que mais erra. Livro sem capítulo detectado, capítulo sem
// título e título vindo de `file.filename` (com ".pdf" colado) são todos casos
// reais deste projeto, e nenhum deles pode virar linha em branco na tela de
// alguém que tirou o telefone do bolso no meio da rua.
(function (root) {
  "use strict";

  const SEM_TITULO = "Audiobook";

  /** Remove só a extensão .pdf final do nome do arquivo, preservando o resto. */
  function semExtensao(titulo) {
    return String(titulo).replace(/\.pdf$/i, "");
  }

  /** Texto não vazio, ou null. */
  function texto(valor) {
    if (valor === null || valor === undefined) return null;
    const limpo = String(valor).trim();
    return limpo.length > 0 ? limpo : null;
  }

  /**
   * Monta os metadados da tela bloqueada.
   *
   * `title` é a linha grande: o capítulo, porque é o que o ouvinte reconhece de
   * relance. `artist` é o livro. `album` é a contagem de capítulos, omitida
   * quando o livro tem um só — "Capítulo 1 de 1" é ruído.
   */
  function build(estado) {
    const dados = estado || {};
    const capitulo = dados.chapter || null;
    const totalCapitulos = Number(dados.chapterCount) || 0;
    const totalTrechos = Number(dados.chunkCount) || 0;
    const indiceTrecho = Number(dados.chunkIndex) || 0;

    const livro = texto(dados.bookTitle);
    const artist = livro ? semExtensao(livro) || SEM_TITULO : SEM_TITULO;

    const tituloCapitulo = capitulo ? texto(capitulo.title) : null;
    // chunkIndex é 0-based; quem lê conta a partir de 1.
    const title =
      tituloCapitulo || `Trecho ${indiceTrecho + 1} de ${totalTrechos || 1}`;

    const album =
      capitulo && totalCapitulos > 1
        ? `Capítulo ${(Number(capitulo.order) || 0) + 1} de ${totalCapitulos}`
        : "";

    return { title: title, artist: artist, album: album };
  }

  const api = { build: build };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.NowPlaying = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
