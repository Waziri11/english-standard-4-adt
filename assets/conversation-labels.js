(() => {
  const speakers = [
    "Atu", "Bahati", "Class", "Daughter", "Doctor", "Father", "Hellen", "Iku",
    "James", "Jane", "Juma", "Kemy", "Mashaka", "Mother", "Mrs Babu",
    "Oddo", "Parent", "Police Officer", "Police officer", "Pupil", "Roza",
    "Shopkeeper", "Station announcer", "Station staff", "Teacher", "Ticket agent", "Tumani"
  ];
  const speakerPattern = new RegExp(`^(${speakers
    .map((speaker) => speaker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|")}|Pupil \\d+):\\s*(.*)$`, "s");

  const installStyles = () => {
    if (document.getElementById("conversation-inline-styles")) return;
    const style = document.createElement("style");
    style.id = "conversation-inline-styles";
    style.textContent = `
      .conversation-scroll {
        overflow-x: auto !important;
        overflow-y: visible;
      }
      .conversation-turn {
        display: inline-flex !important;
        align-items: baseline;
        gap: 0.5rem;
        min-width: max-content;
        max-width: none !important;
        white-space: nowrap !important;
      }
      .conversation-turn > * {
        white-space: nowrap !important;
      }
      .conversation-speaker {
        flex: none;
      }
    `;
    document.head.appendChild(style);
  };

  const markTurn = (element, speech) => {
    const turn = speech ? element : element.parentElement;
    if (!turn) return;
    turn.classList.add("conversation-turn");
    turn.parentElement?.classList.add("conversation-scroll");
  };

  const styleSpeaker = (element) => {
    if (!(element instanceof HTMLElement) || !element.matches("[data-id]")) return;
    if (element.classList.contains("sr-only") || element.classList.contains("hidden")) return;
    if (element.querySelector(":scope > .conversation-speaker")) return;

    const match = element.textContent.trim().match(speakerPattern);
    if (!match) return;

    const [, speaker, speech] = match;
    markTurn(element, speech);

    if (!speech) {
      element.classList.add("conversation-speaker");
      return;
    }

    const label = document.createElement("strong");
    label.className = "conversation-speaker mr-1 font-bold";
    label.textContent = `${speaker}:`;

    const words = document.createElement("span");
    words.className = "conversation-words font-normal text-gray-800";
    words.textContent = ` ${speech}`;
    element.replaceChildren(label, words);
  };

  const styleAll = (root = document) => {
    if (root instanceof HTMLElement) styleSpeaker(root);
    root.querySelectorAll?.("[data-id]").forEach(styleSpeaker);
  };

  const start = () => {
    const content = document.getElementById("content");
    if (!content) return;
    installStyles();
    styleAll(content);
    new MutationObserver((mutations) => {
      mutations.forEach((mutation) => styleAll(mutation.target));
    }).observe(content, { childList: true, subtree: true, characterData: true });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
