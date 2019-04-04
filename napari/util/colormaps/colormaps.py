import os

from .vendored import colorconv
import numpy as np
import vispy.color

_matplotlib_list_file = os.path.join(os.path.dirname(__file__),
                                     'matplotlib_cmaps.txt')
with open(_matplotlib_list_file) as fin:
    matplotlib_colormaps = [line.rstrip() for line in fin]


def _all_rgb():
    """Return all 256**3 valid rgb tuples."""
    base = np.arange(256, dtype=np.uint8)
    r, g, b = np.meshgrid(base, base, base, indexing='ij')
    return np.stack((r, g, b), axis=-1).reshape((-1, 3))


# obtained with colorconv.rgb2luv(_all_rgb().reshape((-1, 256, 3)))
LUVMIN = np.array([0., -83.07790815, -134.09790293])
LUVMAX = np.array([100., 175.01447356, 107.39905336])
LUVRNG = LUVMAX - LUVMIN

# obtained with colorconv.rgb2lab(_all_rgb().reshape((-1, 256, 3)))
LABMIN = np.array([0., -86.18302974, -107.85730021])
LABMAX = np.array([100., 98.23305386, 94.47812228])
LABRNG = LABMAX - LABMIN


def _validate_rgb(colors, *, tolerance=0.):
    """Return the subset of colors that is in [0, 1] for all channels.

    Parameters
    ----------
    colors : array of float, shape (N, 3)
        Input colors in RGB space.

    Other Parameters
    ----------------
    tolerance : float, optional
        Values outside of the range by less than ``tolerance`` are allowed and
        clipped to be within the range.

    Returns
    -------
    filtered_colors : array of float, shape (M, 3), M <= N
        The subset of colors that are in valid RGB space.

    Examples
    --------
    >>> colors = np.array([[  0. , 1.,  1.  ],
    ...                    [  1.1, 0., -0.03],
    ...                    [  1.2, 1.,  0.5 ]])
    >>> _validate_rgb(colors)
    array([[0., 1., 1.]])
    >>> _validate_rgb(colors, tolerance=0.15)
    array([[0., 1., 1.],
           [1., 0., 0.]])
    """
    lo = 0 - tolerance
    hi = 1 + tolerance
    valid = np.all((colors > lo) & (colors < hi), axis=1)
    filtered_colors = np.clip(colors[valid], 0, 1)
    return filtered_colors


def _low_discrepancy_image(image, seed=0.5):
    """Generate a 1d discrepancy sequence of coordinates.

    Parameters
    ----------
    labels : array of int
        A set of labels or label image.
    seed : float
        The seed from which to start the quasirandom sequence.

    Returns
    -------
    image_out : array of float
        The set of ``labels`` remapped to [0, 1] quasirandomly.

    """
    phi = 1.6180339887498948482
    image_out = (seed + image / phi) % 1
    return image_out


def _low_discrepancy(dim, n, seed=0.5):
    """Generate a 1d, 2d, or 3d low discrepancy sequence of coordinates.

    Parameters
    ----------
    dim : one of {1, 2, 3}
        The dimensionality of the sequence.
    n : int
        How many points to generate.
    seed : float or array of float, shape (dim,)
        The seed from which to start the quasirandom sequence.

    Returns
    -------
    pts : array of float, shape (n, dim)
        The sampled points.

    References
    ----------
    ..[1]: http://extremelearning.com.au/unreasonable-effectiveness-of-quasirandom-sequences/
    """
    phi1 = 1.6180339887498948482
    phi2 = 1.32471795724474602596
    phi3 = 1.22074408460575947536
    seed = np.broadcast_to(seed, (1, dim))
    phi = np.array([phi1, phi2, phi3])
    g = 1 / phi
    n = np.reshape(np.arange(n), (n, 1))
    pts = (seed + (n * g[:dim])) % 1
    return pts


