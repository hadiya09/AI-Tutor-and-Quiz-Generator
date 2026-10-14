# AI Tutor & Quiz Generator (Streamlit)

## Features
- Generate a simple explanation on a topic.
- Download the explanation as a PDF.
- Generate 5–20 multiple-choice questions.
- Submit answers and see score, correct answers, and explanations.

## Run locally
1. Install packages:
   `pip install -r requirements.txt`
2. Set your Gemini API key as an environment variable named `GEMINI_API_KEY`.
3. Run:
   `streamlit run app.py`

## Deploy on Streamlit Community Cloud
1. Upload `app.py` and `requirements.txt` to a GitHub repository.
2. In Streamlit Community Cloud, create an app from that repository and select `app.py`.
3. Open the app's Settings / Secrets and add:

   ```toml
   GEMINI_API_KEY = "your_real_gemini_api_key"
   ```

4. If the API reports that the model is unavailable, add this to Secrets with a model name enabled for your API key:
   `GEMINI_MODEL = "your_available_model_name"`

Never publish your API key in GitHub or paste it into `app.py`.
