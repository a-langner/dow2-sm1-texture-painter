from PIL import (
    Image,
)
from pathlib import Path
from collections.abc import Mapping, Sequence

from src.texture_naming import (
    DEFAULT_TEXTURE_NAMING,
    TextureKind,
    TextureNamingProfile,
    with_texture_kind,
)


DOW1_DEFAULT_GROUP_TAG = "default"
TemTexturePaths = dict[str, Path]
TemFileGroups = dict[str, TemTexturePaths]


def team_color_output_path(
    group_name: str,
    destination: Path,
    extension: str,
    profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING,
) -> Path | None:
    """Build a packed team-color output path for one DoW1 source group.

    A terminal ``default`` group tag is a DoW1 input convention and is removed
    before the active profile's team-color suffix is applied.
    """
    name_parts = group_name.rsplit("_", 1)
    if (
        len(name_parts) == 2
        and name_parts[1].casefold() == DOW1_DEFAULT_GROUP_TAG.casefold()
    ):
        group_name = name_parts[0]
    extension = extension.lstrip(".")
    if not group_name or not extension:
        return None
    output_candidate = Path(destination) / f"{group_name}.{extension}"
    return with_texture_kind(output_candidate, TextureKind.TEAM_COLOR, profile)


def get_tem_filenames(path: Path, src_format: Sequence[str]) -> TemFileGroups:
    file_suffix = set(["Primary", "Secondary", "Trim", "Weapon"])

    def check_if_tem_exist(files_dict: TemFileGroups) -> None:
        """Check if the 4 files necessary to construct packed tem files exists

        :param files_dict: a dict containing unit name prefix as a key
            to access a nested dict containing the file path as a value
            an its suffix as key,
            e.g {'space_marine_unit':
                    {
                    'Primary': Path('space_marine_unit_Primary.tga)',
                    'Secondary': Path('space_marine_unit_Secondary.tga)',
                    'Trim': Path('space_marine_unit_Trim.tga)',
                    'Weapon': Path('space_marine_unit_Weapon.tg)a'
                    }
                }
        :raises FileNotFoundError: Missing tem textures
        """
        for v in files_dict.values():
            diff = list(set(v.keys()) - file_suffix)
            if len(diff) > 0:
                filetype_missing = ", ".join(diff)
                raise FileNotFoundError(
                    f"Missing {filetype_missing} tem textures files"
                )

    def find_tem_files(file_paths: list[Path]) -> TemFileGroups:
        files_dict: TemFileGroups = {}
        """
            Dawn of War 1 team colour texture used for the army painter are named
            with the following pattern :
            {unit_name}_Primary -> First color/Red mask
            {unit_name}_Secondary -> Second color/Blue mask
            {unit_name}_Trim -> Green color/Green mask
            {unit_name}_Weapon -> Fourth color/Alpha mask]

        :return: a dict containing unit name prefix as a key to access a nested
            dict containing the file path as a value an its suffix as key
            e.g {'space_marine_unit':
                    {
                    'Primary': Path('space_marine_unit_Primary.tga'),
                    'Secondary': Path('space_marine_unit_Secondary.tga'),
                    'Trim': Path('space_marine_unit_Trim.tga'),
                    'Weapon': Path('space_marine_unit_Weapon.tga)'
                    }
                }
        :rtype: nested dict
        """
        for file in file_paths:
            # Get the filename suffix, expecting: (Primary | Secondary | Trim | Weapon)
            f_suffix = file.stem.rsplit("_", 1)[-1]
            if f_suffix in file_suffix:
                # Get the filename prefix, expecting a unit name
                f_prefix = file.stem.rsplit("_", 1)[0]

                # Register unit name as a key to a dictionary containing the filename
                # as a value and their suffix as key
                if not f_prefix in files_dict:
                    files_dict[f_prefix] = {}
                files_dict[f_prefix][f_suffix] = file
        check_if_tem_exist(files_dict)
        return files_dict

    file_paths: list[Path] = []
    for format in src_format:
        file_paths.extend(Path(path).glob(f"*.{format}"))
    return find_tem_files(file_paths)


def convert_tem_texture(
    tem_textures: Mapping[str, Path],
    path: Path,
) -> Image.Image:
    # TODO: Find a way to handle icon banner pasted on textures
    # TODO: Check the size of Dawn of War 1 unit textures
    # can the different textures for the same unit differ in size?

    black_pixel_threshold = 1
    bands: list[Image.Image] = []

    if len(tem_textures) != 4:
        print(f"Found only {len(tem_textures)} textures :")

    for k, v in tem_textures.items():
        img = Image.open(path / v)

        # tem textures are grayscaled images, therefore we can convert them
        # to 8 bit pixel format, each image will be used as a band/chan
        # upon Image.merge() function call
        img.convert("L")
        white_chan = img.getchannel(0)

        # Each gray pixel has to be set to 255, this is how dawn of war 2
        # tem textures were made, if not, the blending within texture painter
        # will be darken
        colored_mask = Image.eval(
            white_chan, lambda x: 255 if x >= black_pixel_threshold else 0
        )
        bands.append(colored_mask)

        # Debug
        # colored_mask.save(path / ("test_" + k + ".tga"), "tga")

    mode = "RGBA" if len(bands) == 4 else "RGB"
    return Image.merge(mode=mode, bands=bands)


def exec_convert(
    path: Path,
    src_format: Sequence[str],
    dest_format: str,
    profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING,
) -> None:
    files_dict = get_tem_filenames(path, src_format)
    for k, textures in files_dict.items():
        result = convert_tem_texture(textures, path)
        output_path = team_color_output_path(k, path, dest_format, profile)
        if output_path is None:
            raise ValueError(f"Cannot create a team-color filename from '{k}'.")
        result.save(output_path, dest_format)


def local_test() -> None:
    # Put test sample texture in /assets/dow1 directory
    path = Path.cwd() / "assets/dow1"
    exec_convert(path, ["tga"], "tga")


if __name__ == "__main__":
    local_test()
