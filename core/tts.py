#!/usr/bin/env python3
"""
ENHANCED JARVIS - REAL TEXT TO SPEECH FOR LINUX
"""

import pyttsx3
import time
import os
import platform
import subprocess
import re
import tempfile
import threading
import queue
import html
from pathlib import Path
import requests
import shutil
from .enhanced_compat import EnhancedErrorHandler, PerformanceTracker
from .utils import env_get, load_env_map

VERBOSE_TTS = os.getenv("JARVIS_VERBOSE_STARTUP", "0") == "1"
ENV_VARS = load_env_map(".env")
OPENAI_API_KEY = env_get("OPENAI_API_KEY", "OPENAIAPIKEY", "OPEN_AI_API_KEY", env_map=ENV_VARS) or ""
ELEVENLABS_API_KEY = (env_get("ELEVENLABS_API_KEY", env_map=ENV_VARS) or "").strip().strip('"').strip("'")

ELEVENLABS_VOICE_IDS = {
    "adam": "pNInz6obpgDQGcFmaJgB",
    "antoni": "ErXwobaYiN019PkySvjV",
}

class EnhancedJARVIS:
    """
    Enhanced JARVIS - Speaks with real speech and enhanced features
    """
    
    def __init__(self):
        self.response_language = None
        self.current_voice = None
        self.tts_engine = None
        self._tts_init_error = ""
        self.available_voices = []
        self.default_rate = int(os.getenv("JARVIS_TTS_RATE", "150"))
        self.default_volume = float(os.getenv("JARVIS_TTS_VOLUME", "1.0"))
        self.max_chunk_chars = int(os.getenv("JARVIS_TTS_MAX_CHUNK", "220"))
        neural_tts_flag = env_get("JARVIS_USE_NEURAL_TTS", default="1", env_map=ENV_VARS)
        self.use_neural_tts = str(neural_tts_flag).strip().lower() in {"1", "true", "yes", "on"}
        self.elevenlabs_api_key = ELEVENLABS_API_KEY
        self.elevenlabs_voice = env_get("JARVIS_ELEVENLABS_VOICE", "ELEVENLABS_VOICE", default="Adam", env_map=ENV_VARS)
        self.elevenlabs_model = env_get("JARVIS_ELEVENLABS_MODEL", "ELEVENLABS_MODEL", default="eleven_flash_v2_5", env_map=ENV_VARS)
        self.openai_api_key = OPENAI_API_KEY
        self.openai_voice = os.getenv("JARVIS_OPENAI_TTS_VOICE", "onyx")
        self.openai_tts_model = os.getenv("JARVIS_OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
        self._speaking = False
        self._stream_queue: queue.Queue[str] = queue.Queue(maxsize=int(os.getenv("JARVIS_STREAM_BUFFER_SIZE", "1024")))
        self._stream_stop_event = threading.Event()
        self._stream_thread = None
        self._speech_finished_callback = None
        self._ducked = False
        self._state_lock = threading.Lock()
        self._duck_volume = os.getenv("JARVIS_DUCK_VOLUME", "35%")
        self._normal_volume = os.getenv("JARVIS_NORMAL_VOLUME", "100%")
        self.setup_tts()
        
        # Initialize enhanced utilities
        self.error_handler = EnhancedErrorHandler()
        self.performance_tracker = PerformanceTracker()
        
        if VERBOSE_TTS:
            print(" ENHANCED JARVIS WITH REAL TTS Initialized")
    
    def setup_tts(self):
        """Enhanced TTS initialization with platform-aware driver selection"""
        try:
            system_name = platform.system().lower()

            # Linux-specific audio defaults
            os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
            if system_name == "linux":
                os.environ.setdefault('SDL_AUDIODRIVER', "pulse")

            # Platform-aware pyttsx3 initialization
            driver_name = 'espeak' if system_name == "linux" else None
            if driver_name:
                self.tts_engine = pyttsx3.init(driverName=driver_name)
            else:
                self.tts_engine = pyttsx3.init()
            self._tts_init_error = ""
            
            # Get all available voices
            self.available_voices = self.tts_engine.getProperty('voices')
            if VERBOSE_TTS:
                print(f" Found {len(self.available_voices)} available voices")
            
            # Common speech properties
            self.tts_engine.setProperty('rate', self.default_rate)
            self.tts_engine.setProperty('volume', max(0.4, min(1.0, self.default_volume)))
            
            # Auto-select the best voice for Linux
            self.auto_select_voice()
            
            if VERBOSE_TTS:
                print(" Enhanced text-to-speech engine ready for Linux")
            
        except Exception as e:
            self._tts_init_error = f"Primary TTS init failed: {e}"
            if VERBOSE_TTS:
                print(f" TTS initialization error: {e}")
            # Fallback to default init
            try:
                self.tts_engine = pyttsx3.init()
                self.available_voices = self.tts_engine.getProperty('voices')
                if self.available_voices:
                    self.tts_engine.setProperty('voice', self.available_voices[0].id)
                    self.current_voice = 0
                self._tts_init_error = ""
                if VERBOSE_TTS:
                    print(" Fallback TTS initialized")
            except Exception as e2:
                self._tts_init_error = f"Primary TTS init failed: {e}; fallback init failed: {e2}"
                if VERBOSE_TTS:
                    print(f" Fallback TTS also failed: {e2}")
                self.tts_engine = None
    
    def auto_select_voice(self):
        """Automatically select the best voice for Linux"""
        if not self.tts_engine or not self.available_voices:
            return False
            
        preferred_voices = []
        
        for i, voice in enumerate(self.available_voices):
            voice_name_lower = voice.name.lower()
            voice_id_lower = voice.id.lower()
            
            is_english = any(term in voice_name_lower for term in ['english', 'en-']) or 'en_' in voice_id_lower
            if not is_english:
                continue

            score = 0
            if any(term in voice_name_lower for term in ['english-us', 'english_rp', 'en-us', 'en-gb']):
                score += 4
            if any(term in voice_name_lower for term in ['female', 'f1', 'f2', 'f3']):
                score += 2
            if any(term in voice_name_lower for term in ['whisper', 'croak', 'mumble', 'robot']):
                score -= 5

            preferred_voices.append((score, i))
        
        # Select the best available voice
        if preferred_voices:
            preferred_voices.sort(reverse=True)
            best_voice_index = preferred_voices[0][1]
            self.tts_engine.setProperty('voice', self.available_voices[best_voice_index].id)
            self.current_voice = best_voice_index
            if VERBOSE_TTS:
                print(f" Auto-selected voice: {self.available_voices[best_voice_index].name}")
            return True
        elif self.available_voices:
            # Fallback to first available voice
            self.tts_engine.setProperty('voice', self.available_voices[0].id)
            self.current_voice = 0
            if VERBOSE_TTS:
                print(f" Using fallback voice: {self.available_voices[0].name}")
            return True
        
        return False

    def _prepare_speech_text(self, text: str) -> str:
        prepared = (text or "").strip()
        if not prepared:
            return ""

        prepared = prepared.replace("J.A.R.V.I.S.", "Jarvis")
        prepared = prepared.replace("JARVIS", "Jarvis")
        prepared = re.sub(r"\*\*(.*?)\*\*", r"\1", prepared)
        prepared = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", prepared)
        prepared = re.sub(r"https?://\S+", "link", prepared)
        prepared = re.sub(r"\s+", " ", prepared)
        prepared = prepared.replace("|", ". ")
        prepared = prepared.replace("\n", ". ")
        return prepared.strip()

    def _build_prosody_variants(self, text: str):
        prepared = self._prepare_speech_text(text)
        if not prepared:
            return "", ""

        prosody_plain = re.sub(r",\s*", ", ... ", prepared)
        prosody_plain = re.sub(r"\s+", " ", prosody_plain).strip()

        is_question = prosody_plain.endswith("?")
        pitch = "+8%" if is_question else "-4%"

        ssml_text = html.escape(prosody_plain)
        ssml_text = ssml_text.replace(",", ", <break time=\"220ms\"/>")
        ssml = f"<speak><prosody pitch=\"{pitch}\">{ssml_text}</prosody></speak>"
        return prosody_plain, ssml

    def _chunk_text(self, text: str):
        clean = self._prepare_speech_text(text)
        if not clean:
            return []

        chunks = []
        current = ""
        sentences = re.split(r"(?<=[.!?])\s+", clean)

        for sentence in sentences:
            if not sentence:
                continue

            if len(current) + len(sentence) + 1 <= self.max_chunk_chars:
                current = f"{current} {sentence}".strip()
            else:
                if current:
                    chunks.append(current)
                if len(sentence) <= self.max_chunk_chars:
                    current = sentence
                else:
                    words = sentence.split()
                    part = ""
                    for word in words:
                        if len(part) + len(word) + 1 <= self.max_chunk_chars:
                            part = f"{part} {word}".strip()
                        else:
                            if part:
                                chunks.append(part)
                            part = word
                    current = part

        if current:
            chunks.append(current)
        return chunks

    def _play_audio_file(self, audio_path: Path) -> bool:
        players = [
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_path)],
            ["mpg123", "-q", str(audio_path)],
            ["mpv", "--really-quiet", "--no-video", str(audio_path)],
            ["vlc", "--intf", "dummy", "--play-and-exit", str(audio_path)],
        ]

        for command in players:
            if not shutil.which(command[0]):
                continue
            try:
                result = subprocess.run(command, capture_output=True, timeout=30)
                if result.returncode == 0:
                    return True
            except Exception:
                continue
        return False

    def _elevenlabs_voice_id(self) -> str:
        selected = (self.elevenlabs_voice or "").strip().lower()
        if not selected:
            selected = "adam"
        return ELEVENLABS_VOICE_IDS.get(selected, ELEVENLABS_VOICE_IDS["adam"])

    def _speak_elevenlabs(self, text: str) -> bool:
        if not self.use_neural_tts or not self.elevenlabs_api_key:
            return False

        prosody_plain, ssml = self._build_prosody_variants(text)
        if not prosody_plain:
            return False

        voice_id = self._elevenlabs_voice_id()
        endpoints = [
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?optimize_streaming_latency=2&output_format=mp3_44100_128",
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        ]

        model_candidates = []
        for model_name in [self.elevenlabs_model, "eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2"]:
            normalized_model = (model_name or "").strip()
            if normalized_model and normalized_model not in model_candidates:
                model_candidates.append(normalized_model)

        payloads = [
            {"text": ssml, "apply_text_normalization": "auto", "enable_ssml_parsing": True,
             "voice_settings": {"stability": 0.35, "similarity_boost": 0.85, "style": 0.25, "use_speaker_boost": True}},
            {"text": prosody_plain,
             "voice_settings": {"stability": 0.35, "similarity_boost": 0.85, "style": 0.25, "use_speaker_boost": True}},
        ]

        for model_name in model_candidates:
            for endpoint in endpoints:
                for index, payload in enumerate(payloads, start=1):
                    try:
                        payload_with_model = dict(payload)
                        payload_with_model["model_id"] = model_name

                        response = requests.post(
                            endpoint,
                            headers={
                                "xi-api-key": self.elevenlabs_api_key,
                                "Accept": "audio/mpeg",
                                "Content-Type": "application/json",
                            },
                            json=payload_with_model,
                            timeout=40,
                        )

                        if response.status_code != 200 or not response.content:
                            if VERBOSE_TTS and response.status_code >= 400:
                                error_preview = (response.text or "").strip().replace("\n", " ")[:240]
                                if error_preview:
                                    print(f"️ ElevenLabs HTTP {response.status_code}: {error_preview}")
                            continue

                        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                            tmp_file.write(response.content)
                            audio_path = Path(tmp_file.name)

                        try:
                            if self._play_audio_file(audio_path):
                                return True
                        finally:
                            try:
                                audio_path.unlink(missing_ok=True)
                            except Exception:
                                pass
                    except Exception as error:
                        if VERBOSE_TTS:
                            print(f"️ ElevenLabs exception: {error}")
                        continue

        return False

    def _speak_openai(self, text: str) -> bool:
        if not self.use_neural_tts or not self.openai_api_key:
            return False

        prosody_plain, _ = self._build_prosody_variants(text)
        if not prosody_plain:
            return False

        try:
            response = requests.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.openai_tts_model,
                    "voice": self.openai_voice,
                    "input": prosody_plain,
                    "response_format": "mp3",
                },
                timeout=40,
            )

            if response.status_code != 200 or not response.content:
                return False

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                tmp_file.write(response.content)
                audio_path = Path(tmp_file.name)

            try:
                return self._play_audio_file(audio_path)
            finally:
                try:
                    audio_path.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception:
            return False

    def list_voices(self):
        """List all available voices"""
        if not self.available_voices:
            return "No voices available"
        
        voice_list = "Available Voices:\n"
        for i, voice in enumerate(self.available_voices):
            current = " ← CURRENT" if i == self.current_voice else ""
            voice_list += f"{i}: {voice.name} (ID: {voice.id}){current}\n"
        
        return voice_list

    def change_voice(self, voice_index: int):
        """Change to a specific voice by index"""
        if not self.tts_engine:
            return " TTS engine not available"
        
        if voice_index < 0 or voice_index >= len(self.available_voices):
            return f" Invalid voice index. Please use 0-{len(self.available_voices)-1}"
        
        try:
            self.tts_engine.setProperty('voice', self.available_voices[voice_index].id)
            self.current_voice = voice_index
            voice_name = self.available_voices[voice_index].name
            return f" Voice changed to: {voice_name}"
        except Exception as e:
            return f" Failed to change voice: {e}"

    def change_voice_rate(self, rate: int):
        """Change speech rate (speed)"""
        if not self.tts_engine:
            return " TTS engine not available"
        
        try:
            # Validate rate (typical range: 50-300, default is ~200)
            if rate < 50:
                rate = 50
            elif rate > 300:
                rate = 300
                
            self.tts_engine.setProperty('rate', rate)
            return f" Speech rate set to: {rate}"
        except Exception as e:
            return f" Failed to change speech rate: {e}"

    def change_volume(self, volume: float):
        """Change volume level"""
        if not self.tts_engine:
            return " TTS engine not available"
        
        try:
            # Validate volume (0.0 to 1.0)
            if volume < 0.0:
                volume = 0.0
            elif volume > 1.0:
                volume = 1.0
                
            self.tts_engine.setProperty('volume', volume)
            return f" Volume set to: {volume*100}%"
        except Exception as e:
            return f" Failed to change volume: {e}"

    @PerformanceTracker.track_performance("Text to Speech")
    def speak_text(self, text: str):
        """Enhanced text speaking with error handling"""
        if self._stream_stop_event.is_set():
            return False

        if self._speak_elevenlabs(text):
            return True

        if self._speak_openai(text):
            return True

        if not self.tts_engine:
            if VERBOSE_TTS:
                detail = f" ({self._tts_init_error})" if self._tts_init_error else ""
                print(f" TTS engine not available{detail}")
            return False
            
        try:
            if VERBOSE_TTS:
                print(f" Speaking: {text}")
            
            # Clear any pending speech
            self.tts_engine.stop()
            self.tts_engine.setProperty('rate', self.default_rate)
            self.tts_engine.setProperty('volume', max(0.4, min(1.0, self.default_volume)))

            prosody_plain, _ = self._build_prosody_variants(text)
            chunks = self._chunk_text(prosody_plain)
            if not chunks:
                return False

            for chunk in chunks:
                if self._stream_stop_event.is_set():
                    return False
                self.tts_engine.say(chunk)
                self.tts_engine.runAndWait()
                time.sleep(0.05)
            
            if VERBOSE_TTS:
                print(f" Finished speaking: {text}")
            return True
                
        except Exception as e:
            if VERBOSE_TTS:
                print(f" Speech error: {str(e)}")
            # Try fallback method
            return self.speak_fallback(text)
    
    def speak_fallback(self, text: str):
        """Fallback speech method using system commands"""
        try:
            if VERBOSE_TTS:
                print(f" Trying fallback speech: {text}")
            
            # Try using espeak directly
            prepared = self._prepare_speech_text(text)
            result = subprocess.run([
                'espeak', '-v', 'en-us', '-s', str(self.default_rate), '-p', '45', '-a', '170', prepared
            ], capture_output=True, timeout=15)
            
            if result.returncode == 0:
                if VERBOSE_TTS:
                    print(" Fallback speech successful")
                return True
            else:
                if VERBOSE_TTS:
                    print(" Fallback speech failed")
                return False
                
        except Exception as e:
            if VERBOSE_TTS:
                print(f" Fallback speech error: {e}")
            return False
    
    @EnhancedErrorHandler.error_handler
    def speak(self, text: str):
        """Enhanced main speak function"""
        if not text or not text.strip():
            return "️ Please enter something to speak"
        
        success = self.speak_text(text)
        if success:
            return f" Said: {text}"
        else:
            if not self.tts_engine and self._tts_init_error:
                return f" Failed to speak: TTS unavailable ({self._tts_init_error})"
            return f" Failed to speak: {text}"

    def speak_streaming(self, text: str):
        clean = (text or "").strip()
        if not clean:
            return False

        self._stream_stop_event.clear()
        self._ensure_stream_worker()
        try:
            self._stream_queue.put_nowait(clean)
            return True
        except queue.Full:
            return False

    def stop_speaking(self):
        self._stream_stop_event.set()
        self.duck_output(True)
        self._drain_stream_queue()
        try:
            if self.tts_engine:
                self.tts_engine.stop()
        except Exception:
            pass
        with self._state_lock:
            self._speaking = False
        if self._stream_thread and self._stream_thread.is_alive():
            try:
                self._stream_thread.join(timeout=1.2)
            except Exception:
                pass
        self._stream_thread = None
        self.duck_output(False)
        return True

    def is_speaking(self):
        with self._state_lock:
            return bool(self._speaking)

    def on_speech_finished(self, callback=None):
        self._speech_finished_callback = callback
        return True

    def _ensure_stream_worker(self):
        if self._stream_thread and self._stream_thread.is_alive():
            return
        self._stream_thread = threading.Thread(target=self._stream_worker_loop, daemon=True)
        self._stream_thread.start()

    def _stream_worker_loop(self):
        while True:
            try:
                chunk = self._stream_queue.get(timeout=0.2)
            except queue.Empty:
                if self._stream_stop_event.is_set():
                    return
                continue

            if self._stream_stop_event.is_set():
                continue

            with self._state_lock:
                self._speaking = True
            try:
                self.speak_text(chunk)
            finally:
                with self._state_lock:
                    self._speaking = False
                if self._speech_finished_callback:
                    try:
                        self._speech_finished_callback(chunk)
                    except Exception:
                        pass

    def _drain_stream_queue(self):
        try:
            while True:
                self._stream_queue.get_nowait()
        except queue.Empty:
            return

    def duck_output(self, enable: bool):
        desired = bool(enable)
        if desired == self._ducked:
            return True

        if not shutil.which("pactl"):
            self._ducked = desired
            return False

        target_volume = self._duck_volume if desired else self._normal_volume
        try:
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", target_volume], capture_output=True, timeout=2)
            self._ducked = desired
            return True
        except Exception:
            return False

    def test_audio_system(self):
        """Test the audio system and provide diagnostics"""
        print("\n Audio System Diagnostics:")
        print(f"TTS Engine: {'Available' if self.tts_engine else 'Not Available'}")
        print(f"Available Voices: {len(self.available_voices)}")
        
        if self.tts_engine:
            print(f"Current Voice: {self.available_voices[self.current_voice].name if self.current_voice is not None else 'None'}")
            print(f"Speech Rate: {self.tts_engine.getProperty('rate')}")
            print(f"Volume: {self.tts_engine.getProperty('volume')}")
        
        # Test system audio
        try:
            result = subprocess.run(['which', 'espeak'], capture_output=True, text=True)
            if result.returncode == 0:
                print(" eSpeak is installed")
            else:
                print(" eSpeak is not installed")
        except:
            print(" Cannot check eSpeak installation")

