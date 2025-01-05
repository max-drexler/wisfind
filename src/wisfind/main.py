"""wisfind.main"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import ssl
import sys
from typing import TYPE_CHECKING, AsyncIterator, Awaitable, Callable, Literal

import aiomqtt
from pydantic import ValidationError
from typing_extensions import TypedDict

from wisfind.action import emit_json
from wisfind.definitions import DEFAULT_BROKER, WIS2_CORE_PASS, WIS2_CORE_USER, WNM, Topic

LOG = logging.getLogger("wisfind")

CLI_USAGE = "usage: wisfind [OPTIONS] [EXPRESSION ...]"

DEFAULT_TOPICS = [Topic.ALL_CORE_DATA.value]

# Mapping between the CLI argument and action function

ACTION_MAP = {
    "-print": emit_json(),
    "-pprint": emit_json(indent=2),
    "-print0": emit_json(end="\0"),
    "-fprint": None,
    "-fprint0": None,
    "-download": None,
    "-fdownload": None,
}

DEFAULT_ACTION = ACTION_MAP["-print"]


if TYPE_CHECKING:

    class MqttConnectionInfo(TypedDict):
        """How to create a MQTT connection to a WIS2 global broker or cache."""

        endpoint: str
        topics: list[str]
        user: str
        password: str
        transport: Literal["tcp", "websockets"]
        reconnect_delay: float
        reconnect_attempts: int


async def iter_mqtt(info: MqttConnectionInfo) -> AsyncIterator[aiomqtt.Message]:
    """Create a MQTT connection given connection information ``info`` and yield all messages from the connection.

    Args:
        info (MqttConnectionInfo): How to establish the connection.

    Yields:
        aiomqtt.Message: The messages received from the connection.
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
                for topic in info["topics"]:
                    await client.subscribe(topic, qos=1)
                    LOG.info("Subscribed to topic '%s'.", topic)
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


async def wis_event_loop(
    connection_info: MqttConnectionInfo,
    callback: Callable[[WNM | dict], None] | Callable[[WNM | dict], Awaitable[None]],
    validate_wnm=True,
) -> None:
    """Async event loop for wisfind.

    Listens for WIS2 messages on the connection given by ``connection_info``, parses
    them, and passes them to ``callback``.

    Args:
        connection_info (MqttConnectionInfo): How to establish a MQTT connection to
        receive messages from.
        callback
        (Callable[[WNM | dict], bool] | Callable[[WNM | dict], Awaitable[None]]):
        A sync or async function that will passed all parsed WIS2 messages.
        validate_wnm (bool): Should received messages be checked to make sure they
        follow the WIS2 Notification Message (WNM) standard. Default True.
    """
    async for msg in iter_mqtt(connection_info):
        try:
            data = json.loads(msg.payload)
        except ValueError:
            LOG.warning("wis_event_loop got invalid JSON from '%s'.", connection_info["endpoint"])
            continue
        if validate_wnm:
            try:
                data = WNM(**data)
            except ValidationError:
                LOG.warning("wis_event_loop got invalid WNM from '%s'.", connection_info["endpoint"])
                raise

        if asyncio.iscoroutine(callback):
            await callback(data)
        else:
            callback(data)


def parse_options():
    """Parse program options from command-line arguments."""
    parser = argparse.ArgumentParser(prog="wisfind", usage=CLI_USAGE, allow_abbrev=False)

    parser.add_argument("--version", action="store_true", help="Show version information and exit.")
    parser.add_argument("--verbose", action="store_true", help="Print verbose log information to stderr.")
    parser.add_argument("--quiet", action="store_true", help="Disable all log output to stderr.")

    # TODO: rename argument
    parser.add_argument(
        "--no-wnm-validate",
        action="store_true",
        help="Permit WIS2 messages that don't follow the WIS2 Notification Message standard.",
    )
    # TODO: add argument for validating download.

    conn_group = parser.add_argument_group(title="connection options")
    conn_group.add_argument(
        "-B",
        dest="broker",
        default=DEFAULT_BROKER,
        help="WIS2 global broker or cache to connect to. Default is '%(default)s'.",
    )
    conn_group.add_argument(
        "-T", dest="topic", nargs="+", default=DEFAULT_TOPICS, help="One or more WIS2 topics to subscribe to."
    )
    conn_group.add_argument(
        "-U", dest="user", default=WIS2_CORE_USER, help="Username to connect with. Use default for free WIS2 data."
    )
    conn_group.add_argument(
        "-P", dest="passwd", default=WIS2_CORE_PASS, help="Password to connect with. Use default for free WIS2 data."
    )
    conn_group.add_argument(
        "--ws", dest="websocket", action="store_true", help="Use MQTT over WebSocket instead of TCP."
    )

    # leftover will have the expression
    parsed, leftover = parser.parse_known_args()

    if parsed.quiet and parsed.verbose:
        parser.error("Cannot specify both --quiet AND --verbose!")

    return parsed, leftover


def parse_expression(args: list[str] | None):
    """Parse an expression from CLI arguments."""
    if not args:
        return DEFAULT_ACTION

    return None, None


def main():
    """Handles the construction/destruction of the event loop."""
    opts, leftover = parse_options()
    expression = parse_expression(leftover)

    conn_info = {
        "endpoint": opts.broker,
        "user": opts.user,
        "password": opts.passwd,
        "topics": opts.topic,
        "transport": "tcp" if not opts.websocket else "websockets",
        "reconnect_delay": 3.5,
        "reconnect_attempts": -1,
    }
    if not opts.quiet:
        log_level = logging.INFO if opts.verbose else logging.WARNING
        logging.basicConfig(level=log_level)

    try:
        asyncio.run(
            wis_event_loop(connection_info=conn_info, callback=expression, validate_wnm=not opts.no_wnm_validate)
        )
    except KeyboardInterrupt:
        LOG.info("Got interrupt, goodbye!")


if __name__ == "__main__":
    sys.exit(main())
