from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
from transcriber import Transcriber

app = FastAPI()

origins = ["https://aistudio.contentedai.com",
           "https://news.contentedai.com"
        ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type"],
)

transcriber = Transcriber()

@app.get("/")
async def home():
    return {"message": "Welcome to real-time transcription api"}
          
@app.post("/start/")
async def start_recording(userId: str):
    userId=userId
    transcriber.start_recording(userId)
    return {"message": "Recording started"}
  
@app.post("/upload/")
async def upload_audio(userId: str, file: UploadFile = File(...)):
    userId = userId
    # Define the directory to save the uploaded files. Use the /home directory in Azure App Service
    upload_dir = "/tmp"
    os.makedirs(upload_dir, exist_ok=True)  # Ensure the directory exists
    temp_file_path = os.path.join(upload_dir, file.filename) # Save the uploaded file temporarily
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)   
    # Check if the file format is .wav, if not convert it
    if not temp_file_path.endswith(".wav"):
        converted_file_path = transcriber.convert_to_wav(temp_file_path)
        os.remove(temp_file_path)  # Remove the original file after conversion
    else:
        converted_file_path = temp_file_path
    # Check if converted_file_path exists.
    if not os.path.exists(converted_file_path):
        print(f"File not found: {converted_file_path}")
        return {"error": "File not found or inaccessible."}
    else:
        print(f"File ready for transcription: {converted_file_path}")
    # Start transcription using the (converted) file path
    transcriber.start_recording_from_file(converted_file_path, userId)
    return {"filename": file.filename,
            "userId": userId}

@app.post("/stop/")
async def stop_recording(userId: str):
    userId=userId
    current_transcription = transcriber.get_transcription(userId) 
    transcriber.stop_recording(userId)       
    return {"message": "Recording stopped",
            "userId": userId,
            "transcription": current_transcription}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)