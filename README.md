# 🛡️ AI Cyber Scam Detector — Enterprise Edition

An intelligent, machine learning-powered system that detects cyber scams, phishing attempts, and spam messages in real-time. Built with FastAPI, React, and scikit-learn.

---

## 📋 Project Overview

**AI Cyber Scam Detector** is a full-stack web application that uses machine learning to automatically classify messages as **SAFE** or **SCAM**. It analyzes SMS, email, WhatsApp-style text, and other message formats to identify potential cyber threats before they cause harm.

### Problem Statement

Cyber scams and phishing attacks are increasing at an alarming rate. Every day, millions of people receive fraudulent messages designed to steal passwords, money, or personal information. Traditional rule-based filters are easily bypassed by sophisticated attackers. This project uses machine learning to detect scam patterns automatically and provide explainable results.

### Objectives

1. Build a machine learning model that accurately classifies messages as safe or scam
2. Create a user-friendly web interface for real-time scam detection
3. Provide explainable AI results with confidence scores and risk levels
4. Implement enterprise-grade security and observability
5. Deliver a complete, production-ready system suitable for demonstration

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Real-time Detection** | Analyze any message instantly with ML-powered predictions |
| **Explainable AI** | Get keywords, reasons, and safety advice for every prediction |
| **Confidence Scoring** | See how confident the model is in its prediction |
| **Risk Levels** | LOW, MEDIUM, or HIGH risk classification |
| **User Authentication** | Secure signup/login with JWT tokens |
| **Scan History** | Track and review past analyses |
| **Dashboard** | View statistics and recent scans |
| **Model Information** | See model accuracy, precision, and recall metrics |
| **Responsive UI** | Works on desktop, tablet, and mobile |
| **Docker Support** | Containerized deployment ready |

---

## 🏗️ System Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│   React     │────▶│   FastAPI    │────▶│   ML Model   │     │  SQLite/    │
│   Frontend  │     │   Backend    │     │  (Pipeline)  │────▶│  PostgreSQL │
│   (Vite)    │     │   (Port 8000)│     │  TF-IDF +    │     │  Database   │
└─────────────┘     └──────────────┘     │  Logistic    │     └─────────────┘
       │                  │              │  Regression  │
       │                  │              └──────────────┘
       │                  │
       │                  └──▶ /health, /predict, /api/detect, /api/model-info
       │
       └──▶ http://localhost:3000 (Frontend)
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, Vite 5, Tailwind CSS 3, Axios |
| **Backend** | FastAPI, Python 3.11, SQLModel, Pydantic |
| **ML** | scikit-learn (TF-IDF + Logistic Regression) |
| **Database** | SQLite (dev), PostgreSQL (production) |
| **Auth** | JWT with refresh tokens, bcrypt |
| **Deployment** | Docker, Docker Compose |

---

## 🤖 Machine Learning Workflow

### Dataset

The model is trained on a **curated, reproducible corpus** of SMS/email-style messages:
- **1,086 messages** total
- **799 scam** messages covering phishing, impersonation, prize scams, tax fraud, delivery scams, crypto schemes, and more
- **287 safe** messages covering normal human communication and benign notifications
- Built deterministically from curated templates and word banks for full reproducibility

### Preprocessing Pipeline

1. **Text Cleaning**: Remove null bytes, normalize whitespace
2. **TF-IDF Vectorization**: Convert text to numerical features
   - Max features: 50,000
   - N-grams: 1-2 (captures word pairs like "free prize")
   - Sublinear TF: Reduces impact of frequent words
3. **Logistic Regression Classifier**:
   - Class-balanced to handle imbalanced data
   - Trained with stratified 80/20 split

### Model Performance

| Metric | Score |
|--------|-------|
| **Accuracy** | 96.3% |
| **Precision** | 100.0% |
| **Recall** | 95.0% |
| **F1 Score** | 97.4% |

### Model Artifact

- **Location**: `models/exports/best_model.pkl`
- **Format**: Complete scikit-learn Pipeline (TF-IDF + Logistic Regression)
- **Size**: ~35 KB
- **Classes**: `['safe', 'scam']`

---

## 🔌 API Documentation

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API information |
| `GET` | `/health` | Health check |
| `GET` | `/health/live` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe |
| `POST` | `/predict` | Analyze text (detailed response) |
| `POST` | `/api/predict` | Alias for `/predict` |
| `POST` | `/api/detect` | Analyze text (simplified response) |
| `GET` | `/api/model-info` | Model information |
| `POST` | `/auth/signup` | Register user |
| `POST` | `/auth/login` | Login |
| `POST` | `/auth/refresh` | Refresh token |
| `GET` | `/dashboard` | Dashboard statistics |
| `GET` | `/history` | User scan history |

### Example Request

```json
POST /api/detect
{
  "text": "Congratulations! You have won £1000. Click this link now."
}
```

### Example Response

