import base64
import tempfile

import chainlit as cl
from chainlit.context import init_ws_context
from chainlit.session import WebsocketSession
from chainlit.utils import mount_chainlit
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Import shared state - this is the single source of truth
from interactive_sketchpad.state import (
    add_sketchpad_connection,
    remove_sketchpad_connection,
    get_sketchpad_connection,
    get_all_sketchpad_connections,
    get_latest_chainlit_session,
    set_latest_chainlit_session,
)

app = FastAPI()

# Serve static files (for CSS, images, etc.)
public_path = Path(__file__).parent / "public"
app.mount("/static", StaticFiles(directory=public_path), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main page with side-by-side layout."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interactive Sketchpad</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Outfit', sans-serif;
            background: #0a0a0f;
            height: 100vh;
            overflow: hidden;
        }
        
        .container {
            display: flex;
            height: 100vh;
            width: 100vw;
        }
        
        .panel {
            flex: 1;
            height: 100%;
            position: relative;
        }
        
        .panel iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
        
        .divider {
            width: 4px;
            background: linear-gradient(180deg, #6366f1 0%, #8b5cf6 100%);
            cursor: col-resize;
            position: relative;
            transition: width 0.15s ease;
        }
        
        .divider:hover {
            width: 6px;
        }
        
        .divider::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 4px;
            height: 40px;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 2px;
        }
        
        .loading-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: #0a0a0f;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 16px;
            color: #8888a0;
            font-size: 14px;
            z-index: 10;
            transition: opacity 0.3s ease;
        }
        
        .loading-overlay.hidden {
            opacity: 0;
            pointer-events: none;
        }
        
        .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid rgba(99, 102, 241, 0.2);
            border-top-color: #6366f1;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="panel" id="chatPanel">
            <div class="loading-overlay" id="chatLoading">
                <div class="spinner"></div>
                <span>Loading chat...</span>
            </div>
            <iframe id="chatFrame" src="/chat"></iframe>
        </div>
        <div class="divider" id="divider"></div>
        <div class="panel" id="sketchpadPanel">
            <div class="loading-overlay" id="sketchpadLoading">
                <div class="spinner"></div>
                <span>Loading sketchpad...</span>
            </div>
            <iframe id="sketchpadFrame" src="/sketchpad"></iframe>
        </div>
    </div>
    
    <script>
        const chatFrame = document.getElementById('chatFrame');
        const sketchpadFrame = document.getElementById('sketchpadFrame');
        const chatLoading = document.getElementById('chatLoading');
        const sketchpadLoading = document.getElementById('sketchpadLoading');
        
        chatFrame.addEventListener('load', () => {
            chatLoading.classList.add('hidden');
        });
        
        sketchpadFrame.addEventListener('load', () => {
            sketchpadLoading.classList.add('hidden');
        });
        
        // Resizable divider
        const divider = document.getElementById('divider');
        const chatPanel = document.getElementById('chatPanel');
        const sketchpadPanel = document.getElementById('sketchpadPanel');
        
        let isResizing = false;
        
        divider.addEventListener('mousedown', (e) => {
            isResizing = true;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            chatFrame.style.pointerEvents = 'none';
            sketchpadFrame.style.pointerEvents = 'none';
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            
            const containerWidth = document.querySelector('.container').offsetWidth;
            const percentage = (e.clientX / containerWidth) * 100;
            const clampedPercentage = Math.max(20, Math.min(80, percentage));
            
            chatPanel.style.flex = `0 0 ${clampedPercentage}%`;
            sketchpadPanel.style.flex = `0 0 ${100 - clampedPercentage}%`;
        });
        
        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                chatFrame.style.pointerEvents = '';
                sketchpadFrame.style.pointerEvents = '';
            }
        });
    </script>
</body>
</html>
"""


@app.get("/sketchpad")
async def serve_sketchpad():
    """Serve the sketchpad HTML page."""
    return FileResponse(public_path / "sketchpad.html")


@app.get("/api/session")
async def get_session():
    """Get the current Chainlit session ID."""
    return {"session_id": get_latest_chainlit_session()}


@app.websocket("/ws/sketchpad")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication with sketchpad."""
    await websocket.accept()
    
    # Use a simple connection key - store as "default" for single-user mode
    connection_id = id(websocket)
    add_sketchpad_connection("default", websocket)
    print(f"[SKETCHPAD-WS] Connected! ID={connection_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"[SKETCHPAD-WS] Received: {data}")
    except WebSocketDisconnect:
        remove_sketchpad_connection("default")
        print(f"[SKETCHPAD-WS] Disconnected! ID={connection_id}")


async def send_image_to_sketchpad_ws(image_bytes: bytes):
    """Send an image to the sketchpad via WebSocket."""
    connections = get_all_sketchpad_connections()
    print(f"[SKETCHPAD-SEND] Attempting to send image, size={len(image_bytes)} bytes")
    print(f"[SKETCHPAD-SEND] Available connections: {list(connections.keys())}")
    
    websocket = get_sketchpad_connection("default")
    if websocket:
        try:
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            print(f"[SKETCHPAD-SEND] Sending base64 image, length={len(base64_image)}")
            await websocket.send_json({
                "type": "image",
                "image": f"data:image/png;base64,{base64_image}"
            })
            print("[SKETCHPAD-SEND] SUCCESS - Image sent to sketchpad!")
        except Exception as e:
            print(f"[SKETCHPAD-SEND] ERROR sending image: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("[SKETCHPAD-SEND] FAILED - No WebSocket connection available (key 'default' not found)")


# Handle uploaded images from sketchpad
@app.post("/upload")
async def upload_image(
    text: str = "Here's my working so far, can you help me?",
    file: UploadFile = File(...),
):
    # Import here to avoid circular imports
    from interactive_sketchpad.chatbot import main
    
    # Use the latest Chainlit session
    chainlit_session_id = get_latest_chainlit_session()
    
    if not chainlit_session_id:
        print("No Chainlit session available")
        return {"error": "No chat session available. Please start a chat first."}
    
    ws_session = WebsocketSession.get_by_id(session_id=chainlit_session_id)
    if not ws_session:
        print(f"WebsocketSession not found for: {chainlit_session_id}")
        return {"error": "Chat session not found"}
    
    init_ws_context(ws_session)

    content = await file.read()

    image_element = cl.Image(
        name=file.filename, content=content, display="inline", size="large"
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as temp_file:
        temp_file.write(content)
        temp_file_path = temp_file.name
        image_element.path = temp_file_path

        message = cl.Message(content=text, elements=[image_element])
        await message.send()
        await main(message)

    return {"message": "Image received"}


# Mount Chainlit at /chat path
mount_chainlit(app=app, target="interactive_sketchpad/chatbot.py", path="/chat")
