# Claude Desktop — Native Qt6 Client for Arch Linux

A native, lightweight desktop client for the Anthropic Claude API built with PyQt6.
Glassmorphism UI with blur, pywal integration, project context loading, and full customization.

## Features

- **Native Qt6 UI** — Glassmorphism dark theme, translucent backgrounds, smooth scrolling
- **Streaming responses** — Real-time token-by-token display
- **Conversation history** — Saved locally in `~/.config/claude-desktop/history/`
- **Markdown rendering** — Code blocks, bold, italic, headers
- **Model selection** — Opus 4, Sonnet 4, Haiku 4.5
- **System prompts** — Customizable per-session
- **Project loading** — Load entire codebases into Claude's context (`Ctrl+O`)
- **pywal / wallust integration** — Auto-reload colors when wallpaper changes
- **Customizable fonts** — All installed system fonts selectable, monospace filter, live preview
- **Customizable colors** — 10 colors with color picker + hex input, pywal import
- **Blur support** — Kvantum, KWin forceblur, Hyprland
- **Transparency** — Adjustable window opacity (40-100%)
- **Keyboard shortcuts** — `Ctrl+N` new chat, `Ctrl+,` settings, `Ctrl+O` load project

## Installation

### Build from source

```bash
git clone https://github.com/xusader/claude-desktop.git
cd claude-desktop-qt6
makepkg -si
```

### Dependencies

- `python` `python-pyqt6` `python-anthropic` `qt6-base`
- Optional: `kvantum` (blur), `python-pywal` / `wallust` (color schemes)

## Configuration

On first launch, open **Settings** (`Ctrl+,`) and enter your Anthropic API key.

All settings are stored in `~/.config/claude-desktop/config.json`.

### pywal Integration

Claude Desktop automatically watches `~/.cache/wal/colors.json` for changes.
When you run `wal -i <image>`, colors update live — no restart needed.

Manual reload:

```bash
claude-desktop --reload-colors
```

### Project Loading

Press `Ctrl+O` to load a project folder. Claude receives the full project structure
and source file contents as context (~60 file extensions supported, ignores
`.git`, `node_modules`, `__pycache__`, etc.).

## Blur Setup

### Kvantum (recommended)

```bash
sudo pacman -S kvantum
```

Select a translucent Kvantum theme in Kvantum Manager.

### KWin ForceBlur

```bash
yay -S kwin-effects-forceblur
```

System Settings → Desktop Effects → disable "Blur" → enable "Force Blur".
Add window class `python3` or `claude-desktop`.

### Hyprland

Blur rules are set automatically via `hyprctl`.

## Keyboard Shortcuts

| Shortcut         | Action               |
|------------------|----------------------|
| `Enter`          | Send message         |
| `Shift+Enter`    | New line in input    |
| `Ctrl+N`         | New conversation     |
| `Ctrl+,`         | Open settings        |
| `Ctrl+O`         | Load project         |

## License

MIT
