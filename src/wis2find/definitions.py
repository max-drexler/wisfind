"""wiswatch.wis2

WIS2 definitions.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field, FtpUrl, HttpUrl, model_validator

# Core data accessible by 'everyone'
WIS2_CORE_USER = "everyone"
WIS2_CORE_PASS = "everyone"  # noqa

# Default WIS2 connection info
DEFAULT_BROKER = "globalbroker.meteo.fr"


NOTSET = object()


# Topic definitions
# https://codes.wmo.int/wis/topic-hierarchy
class Topic(Enum):
    ALL_CORE_DATA = "cache/a/wis2/+/data/core/#"


class GeoJSON(BaseModel):
    pass


def parse_wnm_datetime(_obj: Any) -> datetime:
    """Parse date/time information that's compatible with WNM.

    WNM uses the RFC339 timestamp format that, additionally, MUST be in UTC.

    https://www.rfc-editor.org/rfc/rfc3339

    Args:
        _obj (object): The thing to try to parse as a WNM-compatible timestamp.

    Raises:
        TypeError: If ``_obj`` isn't a string.
        ValueError: If ``_obj`` isn't a valid WNM-compatible timestamp.

    Returns:
        datetime: The parsed timestamp.
    """
    if not isinstance(_obj, str):
        raise TypeError("WNM datetimes must be strings")
    try:
        # TODO: Parse string as RFC339 format instead of ISO8601 format.
        dt = datetime.fromisoformat(_obj)
    except Exception as e:
        raise ValueError from e
    if dt.tzinfo is None:
        dt.tzinfo = timezone.utc
    elif dt.tzinfo != timezone.utc:
        raise ValueError(f"Invalid timezone '{dt.tzinfo}' in datetime '{dt.toisoformat()}'")

    return dt


WisDatetime = Annotated[datetime, BeforeValidator(parse_wnm_datetime)]


class WNMIntegrity(BaseModel):
    """Pydantic model to validate a WIS2 Notification Message's (WNM) `properties.integrity` field.

    "For data verification, it is recommended that data integrity information to be included via the integrity property. Providing this information will allow data consumers to ensure that a given data granule has not been corrupted during download."

    The WNM Standard can be found at: https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-DRAFT.html#_wis2_notification_message.
    """

    method: Literal["sha256", "sha384", "sha512", "sha3-256", "sha3-385", "sha3-512"]

    # The value property provides the result of the hashing method in base64 encoding.
    value: str


class WNMContent(BaseModel):
    """Pydantic model to validate a WIS2 Notification Message's (WNM) `properties.content` field.

    "The content property allows for the inclusion of data in the notification message when the length of the data, once encoded, is smaller than 4 096 bytes."

    The WNM Standard can be found at: https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-DRAFT.html#_wis2_notification_message.
    """

    encoding: Literal["utf-8", "base64", "gzip"]

    value: str

    # Req 10.A: For data whose resulting size in the encoded form is greater than 4 096 bytes, notifications SHALL NOT provide the data inline via properties.content.value.
    size: int


class WNMLink(BaseModel):
    """Pydantic model to validate one object in the WIS2 Notification Message's (WNM) `properties.links` list.

    "The links array property consists of one or more objects providing URLs to access data."

    The WNM Standard can be found at: https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-DRAFT.html#_wis2_notification_message.
    """

    # Req 11.B: The links array property SHALL contain at least one link with, at a minimum, the href and rel properties.
    # Req 11.D: The links SHALL be HTTP, HTTPS, FTP or SFTP.
    href: HttpUrl | FtpUrl

    rel: str

    type: str

    length: int | None = Field(default=None)

    security: dict | None = Field(default=None)


class WNMProperties(BaseModel):
    """Pydantic model to validate a WIS2 Notification Message's (WNM) `properties` field.

    The WNM Standard can be found at: https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-DRAFT.html#_wis2_notification_message.
    """

    # Req 7.A: A WNM SHALL provide a properties.pubtime property.
    # Req 7.B: The properties.pubtime property SHALL be in RFC3339 format.
    # Req 7.C: The properties.pubtime property SHALL be in UTC.
    pubtime: WisDatetime

    # Req 8.A: A WNM SHALL provide a properties.data_id property.
    data_id: str

    metadata_id: str | None = Field(default=None)

    producer: str | None = Field(default=None)

    # Req 9.B: The temporal description SHALL be in RFC3339 format.
    # Req 9.C: The temporal description SHALL be in UTC.
    datetime: WisDatetime | None = Field(default=NOTSET)

    # Req 9.B: The temporal description SHALL be in RFC3339 format.
    # Req 9.C: The temporal description SHALL be in UTC.
    start_datetime: WisDatetime | None = Field(default=NOTSET)

    # Req 9.B: The temporal description SHALL be in RFC3339 format.
    # Req 9.C: The temporal description SHALL be in UTC.
    end_datetime: WisDatetime | None = Field(default=NOTSET)

    cache: bool = Field(default=False)

    integrity: WNMIntegrity | None = Field(default=None)

    content: WNMContent | None = Field(default=None)

    @model_validator(mode='after')
    def check_temporal_description(self) -> Self:
        """"""
        # Req 9.A: A WNM SHALL provide a temporal description by either a properties.datetime property or both the properties.start_datetime and properties.end_datetime properties.
        if self.datetime is NOTSET and (self.start_datetime is NOTSET or self.end_datetime is NOTSET):
            raise ValueError("Must specify a temporal description!")


class WNM(BaseModel):
    """Pydantic model to validate WIS2 Notification Messages (WNM).

    The WNM Standard can be found at: https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-DRAFT.html#_wis2_notification_message.
    """

    # Req 2.B: Each WNM SHALL provide `id`, `type`, `geometry` and `properties` properties for GeoJSON compliance.
    # Req 3.A: The id property SHALL be a Universally Unique Identifier (UUID).
    id: UUID

    # Req 2.B: Each WNM SHALL provide `id`, `type`, `geometry` and `properties` properties for GeoJSON compliance.
    # Req 2.C: Each WNM record type property SHALL be set to a fixed value of Feature for GeoJSON compliance.
    type: Literal["Feature"]

    # Req 4.A: A WNM SHALL provide information on conformance via the OAFeat conformsTo property.
    # Ignore N815, we don't have control over variable name.
    # TODO: check the conformance link is valid
    conformsTo: list[str]  | None = Field(default=None) # noqa: N815

    # Req 5.A: A WNM SHALL provide information on version conformance via the version property.
    # Req 5.B: The version property SHALL be fixed to v04 for this version of the specification.
    version: Literal["v04"] | None = Field(default=None)

    # Req 6.A: A WNM record SHALL provide one geometry property to convey the geospatial properties of a notification using a geographic coordinate reference system (World Geodetic System 1984 [WGS 84]) with longitude and latitude decimal degree units.

    # Req 6.B: The geometry property SHALL only provide one of a Point or Polygon geometry, or a null value when a geometry value is unknown or cannot be determined.
    geometry: GeoJSON | None

    # Req 2.B: Each WNM SHALL provide `id`, `type`, `geometry` and `properties` properties for GeoJSON compliance.
    properties: WNMProperties

    # Req 11.A: A WNM SHALL provide a links array property.
    links: list[WNMLink]

    @model_validator(mode='after')
    def check_conforms_to_or_version(self) -> Self:
        """Make sure that `version` OR `conformsTo` exists.

        "conformsTo replaces version. For the deprecation period, only one (but not both) of conformsTo or version are permitted."
        """
        if self.conformsTo is None and self.version is None:
            raise ValueError("Must specify at least one of: 'version', 'conformsTo'!")
