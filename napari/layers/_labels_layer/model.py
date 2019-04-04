import numpy as np
from numpy import clip
from copy import copy

from .._base_layer import Layer
from ..._vispy.scene.visuals import Image as ImageNode

from ...util.colormaps import colormaps
from ...util.event import Event

from .._register import add_to_viewer

from .view import QtLabelsLayer


@add_to_viewer
class Labels(Layer):
    """Labels (or segmentation) layer.

    An image layer where every pixel contains an integer ID corresponding
    to the region it belongs to.

    Parameters
    ----------
    image : np.ndarray
        Image data.
    meta : dict, optional
        Image metadata.
    multichannel : bool, optional
        Whether the image is multichannel. Guesses if None.
    name : str, keyword-only
        Name of the layer.
    num_colors : int, optional
        Number of unique colors to use. Default used if not given.
    **kwargs : dict
        Parameters that will be translated to metadata.
    """
    def __init__(self, label_image, meta=None, *, name=None, num_colors=256, **kwargs):
        if name is None and meta is not None:
            if 'name' in meta:
                name = meta['name']

        visual = ImageNode(None, method='auto')
        super().__init__(visual, name)
        self.events.add(colormap=Event)

        self.seed = 0.5
        self._raw_image = label_image
        self._max_label = np.max(label_image)
        self._image = colormaps._low_discrepancy_image(self._raw_image, self.seed)
        self._meta = meta
        self.interpolation = 'nearest'
        self.colormap_name = 'random'
        self.colormap = colormaps.label_colormap(num_colors)
        self.opacity = 0.7

        # update flags
        self._need_display_update = False
        self._need_visual_update = False

        self._qt_properties = QtLabelsLayer(self)

        self._node.clim = [0., 1.]
        self.events.colormap()

    def new_colormap(self):
        seed = np.random.random((3,))
        self.colormap = colormaps.label_random_colormap(self._image, seed=seed)
        self.events.colormap()

    def label_color(self, label):
        """Return the color corresponding to a specific label."""
        return self.colormap.map(colormaps._low_discrepancy_image(np.array([label]), self.seed))

    @property
    def image(self):
        """np.ndarray: Image data.
        """
        return self._image

    @image.setter
    def image(self, image):
        self._image = image
        self.refresh()

    @property
    def meta(self):
        """dict: Image metadata.
        """
        return self._meta

    @meta.setter
    def meta(self, meta):
        self._meta = meta
        self.refresh()

    @property
    def data(self):
        """tuple of np.ndarray, dict: Image data and metadata.
        """
        return self.image, self.meta

    @data.setter
    def data(self, data):
        self._image, self._meta = data
        self.refresh()

    def _get_shape(self):
        return self.image.shape

    def _update(self):
        """Update the underlying visual.
        """
        if self._need_display_update:
            self._need_display_update = False

            self.viewer.dims._child_layer_changed = True
            self.viewer.dims._update()

            self._node._need_colortransform_update = True
            self._set_view_slice(self.viewer.dims.indices)

        if self._need_visual_update:
            self._need_visual_update = False
            self._node.update()

    def _refresh(self):
        """Fully refresh the underlying visual.
        """
        self._need_display_update = True
        self._update()

    def _slice_image(self, indices, image=None):
        """Determines the slice of image given the indices.

        Parameters
        ----------
        indices : sequence of int or slice
            Indices to slice with.
        image : array, optional
            The image to slice. Defaults to self._image if None.

        Returns
        -------
        sliced : array or value
            The requested slice.
        """
        if image is None:
            image = self._image
        ndim = self.ndim
        indices = list(indices)[:ndim]

        for dim in range(len(indices)):
            max_dim_index = self.image.shape[dim] - 1

            try:
                if indices[dim] > max_dim_index:
                    indices[dim] = max_dim_index
            except TypeError:
                pass

        return image[tuple(indices)]

    def _set_view_slice(self, indices):
        """Sets the view given the indices to slice with.

        Parameters
        ----------
        indices : sequence of int or slice
            Indices to slice with.
        """
        sliced_image = self._slice_image(indices)
        self._node.set_data(sliced_image)

        self._need_visual_update = True
        self._update()

    @property
    def method(self):
        """string: Selects method of rendering image in case of non-linear
        transforms. Each method produces similar results, but may trade
        efficiency and accuracy. If the transform is linear, this parameter
        is ignored and a single quad is drawn around the area of the image.

            * 'auto': Automatically select 'impostor' if the image is drawn
              with a nonlinear transform; otherwise select 'subdivide'.
            * 'subdivide': ImageVisual is represented as a grid of triangles
              with texture coordinates linearly mapped.
            * 'impostor': ImageVisual is represented as a quad covering the
              entire view, with texture coordinates determined by the
              transform. This produces the best transformation results, but may
              be slow.
        """
        return self._node.method

    @method.setter
    def method(self, method):
        self._node.method = method

    def get_value(self, position, indices):
        """Returns coordinates, values, and a string for a given mouse position
        and set of indices.

        Parameters
        ----------
        position : sequence of two int
            Position of mouse cursor in canvas.
        indices : sequence of int or slice
            Indices that make up the slice.

        Returns
        ----------
        coord : sequence of int
            Position of mouse cursor in data.
        label : int
            Value of the label image at the coord.
        msg : string
            String containing a message that can be used as
            a status update.
        """
        transform = self._node.canvas.scene.node_transform(self._node)
        pos = transform.map(position)
        pos = [clip(pos[1], 0, self.shape[0]-1), clip(pos[0], 0,
                                                      self.shape[1]-1)]
        coord = copy(indices)
        coord[0] = int(pos[0])
        coord[1] = int(pos[1])
        label = self._slice_image(coord, image=self._raw_image)
        msg = f'{coord}, {self.name}, label {label}'
        return coord, label, msg

    def on_mouse_move(self, event):
        """Called whenever mouse moves over canvas.
        """
        if event.pos is None:
            return
        coord, value, msg = self.get_value(event.pos, self.viewer.dims.indices)
        self.status = msg
