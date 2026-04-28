import streamlit as st
import os
import tempfile
import whisper
import srt
import datetime
import re
import time
import threading
import pandas as pd
from pydub import AudioSegment
from io import BytesIO
from openpyxl.styles import Alignment, Font, PatternFill

st.set_page_config(page_title="Aakash EduTranscribe", layout="centered", page_icon="🎯")

# ================= SETTINGS =================
TRANSCRIPT_WINDOW = 3
TIME_OFFSET = 2  # ✅ GLOBAL +2 SECOND OFFSET

QUESTION_PATTERNS = [
    r"\bmoving\s+(to|with|on\s+to)\s+(the\s+)?next\s+question\b",
    r"\blet[''s]*\s+(come|move)\s+to\s+(question|problem)(\s*(number\s*)?\d+)?\b",
    r"\bnext\s+question\b",
    r"\bquestion\s*(number\s*)?\d+\b",
    r"\bq\.?\s*\d+\b",
    r"\bproblem\s*(number\s*)?\d+\b",
]

LETS_START_PATTERNS = [
    r"\blet[''s]*\s+(start|begin|get\s+started|go)\b",
    r"\bchalo\s+(shuru|start)\b",
    r"\bshuru\s+karte\b",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in QUESTION_PATTERNS]
COMPILED_START_PATTERNS = [re.compile(p, re.IGNORECASE) for p in LETS_START_PATTERNS]

# ================= HELPERS =================
def format_ts(seconds):
    seconds = max(0, int(seconds))
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"

def get_transcript_at(segments, target_sec):
    return " ".join([
        seg["text"].strip()
        for seg in segments
        if abs(seg["start"] - target_sec) <= TRANSCRIPT_WINDOW
    ])

def find_lets_start_second(segments):
    for seg in segments:
        for p in COMPILED_START_PATTERNS:
            if p.search(seg["text"]):
                return seg["start"]
    return None

# ================= MAIN LOGIC =================
def detect_question_changes(segments, is_q_series=False):
    hits = []
    seen = set()

    for seg in segments:
        text = seg["text"].strip()
        for p in COMPILED_PATTERNS:
            if p.search(text):

                raw = seg["start"] + TIME_OFFSET  # ✅ OFFSET

                if any(abs(raw - s) < 5 for s in seen):
                    break

                seen.add(raw)

                hits.append({
                    "adj_sec": raw,
                    "timestamp": format_ts(raw),
                    "transcript": text
                })
                break

    hits.sort(key=lambda x: x["adj_sec"])

    if is_q_series:
        start = find_lets_start_second(segments)
        first_sec = (start + TIME_OFFSET) if start else TIME_OFFSET
    else:
        first_sec = TIME_OFFSET

    first = {
        "adj_sec": first_sec,
        "timestamp": format_ts(first_sec),
        "transcript": get_transcript_at(segments, first_sec)
    }

    hits = [h for h in hits if h["adj_sec"] > first_sec + 5]

    return [first] + hits

# ================= EXCEL =================
def make_excel(rows):
    df = pd.DataFrame(rows)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)
    return buf

# ================= UI =================
st.title("🎯 Aakash EduTranscribe")
uploaded = st.file_uploader("Upload Videos", type=["mp4", "mkv"], accept_multiple_files=True)

if uploaded:
    model = whisper.load_model("base")

    for file in uploaded:
        st.write("###", file.name)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, file.name)

            with open(path, "wb") as f:
                f.write(file.read())

            audio_path = os.path.join(tmp, "audio.wav")
            AudioSegment.from_file(path).export(audio_path, format="wav")

            result = model.transcribe(audio_path)
            segments = result["segments"]

            hits = detect_question_changes(segments)

            rows = []
            for i, h in enumerate(hits):
                rows.append({
                    "Timestamp": h["timestamp"],
                    "Question No.": i + 1,
                    "Transcript": h["transcript"]
                })

            st.dataframe(pd.DataFrame(rows))

            st.download_button(
                "Download Excel",
                make_excel(rows),
                file_name=file.name + ".xlsx"
            )