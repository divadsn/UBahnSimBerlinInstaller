import sys
import webview
import webbrowser

from usb_installer.api import InstallerAPI

api = InstallerAPI()
window = webview.create_window(
    title="U-Bahn Sim Berlin Installer",
    url="./usb_installer/templates/index.html",
    js_api=api,
    width=800,
    height=600,
    resizable=False,
    background_color="#212529",
    confirm_close=False,
)

api._window = window

try:
    webview.start(gui="edgechromium", debug=not getattr(sys, "frozen", False))
except webview.WebViewException as e:
    webbrowser.open("https://dl.u7-trainz.de/error.html?error=webview")
    raise SystemExit(1)

print("Installer finished")