def _color_random(n, *, colorspace='lab', tolerance=0.0, seed=0.5):
    """Generate n random RGB colors uniformly from LAB or LUV space.

    Parameters
    ----------
    n : int
        Number of colors to generate.
    colorspace : str, one of {'lab', 'luv', 'rgb'}
        The colorspace from which to get random colors.
    tolerance : float
        How much margin to allow for out-of-range RGB values (these are
        clipped to be in-range).
    seed : float or array of float, shape (3,)
        Value from which to start the quasirandom sequence.

    Returns
    -------
    rgb : array of float, shape (n, 3)
        RGB colors chosen uniformly at random from given colorspace.
    """
    factor = 6  # about 1/5 of random LUV tuples are inside the space
    expand_factor = 2
    rgb = np.zeros((0, 3))
    while len(rgb) < n:
        random = _low_discrepancy(3, n * factor, seed=seed)
        if colorspace == 'luv':
            raw_rgb = colorconv.luv2rgb(random * LUVRNG + LUVMIN)
        elif colorspace == 'rgb':
            raw_rgb = random
        else:  # 'lab' by default
            raw_rgb = colorconv.lab2rgb(random * LABRNG + LABMIN)
        rgb = _validate_rgb(raw_rgb, tolerance=tolerance)
        factor *= expand_factor
    return rgb[:n]


def label_colormap(num_colors=256, seed=0.5):
    """Produce a colormap suitable for use with a given label set.

    Parameters
    ----------
    num_colors : int, optional
        Number of unique colors to use. Default used if not given.
    seed : float or array of float, length 3
-       The seed for the random color generator.

    Returns
    -------
    cmap : vispy.color.Colormap
        A colormap for use with labels are remapped to [0, 1].

    Notes
    -----
    0 always maps to fully transparent.
    """
    midpoints = np.linspace(0, 1, num_colors - 1)
    control_points = np.concatenate(([0.], midpoints, [1.]))
    # make sure to add an alpha channel to the colors
    colors = np.concatenate((_color_random(num_colors, seed=seed),
                             np.full((num_colors, 1), 1)), axis=1)
    colors[0, :] = 0  # ensure alpha is 0 for label 0
    cmap = vispy.color.Colormap(colors=colors, controls=control_points,
                                interpolation='zero')
    return cmap



def label_random_colormap(labels, seed=[0.5,0.5,0.5], max_label=None):
    """Attempt at a generating a random colormap shader.ArithmeticError

    Parameters
    ----------
    labels : array of int
        A set of labels or label image.
    seed : float or array of float, length 3
        The seed for the low discrepancy sequence generator.

    Returns
    -------
    cmap : vispy.color.Colormap
        A colormap for use with ``labels``. The labels are remapped so that
        the maximum label falls on 1.0, since vispy requires colormaps to map
        within [0, 1].
    
        Notes
    -----
    This is based on the shader included with neuroglancer:
        https://github.com/google/neuroglancer/blob/master/src/neuroglancer/segment_color.ts

    """
    seed = sum(seed)
    return LabelColormap(seed=seed)


class LabelColormap(vispy.color.colormap.BaseColormap):
    def __init__(self, seed=0.5):
        self.seed = seed
        self.update_shader()

    def update_shader(self):
        self.glsl_map = self.glsl_map_base.replace('$seed', "%.3f" % self.seed)
    
    colors = vispy.color.color_array.ColorArray([(0., .33, .66, 1.0),
              (.33, .66, 1., 1.0)])

    glsl_map_base = """
    vec4 bad_random(float t) {
        float r = fract(sin(1+(971*t*$seed)));
        float g = fract(tan(1+(829*t*$seed)));
        float b = fract(cos(1+(419*t*$seed)));
        return vec4(r, g, b, 1.0);
    }
    """

    def map(self, t):
        # TODO: Implement this version
        rgba = self.colors.rgba
        smoothed = vispy.color.colormap.smoothstep(rgba[0, :3], rgba[1, :3], t)
        return np.hstack((smoothed, np.ones((len(t), 1))))

