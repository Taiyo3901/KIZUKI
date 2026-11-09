"""Stage 4b on its own: boxes -> masks, and the Vision name filter."""
import numpy as np

from pipeline.object_mask import MockObjectDetector, boxes_mask, build_ignore_mask, mask_names
from pipeline.settings import Settings
from tests.helpers import make_wall


class Fixed:
    def __init__(self, regions):
        self.regions = regions

    def detect(self, jpeg_bytes, w, h):
        return self.regions


def test_boxes_mask_covers_the_box_and_its_padding_only():
    m = boxes_mask((100, 200), [(50, 40, 20, 10)], pad=0.5)
    assert m[45, 60] == 255 and m[41, 41] == 255          # inside, and inside the padding (10px / 5px)
    assert m[0, 0] == 0 and m[99, 199] == 0
    assert m.shape == (100, 200)


def test_target_boxes_are_moved_into_reference_space_by_the_homography():
    wall = make_wall()
    shift = np.float32([[1, 0, 100], [0, 1, 50], [0, 0, 1]])        # target is 100px left / 50px above the reference
    s = Settings()
    mask, n = build_ignore_mask(wall, wall, shift, Fixed([(10, 10, 40, 40)]), s)
    assert n == 2                                                  # one box found in each photo
    assert mask[10 + 50 + 20, 10 + 100 + 20] == 255                # the target's box, after the shift
    assert mask[10 + 20, 10 + 20] == 255                           # the reference's own box
    assert mask[600, 900] == 0


def test_mock_detector_and_name_list():
    assert MockObjectDetector().detect(b"", 10, 10) == []
    names = mask_names("Person, Car ,")
    assert names == frozenset({"person", "car"})
