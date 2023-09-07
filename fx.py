# QLC+ plasma plugin is a 2D perlin noise generator
# then mapped to a range of interpolated colours
# https://github.com/mcallegari/qlcplus/blob/master/resources/rgbscripts/plasma.js


# https://adrianb.io/2014/08/09/perlinnoise.html
# perlin noise is generated over x,y plane and z (time) and is 1-dimensional

# QLC+ offers four presets with 2-4 control points
# Rainbow   0xFF0000, 0x00FF00, 0x0000FF
# Fire      0xFFFF00, 0xFF0000, 0x000040, 0xFF0000
# Abstract  0x5571FF, 0x00FFFF, 0xFF00FF, 0xFFFF00
# Ocean     0x003AB9, 0x02EAFF
# each pair of points is expanded to 300 samples, so ocean has 300, fire 900.

# possibly existing python implemantation of perlin noise?
# https://gitlab.com/atrus6/pynoise/-/tree/master/pynoise?ref_type=heads

import functools
import itertools
import math
from typing import Any, List

from registration import EFX, register_efx
from trait import RGB, Channel, IntensityChannel

# Hash lookup table as defined by Ken Perlin.  This is a randomly
# arranged array of all numbers from 0-255 inclusive.
# fmt: off
_perlin_permutation_lut: List[int] = [151, 160, 137, 91, 90, 15,
    131, 13, 201, 95, 96, 53, 194, 233, 7, 225, 140, 36, 103, 30, 69, 142, 8, 99, 37, 240, 21, 10, 23,
    190, 6, 148, 247, 120, 234, 75, 0, 26, 197, 62, 94, 252, 219, 203, 117, 35, 11, 32, 57, 177, 33,
    88, 237, 149, 56, 87, 174, 20, 125, 136, 171, 168, 68, 175, 74, 165, 71, 134, 139, 48, 27, 166,
    77, 146, 158, 231, 83, 111, 229, 122, 60, 211, 133, 230, 220, 105, 92, 41, 55, 46, 245, 40, 244,
    102, 143, 54, 65, 25, 63, 161, 1, 216, 80, 73, 209, 76, 132, 187, 208, 89, 18, 169, 200, 196,
    135, 130, 116, 188, 159, 86, 164, 100, 109, 198, 173, 186, 3, 64, 52, 217, 226, 250, 124, 123,
    5, 202, 38, 147, 118, 126, 255, 82, 85, 212, 207, 206, 59, 227, 47, 16, 58, 17, 182, 189, 28, 42,
    223, 183, 170, 213, 119, 248, 152, 2, 44, 154, 163, 70, 221, 153, 101, 155, 167, 43, 172, 9,
    129, 22, 39, 253, 19, 98, 108, 110, 79, 113, 224, 232, 178, 185, 112, 104, 218, 246, 97, 228,
    251, 34, 242, 193, 238, 210, 144, 12, 191, 179, 162, 241, 81, 51, 145, 235, 249, 14, 239, 107,
    49, 192, 214, 31, 181, 199, 106, 157, 184, 84, 204, 176, 115, 121, 50, 45, 127, 4, 150, 254,
    138, 236, 205, 93, 222, 114, 67, 29, 24, 72, 243, 141, 128, 195, 78, 66, 215, 61, 156, 180
] * 2
# fmt: on


def perlin(x: float, y: float, z: float) -> float:
    p = _perlin_permutation_lut

    # Calculate the "unit cube" that the point asked will be located in
    # The left bound is ( |_x_|,|_y_|,|_z_| ) and the right bound is that
    # plus 1.  Next we calculate the location (from 0.0 to 1.0) in that cube.
    # We also fade the location to smooth the result.
    xi: int = int(x) & 255
    yi: int = int(y) & 255
    zi: int = int(z) & 255
    xf = x - int(x)
    yf = y - int(y)
    zf = z - int(z)
    u = fade(xf)
    v = fade(yf)
    w = fade(zf)

    # int aaa, aba, aab, abb, baa, bba, bab, bbb;
    aaa = p[p[p[xi] + yi] + zi]
    aba = p[p[p[xi] + yi + 1] + zi]
    aab = p[p[p[xi] + yi] + zi + 1]
    abb = p[p[p[xi] + yi + 1] + zi + 1]
    baa = p[p[p[xi + 1] + yi] + zi]
    bba = p[p[p[xi + 1] + yi + 1] + zi]
    bab = p[p[p[xi + 1] + yi] + zi + 1]
    bbb = p[p[p[xi + 1] + yi + 1] + zi + 1]

    # The gradient function calculates the dot product between a pseudorandom
    # gradient vector and the vector from the input coordinate to the 8
    # surrounding points in its unit cube.
    # This is all then lerped together as a sort of weighted average based on the faded (u,v,w)
    # values we made earlier.
    # double x1, x2, y1, y2;
    x1 = lerp(grad(aaa, xf, yf, zf), grad(baa, xf - 1, yf, zf), u)
    x2 = lerp(grad(aba, xf, yf - 1, zf), grad(bba, xf - 1, yf - 1, zf), u)
    y1 = lerp(x1, x2, v)

    x1 = lerp(grad(aab, xf, yf, zf - 1), grad(bab, xf - 1, yf, zf - 1), u)
    x2 = lerp(grad(abb, xf, yf - 1, zf - 1), grad(bbb, xf - 1, yf - 1, zf - 1), u)
    y2 = lerp(x1, x2, v)

    return lerp(y1, y2, w)


