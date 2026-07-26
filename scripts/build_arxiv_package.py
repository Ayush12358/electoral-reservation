"""Build a self-contained arXiv source package from PAPER.md."""

from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "PAPER.md"
ARXIV = ROOT / "arxiv"
TEX = ARXIV / "main.tex"
BBL = ARXIV / "main.bbl"
BIB = ARXIV / "references.bib"
PNG = ARXIV / "measurement_model_concepts.png"
ZIP = ROOT / "release" / "electoral_reservation_arxiv_v0.1.zip"

TITLE = "Electoral Capability, Party Gatekeeping, and the Exit Threshold for Institutional Correction"
REPOSITORY = "https://github.com/Ayush12358/electoral-reservation"


def run_pandoc() -> None:
    ARXIV.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "pandoc",
            str(PAPER),
            "--from=gfm",
            "--to=latex",
            "--standalone",
            "--wrap=none",
            "--top-level-division=section",
            "--metadata",
            f"title={TITLE}",
            "--metadata",
            "author=Ayush Maurya",
            "--metadata",
            "date=Working Paper, Version 0.1 -- July 2026",
            "-o",
            str(TEX),
        ],
        cwd=ROOT,
        check=True,
    )


def extract_reference_items(tex: str) -> tuple[str, list[str]]:
    pattern = re.compile(
        r"\\subsection\{References\}.*?"
        r"(?=\\begin\{center\}\\rule\{0\.5\\linewidth\}\{0\.5pt\}\\end\{center\}\s*"
        r"\\subsection\{Appendix: Replication Guide\})",
        re.DOTALL,
    )
    match = pattern.search(tex)
    if not match:
        raise ValueError("Could not locate the generated reference section")
    reference_block = match.group(0)
    items: list[str] = []
    for itemize in re.findall(r"\\begin\{itemize\}.*?\\end\{itemize\}", reference_block, re.DOTALL):
        items.extend(
            re.sub(r"\s+", " ", item).strip()
            for item in re.findall(
                r"\\item\s+(.*?)(?=\\item|\\end\{itemize\})",
                itemize,
                re.DOTALL,
            )
        )
    if not items:
        raise ValueError("No bibliography items were extracted")
    tex = tex[: match.start()] + "\\input{main.bbl}\n\n" + tex[match.end() :]
    return tex, items


def write_bibliographies(items: list[str]) -> None:
    bbl_lines = ["\\begin{thebibliography}{99}"]
    bib_entries = []
    for index, item in enumerate(items, start=1):
        key = f"ref{index:03d}"
        bbl_lines.extend([f"\\bibitem{{{key}}}", item, ""])
        plain = re.sub(r"\\(?:emph|textquotesingle|url)\{([^{}]*)\}", r"\1", item)
        plain = re.sub(r"\\[A-Za-z]+", "", plain)
        plain = plain.replace("{", "").replace("}", "")
        plain = plain.replace("%", "\\%").replace("&", "\\&").replace("_", "\\_")
        bib_entries.append(
            f"@misc{{{key},\n"
            f"  note = {{{plain}}}\n"
            f"}}\n"
        )
    bbl_lines.append("\\end{thebibliography}")
    BBL.write_text("\n".join(bbl_lines) + "\n", encoding="utf-8")
    BIB.write_text("\n".join(bib_entries), encoding="utf-8")


