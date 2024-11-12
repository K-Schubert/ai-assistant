from pathlib import Path

def find_repo_root(start_path=None):
    # Start at the provided path or current file's directory
    path = Path(start_path or __file__).resolve()
    for parent in path.parents:
        if (parent / ".git").is_dir():
            return parent
    print("No .git directory found; not a Git repository.")
    return None
