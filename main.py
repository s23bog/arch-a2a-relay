from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import json
import os
import sys

# Load your exact maps (the ones you just uploaded)
script_dir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(script_dir, 'map.json'), 'r', encoding='utf-8') as f:
    tier1 = json.load(f)['mapping']

with open(os.path.join(script_dir, 'tier2_map.json'), 'r', encoding='utf-8') as f:
    tier2 = json.load(f)['mapping']

# Import your exact encode/decode functions (the files you uploaded)
sys.path.insert(0, script_dir)
from encode_message import encode_text
from decode_message import decode_string

app = FastAPI(title="Arch A2A Relay v5.0")

class TritMessage(BaseModel):
    payload: str
    mime_type: str = "application/x-arch-trit+v5"

@app.post("/a2a/messages")
async def handle_arch_message(msg: TritMessage):
    # Decode incoming trit stream using your exact decoder
    plaintext = decode_string(msg.payload)
    
    # Simple echo reply (you can later forward to any model here)
    reply_text = f"[Arch Relay] Received in balanced ternary: {plaintext[:400]}..."
    
    # Encode reply back to trit stream using your exact encoder
    trit_reply = encode_text(reply_text)
    
    return {
        "payload": trit_reply,
        "mime_type": "application/x-arch-trit+v5"
    }

@app.get("/.well-known/agent-card.json")
async def get_agent_card():
    return {
        "name": "arch-lexicon-relay",
        "description": "Balanced Ternary Arch v5.0 — direct inter-AI communication relay",
        "version": "1.0",
        "capabilities": ["text", "trits"],
        "supportedMimeTypes": ["application/x-arch-trit+v5", "text/plain"],
        "endpoints": {"messages": "/a2a/messages"}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
