from pathlib import Path

import joblib
import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_MODEL_PATH = PROJECT_ROOT / "models" / "tfidf_logreg.pkl"
METRICS_PATH = PROJECT_ROOT / "data" / "evaluation_metrics.csv"
CONFUSION_MATRIX_PATH = PROJECT_ROOT / "assets" / "confusion_matrices.png"
TRANSFORMER_MODEL_NAME = "distilbert/distilbert-base-uncased-finetuned-sst-2-english"

st.set_page_config(page_title="Review Sentiment Analyzer", page_icon="🎬", layout="wide")


@st.cache_resource(show_spinner="Loading the saved baseline model…")
def load_baseline_model():
    """Load the committed baseline artifact once without retraining it."""
    if not BASELINE_MODEL_PATH.is_file():
        raise FileNotFoundError(
            "The saved baseline model was not found at "
            f"{BASELINE_MODEL_PATH.relative_to(PROJECT_ROOT)}."
        )

    baseline_model = joblib.load(BASELINE_MODEL_PATH)
    if not hasattr(baseline_model, "predict") or not hasattr(
        baseline_model, "predict_proba"
    ):
        raise TypeError("The saved baseline artifact is not a probabilistic classifier.")

    return baseline_model


@st.cache_resource(show_spinner="Loading the public DistilBERT model…")
def load_transformer_model():
    """Load the public tokenizer and classifier only when analysis needs them."""
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(TRANSFORMER_MODEL_NAME)
    transformer_model = AutoModelForSequenceClassification.from_pretrained(
        TRANSFORMER_MODEL_NAME
    )
    transformer_model.eval()
    return tokenizer, transformer_model


@st.cache_data
def load_metrics(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def display_label(raw_label) -> str:
    """Normalize the binary labels used by the committed baseline artifact."""
    normalized = str(raw_label).strip().lower()
    if normalized in {"1", "positive", "pos"}:
        return "POSITIVE"
    if normalized in {"0", "negative", "neg"}:
        return "NEGATIVE"
    return str(raw_label).upper()


def baseline_prediction(model, text: str) -> tuple[str, float]:
    """Return the label and probability without assuming a probability-column order."""
    prediction = model.predict([text])[0]
    probabilities = model.predict_proba([text])[0]
    classes = list(model.classes_)
    predicted_index = classes.index(prediction)
    return display_label(prediction), float(probabilities[predicted_index])


def transformer_prediction(text: str) -> tuple[str, float]:
    """Run direct PyTorch inference without importing Transformers' pipeline module."""
    import torch

    tokenizer, transformer_model = load_transformer_model()
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        logits = transformer_model(**inputs).logits[0]
        probabilities = torch.softmax(logits, dim=-1)

    predicted_index = int(torch.argmax(probabilities).item())
    raw_label = transformer_model.config.id2label.get(
        predicted_index, str(predicted_index)
    )
    return display_label(raw_label), float(probabilities[predicted_index].item())


try:
    baseline_model = load_baseline_model()
except Exception:
    st.error(
        "The saved baseline model could not be loaded. Verify the committed model artifact "
        "and the pinned dependencies, then restart the app."
    )
    st.stop()


st.title("🎬 Review Sentiment Analyzer")
st.markdown(
    "Compare a **TF-IDF + Logistic Regression** baseline against a pretrained "
    "**Hugging Face Transformer (`DistilBERT`)**."
)

user_input = st.text_area(
    "Enter your review text:",
    "The acting was absolutely brilliant, but the second half of the movie was a bit slow.",
)

if st.button("Analyze Sentiment", type="primary"):
    review_text = user_input.strip()
    if not review_text:
        st.warning("Enter a review before running sentiment analysis.")
    else:
        try:
            with st.spinner("Analyzing the review with the saved baseline…"):
                base_label, base_confidence = baseline_prediction(
                    baseline_model, review_text
                )

            transformer_error = False
            try:
                hf_label, hf_confidence = transformer_prediction(review_text)
            except Exception:
                transformer_error = True

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 📊 Baseline: TF-IDF + LogReg")
                st.metric(
                    "Prediction", base_label, f"{base_confidence * 100:.2f}% confidence"
                )
            with col2:
                st.markdown("### 🤗 Transformer: DistilBERT")
                if transformer_error:
                    st.warning(
                        "DistilBERT is unavailable. Check the network connection and try again; "
                        "the baseline result is still valid."
                    )
                else:
                    st.metric(
                        "Prediction",
                        hf_label,
                        f"{hf_confidence * 100:.2f}% confidence",
                    )
            if not transformer_error:
                st.caption(
                    "Confidence is each model's predicted-class probability; scores are not "
                    "calibrated for comparison across models."
                )
        except Exception:
            st.error(
                "Analysis could not be completed. Please try again after confirming that "
                "the model files and network connection are available."
            )

st.divider()
with st.expander("Reference evaluation artifacts"):
    st.caption(
        "The repository includes these committed reference artifacts. The original "
        "training workflow and full evaluation split are not included, so the reported "
        "benchmark values are not independently reproducible from this repository alone."
    )

    if METRICS_PATH.is_file():
        try:
            st.dataframe(
                load_metrics(str(METRICS_PATH)),
                hide_index=True,
                use_container_width=True,
            )
        except Exception:
            st.info("The evaluation metrics file is present but could not be read.")
    else:
        st.info("No evaluation metrics file is included with this checkout.")

    if CONFUSION_MATRIX_PATH.is_file():
        st.image(
            str(CONFUSION_MATRIX_PATH),
            caption="Committed baseline-model confusion matrix artifact",
            use_container_width=False,
        )
    else:
        st.info("No confusion-matrix image is included with this checkout.")
