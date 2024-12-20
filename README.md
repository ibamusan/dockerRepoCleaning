# Inference Script for Transcription Cleaning

This script, `inference_cleaning.py`, uses the Whisper style NLTK model to clean raw transcription files with timestamps.

## Steps Performed:
1. Loads environment variables.
2. Downloads the raw transcription file from a GCS bucket.
3. Cleans the file using the Whisper style NLTK model.
4. Uploads the cleaned transcription to a specified GCS bucket.

## How to Use:

1. Open Terminal.

2. Set Environment Variables:
   Update the script with the following environment variables:

   OUTPUT_BUCKET="vosyncore-transcription-dev"  
   OUTPUT_Folder="cleaned_transcripts/"  
   INPUT_PATH="gs://vosyncore-transcription/Diarization-test/Harris_takes_on_Fox_News_during_heated_interview_transcription.txt"  
   ERROR_LOGS_BUCKET="vosyncore-transcription-dev/cleaned_logs"  
   PROCESS_MODE="parallel"  
   WORKERS_COUNT="5"  

3. Run the Script:
   Execute the script with this command:

## Environment Variables:

1. **OUTPUT_BUCKET**  
- GCS bucket where cleaned transcriptions are uploaded.  
- Example: "vosyncore-transcription-dev"  

2. **OUTPUT_Folder**  
- Folder path in the GCS bucket to store the output.  
- Example: "cleaned_transcripts/"  

3. **INPUT_PATH**  
- GCS path to the raw transcription file.  
- Example: "gs://vosyncore-transcription/Diarization-test/ "  

4. **ERROR_LOGS_BUCKET**  
- GCS bucket path for error logs.  
- Example: "vosyncore-transcription-dev/cleaned_logs"  

5. **PROCESS_MODE**  
- Mode of processing files.  
- Example: "parallel"  

6. **WORKERS_COUNT**  
- Number of parallel workers.  
- Example: "5"  


3. **Run Python Script**: After setting the environment variables, run the script by executing the following command:

```bash
python inference_cleaning.py
```
