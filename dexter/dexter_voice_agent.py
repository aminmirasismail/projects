#!/usr/bin/env python3
"""
Push-to-Talk Voice Agent — PC prototype
=======================================

Hold a key to talk; release to send. The agent transcribes what you said,
sends it to Claude (carrying the right conversation context), and speaks the
reply back. This is the desktop stand-in for the eventual Raspberry Pi handheld:
the three swappable engines (STT / LLM / TTS) are isolated behind functions, so
porting later is mostly replacing those, while the conversation state machine
below carries over unchanged.

Only the transcript text ever leaves the machine (it goes to the Anthropic API).
Audio is recorded, transcribed, and spoken entirely locally.

--------------------------------------------------------------------------------
SETUP
--------------------------------------------------------------------------------
    pip install anthropic sounddevice numpy pynput faster-whisper pyttsx3
    export ANTHROPIC_API_KEY="sk-ant-..."        # Windows: set ANTHROPIC_API_KEY=...
    python ptt_voice_agent.py

First run downloads a small Whisper model (~75 MB) automatically.

USAGE
    - Hold the PTT key (default F8) and speak. Release to send.
    - Try: "what's a good cocktail with mezcal and grapefruit?"
    - Say "check past conversations" -> it reads back recent topics.
      Then say "the first one" / "the cocktail one" to resume it.
    - Say "resume last conversation" to jump back into the most recent.
    - Leave it >24h and your next normal prompt starts a fresh conversation.

NOTES
    - PTT_KEY is captured globally; F8 avoids clobbering normal typing.
    - macOS: grant Microphone + Accessibility (input monitoring) permissions to
      your terminal. If TTS misbehaves off the main thread there, see speak().
    - Pick specific input/output devices by setting INPUT_DEVICE / OUTPUT_DEVICE
      to an index from `python -c "import sounddevice; print(sounddevice.query_devices())"`.
"""

import os
import re
import json
import time
import queue
import sqlite3
import threading
from datetime import datetime, timezone

import numpy as np
import sounddevice as sd
from pynput import keyboard

# ------------------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------------------
PTT_KEY = keyboard.Key.f8        # hold-to-talk key
SAMPLE_RATE = 16000              # 16 kHz mono is what Whisper expects
INPUT_DEVICE = None              # None = system default; or an index (see NOTES)
OUTPUT_DEVICE = None             # None = system default; or an index

CHAT_MODEL = "claude-haiku-4-5-20251001"   # fast for voice; swap to "claude-sonnet-4-6" for more depth
TITLE_MODEL = "claude-haiku-4-5-20251001"  # cheap auto-titling
MAX_REPLY_TOKENS = 400           # keep spoken replies short

WHISPER_SIZE = "base.en"         # tiny.en / base.en / small.en — bigger = better + slower
DB_PATH = "voice_agent.db"
NEW_CONVO_GAP_HOURS = 24         # >24h since last use -> default to a new conversation

# Responses are spoken aloud, so the model must write for the ear, not the page.
SYSTEM_PROMPT = (
    "You are a helpful voice assistant. Your replies are read aloud by a "
    "text-to-speech engine, so write the way a person talks: short, plain "
    "sentences, no markdown, no bullet points, no headings, no code blocks, "
    "no emoji. Get to the point in a sentence or two unless genuinely asked "
    "for detail. If you need to list things, say them in a natural spoken run."
)

# ------------------------------------------------------------------------------
# ENGINE 1 of 3: SPEECH-TO-TEXT  (local, swap on the Pi if desired)
# ------------------------------------------------------------------------------
from faster_whisper import WhisperModel

_whisper = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")


def transcribe(audio: np.ndarray) -> str:
    """float32 mono @ SAMPLE_RATE -> text."""
    if audio.size == 0:
        return ""
    segments, _ = _whisper.transcribe(audio, language="en", vad_filter=True)
    return " ".join(seg.text for seg in segments).strip()


# ------------------------------------------------------------------------------
# ENGINE 2 of 3: THE LLM  (Anthropic API — the only thing that leaves the machine)
# ------------------------------------------------------------------------------
from anthropic import Anthropic

_client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment


