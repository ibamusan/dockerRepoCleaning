import os
import logging
from flask import Flask, request, jsonify
from google.cloud import storage
from inference_cleaning import process_transcripts, load_environment_variables

app = Flask(__name__)

# GCP Bucket details for transcription cleaning
TEMP_DIR = "/tmp"  # Root directory for temporary file storage

# Ensure /tmp directory exists
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Load environment variables
load_environment_variables(".env")

# Initialize logging
logging.basicConfig(level=logging.INFO)

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return "Transcription Cleaning App is ready!", 200

@app.route("/clean", methods=["POST"])
def clean_transcription():
    """
    Endpoint to clean transcription files.
    Expects JSON input with:
    - input_bucket_name
    - input_file_path
    - output_bucket_name
    - output_folder
    """
    try:
        # Parse input JSON
        data = request.get_json()
        input_bucket_name = data.get("input_bucket_name")
        input_file_path = data.get("input_file_path")
        output_bucket_name = data.get("output_bucket_name")
        output_folder = data.get("output_folder")

        # Validate input
        if not (input_bucket_name and input_file_path and output_bucket_name and output_folder):
            return jsonify({"error": "Missing required fields in JSON request"}), 400

        # Initialize GCP Storage client
        storage_client = storage.Client()

        # Download the transcription file from GCS
        logging.info(f"Downloading file from gs://{input_bucket_name}/{input_file_path}...")
        input_bucket = storage_client.bucket(input_bucket_name)
        transcription_blob = input_bucket.blob(input_file_path)
        local_file_path = os.path.join(TEMP_DIR, os.path.basename(input_file_path))
        transcription_blob.download_to_filename(local_file_path)
        logging.info(f"File downloaded to {local_file_path}.")

        # Check if the file was downloaded successfully
        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f"Failed to download transcription file to {local_file_path}.")

        # Process and clean the transcription
        logging.info("Cleaning transcription...")
        process_transcripts(local_file_path)

        # Generate output file name
        original_file_name = os.path.basename(input_file_path).replace('.txt', '')
        if "_transcription" in original_file_name:
            output_file_name = original_file_name.replace("_transcription", "_cleaned_transcription") + ".txt"
        else:
            output_file_name = f"{original_file_name}_cleaned.txt"

        cleaned_file_path = os.path.join(TEMP_DIR, output_file_name)

        # Check if cleaned file exists after processing
        if not os.path.exists(cleaned_file_path):
            raise FileNotFoundError(f"Cleaned transcription file not found at {cleaned_file_path}.")

        # Upload cleaned transcription to GCS
        output_gcs_path = os.path.join(output_folder, output_file_name)
        logging.info(f"Uploading cleaned transcription to gs://{output_bucket_name}/{output_gcs_path}...")
        output_bucket = storage_client.bucket(output_bucket_name)
        output_blob = output_bucket.blob(output_gcs_path)
        output_blob.upload_from_filename(cleaned_file_path)
        logging.info("Cleaned transcription uploaded successfully.")

        return jsonify({"cleaned_transcription_gcs_path": f"gs://{output_bucket_name}/{output_gcs_path}"}), 200

    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
