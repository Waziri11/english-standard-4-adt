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
        overflow-x: visible !important;
        overflow-y: visible;
      }
      .conversation-turn {
        display: grid !important;
        grid-template-columns: 11rem minmax(0, 1fr) !important;
        column-gap: 0.75rem !important;
        align-items: start;
        width: 100% !important;
        min-width: 0;
        max-width: 100% !important;
        white-space: normal !important;
      }
      .conversation-turn > * {
        min-width: 0;
        white-space: normal !important;
      }
      .conversation-speaker {
        grid-column: 1;
        font-weight: 700;
        white-space: nowrap !important;
      }
      .conversation-words {
        grid-column: 2;
        min-width: 0;
        color: #1f2937;
        font-weight: 400;
      }
      .conversation-words > p,
      .conversation-words > div,
      .conversation-words > span:not(.sr-only) {
        display: inline;
      }
      .conversation-words span:not(.sr-only) + span:not(.sr-only) {
        margin-left: 0.25em;
      }
      p[style*="grid-template-columns: 11rem"] {
        align-items: start;
      }
      p[style*="grid-template-columns: 11rem"] > :first-child,
      .book-dialogue-line > strong {
        white-space: nowrap !important;
      }
    `;
    document.head.appendChild(style);
  };

  const getTurn = (element) => {
    if (element.matches("p[data-id], div[data-id]")) return element;
    return element.closest("p, div");
  };

  const getSpeakerColour = (element) => {
    const colourPattern = /^text-(?:red|teal|cyan|green|lime|pink|sky)-\d+$/;
    return [...element.classList].find((name) => colourPattern.test(name)) ||
      [...(element.querySelector("strong")?.classList || [])].find((name) => colourPattern.test(name)) ||
      [...(element.parentElement?.classList || [])].find((name) => colourPattern.test(name)) || "";
  };

  const clearSpeakerPresentation = (element) => {
    const presentationPattern = /^(?:text-(?:red|teal|cyan|green|lime|pink|sky)-\d+|font-(?:bold|semibold|medium|extrabold))$/;
    [...element.classList]
      .filter((name) => presentationPattern.test(name))
      .forEach((name) => element.classList.remove(name));
  };

  const removeSpeakerPrefix = (root, speaker) => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let remaining = `${speaker}:`;
    while (remaining) {
      const node = walker.nextNode();
      if (!node) break;
      const value = node.nodeValue || "";
      const leading = value.match(/^\s*/)?.[0] || "";
      const candidate = value.slice(leading.length);
      const amount = Math.min(candidate.length, remaining.length);
      if (candidate.slice(0, amount) !== remaining.slice(0, amount)) break;
      node.nodeValue = leading + candidate.slice(amount).replace(/^\s+/, "");
      remaining = remaining.slice(amount);
    }
  };

  const styleSpeaker = (element) => {
    if (!(element instanceof HTMLElement) || !element.matches("[data-id]")) return;
    if (element.classList.contains("sr-only") || element.classList.contains("hidden")) return;
    const match = element.textContent.trim().match(speakerPattern);
    if (!match) return;

    const [, speaker, speech] = match;
    const turn = speech.trim()
      ? getTurn(element)
      : element.closest(".conversation-turn") || element.parentElement;
    if (!turn) return;
    if (turn.dataset.conversationFormatted === "true") {
      if (!turn.querySelector(":scope > .conversation-speaker")) {
        delete turn.dataset.conversationFormatted;
        styleSpeaker(element);
      } else if (element !== turn) {
        removeSpeakerPrefix(element, speaker);
      }
      return;
    }
    const colour = getSpeakerColour(element);
    clearSpeakerPresentation(element);
    turn.dataset.conversationFormatted = "true";
    turn.classList.add("conversation-turn");
    turn.parentElement?.classList.add("conversation-scroll");

    const label = document.createElement("strong");
    label.className = `conversation-speaker${colour ? ` ${colour}` : ""}`;
    label.textContent = `${speaker}:`;

    const words = document.createElement("span");
    words.className = "conversation-words";

    while (turn.firstChild) words.appendChild(turn.firstChild);
    removeSpeakerPrefix(words, speaker);
    const whitespaceWalker = document.createTreeWalker(words, NodeFilter.SHOW_TEXT);
    const whitespaceNodes = [];
    while (whitespaceWalker.nextNode()) {
      if (!whitespaceWalker.currentNode.nodeValue.trim()) whitespaceNodes.push(whitespaceWalker.currentNode);
    }
    whitespaceNodes.forEach((node) => node.remove());
    words.querySelectorAll("strong, span, p, div").forEach((node) => {
      if (!node.textContent.trim() && !node.matches("[data-id]")) node.remove();
    });
    turn.append(label, words);
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
