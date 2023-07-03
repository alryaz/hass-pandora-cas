import logging
import re
from collections import defaultdict
from os import listdir
from os.path import dirname, join, isfile
from typing import Final, Optional, Collection


def from_path(path: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>' + "<svg "
        'version="1.1" '
        'width="512" '
        'height="512" '
        'xmlns="http://www.w3.org/2000/svg" '
        'xmlns:svg="http://www.w3.org/2000/svg">' + "<path "
        'transform="rotate({rotation} 256 256)" '
        + 'style="fill:{fill};fill-opacity:1" d="'
        + path
        + '"/></svg>'
    )


DEFAULT_CURSORS_PATH: Final = join(dirname(__file__), "cursors")

_RE_TRANSFORMATION = re.compile(r"rotate\(([0-9\.]+)\s+256\s+256\)")
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
        fill: Optional[str] = None,
        rotation: Optional[float] = None,
    ) -> str:
        base_code, base_rotation = self[car_type]
        return base_code.format(
            fill=(fill or "#000000"),
            rotation=(float(rotation or 0.0) - base_rotation) % 360,
        )


CURSOR_DEFAULT: Final = "arrow"
IMAGE_REGISTRY: Final = ImagesDefaultDict(CURSOR_DEFAULT)
