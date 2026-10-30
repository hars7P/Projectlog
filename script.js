"use strict";

const screens = [...document.querySelectorAll(".screen")];
const photoInput = document.querySelector("#photo-upload");
const photoImage = document.querySelector(".photo-frame__image");
const thoughtMessage = document.querySelector("#thought-message");
const proposalContent = document.querySelector("#proposal-content");
const heartsContainer = document.querySelector("#celebration-hearts");
const confettiLayer = document.querySelector("#confetti-layer");
const musicPlayer = document.querySelector("#music-player");
const musicToggle = document.querySelector("#music-toggle");
const musicStatus = document.querySelector("#music-status");
const backgroundMusic = document.querySelector("#background-music");

let currentPhotoUrl = null;
let celebrationTimers = [];
let musicUnavailable = false;
let localAudioUrl = null;
let loadingLocalAudio = false;

function showScreen(screenId) {
  const nextScreen = document.getElementById(screenId);

  if (!nextScreen || !nextScreen.classList.contains("screen")) {
    return;
  }

  screens.forEach((screen) => {
    const isActive = screen === nextScreen;
    screen.hidden = !isActive;
    screen.classList.toggle("screen--active", isActive);
  });

  thoughtMessage.hidden = true;
  proposalContent.hidden = false;
  nextScreen.querySelector("h1, h2")?.focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: "smooth" });

  if (screenId === "celebration") {
    startCelebration();
  } else {
    stopCelebration();
  }
}

document.querySelectorAll("[data-go]").forEach((button) => {
  button.addEventListener("click", () => {
    showScreen(button.dataset.go);
  });
});

document.querySelector(".wordmark").addEventListener("click", (event) => {
  event.preventDefault();
  showScreen("welcome");
});

document.querySelector("#think-button").addEventListener("click", () => {
  proposalContent.hidden = true;
  thoughtMessage.hidden = false;
  document.querySelector("#thought-title").focus();
});

document.querySelector("#back-to-question").addEventListener("click", () => {
  thoughtMessage.hidden = true;
  proposalContent.hidden = false;
  document.querySelector("#yes-button").focus();
});

document.querySelector("#yes-button").addEventListener("click", () => {
  showScreen("celebration");
});

document.querySelector("#replay-button").addEventListener("click", () => {
  showScreen("welcome");
});

function updateMusicState(isPlaying) {
  musicPlayer.classList.toggle("is-playing", isPlaying);
  musicToggle.setAttribute("aria-pressed", String(isPlaying));
  musicToggle.setAttribute("aria-label", isPlaying ? "Pause our song" : "Play our song");

  if (!musicUnavailable) {
    musicStatus.hidden = true;
    musicStatus.textContent = "";
  }
}

function showMusicError() {
  musicUnavailable = true;
  updateMusicState(false);
  musicToggle.disabled = true;
  musicToggle.setAttribute("aria-label", "Our song is unavailable");
  musicStatus.textContent = "Our song couldn’t play. Check that the MP3 is available and your browser supports MP3 audio.";
  musicStatus.hidden = false;
}

musicToggle.addEventListener("click", async () => {
  if (musicUnavailable) {
    return;
  }

  if (!backgroundMusic.paused) {
    backgroundMusic.pause();
    return;
  }

  if (location.protocol === "file:" && !localAudioUrl) {
    if (loadingLocalAudio) {
      return;
    }

    loadingLocalAudio = true;
    musicToggle.disabled = true;
    musicStatus.textContent = "Getting our song ready…";
    musicStatus.hidden = false;

    try {
      const response = await fetch(backgroundMusic.getAttribute("src"));
      if (!response.ok && response.status !== 0) {
        throw new Error(`Could not load the song (HTTP ${response.status}).`);
      }

      const song = await response.blob();
      if (song.size === 0) {
        throw new Error("The song file is empty.");
      }

      localAudioUrl = URL.createObjectURL(song);
      backgroundMusic.src = localAudioUrl;
    } catch {
      showMusicError();
      return;
    } finally {
      loadingLocalAudio = false;
      if (!musicUnavailable) {
        musicToggle.disabled = false;
      }
    }
  }

  try {
    await backgroundMusic.play();
  } catch {
    if (backgroundMusic.error) {
      showMusicError();
      return;
    }

    musicStatus.textContent = "Unable to play the song. Please try again.";
    musicStatus.hidden = false;
  }
});