def clean_tex(tex: str) -> str:
    # Remove the duplicate Markdown title/front matter and use a real abstract.
    tex = re.sub(
        r"\\section\{Electoral Capability.*?"
        r"\\subsection\{Abstract\}\\label\{abstract\}\s*",
        "\\\\begin{abstract}\n",
        tex,
        count=1,
        flags=re.DOTALL,
    )
    tex = tex.replace(
        "\\textbf{Keywords:}",
        "\\end{abstract}\n\n\\noindent\\textbf{Keywords:}",
        1,
    )
    # The Markdown H1 was the title, so after removing its duplicate body block
    # promote every remaining heading by one level.
    heading_levels = {
        "subsection": "section",
        "subsubsection": "subsection",
        "paragraph": "subsubsection",
    }
    tex = re.sub(
        r"\\(subsubsection|subsection|paragraph)\{",
        lambda match: f"\\{heading_levels[match.group(1)]}{{",
        tex,
    )
    tex = tex.replace("\\usepackage{svg}\n", "")
    tex = tex.replace("Working Paper, Version 0.1 -\\/- July 2026", "Working Paper, Version 0.1 --- July 2026")
    tex = tex.replace("\\usepackage{fancyvrb}", "\\usepackage{fancyvrb}\n\\usepackage{fvextra}", 1)
    tex = tex.replace(
        "\\pandocbounded{\\includesvg[keepaspectratio]{outputs/measurement_model_concepts.svg}}",
        "\\begin{figure}[htbp]\n"
        "\\centering\n"
        "\\includegraphics[width=\\textwidth]{measurement_model_concepts.png}\n"
        "\\caption{Measurement model. The residual is an observable proxy for latent capability "
        "and an election-specific index of measured electoral contribution; it is neither latent "
        "capability itself nor realized electoral success.}\n"
        "\\label{fig:measurement-model}\n"
        "\\end{figure}",
    )
    tex = re.sub(
        r"\s*\\emph\{Figure 1\. Measurement model\..*?\}\s*",
        "\n",
        tex,
        count=1,
        flags=re.DOTALL,
    )
    tex = tex.replace("\\usepackage{xcolor}", "\\usepackage[margin=1in]{geometry}\n\\usepackage{xcolor}", 1)
    tex = tex.replace(
        "\\begin{document}",
        "\\setlength{\\emergencystretch}{3em}\n\\sloppy\n\\begin{document}",
        1,
    )
    tex = tex.replace(
        "\\begin{verbatim}",
        "\\begin{Verbatim}[breaklines=true,breakanywhere=true,fontsize=\\small]",
    ).replace("\\end{verbatim}", "\\end{Verbatim}")
    # Give prose-heavy tables fixed wrapping columns. Numeric tables retain
    # Pandoc's compact natural-width layout.
    table_specs = {
        1: "@{}p{0.23\\linewidth}p{0.71\\linewidth}@{}",
        2: "@{}p{0.28\\linewidth}p{0.66\\linewidth}@{}",
        3: "@{}p{0.22\\linewidth}p{0.27\\linewidth}p{0.22\\linewidth}p{0.17\\linewidth}@{}",
        8: "@{}p{0.17\\linewidth}p{0.12\\linewidth}p{0.07\\linewidth}p{0.08\\linewidth}p{0.17\\linewidth}p{0.27\\linewidth}@{}",
        11: "@{}p{0.25\\linewidth}p{0.20\\linewidth}p{0.49\\linewidth}@{}",
        17: "@{}p{0.22\\linewidth}p{0.24\\linewidth}p{0.09\\linewidth}p{0.37\\linewidth}@{}",
        18: "@{}p{0.27\\linewidth}p{0.18\\linewidth}p{0.49\\linewidth}@{}",
        20: "@{}p{0.06\\linewidth}p{0.54\\linewidth}p{0.34\\linewidth}@{}",
    }
    table_number = 0

    def replace_table_spec(match: re.Match[str]) -> str:
        nonlocal table_number
        table_number += 1
        spec = table_specs.get(table_number)
        return f"\\begin{{longtable}}[]{{{spec}}}" if spec else match.group(0)

    tex = re.sub(r"\\begin\{longtable\}\[\]\{[^\\n]*\}", replace_table_spec, tex)
    # Keep the three widest displayed equations within the text block.
    for equation in (
        r"\mathbb{E}[V \mid P, C, T] = \alpha + \beta_1 \cdot \text{PartyBaseline}_{PC} + \beta_2 \cdot \text{StateSwing}_{PT} + \beta_3 \cdot \text{Alliance}_{PT} + \beta_4 \cdot \text{Incumbent}_{IC} + \beta_5 \cdot \text{SeatType}_C + \varepsilon_{PCT}",
        r"\underbrace{\text{All women}}_{\text{electorate}} \xrightarrow{\text{Stage 1: Nomination}} \underbrace{\text{Ticketed women}}_{\text{candidates}} \xrightarrow{\text{Stage 2: Seat quality}} \underbrace{\text{Women in winnable seats}}_{\text{competitive tickets}} \xrightarrow{\text{Stage 3: Conversion}} \underbrace{\text{Women winners}}_{\text{elected}}",
        r"V_{PC}(T) = \alpha + \beta_1 V_{PC}(T-1) + \beta_2 V_{PC}(T-2) + \beta_3 \Delta V_{P,\text{state}}(T) + \beta_4 \text{Alliance}_{PC}(T) + \beta_5 \text{Incumbent}_{IC}(T) + \delta_C + \gamma_P + \varepsilon_{PCT}",
    ):
        tex = tex.replace(
            f"\\[{equation}\\]",
            f"\\[\\resizebox{{\\textwidth}}{{!}}{{${equation}$}}\\]",
        )
    # PDFLaTeX-safe replacements for the remaining Unicode mathematical symbols.
    replacements = {
        "−": "$-$",
        "→": "$\\rightarrow$",
        "±": "$\\pm$",
        "×": "$\\times$",
        "≈": "$\\approx$",
        "≥": "$\\geq$",
        "²": "$^2$",
        "Δ": "$\\Delta$",
        "σ": "$\\sigma$",
    }
    for source, target in replacements.items():
        tex = tex.replace(source, target)
    # Horizontal rules were Markdown separators, not manuscript content.
    tex = re.sub(
        r"\s*\\begin\{center\}\\rule\{0\.5\\linewidth\}\{0\.5pt\}\\end\{center\}\s*",
        "\n\n",
        tex,
    )
    return tex


