import speech_recognition as sr
import pyttsx3


class VoiceEngine:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.engine = pyttsx3.init()

        self.engine.setProperty("rate", 170)
        self.engine.setProperty("volume", 1.0)

        voices = self.engine.getProperty("voices")
        if voices:
            # Change index to 1 or 2 if a different voice sounds better on this machine.
            self.engine.setProperty("voice", voices[0].id)

    def listen(self) -> str:
        """
        Capture voice and convert to text
        """
        with sr.Microphone() as source:
            print("Listening...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = self.recognizer.listen(source)

        try:
            text = self.recognizer.recognize_google(audio)
            print(f"You said: {text}")
            if "jarvis" not in text.lower():
                return ""
            return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            return ""

    def speak(self, text: str):
        """
        Convert text to speech
        """
        message = str(text or "").strip()
        if not message:
            return
        print(f"JARVIS: {message}")
        self.engine.say(message)
        self.engine.runAndWait()