def _text_of(resp) -> str:
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def chat(messages: list) -> str:
    """messages = [{'role': 'user'/'assistant', 'content': str}, ...] -> reply text."""
    resp = _client.messages.create(
        model=CHAT_MODEL,
        max_tokens=MAX_REPLY_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return _text_of(resp)


def make_title(user_text: str, assistant_text: str) -> str:
    resp = _client.messages.create(
        model=TITLE_MODEL,
        max_tokens=20,
        messages=[{
            "role": "user",
            "content": (
                "Give a 3-5 word topic label for this exchange. No quotes, no "
                f"punctuation.\nUser: {user_text}\nAssistant: {assistant_text}"
            ),
        }],
    )
    return _text_of(resp) or "Untitled"


# ------------------------------------------------------------------------------
# ENGINE 3 of 3: TEXT-TO-SPEECH  (local; swap for Piper on the Pi)
# ------------------------------------------------------------------------------
import pyttsx3

_tts = pyttsx3.init()


def speak(text: str) -> None:
    print(f"  [agent] {text}")
    _tts.say(text)
    _tts.runAndWait()
    # macOS note: if runAndWait() stalls off the main thread, route TTS through a
    # main-thread queue, or shell out to `say`, or move to Piper as planned.


# ------------------------------------------------------------------------------
# STORAGE — conversations live in SQLite; this is the "memory" the agent owns
# ------------------------------------------------------------------------------
def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                created   REAL,
                last_used REAL,
                title     TEXT,
                messages  TEXT
            )
        """)


def create_conversation() -> int:
    with db() as c:
        cur = c.execute(
            "INSERT INTO conversations (created, last_used, title, messages) VALUES (?, ?, ?, ?)",
            (_now(), _now(), None, "[]"),
        )
        return cur.lastrowid


def get_conversation(conv_id: int):
    with db() as c:
        return c.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()


def recent_conversations(limit: int = 5):
    with db() as c:
        return c.execute(
            "SELECT * FROM conversations ORDER BY last_used DESC LIMIT ?", (limit,)
        ).fetchall()


def load_messages(conv_id: int) -> list:
    row = get_conversation(conv_id)
    return json.loads(row["messages"]) if row else []


def save_turn(conv_id: int, messages: list, title: str | None):
    with db() as c:
        if title is None:
            c.execute(
                "UPDATE conversations SET messages = ?, last_used = ? WHERE id = ?",
                (json.dumps(messages), _now(), conv_id),
            )
        else:
            c.execute(
                "UPDATE conversations SET messages = ?, last_used = ?, title = ? WHERE id = ?",
                (json.dumps(messages), _now(), title, conv_id),
            )


def hours_since(ts: float) -> float:
    return (_now() - ts) / 3600.0


# ------------------------------------------------------------------------------
# SESSION STATE MACHINE — requirements 4, 5, 6 live here
# ------------------------------------------------------------------------------
class Session:
    def __init__(self):
        self.active_id: int | None = None
        self.awaiting_pick: bool = False     # did we just read out a list to choose from?
        self.listed: list = []               # the conversations we offered
        self.skip_stale_check: bool = False  # set after an explicit resume

    # --- intent routing -------------------------------------------------------
    def route(self, text: str) -> None:
        low = text.lower().strip()
        if not low:
            speak("I didn't catch that.")
            return

        # If we just offered a list, the next utterance is a selection.
        if self.awaiting_pick:
            self._resolve_pick(low)
            return

        if re.search(r"\bresume (the )?last\b|\bcontinue (the )?last\b", low):
            self._resume_last()
        elif re.search(r"\b(check|list|show|what were|previous|past) .*conversations?\b", low) \
                or "past conversations" in low or "previous conversations" in low:
            self._offer_list()
        elif re.search(r"\b(new|start a new|start over|fresh) conversation\b", low) or low in ("new conversation", "start over"):
            self._force_new()
        else:
            self._prompt(text)

    # --- commands -------------------------------------------------------------
    def _resume_last(self) -> None:
        recent = recent_conversations(1)
        if not recent:
            speak("There aren't any past conversations yet. Go ahead and start one.")
            return
        self.active_id = recent[0]["id"]
        self.skip_stale_check = True
        speak(f"Resuming: {recent[0]['title'] or 'your last conversation'}. Go ahead.")

    def _offer_list(self) -> None:
        self.listed = recent_conversations(5)
        if not self.listed:
            speak("You don't have any past conversations yet.")
            return
        titles = [row["title"] or "untitled" for row in self.listed]
        spoken = "; ".join(f"{i+1}, {t}" for i, t in enumerate(titles))
        speak(f"Here are your recent conversations: {spoken}. Which one?")
        self.awaiting_pick = True

    def _resolve_pick(self, low: str) -> None:
        self.awaiting_pick = False
        idx = self._match_selection(low)
        if idx is None:
            speak("I didn't catch which one. Say the number or the topic.")
            self.awaiting_pick = True
            return
        chosen = self.listed[idx]
        self.active_id = chosen["id"]
        self.skip_stale_check = True
        speak(f"Okay, back in {chosen['title'] or 'that conversation'}. Go ahead.")

    def _force_new(self) -> None:
        self.active_id = create_conversation()
        self.skip_stale_check = True
        speak("Started a new conversation. What's up?")

    # --- the normal path: ask Claude ------------------------------------------
    def _prompt(self, text: str) -> None:
        self._ensure_active()
        messages = load_messages(self.active_id)
        messages.append({"role": "user", "content": text})
        reply = chat(messages)
        messages.append({"role": "assistant", "content": reply})

        # Auto-title a brand-new conversation after its first exchange.
        existing = get_conversation(self.active_id)["title"]
        title = None
        if existing is None:
            title = make_title(text, reply)
        save_turn(self.active_id, messages, title)
        speak(reply)

    def _ensure_active(self) -> None:
        """Implements requirement 6: pick up the recent thread, or start fresh
        if it's been more than NEW_CONVO_GAP_HOURS since the system was last used."""
        if self.active_id is None:
            recent = recent_conversations(1)
            if recent and hours_since(recent[0]["last_used"]) <= NEW_CONVO_GAP_HOURS:
                self.active_id = recent[0]["id"]            # continue where we left off
            else:
                self.active_id = create_conversation()      # cold start -> new thread
        elif not self.skip_stale_check:
            row = get_conversation(self.active_id)
            if hours_since(row["last_used"]) > NEW_CONVO_GAP_HOURS:
                self.active_id = create_conversation()      # came back after a long gap
        self.skip_stale_check = False

    # --- helpers --------------------------------------------------------------
    _ORDINALS = {
        "first": 0, "1": 0, "one": 0,
        "second": 1, "2": 1, "two": 1,
        "third": 2, "3": 2, "three": 2,
        "fourth": 3, "4": 3, "four": 3,
        "fifth": 4, "5": 4, "five": 4,
    }

    def _match_selection(self, low: str):
        if "last" in low:
            return len(self.listed) - 1
        for word, idx in self._ORDINALS.items():
            if re.search(rf"\b{re.escape(word)}\b", low) and idx < len(self.listed):
                return idx
        # Fuzzy: best title-word overlap with what they said.
        said = set(re.findall(r"\w+", low))
        best, best_score = None, 0
        for i, row in enumerate(self.listed):
            title_words = set(re.findall(r"\w+", (row["title"] or "").lower()))
            score = len(said & title_words)
            if score > best_score:
                best, best_score = i, score
        return best


