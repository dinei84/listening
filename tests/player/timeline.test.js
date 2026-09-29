// Testes da matemática da linha de tempo do livro (OS-057). Rodam com
// `node --test tests/player/`, sem navegador e sem dependência nova: o módulo
// em player/timeline.js é puro de propósito, exatamente para ser testável aqui.
const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const Timeline = require(path.join(__dirname, "..", "..", "player", "timeline.js"));

// Durações que dão fronteiras redondas: offsets [0, 10, 30], total 60.
const CHUNKS = [
  { sequence: 0, duration_seconds: 10 },
  { sequence: 1, duration_seconds: 20 },
  { sequence: 2, duration_seconds: 30 },
];

test("build acumula os deslocamentos e soma o total", () => {
  const tl = Timeline.build(CHUNKS);
  assert.deepStrictEqual(tl.offsets, [0, 10, 30]);
  assert.strictEqual(tl.total, 60);
  assert.strictEqual(tl.count, 3);
});

test("build de lista vazia não quebra", () => {
  const tl = Timeline.build([]);
  assert.deepStrictEqual(tl.offsets, []);
  assert.strictEqual(tl.total, 0);
  assert.strictEqual(tl.count, 0);
});

test("build de um chunk só", () => {
  const tl = Timeline.build([{ sequence: 0, duration_seconds: 42.5 }]);
  assert.deepStrictEqual(tl.offsets, [0]);
  assert.strictEqual(tl.total, 42.5);
});

test("build tolera duration_seconds ausente ou inválida", () => {
  // Chunk vindo do banco com duração nula não pode envenenar o total com NaN:
  // um NaN no acumulado apagaria a linha de tempo inteira a partir dali.
  const tl = Timeline.build([
    { sequence: 0, duration_seconds: 10 },
    { sequence: 1 },
    { sequence: 2, duration_seconds: null },
    { sequence: 3, duration_seconds: 5 },
  ]);
  assert.strictEqual(tl.total, 15);
  assert.deepStrictEqual(tl.offsets, [0, 10, 10, 10]);
});

test("locate no começo do primeiro trecho", () => {
  assert.deepStrictEqual(Timeline.locate(Timeline.build(CHUNKS), 0), {
    index: 0,
    offset: 0,
  });
});

test("locate no meio de um trecho", () => {
  assert.deepStrictEqual(Timeline.locate(Timeline.build(CHUNKS), 5), {
    index: 0,
    offset: 5,
  });
  assert.deepStrictEqual(Timeline.locate(Timeline.build(CHUNKS), 45), {
    index: 2,
    offset: 15,
  });
});

test("locate na fronteira exata cai no trecho que começa ali", () => {
  // 10 é o fim do trecho 0 e o começo do 1. Cair no 0 com offset 10 faria o
  // áudio terminar imediatamente e pular um trecho na navegação.
  assert.deepStrictEqual(Timeline.locate(Timeline.build(CHUNKS), 10), {
    index: 1,
    offset: 0,
  });
  assert.deepStrictEqual(Timeline.locate(Timeline.build(CHUNKS), 30), {
    index: 2,
    offset: 0,
  });
});

test("locate satura no fim em vez de estourar o índice", () => {
  const tl = Timeline.build(CHUNKS);
  assert.deepStrictEqual(Timeline.locate(tl, 60), { index: 2, offset: 30 });
  assert.deepStrictEqual(Timeline.locate(tl, 9999), { index: 2, offset: 30 });
});

test("locate satura no começo com valor negativo", () => {
  assert.deepStrictEqual(Timeline.locate(Timeline.build(CHUNKS), -5), {
    index: 0,
    offset: 0,
  });
});

test("locate em linha de tempo vazia devolve o início", () => {
  assert.deepStrictEqual(Timeline.locate(Timeline.build([]), 10), {
    index: 0,
    offset: 0,
  });
});

test("absolute é o inverso de locate", () => {
  const tl = Timeline.build(CHUNKS);
  for (const segundo of [0, 5, 10, 29.5, 30, 59.9]) {
    const { index, offset } = Timeline.locate(tl, segundo);
    assert.ok(
      Math.abs(Timeline.absolute(tl, index, offset) - segundo) < 1e-9,
      `ida e volta falhou em ${segundo}`
    );
  }
});

test("absolute com índice fora da faixa não devolve NaN", () => {
  const tl = Timeline.build(CHUNKS);
  assert.strictEqual(Timeline.absolute(tl, 99, 3), 3);
  assert.strictEqual(Timeline.absolute(tl, -1, 3), 3);
});

test("format usa mm:ss abaixo de uma hora", () => {
  assert.strictEqual(Timeline.format(0), "0:00");
  assert.strictEqual(Timeline.format(9), "0:09");
  assert.strictEqual(Timeline.format(59), "0:59");
  assert.strictEqual(Timeline.format(60), "1:00");
  assert.strictEqual(Timeline.format(3599), "59:59");
});

test("format usa h:mm:ss a partir de uma hora", () => {
  assert.strictEqual(Timeline.format(3600), "1:00:00");
  assert.strictEqual(Timeline.format(3661), "1:01:01");
  // 7,8h é o livro real medido no estudo.
  assert.strictEqual(Timeline.format(28080), "7:48:00");
});

test("format trunca fração e trata entrada inválida como zero", () => {
  assert.strictEqual(Timeline.format(65.9), "1:05");
  assert.strictEqual(Timeline.format(-3), "0:00");
  assert.strictEqual(Timeline.format(NaN), "0:00");
  assert.strictEqual(Timeline.format(undefined), "0:00");
});

test("remaining nunca é negativo", () => {
  const tl = Timeline.build(CHUNKS);
  assert.strictEqual(Timeline.remaining(tl, 0), 60);
  assert.strictEqual(Timeline.remaining(tl, 45), 15);
  assert.strictEqual(Timeline.remaining(tl, 60), 0);
  assert.strictEqual(Timeline.remaining(tl, 9999), 0);
});

// --------------------------------------------------------------------------
// nextSince: quanto o cliente pode pedir de delta sem perder chunk
// --------------------------------------------------------------------------

test("nextSince devolve null quando não há nada conhecido", () => {
  // Sem chunk nenhum não há delta possível: precisa pedir o payload cheio.
  assert.strictEqual(Timeline.nextSince([]), null);
  assert.strictEqual(Timeline.nextSince(null), null);
});

test("nextSince devolve a maior sequence quando a faixa é contígua desde 0", () => {
  assert.strictEqual(Timeline.nextSince([{ sequence: 0 }]), 0);
  assert.strictEqual(
    Timeline.nextSince([{ sequence: 0 }, { sequence: 1 }, { sequence: 2 }]),
    2
  );
});

test("nextSince devolve null quando há buraco na faixa conhecida", () => {
  // `worker/tasks.py::_resume_inconsistency` só compara a MAIOR sequence com o
  // total; não impede buraco. Pedir since=25 com 10..19 faltando perderia esses
  // trechos para sempre — na dúvida, paga a banda e pede tudo.
  assert.strictEqual(
    Timeline.nextSince([{ sequence: 0 }, { sequence: 1 }, { sequence: 5 }]),
    null
  );
  assert.strictEqual(Timeline.nextSince([{ sequence: 3 }]), null);
});
