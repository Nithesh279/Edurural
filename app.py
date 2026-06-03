
from flask import Flask, request, jsonify, send_from_directory, session, redirect, send_file
from flask_cors import CORS
import os
import io
import uuid
import asyncio
import sqlite3
import json
from datetime import datetime
from moviepy.editor import VideoFileClip, AudioFileClip
from faster_whisper import WhisperModel
import wave
import numpy as np
try:
    import librosa
    _HAS_LIBROSA = True
except Exception:
    _HAS_LIBROSA = False
from googletrans import Translator
import edge_tts
from fpdf import FPDF  
from werkzeug.security import generate_password_hash, check_password_hash
import traceback
try:
    from ai_quiz_generator import AIQuizGenerator
except Exception:
    class AIQuizGenerator:
        def generate_quiz(self, video_topic: str = "General", video_description: str | None = None, num_questions: int = 5):
            qs = []
            for i in range(num_questions):
                qs.append({
                    "question": f"Sample question {i+1} about {video_topic}",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_answer": 0,
                    "explanation": "This is a placeholder explanation."
                })
            return qs
import subprocess
from threading import Thread, Lock
import smtplib
import ssl
from email.message import EmailMessage
import secrets
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# === Load environment variables early ===
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k.strip()] = v.strip()

# Initialize API Keys globally
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Load Generative AI Globally to prevent request timeouts on first use
try:
    if GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        print("✅ Google Generative AI configured globally.")
    else:
        import g4f
        print("⚠️ No Gemini API key found, loaded G4F free provider globally.")
except Exception as e:
    print(f"⚠️ Error loading AI providers: {e}")
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")
CORS(app, supports_credentials=True, resources={r"/*": {"origins": ["http://127.0.0.1:5000", "http://localhost:5000", "http://127.0.0.1:5500", "http://localhost:5500", "null"]}})
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
CONTENT_FOLDER = os.path.join(BASE_DIR, "content")
THUMBNAIL_FOLDER = os.path.join(BASE_DIR, "thumbnails")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(CONTENT_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
TEMPLATE_FOLDER = BASE_DIR
MAX_PROCESS_SECONDS = int(os.environ.get("MAX_PROCESS_SECONDS", "180"))  # cap long jobs to N seconds
GENDER_F0_THRESHOLD_HZ = float(os.environ.get("GENDER_F0_THRESHOLD_HZ", "165"))
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER or "")
def send_email(to_email: str, subject: str, html_body: str, text_body: str | None = None) -> bool:
    if not (SMTP_HOST and SMTP_PORT and SMTP_FROM and SMTP_USER and SMTP_PASS):
        print("✉️ SMTP not configured; skipping real email. Configure SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM.")
        return False
    try:
        msg = EmailMessage()
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        if text_body:
            msg.set_content(text_body)
        else:
            msg.set_content("This message requires an HTML-capable client.")
        msg.add_alternative(html_body, subtype="html")
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"✅ Sent email to {to_email}")
        return True
    except Exception as e:
        print(f"❌ SMTP send failed: {e}")
        return False
