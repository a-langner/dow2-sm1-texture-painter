# Army Painter

**Army Painter** is an easy-to-use texture recoloring tool for **Warhammer 40,000: Dawn of War II** and **Warhammer 40,000: Space Marine (Space Marine 1)**.

It allows you to quickly create and preview custom color schemes using the games' existing team-color masks. Choose your colors, apply a Pattern, fine-tune the result and export the finished texture — without having to manually edit individual mask channels in an image editor.

Army Painter is based on the original **dow2-texture-painter** by **Jaccouille (Marc Szilagyi)** and has since been expanded with support for **Space Marine 1** textures, Patterns, the Citadel Color library, additional image processing options, and many other features.

> **Army Painter is an unofficial community tool and is not affiliated with, endorsed by, or associated with Games Workshop, Citadel, Relic Entertainment, or their respective owners.**

**[Download the latest release](https://github.com/a-langner/dow2-sm1-texture-painter/releases)**

[View the Army Painter repository on GitHub](https://github.com/a-langner/dow2-sm1-texture-painter)

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

The four Color Slots represent the texture's four team-color channels. Click **Edit Color** for a slot to create a custom color or browse the Citadel Color Picker. Drag one Color Slot onto another to swap their complete colors and settings.

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

**Closest Color** compares the current color with the Citadel Color palette and shows the three closest matches. Each result includes its perceptual color difference (**ΔE00 / CIEDE2000**), and you can select the match you want to use.

## Patterns

Patterns let you save and reuse complete color schemes. Army Painter includes a separate set of built-in Patterns, which are always available and read-only, as well as your own editable User Patterns.

Use the Pattern panel to:

- create a User Pattern with **Save New**;
- apply changes to it with **Update**;
- **Rename** or **Delete** it;
- drag User Patterns into your preferred order; and
- mark User Patterns with colored stars to organize or highlight them.

You can export an individual built-in or User Pattern to share it, and import shared Patterns into your User Patterns. Use `Patterns -> Export Selected Pattern…` or `Patterns -> Import Pattern…`.

### Pattern Collections

A Pattern Collection packages all of your User Patterns together for backup or sharing. Use `Patterns -> Export All User Patterns…` to create a Collection and `Patterns -> Import Pattern Collection…` to restore or import one. Built-in Patterns remain separate and are not included in User Pattern Collections.

## Supported Games and Textures

### Dawn of War II

| Texture | Purpose |
|---|---|
| **DIF** | Base/diffuse texture |
| **TEM** | Team-color mask |
| **SPC** | Specular information |
| **DRT** | Dirt information |

### Space Marine 1

| Texture | Purpose |
|---|---|
| **DIF** | Base/diffuse texture |
| **PNT** | Team-color mask |
| **SPC** | Specular information |

### NRM

NRM normal maps are not part of Army Painter's recoloring workflow and are intentionally ignored.

To make selected team-color channels transparent in the exported texture, select the channels and enable **Apply alpha**.

## Undo, Redo, and Reset Workspace

Use **Undo** (`Ctrl+Z`) and **Redo** (`Ctrl+Y`) to move backward or forward through changes to the current editing workspace.

**Reset Workspace** restores the current workspace to its editing defaults. It does not delete persistent User Patterns or application settings.

## Settings and Factory Reset

Army Painter remembers relevant preferences and persistent user data between sessions.

Use `Edit -> Factory Reset...` to restore application settings and preferences. User Patterns are preserved by default; the confirmation dialog provides a separate option to delete them when explicitly selected.

## Batch Edit

Open `Tools -> Batch Edit Tools` to process or convert a folder of textures:

1. Choose one or more **Source formats**.
2. Choose the **Destination format**.
3. Choose the **Source folder**.
4. Choose the **Destination folder**.
5. Select **Process Batch Edit** to apply the current color scheme and processing settings to compatible DIF textures, or **Process Batch Convert** to convert compatible legacy mask groups.

**Process Batch Convert** retains the original utility for combining four previously extracted Dawn of War I team-color mask images into one compatible Team Color Mask. This conversion helper does not make Dawn of War I a fully supported Army Painter recoloring target.

## Updates

Use `Help -> About -> Check for Updates` to check GitHub Releases for a newer published version. Army Painter does not download or install updates automatically.

## Credits

### Current development

**a-langner (Andreas Langner)**

### Original application

**Jaccouille (Marc Szilagyi)**

Army Painter is based on Marc's original [dow2-texture-painter](https://github.com/Jaccouille/dow2-texture-painter).

### Citadel Color Data

Citadel Color data is sourced and adapted from [**Arcturus5404/miniature-paints**](https://github.com/Arcturus5404/miniature-paints) under the MIT License. See [Third-Party Notices](THIRD_PARTY_NOTICES.md) for complete attribution and license information.

## Disclaimer

**Army Painter is an unofficial community-created tool.**

It is not affiliated with, endorsed by, sponsored by, or associated with **Games Workshop, Citadel, Relic Entertainment**, or their respective owners.

Warhammer 40,000, Dawn of War, Space Marine, Citadel, and other related names and properties belong to their respective owners.

## License

Army Painter is released under the MIT License.

See [LICENSE](LICENSE) and [Third-Party Notices](THIRD_PARTY_NOTICES.md).

## Developing

This README is intended for users of Army Painter.

If you want to build Army Painter from source, contribute to the project, understand its architecture, or work on the codebase, see the [Development Documentation](docs/developing.md).
