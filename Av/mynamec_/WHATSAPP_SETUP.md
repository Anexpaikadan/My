# WhatsApp sending — setup guide

The website can send WhatsApp messages by itself:

| Message | When |
|---|---|
| Login code (OTP) — **optional, off by default** | Member taps “Get a login code on WhatsApp instead” (only if “Login & passkey reset codes” is switched on) |
| Passkey reset code — optional | Member taps “Forgot passkey? Reset it” (when codes are on, the code replaces the name check) |
| Welcome message | An admin approves a new member |
| New event | An event is added (to all active members) |
| Blood request | A blood request is posted (to available donors of the same group) |
| Fee reminder | 7 days, 1 day and on the day a membership ends |
| Broadcast | An admin sends from **WA Broadcast** to all members, the committee, one blood group, or only themselves (test) |

Everything is controlled in **Club Settings → WhatsApp**. If sending is **Off**, the site works exactly as before.

## Option A — GOWA (free, self-hosted) — recommended

GOWA is open-source: https://github.com/aldinokemal/go-whatsapp-web-multidevice (MIT licence).
It is **unofficial** (it works like WhatsApp Web), so use a separate club number and send only to members.

### What you need
- A **separate SIM** for the club with WhatsApp installed on a phone. Do not use a personal number.
- A small **always-on Linux server** (VPS or a free cloud tier) with **Docker**. Shared hosting cannot run GOWA.

### Steps
1. **Install Docker** on the server (Ubuntu): `curl -fsSL https://get.docker.com | sh`
2. **Start GOWA** (choose your own strong password):
   ```bash
   docker run -d --name whatsapp --restart always -p 3000:3000 \
     -v whatsapp-storages:/app/storages \
     aldinokemal2104/go-whatsapp-web-multidevice \
     rest --basic-auth=club:CHOOSE-A-STRONG-PASSWORD
   ```
3. **(Recommended) HTTPS:** point a sub-domain such as `wa.yourclub.in` to the server and put Caddy or Nginx
   in front of port 3000. Otherwise you can use `http://SERVER-IP:3000` (allow port 3000 in the server firewall).
4. **Link the club phone:** open the GOWA address in a browser, log in with `club` and your password,
   choose **Login**, and on the club phone open WhatsApp → **Linked devices** → **Link a device** → scan the QR code.
5. **On the website:** Club Settings → **WhatsApp** → choose **GOWA** → fill in
   *Server address*, *Username* (`club`) and *Password* → **Save WhatsApp settings**.
6. Press **Check connection** — it should say “Connected as 91…”.
7. Enter your own number under **Send a test message** → **Send test**. You should get it on WhatsApp.
8. **Cron job** (so big announcements go out steadily): in your hosting control panel → **Cron Jobs**,
   add a job that runs **every minute** with the line shown on the WhatsApp tab:
   `curl -s "https://YOUR-SITE/modules/wa_worker.php?key=…" >/dev/null`
   Without a cron job, waiting messages still go out a few at a time while members use the site.
9. Under **What to send**, switch on the messages you want, then Save.

### Keeping the number safe
- Keep “Seconds between messages” at 4 or more.
- Send only to members (who have saved the club number). No marketing to strangers.
- If GOWA logs out, open its page and scan the QR code again.

## Option B — Meta WhatsApp Cloud API (official)
1. Create a Meta Business account and a WhatsApp Business app at https://developers.facebook.com.
2. Add a phone number (not already used in the normal WhatsApp app) and create a **permanent access token**.
3. Create and get approved:
   - an **Authentication** template for codes (e.g. `login_code`, with the copy-code button), and
   - a **Utility** template with one variable, e.g. `club_notice`: “{{1}}”.
4. Club Settings → WhatsApp → choose **Meta** → paste the token, phone number ID and the two template names → Save.
5. Check connection and send a test. Meta charges per code/alert message — see Meta’s WhatsApp pricing page.

## Files
- `includes/wa_gateway.php` — sending, queue, codes, message texts
- `modules/wa_worker.php` — sends queued messages (cron or automatic)
- Tables created automatically: `wa_queue`, `wa_log`, `wa_otps` (codes are stored hashed)