```json
{
  "prediction": "SCAM",
  "confidence": 0.968,
  "risk_level": "HIGH",
  "message": "Potential scam detected",
  "explanation": {
    "keywords": ["no obvious trigger words"],
    "reason": "The message contains high-risk urgency and impersonation patterns commonly used in scams.",
    "risk_level": "High",
    "safety_advice": "Do not click links, share credentials, or respond to the sender.",
    "simple_explanation": "This looks like a scam because it pressures you to act fast and may try to steal your password or money."
  }
}
```

---

## 🚀 Installation & Setup

### Prerequisites

- **Python 3.11+**
- **Node.js 20+**
- **npm** (comes with Node.js)

### Step 1: Clone the Repository

```bash
git clone https://github.com/sanketpopalghat26-lang/AI-Cyber-Scam-Detector.git
cd AI-Cyber-Scam-Detector
```

### Step 2: Backend Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\activate

# Activate (Mac/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Start the backend
cd backend
uvicorn app.main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### Step 3: Frontend Setup

```bash
# In a new terminal
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Step 4: Train the Model (Optional)

The model is already trained and saved. To retrain:

```bash
python model/train_final.py
```

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_api_endpoints.py -v

# Run with coverage
python -m pytest tests/ --cov=backend --cov-report=term-missing
```

**Current Test Results**: 572 passed, 1 skipped

---

## 🐳 Docker Deployment

```bash
# Validate configuration
docker compose config

# Build and start all services
docker compose up --build

# Stop services
docker compose down
```

Services:
- **Frontend**: http://localhost:3000
- **Backend**: http://localhost:8000
- **Database**: PostgreSQL on port 5432

---

## 📝 Sample Inputs & Outputs

### Example 1: Scam Message
**Input**: "Congratulations! You won £1000 cash. Call now to claim your prize."
**Output**: `SCAM` | Confidence: 96.8% | Risk: HIGH

### Example 2: Safe Message
**Input**: "Hey, are you free this evening? Let's meet tomorrow."
**Output**: `SAFE` | Confidence: 83.2% | Risk: LOW

### Example 3: Phishing Attempt
**Input**: "Your account has been selected for a reward. Click the link immediately to claim."
**Output**: `SCAM` | Confidence: 84.6% | Risk: HIGH

### Example 4: Normal Message
**Input**: "Can you send me the project report before 5 PM?"
**Output**: `SAFE` | Confidence: 72.6% | Risk: LOW

---

## 📁 Project Structure

```
AI-Cyber-Scam-Detector/
│
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py            # Application entry point
│   │   ├── core/              # Security, middleware, config
│   │   ├── models.py          # Database models
│   │   └── schemas.py         # API schemas
│   ├── requirements.txt       # Python dependencies
│   └── Dockerfile             # Backend container
│
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── App.jsx            # Main application
│   │   ├── config.js          # Configuration
│   │   └── main.jsx           # Entry point
│   ├── package.json           # npm dependencies
│   └── Dockerfile             # Frontend container
│
├── models/
│   └── exports/
│       ├── best_model.pkl     # Trained ML model
│       └── metrics.json       # Model performance metrics
│
├── data/
│   └── smsspamcollection/     # Training dataset
│
├── model/
│   └── train_final.py         # Model training script
│
├── tests/                      # Test suite
├── docs/                       # Documentation
├── docker-compose.yml          # Docker orchestration
├── .env.example                # Environment template
└── README.md                   # This file
```

---

## 🔒 Security Features

- **JWT Authentication** with refresh tokens
- **Password hashing** with bcrypt
- **Input validation** and sanitization
- **Rate limiting** to prevent abuse
- **CORS** configuration
- **Security headers** (CSP, HSTS, X-Frame-Options)
- **Audit logging** for all actions
- **No hardcoded secrets** - all via environment variables

---

## ⚠️ Limitations

1. **English-only**: The model is trained on English SMS messages
2. **SMS-focused**: Best performance on short text messages
3. **Static model**: Model doesn't update in real-time
4. **No URL analysis**: Doesn't inspect linked websites
5. **False positives**: Some legitimate marketing messages may be flagged

---

## 🔮 Future Scope

1. **Multi-language support** using multilingual transformers
2. **URL and domain reputation analysis**
3. **Real-time model retraining** with user feedback
4. **Image-based scam detection** (screenshots, QR codes)
5. **Browser extension** for automatic page scanning
6. **Mobile app** for SMS/WhatsApp integration
7. **Deep learning models** (BERT, RoBERTa) for better accuracy
8. **Integration with threat intelligence feeds**

---

## 👥 Team Contribution

| Team Member | Contribution |
|-------------|-------------|
| [Your Name] | ML model development, backend API |
| [Team Member 2] | Frontend UI, integration |
| [Team Member 3] | Testing, documentation |

---

## 📄 License

This project is for educational purposes. See [LICENSE](LICENSE) for details.

---

## 📚 Additional Documentation

- [Demo Guide](PROJECT_DEMO.md) - Step-by-step demonstration script
- [Viva Questions](VIVA_QUESTIONS.md) - Common interview questions and answers
- [API Reference](docs/API.md) - Complete API documentation
- [Architecture](docs/architecture.md) - System design details