def write_metadata() -> None:
    abstract_match = re.search(
        r"## Abstract\s+(.*?)\s+\*\*Keywords:",
        PAPER.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    if not abstract_match:
        raise ValueError("Could not extract abstract from PAPER.md")
    abstract = re.sub(r"\s+", " ", abstract_match.group(1)).strip()
    ascii_abstract = (
        abstract.replace("—", "--")
        .replace("–", "-")
        .replace("−", "-")
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    metadata = (
        f"Title: {TITLE}\n"
        "Author: Ayush Maurya\n"
        "Primary category: stat.AP\n"
        "Version: Working Paper, Version 0.1 -- July 2026\n\n"
        f"Abstract:\n{ascii_abstract}\n\n"
        "Suggested comments:\n"
        "Working paper. 27 pages, 1 figure, and 20 tables. Code, data documentation, and reproducibility materials are available "
        f"at {REPOSITORY}.\n\n"
        "License selection: Choose deliberately in the arXiv submission form; no selection is "
        "encoded in this package.\n"
    )
    (ARXIV / "arxiv_metadata.txt").write_text(metadata, encoding="ascii")


def write_readme(items: list[str]) -> None:
    readme = f"""# arXiv source package

Top-level TeX file: `main.tex`

Intended compiler: PDFLaTeX

Primary category: `stat.AP`

Working Paper, Version 0.1 -- July 2026

Replication repository: {REPOSITORY}

Package contents:

- `main.tex`: manuscript source
- `references.bib`: machine-readable bibliography registry
- `main.bbl`: self-contained rendered bibliography ({len(items)} entries)
- `measurement_model_concepts.png`: local figure
- `arxiv_metadata.txt`: ASCII-safe submission metadata

Do not upload the repository datasets as arXiv ancillary files. The license selected
on arXiv applies to the manuscript version and does not relicense third-party data.
"""
    (ARXIV / "README.md").write_text(readme, encoding="utf-8")


def write_zip() -> None:
    ZIP.parent.mkdir(parents=True, exist_ok=True)
    members = [
        TEX,
        BIB,
        BBL,
        PNG,
        ARXIV / "arxiv_metadata.txt",
        ARXIV / "README.md",
    ]
    missing = [path.name for path in members if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing arXiv package members: {missing}")
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in members:
            archive.write(path, path.name)


def main() -> None:
    if not shutil.which("pandoc"):
        raise FileNotFoundError("pandoc is required to build the arXiv package")
    if not PNG.is_file():
        raise FileNotFoundError(
            "Convert outputs/measurement_model_concepts.svg to "
            "arxiv/measurement_model_concepts.png before building"
        )
    run_pandoc()
    tex = TEX.read_text(encoding="utf-8")
    tex, items = extract_reference_items(tex)
    write_bibliographies(items)
    tex = clean_tex(tex)
    TEX.write_text(tex, encoding="utf-8")
    write_metadata()
    write_readme(items)
    write_zip()
    print(f"Built {ZIP.relative_to(ROOT)} with {len(items)} bibliography entries")


if __name__ == "__main__":
    main()
