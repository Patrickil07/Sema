"""Local API so the Chrome/Edge extension can use Sema's voices and settings.

Listens on 127.0.0.1 only. Every request must carry the pairing code shown in the
tray menu, and requests coming from ordinary web pages are refused, so websites
cannot make Sema talk.
"""
from __future__ import annotations

import asyncio
import logging

from aiohttp import web

log = logging.getLogger("sema")


def _allowed(request: web.Request, token: str) -> bool:
    origin = request.headers.get("Origin", "")
    if origin and not origin.startswith(("chrome-extension://", "extension://", "moz-extension://")):
        return False
    return request.headers.get("X-Sema-Token", "") == token


def make_app(engine) -> web.Application:
    cfg = engine.config

    @web.middleware
    async def guard(request, handler):
        if request.method == "OPTIONS":
            return web.Response(status=204)
        if request.path != "/ping" and not _allowed(request, cfg["server"]["token"]):
            return web.json_response({"error": "not paired"}, status=401)
        return await handler(request)

    async def ping(_):
        return web.json_response({"app": "sema", "ok": True})

    async def status(_):
        return web.json_response(engine.status())

    async def speak(request):
        body = await request.json()
        segments = body.get("segments")
        if segments:
            segments = [{"id": s.get("id", i), "text": str(s.get("text", ""))[:20000],
                         "pause_after_ms": s.get("pause_after_ms", 0)}
                        for i, s in enumerate(segments) if str(s.get("text", "")).strip()]
        engine.speak(str(body.get("text", ""))[:500000], source=body.get("source", "web"),
                     kind=body.get("kind"), segments=segments)
        return web.json_response({"ok": True})

    async def control(request):
        body = await request.json()
        action = body.get("action")
        actions = {"pause": engine.pause, "resume": engine.resume, "toggle": engine.toggle,
                   "stop": engine.stop, "next": lambda: engine.skip(1), "previous": lambda: engine.skip(-1)}
        if action == "speed":
            engine.set_speed(float(body.get("value", 1.0)))
        elif action == "seek":
            engine.seek_segment(body.get("segment"))
        elif action in actions:
            actions[action]()
        else:
            return web.json_response({"error": "unknown action"}, status=400)
        return web.json_response(engine.status())

    async def voices(_):
        b = engine.backend()
        try:
            vs = await b.list_voices()
        except Exception:
            vs = b.curated_voices()
        return web.json_response({"backend": b.name, "current": cfg.voice_for(b),
                                  "voices": [v.__dict__ for v in vs]})

    async def settings(request):
        body = await request.json()
        if "backend" in body and body["backend"]:
            cfg.set("backend", body["backend"])
        if body.get("voice"):
            voices = dict(cfg["voices"])
            voices[cfg["backend"]] = body["voice"]
            cfg.set("voices", voices)
        return web.json_response(engine.status())

    app = web.Application(middlewares=[guard])
    app.add_routes([web.get("/ping", ping), web.get("/status", status), web.post("/speak", speak),
                    web.post("/control", control), web.get("/voices", voices),
                    web.post("/settings", settings)])
    return app


def start(engine):
    """Start the API on the engine's event loop."""
    port = engine.config["server"]["port"]

    async def run():
        runner = web.AppRunner(make_app(engine), access_log=None)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", port).start()
        log.info("browser bridge on http://127.0.0.1:%s", port)

    return asyncio.run_coroutine_threadsafe(run(), engine.loop)
