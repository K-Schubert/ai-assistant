import os
from pynput import keyboard
import pyperclip

from get_repo_root import find_repo_root

project_root = find_repo_root()

def copy_selected_text():
    text = pyperclip.paste()
    with open(os.path.join(project_root, "src/playground/arxiv/queue", "data_to_process.txt"), "a", encoding="utf-8") as f:
        f.write(text + "\n")

def on_activate():
    copy_selected_text()

if __name__ == "__main__":
    with keyboard.GlobalHotKeys({'<ctrl>+s': on_activate}) as h:
        h.join()