_enhanced_jarvis = None


def _get_tts():
    global _enhanced_jarvis
    if _enhanced_jarvis is None:
        _enhanced_jarvis = EnhancedJARVIS()
    return _enhanced_jarvis

def EnhancedSpeak(text: str):
    """Enhanced speak function - MAIN FUNCTION FOR YOUR SYSTEM"""
    return _get_tts().speak(text)

def EnhancedChangeVoice(voice_index: int):
    """Change voice by index"""
    return _get_tts().change_voice(voice_index)

def EnhancedListVoices():
    """List all available voices"""
    return _get_tts().list_voices()

def EnhancedChangeRate(rate: int):
    """Change speech rate"""
    return _get_tts().change_voice_rate(rate)

def EnhancedChangeVolume(volume: float):
    """Change volume level"""
    return _get_tts().change_volume(volume)

def EnhancedTestAudio():
    """Test audio system"""
    return _get_tts().test_audio_system()

# Simple direct function for your main system
def speak(text):
    """Simple speak function for your main system"""
    return EnhancedSpeak(text)

if __name__ == "__main__":
    """
    Test mode for voice system
    """
    print("️  JARVIS VOICE SYSTEM TEST")
    print("=" * 50)
    
    # Run diagnostics
    tts = _get_tts()
    tts.test_audio_system()
    
    # Show available voices
    print("\n" + tts.list_voices())
    
    # Test speaking
    test_text = "Hello, I am JARVIS. My voice system is working."
    print(f"\n Testing voice: '{test_text}'")
    result = EnhancedSpeak(test_text)
    print(f"Result: {result}")
    
    # Voice changing options
    print("\n️  VOICE OPTIONS:")
    print("1. Test current voice")
    print("2. Change voice")
    print("3. Change speech speed")
    print("4. Change volume")
    print("5. Exit")
    
    while True:
        try:
            choice = input("\nChoose option (1-5): ").strip()
            
            if choice == "1":
                text = input("Enter text to speak: ")
                EnhancedSpeak(text)
                
            elif choice == "2":
                print("\n" + tts.list_voices())
                try:
                    voice_choice = int(input("Enter voice number: "))
                    result = EnhancedChangeVoice(voice_choice)
                    print(result)
                except ValueError:
                    print(" Please enter a valid number")
                    
            elif choice == "3":
                try:
                    rate = int(input("Enter speech rate (50-300): "))
                    result = EnhancedChangeRate(rate)
                    print(result)
                except ValueError:
                    print(" Please enter a valid number")
                    
            elif choice == "4":
                try:
                    volume = float(input("Enter volume (0.0-1.0): "))
                    result = EnhancedChangeVolume(volume)
                    print(result)
                except ValueError:
                    print(" Please enter a valid number")
                    
            elif choice == "5":
                print(" Voice test complete")
                break
            else:
                print(" Invalid choice")
                
        except KeyboardInterrupt:
            print("\n Voice test interrupted")
            break
        except Exception as e:
            print(f" Error: {e}")