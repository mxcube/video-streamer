import os
import asyncio

from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from video_streamer.core.websockethandler import WebsocketHandler
from video_streamer.core.streamer import FFMPGStreamer, MJPEGStreamer, VideoMediaStreamer
from fastapi.templating import Jinja2Templates

from contextlib import asynccontextmanager
import signal
import sys

from typing import Optional
from types import FrameType

from aiortc import RTCPeerConnection, RTCRtpSender, RTCSessionDescription
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# This function makes sure that the server is correctly shutted down
def handle_shutdown(signum: int, frame: Optional[FrameType]) -> None:
    print(f"Received signal {signum}, shutting down streamer...")
    sys.exit(0)

def create_app(config, host, port, debug):
    app = None
    app_cls = available_applications.get(config.format, None)

    if app_cls:
        app = app_cls(config, host, port, debug)

    return app

def create_mjpeg_app(config, host, port, debug):
    streamer = MJPEGStreamer(config, host, port, debug)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Some signals are catched from uvicorn/fastapi, this makes sure that the server is correctly 
        # shutting down and the second part of the lifespan is called
        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)
        try:
            yield
        finally:
            streamer.stop()

    app = FastAPI(lifespan=lifespan)
    ui_template_root = os.path.join(os.path.dirname(__file__), "ui/template")
    templates = Jinja2Templates(directory=ui_template_root)

    @app.get("/ui", response_class=HTMLResponse)
    async def video_ui(request: Request):
        return templates.TemplateResponse(
            "index_mjpeg.html",
            {
                "request": request,
                "source": f"http://localhost:{port}/video/{config.hash}",
            },
        )

    @app.get(f"/video/{config.hash}")
    def video_feed():
        return StreamingResponse(
            streamer.start(), media_type='multipart/x-mixed-replace;boundary="!>"'
        )

    return app


def create_mpeg1_app(config, host, port, debug):
    streamer = FFMPGStreamer(config, host, port, debug)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        streamer.start()
        # Some signals are catched from uvicorn/fastapi, this makes sure that the server is correctly 
        # shutting down and the second part of the lifespan is called
        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)
        try:
            yield
        finally:
            streamer.stop()

    app = FastAPI(lifespan=lifespan)
    manager = WebsocketHandler()
    ui_static_root = os.path.join(os.path.dirname(__file__), "ui/static")
    ui_template_root = os.path.join(os.path.dirname(__file__), "ui/template")
    templates = Jinja2Templates(directory=ui_template_root)

    app.mount(
        "/static", StaticFiles(directory=ui_static_root, html=True), name="static"
    )

    @app.get("/ui", response_class=HTMLResponse)
    async def video_ui(request: Request):
        return templates.TemplateResponse(
            "index_mpeg1.html",
            {"request": request, "source": f"ws://localhost:{port}/ws/{config.hash}"},
        )

    @app.websocket(f"/ws/{config.hash}")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)
            await manager.broadcast(f"client disconnected")

    @app.post("/video_input/")
    async def video_in(request: Request):
        async for chunk in request.stream():
            await manager.broadcast(chunk)

    return app

def create_vp8_app(config, host, port, debug):

    video_capabilities = RTCRtpSender.getCapabilities("video")

    vp8_codecs = [
        codec for codec in video_capabilities.codecs
        if codec.mimeType == "video/VP8"
    ]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.streamer = VideoMediaStreamer(config, host, port, debug)
        app.state.video_track = app.state.streamer.start()

        app.state.pcs = set()

        # Some signals are catched from uvicorn/fastapi, this makes sure that the server is correctly 
        # shutting down and the second part of the lifespan is called
        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)
        try:
            yield
        finally:
            for pc in set(app.state.pcs):
                try:
                    await asyncio.wait_for(pc.close(), timeout=2)
                except asyncio.TimeoutError:
                    print("Timeout while closing peer connection, closing forcefully...")
            app.state.pcs.clear()
            app.state.streamer.stop()

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_methods=["OPTIONS", "POST"], allow_origins=config.allowed_origins, allow_headers=["Content-Type"])

    @app.post("/offer")
    async def offer(request: Request):
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
        pc = RTCPeerConnection()
        request.app.state.pcs.add(pc)

        track = request.app.state.video_track
        pc.addTrack(track)

        # set the preferred codec to VP8
        for transceiver in pc.getTransceivers():
            if transceiver.kind == "video":
                transceiver.setCodecPreferences(vp8_codecs)

        @pc.on("connectionstatechange")
        async def on_state_change():
            if pc.connectionState in ("failed", "closed", "disconnected"):
                await pc.close()
                request.app.state.pcs.discard(pc)

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        return JSONResponse(
            content={
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type,
            }
        )

    return app

available_applications = {"MPEG1": create_mpeg1_app, "MJPEG": create_mjpeg_app, "VP8": create_vp8_app}
