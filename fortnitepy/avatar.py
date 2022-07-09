from typing import Dict, Optional


class Avatar:
    """Represents a friend's avatar. This is always related to the outfit
    the friend has equipped."""

    __slots__ = ('_namespace', '_asset_type', '_asset')

    def __init__(self, data: Dict[str, str]) -> None:
        self._namespace = data['namespace']

        avatar_id = data['avatarId']
        if avatar_id:
            split = avatar_id.split(':')
            self._asset_type = split[0]
            self._asset = split[1]
        else:
            self._asset_type = None
            self._asset = None

    def __repr__(self) -> str:
        return ('<Avatar asset={0.asset!r} '
                'asset_type={0.asset_type!r}>'.format(self))

    def __eq__(self, other) -> bool:
        return isinstance(other, Avatar) and \
            other.namespace == self.namespace and \
            other.asset_type == self.asset_type and \
            other.asset == self.asset

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    @property
    def namespace(self) -> str:
        """:class:`str`: The namespace of the avatar."""
        return self._namespace

    @property
    def asset_type(self) -> Optional[str]:
        """Optional[:class:`str`]: The asset type. This is usually ``ATHENACHARACTER``
        If the friend has no avatar set, or has a default character set,
        then this will be ``None``.
        """
        return self._asset_type

    @property
    def asset(self) -> Optional[str]:
        """Optional[:class:`str`]: The asset of the avatar. This is usually a
        CID in full caps. If the friend has no avatar set, or has a default
        character set, then this will be ``None``.
        """
        return self._asset