window.addEventListener("beforeunload", () => {
  if (localAudioUrl) {
    URL.revokeObjectURL(localAudioUrl);
  }
});

backgroundMusic.addEventListener("play", () => updateMusicState(true));
backgroundMusic.addEventListener("pause", () => updateMusicState(false));
backgroundMusic.addEventListener("error", showMusicError);

photoImage.addEventListener("error", () => {
  if (photoImage.dataset.fallbackApplied === "true") {
    return;
  }

  photoImage.dataset.fallbackApplied = "true";
  photoImage.src = "assets/portrait-placeholder.svg";
  photoImage.alt = "An elegant illustrated photo placeholder for Khushi";
});

photoInput.addEventListener("change", () => {
  const [file] = photoInput.files;

  if (!file) {
    return;
  }

  if (!file.type.startsWith("image/")) {
    photoInput.value = "";
    window.alert("Please choose an image file.");
    return;
  }

  if (currentPhotoUrl) {
    URL.revokeObjectURL(currentPhotoUrl);
  }

  currentPhotoUrl = URL.createObjectURL(file);
  photoImage.dataset.fallbackApplied = "false";
  photoImage.src = currentPhotoUrl;
  photoImage.alt = `Your chosen photo: ${file.name}`;
});

function stopCelebration() {
  celebrationTimers.forEach((timer) => window.clearTimeout(timer));
  celebrationTimers = [];
  heartsContainer.replaceChildren();
  confettiLayer.replaceChildren();
}

function startCelebration() {
  stopCelebration();

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const heartCount = reducedMotion ? 0 : 24;
  const confettiCount = reducedMotion ? 0 : 70;

  for (let index = 0; index < heartCount; index += 1) {
    const heart = document.createElement("span");
    const size = 12 + Math.random() * 15;
    const duration = 4.8 + Math.random() * 4.2;
    const delay = Math.random() * 5;

    heart.className = "floating-heart";
    heart.textContent = Math.random() > 0.24 ? "♥" : "♡";
    heart.style.left = `${Math.random() * 100}%`;
    heart.style.setProperty("--size", `${size}px`);
    heart.style.setProperty("--duration", `${duration}s`);
    heart.style.setProperty("--delay", `${delay}s`);
    heart.style.setProperty("--drift", `${Math.round(Math.random() * 100 - 50)}px`);
    heart.style.setProperty(
      "--heart-color",
      ["#c78683", "#d4a28f", "#b96f76", "#dfb3a5"][index % 4],
    );
    heartsContainer.append(heart);
  }

  for (let index = 0; index < confettiCount; index += 1) {
    const piece = document.createElement("span");
    const delay = Math.random() * 1.8;

    piece.className = "confetti-piece";
    piece.style.left = `${Math.random() * 100}%`;
    piece.style.setProperty("--duration", `${2.8 + Math.random() * 2.2}s`);
    piece.style.setProperty("--delay", `${delay}s`);
    piece.style.setProperty("--drift", `${Math.round(Math.random() * 130 - 65)}px`);
    piece.style.setProperty(
      "--confetti-color",
      ["#c78683", "#d4a28f", "#e7c8b7", "#bd8f96", "#f0d7ca"][index % 5],
    );
    confettiLayer.append(piece);
  }

  const cleanupTimer = window.setTimeout(() => {
    heartsContainer.replaceChildren();
    confettiLayer.replaceChildren();
  }, 11000);
  celebrationTimers.push(cleanupTimer);
}
