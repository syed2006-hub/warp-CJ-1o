import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify,  send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import re
from PIL import Image
import base64
from io import BytesIO  # Import Google's Image handler


# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure Gemini AI
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Store uploaded file content
uploaded_data = ""
conversation_history = []

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure folder exists
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/")
def index():
    global uploaded_data, conversation_history
    uploaded_data = ""  # Reset file content
    conversation_history = []  # Clear chat history

    file_name = request.args.get("file")  # Get filename from URL

    if file_name:
        try:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], file_name)
            with open(file_path, "r", encoding="utf-8") as file:
                uploaded_data = file.read()
                print(f"Loaded file: {file_name}")
        except FileNotFoundError:
            return jsonify({"message": f"File '{file_name}' not found"}), 404
        except Exception as e:
            return jsonify({"message": f"Error reading file: {str(e)}"}), 500

    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    global uploaded_data

    if "file" not in request.files:
        return jsonify({"message": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"message": "No file selected"}), 400

    try:
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(file_path)  # save the file


        with open(file_path, "r", encoding="utf-8") as f:
            uploaded_data = f.read()

        print(f"✅ File uploaded successfully: {file.filename}")
        print(f"📂 First 200 characters:\n{uploaded_data[:200]}")

        return jsonify({"message": "File uploaded successfully", "filename": file.filename})
    except Exception as e:
        print(f"⚠️ Error processing file: {str(e)}")
        return jsonify({"message": f"Error processing file: {str(e)}"}), 500


@app.route("/chat", methods=["POST"])
def chat():
    global uploaded_data, conversation_history
    data = request.json
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"content": "Error: Empty message"}), 400
    # Check for name-related queries
    if re.search(r"\b(what is your name|what is your model name)\b", user_message):
        return jsonify({
            "explanation": "My name is CJ-1o,you can call me CJ.",
            "code_snippets": [],
            "history": conversation_history
        })
    if re.search(r"\b(change your name)\b", user_message):
        return jsonify({
            "explanation": "sorry you can't change my name.",
            "code_snippets": [],
            "history": conversation_history
        })
    try:
        # Append user message to conversation history
        conversation_history.append({"role": "user", "parts": [{"text": user_message}]})

        # Create AI prompt including history and uploaded data
        conversation_text = "\n".join([f"{m['role']}: {m['parts'][0]['text']}" for m in conversation_history])
        prompt = f"File Data:\n{uploaded_data}\n\nConversation History:\n{conversation_text}\n\nAI Response:"

        # Get AI response
        model = genai.GenerativeModel("gemini-1.5-flash-latest")
        response = model.generate_content(prompt)

        ai_message = response.text.strip()

        # Extract code snippets using regex
        code_snippets = re.findall(r"```(?:\w+)?\n(.*?)```", ai_message, re.DOTALL)

        # Remove code from main message (keep explanation only)
        explanation = re.sub(r"```(?:\w+)?\n.*?```", "", ai_message, flags=re.DOTALL).strip()

        # Append AI response to conversation history
        conversation_history.append({"role": "model", "parts": [{"text": ai_message}]})

        # Response format:
        # If code snippets exist, return them separately
        return jsonify({
            "explanation": explanation if explanation else "No explanation provided.",
            "code_snippets": code_snippets if code_snippets else ["No code provided."],
            "history": conversation_history
        })

    except Exception as e:
        return jsonify({"content": f"Error: {str(e)}"}), 500



@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico",mimetype="image/vnd.microsoft.icon")

@app.route("/upload_image", methods=["POST"])
def upload_image():
    global conversation_history  # Ensure we update global history

    if "file" not in request.files:
        return jsonify({"message": "No image uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"message": "No file selected"}), 400

    try:
        # Save Image to Server
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(file_path)

        # Convert image to Base64 for AI processing
        with open(file_path, "rb") as img_file:
            img_data = base64.b64encode(img_file.read()).decode("utf-8")

        print(f"✅ Image '{file.filename}' uploaded & converted to Base64.")

        # Generate AI Response
        model = genai.GenerativeModel("gemini-1.5-flash-latest")
        response = model.generate_content([
            "Describe this image in detail and just say Ask for further information about the uploaded image but in case of any question papers or like quiz give exact answers for that.",
            {
                "mime_type": "image/png",  # Adjust based on actual file type
                "data": img_data
            }
        ])

        # Extract AI response text
        ai_response = response.text.strip()

        # **Store Image and AI Response in Conversation History**
        conversation_history.append({
            "role": "user",
            "parts": [{"text": f"Uploaded an image: {file.filename}"}],
            "image_path": file_path  # Store image path for future reference
        })
        conversation_history.append({
            "role": "model",
            "parts": [{"text": ai_response}]
        })

        print(f"✅ AI Response Stored: {ai_response}")

        return jsonify({"description": ai_response})

    except Exception as e:
        print(f"⚠️ Error processing image: {str(e)}")
        return jsonify({"message": f"Error processing image: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
