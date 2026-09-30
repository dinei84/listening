const STORAGE_KEY = "audiobook_player_state_v1";
const POLL_INTERVAL_MS = 2000;
const SAVE_THROTTLE_MS = 3000;
const WAITING_MESSAGE = "Aguardando próximo trecho...";
// Acima de ~3s no trecho corrente, "Anterior" reinicia o trecho (padrão de
// podcast); abaixo disso, volta para o trecho anterior (OS-039).
const PREV_RESTART_THRESHOLD_S = 3;
// Salto fixo da OS-057. 15 s é o passo de tocador de audiobook: cobre a frase
// perdida sem exigir mira na barra.
const SKIP_SECONDS = 15;

// Vozes selecionáveis por idioma (OS-053), espelhando o catálogo do
// KokoroSpeaker. Chave é o valor do seletor de idioma (Automático não entra:
// voz fica desabilitada). Cada lista começa pela voz padrão do idioma — quem
// não escolhe recebe exatamente o comportamento de hoje.
const VOICES_BY_LANGUAGE = {
  en: [
    "af_heart",
    "af_alloy",
    "af_aoede",
    "af_bella",
    "af_jessica",
    "af_kore",
    "af_nicole",
    "af_nova",
    "af_river",
    "af_sarah",
    "af_sky",
    "am_adam",
    "am_echo",
    "am_eric",
    "am_fenrir",
    "am_liam",
    "am_michael",
    "am_onyx",
    "am_puck",
    "am_santa",
  ],
  es: ["ef_dora", "em_alex", "em_santa"],
  fr: ["ff_siwis"],
  hi: ["hf_alpha", "hf_beta", "hm_omega", "hm_psi"],
  it: ["if_sara", "im_nicola"],
  pt: ["pf_dora", "pm_alex", "pm_santa"],
  ja: ["jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo"],
  "zh-cn": [
    "zf_xiaoxiao",
    "zf_xiaobei",
    "zf_xiaoni",
    "zf_xiaoyi",
    "zm_yunjian",
    "zm_yunxi",
    "zm_yunxia",
    "zm_yunyang",
  ],
  "zh-tw": [
    "zf_xiaoxiao",
    "zf_xiaobei",
    "zf_xiaoni",
    "zf_xiaoyi",
    "zm_yunjian",
    "zm_yunxi",
    "zm_yunxia",
    "zm_yunyang",
  ],
};

// Preenche o seletor de voz com as vozes do idioma escolhido. Com idioma
// Automático o seletor fica desabilitado e vazio: não há como validar a voz
// contra um idioma que só será conhecido depois da detecção (OS-053).
function populateVoiceSelect() {
  const voices = VOICES_BY_LANGUAGE[languageSelect.value];
  voiceSelect.innerHTML = "";
  const padrao = document.createElement("option");
  padrao.value = "";
  padrao.textContent = "Padrão do idioma";
  voiceSelect.appendChild(padrao);
  if (voices) {
    for (const voice of voices) {
      const option = document.createElement("option");
      option.value = voice;
      option.textContent = voice;
      voiceSelect.appendChild(option);
    }
  }
  voiceSelect.disabled = !voices;
}

const uploadForm = document.getElementById("upload-form");
const pdfInput = document.getElementById("pdf-input");
const uploadStatus = document.getElementById("upload-status");
const languageSelect = document.getElementById("language-select");
const voiceSelect = document.getElementById("voice-select");
const manualForm = document.getElementById("manual-form");
const bookIdInput = document.getElementById("book-id-input");
const refreshBooksBtn = document.getElementById("refresh-books-btn");
const booksList = document.getElementById("books-list");
const booksListEmpty = document.getElementById("books-list-empty");
const playerSection = document.getElementById("player-section");
const playerTitle = document.getElementById("player-title");
const playerStatus = document.getElementById("player-status");
const synthesisProgress = document.getElementById("synthesis-progress");
const costWarning = document.getElementById("cost-warning");
const confirmCostBanner = document.getElementById("confirm-cost-banner");
const confirmCostBtn = document.getElementById("confirm-cost-btn");
const positionIndicator = document.getElementById("position-indicator");
const engineIndicator = document.getElementById("engine-indicator");
const engineSummary = document.getElementById("engine-summary");
const costBreakdown = document.getElementById("cost-breakdown");
const chaptersSection = document.getElementById("chapters-section");
const chaptersList = document.getElementById("chapters-list");
const audioPlayer = document.getElementById("audio-player");
const prevBtn = document.getElementById("prev-btn");
const playPauseBtn = document.getElementById("play-pause-btn");
const nextBtn = document.getElementById("next-btn");
const speedSelect = document.getElementById("speed-select");
const workerWarning = document.getElementById("worker-warning");
const resumeBanner = document.getElementById("resume-banner");
const resumeBtn = document.getElementById("resume-btn");
const restartBtn = document.getElementById("restart-btn");
const scrub = document.getElementById("scrub");
const timeReadout = document.getElementById("time-readout");
const back15Btn = document.getElementById("back-15-btn");
const forward15Btn = document.getElementById("forward-15-btn");

let chunks = [];
let currentIndex = 0;
// A posição em reprodução é ancorada na `sequence`, não no índice do array: a lista
// cresce durante a síntese e o índice do mesmo trecho pode mudar quando ela cresce.
let currentSequence = null;
let currentBookId = null;
let currentBookTitle = null;
let pollTimer = null;
let lastSaveTime = 0;
let pendingResume = null;
let playbackStarted = false;
let waitingForNextChunk = false;
let bookStatus = null;
// Capítulos do livro aberto (OS-027 via GET /books/{id}/chapters). Vazio para livros
// processados antes daquela OS — a seção fica escondida nesse caso.
let chapters = [];
// Total de trechos previsto para o livro (chunks_total da OS-024). Null enquanto a
// síntese não começou; o indicador cai no que já existe nesse caso.
let totalChunks = null;

