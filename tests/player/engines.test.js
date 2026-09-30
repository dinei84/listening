// Nome humano do motor e resumo por trecho (OS-059).
//
// `engine_used` é gravado como "kokoro"/"openai" — nomes de encanamento. O que o
// ouvinte precisa saber é "voz local" (não custa nada) ou "voz premium" (custa),
// e o fallback importa: um motor novo no futuro não pode virar "undefined" na
// tela de quem está pagando por ele.
const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const Engines = require(path.join(__dirname, "..", "..", "player", "engines.js"));

test("label traduz os motores conhecidos", () => {
  assert.strictEqual(Engines.label("kokoro"), "voz local");
  assert.strictEqual(Engines.label("openai"), "voz premium");
});

test("label não imprime 'undefined' para motor desconhecido", () => {
  // Um Speaker novo registrado no futuro cai aqui antes de alguém lembrar da UI.
  assert.strictEqual(Engines.label("azure"), "azure");
  assert.strictEqual(Engines.label("elevenlabs"), "elevenlabs");
});

test("label devolve texto exibível para entrada vazia", () => {
  for (const vazio of ["", "   ", null, undefined]) {
    const texto = Engines.label(vazio);
    assert.strictEqual(typeof texto, "string");
    assert.ok(texto.length > 0, `vazio para ${JSON.stringify(vazio)}`);
    assert.ok(!texto.includes("undefined"));
  }
});

test("isPaid separa o que custa do que não custa", () => {
  assert.strictEqual(Engines.isPaid("openai"), true);
  assert.strictEqual(Engines.isPaid("kokoro"), false);
  // Na dúvida sobre um motor desconhecido, NÃO afirmar que é grátis: dizer
  // "não custa nada" sobre algo que cobra é o erro caro dos dois.
  assert.strictEqual(Engines.isPaid("azure"), true);
});

test("summarize de lista vazia não inventa nada", () => {
  assert.deepStrictEqual(Engines.summarize([]), []);
  assert.deepStrictEqual(Engines.summarize(null), []);
});

test("summarize conta trechos por motor", () => {
  const resumo = Engines.summarize([
    { engine_used: "kokoro" },
    { engine_used: "openai" },
    { engine_used: "kokoro" },
  ]);
  assert.deepStrictEqual(resumo, [
    { engine: "kokoro", label: "voz local", count: 2, paid: false },
    { engine: "openai", label: "voz premium", count: 1, paid: true },
  ]);
});

test("summarize ordena do mais frequente para o menos", () => {
  const resumo = Engines.summarize([
    { engine_used: "openai" },
    { engine_used: "openai" },
    { engine_used: "kokoro" },
  ]);
  assert.deepStrictEqual(
    resumo.map((linha) => linha.engine),
    ["openai", "kokoro"]
  );
});

test("summarize ignora trecho sem engine_used", () => {
  // Chunk antigo, gravado antes de o campo existir, não pode virar uma linha
  // "undefined: 1" no resumo.
  const resumo = Engines.summarize([
    { engine_used: "kokoro" },
    {},
    { engine_used: null },
  ]);
  assert.deepStrictEqual(resumo, [
    { engine: "kokoro", label: "voz local", count: 1, paid: false },
  ]);
});

test("summarize de um motor só devolve uma linha", () => {
  const resumo = Engines.summarize([
    { engine_used: "kokoro" },
    { engine_used: "kokoro" },
  ]);
  assert.strictEqual(resumo.length, 1);
  assert.strictEqual(resumo[0].count, 2);
});
