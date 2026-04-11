from ui import MidiControllerApp

if __name__ == "__main__":
    app = MidiControllerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