// Linha de tempo do LIVRO (OS-057), reconstruída a cada chunk novo. É a soma dos
// duration_seconds que o servidor já mandava — nenhum dado novo foi preciso.
let timeline = Timeline.build([]);
// Enquanto o dedo/mouse está na barra, o timeupdate não pode disputar a posição.
let scrubbing = false;
// <audio> oculto que aquece o cache do trecho seguinte (ver preloadNext).
let preloader = null;

// Vocabulário de status para a UI (OS-033): os valores da API continuam crus no
// modelo (Book.status), só a exibição traduz. "uploaded" = Job enfileirado,
// ainda não tocado pelo worker.
function statusLabel(status) {
  switch (status) {
    case "uploaded":
      return "Na fila — aguardando processamento";
    case "extracting":
      return "Extraindo";
    case "processing":
      return "Processando";
    case "synthesizing":
      return "Sintetizando";
    case "ready":
      return "Pronto";
    case "error":
      return "Erro";
    case "paused":
      return "Pausado";
    case "pending_confirmation":
      return "Aguardando confirmação de custo";
    default:
      return status;
  }
}

function loadSavedState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (err) {
    return null;
  }
}

// Grava a posição no cache local e no servidor. É o ponto único de escrita.
function persistPosition(bookId, sequence, currentTime, title) {
  // localStorage continua como cache local (resposta imediata ao reabrir a
  // página), mas desde a OS-028 o servidor é a fonte de verdade.
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ bookId, sequence, currentTime, title })
  );
  saveProgressToServer(bookId, sequence, currentTime);
}

function saveState(bookId, sequence, currentTime, title) {
  const now = Date.now();
  if (now - lastSaveTime < SAVE_THROTTLE_MS) return;
  lastSaveTime = now;
  persistPosition(bookId, sequence, currentTime, title);
}

// Navegação manual (OS-039): grava a posição sem esperar o throttle, para o
// servidor e o cache já apontarem para o trecho novo mesmo se a reprodução
// estiver pausada no momento do clique.
function savePositionAfterNavigation() {
  if (currentBookId && currentSequence !== null) {
    persistPosition(currentBookId, currentSequence, 0, currentBookTitle);
  }
}

// Grava a posição no servidor. Falha de rede aqui é silenciosa de propósito: o
// throttle já garante nova tentativa em segundos e perder uma gravação de
// posição não pode interromper a reprodução.
function saveProgressToServer(bookId, sequence, currentTime) {
  fetch(`/books/${bookId}/progress`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sequence, position_seconds: currentTime }),
  }).catch(() => {});
}

// Busca a posição salva no servidor. Devolve null quando nunca houve progresso
// (404) ou se a chamada falhar — o chamador cai no cache do localStorage.
async function fetchProgress(bookId) {
  try {
    const response = await fetch(`/books/${bookId}/progress`);
    if (!response.ok) return null;
    return await response.json();
  } catch (err) {
    return null;
  }
}

// Busca os capítulos detectados (OS-027). Lista vazia é resposta legítima: livros
// processados antes daquela OS não têm capítulos persistidos.
async function fetchChapters(bookId) {
  try {
    const response = await fetch(`/books/${bookId}/chapters`);
    if (!response.ok) return [];
    return await response.json();
  } catch (err) {
    return [];
  }
}

// Qual capítulo contém uma dada sequence. Como o chapter_id vem em cada AudioChunk
// (OS-027), a associação é direta — sem depender de contagem de chunks por capítulo.
function chapterOfSequence(sequence) {
  const chunk = chunks.find((c) => c.sequence === sequence);
  if (!chunk) return null;
  return chapters.find((chapter) => chapter.id === chunk.chapter_id) || null;
}

// Primeiro chunk já sintetizado de um capítulo, ou null se a síntese ainda não
// chegou nele (livro grande sendo ouvido enquanto sintetiza — OS-030).
function firstChunkIndexOfChapter(chapterId) {
  const index = chunks.findIndex((chunk) => chunk.chapter_id === chapterId);
  return index >= 0 ? index : null;
}

function renderChapters() {
  chaptersList.innerHTML = "";
  chaptersSection.hidden = chapters.length === 0;
  if (chapters.length === 0) return;

  const atual = currentSequence === null ? null : chapterOfSequence(currentSequence);
  for (const chapter of chapters) {
    const li = document.createElement("li");
    const disponivel = firstChunkIndexOfChapter(chapter.id) !== null;

    const botao = document.createElement("button");
    botao.type = "button";
    botao.textContent = chapter.title;
    // Capítulo ainda não sintetizado não é clicável: não há áudio para pular.
    botao.disabled = !disponivel;
    botao.addEventListener("click", () => {
      const index = firstChunkIndexOfChapter(chapter.id);
      if (index !== null) playChunk(index);
    });

    li.appendChild(botao);
    if (atual && atual.id === chapter.id) {
      li.appendChild(document.createTextNode(" ← tocando"));
    }
    if (!disponivel) {
      li.appendChild(document.createTextNode(" (ainda sintetizando)"));
    }
    chaptersList.appendChild(li);
  }
}

// "Capítulo 2 de 12 — Introdução · trecho 45 de 340"
// Posição absoluta no livro: início do trecho corrente + onde o áudio está dentro
// dele. É o número que a barra e a leitura de tempo mostram.
function absolutePosition() {
  if (chunks.length === 0) return 0;
  return Timeline.absolute(timeline, currentIndex, audioPlayer.currentTime || 0);
}

