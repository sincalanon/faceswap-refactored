#!/usr/bin/env python3
"""
Library for serializing python objects to and from various different serializer formats
"""
from __future__ import annotations

import json
import logging
import os
import pickle
import typing as T
import zlib

from io import BytesIO

import numpy as np

from lib.utils import FaceswapError, get_module_objects

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

logger = logging.getLogger(__name__)


class Serializer:
    """ A convenience class for various serializers.

    This class should not be called directly as it acts as the parent for various serializers.
    All serializers should be called from :func:`get_serializer` or
    :func:`get_serializer_from_filename`

    Example
    -------
    >>> from lib.serializer import get_serializer
    >>> serializer = get_serializer('json')
    >>> json_file = '/path/to/json/file.json'
    >>> data = serializer.load(json_file)
    >>> serializer.save(json_file, data)

    """
    def __init__(self) -> None:
        self._file_extension: str | None = None
        self._write_option = "wb"
        self._read_option = "rb"

    @property
    def file_extension(self) -> str | None:
        """ str: The file extension of the serializer """
        return self._file_extension

    def save(self, filename: str, data: T.Any) -> None:
        """ Serialize data and save to a file

        Parameters
        ----------
        filename: str
            The path to where the serialized file should be saved
        data: varies
            The data that is to be serialized to file

        Example
        ------
        >>> serializer = get_serializer('json')
        >>> data ['foo', 'bar']
        >>> json_file = '/path/to/json/file.json'
        >>> serializer.save(json_file, data)
        """
        logger.debug("filename: %s, data type: %s", filename, type(data))
        filename = self._check_extension(filename)
        try:
            with open(filename, self._write_option) as s_file:
                s_file.write(self.marshal(data))
        except IOError as err:
            msg = f"Error writing to '{filename}': {err.strerror}"
            raise FaceswapError(msg) from err

    def _check_extension(self, filename: str) -> str:
        """ Check the filename has an extension. If not add the correct one for the serializer """
        extension = os.path.splitext(filename)[1]
        retval = filename if extension else f"{filename}.{self.file_extension}"
        logger.debug("Original filename: '%s', final filename: '%s'", filename, retval)
        return retval

    def load(self, filename: str) -> T.Any:
        """ Load data from an existing serialized file

        Parameters
        ----------
        filename: str
            The path to the serialized file

        Returns
        ----------
        data: varies
            The data in a python object format

        Example
        ------
        >>> serializer = get_serializer('json')
        >>> json_file = '/path/to/json/file.json'
        >>> data = serializer.load(json_file)
        """
        logger.debug("filename: %s", filename)
        try:
            with open(filename, self._read_option) as s_file:
                data = s_file.read()
                logger.debug("stored data type: %s", type(data))
                retval = self.unmarshal(data)

        except IOError as err:
            msg = f"Error reading from '{filename}': {err.strerror}"
            raise FaceswapError(msg) from err
        logger.debug("data type: %s", type(retval))
        return retval

    def marshal(self, data: T.Any) -> bytes:
        """ Serialize an object

        Parameters
        ----------
        data: varies
            The data that is to be serialized

        Returns
        -------
        data: varies
            The data in a the serialized data format

        Example
        ------
        >>> serializer = get_serializer('json')
        >>> data ['foo', 'bar']
        >>> json_data = serializer.marshal(data)
        """
        logger.debug("data type: %s", type(data))
        try:
            retval = self._marshal(data)
        except Exception as err:
            msg = f"Error serializing data for type {type(data)}: {str(err)}"
            raise FaceswapError(msg) from err
        logger.debug("returned data type: %s", type(retval))
        return retval

    def unmarshal(self, serialized_data: bytes) -> T.Any:
        """ Unserialize data to its original object type

        Parameters
        ----------
        serialized_data: varies
            Data in serializer format that is to be unmarshalled to its original object

        Returns
        -------
        data: varies
            The data in a python object format

        Example
        ------
        >>> serializer = get_serializer('json')
        >>> json_data = <json object>
        >>> data = serializer.unmarshal(json_data)
        """
        logger.debug("data type: %s", type(serialized_data))
        try:
            retval = self._unmarshal(serialized_data)
        except Exception as err:
            msg = f"Error unserializing data for type {type(serialized_data)}: {str(err)}"
            raise FaceswapError(msg) from err
        logger.debug("returned data type: %s", type(retval))
        return retval

    def _marshal(self, data: T.Any) -> bytes:
        """ Override for serializer specific marshalling """
        raise NotImplementedError()

    def _unmarshal(self, data: bytes) -> T.Any:
        """ Override for serializer specific unmarshalling """
        raise NotImplementedError()


class _YAMLSerializer(Serializer):
    """ YAML Serializer """
    def __init__(self) -> None:
        super().__init__()
        self._file_extension = "yml"

    def _marshal(self, data: T.Any) -> bytes:
        return yaml.dump(data, default_flow_style=False).encode("utf-8")

    def _unmarshal(self, data: bytes) -> T.Any:
        return yaml.load(data.decode("utf-8", errors="replace"), Loader=yaml.FullLoader)


