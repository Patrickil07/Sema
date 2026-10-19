# Sema

Sema reads anything on your screen aloud with natural AI voices: web pages in Chrome and Edge, Word documents, Outlook emails, PDFs, images, apps, even text inside videos or screenshots.

Before the text reaches the voice, Sema works out what kind of text it is and prepares it for speech the way a careful human reader would:

| On screen | Sema says |
|---|---|
| `$1.5M in Q3, up 4.5% YoY` | one point five million dollars in Q three, up four point five percent year over year |
| `Dr. Smith, 221 Main St., 10/18/2026 at 3:30 PM` | Doctor Smith, two hundred twenty-one Main Street, October eighteenth, twenty twenty-six at three thirty PM |
| `Henry VIII`, `World War II`, `the 1990s` | Henry the eighth, World War two, the nineteen nineties |
| `(202) 456-1111`, `jane.doe@acme.com` | two zero two, four five six, one one one one; jane dot doe at acme dot com |
| `72°F`, `60 mph`, `16 GB`, `pp. 10-20`, `e.g.` | seventy-two degrees Fahrenheit, sixty miles per hour, sixteen gigabytes, pages ten to twenty, for example |

It also:
- **Reads emails like a person.** It says who the email is from and the subject, then the message. It skips the quoted reply chain, "Sent from my iPhone" and legal disclaimers.
- **Repairs messy text.** It rejoins lines broken by PDFs and OCR, fixes words hyphenated across lines, drops page numbers, and gives headings and list items their own pause.
- **Matches the delivery to the content.** Email sounds conversational, news sounds like a presenter, stories sound like an audiobook narrator, and technical text is read clearly and a little slower. With OpenAI the voice gets these directions in plain language; with Azure, voices that support styles use the matching style (`newscast`, `chat`); with ElevenLabs, the neighbouring sentences are sent along so the intonation flows across sentences.
- **Starts fast and never stalls.** The first sentence is voiced on its own so speech starts almost at once, and the following sentences are prepared while the current one plays.

## Install (Windows 10/11)

