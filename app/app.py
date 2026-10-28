import os
import joblib
import streamlit as st
import pandas as pd
from transformers import pipeline

st.set_page_config(page_title='Review Sentiment Analyzer', page_icon='🎬', layout='wide')

@st.cache_resource
def load_models():
    model_path = 'models/tfidf_logreg.pkl'
    if os.path.exists(model_path):
        pipe = joblib.load(model_path)
    else:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        pipe = Pipeline([
            ('tfidf', TfidfVectorizer(max_features=5000, stop_words='english')),
            ('clf', LogisticRegression())
        ])
    
    hf_pipe = pipeline(
        'sentiment-analysis',
        model='distilbert/distilbert-base-uncased-finetuned-sst-2-english',
        truncation=True,
        max_length=512
    )
    return pipe, hf_pipe

baseline_model, hf_model = load_models()

st.title('🎬 Review Sentiment Analyzer')
st.markdown('Compare a **TF-IDF + Logistic Regression** baseline against a pretrained **Hugging Face Transformer (`DistilBERT`)**.')

user_input = st.text_area('Enter your review text:', 'The acting was absolutely brilliant, but the second half of the movie was a bit slow.')

if st.button('Analyze Sentiment', type='primary'):
    probs = baseline_model.predict_proba([user_input])[0]
    base_pred_idx = int(probs[1] >= 0.5)
    base_label = 'POSITIVE' if base_pred_idx == 1 else 'NEGATIVE'
    base_conf = float(probs[base_pred_idx])

    hf_res = hf_model(user_input)[0]
    hf_label = hf_res['label']
    hf_conf = float(hf_res['score'])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('### 📊 Baseline: TF-IDF + LogReg')
        st.write(f'**Prediction:** {base_label} ({base_conf*100:.2f}%)')
    with col2:
        st.markdown('### 🤗 Transformer: DistilBERT')
        st.write(f'**Prediction:** {hf_label} ({hf_conf*100:.2f}%)')
