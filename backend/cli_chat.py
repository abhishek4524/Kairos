import os
import io
import uuid
import asyncio

# Suppress pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

# Import our agents
from llm_agent import generate_streaming_response
from tts_agent import generate_audio_async

# Initialize pygame mixer for audio playback
pygame.mixer.init()

async def play_audio_bytes(audio_bytes: bytes):
    """Plays audio bytes from memory using Pygame."""
    try:
        # Load the MP3 bytes into a BytesIO object
        audio_file = io.BytesIO(audio_bytes)
        
        # Load and play using pygame
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        
        # Wait until playback finishes asynchronously
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"\n[Error playing audio]: {e}")

async def run_cli():
    print("="*50)
    print(" 🤖 Personal Assistant - Terminal Mode (with Audio)")
    print(" Type 'exit' or 'quit' to stop.")
    print("="*50)
    
    # Unique session ID for Redis history
    session_id = str(uuid.uuid4())
    print(f"Session ID: {session_id}\n")
    
    while True:
        try:
            # Take input from the terminal
            user_input = input("\nYou: ")
            if user_input.lower().strip() in ['exit', 'quit']:
                print("Goodbye!")
                break
            if not user_input.strip():
                continue
            
            # Simple heuristic for language detection to pass to TTS
            # If text contains mostly ASCII, assume English. Otherwise, Hindi.
            detected_lang = "en"
            if any(ord(c) > 127 for c in user_input):
                 detected_lang = "hi"
            
            print("AI: ", end="", flush=True)
            
            full_llm_response = ""
            
            # Stream the response from the LLM
            for chunk in generate_streaming_response(session_id, user_input):
                if chunk.startswith("[Error") or chunk.startswith("[ERROR"): 
                    print(chunk)
                    break
                print(chunk, end="", flush=True)
                full_llm_response += chunk
                
            print() # Newline after the full response
            
            if full_llm_response.strip():
                # Generate TTS audio and visemes
                audio_bytes, visemes = await generate_audio_async(full_llm_response, detected_lang)
                
                if visemes and "mouthCues" in visemes:
                    print(f"[Lip Sync Generated: {len(visemes['mouthCues'])} visemes]")
                
                # Play the generated audio bytes
                await play_audio_bytes(audio_bytes)
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\n[Error]: {e}")

if __name__ == "__main__":
    # Ensure asyncio uses Windows selector event loop if necessary for some versions
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(run_cli())