1. Install **Python 3.12** from [python.org](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"** in the installer.
2. Copy this `sema` folder anywhere on your PC, for example `C:\Sema`.
3. Double-click **`setup.bat`**. It installs everything, adds Sema to the Start menu and to startup, and launches it.
4. Look for the round purple **Sema icon** in the system tray (bottom right, near the clock). Select some text anywhere and press **Alt+Shift+S**.

The free Microsoft neural voices (Ava, Andrew, Emma, Brian and others) work straight away with no account and no key.

### Hotkeys

| Keys | What it does |
|---|---|
| **Alt+Shift+S** | Read the selected text. With nothing selected, it reads the paragraph under the mouse. |
| **Alt+Shift+D** | Read the whole document from the cursor (Word), or the open email (Outlook), or the focused page or app |
| **Alt+Shift+O** | Drag a box around **anything on screen** to read it with OCR (images, scanned PDFs, video, Google Docs, remote desktops) |
| **Alt+Shift+H** | Read the text under the mouse |
| **Alt+Shift+C** | Read the clipboard |
| **Alt+Shift+P** | Pause / resume |
| **Alt+Shift+X** | Stop |
| **Alt+Shift+→ / ←** | Next / previous sentence |
| **Alt+Shift+↑ / ↓** | Faster / slower |

A small player appears at the bottom right while Sema is reading, with the current sentence and buttons for skipping, pausing and changing speed. You can drag it anywhere. To change any hotkey, open **Open config folder** in the tray menu and edit `config.json`.

## Voices

Right-click the tray icon and choose **Settings…** to pick a voice engine and voice, paste API keys and press **Test voice**. API keys are stored only on your PC, in `%APPDATA%\Sema\config.json`.

| Engine | Quality | Cost | What you need |
|---|---|---|---|
| **Microsoft Neural** (default) | Very natural, 400+ voices, many languages | Free | Nothing |
| **Kokoro** | Natural neural voice that runs on your PC; also the backup when you're offline | Free | Nothing (downloads a 310 MB voice model once, in the background) |
| **ElevenLabs** | The most human-sounding, very expressive | Paid per character | An API key from elevenlabs.io (Profile, then API keys) |
| **OpenAI** (`gpt-4o-mini-tts`) | Natural, and follows directions on tone | Paid per use | An API key from platform.openai.com |
| **Azure Neural** | Studio quality, speaking styles | Free tier, then paid | A Speech resource key and region from portal.azure.com |
| **Piper** | Good, fully offline | Free | `pip install piper-tts` and a downloaded voice `.onnx` file |
| **Windows voices** | Robotic, offline; last resort only | Free | Nothing (built in) |

If the chosen engine fails (no internet, quota used up, wrong key), Sema switches to the next engine in `fallback_order` (Microsoft Neural, then Kokoro, then Windows voices) and tells you in the player.

Recommended voices: **Ava** or **Andrew Multilingual** (free), Kokoro **Heart** or **George** (free, offline), ElevenLabs **George** or **Sarah**, OpenAI **marin** or **cedar**. The multilingual voices detect the language of the text on their own, so French, Spanish or German pages are read by the same voice.

## Chrome and Edge extension

The extension adds a reading bar to web pages, highlights each sentence as it is read (and each word, with browser voices), and finds the article on a page while leaving out menus, sidebars and footers.

1. Open `chrome://extensions` (or `edge://extensions`) and switch on **Developer mode**.
2. Click **Load unpacked** and choose the `sema\extension` folder.
3. Right-click the Sema tray icon, choose **Copy browser pairing code**, then paste it into the extension's **Settings** page.

To use it:
- Select text and click the purple **▶** bubble, or
- Press **Alt+Shift+R** to read the selection, or the whole article from the top, or
- Right-click and choose **Sema: read from here**.
- **Alt+click** any sentence to jump to it while reading. **Alt+Shift+K** pauses and resumes.

When the desktop app is running and paired, the extension uses its voices and text preparation. Otherwise it uses the best voice in the browser; in Edge, that includes Microsoft's free natural voices.

## Privacy

Text goes only to the voice service you choose. The free Microsoft voices use the same online service as Edge's "Read aloud", and Piper and Windows voices never leave your PC. The browser bridge listens only on `127.0.0.1`, needs the pairing code, and refuses requests from websites.

## Troubleshooting

- **Nothing happens when I press the hotkey in one particular app.** If that app runs as administrator, Windows blocks hotkeys from normal apps. Run Sema as administrator too, or use **Alt+Shift+O** (OCR).
- **It reads the wrong thing, or nothing, in some app.** That app doesn't expose its text to Windows accessibility. Select the text and try again (Sema then copies it), or use **Alt+Shift+O**.
- **Google Docs.** It draws text on a canvas, so the extension can't see it. Use **Alt+Shift+O**, or select text and press **Alt+Shift+S**.
- **OCR says no language is installed.** Add your language under Windows **Settings > Time & language > Language & region**.
- **Dates like 03/04/2026 are read the wrong way round.** In Settings, choose the 18/10/2026 date format.
- Logs are in `%APPDATA%\Sema\sema.log`.

## For developers

```
sema/
  normalize.py   text → speakable text (numbers, money, dates, units, abbreviations, URLs…)
  context.py     layout repair, email cleanup, content-type and mood detection, delivery directions
  chunker.py     sentence splitting and chunking for fast start and smooth prosody
  engine.py      pipeline: prepare → synthesize ahead → decode → time-stretch → play; fallback between engines
  voices/        edge, openai, elevenlabs, azure, piper, sapi backends (one small file each)
  audio.py       decoding (miniaudio), pitch-preserving WSOLA time-stretch, gapless player
  capture.py     Word/Outlook COM, UI Automation, clipboard capture
  ocr.py         Windows OCR (Tesseract fallback), paragraph rebuilding, read-under-mouse
  server.py      127.0.0.1 bridge for the browser extension
  app.py, ui.py, settings_ui.py   tray, hotkeys, mini player, region picker, settings
extension/       Manifest V3 extension for Chrome and Edge
tests/           pytest suite
```

- Run the tests: `pip install -r requirements-dev.txt`, then `pytest`.
- Try a voice from the command line without the tray UI: `python -m sema say "It costs $12.50 on Oct. 3rd."`
- Build a standalone `Sema.exe` that runs without Python installed: `build_exe.bat`.
- To add a voice engine, subclass `voices.base.Backend`, implement `synthesize()`, and register it in `voices/__init__.py`.
