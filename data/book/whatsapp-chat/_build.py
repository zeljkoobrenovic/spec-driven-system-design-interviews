#!/usr/bin/env python3
"""Builder for the WhatsApp / Chat book case."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

NODES = {
    "Client":   ("Mobile / Web Client", "client", "boundary", [], "User's app; holds a persistent connection and a local message store."),
    "LB":       ("Connection Load Balancer", "edge", "traffic", ["stateless"], "Routes new connections to gateway nodes; sticky per connection."),
    "Gateway":  ("WebSocket Gateway", "service", "compute", ["stateful"], "Holds millions of long-lived connections; one user's devices map here while online."),
    "Session":  ("Session / Presence Registry", "cache", "state", ["stateful"], "Maps userId/deviceId -> which gateway holds the live connection; tracks online status."),
    "ChatSvc":  ("Chat Service", "service", "compute", ["stateless"], "Validates, persists, and routes messages; owns delivery semantics."),
    "MsgQ":     ("Per-User Message Queue", "queue", "async", ["stateful"], "Inbox of undelivered messages per recipient (offline buffer)."),
    "MsgDB":    ("Message Store", "database", "state", ["stateful"], "Durable messages, sharded by conversation/user for history sync."),
    "Fanout":   ("Group Fanout Service", "worker", "async", ["stateless"], "Expands a group message to each member's queue/gateway."),
    "GroupDB":  ("Group Membership Store", "database", "state", ["stateful"], "Group -> member list, sharded by group id."),
    "Push":     ("Push Notification Service", "service", "async", ["stateless"], "APNs/FCM bridge to wake offline devices."),
    "Media":    ("Media Service + Blob Store", "object-storage", "state", ["stateful"], "Stores image/video/voice attachments; messages carry a media id."),
}

LINKS = {
    "client-lb":        ("Client", "LB", "connect (WSS)"),
    "lb-gateway":       ("LB", "Gateway", "assign connection"),
    "gateway-session":  ("Gateway", "Session", "register conn"),
    "gateway-chat":     ("Gateway", "ChatSvc", "send message"),
    "chat-msgdb":       ("ChatSvc", "MsgDB", "persist message"),
    "chat-session":     ("ChatSvc", "Session", "recipient online?"),
    "chat-gateway":     ("ChatSvc", "Gateway", "push to online device"),
    "chat-msgq":        ("ChatSvc", "MsgQ", "enqueue (offline)"),
    "msgq-gateway":     ("MsgQ", "Gateway", "drain on reconnect"),
    "chat-fanout":      ("ChatSvc", "Fanout", "group message"),
    "fanout-group":     ("Fanout", "GroupDB", "list members"),
    "fanout-msgq":      ("Fanout", "MsgQ", "enqueue per member"),
    "chat-push":        ("ChatSvc", "Push", "wake offline device"),
    "push-client":      ("Push", "Client", "notification"),
    "client-media":     ("Client", "Media", "upload/download blob"),
    "chat-media":       ("ChatSvc", "Media", "validate media id"),
}


def view(nodes, links, highlight=None, groups=None):
    v = {"nodes": list(nodes), "links": list(links)}
    if highlight: v["highlight"] = list(highlight)
    if groups: v["groups"] = list(groups)
    return v


def hla():
    nodes = [{"id": n, "label": l, "type": t, "category": c, "traits": tr, "description": d}
             for n, (l, t, c, tr, d) in NODES.items()]
    links = [{"id": i, "from": f, "to": to, "label": lb} for i, (f, to, lb) in LINKS.items()]
    types = [
        {"id": "connection-tier", "label": "Connection Tier", "nodes": ["LB", "Gateway", "Session"]},
        {"id": "delivery-core", "label": "Delivery Core", "nodes": ["ChatSvc", "MsgQ", "MsgDB", "Fanout"]},
    ]
    return {"nodes": nodes, "links": links, "types": types}


def seq(parts, msgs, highlight=None):
    out = {"sequence": {"participants": parts, "messages": msgs}}
    if highlight: out["highlight"] = highlight
    return out


data = {
    "title": "WhatsApp / Chat — System Design",
    "description": "Design a real-time messaging system: deliver 1:1 and group messages instantly to online users, buffer them for offline users, and sync history across devices. The themes are persistent connections, delivery state machines, presence, and group fanout.",
    "highLevelArchitecture": hla(),

    "requirementsDiagram": [
        "graph LR",
        "  User[User]",
        "  Send[Send message]",
        "  Deliver[Deliver in real time]",
        "  Offline[Buffer if offline]",
        "  Receipts[Delivery + read receipts]",
        "  User --> Send",
        "  Send --> Deliver",
        "  Send --> Offline",
        "  Deliver --> Receipts",
    ],
    "capacityDiagram": [
        "graph LR",
        "  Conns[100s of M live connections]",
        "  Msgs[~1M messages/s]",
        "  Groups[Group fanout]",
        "  Conns --> Msgs",
        "  Msgs --> Groups",
    ],

    "requirements": {
        "functional": [
            "Send a 1:1 message; deliver in real time if the recipient is online.",
            "Buffer messages for offline recipients and deliver on reconnect.",
            "Group messaging: a message goes to all current group members.",
            "Delivery receipts (sent / delivered / read).",
            "Presence (online / last-seen) and typing indicators.",
            "Sync message history across a user's multiple devices.",
            "Attach media (images, video, voice).",
        ],
        "nonFunctional": [
            "Real-time delivery: online-to-online latency well under a second.",
            "Reliable: an accepted message is never lost, even across crashes.",
            "Ordered: messages within a conversation arrive in send order.",
            "Scale to hundreds of millions of concurrent persistent connections.",
            "Highly available; tolerate gateway and region failures.",
        ],
    },

    "capacity": [
        {"label": "Concurrent connections", "value": "100s of millions", "note": "Each user device holds one persistent socket."},
        {"label": "Messages per second", "value": "~1,000,000", "note": "Peak, across all conversations."},
        {"label": "Connections per gateway", "value": "~1M", "note": "Drives gateway node count and memory."},
        {"label": "Avg message size", "value": "~100 bytes text", "note": "Media goes via blob store, not the message path."},
        {"label": "Offline buffer", "value": "until delivered / TTL", "note": "Per-user queue persists undelivered messages."},
    ],

    "api": [
        {"method": "WS", "path": "/connect",
         "description": "Open a persistent WebSocket. The gateway registers the device in the session registry.",
         "request": "Upgrade: websocket  (auth token)",
         "response": "connection established; server may push queued messages",
         **seq(
             [{"id": "Client"}, {"id": "LB", "label": "Conn LB"}, {"id": "Gateway", "label": "WS Gateway"},
              {"id": "Session", "label": "Session Registry"}, {"id": "MsgQ", "label": "Message Queue"}],
             [
                 {"from": "Client", "to": "LB", "arrow": "->>", "label": "WSS connect"},
                 {"from": "LB", "to": "Gateway", "arrow": "->>", "label": "assign gateway"},
                 {"from": "Gateway", "to": "Session", "arrow": "->>", "label": "register device->gateway"},
                 {"from": "Gateway", "to": "MsgQ", "arrow": "->>", "label": "drain queued messages"},
                 {"from": "Gateway", "to": "Client", "arrow": "-->>", "label": "deliver backlog"},
             ])},
        {"method": "WS", "path": "send-message",
         "description": "Client sends a message frame over its socket. Server persists, routes, and acks.",
         "request": "{ \"to\": \"u_42\", \"clientMsgId\": \"c_9\", \"body\": \"hi\" }",
         "response": "{ \"serverMsgId\": \"m_88\", \"state\": \"sent\" }",
         **seq(
             [{"id": "Client"}, {"id": "Gateway", "label": "WS Gateway"}, {"id": "ChatSvc", "label": "Chat Service"},
              {"id": "MsgDB", "label": "Message Store"}, {"id": "Session", "label": "Session Registry"}],
             [
                 {"from": "Client", "to": "Gateway", "arrow": "->>", "label": "send {clientMsgId}"},
                 {"from": "Gateway", "to": "ChatSvc", "arrow": "->>", "label": "route message"},
                 {"from": "ChatSvc", "to": "MsgDB", "arrow": "->>", "label": "persist (assign serverMsgId)"},
                 {"from": "ChatSvc", "to": "Gateway", "arrow": "-->>", "label": "ack(sent)"},
                 {"from": "ChatSvc", "to": "Session", "arrow": "->>", "label": "recipient online?"},
             ])},
        {"method": "POST", "path": "/v1/groups/{id}/messages",
         "description": "Post to a group; fanned out to all members' queues/gateways.",
         "request": "{ \"body\": \"team lunch?\" }",
         "response": "{ \"serverMsgId\": \"m_91\" }"},
    ],

    "dataModel": [
        {"name": "messages", "note": "Durable message log, sharded by conversation id; ordered by server sequence.",
         "fields": [
             {"name": "server_msg_id", "type": "bigint PK (per-conversation sequence / snowflake)"},
             {"name": "conversation_id", "type": "bigint (shard key)"},
             {"name": "sender_id", "type": "bigint"},
             {"name": "client_msg_id", "type": "uuid (idempotency / dedup)"},
             {"name": "body", "type": "text / encrypted blob"},
             {"name": "media_id", "type": "uuid | null"},
             {"name": "created_at", "type": "timestamp"},
         ]},
        {"name": "delivery_state", "note": "Per-recipient receipt state for a message.",
         "fields": [
             {"name": "server_msg_id", "type": "bigint"},
             {"name": "recipient_id", "type": "bigint"},
             {"name": "state", "type": "enum(sent, delivered, read)"},
             {"name": "updated_at", "type": "timestamp"},
         ]},
        {"name": "sessions", "note": "Live routing table: which gateway holds each device's connection.",
         "fields": [
             {"name": "device_id", "type": "string PK"},
             {"name": "user_id", "type": "bigint"},
             {"name": "gateway_id", "type": "string"},
             {"name": "last_seen", "type": "timestamp"},
         ]},
        {"name": "group_members", "note": "Group membership, sharded by group id.",
         "fields": [
             {"name": "group_id", "type": "bigint (shard key)"},
             {"name": "user_id", "type": "bigint"},
             {"name": "role", "type": "enum(member, admin)"},
         ]},
    ],

    "patterns": [
        {"name": "Persistent connection (WebSocket)", "what": "Keep a long-lived socket per device so the server can push messages instantly.",
         "whenToUse": "Real-time delivery where polling latency/overhead is unacceptable.", "steps": ["connections"]},
        {"name": "Connection routing registry", "what": "A fast lookup of device -> gateway so any service can reach an online user's socket.",
         "whenToUse": "When millions of stateful connections are spread across many gateway nodes.", "steps": ["routing"]},
        {"name": "Offline message queue", "what": "Persist undelivered messages per recipient and drain on reconnect.",
         "whenToUse": "Recipients are frequently offline but must not miss messages.", "steps": ["offline"]},
        {"name": "Idempotent message id", "what": "Client-generated id dedups retries so a flaky network doesn't double-send.",
         "whenToUse": "At-least-once delivery over unreliable mobile networks.", "steps": ["delivery"]},
        {"name": "Fanout-on-write (groups)", "what": "Expand a group message to each member at send time.",
         "whenToUse": "Group sizes are bounded; per-member delivery state is needed.", "steps": ["groups"]},
        {"name": "Per-conversation ordering", "what": "Assign a monotonic sequence per conversation so messages display in order.",
         "whenToUse": "Chat where out-of-order display is confusing.", "steps": ["delivery"]},
    ],

    "steps": [
        {
            "id": "connections",
            "title": "1. Persistent Connections via WebSocket Gateways",
            "description": [
                "Polling can't deliver in real time at this scale. Each device opens a long-lived WebSocket to a gateway node that holds the connection open and can push messages down instantly.",
                "A gateway holds ~1M connections; a connection load balancer spreads new connections across the fleet. The connection is stateful, so it's sticky to one gateway for its lifetime.",
                "Gateways are dumb pipes: they own the socket and (de)serialize frames, but delivery logic lives in the chat service behind them.",
            ],
            "view": view(["Client", "LB", "Gateway", "ChatSvc"],
                         ["client-lb", "lb-gateway", "gateway-chat"],
                         highlight=["Gateway"], groups=["connection-tier"]),
            "decisionPrompt": "Why a persistent WebSocket rather than HTTP long-polling or periodic polling?",
            "concepts": [
                {"term": "WebSocket gateway", "definition": "A node that terminates many long-lived bidirectional sockets and relays frames.",
                 "whyItMatters": "Enables server push with low latency and no polling overhead.",
                 "example": "One gateway holds 1M sockets; the cluster holds hundreds of millions."},
            ],
            "patterns": ["Persistent connection (WebSocket)"],
            "whyNow": ["The connection model is the foundation — everything about routing, presence, and delivery depends on where the live socket lives."],
            "recap": {"before": "Nothing.", "after": "Devices hold live sockets to gateways; server can push.",
                      "newRisk": "Connections are spread across many gateways — how does a sender's message find the recipient's gateway?"},
            "traps": [
                {"trap": "Putting delivery logic in the gateway.", "why": "Stateful gateways become hard to scale and deploy; a restart drops connections AND logic.",
                 "instead": "Keep gateways thin; route to a stateless chat service for delivery."},
            ],
        },
        {
            "id": "routing",
            "title": "2. Route a Message to the Recipient's Connection",
            "description": [
                "When a message arrives, the chat service looks up the recipient in the session registry: which gateway (if any) currently holds their device's socket.",
                "If online, the chat service tells that gateway to push the frame down the recipient's socket. The registry is the live device -> gateway map, updated on connect/disconnect.",
                "Keep the registry in a fast store (e.g. Redis) keyed by device id; it's rebuildable from gateways re-registering, so it isn't the durable source of truth for messages.",
            ],
            "view": view(["Client", "Gateway", "ChatSvc", "Session", "MsgDB"],
                         ["gateway-chat", "chat-msgdb", "chat-session", "chat-gateway"],
                         highlight=["Session", "ChatSvc"], groups=["connection-tier", "delivery-core"]),
            "decisionPrompt": "A user has three devices on three different gateways. How does a message reach all of them?",
            "patterns": ["Connection routing registry"],
            "whyNow": ["Routing across a sharded connection fleet is the core real-time problem; the session registry is how it's solved."],
            "concepts": [
                {"term": "Session registry", "definition": "A live mapping of device/user -> the gateway holding its connection.",
                 "whyItMatters": "Lets any backend node locate and push to an online device.",
                 "example": "Lookup u_42's devices -> [gw7, gw19] -> push to both."},
            ],
            "recap": {"before": "Sockets exist but are unreachable from the backend.", "after": "Any message can find an online recipient's gateway.",
                      "newRisk": "Recipient may be offline — the message still must not be lost."},
        },
        {
            "id": "delivery",
            "title": "3. Reliable, Ordered, Idempotent Delivery",
            "description": [
                "Persist the message durably before acking the sender — that's what makes 'never lost' true across crashes. The store assigns a per-conversation sequence number for ordering.",
                "The client attaches a clientMsgId; the server dedups on it so a retry over a flaky network doesn't create a duplicate (at-least-once + idempotency = effectively-once).",
                "Track delivery state per recipient (sent -> delivered -> read); receipts flow back as small control messages and update the state.",
            ],
            "view": view(["Client", "Gateway", "ChatSvc", "MsgDB"],
                         ["gateway-chat", "chat-msgdb", "chat-gateway"],
                         highlight=["ChatSvc", "MsgDB"], groups=["delivery-core"]),
            "decisionPrompt": "The client sends, the network drops the ack, the client retries. How do you avoid a duplicate message?",
            "concepts": [
                {"term": "Idempotent send (clientMsgId)", "definition": "A client-generated id the server uses to dedup retried sends.",
                 "whyItMatters": "Mobile networks make retries common; without dedup, users see double messages.",
                 "example": "Second send with the same clientMsgId returns the original serverMsgId."},
                {"term": "Per-conversation sequence", "definition": "A monotonic counter per conversation defining message order.",
                 "whyItMatters": "Guarantees consistent ordering across devices regardless of arrival timing.",
                 "example": "Devices sort by sequence, not by local receive time."},
            ],
            "patterns": ["Idempotent message id", "Per-conversation ordering"],
            "whyNow": ["Reliability, ordering, and dedup are the correctness heart of chat; getting them explicit is the senior signal."],
            "recap": {"before": "Messages routed best-effort.", "after": "Durable, ordered, dedup'd messages with receipt state.",
                      "newRisk": "Recipient offline -> need a buffer; presence/receipts add traffic."},
            "failureDrills": [
                {"scenario": "Chat service crashes after persisting but before acking.",
                 "expectedBehavior": "Client retries with the same clientMsgId; server recognizes it and re-acks without duplicating.",
                 "mitigation": "Persist-before-ack + idempotent dedup on clientMsgId."},
            ],
        },
        {
            "id": "offline",
            "title": "4. Offline Delivery and History Sync",
            "description": [
                "If the recipient is offline (no session in the registry), enqueue the message in their per-user message queue. On reconnect, the gateway drains the queue down the new socket before live traffic.",
                "Wake the device with a push notification (APNs/FCM) so it reconnects and pulls. Push is a hint, not the delivery channel — the durable queue is.",
                "History sync across devices reads from the durable message store by conversation sequence, so a new or returning device catches up to the same ordered view.",
            ],
            "view": view(["Client", "Gateway", "ChatSvc", "Session", "MsgQ", "Push"],
                         ["chat-session", "chat-msgq", "msgq-gateway", "chat-push", "push-client", "gateway-chat"],
                         highlight=["MsgQ", "Push"], groups=["delivery-core"]),
            "decisionPrompt": "Recipient is offline for two days, then reconnects on a new phone. What should they see?",
            "patterns": ["Offline message queue"],
            "whyNow": ["Offline is the common case on mobile; the durable per-user queue + push is the standard answer and ties back to 'never lost'."],
            "flows": [
                seq(
                    [{"id": "ChatSvc", "label": "Chat Service"}, {"id": "Session", "label": "Session Registry"},
                     {"id": "MsgQ", "label": "Message Queue"}, {"id": "Push", "label": "Push Service"},
                     {"id": "Gateway", "label": "WS Gateway"}],
                    [
                        {"from": "ChatSvc", "to": "Session", "arrow": "->>", "label": "recipient online?"},
                        {"type": "alt", "label": "offline",
                         "messages": [
                             {"from": "ChatSvc", "to": "MsgQ", "arrow": "->>", "label": "enqueue message"},
                             {"from": "ChatSvc", "to": "Push", "arrow": "->>", "label": "wake device"},
                         ],
                         "else": {"label": "online",
                                  "messages": [{"from": "ChatSvc", "to": "Gateway", "arrow": "->>", "label": "push now"}]}},
                        {"from": "MsgQ", "to": "Gateway", "arrow": "-->>", "label": "drain on reconnect"},
                    ],
                    highlight=["MsgQ", "Push"]),
            ],
            "recap": {"before": "Online-only delivery.", "after": "Offline users buffered + woken; history syncs across devices.",
                      "newRisk": "Group messages multiply this work per member — need fanout."},
        },
        {
            "id": "groups",
            "title": "5. Group Messaging and Fanout",
            "description": [
                "A group message must reach every current member. The fanout service reads the group membership, then for each member does the same online/offline decision: push to their gateway or enqueue.",
                "Per-recipient delivery state means receipts work in groups too (delivered/read counts). Bound group size so fanout stays cheap; very large 'broadcast' groups may switch to a pull model.",
                "Store one canonical message; fan out references plus per-member delivery rows — don't duplicate the body per member.",
            ],
            "view": view(["ChatSvc", "Fanout", "GroupDB", "MsgQ", "Gateway"],
                         ["chat-fanout", "fanout-group", "fanout-msgq", "msgq-gateway"],
                         highlight=["Fanout", "GroupDB"], groups=["delivery-core"]),
            "decisionPrompt": "A 256-member group gets a message; 100 members are offline. What work happens?",
            "patterns": ["Fanout-on-write (groups)"],
            "whyNow": ["Group fanout reuses the 1:1 delivery primitives and is the natural scaling step; bounding group size is the tradeoff to name."],
            "recap": {"before": "1:1 only.", "after": "Group messages fan out to each member with per-member receipts.",
                      "newRisk": "Large groups and presence updates create fanout amplification; gateways are a scaling pressure point."},
            "bottlenecks": [
                {"issue": "Huge group floods the fanout service.", "mitigation": "Cap group size; for broadcast-scale, switch to pull/feed model."},
                {"issue": "Presence/typing updates amplify across large groups.", "mitigation": "Throttle and batch presence; don't fan out typing to huge groups."},
            ],
        },
        {
            "id": "scale-presence",
            "title": "6. Presence, Media, and Gateway Resilience",
            "description": [
                "Presence (online / last-seen) derives from session registry entries and heartbeats; broadcast presence changes only to a user's contacts, not everyone, and rate-limit typing indicators.",
                "Media never travels the message path: the client uploads to the media/blob service and the message carries a media id; recipients download from the blob store/CDN.",
                "When a gateway dies, its connections drop and clients reconnect (to a new gateway, re-registering in the session registry) and drain any queued messages — so a gateway loss is a brief reconnect, not data loss.",
            ],
            "view": view(["Client", "Gateway", "Session", "Media", "ChatSvc"],
                         ["gateway-session", "client-media", "chat-media", "gateway-chat"],
                         highlight=["Session", "Media"], groups=["connection-tier"]),
            "decisionPrompt": "A whole gateway node crashes with 1M connections. What is the user-visible impact?",
            "whyNow": ["Closing on presence/media/resilience maps the remaining requirements and shows the design degrades gracefully under failure."],
            "concepts": [
                {"term": "Heartbeat presence", "definition": "Liveness inferred from periodic pings on the live socket plus a TTL in the registry.",
                 "whyItMatters": "Accurate online/last-seen without a separate presence write path.",
                 "example": "Missed heartbeats past TTL -> mark offline -> notify contacts."},
            ],
            "recap": {"before": "Core delivery only.", "after": "Presence, media, and graceful gateway failover handled.",
                      "newRisk": "Reconnect storms after a gateway loss; presence fanout cost — both bounded by batching and backoff."},
            "failureDrills": [
                {"scenario": "A gateway with 1M connections crashes.",
                 "expectedBehavior": "Those clients detect the drop and reconnect (with backoff) to other gateways, re-register, and drain queues.",
                 "mitigation": "Stateless durable backend + rebuildable session registry + client reconnect with jittered backoff."},
            ],
        },
    ],

    "finalDesign": {
        "title": "Final Design — Real-Time Chat",
        "description": "Devices hold WebSocket connections to thin gateways; a session registry maps device -> gateway. The chat service persists each message (per-conversation sequence, dedup by clientMsgId) before acking, then routes: push to the recipient's gateway if online, else enqueue in their durable per-user queue and send a wake push. Groups fan out per member; receipts and presence flow as control messages; media goes via a separate blob/CDN path. Gateways are replaceable — clients reconnect and drain queues on failure.",
        "view": view(
            ["Client", "LB", "Gateway", "Session", "ChatSvc", "MsgDB", "MsgQ", "Fanout", "GroupDB", "Push", "Media"],
            ["client-lb", "lb-gateway", "gateway-session", "gateway-chat", "chat-msgdb", "chat-session",
             "chat-gateway", "chat-msgq", "msgq-gateway", "chat-fanout", "fanout-group", "fanout-msgq",
             "chat-push", "push-client", "client-media", "chat-media"],
            groups=["connection-tier", "delivery-core"]),
    },

    "satisfies": {
        "functional": [
            {"requirement": "Real-time 1:1 delivery", "how": "Persistent socket + session-registry routing + gateway push.", "steps": ["connections", "routing"]},
            {"requirement": "Offline buffering", "how": "Per-user durable queue drained on reconnect; push to wake.", "steps": ["offline"]},
            {"requirement": "Group messaging", "how": "Fanout service expands to members and reuses delivery primitives.", "steps": ["groups"]},
            {"requirement": "Receipts + presence", "how": "Per-recipient delivery state; presence from heartbeats.", "steps": ["delivery", "scale-presence"]},
            {"requirement": "History sync across devices", "how": "Durable message store read by conversation sequence.", "steps": ["delivery", "offline"]},
        ],
        "nonFunctional": [
            {"requirement": "Sub-second delivery", "how": "Direct push over live sockets, no polling.", "steps": ["connections", "routing"]},
            {"requirement": "Never lose a message", "how": "Persist before ack; durable offline queue.", "steps": ["delivery", "offline"]},
            {"requirement": "Ordered within a conversation", "how": "Per-conversation monotonic sequence.", "steps": ["delivery"]},
            {"requirement": "Hundreds of millions of connections", "how": "Sharded gateway fleet + rebuildable session registry.", "steps": ["connections", "scale-presence"]},
            {"requirement": "Tolerate gateway failure", "how": "Thin stateless gateways; clients reconnect and drain.", "steps": ["scale-presence"]},
        ],
    },

    "interviewScript": [
        {"phase": "Scope & requirements", "time": "first 5 min",
         "say": ["Confirm real-time 1:1 + group, offline delivery, receipts, and history sync.",
                 "Pin sub-second delivery and 'never lost' as the hard guarantees.",
                 "Establish the scale: hundreds of millions of live connections."]},
        {"phase": "High-level design", "time": "next 10 min",
         "say": ["WebSocket gateways for persistent connections.",
                 "Session registry to route to a recipient's gateway.",
                 "Chat service persists-before-ack and routes."]},
        {"phase": "Deep dive", "time": "next 15 min",
         "say": ["Delivery: ordering by sequence, dedup by clientMsgId, receipts.",
                 "Offline queue + push wake; history sync.",
                 "Group fanout; presence and media paths."]},
        {"phase": "Wrap-up", "time": "final 5 min",
         "say": ["Map requirements to mechanisms.",
                 "Tradeoffs: at-least-once+dedup vs exactly-once, group-size limits, presence cost.",
                 "Mention E2E encryption and multi-region as extensions."]},
    ],

    "levelVariants": [
        {"level": "Junior", "expectations": ["Uses WebSockets and a session lookup.", "Persists messages.", "May miss dedup/ordering and offline handling."]},
        {"level": "Senior", "expectations": ["Designs persist-before-ack, idempotent send, and per-conversation ordering.", "Handles offline queue + push.", "Designs group fanout."]},
        {"level": "Staff", "expectations": ["Reasons about gateway sharding, reconnect storms, and registry rebuildability.", "Discusses presence fanout cost, multi-region routing, and E2E encryption tradeoffs."]},
    ],

    "followUps": [
        "How would you add end-to-end encryption without breaking server-side fanout/receipts?",
        "How do you handle a reconnect storm when a whole region's gateways fail over?",
        "How would you support very large broadcast groups (10K+ members)?",
        "How do you keep presence accurate without flooding contacts with updates?",
        "How would you order messages across multiple senders in a group fairly?",
    ],
}

if __name__ == "__main__":
    out = os.path.join(HERE, "interview.json")
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"WROTE {out}: {os.path.getsize(out)} bytes, {len(data['steps'])} steps")
