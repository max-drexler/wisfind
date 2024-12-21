"""wiswatch.main

Main entrypoint for wiswatch.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import sys
from typing import Iterator, Literal

if sys.version_info >= (3, 10):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

import aiomqtt

from wiswatch.definitions import DEFAULT_BROKER, WIS2_CORE_PASS, WIS2_CORE_USER

LOG = logging.getLogger("wiswatch")


class MqttConnectionInfo(TypedDict):
    """How to create a MQTT connection to a WIS2 global broker or cache."""

    endpoint: str
    topics: list[str]
    user: str
    password: str
    transport: Literal["tcp", "websockets"]
    reconnect_delay: float
    reconnect_attempts: int


async def mqtt_connection(info: MqttConnectionInfo) -> Iterator[aiomqtt.Message]:
    """Create a MQTT connection given connection information ``info``.

    Args:
        info (MqttConnectionInfo): How to establish the connection.

    Yields:
        aiomqtt.Message: All messages received from the connection.
    """
    LOG.info("Starting MQTT connection to '%s'.", info["endpoint"])

    # https://wmo-im.github.io/wis2-guide/guide/wis2-guide-DRAFT.html#_2_5_1_publish_subscribe_protocol_mqtt
    port = 8883 if info["transport"] == "tcp" else 443
    client = aiomqtt.Client(
        hostname=info["endpoint"],
        protocol=aiomqtt.ProtocolVersion.V5,  # WMO prefers MQTT 5.0
        port=port,
        username=info["user"],
        password=info["password"],
        transport=info["transport"],
        tls_context=ssl.create_default_context(),
    )
    attempts = info["reconnect_attempts"]
    while True:
        try:
            async with client:
                LOG.info("Connected to '%s'.", info["endpoint"])
                await client.subscribe("cache/a/wis2/#", qos=1)
                async for message in client.messages:
                    yield message
        except aiomqtt.MqttError as e:
            if not attempts:
                raise ConnectionError(
                    "Lost connection to %s after %d failed attempts!", info["reconnect_attempts"], info["endpoint"]
                ) from e
            attempts -= 1
            LOG.warning("Lost connection to %s; Reconnecting in %s seconds.", info["endpoint"], info["reconnect_delay"])
            await asyncio.sleep(info["reconnect_delay"])


async def async_main():
    info = {
        "endpoint": DEFAULT_BROKER,
        "user": WIS2_CORE_USER,
        "password": WIS2_CORE_PASS,
        "topics": ["cache/a/wis2/#"],
        "transport": "tcp",
        "reconnect_delay": 3.5,
        "reconnect_attempts": -1,
    }
    async for msg in mqtt_connection(info):
        print(msg.payload)


def main():
    logging.basicConfig(level=logging.DEBUG)
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        LOG.info("Got interrupt, goodbye!")


if __name__ == "__main__":
    sys.exit(main())
