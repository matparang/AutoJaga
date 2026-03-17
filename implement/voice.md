📋 SCOPE PROMPT: JAGABOT v3.7 Phase 1 - Basic Local Voice Integration

```markdown
# SCOPE: JAGABOT v3.7 Phase 1 - Basic Local Voice for Chat Tab

## CURRENT STATE
✅ v3.6 complete:
- 1245 tests passing
- 6 UI tabs (including Chat)
- 5 query categories
- Bilingual responses (Malay/English)
- ParallelLab + Auto-scaling

⏳ TARGET: Add local voice input/output to Chat tab

## OBJECTIVE
Add voice capability to existing Chat tab:

1. SPEECH-TO-TEXT (STT): User speaks → transcribed to text
2. TEXT-TO-SPEECH (TTS): JAGABOT response → spoken aloud
3. PUSH-TO-TALK button in UI
4. OFFLINE, local processing (no API calls)
5. LOW LATENCY (<2s end-to-end)

## TECHNOLOGY STACK

### Speech-to-Text: Vosk
```yaml
Pros:
  - ✅ Offline, 75+ languages
  - ✅ Real-time streaming
  - ✅ ~500MB model
  - ✅ Active development
  
Cons:
  - ⚠️ Requires model download
  - ⚠️ Accuracy slightly below Whisper
```

Text-to-Speech: pyttsx3

```yaml
Pros:
  - ✅ Built into Python
  - ✅ No ML models needed
  - ✅ Instant (no loading)
  - ✅ Works offline
  
Cons:
  - ⚠️ Robotic voice (but works)
  - ⚠️ Limited voice options
```

NEW COMPONENTS

1. Voice Service

```python
# jagabot/voice/service.py

import queue
import threading
import wave
import pyaudio
import vosk
import pyttsx3
import json
import os
from pathlib import Path

