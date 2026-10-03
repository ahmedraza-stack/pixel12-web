import os
import re
import time
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Gemini configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODEL = os.getenv(
    "GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite"
)
GEMINI_MAX_RETRIES = 3
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing. Check your .env file!")

client = genai.Client(api_key=GEMINI_API_KEY)


def validate_image(image_file):
    """Validates the uploaded file type and returns its bytes and MIME type."""
    if not image_file or not image_file.filename:
        raise ValueError("No image uploaded.")

    extension = os.path.splitext(image_file.filename)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Please upload PNG, JPG, JPEG, or WEBP."
        )

    try:
        image_file.stream.seek(0)
        image_bytes = image_file.read()
        mime_type = (
            "image/jpeg"
            if extension in [".jpg", ".jpeg"]
            else f"image/{extension[1:]}"
        )
        return image_bytes, mime_type
    except Exception as exc:
        raise ValueError(
            "Unable to read the uploaded image. Please upload a valid image file."
        ) from exc


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/service-worker.js")
def service_worker():
    response = app.send_static_file("service-worker.js")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/generate", methods=["POST"])
def generate_code():
    try:
        mode = request.form.get("mode", "photo").strip().lower()
        target_language = request.form.get("language", "HTML + Tailwind CSS")

        if mode == "text":
            prompt_text = request.form.get("prompt", "").strip()
            if not prompt_text:
                return jsonify({"error": "Please write a prompt for the design you want."}), 400

            prompt = f"""
            You are an expert software engineer and UI generator.
            Generate production-ready code based on this description written in: {target_language}.

            Design request:
            {prompt_text}

            CRITICAL REQUIREMENTS:
            1. If HTML is chosen, include Tailwind CSS CDN (<script src="https://cdn.tailwindcss.com"></script>) in <head>.
            2. Output ONLY valid raw code starting with <!DOCTYPE html> if HTML.
            3. Do NOT wrap code in markdown backticks like ```html, ```java, or ```.
            4. Do NOT include explanations or text outside the code itself.
            """
            contents = [prompt]
        else:
            image_files = request.files.getlist("image")
            image_files = [image_file for image_file in image_files if image_file.filename]
            if not image_files:
                return jsonify({"error": "No image uploaded"}), 400

            image_parts = []
            for image_file in image_files:
                image_bytes, mime_type = validate_image(image_file)
                image_parts.append(
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                )

            prompt = f"""
            You are an expert software engineer and UI generator.
            Convert the uploaded UI design into production-ready code written in: {target_language}.

            CRITICAL REQUIREMENTS:
            1. If HTML is chosen, include Tailwind CSS CDN (<script src="https://cdn.tailwindcss.com"></script>) in <head>.
            2. Output ONLY valid raw code starting with <!DOCTYPE html> if HTML.
            3. Do NOT wrap code in markdown backticks like ```html, ```java, or ```.
            4. Do NOT include explanations or text outside the code itself.
            """

            contents = [
                prompt,
                *image_parts,
            ]

        response = None
        model_errors = []

        for model in dict.fromkeys((GEMINI_MODEL, GEMINI_FALLBACK_MODEL)):
            for attempt in range(GEMINI_MAX_RETRIES):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=contents,
                    )
                    break
                except Exception as exc:
                    error_text = str(exc)
                    model_errors.append(f"{model}: {error_text}")
                    if "503" not in error_text and "UNAVAILABLE" not in error_text:
                        raise
                    if attempt < GEMINI_MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)
            if response is not None:
                break

        if response is None:
            return jsonify(
                {
                    "error": (
                        "The AI service is temporarily busy. Please wait a moment "
                        "and try again."
                    ),
                    "retryable": True,
                }
            ), 503

        raw_code = response.text or ""

        # Clean any markdown block wrappers (```html ... ```)
        clean_code = re.sub(
            r"^```[a-zA-Z]*\n", "", raw_code, flags=re.MULTILINE
        )
        clean_code = re.sub(
            r"```$", "", clean_code, flags=re.MULTILINE
        ).strip()

        if not clean_code:
            return jsonify(
                {
                    "error": "The model returned an empty response. Please try again."
                }
            ), 500

        return jsonify({"code": clean_code})

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        print("Error during generation:", str(e))
        return jsonify({"error": f"Failed to generate code: {e}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)