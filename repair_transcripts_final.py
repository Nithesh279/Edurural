import sqlite3
import os
from faster_whisper import WhisperModel

# Configuration
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.db")
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
LIMIT = 1000  # Process all videos

def repair_transcripts():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    print("🔹 Loading Faster-Whisper model (tiny, int8)...")
    try:
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
    except Exception as e:
        print(f"Failed to load model: {e}")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        # Find videos with missing transcripts but existing translated files
        rows = conn.execute("""
            SELECT id, title, translated_filename 
            FROM contents 
            WHERE (transcript IS NULL OR transcript = '') 
              AND translated_filename IS NOT NULL
        """).fetchall()
        
        print(f"Found {len(rows)} candidates for repair.")
        
        fixed_count = 0
        for r in rows:
            if fixed_count >= LIMIT:
                break
                
            video_id, title, filename = r
            file_path = os.path.join(OUTPUT_FOLDER, filename)
            
            if not os.path.exists(file_path):
                print(f"Skipping ID {video_id}: File {filename} not found.")
                continue
                
            print(f"Processing ID {video_id} ({title or 'Untitled'})...")
            try:
                # Transcribe
                segments, _ = model.transcribe(file_path, beam_size=1)
                text = " ".join([s.text for s in segments]).strip()
                
                if text:
                    conn.execute("UPDATE contents SET transcript = ? WHERE id = ?", (text, video_id))
                    conn.commit()
                    print(f"   ✅ Fixed! Transcript length: {len(text)}")
                    fixed_count += 1
                else:
                    print(f"   ⚠️ Transcribed text was empty.")
                    
            except Exception as e:
                print(f"   ❌ Failed to transcribe: {e}")

        print(f"\nRepair session finished. Fixed {fixed_count} videos.")
        
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    repair_transcripts()
