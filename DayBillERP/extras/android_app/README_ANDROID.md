# DayBill Mobile — Android app (APK)

The same DayBill Mobile app, installed like a normal app, plus:

* **PDT scan button** sends the barcode straight in (Zebra DataWedge, Urovo,
  Honeywell, Newland, iData, Sunmi, Chainway…). Keyboard ("wedge") mode also
  works with no setup.
  *Zebra:* DataWedge ▸ profile for "DayBill" ▸ Intent output ON ▸ action
  `com.daybill.SCAN` ▸ delivery *Broadcast* (or *Start activity*).
* **📷 camera scan** on phones (Google code scanner).
* **🖨 Bluetooth receipt printer** (58/80 mm ESC/POS) for van bills: pair the
  printer in Android Settings ▸ Bluetooth, then Print ▸ choose it once.
* First start asks the **server address**: the shop Wi-Fi address shown in
  DayBill ▸ Mobile & Van (e.g. `http://192.168.1.10:8090`), or the van relay
  (`https://van.yourshop.com/`). Scan the QR on the DayBill screen to fill it.

## Build the APK (pick one)

**A. GitHub (nothing to install)**
1. Make a free GitHub account ▸ New repository (private) ▸ upload the
   contents of this `android_app` folder (keep `.github/workflows`).
2. Actions ▸ *Build DayBill APK* ▸ Run workflow. After ~5 minutes download
   **DayBill-APK** (a zip with `app-debug.apk`).
3. Copy the APK to the phone / PDT ▸ open it ▸ allow "install unknown apps".

**B. Android Studio** (Windows): Open ▸ this folder ▸ wait for Gradle ▸
Build ▸ Build APK(s).

For the Play Store / a release build make your own keystore
(Build ▸ Generate Signed Bundle / APK) — keep it safe, updates need the same key.
