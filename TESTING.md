# Testing Sema

Work through the parts in order. Tick each box, and when something doesn't work, write down what you did and what happened. If anything fails, send the log at `%APPDATA%\Sema\sema.log`.

## Part 1: The preview (2 minutes, nothing to install)

Open [Sema Preview](https://claude.ai/artifact/P3AjJWhHimeoAp5EhdnxNu).

- [ ] Press **Play** on each of the four samples. Do the voices sound natural rather than robotic?
- [ ] Switch the voice between **Heart** and **George**.
- [ ] Click a sentence in the middle. Does reading jump to it, with that sentence highlighted?
- [ ] Compare **On screen** with **Sema says**. Are amounts, dates, Dr./St. and "pp. 40-52" read the way you would say them?

## Part 2: Install the Windows app (about 10 minutes)

1. Download `sema-v0.1.zip` from the project, or use **Code → Download ZIP** at github.com/Patrickil07/sema. Unzip it to `C:\Sema`.
2. Install **Python 3.12** from python.org. In the installer, tick **"Add python.exe to PATH"**.
3. Double-click **`setup.bat`**.

- [ ] Setup finishes without red errors.
- [ ] A round purple **Sema** icon appears in the system tray, near the clock. You may need to click the **^** arrow to see it.
- [ ] A small "Sema is ready" bar appears at the bottom right.

## Part 3: The Windows app

**Voice quality**
- [ ] Right-click the tray icon, choose **Settings…**, then press **Test voice**. The voice should be Ava, a natural neural voice.
- [ ] In Settings, set **Voice engine** to **Kokoro (natural, offline)**, then press **Save** and **Test voice**. The first use downloads the voice model, about 310 MB, so the first try can take a while.

**Selecting text** (select some text, then press **Alt+Shift+S**)
- [ ] **Word:** a paragraph. Then put the cursor somewhere and press **Alt+Shift+D** to read from there to the end.
- [ ] **Outlook:** open an email with a reply chain and press **Alt+Shift+D**. Sema should say who it's from and the subject, read the message, and skip the old quoted replies.
- [ ] **Excel:** select a small table with a header row. Each value should be read with its column header.
- [ ] **PowerPoint:** select a text box. Also try **Alt+Shift+D** on a slide.
- [ ] **OneNote:** a selected paragraph.
- [ ] **Chrome or Edge:** text selected on any page.

**Anything on screen**
- [ ] Press **Alt+Shift+O** and drag a box around an image with text, a scanned PDF, or a chat app with a side panel. The panels should be read one after the other, without "19m ago" or button labels.
- [ ] Point the mouse at a paragraph without selecting it, then press **Alt+Shift+H**.

**Controls**
- [ ] **Alt+Shift+P** pauses and resumes. **Alt+Shift+X** stops.
- [ ] **Alt+Shift+→ / ←** move to the next or previous sentence. **Alt+Shift+↑ / ↓** change the speed. At 1.5×, the voice should not sound chipmunk-like.
- [ ] The mini player at the bottom right shows the sentence being read, and its buttons work.

## Part 4: The Chrome/Edge extension

1. Open `chrome://extensions` (or `edge://extensions`) and turn on **Developer mode**.
2. Click **Load unpacked** and choose the `C:\Sema\extension` folder.
3. Right-click the Sema tray icon, choose **Copy browser pairing code**, then open the extension's **Settings** and paste it. Press **Check connection**. It should say **Connected**.

- [ ] Open a news article and press **Alt+Shift+R**. Sema reads the article without menus, sidebars or the footer, and highlights each sentence as it goes.
- [ ] Select text. A purple **▶** button appears next to it. Click it.
- [ ] Right-click partway down a page and choose **Sema: read from here**.
- [ ] **Alt+click** a sentence while it's reading. Reading should jump there.
- [ ] Quit the Sema app from the tray and try again. The extension should switch to your browser's voices. In Edge, pick a voice with **Natural** in its name.

## What to send back

For each box you couldn't tick, tell me the app, what you did, and what happened, or what Sema said wrong. A screenshot helps.
