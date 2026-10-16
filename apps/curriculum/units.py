"""Group lesson records into the lessons students see (Lesson 1-3).

Lesson 2 is taught in parts (2.1, 2.2, 2.3) and each part is its own Lesson record, so
student pages group consecutive records that share a unit number.
"""


def group_by_unit(items, *, lesson=lambda item: item):
    """Consecutive `items` (in lesson order) grouped by unit. `lesson(item)` gives the record."""
    units = []
    for item in items:
        record = lesson(item)
        if not units or units[-1]["unit_number"] != record.unit_number:
            units.append({
                "unit_number": record.unit_number,
                "title": record.unit_title,
                "has_parts": bool(record.part_number),
                "items": [],
            })
        units[-1]["items"].append(item)
    return units


def unit_state(states):
    """A unit is done when every part is done, current when any part is current, open when
    any part has been reached, otherwise locked."""
    if states and all(state == "completed" for state in states):
        return "completed"
    if "current" in states:
        return "current"
    if any(state in {"completed", "available"} for state in states):
        return "available"
    return "locked"
