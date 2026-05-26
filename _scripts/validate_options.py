#!/usr/bin/env python3
"""Validate option `view` objects in one or more interview.json files.

Mirrors the renderer's resolution rules (interview.js): node refs resolve to the
HLA catalog or are inline objects; link string-ids must exist in the catalog and
have both endpoints present in the view's node set; inline links and highlights
must reference nodes present in the view; group ids must exist in
highLevelArchitecture.types; mermaid ids must match [A-Za-z_][A-Za-z0-9_-]*.

Usage: python3 _scripts/validate_options.py <path-to-interview.json> [more...]
Exit 0 and prints OK if clean; exit 1 and lists problems otherwise.
"""
import json, re, sys

ID_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_-]*$')


def node_ids(view):
    ids = set()
    for ref in view.get('nodes', []):
        if isinstance(ref, str):
            ids.add(ref)
        elif isinstance(ref, dict) and ref.get('id'):
            ids.add(ref['id'])
    return ids


def check_file(path):
    problems = []
    data = json.load(open(path))
    arch = data.get('highLevelArchitecture', {})
    catalog_nodes = {n['id'] for n in arch.get('nodes', [])}
    catalog_links = {l['id']: l for l in arch.get('links', [])}
    catalog_types = {t['id'] for t in arch.get('types', [])}

    def check_view(v, tag, require_highlight=False):
        if not isinstance(v, dict):
            problems.append(f"{tag}: view is not an object"); return
        nids = node_ids(v)
        for ref in v.get('nodes', []):
            if isinstance(ref, dict) and ref.get('id') and not ID_RE.match(ref['id']):
                problems.append(f"{tag}: inline node id '{ref['id']}' fails mermaid id regex")
        for ln in v.get('links', []):
            if isinstance(ln, str):
                if ln not in catalog_links:
                    problems.append(f"{tag}: link id '{ln}' not in catalog -> dropped")
                else:
                    lk = catalog_links[ln]
                    if lk['from'] not in nids or lk['to'] not in nids:
                        problems.append(f"{tag}: catalog link '{ln}' ({lk['from']}->{lk['to']}) endpoints not both in view nodes -> dropped")
            elif isinstance(ln, dict):
                fr, to = ln.get('from'), ln.get('to')
                if fr not in nids or to not in nids:
                    problems.append(f"{tag}: inline link {fr}->{to} endpoints not both in view nodes -> dropped")
        for h in v.get('highlight', []):
            if h not in nids:
                problems.append(f"{tag}: highlight '{h}' not in this view's nodes")
            if not ID_RE.match(str(h)):
                problems.append(f"{tag}: highlight '{h}' fails mermaid id regex")
        for g in v.get('groups', []):
            gid = g if isinstance(g, str) else g.get('id')
            if gid not in catalog_types:
                problems.append(f"{tag}: group '{gid}' not in highLevelArchitecture.types")

    for i, step in enumerate(data.get('steps', [])):
        for j, opt in enumerate(step.get('options', [])):
            tag = f"{step.get('id')} option[{j}] '{opt.get('name') or opt.get('title')}'"
            if opt.get('diagram') is not None:
                problems.append(f"{tag}: must use 'view', not 'diagram'")
            if not (opt.get('name') or opt.get('title')):
                problems.append(f"{tag}: missing name/title")
            # canonical book shape needs pros+cons; tradeoffs shape is also valid
            if not (opt.get('pros') or opt.get('cons') or opt.get('tradeoffs')):
                problems.append(f"{tag}: missing pros/cons (or tradeoffs)")
            if not isinstance(opt.get('view'), dict):
                problems.append(f"{tag}: missing view")
            else:
                check_view(opt['view'], tag)
    return problems


def main():
    paths = sys.argv[1:]
    if not paths:
        print("usage: validate_options.py <interview.json> [...]"); sys.exit(2)
    any_bad = False
    for p in paths:
        try:
            probs = check_file(p)
        except Exception as e:
            print(f"PARSE ERROR {p}: {e}"); any_bad = True; continue
        if probs:
            any_bad = True
            print(f"ISSUES in {p}:")
            for pr in probs:
                print("  -", pr)
        else:
            print(f"OK {p}")
    sys.exit(1 if any_bad else 0)


if __name__ == '__main__':
    main()
