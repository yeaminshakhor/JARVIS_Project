"""Simple speech-recognition voice loop for JARVIS command processing."""

from __future__ import annotations

import speech_recognition as sr
import pyttsx3


class VoiceInput:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    def listen(self):
        with sr.Microphone() as source:
            print("Listening...")
            audio = self.recognizer.listen(source)

        try:
            text = self.recognizer.recognize_google(audio)
            print("You said:", text)
            return text
        except Exception:
            return ""


class VoiceOutput:
    def __init__(self):
        self.engine = pyttsx3.init()

    def speak(self, text: str):
        message = str(text or "").strip()
        if not message:
            return
        self.engine.say(message)
        self.engine.runAndWait()


class VoiceAssistant:
    def __init__(self, jarvis):
        self.jarvis = jarvis
        self.input = VoiceInput()
        self.output = VoiceOutput()

    def run(self):
        while True:
            command = self.input.listen()

            if not command:
                continue

            if "exit" in command.lower():
                self.output.speak("Goodbye")
                break

            result = self.jarvis.process_command(command)
            print("JARVIS:", result)
            self.output.speak(str(result))