// Reconstrói a linha de tempo quando a lista de chunks muda (síntese em curso).
function rebuildTimeline() {
  timeline = Timeline.build(chunks);
  renderTimeline();
}

// Escreve a leitura de tempo: "posição / total" à esquerda, restante à direita.
// `sufixo` só é usado enquanto a síntese não terminou, para a barra não mentir.
function writeReadout(posicao, sufixo) {
  timeReadout.innerHTML = "";
  const esquerda = document.createElement("span");
  esquerda.textContent = `${Timeline.format(posicao)} / ${Timeline.format(timeline.total)}`;
  const direita = document.createElement("span");
  direita.textContent = `-${Timeline.format(Timeline.remaining(timeline, posicao))}${sufixo || ""}`;
  timeReadout.appendChild(esquerda);
  timeReadout.appendChild(direita);
}

function renderTimeline() {
  const vazio = chunks.length === 0 || timeline.total <= 0;
  scrub.disabled = vazio;
  if (vazio) {
    scrub.max = 0;
    scrub.value = 0;
    timeReadout.textContent = "";
    return;
  }

  const posicao = absolutePosition();
  scrub.max = timeline.total;
  // Durante o arraste a barra pertence ao usuário: sobrescrever aqui faria o
  // controle "pular de volta" a cada timeupdate.
  if (!scrubbing) scrub.value = posicao;

  // A linha de tempo cobre só o que JÁ foi sintetizado. Enquanto faltam trechos,
  // dizer "7:48:00" seria mentira: o total mostrado é do que existe, e o aviso
  // de parcial fica explícito.
  const parcial = totalChunks !== null && chunks.length < totalChunks;
  writeReadout(
    posicao,
    parcial ? ` do que está pronto (${chunks.length} de ${totalChunks} trechos)` : ""
  );
}

// Pula para um segundo absoluto do livro, trocando de trecho se preciso. É o que
// faz o scrub e o ±15 s atravessarem a fronteira de chunk.
function seekAbsolute(absolute) {
  if (chunks.length === 0) return;
  const alvo = Timeline.locate(timeline, absolute);
  if (alvo.index === currentIndex) {
    audioPlayer.currentTime = alvo.offset;
    renderTimeline();
    savePositionAfterNavigation();
    return;
  }
  // Atravessou a fronteira: troca a src preservando se estava tocando ou pausado.
  playChunk(alvo.index, alvo.offset, !audioPlayer.paused);
  savePositionAfterNavigation();
}

// --------------------------------------------------------------------------
// Tela bloqueada (OS-058)
//
// Um audiobook é ouvido caminhando, no carro e dormindo. Sem isto, pausar exige
// desbloquear o telefone e achar a aba — que é o que separa demo de produto.
// Tudo aqui é opcional por definição: navegador sem mediaSession não pode
// derrubar o player, então cada acesso é guardado.
// --------------------------------------------------------------------------

function temMediaSession() {
  return typeof navigator !== "undefined" && "mediaSession" in navigator;
}

// Atualiza o texto e a barra da tela bloqueada. Chamado a cada troca de trecho.
function updateMediaSession() {
  if (!temMediaSession()) return;

  const meta = NowPlaying.build({
    bookTitle: currentBookTitle,
    chapter: currentSequence === null ? null : chapterOfSequence(currentSequence),
    chapterCount: chapters.length,
    chunkIndex: currentIndex,
    chunkCount: totalChunks || chunks.length,
  });

  if (typeof MediaMetadata !== "undefined") {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: meta.title,
      artist: meta.artist,
      album: meta.album,
      artwork: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml" }],
    });
  }
  updateMediaPositionState();
}

// A barra da tela bloqueada é a do LIVRO, não a do trecho: usa a linha de tempo
// da OS-057, senão o sistema mostraria 53 s de duração num livro de 7,8 h.
function updateMediaPositionState() {
  if (!temMediaSession() || !navigator.mediaSession.setPositionState) return;
  if (chunks.length === 0 || timeline.total <= 0) return;
  try {
    navigator.mediaSession.setPositionState({
      duration: timeline.total,
      playbackRate: audioPlayer.playbackRate || 1,
      // Saturado: o sistema rejeita position > duration, e um arredondamento
      // para cima no fim do último trecho bastaria para estourar.
      position: Math.min(absolutePosition(), timeline.total),
    });
  } catch (err) {
    // Alguns navegadores recusam combinações válidas em teoria; perder a barra
    // da tela bloqueada não pode interromper a reprodução.
  }
}

// Publicado para a verificação em navegador conseguir provar quais ações foram
// de fato aceitas: a Media Session API não deixa ler os handlers de volta, e um
// setActionHandler pode ser recusado por ação em alguns navegadores.
let registeredMediaActions = [];

function setupMediaSession() {
  if (!temMediaSession()) return;
  const acoes = [
    ["play", () => audioPlayer.play()],
    ["pause", () => audioPlayer.pause()],
    ["previoustrack", goToPrevious],
    ["nexttrack", goToNext],
    // Os mesmos 15 s dos botões da tela: dois passos diferentes para a mesma
    // intenção confundiriam quem usa os dois.
    ["seekbackward", () => seekAbsolute(absolutePosition() - SKIP_SECONDS)],
    ["seekforward", () => seekAbsolute(absolutePosition() + SKIP_SECONDS)],
    // seekTime vem em segundos ABSOLUTOS do livro, que é a unidade que a
    // setPositionState anunciou — por isso passa direto pelo seekAbsolute.
    ["seekto", (detalhe) => seekAbsolute(detalhe.seekTime)],
  ];
  for (const [acao, handler] of acoes) {
    try {
      navigator.mediaSession.setActionHandler(acao, handler);
      registeredMediaActions.push(acao);
    } catch (err) {
      // Ação não suportada neste navegador: ignora e segue com as outras.
    }
  }
}

