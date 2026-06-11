from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Generic, TypeVar

from qcodes.instrument import (
    ChannelList,
    Instrument,
    InstrumentBaseKWArgs,
    InstrumentChannel,
)
from qcodes.validators import Ints

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from qcodes.parameters import Parameter

log = logging.getLogger(__name__)

_TINSTR = TypeVar("_TINSTR", bound="MiniCircuitsSPDTBase")


class MiniCircuitsSPDTSwitchChannelBase(InstrumentChannel[_TINSTR], Generic[_TINSTR]):
    def __init__(
        self,
        parent: _TINSTR,
        name: str,
        channel_letter: str,
        **kwargs: Unpack[InstrumentBaseKWArgs],
    ):
        """
        Base class for MiniCircuits SPDT Switch channels.
        Should not be instantiated directly.

        Args:
            parent: The instrument the channel is a part of
            name: the name of the channel
            channel_letter: channel letter ['a', 'b', 'c' or 'd'])
            **kwargs: Forwarded to base class.

        """

        super().__init__(parent, name, **kwargs)
        self.channel_letter = channel_letter.upper()
        _chanlist = ["a", "b", "c", "d", "e", "f", "g", "h"]
        self.channel_number = _chanlist.index(channel_letter)

        self.switch: Parameter = self.add_parameter(
            "switch",
            label=f"switch {self.channel_letter}",
            set_cmd=self._set_switch,
            get_cmd=self._get_switch,
            vals=Ints(1, 2),
        )
        """Parameter switch"""

    def __call__(self, *args: int) -> int | None:
        if len(args) == 1:
            self.switch(args[0])
            return None
        elif len(args) == 0:
            return self.switch()
        else:
            raise RuntimeError("Call channel with either one or zero arguments")

    def _set_switch(self, switch: int) -> None:
        raise NotImplementedError()

    def _get_switch(self) -> int:
        raise NotImplementedError()


class MiniCircuitsSPDTBase(Instrument):
    """
    Base class for MiniCircuits SPDT Switch instruments.
    Should not be instantiated directly.
    """

    CHANNEL_CLASS: type[MiniCircuitsSPDTSwitchChannelBase]

    def add_channels(self) -> None:
        channels = ChannelList(self, "Channels", self.CHANNEL_CLASS, snapshotable=False)

        _chanlist = ["a", "b", "c", "d", "e", "f", "g", "h"]
        _max_channel_number = self.get_number_of_channels()
        _chanlist = _chanlist[0:_max_channel_number]

        for c in _chanlist:
            channel = self.CHANNEL_CLASS(self, f"channel_{c}", c)
            channels.append(channel)
            self.add_submodule(c, channel)
        self.channels = self.add_submodule("channels", channels.to_channel_tuple())
        """Channel list containing all channels of the switch"""

    def all(self, switch_to: int) -> None:
        for c in self.channels:
            c.switch(switch_to)

    def get_number_of_channels(
        self, max_attempts: int = 3, retry_delay: float = 1.0
    ) -> int:
        """
        Determine the number of channels from the model name returned by
        ``get_idn``.

        The first communication with the device after connecting sometimes
        returns an empty or incomplete model name. To be robust against this,
        ``get_idn`` is queried up to ``max_attempts`` times until a model name
        that the number of channels can be parsed from is returned.

        Args:
            max_attempts: Number of times to query ``get_idn`` while trying to
                obtain a parseable model name.
            retry_delay: Time in seconds to wait between failed attempts.

        Raises:
            RuntimeError: If a parseable model name could not be obtained after
                ``max_attempts`` attempts.

        """
        model = None
        for attempt in range(max_attempts):
            model = self.get_idn()["model"]
            number_of_channels = self._parse_number_of_channels(model)
            if number_of_channels is not None:
                return number_of_channels
            log.warning(
                "The driver could not determine the number of channels of the "
                "model '%s' on attempt %d of %d.",
                model,
                attempt + 1,
                max_attempts,
            )
            if attempt < max_attempts - 1:
                time.sleep(retry_delay)
        raise RuntimeError(
            "The driver could not determine the number of channels of the "
            f"model '{model}' after {max_attempts} attempts, "
            "it might not be supported."
        )

    def _parse_number_of_channels(self, model: str | None) -> int | None:
        """
        Parse the number of channels from a model name.

        Returns ``None`` if the model name is missing or does not contain a
        parseable number of channels.
        """
        if not model:
            return None
        model_parts = model.split("-")
        if len(model_parts) < 2:
            return None
        if model_parts[0] not in ("RC", "USB"):
            log.warning(
                f"The model with the name '{model}' might not be supported by"
                " the driver"
            )
        match = re.match("^[0-9]*", model_parts[1])
        if match is None:
            return None
        channels = match[0]
        if not channels:
            return None
        return int(channels)
