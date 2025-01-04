"""wisfind.definitions

WIS2 definitions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, FtpUrl, HttpUrl, model_serializer, model_validator
from typing_extensions import Annotated, Literal, Self

# Core data accessible by 'everyone'
WIS2_CORE_USER = "everyone"
WIS2_CORE_PASS = "everyone"  # noqa

# Default WIS2 connection info
DEFAULT_BROKER = "globalbroker.meteo.fr"

NOTSET = object()


class Topic(Enum):
    """A collection of pre-defined WIS2 topics that follow the topic hierarchy.

    Related Docs:
        Topic hierarchy: https://codes.wmo.int/wis/topic-hierarchy
    """

    # Topic that subscribes to all core (free) data.
    ALL_CORE_DATA = "cache/a/wis2/+/data/core/#"


def parse_wnm_datetime(_obj: str) -> datetime:
    """Parse date/time information from a WNM-compatible timestamp.

    WNM uses the RFC339 timestamp format that, additionally, MUST be in UTC.

    Args:
        _obj (str): The thing to try to parse as a WNM-compatible timestamp.

    Raises:
        ValueError: If ``_obj`` isn't a valid WNM-compatible timestamp.

    Returns:
        datetime: The parsed timestamp.

    Related Docs:
        RFC339: https://www.rfc-editor.org/rfc/rfc3339
    """
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


## Pydantic types

WNMDatetime = Annotated[datetime, BeforeValidator(parse_wnm_datetime)]

WNMIntegrityMethod = Literal["sha256", "sha384", "sha512", "sha3-256", "sha3-384", "sha3-512"]

WNMContentEncoding = Literal["utf-8", "base64", "gzip"]

wnm_content_max_bytes = 4096

wnm_link_required_rel = ["canonical", "update", "deletion"]


class WNMModel(BaseModel):
    """All WNM pydantic models inherit from this class.

    Used to set "global" configuration options."""

    model_config = ConfigDict(strict=True)

    @model_serializer()
    def serialize(self):
        """Serialize the model, removing all keys where the value is NOTSET."""
        return {field: getattr(self, field) for field in self.model_fields_set}


class GeoJSON(WNMModel):
    pass


class WNMIntegrity(WNMModel):
    """Information about the integrity of the data that the WNM message describes
    to "ensure that a given data granule has not been corrupted during download".

    Related Docs:
        WNM Standard: https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-DRAFT.html#_1_14_properties_integrity
    """

    method: WNMIntegrityMethod = Field(description="A specific set of methods for calculating the checksum algorithms.")

    # The value property provides the result of the hashing method in base64 encoding.
    value: str = Field(
        description="The result of the hashing method in base64 encoding on the data granule the message describes."
    )


class WNMContent(WNMModel):
    """Embedded product within the message. Can only be inlined if the size of the
    data is smaller than 4,096 bytes.

    Related Docs:
        WNM Standard: https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-DRAFT.html#_1_15_properties_content
        gzip algorithm: https://datatracker.ietf.org/doc/html/rfc1952
    """

    encoding: WNMContentEncoding = Field(description="The character encoding of the data.")

    value: str = Field(
        description="The inline content of the file base64 encoded.", maximum_length=wnm_content_max_bytes
    )

    # Req 10.A:
    # For data whose resulting size in the encoded form is greater than 4 096 bytes,
    # notifications SHALL NOT provide the data inline via properties.content.value.
    size: int = Field(description="Number of bytes contained in the file.", le=wnm_content_max_bytes)


class WNMLink(WNMModel):
    """Provides URLs to access data.

    Related Docs:
        WNM Standard: https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-DRAFT.html#_1_16_links
        IANA link relation: https://www.iana.org/assignments/link-relations/link-relations.xhtml
        WIS link type: http://codes.wmo.int/wis/link-type
    """

    # Req 11.B:
    # The links array property SHALL contain at least one link with, at a minimum,
    # the href and rel properties.

    # Req 11.D:
    # The links SHALL be HTTP, HTTPS, FTP or SFTP.
    href: HttpUrl | FtpUrl = Field(description="The URI of the link target. Schema must be HTTP, HTTPS, FTP, or SFTP.")

    rel: str = Field(description="Relationship between the link and the message.")

    type: str | None = Field(default=None, description="The media type of the data.")

    length: int | None = Field(default=None, description="The length in bytes of the data.")

    security: dict | None = Field(default=None, description="Access control mechanism applied.")


class WNMProperties(WNMModel):
    """GeoJSON properties field.

    Related Docs:
        WNM Standard: https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-DRAFT.html#_1_16_links
        GeoJSON Standard: https://datatracker.ietf.org/doc/html/rfc7946
        Time format: https://datatracker.ietf.org/doc/html/rfc3339
    """

    # Req 7.A:
    # A WNM SHALL provide a properties.pubtime property.

    # Req 7.B:
    # The properties.pubtime property SHALL be in RFC3339 format.

    # Req 7.C:
    # The properties.pubtime property SHALL be in UTC.
    pubtime: WNMDatetime = Field(description="The date and time when the notification was published.")

    # Req 8.A:
    # A WNM SHALL provide a properties.data_id property.
    data_id: str = Field(description="Unique identifier of the data as defined by the producer.")

    metadata_id: str | None = Field(default=None, description="Identifier for associated discovery metadata record.")

    producer: str | None = Field(
        default=None, description="The provider that initially captured and processed the source data."
    )

    # Req 9.B:
    # The temporal description SHALL be in RFC3339 format.

    # Req 9.C:
    # The temporal description SHALL be in UTC.

    # It's possible to use None to indicate that there is no temporal description.
    # Alternatively, it's possible for the field to not exist if the `start_datetime`
    # and end_datetime` fields exist. As such, NOTSET is used to distinguish between
    # when `datetime` is intentionally set to None and when it doesn't exist.
    datetime: WNMDatetime | None = Field(default=NOTSET, description="The reference date and time of the source data.")

    start_datetime: WNMDatetime | None = Field(
        default=NOTSET, description="The start date and time of the source data."
    )

    end_datetime: WNMDatetime | None = Field(default=NOTSET, description="The end date and time of the source data.")

    cache: bool = Field(default=False, descripiton="Whether the data in the notification should be cached.")

    integrity: WNMIntegrity | None = Field(
        default=None, description="Checksum to be applied to the data to ensure that the download is accurate."
    )

    content: WNMContent | None = Field(default=None, description="A small product embedded inline within the message.")

    @model_validator(mode="after")
    def check_temporal_description(self) -> Self:
        """Checks for the existence of `datetime` OR both `start_datetime` and
        `end_datetime`.
        """
        # Req 9.A:
        # A WNM SHALL provide a temporal description by either a properties.datetime
        # property or both the properties.start_datetime and properties.end_datetime properties.
        if self.datetime is NOTSET:
            if self.start_datetime is NOTSET and self.end_datetime is NOTSET:
                raise ValueError("Must specify a temporal description!")
            elif self.start_datetime is NOTSET or self.end_datetime is NOTSET:
                raise ValueError("Must specify both start_datetime AND end_datetime")
        else:
            if not (self.start_datetime is NOTSET and self.end_datetime is NOTSET):
                raise ValueError("Must choose a temporal description!")
        return self


class WNM(WNMModel):
    """A standard-conformant WIS2 Notification Messages (WNM).

    Related Docs:
        WNM Standard: https://wmo-im.github.io/wis2-notification-message/standard/wis2-notification-message-DRAFT.html#_1_16_links
        GeoJSON Standard: https://datatracker.ietf.org/doc/html/rfc7946
        Time format: https://datatracker.ietf.org/doc/html/rfc3339
    """

    # Req 2.B:
    # Each WNM SHALL provide `id`, `type`, `geometry` and `properties` properties
    # for GeoJSON compliance.

    # Req 3.A:
    # The id property SHALL be a Universally Unique Identifier (UUID).
    id: str = Field(description="A universally unique identifier of the message.")

    # Req 2.C:
    # Each WNM record type property SHALL be set to a fixed value of Feature for
    # GeoJSON compliance.
    type: Literal["Feature"] = Field(description="A fixed value denoting the record as a GeoJSON Feature")

    # Req 4.A:
    # A WNM SHALL provide information on conformance via the OAFeat conformsTo
    # property.

    # TODO: check the conformance link is valid
    conformsTo: list[str] = Field(
        default=NOTSET, description="The version of WNM associated that the record conforms to."
    )  # noqa: N815

    # Req 5.A:
    # A WNM SHALL provide information on version conformance via the version
    # property.

    # Req 5.B:
    # The version property SHALL be fixed to v04 for this version of the
    # specification.
    version: Literal["v04"] = Field(default=NOTSET, description="Deprecated way to specify the version of the WNM.")

    # Req 6.A:
    # A WNM record SHALL provide one geometry property to convey the geospatial
    # properties of a notification using a geographic coordinate reference system
    # (World Geodetic System 1984 [WGS 84]) with longitude and latitude decimal
    # degree units.

    # Req 6.B:
    # The geometry property SHALL only provide one of a Point or Polygon geometry,
    # or a null value when a geometry value is unknown or cannot be determined.
    geometry: GeoJSON | None = Field(description="Geospatial location associated with the [meta]data.")

    properties: WNMProperties = Field(description="GeoJSON properties of the associated message.")

    # Req 11.A:
    # A WNM SHALL provide a links array property.
    links: list[WNMLink] = Field(min_length=1, description="Online linkages for data retrieval.")

    @model_validator(mode="after")
    def check_conforms_to_or_version(self) -> Self:
        """Make sure that `version` OR `conformsTo` exists.

        From standard: "conformsTo replaces version. For the deprecation period,
        only one (but not both) of conformsTo or version are permitted."
        """
        if self.conformsTo is NOTSET and self.version is NOTSET:
            raise ValueError("Must specify at least one of: 'version', 'conformsTo'!")
        if self.conformsTo is not NOTSET and self.version is not NOTSET:
            raise ValueError("Cannot specify both: 'version' and 'conformsTo'!")
        return self

    @model_validator(mode="after")
    def check_links_rel(self) -> Self:
        """Check that links array property contains one link object with a
        rel property with one of the values canonical, update, deletion.
        """
        if not any(link.rel in wnm_link_required_rel for link in self.links):
            raise ValueError(
                "At least one member of links must have rel of type {}!".format(", or".join(wnm_link_required_rel))
            )
        return self
