"""wisfind.main"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import logging
import ssl
import sys
from typing import Callable, Iterator, Literal

if sys.version_info >= (3, 10):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

import aiomqtt
from pydantic import ValidationError
from wisfind.definitions import DEFAULT_BROKER, WIS2_CORE_PASS, WIS2_CORE_USER, WNM, Topic

LOG = logging.getLogger("wisfind")

CLI_USAGE = "usage: wisfind [GLOBAL_OPTS] [CONSTRAINT..CONSTRAINT] [ACTION]" ""

DEFAULT_TOPICS = [Topic.ALL_CORE_DATA.value]

## possible wisfind actions


def emit_json(msg: WNM | dict, end="\n") -> None:
    """Prints the WNM to stdout as JSON."""
    data = msg.model_dump_json(indent=2) if isinstance(msg, WNM) else json.dumps(msg, indent=2)
    print(data, end=end)


DEFAULT_ACTION = functools.partial(emit_json, end="\n")


class MqttConnectionInfo(TypedDict):
    """How to create a MQTT connection to a WIS2 global broker or cache."""

    endpoint: str
    topics: list[str]
    user: str
    password: str
    transport: Literal["tcp", "websockets"]
    reconnect_delay: float
    reconnect_attempts: int


async def iter_mqtt(info: MqttConnectionInfo) -> Iterator[aiomqtt.Message]:
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


async def wis_event_loop(
    connection_info: MqttConnectionInfo,
    constraint_check: Callable[[WNM | dict], bool] | None = None,
    action: Callable[[WNM | dict], None] | None = None,
    validate_wnm=True,
) -> None:
    """Run the async io loop: receives MQTT messages, checks messages for validity,
    and performs an action on the message.

    Args:
        connection_info (MqttConnectionInfo): How to establish a MQTT connection to
        receive messages from.
        constraint_check (Callable[[WNM | dict], bool] | None): A function that will
        be passed all received WIS2 messages and returns a boolean indicating if the
        action should be performed on the message. Default None.
        action (Callable[[WNM | dict], None] | None): A function that will be passsed
        all received AND checked WIS2 messages. Default None.
        validate_wnm (bool): Should received messages be checked to make sure they
        follow the WIS2 Notification Message (WNM) standard. Default True.
    """
    action = DEFAULT_ACTION if action is None else action
    async for msg in iter_mqtt(connection_info):
        try:
            payload = msg.payload.decode("utf-8")
        except ValueError:
            LOG.warning("wis_event_loop got invalid bytes from '%s'.", connection_info["endpoint"])
            continue
        try:
            data = json.loads(payload)
        except ValueError:
            LOG.warning("wis_event_loop got invalid JSON from '%s'.", connection_info["endpoint"])
            continue
        if validate_wnm:
            try:
                data = WNM(**data)
            except ValidationError:
                LOG.warning("wis_event_loop got invalid WNM from '%s'.", connection_info["endpoint"])
                raise

        if constraint_check is not None and not constraint_check(data):
            LOG.info("wis_event_loop message '%s' didn't meet user constraints.", str(data))
            continue

        action(data)


def parse_global_args():
    """Parse the command line arguments."""
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
    conn_group.add_argument("--websocket", action="store_true", help="Use MQTT over WebSocket instead of TCP.")

    # leftover should have a list of constraints and an action
    parsed, leftover = parser.parse_known_args()

    if parsed.quiet and parsed.verbose:
        parser.error("Cannot specify both --quiet AND --verbose!")

    return parsed, leftover


def parse_action_constraints(args: list[str] | None):
    if not args:
        return None, None
    return None, None


def main():
    """Handles the construction/destruction of the event loop."""
    global_args, leftover = parse_global_args()
    action, constraint_check = parse_action_constraints(leftover)

    conn_info = {
        "endpoint": global_args.broker,
        "user": global_args.user,
        "password": global_args.passwd,
        "topics": global_args.topic,
        "transport": "tcp" if not global_args.websocket else "websockets",
        "reconnect_delay": 3.5,
        "reconnect_attempts": -1,
    }
    if not global_args.quiet:
        log_level = logging.INFO if global_args.verbose else logging.WARNING
        logging.basicConfig(level=log_level)

    try:
        asyncio.run(wis_event_loop(conn_info, constraint_check, action, validate_wnm=not global_args.no_wnm_validate))
    except KeyboardInterrupt:
        LOG.info("Got interrupt, goodbye!")


if __name__ == "__main__":
    sys.exit(main())
