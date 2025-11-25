from fastapi import FastAPI
from services.audio_augmentation import AudioAugmentation

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

# audio augmentation testing endpoint
@app.post("/augment-audio")
def augment_audio():

    with open("/Users/akshatsoni/Desktop/project-x-processing-engine/harvard.wav", "rb") as f:
        audio_bytes = f.read()

    service = AudioAugmentation({})
    audio = service.run_pipeline(audio_bytes)

    with open("output_audio.wav", "wb") as f:
        f.write(audio)
    return {"message": "Audio augmentation endpoint"}

@app.post("/llm-test")
def llm_test():
    from services.llm_service import LLMService

    config = {
        "provider": "gemini",
        "api_key": "AQ.Ab8RN6LbX-AmjvGNCW_E0Q7gi30mD7atLhLcGCHEKJbHQniZbw",
        "model_name": "gemini-2.5-flash",
        "temperature": 0.5,
        "max_tokens": 150
    }

    llm_service = LLMService(config)
    response = llm_service.process("Hello, how are you?")
    return {"llm_response": response.content}