// Qual motor narrou o trecho que está tocando, e o balanço do livro. Sem isto,
// o roteamento por expressividade — o diferencial do produto, decidido a cada
// chunk — não tem nenhuma superfície: `engine_used` era gravado e nunca saía do
// banco (achado 2.4 do estudo de UI/UX).
// Detalha o que sustenta o número do banner. Antes desta OS ele dizia só "este
// livro deve custar US$ X" e calava sobre de onde o valor vem — o usuário
// confirmava um número sem entender por que ele é baixo.
function renderCostBreakdown(statusData) {
  const total = statusData.estimated_cost;
  const premium = statusData.estimated_premium_cost;
  const trechosPagos = statusData.premium_chunk_count;
  const trechosTotais = statusData.estimated_chunk_count;

  const partes = [`Custo estimado: ${formatEstimate(total)}.`];

  // null é "nunca estimado", diferente de 0 ("medido e deu nada"): livro antigo,
  // gravado antes desta OS, não pode fingir que tem a divisão.
  if (premium !== null && premium !== undefined && trechosTotais) {
    if (trechosPagos > 0) {
      // toLocaleString, e não toFixed: o resto da linha usa vírgula decimal
      // ("US$ 0,85"), e um "9.1%" com ponto ao lado disso é erro visível.
      const porcento = ((trechosPagos / trechosTotais) * 100).toLocaleString(
        "pt-BR",
        { minimumFractionDigits: 1, maximumFractionDigits: 1 }
      );
      partes.push(
        `${trechosPagos} de ${trechosTotais} trechos (${porcento}%) vão para a ` +
          `voz premium, a ${formatEstimate(premium)}.`
      );
      partes.push(
        `Os outros ${trechosTotais - trechosPagos} ficam na voz local, que não custa nada.`
      );
    } else {
      partes.push("Nenhum trecho vai para a voz premium neste livro.");
    }
  }

  costBreakdown.textContent = partes.join(" ");
}

function renderEngineInfo() {
  const atual = chunks[currentIndex];
  if (!atual || !atual.engine_used) {
    engineIndicator.hidden = true;
  } else {
    engineIndicator.innerHTML = "";
    engineIndicator.appendChild(document.createTextNode("Narrado com "));
    const marca = document.createElement("span");
    marca.className = Engines.isPaid(atual.engine_used)
      ? "marca-motor pago"
      : "marca-motor";
    marca.textContent = Engines.label(atual.engine_used);
    engineIndicator.appendChild(marca);
    engineIndicator.hidden = false;
  }

  const resumo = Engines.summarize(chunks);
  // Um motor só é o caso normal de quem não usa roteamento: anunciar "2 de 2
  // trechos com voz local" é ruído sobre uma escolha que o usuário não fez.
  if (resumo.length < 2) {
    engineSummary.hidden = true;
    return;
  }
  const total = resumo.reduce((soma, linha) => soma + linha.count, 0);
  engineSummary.textContent =
    "Neste livro: " +
    resumo
      .map((linha) => `${linha.count} de ${total} trechos com ${linha.label}`)
      .join(" · ");
  engineSummary.hidden = false;
}

function renderPositionIndicator() {
  if (currentSequence === null || chunks.length === 0) {
    positionIndicator.hidden = true;
    return;
  }
  const partes = [];
  const capitulo = chapterOfSequence(currentSequence);
  if (capitulo) {
    partes.push(
      `Capítulo ${capitulo.order + 1} de ${chapters.length} — ${capitulo.title}`
    );
  }
  const total = totalChunks || chunks.length;
  partes.push(`trecho ${currentSequence + 1} de ${total}`);
  positionIndicator.textContent = partes.join(" · ");
  positionIndicator.hidden = false;
}

async function uploadBook(file) {
  const formData = new FormData();
  formData.append("file", file);
  const language = document.getElementById("language-select").value;
  if (language) {
    formData.append("language", language);
  }
  // Voz (OS-053): só é enviada quando um idioma foi escolhido e uma voz
  // específica selecionada — com idioma Automático o seletor fica desabilitado.
  const voice = voiceSelect.value;
  if (voice) {
    formData.append("voice", voice);
  }
  // Opt-in do nível médio (OS-038): só é enviado quando marcado, para que o
  // caminho padrão continue sem normalização, sem rede e sem custo.
  if (document.getElementById("normalize-checkbox").checked) {
    formData.append("normalize_text", "true");
  }
  const response = await fetch("/books", { method: "POST", body: formData });
  if (!response.ok) {
    throw new Error("Falha no upload");
  }
  return response.json();
}

async function fetchStatus(bookId) {
  const response = await fetch(`/books/${bookId}/status`);
  if (!response.ok) {
    throw new Error("Livro não encontrado");
  }
  return response.json();
}

async function fetchBooks() {
  const response = await fetch("/books");
  if (!response.ok) {
    throw new Error("Falha ao buscar livros");
  }
  return response.json();
}

function formatCreatedAt(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return date.toLocaleString();
}

function canPrioritize(status) {
  // Só faz sentido "Processar agora" em livro que ainda está esperando na fila
  // (uploaded) ou que foi pausado para dar lugar a outro — num livro pronto,
  // falho ou em processamento ativo não há o que priorizar.
  return status === "uploaded" || status === "paused";
}