def perlin01(x: float, y: float, z: float) -> float:
    # For convenience bound to 0 - 1
    # see https://digitalfreepen.com/2017/06/20/range-perlin-noise.html
    # 3D noise -sqrt(0.75) - sqrt(0.75)
    p = (perlin(x, y, z) + math.sqrt(2 / 4)) / (2 * math.sqrt(2 / 4))
    return max(0, min(1, p))


def grad(hash: int, x: float, y: float, z: float) -> float:
    # Take the hashed value and take the first 4 bits of it (15 == 0b1111)
    h: int = hash & 15
    # 8 = 0b1000
    # If the most significant bit (MSB) of the hash is 0 then set u = x.  Otherwise y.
    u: float = x if h < 8 else y
    v: float = 0

    # In Ken Perlin's original implementation this was another conditional operator (?:).  I
    # expanded it for readability.
    if h < 4:  # If the first and second significant bits are 0 set v = y
        v = y
    elif h == 12 or h == 14:  # If the first and second significant bits are 1 set v = x
        v = x
    else:  # If the first and second significant bits are not equal (0/1, 1/0) set v = z
        v = z

    # Use the last 2 bits to decide if u and v are positive or negative.  Then return their addition.
    p1 = u if (h & 1) == 0 else -u
    p2 = v if (h & 2) == 0 else -v
    return p1 + p2


def fade(t: float) -> float:
    # Fade function as defined by Ken Perlin.  This eases coordinate values
    # so that they will "ease" towards integral values.  This ends up smoothing
    # the final output.
    # 6t^5 - 15t^4 + 10t^3
    return t * t * t * (t * (t * 6 - 15) + 10)


def lerp(a: float, b: float, x: float) -> float:
    return a + x * (b - a)


@register_efx
class PerlinNoiseEFX(EFX):
    def __init__(self, count=0):
        self.speed = Channel()
        super().__init__()
        self.can_act_on = [Channel]
        self._count = count
        self._outputs: List[Channel] = []
        for i in range(count):
            o = IntensityChannel()
            self._outputs.append(o)
            setattr(self, f"o{i}", o)

    def tick(self, counter):
        # plasma.js scales the 2D grid of fixtures to fit a unit square, then scales
        # it back to a user editable total size, called 'scale'. So adding a fixture
        # *reduces* the effective scale, which doesn't seem right.
        # I've just mapped the coordinates as position, equivelent to scale=w or h
        # The output of perlin lies between -sqrt(0.5) and +sqrt(0.5)
        z = counter
        if self.enabled.value.pos > 0:
            for i in range(self._count):
                self._outputs[i].set(int(256 * perlin01(i, 1, z)))


@register_efx
class ColourInterpolateEFX(EFX):
    # Rainbow   0xFF0000, 0x00FF00, 0x0000FF
    # Fire      0xFFFF00, 0xFF0000, 0x000040, 0xFF0000
    # Abstract  0x5571FF, 0x00FFFF, 0xFF00FF, 0xFFFF00
    # Ocean     0x003AB9, 0x02EAFF

    def __init__(self, count=0, steps=100):
        self.speed = Channel()
        super().__init__()

        self.c1 = RGB()
        self.c1.set_hex("#FFFF00")
        self.c2 = RGB()
        self.c2.set_hex("#FF0000")
        self.c3 = RGB()
        self.c3.set_hex("#000040")
        self.c4 = RGB()
        self.c4.set_hex("#FF0000")

        self._count = count
        self._inputs: List[IntensityChannel] = []
        self._outputs: List[RGB] = []
        for i in range(count):
            inch = IntensityChannel()
            self._inputs.append(inch)
            setattr(self, f"i{i}", inch)
            och = RGB()
            self._outputs.append(och)
            setattr(self, f"o{i}", och)
            inch._patch_listener(functools.partial(self.remap_intensity, inch, och))

        self._interp = self.interpolate([self.c1, self.c2, self.c3, self.c4])

    def remap_intensity(self, inch, outch, source: Any):
        x = inch.value.pos
        n = self._interp[int(x / 256 * len(self._interp))]
        if self.enabled.value.pos > 0:
            n._copy_to(outch, None)

    def interpolate(self, control_points):
        o = []
        for i, j in itertools.pairwise(control_points):
            o.extend(i.interpolate_to(j, 100))
        return o

    def tick(self, counter):
        pass


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    # Generate some data...
    for z in range(10):
        x, y = np.meshgrid(np.linspace(0, 10, num=500), np.linspace(0, 10, num=500))
        z = np.vectorize(perlin)(x, y, z)
        print(pd.DataFrame(z.ravel()).describe())

    # Plot the grid

    plt.imshow(z)
    plt.gray()
    plt.show()
