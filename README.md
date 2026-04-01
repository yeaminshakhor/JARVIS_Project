A powerful, feature-rich AI assistant with voice control, multi-platform integration, and advanced automation capabilities.

> **⚠️ Note:** This project is under active development. Some features may be unstable, and performance optimizations are ongoing.

## ✨ Features

### 🎯 Core AI
- Multi-provider AI (OpenAI, Groq, Cohere, DeepSeek, xAI)
- Streaming responses with automatic failover
- 24-message context window
- Intent classification (85%+ accuracy)

### 🎤 Voice System
- Wake word detection ("Hey Jarvis")
- Multiple TTS engines (ElevenLabs, pyttsx3, OpenAI)
- Voice activity detection
- Real-time streaming TTS

### 🔐 Security
- Face recognition authentication
- Emergency passphrase override
- Command sanitization
- Audit logging

### 📱 Messaging
- Email (IMAP/SMTP)
- Facebook Messenger
- WhatsApp Business
- Unified channel manager

### 🖥️ UI
- Cyberpunk-themed GUI
- Interactive maps
- Real-time system monitoring
- Orbit notification system

### 🔍 Research
- Wikipedia summaries
- Academic paper search (arXiv, CrossRef)
- Topic deep-dive
- Note saving

## 🚨 Current Limitations

### Known Issues
- **System Stability:** The application may occasionally crash, especially when handling multiple concurrent operations or during voice processing
- **Performance:** Some lag may be experienced during:
  - Voice recognition with wake word detection
  - API switching between AI providers
  - Loading the 3D maps panel
  - Processing large context windows (24+ messages)
  - Concurrent messaging channel operations

### System Requirements
- Minimum 8GB RAM recommended (16GB for optimal performance)
- GPU recommended for face recognition and local LLM
- Stable internet connection for API-based features
- Microphone required for voice features
- Webcam optional for face recognition

## 🔑 Required API Keys

The following API keys are needed for full functionality. Add them to your `.env` file:

### Essential Keys
| Service | Key Variable | Purpose | Get From |
|---------|--------------|---------|----------|
| OpenAI | `OPENAI_API_KEY` | Primary AI model (GPT-4o) | [OpenAI Platform](https://platform.openai.com/api-keys) |

### Optional but Recommended
| Service | Key Variable | Purpose | Get From |
|---------|--------------|---------|----------|
| Cohere | `COHERE_API_KEY` | Intent classification (improves accuracy) | [Cohere Dashboard](https://dashboard.cohere.ai/api-keys) |
| ElevenLabs | `ELEVENLABS_API_KEY` | Premium voice synthesis with emotional prosody | [ElevenLabs](https://elevenlabs.io/speech-synthesis) |

### AI Provider Options (Choose at least one)
| Service | Key Variable | Purpose | Get From |
|---------|--------------|---------|----------|
| Groq | `GROQ_API_KEY` | Fast LLM inference (Llama-3, Mixtral) | [Groq Console](https://console.groq.com/keys) |
| DeepSeek | `DEEPSEEK_API_KEY` | Alternative AI provider | [DeepSeek Platform](https://platform.deepseek.com/) |
| xAI (Grok) | `XAI_API_KEY` | xAI Grok model | [xAI Console](https://console.x.ai/) |

### Messaging Integration Keys (Optional)
| Service | Key Variable | Purpose | Get From |
|---------|--------------|---------|----------|
| Facebook | `FACEBOOK_PAGE_ACCESS_TOKEN` | Messenger integration | [Facebook Developers](https://developers.facebook.com/) |
| WhatsApp | `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp Business API | [WhatsApp Business API](https://business.whatsapp.com/) |

### Search & Research Keys (Optional)
| Service | Key Variable | Purpose | Get From |
|---------|--------------|---------|----------|
| Tavily | `TAVILY_API_KEY` | AI-optimized search | [Tavily](https://tavily.com/) |
| Serper | `SERPER_API_KEY` | Google search API | [Serper.dev](https://serper.dev/) |
| NewsAPI | `NEWS_API_KEY` | News-specific search | [NewsAPI](https://newsapi.org/) |

### Image Generation Keys (Optional)
| Service | Key Variable | Purpose | Get From |
|---------|--------------|---------|----------|
| Stability AI | `STABILITY_API_KEY` | AI image generation | [Stability AI](https://platform.stability.ai/) |
| Replicate | `REPLICATE_API_KEY` | Diverse image models | [Replicate](https://replicate.com/) |

## 🚀 Quick Start