class _JSONSerializer(Serializer):
    """ JSON Serializer """
    def __init__(self) -> None:
        super().__init__()
        self._file_extension = "json"

    def _marshal(self, data: T.Any) -> bytes:
        return json.dumps(data, indent=2).encode("utf-8")

    def _unmarshal(self, data: bytes) -> T.Any:
        return json.loads(data.decode("utf-8", errors="replace"))


class _PickleSerializer(Serializer):
    """ Pickle Serializer """
    def __init__(self) -> None:
        super().__init__()
        self._file_extension = "pickle"

    def _marshal(self, data: T.Any) -> bytes:
        return pickle.dumps(data)

    def _unmarshal(self, data: bytes) -> T.Any:
        return pickle.loads(data)


class _NPYSerializer(Serializer):
    """ NPY Serializer """
    def __init__(self) -> None:
        super().__init__()
        self._file_extension = "npy"

    def _marshal(self, data: T.Any) -> bytes:
        """ NPY Marshal to bytesIO so standard bytes writer can write out """
        b_handler = BytesIO()
        np.save(b_handler, data)
        b_handler.seek(0)
        return b_handler.read()

    def _unmarshal(self, data: bytes) -> T.Any:
        """ NPY Unmarshal to bytesIO so we can use numpy loader """
        b_handler = BytesIO(data)
        retval = np.load(b_handler)
        del b_handler
        if retval.dtype == "object":
            retval = retval[()]
        return retval


class _CompressedSerializer(Serializer):
    """ A compressed pickle serializer for Faceswap """
    def __init__(self) -> None:
        super().__init__()
        self._file_extension = "fsa"
        self._child = _PickleSerializer()

    def _marshal(self, data: T.Any) -> bytes:
        """ Pickle and compress data """
        data = self._child._marshal(data)  # pylint:disable=protected-access
        return zlib.compress(data)

    def _unmarshal(self, data: bytes) -> T.Any:
        """ Decompress and unpicke data """
        data = zlib.decompress(data)
        return self._child._unmarshal(data)  # pylint:disable=protected-access


_SERIALIZERS: dict[str, type[Serializer]] = {
    "npy": _NPYSerializer,
    "compressed": _CompressedSerializer,
    "json": _JSONSerializer,
    "pickle": _PickleSerializer,
    "yaml": _YAMLSerializer}
"""dict[str, type[Serializer]]: Serializer name to serializer class lookup"""

_EXTENSIONS: dict[str, str] = {".json": "json",
                               ".p": "pickle",
                               ".pickle": "pickle",
                               ".npy": "npy",
                               ".fsa": "compressed",
                               ".yaml": "yaml",
                               ".yml": "yaml"}
"""dict[str, str]: File extension to serializer name lookup"""


def _yaml_fallback() -> Serializer:
    """ Return the JSON serializer when YAML has been requested but PyYAML is not installed """
    logger.warning("You must have PyYAML installed to use YAML as the serializer.\n"
                   "Switching to JSON as the serializer.")
    return _JSONSerializer()


def get_serializer(serializer: T.Literal["json", "pickle", "yaml", "npy", "compressed"]
                   ) -> Serializer:
    """ Obtain a serializer object

    Parameters
    ----------
    serializer: {'json', 'pickle', yaml', 'npy', 'compressed'}
        The required serializer format

    Returns
    -------
    serializer: :class:`Serializer`
        A serializer object for handling the requested data format. If the requested format is
        not recognized (or is YAML and PyYAML is not installed), a JSON serializer is returned

    Example
    -------
    >>> serializer = get_serializer('json')
    """
    name = serializer.lower()
    retval: Serializer
    if name == "yaml" and not _HAS_YAML:
        retval = _yaml_fallback()
    elif name in _SERIALIZERS:
        retval = _SERIALIZERS[name]()
    else:
        logger.warning("Unrecognized serializer: '%s'. Returning json serializer", serializer)
        retval = _JSONSerializer()
    logger.debug(retval)
    return retval


def get_serializer_from_filename(filename: str) -> Serializer:
    """ Obtain a serializer object from a filename

    Parameters
    ----------
    filename: str
        Filename to determine the serializer type from

    Returns
    -------
    serializer: :class:`Serializer`
        A serializer object for handling the requested data format

    Example
    -------
    >>> filename = '/path/to/json/file.json'
    >>> serializer = get_serializer_from_filename(filename)
    """
    logger.debug("filename: '%s'", filename)
    extension = os.path.splitext(filename)[1].lower()
    logger.debug("extension: '%s'", extension)

    name = _EXTENSIONS.get(extension)
    retval: Serializer
    if name == "yaml" and not _HAS_YAML:
        retval = _yaml_fallback()
    elif name is not None:
        retval = _SERIALIZERS[name]()
    else:
        logger.warning("Unrecognized extension: '%s'. Returning json serializer", extension)
        retval = _JSONSerializer()
    logger.debug(retval)
    return retval


__all__ = get_module_objects(__name__)
