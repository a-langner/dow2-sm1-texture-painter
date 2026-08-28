# Army Painter

**Army Painter** is an easy-to-use texture recoloring tool for **Warhammer 40,000: Dawn of War II** and **Warhammer 40,000: Space Marine (Space Marine 1)**.

It allows you to quickly create and preview custom color schemes using the games' existing team-color masks. Choose your colors, apply a Pattern, fine-tune the result and export the finished texture — without having to manually edit individual mask channels in an image editor.

Army Painter is based on the original **dow2-texture-painter** by **Jaccouille (Marc Szilagyi)** and has since been expanded with support for **Space Marine 1** textures, Patterns, Citadel colors, additional image processing options, and many other features.

> **Army Painter is an unofficial community tool and is not affiliated with, endorsed by, or associated with Games Workshop, Citadel, Relic Entertainment, or their respective owners.**

**[Download the latest release](https://github.com/a-langner/dow2-sm1-texture-painter/releases)**

<!-- TODO 1.0 screenshot: Main Army Painter window with a representative loaded texture -->

## Features

- Recolor **Dawn of War II** and **Space Marine 1** textures with four independently configurable team-color channels.
- Automatically find compatible **TEM/PNT, SPC, and DRT** companion textures where available.
- Discover multiple **TEM/PNT team-color masks** for a DIF texture and switch between available variants.
- See changes immediately with live preview, or hold **Show Original** to compare the source texture.
- Choose from **12 Blend Modes** and use Global or Per Color Brightness, Contrast, Saturation, and Opacity controls.
- Apply built-in Patterns or create, manage, import, and export User Patterns and Pattern Collections.
- Browse and search the Citadel Color library, including color categories, Citadel Favorites, named Custom Favorites, Recent Colors, and Closest Citadel Color matching.
- Rearrange complete Color Slot settings with drag-and-drop, or reuse colors and settings with copy and paste.
- Correct workspace edits with Undo and Redo.
- Process or convert folders of textures with Batch Edit tools.
- Check GitHub Releases for updates from within Army Painter.

## Getting Started

Recoloring a texture takes five basic steps:

1. Open a DIF texture.
2. Choose colors.
3. Choose a Pattern.
4. Fine-tune the result.
5. Save the finished texture.

### Open a texture

Select the game profile, then click **Select DIF Texture** and choose the base texture you want to recolor. Army Painter searches the same folder for compatible companion textures where available. Dawn of War II uses a **TEM** team-color mask, while Space Marine 1 uses a **PNT** mask.

If Army Painter finds multiple compatible masks for the DIF texture, use the **Team Color Mask** selector to switch between the available variants. The preview updates to show the selected mask.

### Choose colors

The four Color Slots represent the texture's four team-color channels. Click **Edit Color** for a slot to enter a manual/custom color or browse the Citadel Color Picker. Drag one Color Slot onto another to swap their complete colors and settings.

### Choose a Pattern

Select a built-in Pattern for a ready-made color scheme, or choose one of your reusable User Patterns. Applying a Pattern updates the live preview immediately.

### Fine-tune the result

Choose from **12 Blend Modes** and fine-tune the result using Brightness, Contrast, Saturation, and Opacity. **Global** processing applies one set of controls to the whole scheme; **Per Color** lets you configure each Color Slot independently.

Hold **Show Original** to compare your current live preview with the unprocessed DIF texture.

### Save or export

Choose `File -> Save as` or press `Ctrl+S`, select a destination and one of the supported output formats, then save the rendered texture.

## Color Picker

Army Painter includes a color picker designed specifically for miniature and Warhammer 40,000 color schemes.

Browse or search the bundled Citadel Color library through **Reds**, **Oranges**, **Yellows**, **Greens**, **Teals/Cyans**, **Blues**, **Purples**, **Pinks**, **Browns**, **Neutrals**, **All Colors**, and **Favorites**. You can also create a color manually using RGB, HSV, or Hex values.

<!-- TODO 1.0 screenshot: Citadel Color Picker -->

### Favorites

Add Citadel paints to Favorites for quick access. Manual RGB, HSV, or Hex colors can also be saved with a name as Custom Favorites.

### Recent Colors

Recent Colors keeps your latest confirmed Color Picker choices close at hand.

### Closest Citadel Color

**Closest Color** compares the current color with the Citadel palette and shows the three closest matches. Each result includes its perceptual color difference (**ΔE00 / CIEDE2000**), and you can select the match you want to use.

### Saved color patterns

Built-in patterns are bundled with the application and are read-only. Custom patterns are stored persistently outside the executable and are marked with `★` in the pattern list.

The custom-pattern file is stored at:

- Windows: `%LOCALAPPDATA%\DOW2-SM1 Texture Painter\user_patterns.json`
- Linux: `$XDG_DATA_HOME/DOW2-SM1 Texture Painter/user_patterns.json`, or `~/.local/share/DOW2-SM1 Texture Painter/user_patterns.json` by default
- macOS: `~/Library/Application Support/DOW2-SM1 Texture Painter/user_patterns.json`

Updating or replacing the application executable does not normally remove custom patterns because this file is stored separately.

### Editing color patterns

The Pattern panel uses a 2×2 button layout: `Save New`, `Update`, `Rename`, and `Delete`.

- `Save New` creates a custom Pattern from the colors currently shown, whether a built-in or custom Pattern is selected.
- `Update` replaces the stored colors of the selected custom Pattern.
- `Rename` changes only the selected custom Pattern's name.
- `Delete` permanently removes the selected custom Pattern.

Only custom, user-created Patterns can be updated, renamed, or deleted. Built-in Patterns remain read-only. Editing operations are stored persistently and remain available after restarting the application.

`Modified` appears when the current colors differ from the selected Pattern's stored colors. Color changes are not saved automatically: use `Update` to keep them, or `Edit -> Reset to Selected Pattern` to discard them. To create a new custom Pattern from any selected Pattern's stored colors, use `Edit -> Duplicate Selected Pattern…`.

Pattern import and export behavior is unchanged.

### Importing and exporting patterns

The `Patterns` menu contains commands for single patterns and Pattern Collections:

- `Import Pattern…`
- `Export Selected Pattern…`
- `Import Pattern Collection…`
- `Export All User Patterns…`

For single-pattern exchange, both built-in and custom patterns can be exported. Pattern exchange files use the `.pattern.json` suffix and contain versioned JSON, for example:

```json
{
    "format": "dow2-sm1-texture-painter-pattern",
    "version": 1,
    "name": "Example Pattern",
    "colors": {
        "primary_colour_name": "#112233",
        "secondary_colour_name": "#445566",
        "tint_colour_name": "#778899",
        "extra_colour_name": "#aabbcc"
    }
}
```

Imported patterns become custom, user-created patterns and receive the `★` marker in the pattern list. They are copied into persistent user storage, so deleting the original `.pattern.json` file later does not delete the imported pattern.

Built-in patterns cannot be overwritten. If an imported name matches an existing custom pattern, the application asks whether to rename the import, overwrite the existing pattern, or cancel. Nothing is overwritten without confirmation.

### Pattern Collections

`Export All User Patterns…` saves all custom, user-created patterns in one versioned JSON file with the `.pattern-collection.json` suffix. Built-in patterns are never included. The Collection name is informational and is not added to the names of its patterns.

```json
{
    "format": "dow2-sm1-texture-painter-pattern-collection",
    "version": 1,
    "name": "My Space Marine Patterns",
    "patterns": [
        {
            "name": "Blood Ravens Veteran",
            "colors": {
                "primary_colour_name": "#7f1919",
                "secondary_colour_name": "#d1b989",
                "tint_colour_name": "#242424",
                "extra_colour_name": "#ffffff"
            }
        }
    ]
}
```

`Import Pattern Collection…` validates the entire Collection before saving anything. If one pattern is invalid, or if names are duplicated within the Collection, the whole Collection is rejected. A confirmed import is atomic, so it is saved as one operation rather than as a series of partial imports.

Names that conflict with built-in patterns are always skipped because built-in patterns cannot be overwritten. For names that conflict with existing custom patterns, you can skip or overwrite them; **Skip existing user patterns** is the default. Collection import does not automatically rename conflicting patterns.

Single-pattern import and export remain available separately through `Import Pattern…` and `Export Selected Pattern…`.

You can apply dirt & specular texture by clicking on `Edit -> Apply dirt/specular`, those textures must be in the same folder as the diffuse ones and their filenames must follow the following pattern.

- {unit_name}\_drt.dds -> dirt
- {unit_name}\_spc.dds -> specular

You can replace color by transparency with selecting the color mask in the list and checking the `Apply alpha` box.

You can color multiple diffuse textures by using the batch edit tool, select the source directory where your textures are located, input format, output format and the destination directory, the name of the colored files will be the same as the original one, if input & output file have the same format, the output will overwrite the original diffuse texture. Batch edit tool does not process subfolder. Batch edit only works for diffuse texture ending with "\_dif", such as {unit_name}\_dif.dds, because it's the name format for Dawn of War 2 diffuse texture.

## Dawn of War 1 Texture

Dawn of War 1 uses a different format to store their tem textures, the 4 masks are separated into individual file stored in a RTX file, once you extract them with a third party tool, you can merge them into a single file using the batch tool editor. The converted texture can then be used to color Dawn of War 1 diffuse grayscale texture.

This tool is experimental and only process files from a folder in a "batch" manner.

Click `Tools` -> `Batch Edit Tools` -> `Process Batch Convert` to convert Dawn of War 1 tem textures to Dawn of War 2 tem format.

![example4](https://user-images.githubusercontent.com/7768858/148760310-08c01d18-182b-4680-a092-9e7689f4cb93.jpg)

Dawn of War 1 Trim 2 & Eye coloring aren't handled yet.

## Developing

[Developing Documentation](docs/developing.md)
