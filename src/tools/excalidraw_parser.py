"""
Excalidraw files store diagrams as JSON -- shapes, text, arrows, all with
styling, coordinates, and internal IDs. Feeding that raw JSON to an LLM
would waste most of the token budget on noise it doesn't need (colors,
pixel positions, version numbers). This extracts just the meaningful part:
what labels exist, and which shapes connect to which.
"""

import json


def parse_excalidraw(raw_json: str) -> str:
    """
    Returns a plain-text description of an Excalidraw diagram's content:
    labeled shapes and the connections (arrows) between them. Best-effort
    -- if a shape or arrow has no text label, it's described generically
    rather than skipped, since an unlabeled box in a system design diagram
    is still evidence worth the agent seeing.
    """
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return "[Could not parse .excalidraw file -- not valid JSON]"

    elements = data.get("elements", [])
    if not elements:
        return "[Excalidraw file has no elements]"

    # Map: element id -> its text label (if any)
    id_to_label: dict[str, str] = {}
    for el in elements:
        if el.get("type") == "text" and el.get("text"):
            container_id = el.get("containerId")
            target_id = container_id if container_id else el.get("id")
            id_to_label[target_id] = el["text"]

    def label_for(element_id: str | None) -> str:
        if element_id is None:
            return "(unlabeled)"
        return id_to_label.get(element_id, "(unlabeled)")

    shapes = []
    connections = []

    for el in elements:
        el_type = el.get("type")
        if el_type in ("rectangle", "ellipse", "diamond"):
            shapes.append(label_for(el.get("id")))
        elif el_type == "arrow":
            start_id = (el.get("startBinding") or {}).get("elementId")
            end_id = (el.get("endBinding") or {}).get("elementId")
            if start_id or end_id:
                connections.append(f"{label_for(start_id)} -> {label_for(end_id)}")

    lines = ["Diagram shapes/components found:"]
    labeled_shapes = [s for s in shapes if s != "(unlabeled)"]
    if labeled_shapes:
        lines.extend(f"- {s}" for s in labeled_shapes)
    else:
        lines.append("(none labeled)")
    lines.append("\nConnections between components:")
    if connections:
        lines.extend(f"- {c}" for c in connections)
    else:
        lines.append("(no labeled connections found)")

    # Standalone text not attached to any shape (e.g. BOTE calculations,
    # notes) -- these submissions store back-of-envelope estimation here too
    standalone_text = [
        el["text"] for el in elements
        if el.get("type") == "text" and not el.get("containerId") and el.get("text")
    ]
    if standalone_text:
        lines.append("\nStandalone notes/text in the diagram (may include estimation math):")
        lines.extend(f"- {t}" for t in standalone_text)

    return "\n".join(lines)
