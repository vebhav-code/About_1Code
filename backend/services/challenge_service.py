from pathlib import Path

BASE_PATH = Path(__file__).resolve().parent.parent / "assets"


def read_readme(folder_name: str):
    candidates = [
        BASE_PATH / folder_name / "README.md",
        BASE_PATH / "challenges" / folder_name / "README.md",
        BASE_PATH / "challenges" / folder_name / "buggy_project" / "README.md",
    ]
    for readme_path in candidates:
        if readme_path.exists():
            with open(readme_path, "r", encoding="utf-8") as file:
                return file.read()
    return None