"""Download Amiri (SIL OFL) into this folder. Run on a machine with internet."""
import os, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://github.com/alif-type/amiri/raw/master/"
FILES = {"Amiri-Regular.ttf": "Amiri-Regular.ttf",
         "Amiri-Bold.ttf": "Amiri-Bold.ttf"}
for dest, name in FILES.items():
    url = BASE + name
    out = os.path.join(HERE, dest)
    try:
        print("Downloading", dest, "...")
        urllib.request.urlretrieve(url, out)
        print("  saved", out)
    except Exception as e:
        print("  FAILED:", e, "\n  Download manually from https://github.com/alif-type/amiri")
print("Done. Restart DayBill to use the bundled Arabic font.")
