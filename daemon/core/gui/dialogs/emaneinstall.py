import webbrowser
from tkinter import ttk

from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADY


class EmaneInstallDialog(Dialog):
    def __init__(self, app) -> None:
        super().__init__(app, "EMANE Error")
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        label = ttk.Label(self.top, text="EMANE needs to be installed!")
        label.grid(sticky="ew", pady=PADY)
        button = ttk.Button(
            self.top, text="EMANE Documentation", command=self.click_doc
        )
        button.grid(sticky="ew", pady=PADY)
        button = ttk.Button(self.top, text="Close", command=self.destroy)
        button.grid(sticky="ew")

    def click_doc(self):
        webbrowser.open_new("https://coreemu.github.io/core/emane.html")
