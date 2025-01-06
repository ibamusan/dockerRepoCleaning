import os
import logging
import re
import nltk
from google.cloud import storage
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Initialize logger
logging.basicConfig(level=logging.INFO)

# Initialize Google Cloud Storage client
client = storage.Client()

# Download necessary NLTK resources
nltk.download('punkt', quiet=True)

def load_environment_variables(file_path):
    """Loads environment variables from a text file and logs each loaded variable."""
    if not os.path.exists(file_path):
        logging.error(f"Environment file {file_path} does not exist.")
        raise FileNotFoundError(f"Environment file {file_path} not found.")

    with open(file_path, 'r') as env_file:
        for line in env_file:
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ[key] = value.strip('"')
                logging.debug(f"Set environment variable {key}")

# Dynamically locate the environment file
current_dir = os.path.dirname(os.path.abspath(__file__))
env_file_path = os.path.join(current_dir, "cleaning_env_var.txt")

load_environment_variables(env_file_path)

# Fetch the environment variables
output_bucket = os.getenv('OUTPUT_BUCKET')
output_prefix = os.getenv('OUTPUT_TRANSCRIPTION_BLOB', 'Diarization-clean/')
input_path = os.getenv("INPUT_PATH")
error_logs_bucket = os.getenv('ERROR_LOGS_BUCKET')
workers_count = int(os.getenv("WORKERS_COUNT", 5))

# Specify local directory to store the text files temporarily
local_dir = "/tmp/text_files/"
os.makedirs(local_dir, exist_ok=True)

def download_files_from_gcs(bucket_name, prefix, destination_dir):
    """Download text files from a GCS bucket."""
    try:
        bucket = client.get_bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=prefix)
        files = []

        for blob in blobs:
            if blob.name.endswith('.txt'):
                file_path = os.path.join(destination_dir, os.path.basename(blob.name))
                blob.download_to_filename(file_path)
                logging.info(f"Downloaded {blob.name} to {file_path}")
                files.append(file_path)
        
        if not files:
            logging.warning("No text files found with the specified prefix.")
        
        return files
    except Exception as e:
        logging.error(f"Failed to download files from bucket {bucket_name}: {e}")
        return []

# Upload cleaned transcript to GCS
def upload_transcript_to_gcs(bucket_name, transcript, file_name):
    """Upload cleaned transcript back to GCS."""
    try:
        output_bucket = client.get_bucket(bucket_name)
        blob = output_bucket.blob(f"{output_prefix}{file_name}.txt")
        blob.upload_from_string(transcript)
        logging.info(f"Uploaded cleaned transcript to {bucket_name}/{output_prefix}{file_name}.txt")
    except Exception as e:
        logging.error(f"Failed to upload file {file_name} to bucket {bucket_name}: {e}")

# Process raw transcription to clean
def clean_transcript(transcript):
    """Clean the transcript by removing unwanted characters and extra spaces."""
    transcript = re.sub(r'\s+', ' ', transcript).strip()
    transcript = re.sub(r'\b(i)\b', 'I', transcript)  # Capitalize isolated "i"
    return transcript

def process_with_whisper_style(chunk):
    """Simulate Whisper sentence segmentation for natural sentence boundaries and capitalization."""
    sentences = nltk.sent_tokenize(chunk)  # No hardcoded language
    processed_sentences = []
    is_continuation = False

    for sentence in sentences:
        sentence = re.sub(r'\b(i)\b', 'I', sentence)

        if is_continuation:
            sentence = sentence[0].lower() + sentence[1:] if sentence else sentence

        is_complete = sentence.endswith(('.', '!', '?'))
        if is_complete:
            is_continuation = False
        else:
            is_continuation = True

        processed_sentences.append(sentence)

    return ' '.join(processed_sentences)

def log_error(error_message):
    """Log errors to GCS."""
    try:
        bucket = client.get_bucket(error_logs_bucket)
        blob = bucket.blob("error_log.txt")
        blob.upload_from_string(error_message, content_type="text/plain")
        logging.error(error_message)  # Log to console as well
    except Exception as e:
        logging.error(f"Failed to log error: {e}")

def process_transcripts(file_path):
    """Process and clean the transcript, then display it with Whisper-style sentence recognition."""
    try:
        with open(file_path, 'r') as file:
            raw_transcript = file.read()

        cleaned_transcript = clean_transcript(raw_transcript)

        pattern = re.compile(r"\[(\d+\.\d+ - \d+\.\d+)\]\s*(.+?)(?=\[\d+\.\d+ - \d+\.\d+\]|$)", re.DOTALL)
        matches = pattern.findall(cleaned_transcript)

        if not matches:
            logging.warning(f"No timestamped segments found in {file_path}")
            return

        result = [
            f"[{timestamp}] {process_with_whisper_style(text).strip()}"
            for timestamp, text in matches
        ]
        formatted_transcript = "\n".join(result)

        # Generate the output cleaned file name
        original_file_name = os.path.basename(file_path).replace('.txt', '')
        if "_transcription" in original_file_name:
            file_name = original_file_name.replace("_transcription", "_cleaned_transcription")
        else:
            file_name = f"{original_file_name}_cleaned"
        
        cleaned_file_path = os.path.join("/tmp", file_name + ".txt")

        # Log and check if the directory exists
        if not os.path.exists("/tmp"):
            logging.error("The /tmp directory does not exist.")
            raise FileNotFoundError("The /tmp directory does not exist.")
        logging.debug(f"Attempting to save cleaned file to {cleaned_file_path}")

        with open(cleaned_file_path, 'w') as cleaned_file:
            cleaned_file.write(formatted_transcript)

        # Check if the file was created successfully
        if not os.path.exists(cleaned_file_path):
            logging.error(f"Cleaned file not found at {cleaned_file_path}.")
            raise FileNotFoundError(f"Cleaned transcription file not found at {cleaned_file_path}.")
        else:
            logging.info(f"Cleaned transcription file successfully created at {cleaned_file_path}.")

        # Upload the cleaned transcript to GCS
        upload_transcript_to_gcs(output_bucket, formatted_transcript, file_name)

    except Exception as e:
        error_message = f"Error processing {file_path}: {e}"
        log_error(error_message)

def main(input_path=input_path):
    """Main function to process either a directory of files or a single file."""
    if not input_path:
        logging.error("No input path specified.")
        return

    if input_path.startswith("gs://"):
        # Extract bucket and prefix for GCS path
        bucket_name = input_path.split("/")[2]
        prefix = "/".join(input_path.split("/")[3:])
        files = download_files_from_gcs(bucket_name, prefix, local_dir)
    else:
        if os.path.isdir(input_path):
            files = [os.path.join(input_path, f) for f in os.listdir(input_path) if f.endswith('.txt')]
            if not files:
                logging.warning("No .txt files found in the specified directory.")
                return
        elif os.path.isfile(input_path):
            files = [input_path]
        else:
            logging.error("Invalid path specified. Please provide a valid file or directory path.")
            return

    # Process files in parallel with a progress bar
    with ThreadPoolExecutor(max_workers=workers_count) as executor:
        futures = {executor.submit(process_transcripts, file): file for file in files}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing Files"):
            try:
                future.result()  # This will raise an exception if the processing failed
            except Exception as e:
                logging.error(f"Error in parallel processing: {e}")

if __name__ == "__main__":
    main(input_path)
