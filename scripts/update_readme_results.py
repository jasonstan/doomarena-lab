from pathlib import Path
import re


def main():
    summary = Path("results/summary.md").read_text(encoding="utf-8").strip()
    summary_image = Path("results/summary.svg")
    image_block = ""
    if summary_image.exists():
        image_block = f"![Results summary]({summary_image.as_posix()})\n\n"
    readme_path = Path("README.md")
    text = readme_path.read_text(encoding="utf-8")
    begin = "<!-- RESULTS:BEGIN -->"
    end = "<!-- RESULTS:END -->"
    if begin in text and end in text:
        pattern = re.compile(f"{begin}.*?{end}", re.DOTALL)
        replacement = f"{begin}\n\n{image_block}{summary}\n\n{end}"
        new_text = pattern.sub(replacement, text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        new_text = (
            text
            + "\n## Results\n"
            + begin
            + "\n\n"
            + image_block
            + summary
            + "\n\n"
            + end
            + "\n"
        )
    readme_path.write_text(new_text, encoding="utf-8")


if __name__ == "__main__":
    main()