class VoiceService:
    """
    Local voice service using Vosk (STT) and pyttsx3 (TTS)
    """
    
    def __init__(self, model_path: str = None, language: str = "ms"):
        """
        Initialize voice service
        """
        # Setup paths
        self.models_dir = Path.home() / '.jagabot' / 'voice_models'
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Load Vosk model
        self.stt_model = self._load_stt_model(model_path, language)
        
        # Initialize TTS
        self.tts_engine = pyttsx3.init()
        self._configure_tts(language)
        
        # Audio settings
        self.sample_rate = 16000
        self.chunk_size = 4000
        self.audio_queue = queue.Queue()
        self.is_recording = False
        
    def _load_stt_model(self, model_path: str, language: str):
        """Download and load Vosk model if needed"""
        if model_path and os.path.exists(model_path):
            return vosk.Model(model_path)
        
        # Auto-download based on language
        if language == 'ms':  # Malay
            model_url = "https://alphacephei.com/vosk/models/vosk-model-small-ms-0.3.zip"
            model_name = "vosk-model-small-ms-0.3"
        else:  # English
            model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
            model_name = "vosk-model-small-en-us-0.15"
        
        model_path = self.models_dir / model_name
        
        if not model_path.exists():
            self._download_model(model_url, model_path.parent, model_name)
        
        return vosk.Model(str(model_path))
    
    def _configure_tts(self, language: str):
        """Configure TTS engine"""
        voices = self.tts_engine.getProperty('voices')
        
        # Try to find Malay voice
        if language == 'ms':
            for voice in voices:
                if 'malay' in voice.name.lower() or 'ms_' in voice.id:
                    self.tts_engine.setProperty('voice', voice.id)
                    break
        
        # Set properties
        self.tts_engine.setProperty('rate', 150)  # Speed
        self.tts_engine.setProperty('volume', 0.9)  # Volume
    
    def transcribe(self, audio_data: bytes) -> str:
        """
        Convert speech to text using Vosk
        """
        rec = vosk.KaldiRecognizer(self.stt_model, self.sample_rate)
        
        if rec.AcceptWaveform(audio_data):
            result = json.loads(rec.Result())
            return result.get('text', '')
        return ''
    
    def synthesize(self, text: str):
        """
        Convert text to speech using pyttsx3
        """
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()
    
    def start_recording(self):
        """Start capturing from microphone"""
        self.is_recording = True
        self.audio_thread = threading.Thread(target=self._record_loop)
        self.audio_thread.start()
    
    def stop_recording(self) -> bytes:
        """Stop recording and return audio data"""
        self.is_recording = False
        self.audio_thread.join()
        
        # Collect all audio chunks
        audio_data = b''
        while not self.audio_queue.empty():
            audio_data += self.audio_queue.get()
        
        return audio_data
    
    def _record_loop(self):
        """Background recording thread"""
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
        while self.is_recording:
            data = stream.read(self.chunk_size)
            self.audio_queue.put(data)
        
        stream.stop_stream()
        stream.close()
        p.terminate()
    
    def _download_model(self, url: str, target_dir: Path, model_name: str):
        """Download Vosk model if not exists"""
        import requests
        import zipfile
        from tqdm import tqdm
        
        print(f"📥 Downloading voice model {model_name}...")
        
        # Download zip
        zip_path = target_dir / f"{model_name}.zip"
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        
        with open(zip_path, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True) as pbar:
                for data in response.iter_content(chunk_size=1024):
                    f.write(data)
                    pbar.update(len(data))
        
        # Extract
        print(f"📦 Extracting model...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        
        # Cleanup
        zip_path.unlink()
        print(f"✅ Voice model ready at {target_dir / model_name}")
```

2. Updated Chat Tab with Voice

```python
# jagabot/ui/chat.py (updated)

import streamlit as st
import asyncio
import tempfile
import wave
from jagabot.voice.service import VoiceService

def render_chat():
    """Chat interface with voice input/output"""
    
    # Initialize voice service
    if 'voice' not in st.session_state:
        st.session_state.voice = VoiceService(language='ms')  # Malay default
    
    # Chat header with voice toggle
    col1, col2, col3 = st.columns([6, 1, 1])
    with col1:
        st.header("💬 Chat dengan JAGABOT")
    with col2:
        voice_enabled = st.checkbox("🎤 Voice", value=False)
    with col3:
        if st.button("🧹 Clear"):
            st.session_state.chat_messages = []
            st.rerun()
    
    # Display chat history
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])
            if 'dashboard' in msg:
                st.markdown("---")
                st.markdown(msg['dashboard'])
            st.caption(f"🕒 {msg['time'].strftime('%H:%M:%S')}")
    
    # Voice input button (only if enabled)
    if voice_enabled:
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("🎤 Press to Speak", use_container_width=True):
                with st.spinner("Listening..."):
                    # Record audio
                    st.session_state.voice.start_recording()
                    st.info("Speaking... click Stop when done")
            
            if st.button("⏹️ Stop", use_container_width=True):
                # Stop and transcribe
                audio_data = st.session_state.voice.stop_recording()
                
                # Save temporarily
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    with wave.open(f, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(16000)
                        wf.writeframes(audio_data)
                    temp_path = f.name
                
                # Transcribe
                with open(temp_path, 'rb') as f:
                    audio_bytes = f.read()
                
                text = st.session_state.voice.transcribe(audio_bytes)
                
                if text:
                    # Add to chat and process
                    st.session_state.chat_messages.append({
                        'role': 'user',
                        'content': f"🎤 {text}",
                        'time': datetime.now()
                    })
                    
                    # Process response
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    response = loop.run_until_complete(_process_query(text))
                    loop.close()
                    
                    # Speak response
                    st.session_state.voice.synthesize(response['message'])
                    
                    # Add to chat
                    st.session_state.chat_messages.append({
                        'role': 'assistant',
                        'content': response['message'],
                        'dashboard': response.get('dashboard'),
                        'time': datetime.now()
                    })
                    
                    st.rerun()
    
    # Text input (always available)
    prompt = st.chat_input("Tanya JAGABOT apa-apa... (or use 🎤 voice)")
    if prompt:
        # Add user message
        st.session_state.chat_messages.append({
            'role': 'user',
            'content': prompt,
            'time': datetime.now()
        })
        
        # Process
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(_process_query(prompt))
        loop.close()
        
        # Speak if voice enabled
        if voice_enabled:
            st.session_state.voice.synthesize(response['message'])
        
        # Add response
        st.session_state.chat_messages.append({
            'role': 'assistant',
            'content': response['message'],
            'dashboard': response.get('dashboard'),
            'time': datetime.now()
        })
        
        st.rerun()
```

3. Installation Script

```python
# scripts/install_voice.sh

#!/bin/bash
# Install voice dependencies for JAGABOT

echo "🎤 Installing voice dependencies..."

# System dependencies
sudo apt-get update
sudo apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    flac \
    libportaudio2

# Python packages
pip install \
    vosk \
    pyttsx3 \
    pyaudio \
    wave \
    tqdm \
    requests

# Download Malay voice model
python -c "
from pathlib import Path
import requests
import zipfile

models_dir = Path.home() / '.jagabot' / 'voice_models'
models_dir.mkdir(parents=True, exist_ok=True)

# Malay model
url = 'https://alphacephei.com/vosk/models/vosk-model-small-ms-0.3.zip'
zip_path = models_dir / 'vosk-model-small-ms-0.3.zip'

if not (models_dir / 'vosk-model-small-ms-0.3').exists():
    print('📥 Downloading Malay voice model...')
    r = requests.get(url, stream=True)
    with open(zip_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print('📦 Extracting...')
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(models_dir)
    
    zip_path.unlink()
    print('✅ Malay voice model ready')
"

echo "✅ Voice installation complete!"
```

4. Tests

```python
# tests/test_voice.py

import pytest
from jagabot.voice.service import VoiceService

def test_voice_initialization():
    voice = VoiceService()
    assert voice.stt_model is not None
    assert voice.tts_engine is not None

def test_tts_basic():
    voice = VoiceService()
    # Just test that it doesn't crash
    voice.synthesize("Test message")

def test_stt_model_download():
    # Test model download logic
    voice = VoiceService()
    model_path = voice.models_dir / 'vosk-model-small-ms-0.3'
    assert model_path.exists() or voice.models_dir.exists()
```

NEW FILES TO CREATE

1. jagabot/voice/service.py - VoiceService class
2. jagabot/voice/__init__.py - Package init
3. scripts/install_voice.sh - Voice dependencies installer
4. tests/test_voice.py - 10+ tests
5. tests/test_voice_integration.py - 5+ tests

FILES TO MODIFY

1. jagabot/ui/chat.py - Add voice buttons + integration
2. requirements.txt - Add voice dependencies
3. CHANGELOG.md - v3.7 Phase 1

SUCCESS CRITERIA

✅ Voice button appears in Chat tab
✅ "Press to Speak" records audio
✅ Transcription works (Vosk)
✅ JAGABOT responds with text + speech
✅ Malay language support works
✅ All offline, no API calls
✅ 10+ new tests passing
✅ Total tests: 1255+

TIMELINE

Task Hours
VoiceService class 4
Vosk integration 3
pyttsx3 integration 2
Chat tab UI updates 3
Installation script 2
Tests (15+) 3
TOTAL 17 hours

```

---

**v3.7 Phase 1 will give JAGABOT local voice capabilities - private, free, and integrated!** 🚀
