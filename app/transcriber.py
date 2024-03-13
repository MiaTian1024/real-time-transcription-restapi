import os
import azure.cognitiveservices.speech as speechsdk
import threading
import time
import asyncio
from pydub import AudioSegment  # For audio file conversion
from azure.messaging.webpubsubservice import WebPubSubServiceClient

# Initialize the Web PubSub service client with connection string
webpubsub_connection_string = os.environ.get('CONNECTION_STRING')
webpubsub_hub_name = os.environ.get('HUB_NAME')
service = WebPubSubServiceClient.from_connection_string(webpubsub_connection_string, hub=webpubsub_hub_name)

# Async functions for broadcasting messages
async def broadcast(userId: str, message: str):   
    service.send_to_user(userId, message, content_type='text/plain')

async def broadcast_final_message(userId: str):
    final_message = "Transcription stopped."
    service.send_to_user(userId, final_message, content_type='text/plain')


class Transcriber:
    def __init__(self):
        self.transcribing_stop = False
        self.transcription_text = ""
        self.transcription_thread = None
        self.temp_file_path = None
        self.start_time = None
        self.last_speech_time = None
        self.active_sessions = {}  # Dictionary to track active sessions by user ID
        self.transcription_lock = threading.Lock()  # Lock to synchronize threads

    # Callback function for processing transcription results
    def conversation_transcriber_transcribed_cb(self, userId: str, evt: speechsdk.SpeechRecognitionEventArgs):
        line = ""
        # Check if the event is for recognized speech
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            current_time = time.time()
            self.last_speech_time = current_time  # Update the last speech time
            elapsed_time = current_time - self.start_time  # Calculate time since recording started
            # Formatting the elapsed time into minutes and seconds
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            relativetimestamp = f"[{minutes:02}:{seconds:02}]"
            # Prepare the line of transcribed text with timestamp and speaker ID
            line = f"{relativetimestamp} Speaker {evt.result.speaker_id}: {evt.result.text}\n"
            # Thread-safe operation to append the transcribed line
            with self.transcription_lock:
                self.transcription_text += line
            #Broadcast the line to all connected WebSocket clients
            threading.Thread(target=lambda: asyncio.run(broadcast(userId, line))).start()
        # Handle the case where speech could not be recognized
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            line = f"NOMATCH: Speech could not be transcribed: {evt.result.no_match_details}\n"

    def start_recording(self, userId: str):
        if userId in self.active_sessions:
            self.stop_recording(userId)
        self.transcribing_stop = False
        self.active_sessions[userId] = {"transcription_thread": self.transcription_thread}
        # Start a new transcription session here (code to initialize and start transcription)
        print(f"Recording started for user: {userId}")
        self.start_time = time.time()  # Record the start time of recording
        try:
            # Start speech recognition in a separate thread
            self.transcription_thread = threading.Thread(target=self.recognize_from_microphone, args=(userId,))
            self.transcription_thread.start()
        except Exception as err:
            # Handle exceptions, if any
            print(f"Encountered exception: {err}\n")

    def start_recording_from_file(self, file_path, userId: str):
        if userId in self.active_sessions:
            self.stop_recording(userId)
        self.transcribing_stop = False
        self.active_sessions[userId] = {"transcription_thread": self.transcription_thread}
        # Start a new transcription session here (code to initialize and start transcription from file)
        print(f"Recording from file started for user: {userId}")
        self.start_time = time.time()  # Record the start time of recording
        self.last_speech_time = self.start_time  # Initialize last_speech_time to the start time
        self.temp_file_path = file_path
        try:
            # Start speech recognition in a separate thread
            self.transcription_thread = threading.Thread(target=self.recognize_from_file, args=(file_path, userId))
            self.transcription_thread.start()
        except Exception as err:
            # Handle exceptions, if any
            print(f"Encountered exception: {err}\n")

    def stop_recording(self, userId: str):
        # Check if the user has an active session and stop it
        if userId in self.active_sessions:
            self.transcribing_stop = True        
            # Wait for the transcription thread to finish, if any
            if self.transcription_thread is not None:
                self.transcription_thread.join()        
            # Clean up the session
            with self.transcription_lock:
                self.transcription_text = "" 
            self.transcription_thread = None
            if self.temp_file_path and os.path.exists(self.temp_file_path):
                os.remove(self.temp_file_path)
                self.temp_file_path = None        
            # Remove the user from the active sessions
            del self.active_sessions[userId]
            # Create a new event loop in the current thread
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(broadcast_final_message(userId))
            else:
                loop.run_until_complete(broadcast_final_message(userId))       
        print(f"Recording stopped for user: {userId}")
                  
    def save_transcription(self):
        # Save the transcription to a file with a timestamp
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        with open(f"transcription_{timestamp}.txt", 'w') as file:
            file.write(self.transcription_text)

    def get_transcription(self, userId: str):
        if userId in self.active_sessions:
            return self.transcription_text
        return ""

    def recognize_from_file(self, file_path: str, userId: str):
        self.transcribing_stop = False
        # Setting up the Azure Speech Service configuration
        speech_config = speechsdk.SpeechConfig(subscription=os.environ.get('SPEECH_KEY'), region=os.environ.get('SPEECH_REGION'))
        speech_config.speech_recognition_language = "en-US"
        # Configuring the audio source 
        audio_config = speechsdk.audio.AudioConfig(filename=file_path)
        # Creating the ConversationTranscriber object
        conversation_transcriber = speechsdk.transcription.ConversationTranscriber(speech_config=speech_config, audio_config=audio_config)    
        # Connect event handlers for transcribed and session stopped events
        conversation_transcriber.transcribed.connect(lambda evt: self.conversation_transcriber_transcribed_cb(userId, evt))
        def stop_cb(evt: speechsdk.SessionEventArgs):
            print('Transcription stopped.')
            self.transcribing_stop = True
            if hasattr(evt, "reason"):
                print(f"Reason: {evt.reason}")
            if hasattr(evt, "error_details"):
                print(f"Error details: {evt.error_details}")
        conversation_transcriber.session_stopped.connect(stop_cb)
        conversation_transcriber.canceled.connect(stop_cb)
        # Start transcribing asynchronously
        conversation_transcriber.start_transcribing_async()
        # Loop to keep the transcription running until stopped
        try:
            while not self.transcribing_stop:
                time.sleep(.5)
        except KeyboardInterrupt:
            print("Stopping transcription...")
        # Stop transcribing
        conversation_transcriber.stop_transcribing_async()

    def recognize_from_microphone(self, userId: str):
        self.transcribing_stop = False
        # Setting up the Azure Speech Service configuration
        speech_config = speechsdk.SpeechConfig(subscription=os.environ.get('SPEECH_KEY'), region=os.environ.get('SPEECH_REGION'))
        speech_config.speech_recognition_language="en-US"
        # Configuring the audio source 
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
        # Creating the ConversationTranscriber object
        conversation_transcriber = speechsdk.transcription.ConversationTranscriber(speech_config=speech_config, audio_config=audio_config)
        # Connect event handlers for transcribed and session stopped events
        conversation_transcriber.transcribed.connect(lambda evt: self.conversation_transcriber_transcribed_cb(userId, evt))
        def stop_cb(evt: speechsdk.SessionEventArgs):
            print('Transcription stopped.')
            self.transcribing_stop = True
            if hasattr(evt, "reason"):
                print(f"Reason: {evt.reason}")
            if hasattr(evt, "error_details"):
                print(f"Error details: {evt.error_details}")
        conversation_transcriber.session_stopped.connect(stop_cb)
        conversation_transcriber.canceled.connect(stop_cb)
        # Start transcribing asynchronously
        conversation_transcriber.start_transcribing_async()
        # Loop to keep the transcription running until stopped
        try:
            while not self.transcribing_stop:
                time.sleep(.5)
        except KeyboardInterrupt:
            print("Stopping transcription...")
        # Stop transcribing
        conversation_transcriber.stop_transcribing_async()

    def convert_to_wav(self, file_path: str) -> str:
        sound = AudioSegment.from_file(file_path)
        wav_file_path = file_path.rsplit(".", 1)[0] + ".wav"
        sound.export(wav_file_path, format="wav")
        return wav_file_path
    

