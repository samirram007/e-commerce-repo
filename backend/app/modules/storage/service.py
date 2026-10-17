"""Storage location service."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.modules.storage.models import (
    FACILITY_TYPES,
    LOCATION_TYPE_RANKS,
    LOCATION_TYPES,
    STOCKABLE_TYPES,
    StorageLocation,
)


def create_location(
    session: Session, *, company_id: str, actor_user_id: str, code: str, name: str,
    location_type: str, parent_id: str | None = None, address: str | None = None,
) -> StorageLocation:
    if location_type not in LOCATION_TYPE_RANKS:
        raise BusinessRuleError("BAD_LOCATION_TYPE", f"location_type must be one of {list(LOCATION_TYPES)}")
    if session.scalar(select(StorageLocation.id).where(StorageLocation.company_id == company_id, StorageLocation.code == code)):
        raise ConflictError("CODE_TAKEN", f"Location code '{code}' already exists")
    parent = None
    if parent_id is not None:
        parent = session.get(StorageLocation, parent_id)
        if parent is None or parent.company_id != company_id:
            raise NotFoundError("Parent location")
        # a child must sit strictly deeper than its parent (rank ordering).
        if LOCATION_TYPE_RANKS[location_type] <= LOCATION_TYPE_RANKS[parent.location_type]:
            raise BusinessRuleError(
                "LOCATION_ORDER", f"A '{location_type}' cannot be nested under a '{parent.location_type}'"
            )
    location = StorageLocation(
        company_id=company_id,
        parent_id=parent_id,
        code=code,
        name=name,
        location_type=location_type,
        address=address,
        created_by=actor_user_id,
    )
    session.add(location)
    session.flush()
    return location


def get_location(session: Session, company_id: str, location_id: str) -> StorageLocation:
    location = session.get(StorageLocation, location_id)
    if location is None or location.company_id != company_id:
        raise NotFoundError("Storage location")
    return location


def list_locations(session: Session, company_id: str, location_type: str | None = None):
    stmt = select(StorageLocation).where(StorageLocation.company_id == company_id).order_by(StorageLocation.code)
    if location_type:
        stmt = stmt.where(StorageLocation.location_type == location_type)
    return session.execute(stmt).scalars().all()


def bin_ids_under(session: Session, company_id: str, location_id: str) -> set[str]:
    """All stockable location ids receiving stock under a given node (inclusive)."""
    location = get_location(session, company_id, location_id)
    if location.location_type in STOCKABLE_TYPES:
        return {location.id}
    all_locs = session.execute(select(StorageLocation).where(StorageLocation.company_id == company_id)).scalars().all()
    children: dict[str | None, list[StorageLocation]] = {}
    for loc in all_locs:
        children.setdefault(loc.parent_id, []).append(loc)
    collected: set[str] = set()
    stack = [location.id]
    while stack:
        current = stack.pop()
        loc = next((l for l in all_locs if l.id == current), None)
        if loc is None:
            continue
        if loc.location_type in STOCKABLE_TYPES:
            collected.add(loc.id)
        for child in children.get(current, []):
            stack.append(child.id)
    return collected


def facility_root(session: Session, company_id: str, location_id: str) -> StorageLocation:
    """Walk up parents to find the facility root (warehouse/godown/…)."""
    location = get_location(session, company_id, location_id)
    guard_max = 0
    while location.parent_id is not None and guard_max < 10:
        location = get_location(session, company_id, location.parent_id)
        guard_max += 1
    if location.location_type not in FACILITY_TYPES:
        raise BusinessRuleError("ORPHAN_LOCATION", f"Location chain has no facility root: {location.code}")
    return location


# Backwards-compatible alias (facility roots may be a godown, store, …).
warehouse_of_bin = facility_root
