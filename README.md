# sd-forge-prompt-blacklist

A [Stable Diffusion WebUI Forge](https://github.com/lllyasviel/stable-diffusion-webui-forge) (and compatible with A1111 WebUI) extension that automatically strips blacklisted words from prompts before generation.

Useful for:
- Removing words you never want a style/preset to inject (e.g. `watermark`, `signature`).
- Sanitizing prompts pulled from external sources.
- Keeping certain tokens out of all your generations regardless of who wrote the prompt.

## Features

- Separate blacklists for the **positive** and **negative** prompt.
- Whole-word, case-insensitive matching (e.g. blacklisting `cat` will not remove `category`).
- Enable / disable toggle in the panel.
- Settings auto-save to `config.json` and persist across restarts.
- Cleans up leftover artifacts (empty `(:1.2)` weight tags, double commas, etc.).
- Applies to txt2img, img2img, and hires-fix prompts.

## Installation

### Via WebUI (recommended)
1. Open WebUI Forge.
2. Go to **Extensions → Install from URL**.
3. Paste the repository URL and click **Install**.
4. Restart the WebUI.

### Manual
```bash
cd stable-diffusion-webui-forge/extensions
git clone <repo-url> sd-forge-prompt-blacklist
```
Then restart the WebUI.

## Usage

### Where to find the panel
Open the **txt2img** (or **img2img**) tab and scroll down past the prompt fields and the generation settings (Sampling method, Width/Height, CFG Scale, Seed, etc.). Among the collapsible panels — alongside "Hires. fix", "Refiner", "Script" — you'll find one labelled **Prompt Blacklist**. Click to expand it.

### Configuring
1. Expand the **Prompt Blacklist** accordion.
2. Enter words separated by commas in the **positive** and/or **negative** blacklist field.
3. Toggle **Enable filtering** on.
4. Generate as normal. Blacklisted words are stripped from the prompt before it reaches the sampler.

Settings save automatically — no button to press. They persist across restarts in `config.json` inside the extension folder.

## Notes & Limitations

- Matching is whole-word with word boundaries (`\b`). Multi-word entries like `blue sky` are matched as a sequence.
- If a blacklisted word lives inside a weight tag like `(blurry:1.3)`, the surrounding empty tag is cleaned up too.
- The filter runs after styles are applied, so words injected by a style are also caught.
- Order of removal does not preserve LoRA/embedding syntax inside the matched word — keep blacklist entries to plain words.

## License

MIT
