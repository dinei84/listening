const STORAGE_KEY = "audiobook_player_state_v1";
const POLL_INTERVAL_MS = 2000;
const SAVE_THROTTLE_MS = 3000;

const uploadForm = document.getElementById("upload-form");
const pdfInput = document.getElementById("pdf-input");
const uploadStatus = document.getElementById("upload-status");
const manualForm = document.getElementById("manual-form");
const bookIdInput = document.getElementById("book-id-input");
const playerSection = document.getElementById("player-section");
const playerTitle = document.getElementById("player-title");
const playerStatus = document.getElementById("player-status");
const audioPlayer = document.getElementById("audio-player");
const playPauseBtn = document.getElementById("play-pause-btn");
const speedSelect = document.getElementById("speed-select");
const resumeBanner = document.getElementById("resume-banner");
const resumeBtn = document.getElementById("resume-btn");
const restartBtn = document.getElementById("restart-btn");

let chunks = [];
let currentIndex = 0;
let currentBookId = null;
let pollTimer = null;
let lastSaveTime = 0;
let pendingResume = null;

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

function pollUntilReady(bookId, onReady, onError) {
  stopPolling();
  const check = async () => {
    try {
      const { status } = await fetchStatus(bookId);
      playerStatus.textContent = `Status: ${status}`;
      if (status === "ready") {
        stopPolling();
        onReady();
      } else if (status === "error") {
        stopPolling();
        onError("Processamento falhou.");
      }
    } catch (err) {
      stopPolling();
      onError(err.message);
    }
  };
  check();
  pollTimer = setInterval(check, POLL_INTERVAL_MS);
}

function playChunk(index, startTime) {
  if (index < 0 || index >= chunks.length) return;
  currentIndex = index;
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

async function openBook(bookId, resumeState) {
  currentBookId = bookId;
  playerSection.hidden = false;
  playerTitle.textContent = `Livro: ${bookId}`;
  playerStatus.textContent = "Verificando status...";

  pollUntilReady(
    bookId,
    async () => {
      chunks = await fetchAudioChunks(bookId);
      if (chunks.length === 0) {
        playerStatus.textContent = "Nenhum áudio disponível.";
        return;
      }
      if (resumeState && resumeState.bookId === bookId) {
        pendingResume = resumeState;
        resumeBanner.hidden = false;
      } else {
        playChunk(0);
      }
      playerStatus.textContent = "Pronto.";
    },
    (message) => {
      playerStatus.textContent = `Erro: ${message}`;
    }
  );
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
  } catch (err) {
    uploadStatus.textContent = `Erro: ${err.message}`;
  }
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
  const saved = loadSavedState();
  if (saved && saved.bookId) {
    bookIdInput.value = saved.bookId;
    openBook(saved.bookId, saved);
  }
})();
