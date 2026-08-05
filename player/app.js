const STORAGE_KEY = "audiobook_player_state_v1";
const POLL_INTERVAL_MS = 2000;
const SAVE_THROTTLE_MS = 3000;
const WAITING_MESSAGE = "Aguardando próximo trecho...";

const uploadForm = document.getElementById("upload-form");
const pdfInput = document.getElementById("pdf-input");
const uploadStatus = document.getElementById("upload-status");
const manualForm = document.getElementById("manual-form");
const bookIdInput = document.getElementById("book-id-input");
const refreshBooksBtn = document.getElementById("refresh-books-btn");
const booksList = document.getElementById("books-list");
const booksListEmpty = document.getElementById("books-list-empty");
const playerSection = document.getElementById("player-section");
const playerTitle = document.getElementById("player-title");
const playerStatus = document.getElementById("player-status");
const synthesisProgress = document.getElementById("synthesis-progress");
const positionIndicator = document.getElementById("position-indicator");
const chaptersSection = document.getElementById("chapters-section");
const chaptersList = document.getElementById("chapters-list");
const audioPlayer = document.getElementById("audio-player");
const playPauseBtn = document.getElementById("play-pause-btn");
const speedSelect = document.getElementById("speed-select");
const resumeBanner = document.getElementById("resume-banner");
const resumeBtn = document.getElementById("resume-btn");
const restartBtn = document.getElementById("restart-btn");

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

function saveState(bookId, sequence, currentTime, title) {
  const now = Date.now();
  if (now - lastSaveTime < SAVE_THROTTLE_MS) return;
  lastSaveTime = now;
  // localStorage continua como cache local (resposta imediata ao reabrir a
  // página), mas desde a OS-028 o servidor é a fonte de verdade.
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ bookId, sequence, currentTime, title })
  );
  saveProgressToServer(bookId, sequence, currentTime);
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

async function refreshBooksList() {
  try {
    const books = await fetchBooks();
    renderBooksList(books);
  } catch (err) {
    booksListEmpty.hidden = false;
    booksListEmpty.textContent = `Erro ao carregar livros: ${err.message}`;
  }
}

async function fetchAudioChunks(bookId) {
  const response = await fetch(`/books/${bookId}/audio`);
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

function statusMessage(status, chunksDone, chunksTotal) {
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
    statusData.chunks_total
  );
}

function playChunk(index, startTime) {
  if (index < 0 || index >= chunks.length) return;
  currentIndex = index;
  currentSequence = chunks[index].sequence;
  waitingForNextChunk = false;
  // O capítulo em foco e a posição mudam a cada troca de trecho (OS-029).
  renderChapters();
  renderPositionIndicator();
  audioPlayer.src = chunks[index].url;
  audioPlayer.playbackRate = parseFloat(speedSelect.value);

  const onLoaded = () => {
    if (startTime) {
      audioPlayer.currentTime = startTime;
    }
    audioPlayer.play();
    audioPlayer.removeEventListener("loadedmetadata", onLoaded);
  };
  audioPlayer.addEventListener("loadedmetadata", onLoaded);
  audioPlayer.load();
}

function resetPlaybackState() {
  stopPolling();
  audioPlayer.pause();
  audioPlayer.removeAttribute("src");
  audioPlayer.load();
  chunks = [];
  currentIndex = 0;
  currentSequence = null;
  currentBookTitle = null;
  playbackStarted = false;
  waitingForNextChunk = false;
  bookStatus = null;
  pendingResume = null;
  chapters = [];
  totalChunks = null;
  resumeBanner.hidden = true;
  synthesisProgress.hidden = true;
  positionIndicator.hidden = true;
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

playPauseBtn.addEventListener("click", () => {
  if (audioPlayer.paused) {
    audioPlayer.play();
  } else {
    audioPlayer.pause();
  }
});

speedSelect.addEventListener("change", () => {
  audioPlayer.playbackRate = parseFloat(speedSelect.value);
});

audioPlayer.addEventListener("timeupdate", () => {
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
  refreshBooksList();
  const saved = loadSavedState();
  if (saved && saved.bookId) {
    bookIdInput.value = saved.bookId;
    openBook(saved.bookId, saved);
  }
})();
