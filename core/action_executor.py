import logging
import webbrowser
import re
import shutil
import subprocess
import requests
from urllib.parse import quote_plus

from .exceptions import APIError, AuthError, ResourceError, JarvisError

logger = logging.getLogger(__name__)

try:
    from .Assistant import EnhancedProfessionalAIAutomation
    from .search import EnhancedGoogleSearch, EnhancedProcessQuery
    from .image_gen import EnhancedGenerateImages
    from .chatbot import SmartChatBot
    from .model import QuickLocalClassifier, EnhancedFirstLayerDMM
    AUTOMATION_AVAILABLE = True
except ImportError as e:
    logger.warning("Failed to import backend modules: %s", e)
    AUTOMATION_AVAILABLE = False


class ActionExecutor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize modules only if available
        self.automation = None
        self.realtime_search = None
        self.realtime_process = None
        self.image_gen = None
        self.chatbot = None
        self.classifier = None
        self.local_classifier = None
        self.auth = None
        
        if AUTOMATION_AVAILABLE:
            try:
                self.automation = EnhancedProfessionalAIAutomation()
                self.realtime_search = EnhancedGoogleSearch
                self.realtime_process = EnhancedProcessQuery
                self.image_gen = EnhancedGenerateImages
                self.chatbot = SmartChatBot
                try:
                    self.classifier = EnhancedFirstLayerDMM
                    self.local_classifier = QuickLocalClassifier()
                except Exception:
                    self.classifier = None
                    self.local_classifier = None

                try:
                    from .auth import EnhancedAdminOnlyAuth
                    self.auth = EnhancedAdminOnlyAuth
                except Exception:
                    self.auth = None

                self.logger.info(" ActionExecutor initialized with all modules.")
            except Exception as e:
                self.logger.error(f" Failed to initialize some modules: {e}")
        else:
            self.logger.warning("️ Running in limited mode - backend modules not available")

    def classify_query(self, query: str):
        text = (query or "").strip()
        if not text:
            return []

        lower = text.lower()
        if lower.startswith("realtime "):
            return [text]
        if lower.startswith("google search "):
            return [text]
        if lower.startswith("search "):
            return [f"google search {text[7:].strip()}"]

        if self.classifier:
            try:
                result = self.classifier(text)
                if isinstance(result, list) and result:
                    return result
            except Exception as exc:
                self.logger.debug(f"Classifier fallback due to error: {exc}")

        if self.local_classifier:
            try:
                local = self.local_classifier.predict(text)
                if local and getattr(local, "intent", ""):
                    return [local.as_route()]
            except Exception as exc:
                self.logger.debug("Local classifier fallback failed: %s", exc)

        return [f"general {text}"]

    def execute_query(self, query: str):
        routes = self.classify_query(query)
        responses = []

        for route in routes:
            try:
                response = self.execute_route(route, original_query=query)
                if response:
                    responses.append(response)
            except JarvisError as exc:
                self.logger.debug("Route %s skipped: %s", route, exc)
                continue

        if not responses:
            text = (query or "").strip()
            if not text:
                return "I did not receive a query."
            return f"I could not route that request yet, but I understood: {text}"

        return "\n".join([item for item in responses if item]).strip()

    def execute_route(self, route: str, original_query: str = ""):
        text = (route or "").strip()
        low = text.lower()
        if not text:
            raise ResourceError("Empty route")

        if low == "exit":
            return "Exit requested"

        if low.startswith("general "):
            question = text[8:].strip() or (original_query or "")
            if self.chatbot:
                try:
                    return str(self.chatbot(question))
                except Exception as exc:
                    raise APIError(f"Chatbot failed: {exc}") from exc
            raise ResourceError("Chatbot unavailable")

        if low.startswith("realtime "):
            topic = text[9:].strip() or (original_query or "")
            if self.realtime_process:
                try:
                    response = str(self.realtime_process(topic))
                    if response.strip() and "Unable to generate response" not in response:
                        return response
                    if self.realtime_search:
                        return str(self.realtime_search(topic))
                    return response
                except Exception as exc:
                    if self.realtime_search:
                        try:
                            return str(self.realtime_search(topic))
                        except Exception:
                            pass
                    raise APIError(f"Realtime search failed: {exc}") from exc
            raise ResourceError("Realtime processor unavailable")

        if low.startswith("google search "):
            topic = text[14:].strip() or (original_query or "")
            if self.realtime_search:
                try:
                    return str(self.realtime_search(topic))
                except Exception as exc:
                    raise APIError(f"Google search failed: {exc}") from exc
            raise ResourceError("Google search backend unavailable")

        if low.startswith("youtube search "):
            topic = text[15:].strip() or (original_query or "")
            if topic:
                webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(topic)}")
                return f"Opened YouTube search for: {topic}"
            raise ResourceError("Missing YouTube search topic")

        if low.startswith("play "):
            topic = text[5:].strip() or (original_query or "")
            if topic:
                if self._open_youtube_first_video(topic):
                    return f"Playing on YouTube: {topic}"
                webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(topic)}")
                return f"Opened media search for: {topic}"
            raise ResourceError("Missing media topic")

        if low.startswith("generate image "):
            prompt = text[len("generate image "):].strip() or (original_query or "")
            if self.image_gen:
                try:
                    return str(self.image_gen(prompt))
                except Exception as exc:
                    raise APIError(f"Image generation failed: {exc}") from exc
            raise ResourceError("Image generation backend unavailable")

        if low.startswith("content "):
            topic = text[8:].strip() or (original_query or "")
            if self.chatbot:
                try:
                    content_query = f"Write useful content about: {topic}"
                    return str(self.chatbot(content_query))
                except Exception as exc:
                    raise APIError(f"Content generation failed: {exc}") from exc
            raise ResourceError("Content generator unavailable")

        if low.startswith("open "):
            youtube_play_topic = self._extract_youtube_play_topic(low)
            if youtube_play_topic is not None:
                if self.automation:
                    try:
                        self.automation.open_website("youtube")
                    except Exception:
                        pass
                else:
                    webbrowser.open("https://youtube.com")

                if youtube_play_topic and self._open_youtube_first_video(youtube_play_topic):
                    return f"Opened YouTube and started: {youtube_play_topic}"

                return "Opened YouTube. I couldn't auto-start playback in this browser session."

            target = self._normalize_open_target(text[5:].strip())
            if not target:
                raise ResourceError("Missing open target")

            if self.automation:
                if self._is_likely_website_target(target):
                    try:
                        return str(self.automation.open_website(target))
                    except Exception:
                        pass
                return str(self.automation.open_application(target))
            if target:
                webbrowser.open(f"https://www.google.com/search?q={quote_plus(target)}")
                return f"Opened search for {target}"
            raise ResourceError("Could not determine open target")

        if low.startswith("system "):
            command = low[7:].strip()
            if not self.automation:
                raise ResourceError("Automation backend unavailable")

            try:
                if any(word in command for word in ["mute", "silence"]):
                    return str(self.automation.mute_volume())
                if any(word in command for word in ["volume up", "increase volume"]):
                    return str(self.automation.volume_up())
                if any(word in command for word in ["volume down", "decrease volume"]):
                    return str(self.automation.volume_down())
            except Exception as exc:
                raise APIError(f"System command failed: {exc}") from exc

            raise ResourceError("Unknown system command")

        if low.startswith("auth status"):
            if self.auth:
                try:
                    auth_obj = self.auth()
                    state = "configured" if auth_obj.setup_completed else "not configured"
                    return f"Authentication is {state}"
                except Exception as exc:
                    raise AuthError(f"Auth status failed: {exc}") from exc
            raise ResourceError("Auth backend unavailable")

        raise ResourceError("No matching route")

    def _normalize_open_target(self, target: str) -> str:
        text = (target or "").strip().lower()
        if not text:
            return ""

        text = re.sub(r"^open\s+", "", text).strip()
        text = re.sub(r"\s+", " ", text)

        split_tokens = [" and ", ",", " then ", " with "]
        for token in split_tokens:
            if token in text:
                text = text.split(token, 1)[0].strip()

        return text

    def _is_likely_website_target(self, target: str) -> bool:
        website_aliases = {
            "youtube", "facebook", "google", "gmail", "github", "twitter",
            "instagram", "whatsapp", "reddit", "linkedin", "netflix",
            "amazon", "spotify"
        }

        candidate = (target or "").strip().lower()
        if not candidate:
            return False
        if candidate in website_aliases:
            return True
        return "." in candidate or candidate.startswith(("http://", "https://"))

    def _extract_youtube_play_topic(self, low_text: str):
        text = (low_text or "").strip().lower()
        if not text.startswith("open youtube"):
            return None

        match = re.search(r"open\s+youtube\s*(?:and|then)?\s*play\s*(.*)$", text)
        if not match:
            return ""

        topic = (match.group(1) or "").strip()
        fillers = {"", "it", "something", "music", "video"}
        if topic in fillers:
            return topic
        return topic

    def _open_youtube_first_video(self, topic: str) -> bool:
        clean_topic = (topic or "").strip()
        if not clean_topic:
            return False

        ytdlp = shutil.which("yt-dlp")
        if ytdlp:
            try:
                result = subprocess.run(
                    [ytdlp, "--no-warnings", "--skip-download", "--get-id", f"ytsearch1:{clean_topic}"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if result.returncode == 0:
                    video_id = (result.stdout or "").strip().splitlines()[0].strip()
                    if video_id:
                        webbrowser.open(f"https://www.youtube.com/watch?v={video_id}&autoplay=1")
                        return True
            except Exception:
                pass

        try:
            search_url = f"https://www.youtube.com/results?search_query={quote_plus(clean_topic)}"
            response = requests.get(
                search_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            if response.status_code != 200:
                return False

            match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', response.text)
            if not match:
                return False

            video_id = match.group(1)
            watch_url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
            webbrowser.open(watch_url)
            return True
        except Exception:
            return False