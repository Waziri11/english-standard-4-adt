/**
 * Keeps the page-level sign-language video and read-aloud narration together.
 * This runs before the ADT runtime so its mutually-exclusive media handlers
 * do not stop group-learning playback.
 */
(() => {
  "use strict"

  const NativeAudio = window.Audio
  const nativePause = HTMLMediaElement.prototype.pause
  let narration = null
  let narrationPlaying = false
  let startedTogether = false

  const signVideo = () =>
    document.querySelector('video[src*="/content/i18n/"][src*="/video/"]')

  const muteSignVideo = (video) => {
    if (!video) return
    video.defaultMuted = true
    video.muted = true
    video.volume = 0
  }

  const playTogether = (audio) => {
    narration = audio
    narrationPlaying = true
    const video = signVideo()
    if (!video) return

    muteSignVideo(video)

    if (!startedTogether) {
      video.currentTime = 0
      startedTogether = true
    }
    video.playbackRate = audio.playbackRate || 1
    video.play().catch(() => {})
  }

  const pauseTogether = (audio) => {
    if (audio !== narration) return
    narrationPlaying = false
    const video = signVideo()
    if (video) nativePause.call(video)
  }

  window.Audio = function SynchronizedAudio(...args) {
    const audio = new NativeAudio(...args)
    audio.addEventListener("play", () => playTogether(audio))
    audio.addEventListener("pause", () => pauseTogether(audio))
    audio.addEventListener("ratechange", () => {
      const video = signVideo()
      if (video && audio === narration) video.playbackRate = audio.playbackRate
    })
    return audio
  }
  window.Audio.prototype = NativeAudio.prototype

  // The stock runtime pauses sign video when narration becomes active.
  // Ignore only that programmatic pause while narration is actually playing.
  HTMLMediaElement.prototype.pause = function synchronizedPause() {
    if (this === signVideo() && narrationPlaying) return
    return nativePause.call(this)
  }

  // Prevent sign-video play events from switching the runtime into its
  // mutually-exclusive video-only mode and stopping the narration.
  window.addEventListener(
    "play",
    (event) => {
      if (event.target === signVideo()) {
        muteSignVideo(event.target)
        event.stopImmediatePropagation()
      }
    },
    true,
  )

  // The runtime creates the video only after Sign language is enabled.
  // Mute it immediately when that dynamically-created element appears.
  new MutationObserver(() => muteSignVideo(signVideo())).observe(document, {
    childList: true,
    subtree: true,
  })

  window.addEventListener("pagehide", () => {
    narrationPlaying = false
    startedTogether = false
  })
})()
