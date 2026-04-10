# Desktop App Resources

Place your app icon files here:

- `icon.ico` — Windows application icon (256x256 recommended, multi-resolution)
- `icon.png` — PNG version for use in UI (256x256)

## Generating an icon

You can convert a PNG to ICO using online tools like:
- https://convertio.co/png-ico/
- https://icoconvert.com/

Or use ImageMagick:
```bash
magick convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico
```
