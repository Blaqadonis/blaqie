# internet search mcp server
import os
import time
from groq import Groq
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("generate_audio")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Create recordings folder
RECORDINGS_DIR = "recordings"
os.makedirs(RECORDINGS_DIR, exist_ok=True)

@mcp.tool()
def generate_audio(text: str, voice: str = "Fritz-PlayAI", model: str = "playai-tts", response_format: str = "wav") -> str:
    """Converts text to speech using the Groq API and saves the audio file locally."""
    try:
        timestamp = time.strftime("%Y%m%d%H%M%S")
        audio_file_path = os.path.join(RECORDINGS_DIR, f"audio_{timestamp}.wav")
        response = groq_client.audio.speech.create(model=model, voice=voice, input=text, response_format=response_format)
        response.write_to_file(audio_file_path)
        return f"Audio file saved successfully to {audio_file_path}"
    except Exception as e:
        return f"Failed to generate audio: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")