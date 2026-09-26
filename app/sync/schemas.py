"""Pydantic v2 schemas for WatermelonDB offline-first synchronization protocol."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TableChanges(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    created: list[dict[str, Any]] = Field(default_factory=list)
    updated: list[dict[str, Any]] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)


class SyncPullResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    changes: dict[str, TableChanges]
    newLastPulledAt: int  # Millisecond epoch
    migrationVersion: int = 1
    schemaVersion: int = 1
    hasMore: bool = False
    cursor: str | None = None


class SyncPushPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    changes: dict[str, TableChanges] = Field(default_factory=dict)
    lastPulledAt: int | None = Field(default=None, alias="lastPulledAt")
    migrationVersion: int | None = Field(default=1, alias="migrationVersion")
    schemaVersion: int | None = Field(default=1, alias="schemaVersion")


class ConflictItem(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    table: str
    id: str
    type: str  # created_existing_uuid, concurrent_update, delete_rejected, read_only_table
    resolution: str  # merged_as_update, server_won, client_won, rejected_active_lien_or_listing, server_authoritative
    server_version: dict[str, Any] | None = None
    client_version: dict[str, Any] | None = None
    message: str


class SyncPushResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    accepted: dict[str, dict[str, int]]
    conflicts: list[ConflictItem] = Field(default_factory=list)


class ColumnSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False


class TableSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: str  # "read_write" | "read_only"
    primary_key: str = "id"
    columns: list[ColumnSchema]


class SyncSchemaResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    migration_version: int = 1
    tables: dict[str, TableSchema]
