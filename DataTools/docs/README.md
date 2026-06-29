# DataTools Documentation

This folder contains markdown documentation and source assets for DataTools.

## Folder Structure

- `screenshots/`: Image assets referenced by markdown pages.
- `scripts/`: Helper scripts to generate markdown files.
- `generated/`: Generated manuals (for example, Settings and Matching Viewer).

## Generate Settings Markdown

Run from repository root:

```powershell
.venv\Scripts\python.exe DataTools\docs\scripts\generate_settings_markdown.py
```

Optional custom title:

```powershell
.venv\Scripts\python.exe DataTools\docs\scripts\generate_settings_markdown.py --title "DataTools Settings Menu v0.1"
```

## Generate Matching Viewer Manual

Run from repository root:

```powershell
.venv\Scripts\python.exe DataTools\docs\scripts\generate_matching_viewer_markdown.py
```

Skip screenshot capture and regenerate markdown only:

```powershell
.venv\Scripts\python.exe DataTools\docs\scripts\generate_matching_viewer_markdown.py --skip-screenshots
```
