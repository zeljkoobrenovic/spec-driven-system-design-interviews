#!/usr/bin/env python3
"""Shared helpers for book dataset builder scripts.

Provides the diagram builder and the consistency pass (renderer-exact regex +
implicit/unlabelled-node detection + satisfies/pattern step-ref resolution).
Temporary build-time helper; _-prefixed so build.py never ships it.
"""
import json
import os
import re


def make_diagram(label_map):
    def diagram(node_ids, edges, header="graph TB"):
        lines = [header]
        for nid in node_ids:
            lines.append("  " + label_map[nid])
        lines.extend("  " + e for e in edges)
        return lines
    return diagram


def _src(v):
    return "\n".join(v) if isinstance(v, list) else (v if isinstance(v, str) else "")


def _is_flow(diag):
    f = next((l for l in _src(diag).split("\n") if l.strip()), "")
    return bool(re.match(r"\s*(graph|flowchart)\b", f))


def _extract(diag):
    s = _src(diag)
    ids = set()
    for m in re.finditer(r"(?:^|[\s;])([A-Za-z_][A-Za-z0-9_-]*)\s*(?:\[\(|\(\(|\[\[|\{\{|\[|\(|\{|>)", s):
        ids.add(m.group(1))
    for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_-]*)\s*(?:--+>|--+|==+>|-\.-+>|<-+>|<--+)\s*(?:\|[^|]*\|\s*)?([A-Za-z_][A-Za-z0-9_-]*)", s):
        ids.add(m.group(1)); ids.add(m.group(2))
    for r in ("graph", "flowchart", "subgraph", "end", "classDef", "class", "LR", "RL", "TB", "BT", "TD"):
        ids.discard(r)
    return ids


def _labelled(diag):
    s = _src(diag)
    ids = set()
    for m in re.finditer(r"(?:^|[\s;])([A-Za-z_][A-Za-z0-9_-]*)\s*(?:\[\(|\(\(|\[\[|\{\{|\[|\(|\{|>)", s):
        ids.add(m.group(1))
    return ids


def _seq(diag):
    s = _src(diag)
    ids = set()
    for m in re.finditer(r"^\s*(?:participant|actor)\s+([A-Za-z_][A-Za-z0-9_]*)", s, re.M):
        ids.add(m.group(1))
    for m in re.finditer(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:-?->>?|--?>>?|-[)x]|->>|-->>|->|-->)\s*\+?([A-Za-z_][A-Za-z0-9_]*)", s, re.M):
        ids.add(m.group(1)); ids.add(m.group(2))
    return ids


def finalize(data, here):
    """Run consistency checks; on success write interview.json, else raise."""
    steps = data.get("steps", [])
    step_ids = {s["id"] for s in steps}
    errors = []

    def check_any(name, diag, hl):
        if _is_flow(diag):
            ids = _extract(diag)
            lab = _labelled(diag)
            for h in (hl or []):
                if h not in ids:
                    errors.append(f"{name}: highlight '{h}' not in {sorted(ids)}")
            for nid in ids:
                if nid not in lab:
                    errors.append(f"{name}: implicit/unlabelled node '{nid}'")
        else:
            ids = _seq(diag)
            for h in (hl or []):
                if h not in ids:
                    errors.append(f"{name}: seq highlight '{h}' not in {sorted(ids)}")

    if data.get("requirementsDiagram"):
        check_any("requirementsDiagram", data["requirementsDiagram"], [])
    if data.get("capacityDiagram"):
        check_any("capacityDiagram", data["capacityDiagram"], [])
    for s in steps:
        if s.get("diagram"):
            check_any(f"step {s['id']}", s["diagram"], s.get("highlight"))
        for o in s.get("options", []) or []:
            if o.get("diagram"):
                check_any(f"step {s['id']} opt '{o.get('name')}'", o["diagram"], o.get("highlight"))
        for fl in s.get("flows", []) or []:
            if fl.get("diagram"):
                check_any(f"step {s['id']} flow '{fl.get('name')}'", fl["diagram"], fl.get("highlight"))
        if s.get("parent") and s["parent"] not in step_ids:
            errors.append(f"step {s['id']}: unknown parent '{s['parent']}'")
    fd = data.get("finalDesign")
    if fd and fd.get("diagram"):
        check_any("finalDesign", fd["diagram"], fd.get("highlight"))
    for a in data.get("api", []) or []:
        if a.get("diagram"):
            check_any(f"api {a['path']}", a["diagram"], a.get("highlight", []))
    for grp in ("functional", "nonFunctional"):
        for item in (data.get("satisfies", {}) or {}).get(grp, []) or []:
            for sid in item.get("steps", []):
                if sid not in step_ids:
                    errors.append(f"satisfies.{grp} '{item['requirement']}' -> unknown step '{sid}'")
    for p in data.get("patterns", []) or []:
        for sid in p.get("steps", []):
            if sid not in step_ids:
                errors.append(f"pattern '{p['name']}' -> unknown step '{sid}'")

    if errors:
        print("CONSISTENCY ERRORS:")
        for e in errors:
            print("  -", e)
        raise SystemExit(1)

    out = os.path.join(here, "interview.json")
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"WROTE {out}: {os.path.getsize(out)} bytes, {len(steps)} steps")
    print("steps:", [s["id"] for s in steps])
