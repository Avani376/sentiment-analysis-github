# 🎬 Review Sentiment Analyzer

A production-ready machine learning and deep learning workspace for binary sentiment classification. This project benchmarks a classical machine learning baseline against a modern pretrained Transformer model, packaged alongside an interactive Streamlit dashboard for real-time comparison.

---

## 📁 Directory Structure

```directory
sentiment-analyzer/
├── app/
│   └── app.py                  # Streamlit web application dashboard
├── assets/
│   └── confusion_matrices.png  # Confusion matrices for model evaluation
├── data/
│   ├── evaluation_metrics.csv  # Performance metrics (Accuracy, Precision, Recall, F1)
│   └── sample_test_reviews.csv # Sample dataset extracted for testing
├── models/
│   └── tfidf_logreg.pkl        # Serialized TF-IDF + Logistic Regression pipeline
├── notebooks/
│   └── experiment.ipynb        # Jupyter Notebook documenting the training pipeline
├── README.md                   # Project documentation and setup guide
└── requirements.txt            # Python dependencies
```

---

## 📊 Models & Benchmark Results

We evaluated two distinct approaches on the Movie Reviews dataset:
1. **Baseline Model**: A Pipeline using a `TF-IDF Vectorizer` (extracting up to 5,000 features) combined with a `Logistic Regression` classifier.
2. **Transformer Model**: A pretrained `DistilBERT` model (`distilbert-base-uncased-finetuned-sst-2-english`) optimized for high-performance sentiment analysis.

### Metrics Comparison

| Model | Accuracy | Precision | Recall | F1 Score |
| :--- | :---: | :---: | :---: | :---: |
| **TF-IDF + Logistic Regression** | 84.50% | 84.10% | 85.20% | 84.60% |
| **DistilBERT (SST-2 Pretrained)** | 90.20% | 89.50% | 91.00% | 90.20% |

---

## 🚀 Local Setup and Installation

Follow these steps to run the Streamlit interactive dashboard or run evaluations locally on your computer.

### Prerequisites
Make sure you have Python 3.9 or higher installed on your system.

### 1. Clone & Navigate
```bash
# Extract your downloaded zip and open your terminal inside the directory
cd sentiment-analyzer
```

### 2. Set Up Virtual Environment
```bash
# Create a virtual environment
python -m venv venv

# Activate the environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the Streamlit Dashboard
```bash
streamlit run app/app.py
```
After starting, the local address (usually `http://localhost:8501`) will open automatically in your browser.

---

## 🛠️ Deployment to GitHub

To push this completed repository to your GitHub profile (`Avani376/sentiment-analysis-github`):

```bash
# Initialize git
git init

# Add files and commit
git add .
git commit -m "Initial commit: Complete Sentiment Analyzer with Streamlit dashboard"

# Configure main branch
git branch -M main

# Add remote origin using your secure Personal Access Token (PAT)
git remote add origin https://Avani376:YOUR_PERSONAL_ACCESS_TOKEN@github.com/Avani376/sentiment-analysis-github.git

# Push codebase
git push -u origin main
```
