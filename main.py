import streamlit as st
import requests
import sqlite3
from datetime import datetime
from gtts import gTTS  # ✅ NEW: gTTS for cloud-compatible text-to-speech
import os

def update_db_schema():
    conn = sqlite3.connect("vocab.db")
    c = conn.cursor()
    c.execute("PRAGMA table_info(words)")
    columns = [column[1] for column in c.fetchall()]
    if 'synonyms' not in columns:
        c.execute("ALTER TABLE words ADD COLUMN synonyms TEXT")
    if 'part_of_speech' not in columns:
        c.execute("ALTER TABLE words ADD COLUMN part_of_speech TEXT")
    conn.commit()
    conn.close()

def get_random_word():
    words = ["apple", "banana", "cherry", "table", "chair", "run", "beautiful", "happy", "quick"]
    return words[int(datetime.now().timestamp() % len(words))]

def get_word():
    api_url = "https://random-word-api.herokuapp.com/word"
    try:
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()
        word = response.json()[0]
        return fetch_word_details(word)
    except (requests.exceptions.RequestException, IndexError):
        word = get_random_word()
        return fetch_word_details(word)

def fetch_word_details(word):
    api_url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()
        data = response.json()
        meaning = data[0]['meanings'][0]['definitions'][0]['definition']
        example = data[0]['meanings'][0]['definitions'][0].get('example')
        synonyms = data[0]['meanings'][0].get('synonyms', [])
        part_of_speech = data[0]['meanings'][0].get('partOfSpeech', 'Unknown')
        phonetics = data[0].get('phonetics', [])
        uk_audio = next((item.get('audio') for item in phonetics if 'uk' in item.get('text', '').lower()), None)
        us_audio = next((item.get('audio') for item in phonetics if 'us' in item.get('text', '').lower()), None)

        if not example:
            example = generate_example(word, meaning, synonyms, part_of_speech)

        return {
            'word': word,
            'meaning': meaning,
            'example': example,
            'synonyms': synonyms,
            'part_of_speech': part_of_speech,
            'pronunciations': {"UK": uk_audio, "US": us_audio}
        }
    except (requests.exceptions.RequestException, IndexError, KeyError):
        return None

def generate_example(word, meaning, synonyms, part_of_speech):
    if part_of_speech in ["verb", "action"]:
        return f"I often {word} when I feel energetic."
    elif part_of_speech in ["adjective", "descriptive"]:
        return f"The sunset was truly {word}."
    elif part_of_speech in ["noun", "object"]:
        return f"The {word} is essential in my daily life."
    else:
        return f"This is an example sentence using the word '{word}'."

def create_db():
    conn = sqlite3.connect("vocab.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE,
            meaning TEXT,
            example TEXT,
            synonyms TEXT,
            part_of_speech TEXT,
            date_added TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_word(word_data):
    conn = sqlite3.connect("vocab.db", timeout=5)
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO words 
        (word, meaning, example, synonyms, part_of_speech, date_added) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        word_data['word'], word_data['meaning'], word_data['example'],
        ', '.join(word_data['synonyms']), word_data['part_of_speech'],
        datetime.now().strftime('%Y-%m-%d')
    ))
    conn.commit()
    conn.close()

def fetch_saved_words():
    conn = sqlite3.connect("vocab.db", timeout=5)
    c = conn.cursor()
    c.execute("SELECT word, meaning, example, synonyms, part_of_speech, date_added FROM words")
    words = c.fetchall()
    conn.close()
    return words

def delete_word(word):
    conn = sqlite3.connect("vocab.db", timeout=5)
    c = conn.cursor()
    c.execute("DELETE FROM words WHERE word = ?", (word,))
    conn.commit()
    conn.close()

# ✅ NEW FUNCTION: generate audio using gTTS
def generate_tts_audio(word):
    tts = gTTS(text=word, lang='en')
    tts.save("tts_output.mp3")
    with open("tts_output.mp3", "rb") as audio_file:
        audio_bytes = audio_file.read()
    os.remove("tts_output.mp3")
    return audio_bytes

# ================================
#         STREAMLIT UI
# ================================

st.title("AI Vocabulary Enhancement Bot")
st.write("Expand your vocabulary with new words and pronunciations!")

update_db_schema()
create_db()

if st.button("Get New Word"):
    word_data = get_word()
    if word_data:
        save_word(word_data)
        st.session_state['word_data'] = word_data
    else:
        st.error("Failed to fetch a word. Check your internet connection and try again.")

# Displaying the word
if 'word_data' in st.session_state:
    word_data = st.session_state['word_data']
    st.subheader(f"Word: {word_data['word']} ({word_data['part_of_speech']})")
    st.write(f"**Meaning:** {word_data['meaning']}")
    st.write(f"**Example:** {word_data['example']}")
    if word_data['synonyms']:
        st.write(f"**Synonyms:** {', '.join(word_data['synonyms'])}")
    if word_data['pronunciations']['UK']:
        st.write("**UK Pronunciation:**")
        st.audio(word_data['pronunciations']['UK'])
    if word_data['pronunciations']['US']:
        st.write("**US Pronunciation:**")
        st.audio(word_data['pronunciations']['US'])
    
    # ✅ Updated: Use gTTS-based playback
    if st.button("Play Pronunciation (gTTS)"):
        audio_data = generate_tts_audio(word_data['word'])
        st.audio(audio_data, format="audio/mp3")

# Saved words section
st.subheader("Saved Words")
saved_words = fetch_saved_words()

if 'rerun' not in st.session_state:
    st.session_state['rerun'] = False

if saved_words:
    for word, meaning, example, synonyms, part_of_speech, date in saved_words:
        with st.expander(f"{word} ({part_of_speech}) - {date}"):
            st.write(f"**Meaning:** {meaning}")
            st.write(f"**Example:** {example}")
            st.write(f"**Synonyms:** {synonyms}" if synonyms else "**Synonyms:** None")
            
            # ✅ Use gTTS for saved words too
            if st.button(f"Play Pronunciation for {word}", key=f"tts_{word}"):
                audio_data = generate_tts_audio(word)
                st.audio(audio_data, format="audio/mp3")

            if st.button(f"Delete {word}", key=f"delete_{word}"):
                delete_word(word)
                st.session_state['rerun'] = not st.session_state['rerun']
else:
    st.write("No words saved yet.")
