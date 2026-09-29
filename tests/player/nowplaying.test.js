// O que aparece na tela bloqueada do celular (OS-058). Lógica pura, sem DOM:
// é o texto que o ouvinte vê ao tirar o telefone do bolso, e os fallbacks
// importam porque livro sem capítulo detectado e título vazio acontecem.
const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const NowPlaying = require(
  path.join(__dirname, "..", "..", "player", "nowplaying.js")
);

test("build com livro e capítulo completos", () => {
  const meta = NowPlaying.build({
    bookTitle: "Programador Pragmático.pdf",
    chapter: { title: "Prefácio", order: 0 },
    chapterCount: 12,
    chunkIndex: 5,
    chunkCount: 533,
  });
  // O capítulo é o título grande: é o que o ouvinte quer reconhecer de relance.
  assert.strictEqual(meta.title, "Prefácio");
  assert.strictEqual(meta.artist, "Programador Pragmático");
  assert.strictEqual(meta.album, "Capítulo 1 de 12");
});

test("build remove a extensão .pdf do título do livro", () => {
  // O título vem de `file.filename`, então carrega a extensão. "Livro.pdf" na
  // tela bloqueada denuncia o encanamento.
  assert.strictEqual(
    NowPlaying.build({ bookTitle: "Meu Livro.pdf", chunkIndex: 0, chunkCount: 1 })
      .artist,
    "Meu Livro"
  );
  assert.strictEqual(
    NowPlaying.build({ bookTitle: "Meu Livro.PDF", chunkIndex: 0, chunkCount: 1 })
      .artist,
    "Meu Livro"
  );
  // Só a extensão final: um ".pdf" no meio do nome não pode ser comido.
  assert.strictEqual(
    NowPlaying.build({
      bookTitle: "guia.pdf.para.iniciantes.pdf",
      chunkIndex: 0,
      chunkCount: 1,
    }).artist,
    "guia.pdf.para.iniciantes"
  );
});

test("build sem capítulo detectado cai para a posição do trecho", () => {
  const meta = NowPlaying.build({
    bookTitle: "Livro.pdf",
    chapter: null,
    chapterCount: 0,
    chunkIndex: 5,
    chunkCount: 533,
  });
  // chunkIndex é 0-based; o humano conta a partir de 1.
  assert.strictEqual(meta.title, "Trecho 6 de 533");
  assert.strictEqual(meta.album, "");
});

test("build com um capítulo só não anuncia 'Capítulo 1 de 1'", () => {
  const meta = NowPlaying.build({
    bookTitle: "Livro.pdf",
    chapter: { title: "Parte 1", order: 0 },
    chapterCount: 1,
    chunkIndex: 0,
    chunkCount: 2,
  });
  assert.strictEqual(meta.title, "Parte 1");
  assert.strictEqual(meta.album, "");
});

test("build com título vazio não deixa a linha em branco", () => {
  for (const vazio of ["", "   ", null, undefined]) {
    const meta = NowPlaying.build({
      bookTitle: vazio,
      chunkIndex: 0,
      chunkCount: 3,
    });
    assert.strictEqual(meta.artist, "Audiobook", `falhou com ${JSON.stringify(vazio)}`);
  }
});

test("build com capítulo sem título cai para a posição do trecho", () => {
  const meta = NowPlaying.build({
    bookTitle: "Livro.pdf",
    chapter: { title: "   ", order: 2 },
    chapterCount: 5,
    chunkIndex: 9,
    chunkCount: 40,
  });
  assert.strictEqual(meta.title, "Trecho 10 de 40");
  // O capítulo existe, mesmo sem título: a contagem continua útil.
  assert.strictEqual(meta.album, "Capítulo 3 de 5");
});

test("build sem argumento nenhum devolve algo exibível", () => {
  const meta = NowPlaying.build();
  assert.strictEqual(typeof meta.title, "string");
  assert.strictEqual(typeof meta.artist, "string");
  assert.strictEqual(typeof meta.album, "string");
  assert.ok(meta.title.length > 0);
  assert.ok(meta.artist.length > 0);
});
