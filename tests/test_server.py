from sema.config import Config
from sema.server import make_app


class StubEngine:
    def __init__(self, cfg):
        self.config = cfg
        self.calls = []

    def speak(self, text="", **kw):
        self.calls.append(("speak", text, kw))

    def toggle(self):
        self.calls.append(("toggle",))

    def status(self):
        return {"state": "idle"}

    pause = resume = stop = toggle

    def skip(self, d):
        self.calls.append(("skip", d))


async def test_bridge_requires_token_and_extension_origin(aiohttp_client, tmp_path):
    cfg = Config(tmp_path / "c.json")
    eng = StubEngine(cfg)
    client = await aiohttp_client(make_app(eng))
    tok = cfg["server"]["token"]
    assert (await client.get("/ping")).status == 200
    assert (await client.post("/speak", json={"text": "hi"})).status == 401
    r = await client.post("/speak", json={"text": "hi"}, headers={"X-Sema-Token": tok, "Origin": "https://evil.example"})
    assert r.status == 401
    r = await client.post("/speak", json={"segments": [{"id": "a", "text": "Hello."}, {"id": "b", "text": " "}]},
                          headers={"X-Sema-Token": tok, "Origin": "chrome-extension://abc"})
    assert r.status == 200
    assert eng.calls[0][2]["segments"] == [{"id": "a", "text": "Hello.", "pause_after_ms": 0}]
    r = await client.post("/control", json={"action": "next"}, headers={"X-Sema-Token": tok})
    assert r.status == 200 and eng.calls[-1] == ("skip", 1)
