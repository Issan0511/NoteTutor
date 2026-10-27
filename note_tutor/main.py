"""Start NoteSync with the installed NoteTutor extension."""
def main():
    from .LocalSettings import load_local_settings
    load_local_settings()
    from notesync.main import main as launch
    launch()

if __name__ == '__main__': main()