async function prioritizeBook(bookId) {
  const response = await fetch(`/books/${bookId}/prioritize`, { method: "POST" });
  if (!response.ok) {
    let message = "Falha ao priorizar o livro";
    try {
      const data = await response.json();
      if (data && data.detail) message = data.detail;
    } catch (err) {
      // mantém a mensagem padrão
    }
    throw new Error(message);
  }
}

async function confirmBookCost(bookId) {
  const response = await fetch(`/books/${bookId}/confirm`, { method: "POST" });
  if (!response.ok) {
    let message = "Falha ao confirmar o custo";
    try {
      const data = await response.json();
      if (data && data.detail) message = data.detail;
    } catch (err) {
      // mantém a mensagem padrão
    }
    throw new Error(message);
  }
}

function canConfirmCost(status) {
  return status === "pending_confirmation";
}

function formatEstimate(cost) {
  if (cost === null || cost === undefined) return "";
  return cost.toLocaleString("pt-BR", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

function renderBooksList(books) {
  booksList.innerHTML = "";
  booksListEmpty.hidden = books.length > 0;
  booksListEmpty.textContent = "Nenhum livro ainda.";
  for (const book of books) {
    const li = document.createElement("li");
    const label = document.createElement("span");
    label.textContent = `${book.title} — ${statusLabel(book.status)} — ${formatCreatedAt(book.created_at)}`;

    const prioritizeBtn = document.createElement("button");
    prioritizeBtn.type = "button";
    prioritizeBtn.textContent = "Processar agora";
    prioritizeBtn.disabled = !canPrioritize(book.status);
    prioritizeBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      try {
        await prioritizeBook(book.id);
        refreshBooksList();
      } catch (err) {
        window.alert(`Erro ao priorizar: ${err.message}`);
      }
    });

    const confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.textContent = "Confirmar custo";
    confirmBtn.disabled = !canConfirmCost(book.status);
    confirmBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      try {
        await confirmBookCost(book.id);
        refreshBooksList();
        openBook(book.id, null, book.title);
      } catch (err) {
        window.alert(`Erro ao confirmar: ${err.message}`);
      }
    });

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Deletar";
    deleteBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteBook(book.id);
    });

    li.dataset.bookId = book.id;
    li.addEventListener("click", () => {
      // Mostra o título (legível), mas guarda o id junto: o campo continua
      // aceitando um book_id digitado à mão (OS-036).
      bookIdInput.value = book.title;
      bookIdInput.dataset.bookId = book.id;
      bookIdInput.dataset.bookTitle = book.title;
      openBook(book.id, null, book.title);
    });
    li.appendChild(label);
    li.appendChild(prioritizeBtn);
    li.appendChild(confirmBtn);
    li.appendChild(deleteBtn);
    booksList.appendChild(li);
  }
}

async function deleteBook(bookId) {
  if (!window.confirm("Deletar este livro? O áudio e o PDF serão removidos.")) {
    return;
  }
  try {
    const response = await fetch(`/books/${bookId}`, { method: "DELETE" });
    if (!response.ok) {
      // Mostra o motivo real que a API mandou (ex: "Book is still processing"),
      // com a mensagem genérica só como fallback quando não houver detail.
      let message = "Falha ao deletar o livro";
      try {
        const data = await response.json();
        if (data && data.detail) message = data.detail;
      } catch (err) {
        // mantém a mensagem padrão
      }
      throw new Error(message);
    }
    if (currentBookId === bookId) {
      resetPlaybackState();
      playerSection.hidden = true;
      currentBookId = null;
      localStorage.removeItem(STORAGE_KEY);
    }
    refreshBooksList();
  } catch (err) {
    window.alert(`Erro ao deletar: ${err.message}`);
  }
}

// Estados em que o livro depende do worker para sair do lugar. Sem worker, a
// tela dizia exatamente o mesmo que diria com tudo funcionando (OS-051).
const WAITING_FOR_WORKER = ["uploaded", "extracting", "processing", "synthesizing"];

async function updateWorkerWarning(books) {
  const esperando = books.some((book) => WAITING_FOR_WORKER.includes(book.status));
  if (!esperando) {
    workerWarning.hidden = true;
    return;
  }
  try {
    const response = await fetch("/worker");
    if (!response.ok) return;
    const { alive } = await response.json();
    workerWarning.hidden = alive;
    if (!alive) {
      workerWarning.textContent =
        "Nenhum worker ativo — os livros abaixo não vão processar. " +
        "Suba o worker com: python -m worker.tasks";
    }
  } catch {
    // Falha ao consultar o worker não pode atrapalhar a lista de livros.
  }
}

async function refreshBooksList() {
  try {
    const books = await fetchBooks();
    renderBooksList(books);
    updateWorkerWarning(books);
  } catch (err) {
    booksListEmpty.hidden = false;
    booksListEmpty.textContent = `Erro ao carregar livros: ${err.message}`;
  }
}

