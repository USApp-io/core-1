"""
Provides an EMANE network node class, which has several attached NEMs that
share the same MAC+PHY model.
"""

import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Type

from core.emulator.distributed import DistributedServer
from core.emulator.enumerations import LinkTypes, NodeTypes, RegisterTlvs
from core.nodes.base import CoreNetworkBase
from core.nodes.interface import CoreInterface

if TYPE_CHECKING:
    from core.emulator.session import Session
    from core.location.mobility import WirelessModel

    WirelessModelType = Type[WirelessModel]

try:
    from emane.events import LocationEvent
except ImportError:
    try:
        from emanesh.events import LocationEvent
    except ImportError:
        logging.debug("compatible emane python bindings not installed")


class EmaneNet(CoreNetworkBase):
    """
    EMANE node contains NEM configuration and causes connected nodes
    to have TAP interfaces (instead of VEth). These are managed by the
    Emane controller object that exists in a session.
    """

    apitype = NodeTypes.EMANE
    linktype = LinkTypes.WIRED
    type = "wlan"
    is_emane = True

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        start: bool = True,
        server: DistributedServer = None,
    ) -> None:
        super().__init__(session, _id, name, start, server)
        self.conf = ""
        self.up = False
        self.nemidmap = {}
        self.model = None
        self.mobility = None

    def linkconfig(
        self,
        netif: CoreInterface,
        bw: float = None,
        delay: float = None,
        loss: float = None,
        duplicate: float = None,
        jitter: float = None,
        netif2: CoreInterface = None,
    ) -> None:
        """
        The CommEffect model supports link configuration.
        """
        if not self.model:
            return
        self.model.linkconfig(
            netif=netif,
            bw=bw,
            delay=delay,
            loss=loss,
            duplicate=duplicate,
            jitter=jitter,
            netif2=netif2,
        )

    def config(self, conf: str) -> None:
        self.conf = conf

    def shutdown(self) -> None:
        pass

    def link(self, netif1: CoreInterface, netif2: CoreInterface) -> None:
        pass

    def unlink(self, netif1: CoreInterface, netif2: CoreInterface) -> None:
        pass

    def updatemodel(self, config: Dict[str, str]) -> None:
        if not self.model:
            raise ValueError("no model set to update for node(%s)", self.id)
        logging.info(
            "node(%s) updating model(%s): %s", self.id, self.model.name, config
        )
        self.model.set_configs(config, node_id=self.id)

    def setmodel(self, model: "WirelessModelType", config: Dict[str, str]) -> None:
        """
        set the EmaneModel associated with this node
        """
        logging.info("adding model: %s", model.name)
        if model.config_type == RegisterTlvs.WIRELESS:
            # EmaneModel really uses values from ConfigurableManager
            #  when buildnemxml() is called, not during init()
            self.model = model(session=self.session, _id=self.id)
            self.model.update_config(config)
        elif model.config_type == RegisterTlvs.MOBILITY:
            self.mobility = model(session=self.session, _id=self.id)
            self.mobility.update_config(config)

    def setnemid(self, netif: CoreInterface, nemid: int) -> None:
        """
        Record an interface to numerical ID mapping. The Emane controller
        object manages and assigns these IDs for all NEMs.
        """
        self.nemidmap[netif] = nemid

    def getnemid(self, netif: CoreInterface) -> Optional[int]:
        """
        Given an interface, return its numerical ID.
        """
        if netif not in self.nemidmap:
            return None
        else:
            return self.nemidmap[netif]

    def getnemnetif(self, nemid: int) -> Optional[CoreInterface]:
        """
        Given a numerical NEM ID, return its interface. This returns the
        first interface that matches the given NEM ID.
        """
        for netif in self.nemidmap:
            if self.nemidmap[netif] == nemid:
                return netif
        return None

    def netifs(self, sort: bool = True) -> List[CoreInterface]:
        """
        Retrieve list of linked interfaces sorted by node number.
        """
        return sorted(self._netif.values(), key=lambda ifc: ifc.node.id)

    def installnetifs(self) -> None:
        """
        Install TAP devices into their namespaces. This is done after
        EMANE daemons have been started, because that is their only chance
        to bind to the TAPs.
        """
        if (
            self.session.emane.genlocationevents()
            and self.session.emane.service is None
        ):
            warntxt = "unable to publish EMANE events because the eventservice "
            warntxt += "Python bindings failed to load"
            logging.error(warntxt)

        for netif in self.netifs():
            external = self.session.emane.get_config(
                "external", self.id, self.model.name
            )
            if external == "0":
                netif.setaddrs()

            if not self.session.emane.genlocationevents():
                netif.poshook = None
                continue

            # at this point we register location handlers for generating
            # EMANE location events
            netif.poshook = self.setnemposition
            netif.setposition()

    def deinstallnetifs(self) -> None:
        """
        Uninstall TAP devices. This invokes their shutdown method for
        any required cleanup; the device may be actually removed when
        emanetransportd terminates.
        """
        for netif in self.netifs():
            if "virtual" in netif.transport_type.lower():
                netif.shutdown()
            netif.poshook = None

    def _nem_position(
        self, netif: CoreInterface
    ) -> Optional[Tuple[int, float, float, float]]:
        """
        Creates nem position for emane event for a given interface.

        :param netif: interface to get nem emane position for
        :return: nem position tuple, None otherwise
        """
        nemid = self.getnemid(netif)
        ifname = netif.localname
        if nemid is None:
            logging.info("nemid for %s is unknown", ifname)
            return
        node = netif.node
        x, y, z = node.getposition()
        lat, lon, alt = self.session.location.getgeo(x, y, z)
        if node.position.alt is not None:
            alt = node.position.alt
        # altitude must be an integer or warning is printed
        alt = int(round(alt))
        return nemid, lon, lat, alt

    def setnemposition(self, netif: CoreInterface) -> None:
        """
        Publish a NEM location change event using the EMANE event service.

        :param netif: interface to set nem position for
        """
        if self.session.emane.service is None:
            logging.info("position service not available")
            return

        position = self._nem_position(netif)
        if position:
            nemid, lon, lat, alt = position
            event = LocationEvent()
            event.append(nemid, latitude=lat, longitude=lon, altitude=alt)
            self.session.emane.service.publish(0, event)

    def setnempositions(self, moved_netifs: List[CoreInterface]) -> None:
        """
        Several NEMs have moved, from e.g. a WaypointMobilityModel
        calculation. Generate an EMANE Location Event having several
        entries for each netif that has moved.
        """
        if len(moved_netifs) == 0:
            return

        if self.session.emane.service is None:
            logging.info("position service not available")
            return

        event = LocationEvent()
        for netif in moved_netifs:
            position = self._nem_position(netif)
            if position:
                nemid, lon, lat, alt = position
                event.append(nemid, latitude=lat, longitude=lon, altitude=alt)
        self.session.emane.service.publish(0, event)
