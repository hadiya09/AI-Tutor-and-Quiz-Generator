import json
import os
import re
import time
from io import BytesIO
from xml.sax.saxutils import escape

import streamlit as st
from google import genai
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

st.set_page_config(page_title="AI Tutor & Quiz Generator", page_icon="📚", layout="centered")

st.title("📚 AI Tutor & Quiz Generator")
st.write("Generate an explanation PDF or practise with an AI-created MCQ quiz.")

# Add GEMINI_API_KEY in Streamlit Cloud: App settings > Secrets.
try:
    API_KEY = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    API_KEY = os.getenv("GEMINI_API_KEY", "")

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

if not API_KEY:
    st.info("To use the app, add your Gemini API key in Streamlit Secrets as GEMINI_API_KEY.")
    st.code('GEMINI_API_KEY = "your_api_key_here"', language="toml")
    st.stop()

client = genai.Client(api_key=API_KEY)


def ask_ai(prompt):
    last_error = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            answer = response.text
            if not answer:
                raise ValueError("The AI returned an empty response. Please try again.")
            return answer.strip()
        except Exception as exc:
            last_error = exc
            error_text = str(exc).upper()
            if ("503" in error_text or "UNAVAILABLE" in error_text or
                    "429" in error_text or "RESOURCE_EXHAUSTED" in error_text):
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError(
                    "Gemini is temporarily busy or rate-limited. Wait a little and try again. "
                    "If the error mentions the model name, change GEMINI_MODEL in Streamlit Secrets."
                ) from exc
            raise
    raise RuntimeError(str(last_error))


def make_explanation(topic):
    prompt = f"""
You are a helpful school tutor. Write a clear, accurate explanation for a student about:
{topic}

Use a useful title, simple language, short sections, examples, and a short recap.
Do not invent facts. If the topic is ambiguous, state your assumption.
Return plain text, not Markdown tables or code fences.
"""
    return ask_ai(prompt)


def make_quiz(topic, number_of_questions):
    prompt = f"""
Create exactly {number_of_questions} school-level multiple-choice questions about:
{topic}

Return ONLY a valid JSON array. Do not include Markdown fences or extra text.
Each item must have this structure:
{{
  "question": "Question text",
  "options": {{
    "A": "Option A",
    "B": "Option B",
    "C": "Option C",
    "D": "Option D"
  }},
  "answer": "A",
  "explanation": "Brief reason the answer is correct"
}}

Rules:
- Exactly {number_of_questions} questions.
- Four distinct options per question.
- Exactly one correct answer per question.
- "answer" must be one of A, B, C, D.
- Questions must be clear and solvable from the topic.
- Avoid duplicate questions.
- Keep explanations short.
"""
    raw = ask_ai(prompt)
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("The AI did not return quiz data in the expected format. Please try again.")
    questions = json.loads(raw[start:end + 1])

    if not isinstance(questions, list) or len(questions) != number_of_questions:
        raise ValueError("The AI did not create the requested number of questions. Please try again.")

    for item in questions:
        if not all(key in item for key in ("question", "options", "answer", "explanation")):
            raise ValueError("A question is missing required information. Please try again.")
        if not isinstance(item["options"], dict) or not all(k in item["options"] for k in ("A", "B", "C", "D")):
            raise ValueError("A question does not have four options. Please try again.")
        if item["answer"] not in ("A", "B", "C", "D"):
            raise ValueError("A question has an invalid answer key. Please try again.")
    return questions


def make_pdf(topic, explanation):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    story = [
        Paragraph(escape("AI Tutor: " + topic), styles["Title"]),
        Spacer(1, 14),
    ]
    for paragraph in explanation.split("\n"):
        paragraph = paragraph.strip()
        if paragraph:
            story.append(Paragraph(escape(paragraph), styles["BodyText"]))
            story.append(Spacer(1, 8))
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50,
    )
    doc.build(story)
    return buffer.getvalue()


if "quiz" not in st.session_state:
    st.session_state.quiz = None
