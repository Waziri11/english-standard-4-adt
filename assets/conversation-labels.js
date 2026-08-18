(() => {
  const speakers = [
    "Atu", "Bahati", "Class", "Daughter", "Doctor", "Hellen", "Iku",
    "James", "Jane", "Juma", "Kemy", "Mashaka", "Mother", "Mrs Babu",
    "Oddo", "Parent", "Police Officer", "Pupil", "Roza", "Station announcer",
    "Station staff", "Teacher", "Ticket agent", "Tumani"
  ];
  const speakerPattern = new RegExp(`^(${speakers
    .map((speaker) => speaker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|")}|Pupil \\d+):\\s*(.+)$`, "s");
  const styleSpeaker = (element) => {
    if (!(element instanceof HTMLElement) || !element.matches("[data-id]")) return;
    if (element.querySelector(":scope > .conversation-speaker")) return;

    const match = element.textContent.trim().match(speakerPattern);
    if (!match) return;

    const [, speaker, speech] = match;
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