# ------------------------------------------------------------------------------
# AUDIO CAPTURE — record only while the key is held (requirements 1 & 2)
# ------------------------------------------------------------------------------
class Recorder:
    def __init__(self):
        self._frames = []
        self._stream = None
        self._lock = threading.Lock()

    def _cb(self, indata, frames, time_info, status):
        with self._lock:
            self._frames.append(indata.copy())

    def start(self):
        with self._lock:
            self._frames = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            device=INPUT_DEVICE, callback=self._cb,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            if not self._frames:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._frames, axis=0).flatten()


# ------------------------------------------------------------------------------
# MAIN LOOP — key listener feeds a worker thread so the listener never blocks
# ------------------------------------------------------------------------------
def main():
    if OUTPUT_DEVICE is not None:
        sd.default.device = (INPUT_DEVICE, OUTPUT_DEVICE)

    init_db()
    session = Session()
    recorder = Recorder()
    jobs: "queue.Queue[np.ndarray]" = queue.Queue()
    recording = threading.Event()

    def worker():
        while True:
            audio = jobs.get()
            if audio is None:
                return
            text = transcribe(audio)
            print(f"  [you]   {text!r}")
            if text.strip():
                try:
                    session.route(text)
                except Exception as e:
                    print(f"  [error] {e}")
                    speak("Something went wrong handling that.")
            jobs.task_done()

    threading.Thread(target=worker, daemon=True).start()

    def on_press(key):
        if key == PTT_KEY and not recording.is_set():
            recording.set()
            recorder.start()
            print("  [rec]   listening...")

    def on_release(key):
        if key == PTT_KEY and recording.is_set():
            recording.clear()
            audio = recorder.stop()
            print("  [rec]   sent.")
            jobs.put(audio)

    print(f"Ready. Hold {PTT_KEY} to talk, release to send. Ctrl-C to quit.\n")
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            jobs.put(None)
            print("\nBye.")


if __name__ == "__main__":
    main()