// `since` corta o payload do polling: sem ele, um livro de 533 chunks reenviava
// 51,8 KB a cada 2 s (91 MB por hora) para um delta quase sempre de 0 ou 1 chunk.
// Timeline.nextSince devolve null quando a faixa conhecida tem buraco — aí pede
// tudo, porque perder um trecho é pior que gastar banda.
async function fetchAudioChunks(bookId) {
  const since = Timeline.nextSince(chunks);
  const url =
    since === null ? `/books/${bookId}/audio` : `/books/${bookId}/audio?since=${since}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("Falha ao buscar áudio");
  }
  const data = await response.json();
  return data.slice().sort((a, b) => a.sequence - b.sequence);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function renderSynthesisProgress(status, chunksDone, chunksTotal) {
  if (
    chunksTotal === null ||
    chunksTotal === undefined ||
    status === "ready" ||
    status === "paused"
  ) {
    synthesisProgress.hidden = true;
    return;
  }
  synthesisProgress.hidden = false;
  synthesisProgress.max = chunksTotal;
  synthesisProgress.value = Math.min(chunksDone, chunksTotal);
}

function statusMessage(status, chunksDone, chunksTotal, statusData) {
  if (status === "pending_confirmation") {
    // O valor e a divisão ficam no banner logo abaixo (OS-059); repeti-los aqui
    // mostrava o mesmo número duas vezes na mesma tela.
    return "Aguardando confirmação de custo.";
  }
  if (status === "paused") {
    return chunks.length > 0
      ? "Pausado — tocando o que já foi sintetizado."
      : "Pausado.";
  }
  if (status === "error") {
    return chunks.length > 0
      ? `Erro no processamento — tocando os ${chunks.length} trecho(s) já sintetizados.`
      : "Erro: processamento falhou.";
  }
  if (status === "ready") {
    if (chunks.length === 0) return "Nenhum áudio disponível.";
    if (statusData && statusData.cost_degraded) {
      return "Pronto — processado com voz local (custo acima do teto).";
    }
    return waitingForNextChunk ? "Fim do áudio." : "Pronto.";
  }
  if (waitingForNextChunk) return WAITING_MESSAGE;

  const progress =
    chunksTotal === null || chunksTotal === undefined
      ? `Status: ${statusLabel(status)}`
      : `Sintetizando: ${chunksDone} de ${chunksTotal} chunks`;
  return chunks.length > 0 ? `${progress} — tocando o que já está pronto` : progress;
}

function mergeChunks(fetched) {
  const known = new Set(chunks.map((chunk) => chunk.sequence));
  const added = fetched.filter((chunk) => !known.has(chunk.sequence));
  if (added.length === 0) return 0;

  chunks = chunks.concat(added).sort((a, b) => a.sequence - b.sequence);
  if (currentSequence !== null) {
    const index = chunks.findIndex((chunk) => chunk.sequence === currentSequence);
    if (index >= 0) currentIndex = index;
  }
  // Trecho seguinte pode ter acabado de ser sintetizado: destrava "Próximo".
  updateNavButtons();
  // A linha de tempo cresce junto: total e restante mudam a cada trecho novo.
  rebuildTimeline();
  // O balanço entre motores muda com cada trecho sintetizado.
  renderEngineInfo();
  // O trecho seguinte pode ter ficado pronto agora — vale aquecer o cache dele.
  preloadNext(currentIndex);
  return added.length;
}

function startPlayback() {
  playbackStarted = true;
  if (pendingResume) {
    resumeBanner.hidden = false;
    return;
  }
  playChunk(0);
}

// Um ciclo de polling: atualiza o status, incorpora os chunks novos que a síntese
// produziu desde o ciclo anterior e mantém a reprodução andando sem reiniciá-la.
async function pollBook(bookId) {
  let statusData;
  try {
    statusData = await fetchStatus(bookId);
  } catch (err) {
    stopPolling();
    playerStatus.textContent = `Erro: ${err.message}`;
    return;
  }
  if (bookId !== currentBookId) return;

  bookStatus = statusData.status;
  // O título chega no status para aberturas por campo manual ou sessão restaurada
  // sem title salvo; a abertura pela lista já setou o título em mãos em openBook().
  if (statusData.title) {
    currentBookTitle = statusData.title;
    playerTitle.textContent = `Livro: ${statusData.title}`;
  }
  totalChunks = statusData.chunks_total;
  renderSynthesisProgress(
    bookStatus,
    statusData.chunks_done,
    statusData.chunks_total
  );

  // Trava de custo (OS-042): livro em espera mostra a estimativa + botão de
  // confirmar; livro degradado por teto mostra o aviso.
  confirmCostBanner.hidden = bookStatus !== "pending_confirmation";
  if (!confirmCostBanner.hidden) renderCostBreakdown(statusData);
  costWarning.hidden = !(
    bookStatus === "ready" && statusData.cost_degraded
  );
  if (!costWarning.hidden) {
    costWarning.textContent =
      "Processado com voz local — o custo estimado ultrapassou o teto configurado.";
  }

  let added = 0;
  try {
    added = mergeChunks(await fetchAudioChunks(bookId));
  } catch (err) {
    // Falha pontual ao listar o áudio não derruba o que já está tocando —
    // o próximo ciclo tenta de novo.
  }
  if (bookId !== currentBookId) return;

  // Capítulos podem aparecer depois do primeiro poll: o worker só os persiste
  // quando começa a processar o livro (OS-027).
  if (chapters.length === 0) {
    const fetched = await fetchChapters(bookId);
    if (bookId !== currentBookId) return;
    chapters = fetched;
  }

  if (!playbackStarted && chunks.length > 0) {
    startPlayback();
  } else if (waitingForNextChunk && added > 0) {
    playChunk(currentIndex + 1);
  }

  // Chunks novos podem ter destravado capítulos que ainda não tinham áudio.
  if (added > 0 || chapters.length > 0) {
    renderChapters();
    renderPositionIndicator();
  }

  // Livro terminado (ou falho, ou pausado): não há mais chunk novo para
  // esperar. Se a reprodução estava aguardando, o fim da lista agora é mesmo o
  // fim do livro — no caso "paused" o áudio já sintetizado continua tocável.
  if (bookStatus === "ready" || bookStatus === "error" || bookStatus === "paused") {
    stopPolling();
  }

  playerStatus.textContent = statusMessage(
    bookStatus,
    statusData.chunks_done,
    statusData.chunks_total,
    statusData
  );
}

// "Anterior" desabilitado no primeiro trecho e "Próximo" quando o trecho seguinte
// ainda não foi sintetizado (durante a síntese incremental, OS-021/030).
function updateNavButtons() {
  prevBtn.disabled = chunks.length === 0 || currentIndex <= 0;
  nextBtn.disabled = chunks.length === 0 || currentIndex >= chunks.length - 1;
}

// Padrão de tocador de podcast: se já se passaram mais de ~3s do trecho corrente,
// o primeiro clique reinicia o trecho atual (e um segundo clique rápido, agora com
// menos de 3s, volta de verdade para o anterior); abaixo disso, volta um trecho.
function goToPrevious() {
  if (chunks.length === 0) return;
  if (audioPlayer.currentTime > PREV_RESTART_THRESHOLD_S) {
    playChunk(currentIndex, 0);
    return;
  }
  if (currentIndex > 0) {
    playChunk(currentIndex - 1);
    savePositionAfterNavigation();
  }
}

function goToNext() {
  if (chunks.length === 0) return;
  if (currentIndex < chunks.length - 1) {
    playChunk(currentIndex + 1);
    savePositionAfterNavigation();
  }
}

function togglePlayPause() {
  if (chunks.length === 0) return;
  if (audioPlayer.paused) {
    audioPlayer.play();
  } else {
    audioPlayer.pause();
  }
}

// `autoplay` existe por causa do scrub (OS-057): arrastar a barra com o áudio
// pausado não pode começar a tocar sozinho. Padrão true — navegação por trecho,
// retomada e fim de trecho continuam tocando como antes.
function playChunk(index, startTime, autoplay = true) {
  if (index < 0 || index >= chunks.length) return;
  currentIndex = index;
  currentSequence = chunks[index].sequence;
  waitingForNextChunk = false;
  // O capítulo em foco e a posição mudam a cada troca de trecho (OS-029).
  renderChapters();
  renderPositionIndicator();
  renderEngineInfo();
  updateNavButtons();
  audioPlayer.src = chunks[index].url;
  audioPlayer.playbackRate = parseFloat(speedSelect.value);

  const onLoaded = () => {
    if (startTime) {
      audioPlayer.currentTime = startTime;
    }
    if (autoplay) audioPlayer.play();
    renderTimeline();
    audioPlayer.removeEventListener("loadedmetadata", onLoaded);
  };
  audioPlayer.addEventListener("loadedmetadata", onLoaded);
  audioPlayer.load();
  renderTimeline();
  preloadNext(index);
  updateMediaSession();
}

// Aquece o cache do trecho seguinte enquanto o corrente toca.
//
// Antes disto, o `ended` chamava playChunk, que só então começava a baixar: uma
// lacuna de rede + decode a cada ~53 s, ~533 vezes por livro — enquanto as OS-045
// e OS-056 calibravam pausas de 420-520 ms para não produzir emenda audível.
//
// Isto ENCURTA a lacuna (a resposta vem do cache do navegador), não a elimina:
// gapless de verdade exige MediaSource/Web Audio, e está fora do escopo da OS-057.
function preloadNext(index) {
  const proximo = index + 1;
  if (proximo >= chunks.length) {
    preloader = null;
    return;
  }
  const url = chunks[proximo].url;
  if (preloader && preloader.dataset.url === url) return;
  preloader = new Audio();
  preloader.dataset.url = url;
  preloader.preload = "auto";
  preloader.src = url;
  preloader.load();
}

function resetPlaybackState() {
  stopPolling();
  audioPlayer.pause();
  audioPlayer.removeAttribute("src");
  audioPlayer.load();
  chunks = [];
  currentIndex = 0;
  // Sem isto a barra guardaria o total do livro anterior ao abrir outro.
  timeline = Timeline.build([]);
  scrubbing = false;
  preloader = null;
  currentSequence = null;
  currentBookTitle = null;
  playbackStarted = false;
  waitingForNextChunk = false;
  bookStatus = null;
  pendingResume = null;
  chapters = [];
  totalChunks = null;
  updateNavButtons();
  renderTimeline();
  resumeBanner.hidden = true;
  synthesisProgress.hidden = true;
  costWarning.hidden = true;
  confirmCostBanner.hidden = true;
  positionIndicator.hidden = true;
  engineIndicator.hidden = true;
  engineSummary.hidden = true;
  chaptersSection.hidden = true;
  chaptersList.innerHTML = "";
}

async function openBook(bookId, resumeState, title) {
  resetPlaybackState();
  currentBookId = bookId;
  if (resumeState && resumeState.bookId === bookId) {
    pendingResume = resumeState;
    // Sessão restaurada do localStorage pode já carregar o título salvo — sem
    // precisar esperar o primeiro poll.
    if (resumeState.title) {
      currentBookTitle = resumeState.title;
    }
  }
  playerSection.hidden = false;
  const knownTitle = title || currentBookTitle;
  playerTitle.textContent = knownTitle ? `Livro: ${knownTitle}` : `Livro: ${bookId}`;
  playerStatus.textContent = "Verificando status...";

  // OS-028: o servidor é a fonte de verdade da posição de leitura — sobrevive a
  // trocar de navegador/dispositivo. O localStorage só vale como cache quando o
  // servidor não tem nada salvo (ou está inacessível).
  const serverProgress = await fetchProgress(bookId);
  if (bookId !== currentBookId) return;
  if (serverProgress) {
    pendingResume = {
      bookId,
      sequence: serverProgress.sequence,
      currentTime: serverProgress.position_seconds,
      title: currentBookTitle,
    };
  }

  // Desde a OS-021 o áudio é persistido chunk a chunk e `GET /books/{id}/audio`
  // devolve o que já existe sem olhar o status — o player não espera mais "ready".
  // O timer é armado antes do primeiro ciclo para que um livro já pronto/com erro
  // consiga pará-lo de dentro do próprio ciclo.
  pollTimer = setInterval(() => pollBook(bookId), POLL_INTERVAL_MS);
  await pollBook(bookId);
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = pdfInput.files[0];
  if (!file) return;
  uploadStatus.textContent = "Enviando...";
  try {
    const { id } = await uploadBook(file);
    uploadStatus.textContent = `Enviado. id: ${id}`;
    bookIdInput.value = id;
    openBook(id, null);
    refreshBooksList();
  } catch (err) {
    uploadStatus.textContent = `Erro: ${err.message}`;
  }
});

refreshBooksBtn.addEventListener("click", () => {
  refreshBooksList();
});

confirmCostBtn.addEventListener("click", async () => {
  if (!currentBookId) return;
  try {
    await confirmBookCost(currentBookId);
    confirmCostBanner.hidden = true;
    refreshBooksList();
    pollBook(currentBookId);
  } catch (err) {
    window.alert(`Erro ao confirmar: ${err.message}`);
  }
});

manualForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const digitado = bookIdInput.value.trim();
  if (!digitado) return;
  // Se o campo ainda exibe o título vindo de um clique na lista, usa o id guardado;
  // se o usuário digitou (ou alterou) o texto, trata como book_id (OS-036).
  const salvo = bookIdInput.dataset.bookId;
  const titulo = bookIdInput.dataset.bookTitle;
  const bookId = salvo && digitado === titulo ? salvo : digitado;
  openBook(bookId, null);
});

prevBtn.addEventListener("click", goToPrevious);
nextBtn.addEventListener("click", goToNext);
playPauseBtn.addEventListener("click", togglePlayPause);

// Enquanto arrasta: a leitura de tempo acompanha o dedo, mas o áudio NÃO é
// reposicionado a cada pixel — seria uma troca de src por movimento.
scrub.addEventListener("input", () => {
  scrubbing = true;
  writeReadout(Number(scrub.value), "");
});

// Ao soltar: aí sim pula, trocando de trecho se a posição caiu em outro.
scrub.addEventListener("change", () => {
  scrubbing = false;
  seekAbsolute(Number(scrub.value));
});

back15Btn.addEventListener("click", () => {
  seekAbsolute(absolutePosition() - SKIP_SECONDS);
});

forward15Btn.addEventListener("click", () => {
  seekAbsolute(absolutePosition() + SKIP_SECONDS);
});

speedSelect.addEventListener("change", () => {
  audioPlayer.playbackRate = parseFloat(speedSelect.value);
});

languageSelect.addEventListener("change", populateVoiceSelect);

// Atalhos de teclado (OS-039): ← anterior, → próximo, espaço play/pause.
// Não capturar quando o foco está num campo de texto (input/select/textarea),
// senão quebra a digitação (ex: campo "Abrir livro existente").
document.addEventListener("keydown", (event) => {
  const tag = document.activeElement && document.activeElement.tagName;
  if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    goToPrevious();
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    goToNext();
  } else if (event.key === " ") {
    event.preventDefault();
    togglePlayPause();
  }
});

audioPlayer.addEventListener("timeupdate", () => {
  // A barra do livro anda com o áudio; o throttle abaixo é só da GRAVAÇÃO de
  // posição, que continua como estava (OS-028).
  renderTimeline();
  updateMediaPositionState();
  if (currentBookId && chunks.length > 0) {
    saveState(
      currentBookId,
      chunks[currentIndex].sequence,
      audioPlayer.currentTime,
      currentBookTitle
    );
  }
});

audioPlayer.addEventListener("ended", () => {
  const nextIndex = currentIndex + 1;
  if (nextIndex < chunks.length) {
    playChunk(nextIndex);
    return;
  }
  if (pollTimer !== null) {
    // Alcançamos o fim do que já foi sintetizado, não o fim do livro: o próximo
    // ciclo de polling retoma sozinho quando o trecho seguinte ficar pronto.
    waitingForNextChunk = true;
    playerStatus.textContent = WAITING_MESSAGE;
  } else {
    playerStatus.textContent = "Fim do áudio.";
  }
});

// O sistema precisa saber se está tocando para desenhar o botão certo na tela
// bloqueada — sem isto, ele mostra "play" enquanto o áudio toca.
audioPlayer.addEventListener("play", () => {
  if (temMediaSession()) navigator.mediaSession.playbackState = "playing";
  updateMediaPositionState();
});

audioPlayer.addEventListener("pause", () => {
  if (temMediaSession()) navigator.mediaSession.playbackState = "paused";
});

resumeBtn.addEventListener("click", () => {
  resumeBanner.hidden = true;
  if (pendingResume) {
    const index = chunks.findIndex((c) => c.sequence === pendingResume.sequence);
    playChunk(index >= 0 ? index : 0, pendingResume.currentTime);
    pendingResume = null;
  }
});

restartBtn.addEventListener("click", () => {
  resumeBanner.hidden = true;
  pendingResume = null;
  playChunk(0);
});

(function init() {
  setupMediaSession();
  populateVoiceSelect();
  refreshBooksList();
  const saved = loadSavedState();
  if (saved && saved.bookId) {
    bookIdInput.value = saved.bookId;
    openBook(saved.bookId, saved);
  }
})();
