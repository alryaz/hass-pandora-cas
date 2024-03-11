"""Processor for tracker icon registry"""

import logging
import re
from os import listdir
from os.path import dirname, join, isfile
from typing import Final, Optional


DEFAULT_CURSORS_PATH: Final = join(dirname(__file__), "cursors")

_RE_TRANSFORMATION = re.compile(r"rotate\((-?[0-9.]+)\s+256\s+256\)")
_RE_FILL = re.compile(r"fill:#000000")

_LOGGER = logging.getLogger(__name__)


class ImagesDefaultDict(dict):
    def __init__(
        self, default_cursor: str, autoload: bool = True, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.default_cursor = default_cursor
        if autoload:
            self.load_image_registry()

    def __getitem__(self, item: str):
        try:
            return super().__getitem__(item)
        except LookupError:
            if item == self.default_cursor:
                raise
            return self[self.default_cursor]

    def load_image_registry(self, path: str = DEFAULT_CURSORS_PATH) -> None:
        for file in listdir(path):
            if not (
                file.endswith(".svg") and isfile(file_path := join(path, file))
            ):
                continue
            with open(file_path, "r", encoding="utf8") as fp:
                image_contents = fp.read()
            if not (m := _RE_TRANSFORMATION.search(image_contents)):
                _LOGGER.warning(
                    f"Image registry could not load {file} because it does "
                    f"not contain expected transformation instruction"
                )
                continue
            if not _RE_FILL.search(image_contents):
                _LOGGER.warning(
                    f"Image registry could not load {file} because it does "
                    f"not contain expected fill instruction"
                )
                continue
            self[file[:-4]] = (
                _RE_FILL.sub(
                    "fill:{fill}",
                    _RE_TRANSFORMATION.sub(
                        "rotate({rotation} 256 256)", image_contents
                    ),
                ),
                float(m.group(1)),
            )

    def get_image(
        self,
        car_type: str,
        fill: str | None = None,
        rotation: float | None = None,
    ) -> str:
        base_code, base_rotation = self[car_type]
        return base_code.format(
            fill=(fill or "#000000"),
            rotation=(float(rotation or 0.0) + base_rotation) % 360,
        )


CURSOR_DEFAULT: Final = "arrow"
IMAGE_REGISTRY: Final = ImagesDefaultDict(CURSOR_DEFAULT)