DB_PATH = os.path.join(BASE_DIR, "app.db")
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            display_name TEXT,
            bio TEXT,
            phone TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            original_filename TEXT,
            translated_filename TEXT NOT NULL,
            language TEXT NOT NULL,
            title TEXT,
            subject_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS teacher_subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(teacher_id) REFERENCES users(id),
            FOREIGN KEY(subject_id) REFERENCES subjects(id),
            UNIQUE(teacher_id, subject_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            parent_id INTEGER,
            text TEXT NOT NULL,
            is_teacher_reply INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(video_id) REFERENCES contents(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS student_subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            enrolled_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            FOREIGN KEY(student_id) REFERENCES users(id),
            FOREIGN KEY(subject_id) REFERENCES subjects(id),
            UNIQUE(student_id, subject_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS video_watch_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            video_id INTEGER NOT NULL,
            subject_id INTEGER,
            watch_duration REAL DEFAULT 0,
            total_duration REAL,
            last_watched_at TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            language_used TEXT,
            FOREIGN KEY(student_id) REFERENCES users(id),
            FOREIGN KEY(video_id) REFERENCES contents(id),
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            questions TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(video_id) REFERENCES contents(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            quiz_id INTEGER NOT NULL,
            answers TEXT NOT NULL,
            score REAL,
            passed INTEGER DEFAULT 0,
            attempted_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES users(id),
            FOREIGN KEY(quiz_id) REFERENCES quizzes(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS teacher_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            questions TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(video_id) REFERENCES contents(id),
            FOREIGN KEY(teacher_id) REFERENCES users(id),
            UNIQUE(video_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS test_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            score REAL NOT NULL,
            passed INTEGER NOT NULL,
            answers TEXT NOT NULL,
            attempted_at TEXT NOT NULL,
            FOREIGN KEY(test_id) REFERENCES teacher_tests(id),
            FOREIGN KEY(student_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            video_id INTEGER,
            role TEXT NOT NULL CHECK(role IN ('user', 'model')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(video_id) REFERENCES contents(id)
        )
        """
    )
    try:
        cols = conn.execute("PRAGMA table_info(users)").fetchall()
        names = {c[1] for c in cols}
        if "role" not in names:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")
        if "email" not in names:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
            conn.execute("UPDATE users SET email = username WHERE email IS NULL OR TRIM(email) = ''")
        if "current_streak" not in names:
            conn.execute("ALTER TABLE users ADD COLUMN current_streak INTEGER DEFAULT 0")
        if "last_watched_date" not in names:
            conn.execute("ALTER TABLE users ADD COLUMN last_watched_date TEXT")

        content_cols = conn.execute("PRAGMA table_info(contents)").fetchall()
        content_names = {c[1] for c in content_cols}
        if "title" not in content_names:
            try:
                conn.execute("ALTER TABLE contents ADD COLUMN title TEXT")
                print("✅ Added 'title' column to contents table")
            except Exception as e:
                print(f"⚠️ Could not add title column: {e}")
        if "subject_id" not in content_names:
            try:
                conn.execute("ALTER TABLE contents ADD COLUMN subject_id INTEGER")
                print("✅ Added 'subject_id' column to contents table")
            except Exception as e:
                print(f"⚠️ Could not add subject_id column: {e}")
        if "transcript" not in content_names:
            try:
                conn.execute("ALTER TABLE contents ADD COLUMN transcript TEXT")
                print("✅ Added 'transcript' column to contents table")
            except Exception as e:
                print(f"⚠️ Could not add transcript column: {e}")
    except Exception as e:
        print(f"⚠️ Migration error: {e}")
        pass
    conn.commit()
    conn.close()
init_db()
print("🔹 Loading Faster-Whisper model (tiny, int8) ...")
fw_model = WhisperModel("tiny", device="cpu", compute_type="int8")
translator = Translator()
quiz_generator = AIQuizGenerator()
SUPPORTED_LANGS = {
    "Hindi": "hi", "Tamil": "ta", "Telugu": "te", "Malayalam": "ml",
    "Kannada": "kn", "Gujarati": "gu", "Marathi": "mr", "Bengali": "bn",
    "Punjabi": "pa", "Urdu": "ur", "English": "en", "Spanish": "es",
    "French": "fr", "German": "de", "Italian": "it", "Japanese": "ja",
    "Korean": "ko", "Chinese (Simplified)": "zh-CN", "Chinese (Traditional)": "zh-TW",
    "Arabic": "ar", "Russian": "ru"
}
FEMALE_VOICE_BY_LANG = {
    "English": "en-US-AriaNeural",
    "Hindi": "hi-IN-AnanyaNeural",
    "Tamil": "ta-IN-PallaviNeural",
    "Telugu": "te-IN-ShrutiNeural",
    "Malayalam": "ml-IN-SobhanaNeural",
    "Kannada": "kn-IN-SapnaNeural",
    "Gujarati": "gu-IN-DhwaniNeural",
    "Marathi": "mr-IN-AarohiNeural",
    "Bengali": "bn-IN-TanishaaNeural",
    "Punjabi": "pa-IN-VaaniNeural",
    "Urdu": "ur-PK-UzmaNeural",
    "Spanish": "es-ES-ElviraNeural",
    "French": "fr-FR-DeniseNeural",
    "German": "de-DE-KatjaNeural",
    "Italian": "it-IT-ElsaNeural",
    "Japanese": "ja-JP-NanamiNeural",
    "Korean": "ko-KR-SunHiNeural",
    "Chinese (Simplified)": "zh-CN-XiaoxiaoNeural",
    "Chinese (Traditional)": "zh-TW-HsiaoChenNeural",
    "Arabic": "ar-SA-ZariyahNeural",
    "Russian": "ru-RU-SvetlanaNeural",
}
MALE_VOICE_BY_LANG = {
    "English": "en-US-GuyNeural",
    "Hindi": "hi-IN-MadhurNeural", 
    "Tamil": "ta-IN-ValluvarNeural",  # Male-sounding voice
    "Telugu": "te-IN-MohanNeural",  # Male-sounding voice
    "Malayalam": "ml-IN-MidhunNeural",  # Male-sounding voice
    "Kannada": "kn-IN-GaganNeural",  # Actual male voice
    "Gujarati": "gu-IN-NiranjanNeural",  # Male-sounding voice
    "Marathi": "mr-IN-ManoharNeural",  # Male-sounding voice
    "Bengali": "bn-IN-BashkarNeural",  
    "Punjabi": "pa-IN-OjasNeural",  
    "Urdu": "ur-PK-AsadNeural",  
    "Spanish": "es-ES-AlvaroNeural",
    "French": "fr-FR-HenriNeural",
    "German": "de-DE-ConradNeural",
    "Italian": "it-IT-DiegoNeural",
    "Japanese": "ja-JP-KeitaNeural",
    "Korean": "ko-KR-InJoonNeural",  
    "Chinese (Simplified)": "zh-CN-YunxiNeural",
    "Chinese (Traditional)": "zh-TW-HsiaoYuNeural",
    "Arabic": "ar-SA-HamedNeural",  
    "Russian": "ru-RU-DmitryNeural",  
}
def pick_voice_for_language(language: str, gender: str) -> str:
    print(f"🎙️ Voice selection: language={language}, gender={gender}")
    # Prefer native Punjabi voices first; fallbacks handled in synthesize_speech_edge
    if language == "Punjabi":
        if gender == "male":
            voice = "pa-IN-AmanNeural"
        else:
            voice = "pa-IN-NeerjaNeural"
        print(f"🎙️ Selected Punjabi voice: {voice}")
        return voice
    if gender == "male":
        voice = MALE_VOICE_BY_LANG.get(language, "en-US-GuyNeural")
        print(f"🎙️ Selected MALE voice for {language}: {voice}")
        return voice
    voice = FEMALE_VOICE_BY_LANG.get(language, "en-US-AriaNeural")
    print(f"🎙️ Selected FEMALE voice for {language}: {voice}")
    return voice
def detect_speaker_gender_from_wav(wav_path: str) -> str:
    """
    Detects gender using Harmonic Product Spectrum (HPS) with numpy.
    Male: ~85-165Hz
    Female: ~165-255Hz
    """
    try:
        # Use simple numpy HPS if librosa is missing or fails
        if not os.path.exists(wav_path):
            return "female"
            
        with wave.open(wav_path, 'rb') as wf:
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            str_data = wf.readframes(nframes)
            
        # Convert to numpy array
        y = np.frombuffer(str_data, dtype=np.int16)
        
        # If stereo, take one channel
        if len(y.shape) > 1 and y.shape[1] > 1:
            y = y[:, 0]
            
        if len(y) == 0:
            return "female"
            
        # Process a meaningful chunk (middle 1-2 seconds) to avoid intro/outro silence
        duration = len(y) / framerate
        if duration > 1.0:
            start_idx = int(len(y) * 0.3)
            end_idx = int(len(y) * 0.7)
            # Take at most 4 seconds for speed
            if (end_idx - start_idx) > framerate * 4:
                end_idx = start_idx + framerate * 4
            y = y[start_idx:end_idx]
            
        # HPS Algorithm
        # Windowing
        window = np.hanning(len(y))
        y = y * window
        
        # FFT
        fft_spec = np.abs(np.fft.rfft(y))
        freqs = np.fft.rfftfreq(len(y), d=1.0/framerate)
        
        # HPS: Downsample and multiply
        hps_spec = np.copy(fft_spec)
        for h in range(2, 6): # 5 harmonics
            decimated = fft_spec[::h]
            # Truncate to match size
            hps_spec = hps_spec[:len(decimated)] * decimated
            
        # Find peak in human voice range (85Hz - 255Hz)
        valid_idxs = np.where((freqs[:len(hps_spec)] >= 85) & (freqs[:len(hps_spec)] <= 255))[0]
        
        if len(valid_idxs) == 0:
            return "female" # Fallback
            
        peak_idx = valid_idxs[np.argmax(hps_spec[valid_idxs])]
        f0 = freqs[peak_idx]
        
        # Calculate energy/voice strength (simple heuristic)
        # If signal is too quiet, default to female (safer for educational content?)
        # signal_energy = np.sum(y**2) / len(y)
        
        print(f"🎙️ Detected Pitch: {f0:.1f} Hz")
        
        return "male" if f0 < GENDER_F0_THRESHOLD_HZ else "female"

    except Exception as e:
        print(f"⚠️ Gender detection failed (numpy method): {e}")
        return "female"
async def synthesize_speech_edge(text: str, voice: str, file_path: str, rate: str = "+0%", pitch: str = "+0Hz") -> None:
    """Synthesizes speech using Edge TTS and saves it to a file."""
    if not text or not text.strip():
        raise Exception("Text is empty or contains only whitespace")
    MAX_TEXT_LENGTH = 4000
    if len(text) > MAX_TEXT_LENGTH:
        print(f"⚠️ Text is too long ({len(text)} chars), truncating to {MAX_TEXT_LENGTH} chars")
        text = text[:MAX_TEXT_LENGTH] + "..."
    cleaned_text = text.strip()
    if not cleaned_text:
        raise Exception("Text is empty after stripping whitespace")
    print(f"🗣️ Synthesizing text (length: {len(cleaned_text)} chars) with voice '{voice}' to {file_path}")
    print(f"   Text preview: {cleaned_text[:100]}..." if len(cleaned_text) > 100 else f"   Text: {cleaned_text}")
    arabic_fallbacks = {
        "ar-SA-ZariyahNeural": ["ar-EG-SalmaNeural", "ar-AE-FatimaNeural", "ar-LB-LaylaNeural"],
        "ar-SA-HamedNeural": ["ar-EG-ShakirNeural", "ar-AE-HamdanNeural", "ar-LB-RamiNeural"],
    }
    # General fallbacks for languages that can intermittently fail (e.g., Punjabi)
    extra_fallbacks = {
        # Punjabi voices + Hindi + English as last resort
        "pa-IN-NeerjaNeural": ["pa-IN-AmanNeural", "pa-IN-VaaniNeural", "pa-IN-OjasNeural", "hi-IN-AnanyaNeural", "hi-IN-MadhurNeural", "en-US-AriaNeural"],
        "pa-IN-VaaniNeural": ["pa-IN-NeerjaNeural", "pa-IN-AmanNeural", "pa-IN-OjasNeural", "hi-IN-AnanyaNeural", "hi-IN-MadhurNeural", "en-US-AriaNeural"],
        "pa-IN-OjasNeural": ["pa-IN-AmanNeural", "pa-IN-NeerjaNeural", "pa-IN-VaaniNeural", "hi-IN-AnanyaNeural", "hi-IN-MadhurNeural", "en-US-AriaNeural"],
        "pa-IN-AmanNeural": ["pa-IN-NeerjaNeural", "pa-IN-VaaniNeural", "pa-IN-OjasNeural", "hi-IN-MadhurNeural", "hi-IN-AnanyaNeural", "en-US-AriaNeural"],
    }
    voices_to_try = [voice]
    if voice in arabic_fallbacks:
        voices_to_try.extend(arabic_fallbacks[voice])
    if voice in extra_fallbacks:
        voices_to_try.extend(extra_fallbacks[voice])
    last_error = None
    for attempt_voice in voices_to_try:
        try:
            print(f"   Attempting voice: {attempt_voice}")
            communicate = edge_tts.Communicate(text=cleaned_text, voice=attempt_voice, rate=rate, pitch=pitch)
            await communicate.save(file_path)
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                if file_size > 0:
                    if attempt_voice != voice:
                        print(f"✅ Speech synthesized successfully with fallback voice {attempt_voice} ({file_size} bytes)")
                    else:
                        print(f"✅ Speech synthesized successfully ({file_size} bytes)")
                    return
                else:
                    raise Exception(f"Generated file is empty (0 bytes)")
            else:
                raise Exception("File was not created")
        except Exception as e:
            last_error = e
            error_msg = str(e)
            print(f"   ⚠️ Voice {attempt_voice} failed: {error_msg[:100]}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            if "NoAudioReceived" in error_msg or "No audio" in error_msg:
                if attempt_voice != voices_to_try[-1]:
                    print(f"   🔄 Trying next fallback voice...")
                    continue
            else:
                if attempt_voice != voices_to_try[-1]:
                    continue
    if voice.startswith("ar-"):
        print(f"❌ All Arabic voice attempts failed. Falling back to English voice...")
        try:
            fallback_voice = "en-US-AriaNeural"
            print(f"🔄 Using English fallback voice: {fallback_voice}")
            print(f"   Text length: {len(cleaned_text)} characters")
            print(f"   Text preview: {cleaned_text[:100]}...")
            try:
                communicate = edge_tts.Communicate(text=cleaned_text, voice=fallback_voice, rate=rate, pitch=pitch)
                await communicate.save(file_path)
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    if file_size > 0:
                        print(f"✅ Speech synthesized with English fallback voice {fallback_voice} ({file_size} bytes)")
                        print(f"   Note: Using English voice for Arabic text due to Arabic voice limitations")
                        return
            except Exception as e_arabic_text:
                print(f"   ⚠️ English voice failed with Arabic text: {e_arabic_text}")
                fallback_text = f"This is a translation to Arabic. The original text has been translated."
                print(f"   Trying with English fallback text...")
                communicate = edge_tts.Communicate(text=fallback_text, voice=fallback_voice, rate=rate, pitch=pitch)
                await communicate.save(file_path)
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    if file_size > 0:
                        print(f"✅ Speech synthesized with English fallback ({file_size} bytes)")
                        print(f"   Note: Arabic TTS is currently unavailable. Using English placeholder.")
                        return
                raise Exception(f"English fallback failed: {e_arabic_text}")
        except Exception as e2:
            print(f"❌ English fallback also failed: {e2}")
            last_error = e2
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
    error_type = type(last_error).__name__ if last_error else "Unknown"
    error_msg = str(last_error) if last_error else "Unknown error"
    if "NoAudioReceived" in error_msg or "No audio" in error_msg:
        guidance = "Edge TTS service may be unavailable. Please check:\n" \
                   "1. Your internet connection\n" \
                   "2. Firewall/proxy settings blocking Edge TTS\n" \
                   "3. Try again in a few minutes (service may be temporarily down)\n" \
                   "4. Update edge-tts: pip install --upgrade edge-tts"
        error_details = f"TTS synthesis failed: {error_msg}. {guidance}"
    else:
        error_details = f"TTS synthesis failed for all voices. Text length: {len(cleaned_text)}, Error: {error_msg}"
    print(f"❌ {error_details}")
    raise Exception(error_details)
def ffprobe_duration_seconds(path: str) -> float:
    try:
        out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path])
        return float(out.decode().strip())
    except Exception:
        try:
            clip = VideoFileClip(path)
            d = float(clip.duration or 0)
            clip.close()
            return d
        except Exception:
            return 0.0
def transcribe_with_progress(audio_or_video_path: str, job_id: str | None = None) -> str:
    duration = ffprobe_duration_seconds(audio_or_video_path)
    collected = []
    segments, _info = fw_model.transcribe(
        audio_or_video_path,
        vad_filter=True,
        beam_size=1,
        no_speech_threshold=0.6,
        condition_on_previous_text=False,
    )
    last_pct = 10
    for seg in segments:
        collected.append(seg.text)
        if job_id and duration > 0 and seg.end is not None:
            pct = 10 + int(50 * min(max(seg.end / duration, 0.0), 1.0))
            if pct > last_pct:
                set_job(job_id, progress=pct, message="Transcribing")
                last_pct = pct
    return " ".join(collected).strip()
JOBS = {}
JOBS_LOCK = Lock()
def set_job(job_id: str, **kwargs):
    with JOBS_LOCK:
        job = JOBS.get(job_id, {})
        job.update(kwargs)
        JOBS[job_id] = job
def run_translation_job(job_id: str, source: str, source_filename: str, language: str, user_id: int, voice_gender: str | None = None):
    try:
        set_job(job_id, status="running", progress=1, message="Queuing", url=None)
        base_folder = CONTENT_FOLDER if source == "content" else UPLOAD_FOLDER
        video_path = os.path.join(base_folder, source_filename)
        if not os.path.exists(video_path):
            set_job(job_id, status="error", progress=100, message="File not found")
            return
        set_job(job_id, progress=8, message="Preparing audio")
        fast_wav = os.path.join(OUTPUT_FOLDER, f"asr_{uuid.uuid4()}.wav")
        full_duration = ffprobe_duration_seconds(video_path)
        ff_args = [
            "ffmpeg", "-y", "-i", video_path,
            "-ac", "1", "-ar", "16000",
        ]
        if full_duration and full_duration > MAX_PROCESS_SECONDS:
            set_job(job_id, progress=9, message=f"Capping to first {MAX_PROCESS_SECONDS}s")
            ff_args += ["-t", str(MAX_PROCESS_SECONDS)]
        ff_args.append(fast_wav)
        subprocess.run(ff_args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        set_job(job_id, progress=10, message="Transcribing")
        text = transcribe_with_progress(fast_wav, job_id)
        if not text:
            set_job(job_id, status="error", progress=100, message="No speech detected")
            return
        try:
            os.remove(fast_wav)
        except Exception:
            pass
        if voice_gender in ("male", "female"):
            gender = voice_gender
            print(f"🎙️ Using OVERRIDE gender: {gender}")
        else:
            gender = detect_speaker_gender_from_wav(fast_wav)
            print(f"🎙️ DETECTED gender: {gender}")
        set_job(job_id, progress=40, message="Translating")
        try:
            translated_text = translator.translate(text, dest=SUPPORTED_LANGS[language]).text
        except Exception as e:
            print(f"❌ Translation failed for {language} ({SUPPORTED_LANGS[language]}): {e}")
            lang_code = SUPPORTED_LANGS[language]
            if lang_code == "zh-CN":
                try:
                    translated_text = translator.translate(text, dest="zh").text
                except:
                    raise Exception(f"Translation failed for {language}. Please try another language.")
            elif lang_code == "zh-TW":
                try:
                    translated_text = translator.translate(text, dest="zh-tw").text
                except:
                    raise Exception(f"Translation failed for {language}. Please try another language.")
            else:
                raise Exception(f"Translation failed for {language}: {e}")
        if not translated_text or not translated_text.strip():
            set_job(job_id, status="error", progress=100, message="Translation produced empty text")
            return
        print(f"📝 Translated text length: {len(translated_text)} characters")
        print(f"📝 Translated text preview: {translated_text[:200]}...")
        set_job(job_id, progress=65, message="Generating voice")
        selected_voice = pick_voice_for_language(language, gender)
        audio_filename = f"{uuid.uuid4()}.mp3"
        audio_path = os.path.join(OUTPUT_FOLDER, audio_filename)
        try:
            asyncio.run(synthesize_speech_edge(translated_text.strip(), selected_voice, audio_path, rate="-5%", pitch="-1Hz"))
        except Exception as e:
            error_msg = str(e)
            print(f"❌ TTS failed: {error_msg}")
            if "empty" in error_msg.lower():
                set_job(job_id, status="error", progress=100, message="Translation produced empty text")
            elif "No audio" in error_msg or "NoAudioReceived" in error_msg or "Edge TTS service" in error_msg:
                short_msg = error_msg.split('.')[0] if '.' in error_msg else error_msg[:80]
                set_job(job_id, status="error", progress=100, message=f"Voice synthesis failed: {short_msg}. Please check your internet connection and try again.")
            else:
                set_job(job_id, status="error", progress=100, message=f"TTS failed: {error_msg[:100]}")
            return
        set_job(job_id, progress=85, message="Merging audio/video")
        translated_filename = f"translated_{uuid.uuid4()}.mp4"
        translated_path = os.path.join(OUTPUT_FOLDER, translated_filename)
        pad_dur = full_duration + 2 if full_duration and full_duration > 0 else 600
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", f"[1:a]apad=pad_dur={pad_dur}[aout]",
            "-map", "0:v:0", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac",
            "-shortest",
            translated_path
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO contents (user_id, original_filename, translated_filename, language, created_at, transcript) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, source_filename, translated_filename, language, datetime.utcnow().isoformat(), text),
        )
        conn.commit(); conn.close()
        set_job(job_id, status="done", progress=100, message="Video transfered successfully", url=f"http://127.0.0.1:5000/outputs/{translated_filename}")
    except Exception as e:
        set_job(job_id, status="error", progress=100, message=str(e))
@app.route("/")
def root_redirect():
    if "user_id" in session:
        return redirect("/index.html")
    return redirect("/login.html")
@app.route("/index.html")
def serve_index_page():
    return send_from_directory(TEMPLATE_FOLDER, "index.html")
@app.route("/login.html")
def serve_login_page():
    return send_from_directory(TEMPLATE_FOLDER, "login.html")

@app.route("/courses.html")
def serve_courses_page():
    return send_from_directory(TEMPLATE_FOLDER, "courses.html")
@app.route("/play.html")
def serve_play_page():
    return send_from_directory(TEMPLATE_FOLDER, "play.html")
@app.route("/download_notes/<int:video_id>")
def download_notes(video_id):
    if "user_id" not in session:
        return redirect("/login.html")
    
    target_lang = request.args.get("lang")
    
    conn = sqlite3.connect(DB_PATH)
    # Get video details
    row = conn.execute("SELECT title, transcript, original_filename, created_at, language FROM contents WHERE id=?", (video_id,)).fetchone()
    conn.close()
    
    if not row:
        return "Video not found", 404
        
    title, transcript, filename, created_at, video_lang = row
    title = title or filename or "Untitled Video"
    transcript = transcript or "No transcript available."
    
    if target_lang and target_lang.lower() != "english":
        try:
            from googletrans import Translator
            _translator = Translator()
            if target_lang in SUPPORTED_LANGS:
                dest_code = SUPPORTED_LANGS[target_lang]
                translated_obj = _translator.translate(transcript, dest=dest_code)
                if translated_obj and translated_obj.text:
                    transcript = translated_obj.text
                    title = f"{title} ({target_lang})"
            
            # For non-English target languages, FPDF fonts may not support Unicode characters.
            # Return a UTF-8 encoded plain text file instead.
            txt_output = io.BytesIO(transcript.encode('utf-8'))
            return send_file(
                txt_output,
                as_attachment=True,
                download_name=f"Notes_{title}.txt",
                mimetype="text/plain"
            )
        except Exception as e:
            print("Notes Translation error:", e)
    
    # Create PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Title
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Study Notes: {title}", ln=True, align='C')
    pdf.ln(5)
    
    # Metadata
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='C')
    pdf.ln(10)
    
    # Transcript Body
    pdf.set_font("Arial", "", 12)
    # Replace incompatible characters if any (basic sanitization for standard font)
    transcript_safe = transcript.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, transcript_safe)
    
    # Output
    try:
        pdf_output = io.BytesIO()
        pdf_bytes = pdf.output(dest='S').encode('latin-1') # specific to py-fpdf / fpdf logic, output() returns string in some versions, bytes in others.
        # Actually in modern fpdf2 it returns bytes, but let's be safe. 
        # Wait, fpdf 1.7.2 (common) returns string. 
        # Let's use the standard way: output(dest='S') returns string. We encode it to bytes.
        
        pdf_output.write(pdf_bytes)
        pdf_output.seek(0)
        
        return send_file(
            pdf_output,
            as_attachment=True,
            download_name=f"Notes_{title}.pdf",
            mimetype="application/pdf"
        )
    except Exception as e:
        # Fallback for newer fpdf2 versions which might return bytes naturally or have different method
        # If the above fails, prompt user it might be fpdf2
        print(f"PDF Generation Error: {e}")
        return f"Error generating PDF: {e}", 500

@app.route("/reset.html")
def serve_reset_page():
    return send_from_directory(TEMPLATE_FOLDER, "reset.html")
@app.route("/analytics.html")
def serve_analytics_page():
    return send_from_directory(TEMPLATE_FOLDER, "analytics.html")
@app.route("/static/<path:filename>")
def serve_static_file(filename):
    return send_from_directory(os.path.join(TEMPLATE_FOLDER, "static"), filename)
@app.route("/password/forgot", methods=["POST"])
def password_forgot():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "email is required"}), 400
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"message": "If that email exists, a reset link was sent.", "reset_url": None})
    user_id = row[0]
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    conn.execute(
        "INSERT INTO password_resets (user_id, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (user_id, token, expires_at, datetime.utcnow().isoformat()),
    )
    conn.commit(); conn.close()
    reset_link = f"http://127.0.0.1:5000/reset.html?token={token}"
    subject = "Reset your EDURURAL password"
    html = f"""
    <div style='font-family:Segoe UI,Arial,sans-serif'>
      <h2>Password reset</h2>
      <p>We received a request to reset your password. This link expires in 1 hour.</p>
      <p><a href='{reset_link}' style='background:#0ea5e9;color:#fff;padding:10px 14px;border-radius:8px;text-decoration:none;'>Reset password</a></p>
      <p>Or copy and paste this URL: <br>{reset_link}</p>
      <hr><small>If you didn't request this, you can ignore this email.</small>
    </div>
    """
    text = f"Reset your password: {reset_link}\nThis link expires in 1 hour."
    sent = send_email(email, subject, html, text)
    print(f"🔐 Password reset link for {email}: {reset_link} (email_sent={sent})")
    return jsonify({"message": "If that email exists, a reset link was sent.", "reset_url": reset_link})
@app.route("/password/reset", methods=["POST"])
def password_reset():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    new_password = data.get("password") or ""
    if not token or not new_password:
        return jsonify({"error": "token and password are required"}), 400
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT pr.id, pr.user_id, pr.expires_at, pr.used FROM password_resets pr WHERE pr.token=?",
        (token,),
    ).fetchone()
    if not row:
        conn.close(); return jsonify({"error": "invalid or expired token"}), 400
    pr_id, user_id, expires_at, used = row
    if used:
        conn.close(); return jsonify({"error": "token already used"}), 400
    try:
        if datetime.fromisoformat(expires_at) < datetime.utcnow():
            conn.close(); return jsonify({"error": "token expired"}), 400
    except Exception:
        conn.close(); return jsonify({"error": "token expired"}), 400
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_password), user_id))
    conn.execute("UPDATE password_resets SET used=1 WHERE id=?", (pr_id,))
    conn.commit(); conn.close()
    return jsonify({"message": "password updated"})
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "student").strip().lower()
    if role not in ("teacher", "student"):
        return jsonify({"error": "role must be 'teacher' or 'student'"}), 400
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (email, email, generate_password_hash(password), role, datetime.utcnow().isoformat()),
        )
        conn.commit()
        row = conn.execute("SELECT id, role, email FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        user_id, role_db, email_db = row[0], row[1], row[2]
        session["user_id"] = user_id
        session["username"] = email_db
        session["email"] = email_db
        session["role"] = role_db
        return jsonify({"message": "registered", "user": {"id": user_id, "email": email_db, "role": role_db}})
    except sqlite3.IntegrityError:
        return jsonify({"error": "email already exists"}), 409
@app.route("/login", methods=["POST"]) 
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT id, password_hash, role, email FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
    except Exception as e:
        conn.close()
        return jsonify({"error": "Database error: " + str(e)}), 500
    conn.close()
    
    if row and check_password_hash(row[1], password):
        session["user_id"] = row[0]
        session["email"] = row[3]
        session["role"] = row[2]
        return jsonify({"message": "logged_in", "user": {"id": row[0], "email": row[3], "role": row[2]}})
    return jsonify({"error": "invalid credentials"}), 401
@app.route("/update-profile", methods=["POST"])
def update_profile():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    new_password = data.get("password")
    
    conn = get_db_connection()
    try:
        if new_password:
            hashed = generate_password_hash(new_password)
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, session["user_id"]))
            conn.commit()
            return jsonify({"message": "Password updated successfully"})
        
        return jsonify({"message": "No changes made"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route("/logout", methods=["POST"])                                                                                                                         
def logout():
    session.clear()
    return jsonify({"message": "logged_out"})
@app.route("/me")
def me():
    if "user_id" not in session:
        return jsonify({"user": None})
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT current_streak, last_watched_date FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    
    streak = 0
    if row:
        current_streak = row[0] or 0
        last_date = row[1]
        
        today_str = datetime.utcnow().date().isoformat()
        yesterday_str = (datetime.utcnow().date() - timedelta(days=1)).isoformat()
        
        # Streak is active if they watched today or yesterday
        if last_date == today_str or last_date == yesterday_str:
            streak = current_streak
        else:
            streak = 0
            # Need to update DB to reset broken streak
            if current_streak > 0:
                conn.execute("UPDATE users SET current_streak = 0 WHERE id = ?", (session["user_id"],))
                conn.commit()
                
    conn.close()
    return jsonify({"user": {"id": session["user_id"], "email": session.get("email"), "role": session.get("role", "student"), "streak": streak}})
def require_login():
    if "user_id" not in session:
        return False, jsonify({"error": "authentication required"}), 401
    return True, None, None
def require_teacher():
    ok, resp, code = require_login()
    if not ok:
        return ok, resp, code
    if session.get("role") != "teacher":
        return False, jsonify({"error": "teacher role required"}), 403
    return True, None, None
@app.route("/upload", methods=["POST"])
def upload_video():
    try:
        ok, resp, code = require_login()
        if not ok:
            return resp, code
        if "video" not in request.files:
            return jsonify({"error": "No video file uploaded"}), 400
        video = request.files["video"]
        language = request.form.get("language", "Hindi")
        voice_gender = request.form.get("voice_gender")  
        if language not in SUPPORTED_LANGS:
            return jsonify({"error": f"Unsupported language: {language}"}), 400
        video_filename = f"{uuid.uuid4()}.mp4"
        video_path = os.path.join(UPLOAD_FOLDER, video_filename)
        video.save(video_path)
        print(f"🎥 Uploaded: {video_path}")
        print("📝 Transcribing audio...")
        text = transcribe_with_progress(video_path, None)
        if not text:
            return jsonify({"error": "No speech detected in video"}), 400
        print(f"🌐 Translating to {language}...")
        try:
            translated_text = translator.translate(text, dest=SUPPORTED_LANGS[language]).text
        except Exception as e:
            print(f"❌ Translation failed for {language} ({SUPPORTED_LANGS[language]}): {e}")
            lang_code = SUPPORTED_LANGS[language]
            if lang_code == "zh-CN":
                try:
                    translated_text = translator.translate(text, dest="zh").text
                except:
                    raise Exception(f"Translation failed for {language}. Please try another language.")
            elif lang_code == "zh-TW":
                try:
                    translated_text = translator.translate(text, dest="zh-tw").text
                except:
                    raise Exception(f"Translation failed for {language}. Please try another language.")
            else:
                raise Exception(f"Translation failed for {language}: {e}")
        print("🎤 Generating fluent audio using Edge Neural TTS...")
        try:
            fast_wav = os.path.join(OUTPUT_FOLDER, f"asr_{uuid.uuid4()}.wav")
            full_duration = ffprobe_duration_seconds(video_path)
            ff_args = ["ffmpeg", "-y", "-i", video_path, "-ac", "1", "-ar", "16000"]
            if full_duration and full_duration > MAX_PROCESS_SECONDS:
                ff_args += ["-t", str(MAX_PROCESS_SECONDS)]
            ff_args.append(fast_wav)
            subprocess.run(ff_args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            gender = voice_gender if voice_gender in ("male", "female") else detect_speaker_gender_from_wav(fast_wav)
            try:
                os.remove(fast_wav)
            except Exception:
                pass
        except Exception:
            gender = "female"
        selected_voice = pick_voice_for_language(language, gender)
        audio_filename = f"{uuid.uuid4()}.mp3"
        audio_path = os.path.join(OUTPUT_FOLDER, audio_filename)
        asyncio.run(synthesize_speech_edge(translated_text, selected_voice, audio_path, rate="-5%", pitch="-1Hz"))
        print(f"✅ Audio generated: {audio_path}")
        print("🎬 Merging translated audio with video (ffmpeg mux)...")
        translated_filename = f"translated_{uuid.uuid4()}.mp4"
        translated_path = os.path.join(OUTPUT_FOLDER, translated_filename)
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "aac",
                "-shortest",
                translated_path
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)
            if os.path.exists(video_path):
                os.remove(video_path)
        print(f"✅ Translation completed successfully: {translated_filename}")
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO contents (user_id, original_filename, translated_filename, language, created_at, transcript) VALUES (?, ?, ?, ?, ?, ?)",
            (
                session["user_id"],
                video_filename,
                translated_filename,
                language,
                datetime.utcnow().isoformat(),
                text,
            ),
        )
        conn.commit()
        conn.close()
        return jsonify({
            "message": "✅ Video translated successfully!",
            "video_url": f"http://127.0.0.1:5000/outputs/{translated_filename}"
        })
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": str(e)}), 500
@app.route("/outputs/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)
@app.route("/content/<path:filename>")
def serve_content(filename):
    return send_from_directory(CONTENT_FOLDER, filename)
@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)
@app.route("/thumbnails/<path:filename>")
def serve_thumbnail(filename):
    return send_from_directory(THUMBNAIL_FOLDER, filename)
def ensure_thumbnail(video_path: str, thumb_key: str) -> str:
    thumb_filename = f"{thumb_key}.jpg"
    thumb_path = os.path.join(THUMBNAIL_FOLDER, thumb_filename)
    if os.path.exists(thumb_path):
        return thumb_filename
    try:
        clip = VideoFileClip(video_path)
        t = 1.0
        if clip.duration and clip.duration < 1.0:
            t = max(0.0, clip.duration / 2)
        clip.save_frame(thumb_path, t=t)
        clip.close()
        return thumb_filename
    except Exception:
        return thumb_filename
@app.route("/content", methods=["GET"])
def list_content():
    try:
        ok, resp, code = require_login()
        if not ok:
            return resp, code
        subject_id = request.args.get("subject_id", type=int)
        conn = sqlite3.connect(DB_PATH)
        role = session.get("role")
        user_id = session.get("user_id")
        if role == "teacher":
            if subject_id:
                rows = conn.execute(
                    """SELECT c.id, c.title, c.translated_filename, c.subject_id, c.created_at
                       FROM contents c
                       JOIN subjects s ON c.subject_id = s.id
                       LEFT JOIN teacher_subjects ts ON ts.subject_id = s.id
                       WHERE c.subject_id = ?
                         AND c.translated_filename IS NOT NULL
                         AND (s.created_by = ? OR ts.teacher_id = ?)
                       ORDER BY c.created_at DESC""",
                    (subject_id, user_id, user_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT c.id, c.title, c.translated_filename, c.subject_id, c.created_at
                       FROM contents c
                       JOIN subjects s ON c.subject_id = s.id
                       LEFT JOIN teacher_subjects ts ON ts.subject_id = s.id
                       WHERE c.translated_filename IS NOT NULL
                         AND (s.created_by = ? OR ts.teacher_id = ?)
                       ORDER BY c.created_at DESC""",
                    (user_id, user_id),
                ).fetchall()
        elif role == "student":
            if subject_id:
                rows = conn.execute(
                    """SELECT c.id, c.title, c.translated_filename, c.subject_id, c.created_at
                       FROM contents c
                       JOIN student_subjects ss
                         ON ss.subject_id = c.subject_id
                        AND ss.student_id = ?
                        AND ss.status = 'active'
                       WHERE c.subject_id = ?
                         AND c.translated_filename IS NOT NULL
                       ORDER BY c.created_at DESC""",
                    (user_id, subject_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT c.id, c.title, c.translated_filename, c.subject_id, c.created_at
                       FROM contents c
                       JOIN student_subjects ss
                         ON ss.subject_id = c.subject_id
                        AND ss.student_id = ?
                        AND ss.status = 'active'
                       WHERE c.translated_filename IS NOT NULL
                       ORDER BY c.created_at DESC""",
                    (user_id,),
                ).fetchall()
        else:
            if subject_id:
                rows = conn.execute(
                    """SELECT c.id, c.title, c.translated_filename, c.subject_id, c.created_at
                       FROM contents c
                       WHERE c.subject_id = ? AND c.translated_filename IS NOT NULL
                       ORDER BY c.created_at DESC""",
                    (subject_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT c.id, c.title, c.translated_filename, c.subject_id, c.created_at
                       FROM contents c
                       WHERE c.translated_filename IS NOT NULL
                       ORDER BY c.created_at DESC""",
                ).fetchall()
        conn.close()
        items = []
        for row in rows:
            video_id, title, filename, subj_id, created_at = row
            if not filename:
                continue
            video_path = os.path.join(CONTENT_FOLDER, filename)
            if not os.path.exists(video_path):
                continue
            thumb_key = f"content_{os.path.splitext(filename)[0]}"
            thumb_file = ensure_thumbnail(video_path, thumb_key)
            items.append({
                "id": video_id,
                "filename": filename,
                "title": title or filename,
                "subject_id": subj_id,
                "source": "content",
                "url": f"http://127.0.0.1:5000/content/{filename}",
                "thumb_url": f"http://127.0.0.1:5000/thumbnails/{thumb_file}",
                "created_at": created_at
            })
        
        print(f"📚 Library: content={len(items)}")
        return jsonify({"items": items})
    except Exception as e:
        print(f"❌ Error listing content: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"items": [], "error": str(e)})
@app.route("/history")
def history():
    ok, resp, code = require_login()
    if not ok:
        return resp, code
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, original_filename, translated_filename, language, created_at FROM contents WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    items = [
        {
            "id": r[0],
            "original_filename": r[1],
            "translated_filename": r[2],
            "language": r[3],
            "created_at": r[4],
            "video_url": f"http://127.0.0.1:5000/outputs/{r[2]}",
        }
        for r in rows
    ]
    return jsonify({"items": items})
@app.route("/translate", methods=["POST"])
def translate_existing():
    try:
        ok, resp, code = require_login()
        if not ok:
            return resp, code
        data = request.get_json(silent=True) or {}
        source_filename = (data.get("filename") or "").strip()
        source = (data.get("source") or "content").strip()
        language = data.get("language") or "Hindi"
        voice_gender = data.get("voice_gender")
        if not source_filename:
            return jsonify({"error": "filename required"}), 400
        if language not in SUPPORTED_LANGS:
            return jsonify({"error": f"Unsupported language: {language}"}), 400
        job_id = str(uuid.uuid4())
        set_job(job_id, status="queued", progress=1, message="Queued", url=None)
        t = Thread(target=run_translation_job, args=(job_id, source, source_filename, language, session["user_id"], voice_gender), daemon=True)
        t.start()
        return jsonify({"job_id": job_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/translate/status/<job_id>")
def translate_status(job_id: str):
    with JOBS_LOCK:
        info = JOBS.get(job_id) or {"status": "unknown", "progress": 0}
    return jsonify(info)
@app.route("/upload-content", methods=["POST"]) 
def upload_content():
    try:
        ok, resp, code = require_teacher()
        if not ok:
            return resp, code
        if "video" not in request.files:
            return jsonify({"error": "No video file uploaded"}), 400
        video = request.files["video"]
        title = request.form.get("title", "").strip()
        subject_id = request.form.get("subject_id")
        if not title:
            return jsonify({"error": "Title is required"}), 400
        original_filename = video.filename
        if not original_filename:
            return jsonify({"error": "Invalid filename"}), 400
        base_title = "".join(ch for ch in title if ch.isalnum() or ch in ("-", "_", " ")).strip().replace(" ", "_")
        ext = os.path.splitext(original_filename)[1] or ".mp4"
        safe_filename = f"{base_title}{ext}"
        video_path = os.path.join(CONTENT_FOLDER, safe_filename)
        video.save(video_path)
        print(f"📚 Content uploaded: {video_path}")
        print("📝 Transcribing audio for new content...")
        transcript_text = transcribe_with_progress(video_path, None) or ""
        try:
            conn = sqlite3.connect(DB_PATH)
            if subject_id:
                conn.execute(
                    "INSERT INTO contents (user_id, original_filename, translated_filename, language, title, subject_id, created_at, transcript) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (session["user_id"], original_filename, safe_filename, "English", title, int(subject_id), datetime.utcnow().isoformat(), transcript_text)
                )
            else:
                conn.execute(
                    "INSERT INTO contents (user_id, original_filename, translated_filename, language, title, created_at, transcript) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (session["user_id"], original_filename, safe_filename, "English", title, datetime.utcnow().isoformat(), transcript_text)
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Could not save content metadata: {e}")
        return jsonify({
            "message": "✅ Educational content uploaded successfully!",
            "filename": safe_filename
        })
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": str(e)}), 500
@app.route("/subjects", methods=["GET"])
def list_subjects():
    ok, resp, code = require_login()
    if not ok:
        return resp, code
    try:
        conn = sqlite3.connect(DB_PATH)
        if session.get("role") == "teacher":
            rows = conn.execute(
                """SELECT s.id, s.name, s.description, s.created_at, 
                   (SELECT COUNT(DISTINCT ss2.student_id) FROM student_subjects ss2 WHERE ss2.subject_id = s.id AND ss2.status = 'active') as student_count,
                   (SELECT COUNT(DISTINCT c2.id) FROM contents c2 WHERE c2.subject_id = s.id) as video_count
                   FROM subjects s
                   WHERE s.created_by = ? OR EXISTS(SELECT 1 FROM teacher_subjects ts WHERE ts.subject_id = s.id AND ts.teacher_id = ?)
                   ORDER BY s.created_at DESC""",
                (session["user_id"], session["user_id"])
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT s.id, s.name, s.description, s.created_at,
                   COUNT(DISTINCT ss.student_id) as student_count,
                   COUNT(DISTINCT c.id) as video_count,
                   CASE WHEN EXISTS(SELECT 1 FROM student_subjects WHERE student_id = ? AND subject_id = s.id) THEN 1 ELSE 0 END as enrolled
                   FROM subjects s
                   LEFT JOIN student_subjects ss ON s.id = ss.subject_id
                   LEFT JOIN contents c ON s.id = c.subject_id
                   GROUP BY s.id
                   ORDER BY s.created_at DESC""",
                (session["user_id"],)
            ).fetchall()
        conn.close()
        subjects = []
        for row in rows:
            if session.get("role") == "teacher":
                subjects.append({
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "created_at": row[3],
                    "student_count": row[4] or 0,
                    "video_count": row[5] or 0
                })
            else:
                subjects.append({
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "created_at": row[3],
                    "student_count": row[4] or 0,
                    "video_count": row[5] or 0,
                    "enrolled": bool(row[6])
                })
        return jsonify({"subjects": subjects})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/subjects", methods=["POST"])
def create_subject():
    ok, resp, code = require_teacher()
    if not ok:
        return resp, code
    try:
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        if not name:
            return jsonify({"error": "Subject name is required"}), 400
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute(
            "INSERT INTO subjects (name, description, created_by, created_at) VALUES (?, ?, ?, ?)",
            (name, description, session["user_id"], datetime.utcnow().isoformat())
        )
        subject_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO teacher_subjects (teacher_id, subject_id, created_at) VALUES (?, ?, ?)",
            (session["user_id"], subject_id, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "Subject created successfully", "subject_id": subject_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/subjects/<int:subject_id>", methods=["GET"])
def get_subject(subject_id):
    ok, resp, code = require_login()
    if not ok:
        return resp, code
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT id, name, description, created_by, created_at FROM subjects WHERE id = ?",
            (subject_id,)
        ).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "Subject not found"}), 404
        videos = conn.execute(
            "SELECT id, title, translated_filename, language, created_at FROM contents WHERE subject_id = ? ORDER BY created_at DESC",
            (subject_id,)
        ).fetchall()
        conn.close()
        return jsonify({
            "subject": {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "created_by": row[3],
                "created_at": row[4]
            },
            "videos": [
                {
                    "id": v[0],
                    "title": v[1],
                    "filename": v[2],
                    "language": v[3],
                    "created_at": v[4],
                    "url": f"http://127.0.0.1:5000/content/{v[2]}"
                }
                for v in videos
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/subjects/<int:subject_id>", methods=["DELETE"])
def delete_subject(subject_id):
    """
    Allows a teacher to delete a subject they own or are assigned to.
    Deletes associated enrollments, teacher assignments, and content metadata.
    """
    ok, resp, code = require_teacher()
    if not ok:
        return resp, code
    try:
        conn = sqlite3.connect(DB_PATH)
        owner = conn.execute(
            "SELECT id, name FROM subjects WHERE id = ? AND (created_by = ? OR EXISTS(SELECT 1 FROM teacher_subjects ts WHERE ts.subject_id = subjects.id AND ts.teacher_id = ?))",
            (subject_id, session["user_id"], session["user_id"])
        ).fetchone()
        if not owner:
            conn.close()
            return jsonify({"error": "Not authorized to delete this subject"}), 403
        content_files = conn.execute(
            "SELECT translated_filename FROM contents WHERE subject_id = ?",
            (subject_id,)
        ).fetchall()
        conn.execute("DELETE FROM student_subjects WHERE subject_id = ?", (subject_id,))
        conn.execute("DELETE FROM teacher_subjects WHERE subject_id = ?", (subject_id,))
        conn.execute("DELETE FROM contents WHERE subject_id = ?", (subject_id,))
        conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        conn.commit()
        conn.close()
        for (fname,) in content_files:
            if fname:
                file_path = os.path.join(CONTENT_FOLDER, fname)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass

        return jsonify({"message": "Subject deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/subjects/<int:subject_id>/enroll", methods=["POST"])
def enroll_subject(subject_id):
    ok, resp, code = require_login()
    if not ok:
        return resp, code
    if session.get("role") != "student":
        return jsonify({"error": "Only students can enroll"}), 403
    try:
        conn = sqlite3.connect(DB_PATH)
        existing = conn.execute(
            "SELECT id FROM student_subjects WHERE student_id = ? AND subject_id = ?",
            (session["user_id"], subject_id)
        ).fetchone()
        if existing:
            conn.close()
            return jsonify({"error": "Already enrolled in this subject"}), 400
        conn.execute(
            "INSERT INTO student_subjects (student_id, subject_id, enrolled_at, status) VALUES (?, ?, ?, ?)",
            (session["user_id"], subject_id, datetime.utcnow().isoformat(), "active")
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "Enrolled successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/subjects/<int:subject_id>/enroll", methods=["DELETE"])
def unenroll_subject(subject_id):
    ok, resp, code = require_login()
    if not ok:
        return resp, code
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "DELETE FROM student_subjects WHERE student_id = ? AND subject_id = ?",
            (session["user_id"], subject_id)
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "Unenrolled successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/subjects/my-enrollments", methods=["GET"])
def my_enrollments():
    ok, resp, code = require_login()
    if not ok:
        return resp, code
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            """SELECT s.id, s.name, s.description, ss.enrolled_at, ss.status
               FROM subjects s
               JOIN student_subjects ss ON s.id = ss.subject_id
               WHERE ss.student_id = ? AND ss.status = 'active'
               ORDER BY ss.enrolled_at DESC""",
            (session["user_id"],)
        ).fetchall()
        conn.close()
        enrollments = [
            {
                "subject_id": r[0],
                "name": r[1],
                "description": r[2],
                "enrolled_at": r[3],
                "status": r[4]
            }
            for r in rows
        ]
        return jsonify({"enrollments": enrollments})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/watch-history", methods=["POST"])
def track_watch_history():
    ok, resp, code = require_login()
    if not ok:
        return resp, code
    try:
        data = request.get_json(silent=True) or {}
        video_id = data.get("video_id")
        watch_duration = float(data.get("watch_duration", 0))
        total_duration = float(data.get("total_duration", 0))
        language_used = data.get("language_used", "")
        
        # Enforce actual watch duration rather than just skipping to the end
        client_completed = data.get("completed", False)
        if client_completed and total_duration > 0 and watch_duration >= (total_duration * 0.9):
            completed = 1
        else:
            completed = 0
        if not video_id:
            return jsonify({"error": "video_id required"}), 400
        conn = sqlite3.connect(DB_PATH)
        video_row = conn.execute(
            "SELECT subject_id FROM contents WHERE id = ?",
            (video_id,)
        ).fetchone()
        subject_id = video_row[0] if video_row else None
        existing = conn.execute(
            "SELECT id FROM video_watch_history WHERE student_id = ? AND video_id = ?",
            (session["user_id"], video_id)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE video_watch_history 
                   SET watch_duration = ?, total_duration = ?, last_watched_at = ?, 
                       completed = ?, language_used = ?, subject_id = ?
                   WHERE student_id = ? AND video_id = ?""",
                (watch_duration, total_duration, datetime.utcnow().isoformat(), 
                 completed, language_used, subject_id, session["user_id"], video_id)
            )
        else:
            conn.execute(
                """INSERT INTO video_watch_history 
                   (student_id, video_id, subject_id, watch_duration, total_duration, 
                    last_watched_at, completed, language_used)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (session["user_id"], video_id, subject_id, watch_duration, 
                 total_duration, datetime.utcnow().isoformat(), completed, language_used)
            )
        # Streak Logic
        today_str = datetime.utcnow().date().isoformat()
        user_row = conn.execute("SELECT current_streak, last_watched_date FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        current_streak = user_row[0] or 0
        last_date = user_row[1]
        
        new_streak = current_streak
        
        if last_date != today_str:
            yesterday_str = (datetime.utcnow().date() - timedelta(days=1)).isoformat()
            if last_date == yesterday_str:
                new_streak += 1
            else:
                new_streak = 1 # Reset if missed a day or first time
            
            conn.execute("UPDATE users SET current_streak = ?, last_watched_date = ? WHERE id = ?", (new_streak, today_str, session["user_id"]))

        conn.commit()
        conn.close()
        return jsonify({"message": "Watch history updated", "streak": new_streak})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/analytics/subject/<int:subject_id>", methods=["GET"])
def subject_analytics(subject_id):
    ok, resp, code = require_teacher()
    if not ok:
        return resp, code
    try:
        conn = sqlite3.connect(DB_PATH)
        teacher_check = conn.execute(
            "SELECT 1 FROM teacher_subjects WHERE teacher_id = ? AND subject_id = ?",
            (session["user_id"], subject_id)
        ).fetchone()
        if not teacher_check:
            conn.close()
            return jsonify({"error": "Not authorized to view this subject's analytics"}), 403
        subject_info = conn.execute(
            "SELECT name, description FROM subjects WHERE id = ?",
            (subject_id,)
        ).fetchone()
        total_students = conn.execute(
            "SELECT COUNT(DISTINCT student_id) FROM student_subjects WHERE subject_id = ? AND status = 'active'",
            (subject_id,)
        ).fetchone()[0] or 0
        total_videos = conn.execute(
            "SELECT COUNT(*) FROM contents WHERE subject_id = ?",
            (subject_id,)
        ).fetchone()[0] or 0
        student_progress = conn.execute(
            """SELECT u.id, u.email, u.username,
               COUNT(DISTINCT vwh.video_id) as videos_watched,
               COUNT(DISTINCT c.id) as total_videos,
               SUM(CASE WHEN vwh.completed = 1 THEN 1 ELSE 0 END) as videos_completed,
               MAX(vwh.last_watched_at) as last_activity,
               GROUP_CONCAT(DISTINCT vwh.language_used) as languages_used
               FROM users u
               JOIN student_subjects ss ON u.id = ss.student_id
               LEFT JOIN contents c ON c.subject_id = ss.subject_id
               LEFT JOIN video_watch_history vwh ON vwh.student_id = u.id AND vwh.video_id = c.id
               WHERE ss.subject_id = ? AND ss.status = 'active' AND u.role = 'student'
               GROUP BY u.id
               ORDER BY last_activity DESC""",
            (subject_id,)
        ).fetchall()
        video_stats = conn.execute(
            """SELECT c.id, c.title, c.translated_filename,
               COUNT(DISTINCT vwh.student_id) as students_watched,
               AVG(vwh.watch_duration) as avg_watch_duration,
               AVG(CASE WHEN vwh.completed = 1 THEN 1.0 ELSE 0.0 END) * 100 as completion_rate
               FROM contents c
               LEFT JOIN video_watch_history vwh ON c.id = vwh.video_id
               WHERE c.subject_id = ?
               GROUP BY c.id
               ORDER BY students_watched DESC""",
            (subject_id,)
        ).fetchall()
        language_stats = conn.execute(
            """SELECT language_used, COUNT(*) as usage_count
               FROM video_watch_history
               WHERE subject_id = ? AND language_used IS NOT NULL AND language_used != ''
               GROUP BY language_used
               ORDER BY usage_count DESC""",
            (subject_id,)
        ).fetchall()
        conn.close()
        return jsonify({
            "subject": {
                "id": subject_id,
                "name": subject_info[0],
                "description": subject_info[1]
            },
            "overview": {
                "total_students": total_students,
                "total_videos": total_videos
            },
            "student_progress": [
                {
                    "student_id": sp[0],
                    "email": sp[1],
                    "username": sp[2],
                    "videos_watched": sp[3] or 0,
                    "total_videos": sp[4] or 0,
                    "videos_completed": sp[5] or 0,
                    "completion_percentage": round((sp[5] or 0) / max(sp[4] or 1, 1) * 100, 1),
                    "last_activity": sp[6],
                    "languages_used": sp[7].split(",") if sp[7] else []
                }
                for sp in student_progress
            ],
            "video_stats": [
                {
                    "video_id": vs[0],
                    "title": vs[1],
                    "filename": vs[2],
                    "students_watched": vs[3] or 0,
                    "avg_watch_duration": round(vs[4] or 0, 1),
                    "completion_rate": round(vs[5] or 0, 1)
                }
                for vs in video_stats
            ],
            "language_stats": [
                {
                    "language": ls[0],
                    "usage_count": ls[1]
                }
                for ls in language_stats
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/analytics/my-subjects", methods=["GET"])
def my_subjects_analytics():
    ok, resp, code = require_teacher()
    if not ok:
        return resp, code
    try:
        conn = sqlite3.connect(DB_PATH)
        subjects = conn.execute(
            """SELECT s.id, s.name, s.description,
               COUNT(DISTINCT ss.student_id) as student_count,
               COUNT(DISTINCT c.id) as video_count
               FROM subjects s
               JOIN teacher_subjects ts ON s.id = ts.subject_id
               LEFT JOIN student_subjects ss ON s.id = ss.subject_id AND ss.status = 'active'
               LEFT JOIN contents c ON s.id = c.subject_id
               WHERE ts.teacher_id = ?
               GROUP BY s.id
               ORDER BY s.created_at DESC""",
            (session["user_id"],)
        ).fetchall()
        conn.close()
        return jsonify({
            "subjects": [
                {
                    "id": s[0],
                    "name": s[1],
                    "description": s[2],
                    "student_count": s[3] or 0,
                    "video_count": s[4] or 0
                }
                for s in subjects
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/api/videos/<int:video_id>/complete", methods=["POST"])
def complete_video(video_id):
    """Mark a video as completed for a student and generate quiz."""
    ok, resp, code = require_login()
    if not ok:
        return resp, code
    data = request.get_json(silent=True) or {}
    watch_percentage = data.get("watch_percentage", 100.0)
    student_id = session.get("user_id")
    conn = sqlite3.connect(DB_PATH)

@app.route("/api/teacher/tests", methods=["POST"])
def save_teacher_test():
    ok, resp, code = require_teacher()
    if not ok: return resp, code
    
    data = request.get_json(silent=True) or {}
    video_id = data.get("video_id")
    questions = data.get("questions") # List of objects
    
    if not video_id or not questions:
        return jsonify({"error": "video_id and questions are required"}), 400
        
    try:
        conn = sqlite3.connect(DB_PATH)
        # Check if test exists
        exists = conn.execute("SELECT id FROM teacher_tests WHERE video_id = ?", (video_id,)).fetchone()
        
        if exists:
            conn.execute("UPDATE teacher_tests SET questions = ?, created_at = ? WHERE id = ?", 
                        (json.dumps(questions), datetime.utcnow().isoformat(), exists[0]))
        else:
            conn.execute("INSERT INTO teacher_tests (video_id, teacher_id, questions, created_at) VALUES (?, ?, ?, ?)",
                        (video_id, session["user_id"], json.dumps(questions), datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"message": "Test saved successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/teacher/tests/<int:video_id>", methods=["GET"])
def get_teacher_test(video_id):
    ok, resp, code = require_teacher()
    if not ok: return resp, code
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT questions FROM teacher_tests WHERE video_id = ?", (video_id,)).fetchone()
        conn.close()
        if row:
            return jsonify({"questions": json.loads(row[0])})
        return jsonify({"questions": []})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/student/tests/<int:video_id>", methods=["GET"])
def get_student_test(video_id):
    ok, resp, code = require_login()
    if not ok: return resp, code
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT id, questions FROM teacher_tests WHERE video_id = ?", (video_id,)).fetchone()
        
        if not row:
            conn.close()
            return jsonify({"found": False}) # No test for this video
            
        test_id, questions_json = row
        
        # Check if already attempted
        attempt = conn.execute("SELECT score, passed, attempted_at FROM test_attempts WHERE test_id = ? AND student_id = ?", 
                              (test_id, session["user_id"])).fetchone()
        conn.close()
        
        questions = json.loads(questions_json)
        # Strip answers from questions for student
        student_questions = []
        for q in questions:
            sq = {k:v for k,v in q.items() if k != "correctAnswer"} # assuming correctAnswer key stores the answer
            student_questions.append(sq)
            
        return jsonify({
            "found": True,
            "test_id": test_id,
            "questions": student_questions,
            "attempt": {
                "score": attempt[0],
                "passed": bool(attempt[1]),
                "attempted_at": attempt[2]
            } if attempt else None
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/student/tests/<int:test_id>/submit", methods=["POST"])
def submit_test(test_id):
    ok, resp, code = require_login()
    if not ok: return resp, code
    
    data = request.get_json(silent=True) or {}
    answers = data.get("answers") # Index or value of keys
    
    if answers is None:
        return jsonify({"error": "answers required"}), 400
        
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT questions FROM teacher_tests WHERE id = ?", (test_id,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "Test not found"}), 404
            
        questions = json.loads(row[0])
        score = 0
        total = len(questions)
        
        # Calculate score
        for idx, q in enumerate(questions):
            # Assuming answers is a list of user selections
            # And q['correctAnswer'] is the index of the correct option
            if idx < len(answers):
                user_ans = answers[idx]
                correct_ans = int(q.get('correctAnswer', -1))
                if int(user_ans) == correct_ans:
                    score += 1
        
        percentage = (score / total) * 100 if total > 0 else 0
        passed = 1 if percentage >= 60 else 0 # 60% passing mark
        
        conn.execute("INSERT INTO test_attempts (test_id, student_id, score, passed, answers, attempted_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (test_id, session["user_id"], percentage, passed, json.dumps(answers), datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        
        return jsonify({
            "message": "Test submitted",
            "score": percentage,
            "passed": bool(passed),
            "total_questions": total,
            "correct_answers": score
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    try:
        video = conn.execute(
            "SELECT id, title, subject_id FROM contents WHERE id = ?",
            (video_id,)
        ).fetchone()
        if not video:
            return jsonify({"error": "Video not found"}), 404
        subject_name = "General"
        if video[2]:  # subject_id
            subject_row = conn.execute(
                "SELECT name FROM subjects WHERE id = ?",
                (video[2],)
            ).fetchone()
            if subject_row:
                subject_name = subject_row[0]
        existing = conn.execute(
            "SELECT id FROM video_watch_history WHERE student_id = ? AND video_id = ?",
            (student_id, video_id)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE video_watch_history 
                   SET watch_duration = ?, total_duration = ?, last_watched_at = ?, completed = 1
                   WHERE student_id = ? AND video_id = ?""",
                (watch_percentage, 100.0, datetime.utcnow().isoformat(), student_id, video_id)
            )
        else:
            conn.execute(
                """INSERT INTO video_watch_history 
                   (student_id, video_id, subject_id, watch_duration, total_duration, 
                    last_watched_at, completed, language_used)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, video_id, video[2], watch_percentage, 100.0, 
                 datetime.utcnow().isoformat(), 1, "English")
            )
        existing_quiz = conn.execute(
            "SELECT id, questions FROM quizzes WHERE video_id = ?",
            (video_id,)
        ).fetchone()
        if not existing_quiz:
            questions = quiz_generator.generate_quiz(
                video_topic=subject_name or video[1] or "General",
                video_description=video[1],
                num_questions=5
            )
            conn.execute(
                "INSERT INTO quizzes (video_id, title, questions, created_at) VALUES (?, ?, ?, ?)",
                (video_id, f"Quiz: {video[1] or 'Video Quiz'}", json.dumps(questions), datetime.utcnow().isoformat())
            )
            quiz_id = conn.lastrowid
        else:
            quiz_id = existing_quiz[0]
            questions = json.loads(existing_quiz[1])
        conn.commit()
        return jsonify({
            "success": True,
            "quiz_required": True,
            "quiz_id": quiz_id,
            "questions": questions,
            "message": "Video completed. Quiz is required."
        }), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
@app.route("/api/quizzes/<int:quiz_id>", methods=["GET"])
def get_quiz(quiz_id):
    """Get quiz questions."""
    ok, resp, code = require_login()
    if not ok:
        return resp, code
    conn = sqlite3.connect(DB_PATH)
    try:
        quiz = conn.execute(
            "SELECT id, title, questions FROM quizzes WHERE id = ?",
            (quiz_id,)
        ).fetchone()
        if not quiz:
            return jsonify({"error": "Quiz not found"}), 404
        questions = json.loads(quiz[2])
        return jsonify({
            "quiz_id": quiz[0],
            "title": quiz[1],
            "questions": questions
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
@app.route("/api/quizzes/<int:quiz_id>/submit", methods=["POST"])
def submit_quiz(quiz_id):
    """Submit quiz answers and calculate score."""
    ok, resp, code = require_login()
    if not ok:
        return resp, code
    data = request.get_json(silent=True) or {}
    student_id = session.get("user_id")
    answers = data.get("answers", [])  # List of answer indices
    conn = sqlite3.connect(DB_PATH)
    try:
        quiz = conn.execute(
            "SELECT id, questions, video_id FROM quizzes WHERE id = ?",
            (quiz_id,)
        ).fetchone()
        if not quiz:
            return jsonify({"error": "Quiz not found"}), 404
        questions = json.loads(quiz[1])
        correct = 0
        total = len(questions)
        results = []
        for i, question in enumerate(questions):
            student_answer = answers[i] if i < len(answers) else None
            is_correct = student_answer == question['correct_answer']
            if is_correct:
                correct += 1
            results.append({
                "question": question['question'],
                "student_answer": student_answer,
                "correct_answer": question['correct_answer'],
                "is_correct": is_correct,
                "explanation": question.get('explanation', '')
            })
        score = (correct / total) * 100 if total > 0 else 0
        passed = score >= 70  # 70% passing threshold
        conn.execute(
            """INSERT INTO quiz_attempts 
               (student_id, quiz_id, answers, score, passed, attempted_at) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (student_id, quiz_id, json.dumps(answers), score, 1 if passed else 0, datetime.utcnow().isoformat())
        )
        conn.commit()
        return jsonify({
            "success": True,
            "score": score,
            "passed": passed,
            "correct": correct,
            "total": total,
            "results": results
        }), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# --- Comments & AI Chat API ---

@app.route("/api/comments/<int:video_id>", methods=["GET"])
def get_comments(video_id):
    conn = sqlite3.connect(DB_PATH)
    # Get all comments for this video
    rows = conn.execute("""
        SELECT c.id, c.user_id, c.parent_id, c.text, c.is_teacher_reply, c.created_at, u.display_name, u.email, u.role
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.video_id = ?
        ORDER BY c.created_at ASC
    """, (video_id,)).fetchall()
    conn.close()
    
    comments = []
    for r in rows:
        comments.append({
            "id": r[0],
            "user_id": r[1],
            "parent_id": r[2],
            "text": r[3],
            "is_teacher_reply": bool(r[4]),
            "created_at": r[5],
            "user_name": r[6] or r[7].split("@")[0],
            "user_role": r[8]
        })
    return jsonify({"comments": comments})

@app.route("/api/comments", methods=["POST"])
def post_comment():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    video_id = data.get("video_id")
    text = data.get("text")
    
    if not video_id or not text:
        return jsonify({"error": "Missing video_id or text"}), 400
        
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO comments (video_id, user_id, text, created_at) VALUES (?, ?, ?, ?)",
        (video_id, session["user_id"], text, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Comment posted"})

@app.route("/api/comments/reply", methods=["POST"])
def reply_comment():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if session.get("role") != "teacher":
        return jsonify({"error": "Only teachers can reply"}), 403
        
    data = request.json
    video_id = data.get("video_id")
    parent_id = data.get("parent_id") # The comment ID we are replying to
    text = data.get("text")
    
    if not video_id or not parent_id or not text:
        return jsonify({"error": "Missing fields"}), 400
        
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO comments (video_id, user_id, parent_id, text, is_teacher_reply, created_at) VALUES (?, ?, ?, ?, 1, ?)",
        (video_id, session["user_id"], parent_id, text, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Reply posted"})
@app.route("/api/comments/all", methods=["GET"])
def get_all_comments():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if session.get("role") != "teacher":
        return jsonify({"error": "Only teachers can view all questions"}), 403
    
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT c.id, c.text, c.created_at, u.display_name, u.email, cnt.title, cnt.id,
               (SELECT COUNT(*) FROM comments r WHERE r.parent_id = c.id) as reply_count,
               (SELECT COUNT(*) FROM comments r WHERE r.parent_id = c.id AND r.is_teacher_reply = 1) as teacher_replied
        FROM comments c
        JOIN users u ON c.user_id = u.id
        JOIN contents cnt ON c.video_id = cnt.id
        WHERE c.parent_id IS NULL
        AND cnt.subject_id IN (
            SELECT subject_id FROM teacher_subjects WHERE teacher_id = ?
        )
        ORDER BY c.created_at DESC
    """, (session["user_id"],)).fetchall()
    conn.close()
    
    questions = []
    for r in rows:
        questions.append({
            "id": r[0],
            "text": r[1],
            "created_at": r[2],
            "user_name": r[3] or r[4].split("@")[0],
            "video_title": r[5] or "Unknown/Deleted Video",
            "video_id": r[6],
            "reply_count": r[7],
            "is_answered": r[8] > 0
        })
    return jsonify({"questions": questions})

@app.route("/api/ai-chat", methods=["POST"])
def ai_chat():
    if "user_id" not in session:
        return jsonify({"answer": "Please log in to use the AI chatbot."}), 401
    
    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}
    video_id = data.get("video_id") # This is the content ID
    query = data.get("query", "").strip()
    
    if not query:
        return jsonify({"answer": "Please ask a question."})

    answer = "I couldn't find an answer in the video transcript."
    
    try:
        conn = sqlite3.connect(DB_PATH)
        # Attempt to get transcript
        row = conn.execute("SELECT transcript, title, translated_filename, original_filename FROM contents WHERE id = ?", (video_id,)).fetchone()
        
        transcript = row[0] if row else None
        
        if row and not transcript:
            # Lazy generation of transcript if missing (useful for old uploads)
            print("📝 Lazy generating missing transcript for AI...")
            filename = row[2] or row[3]
            if filename:
                for folder in [CONTENT_FOLDER, UPLOAD_FOLDER]:
                    fpath = os.path.join(folder, filename)
                    if os.path.exists(fpath):
                        transcript = transcribe_with_progress(fpath, None)
                        if transcript:
                            conn.execute("UPDATE contents SET transcript = ? WHERE id = ?", (transcript, video_id))
                            conn.commit()
                        break

        transcript_text = transcript if transcript else "No transcript available for this video."

        # Fetch chat history for this user & video to give context
        history_rows = conn.execute(
            "SELECT role, content FROM ai_chat_history WHERE user_id = ? AND video_id = ? ORDER BY id DESC LIMIT 10",
            (user_id, video_id)
        ).fetchall()
        
        # Save user query to DB
        conn.execute(
            "INSERT INTO ai_chat_history (user_id, video_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, video_id, "user", query, datetime.utcnow().isoformat())
        )
        conn.commit()

        # Build history context
        history_text = "Previous conversation context:\n"
        if history_rows:
            history_rows.reverse() # Oldest first among the 10
            for r in history_rows:
                role_label = "Student" if r[0] == "user" else "AI Tutor"
                history_text += f"{role_label}: {r[1]}\n"
        else:
            history_text += "None.\n"
            
        conn.close()

        prompt = f"You are a helpful AI Tutor for an educational platform. A student is asking: \"{query}\"\n\nContext from video transcript (if any): \"{transcript_text}\"\n\n{history_text}\n\nResponse guidelines:\n- Answer the question fully and properly based on your general knowledge and the conversation history.\n- If the video context has the answer, base your explanation on it.\n- Even if the context does not contain the answer, answer the question anyway.\n- Be educational and format nicely using Markdown."

        if GEMINI_API_KEY:
            try:
                model = genai.GenerativeModel("gemini-2.5-flash")
                response = model.generate_content(prompt)
                answer = f"💡 **AI Tutor:**\n\n{response.text}"
            except Exception as e:
                print(f"Gemini API Error: {e}")
                answer = f"I encountered an error connecting to the Gemini AI model. Details: {str(e)}"
        else:
            try:
                response = g4f.ChatCompletion.create(
                    model=g4f.models.gpt_4o_mini,
                    messages=[{"role": "user", "content": prompt}]
                )
                answer = f"💡 **AI Tutor (Free):**\n\n{response}"
            except Exception as e:
                print(f"G4F AI Free Error: {e}")
                answer = "⚠️ **API Key Missing:** I tried to answer using a free AI model, but the service is currently overwhelmed. To guarantee proper responses to ANY question, open the `.env` file in the project folder and paste your `GEMINI_API_KEY=your_key_here`."
                
        # Save AI Answer to DB
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO ai_chat_history (user_id, video_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, video_id, "model", answer, datetime.utcnow().isoformat())
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving AI response to history: {e}")

    except Exception as e:
        print(f"AI Chat Error: {e}")
        answer = "I encountered an error trying to process your question."

    return jsonify({"answer": answer})

@app.route("/api/ai-chat/history/<int:video_id>", methods=["GET"])
def ai_chat_history(video_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session["user_id"]
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT role, content, created_at FROM ai_chat_history WHERE user_id = ? AND video_id = ? ORDER BY created_at ASC",
        (user_id, video_id)
    ).fetchall()
    conn.close()
    
    history = []
    for r in rows:
        history.append({
            "role": r[0],
            "content": r[1],
            "created_at": r[2]
        })
    return jsonify({"history": history})
@app.route("/api/user/profile", methods=["GET", "POST"])
def user_profile():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    user_id = session["user_id"]
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    if request.method == "GET":
        user = conn.execute("SELECT username, full_name, email, phone FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if user:
            return jsonify(dict(user))
        return jsonify({"error": "User not found"}), 404
        
    if request.method == "POST":
        data = request.json
        full_name = data.get("full_name", "")
        email = data.get("email", "")
        phone = data.get("phone", "")
        
        conn.execute("UPDATE users SET full_name = ?, email = ?, phone = ? WHERE id = ?", 
                     (full_name, email, phone, user_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Profile updated successfully"})

@app.route("/api/user/password", methods=["POST"])
def update_password():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
        
    user_id = session["user_id"]
    data = request.json
    current_password = data.get("current_password")
    new_password = data.get("new_password")
    
    if not current_password or not new_password:
        return jsonify({"error": "Missing password fields"}), 400
    
    from werkzeug.security import generate_password_hash, check_password_hash
    
    conn = sqlite3.connect(DB_PATH)
    user = conn.execute("SELECT password FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if not user or not check_password_hash(user[0], current_password):
        conn.close()
        return jsonify({"error": "Incorrect current password"}), 400
        
    hashed_pw = generate_password_hash(new_password)
    conn.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_pw, user_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Password updated successfully"})

@app.route("/api/user/deactivate", methods=["POST"])
def deactivate_account():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
        
    user_id = session["user_id"]
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    session.clear()
    return jsonify({"success": True})

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