if "quiz_result" not in st.session_state:
    st.session_state.quiz_result = None
if "explanation" not in st.session_state:
    st.session_state.explanation = None
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None

mode = st.radio(
    "What would you like to generate?",
    ["Explanation PDF", "MCQ Quiz"],
    horizontal=True
)
topic = st.text_input("Enter a topic", placeholder="Example: The law of demand")

if mode == "MCQ Quiz":
    count = st.slider("Number of MCQs", min_value=5, max_value=20, value=5)
else:
    count = 5

if st.button("Generate", type="primary", use_container_width=True):
    if not topic.strip():
        st.warning("Please enter a topic first.")
    else:
        try:
            with st.spinner("Generating with Gemini..."):
                if mode == "Explanation PDF":
                    explanation = make_explanation(topic.strip())
                    pdf_bytes = make_pdf(topic.strip(), explanation)
                    st.session_state.explanation = explanation
                    st.session_state.pdf_bytes = pdf_bytes
                    st.session_state.quiz = None
                    st.session_state.quiz_result = None
                else:
                    questions = make_quiz(topic.strip(), int(count))
                    st.session_state.quiz = {
                        "topic": topic.strip(),
                        "questions": questions,
                    }
                    st.session_state.quiz_result = None
                    st.session_state.explanation = None
                    st.session_state.pdf_bytes = None
            st.success("Done! Your content is ready.")
        except Exception as exc:
            st.error(f"Could not generate content: {exc}")

if st.session_state.explanation:
    st.subheader("Your explanation")
    st.markdown(st.session_state.explanation)
    st.download_button(
        "📄 Download explanation PDF",
        data=st.session_state.pdf_bytes,
        file_name="ai_tutor_explanation.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

if st.session_state.quiz:
    quiz = st.session_state.quiz
    questions = quiz["questions"]
    st.subheader(f"MCQ Quiz: {quiz['topic']}")
    st.caption(f"{len(questions)} questions. Select one answer for each question, then submit.")

    with st.form("quiz_form"):
        selected_answers = []
        for i, question in enumerate(questions, start=1):
            st.markdown(f"**{i}. {question['question']}**")
            option_keys = ["A", "B", "C", "D"]
            labels = [f"{key}. {question['options'][key]}" for key in option_keys]
            selected_label = st.radio(
                f"Choose your answer for question {i}",
                labels,
                index=None,
                key=f"answer_{i}",
                label_visibility="collapsed",
            )
            selected_answers.append(
                selected_label.split(".", 1)[0] if selected_label else None
            )
        submitted = st.form_submit_button("Submit Quiz", type="primary", use_container_width=True)

    if submitted:
        score = 0
        results = []
        for i, (question, selected) in enumerate(zip(questions, selected_answers), start=1):
            correct = question["answer"]
            if selected == correct:
                score += 1
                status = "✅ Correct"
            else:
                status = "❌ Incorrect"
            your_answer = (
                f"{selected}. {question['options'][selected]}"
                if selected else "Not answered"
            )
            results.append({
                "number": i,
                "status": status,
                "your_answer": your_answer,
                "correct_answer": f"{correct}. {question['options'][correct]}",
                "explanation": question["explanation"],
            })
        st.session_state.quiz_result = {
            "score": score,
            "total": len(questions),
            "results": results,
        }

    if st.session_state.quiz_result:
        result = st.session_state.quiz_result
        percentage = round(result["score"] / result["total"] * 100)
        st.divider()
        st.subheader(f"Your result: {result['score']}/{result['total']} ({percentage}%)")
        for item in result["results"]:
            with st.expander(f"{item['status']} · Question {item['number']}", expanded=True):
                st.write(f"**Your answer:** {item['your_answer']}")
                st.write(f"**Correct answer:** {item['correct_answer']}")
                st.write(f"**Explanation:** {item['explanation']}")

st.caption("AI-generated content can contain mistakes. Please review explanations and answer keys before using them.")
