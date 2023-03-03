import os

from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from video_streamer.core.websockethandler import WebsocketHandler
from video_streamer.core.streamer import FFMPGStreamer, MJPEGStreamer
from fastapi.templating import Jinja2Templates


def create_app(config, host, port):
    app = None
    app_cls = available_applications.get(config.format, None)

    if app_cls:
        app = app_cls(config, host, port)

    return app


def create_mjpeg_app(config, host, port):
    app = FastAPI()
    streamer = MJPEGStreamer(config, host, port)
    ui_static_root = os.path.join(os.path.dirname(__file__), "ui/static")
    ui_template_root = os.path.join(os.path.dirname(__file__), "ui/template")
    templates = Jinja2Templates(directory=ui_template_root)
    app.mount("/ui", StaticFiles(directory=ui_static_root, html=True), name="static")

    @app.get("/ui", response_class=HTMLResponse)
    async def video_ui(request: Request):
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "source": "http://localhost:%s/video" % port},
        )

    @app.get("/video")
    def video_feed():
        return StreamingResponse(
            streamer.start(), media_type='multipart/x-mixed-replace;boundary="!>"'
        )

    @app.on_event("startup")
    async def startup():
        pass

    @app.on_event("shutdown")
    async def shutdown():
        streamer.stop()

    return app


def create_mpeg1_app(config, host, port):
    app = FastAPI()
    manager = WebsocketHandler()
    streamer = FFMPGStreamer(config, host, port)
    uiroot = os.path.join(os.path.dirname(__file__), "ui/static")
    app.mount("/video", StaticFiles(directory=uiroot, html=True), name="static")

    @app.websocket("/ws")
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

    @app.on_event("startup")
    async def startup():
        streamer.start()

    @app.on_event("shutdown")
    async def shutdown():
        streamer.stop()

    return app


available_applications = {"MPEG1": create_mpeg1_app, "MJPEG": create_mjpeg_app}
