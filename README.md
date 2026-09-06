# Priya News AI 📰🤖

Priya News AI is an AI-powered news assistant designed to provide users with news updates, summaries, and detailed explanations through a conversational interface.

The project combines deterministic Python-based news processing with a local Large Language Model (LLM) for detailed follow-up explanations.

## ✨ Features

* 📰 Latest news and headline retrieval
* 🤖 AI-powered conversational news assistant
* 🔎 News search and topic-based queries
* 💬 Detailed explanations and follow-up questions
* 🧠 Local LLM integration using Gemma
* 🔊 Text-to-Speech support using Kokoro
* ⚡ Fast deterministic responses for normal headline queries
* 🔒 Local AI processing for supported components
* 🧩 Modular Python architecture

## 🏗️ Architecture

```text
User
 │
 ▼
Priya AI
 │
 ├── Query Classification
 │
 ├── News Retrieval
 │
 ├── Headline Response
 │
 ├── Detailed Explanation
 │       │
 │       └── Gemma 3
 │
 └── Text-to-Speech
         │
         └── Kokoro TTS
```

## 🛠️ Technologies

* Python
* Gemma 3
* Ollama
* Kokoro TTS
* ONNX Runtime
* CUDA / NVIDIA GPU acceleration
* REST APIs
* JSON
* Git & GitHub

## 📁 Project Structure

```text
news-ai-app/
│
├── app/
├── data/
├── services/
├── models/
├── tests/
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

> The exact directory structure may vary depending on the current implementation.

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/news-ai-app.git
cd news-ai-app
```

### 2. Create a virtual environment

Windows:

```bash
python -m venv .venv
```

Activate it:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 🤖 Gemma / Ollama Setup

Priya uses a local LLM for detailed explanations.

Install Ollama and download the required model:

```bash
ollama pull gemma3:4b
```

Make sure Ollama is running before starting the application.

## 🔐 Environment Variables

Create a `.env` file if the project requires environment variables.

Example:

```env
OLLAMA_URL=http://localhost:11434
MODEL_NAME=gemma3:4b
```

Do **not** commit `.env` or API keys to GitHub.

## 🚀 Running the Application

Activate the virtual environment:

```bash
.venv\Scripts\activate
```

Then start the application using the project's main entry point.

For example:

```bash
python main.py
```

> Replace the command above with the actual entry point used by the project.

## 🧠 AI Response Pipeline

Priya uses different processing paths depending on the user's request.

### Normal News Queries

```text
User Query
    ↓
Query Classification
    ↓
News Retrieval
    ↓
Headline Processing
    ↓
Response
```

These requests can be handled without sending every query to the LLM.

### Detailed Follow-Up Questions

```text
User Query
    ↓
Query Classification
    ↓
News Context
    ↓
Gemma 3
    ↓
Detailed Explanation
    ↓
Response
```

This approach helps reduce unnecessary LLM usage while keeping detailed conversations possible.

## 🔊 Text-to-Speech

Priya can use Kokoro TTS to convert generated responses into speech.

The TTS pipeline can use ONNX Runtime and GPU acceleration when the required NVIDIA CUDA environment is available.

## 🖥️ Hardware Acceleration

GPU acceleration is supported for compatible components.

Typical requirements may include:

* NVIDIA GPU
* Compatible NVIDIA driver
* CUDA
* cuDNN
* ONNX Runtime GPU
* Compatible Python packages

If GPU acceleration is unavailable, supported components can fall back to CPU execution.

## 🔒 Security

Never commit sensitive information such as:

* API keys
* Passwords
* Access tokens
* `.env` files
* Private credentials

Use environment variables for secrets.

## 📌 Project Status

🚧 **Active Development**

Priya News AI is continuously being improved with new AI, news-processing, voice, and automation capabilities.

## 🔮 Future Improvements

* Personalized news recommendations
* Multilingual news support
* Improved RAG pipeline
* Voice-based conversations
* Real-time news monitoring
* News credibility analysis
* More AI models
* Improved GPU optimization
* Mobile/web interface
* Automated news summarization

## 👨‍💻 Author

**Ratna Tej**

Computer Science / Artificial Intelligence & Machine Learning

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

