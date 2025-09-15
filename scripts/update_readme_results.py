from pathlib import Path
import re


def main():
    summary = Path("results/summary.md").read_text(encoding="utf-8").strip()
    readme_path = Path("README.md")
    text = readme_path.read_text(encoding="utf-8")
    begin = "<!-- RESULTS:BEGIN -->"
    end = "<!-- RESULTS:END -->"
    if begin in text and end in text:
        pattern = re.compile(f"{begin}.*?{end}", re.DOTALL)
        replacement = f"{begin}\n\n{summary}\n\n{end}"
        new_text = pattern.sub(replacement, text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        new_text = text + "\n## Results\n" + begin + "\n\n" + summary + "\n\n" + end + "\n"
    readme_path.write_text(new_text, encoding="utf-8")


if __name__ == "__main__":
    main()
