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
let pollTimer = null;
let lastSaveTime = 0;
let pendingResume = null;
let playbackStarted = false;
let waitingForNextChunk = false;
let bookStatus = null;

function loadSavedState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (err) {
    return null;
  }
}

function saveState(bookId, sequence, currentTime) {
  const now = Date.now();
  if (now - lastSaveTime < SAVE_THROTTLE_MS) return;
  lastSaveTime = now;
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ bookId, sequence, currentTime })
  );
}

async function uploadBook(file) {
  const formData = new FormData();
  formData.append("file", file);
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

function renderBooksList(books) {
  booksList.innerHTML = "";
  booksListEmpty.hidden = books.length > 0;
  booksListEmpty.textContent = "Nenhum livro ainda.";
  for (const book of books) {
    const li = document.createElement("li");
    const label = document.createElement("span");
    label.textContent = `${book.title} — ${book.status} — ${formatCreatedAt(book.created_at)}`;

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Deletar";
    deleteBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteBook(book.id);
    });

    li.dataset.bookId = book.id;
    li.addEventListener("click", () => openBook(book.id, null));
    li.appendChild(label);
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
      throw new Error("Falha ao deletar o livro");
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
  if (chunksTotal === null || chunksTotal === undefined || status === "ready") {
    synthesisProgress.hidden = true;
    return;
  }
  synthesisProgress.hidden = false;
  synthesisProgress.max = chunksTotal;
  synthesisProgress.value = Math.min(chunksDone, chunksTotal);
}

function statusMessage(status, chunksDone, chunksTotal) {
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
      ? `Status: ${status}`
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

  if (!playbackStarted && chunks.length > 0) {
    startPlayback();
  } else if (waitingForNextChunk && added > 0) {
    playChunk(currentIndex + 1);
  }

  // Livro terminado (ou falho): não há mais chunk novo para esperar. Se a
  // reprodução estava aguardando, o fim da lista agora é mesmo o fim do livro.
  if (bookStatus === "ready" || bookStatus === "error") {
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
  playbackStarted = false;
  waitingForNextChunk = false;
  bookStatus = null;
  pendingResume = null;
  resumeBanner.hidden = true;
  synthesisProgress.hidden = true;
}

async function openBook(bookId, resumeState) {
  resetPlaybackState();
  currentBookId = bookId;
  if (resumeState && resumeState.bookId === bookId) {
    pendingResume = resumeState;
  }
  playerSection.hidden = false;
  playerTitle.textContent = `Livro: ${bookId}`;
  playerStatus.textContent = "Verificando status...";

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
  const bookId = bookIdInput.value.trim();
  if (!bookId) return;
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
      audioPlayer.currentTime
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
