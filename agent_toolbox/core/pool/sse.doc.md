# Pool SSE Mixin

Server-Sent Events for dashboard live updates.

## Purpose
Push real-time pool events to connected dashboard clients.

## Events
- `key_leased` -- key was leased by a proxy
- `key_returned` -- key was returned
- `key_swapped` -- bad key was swapped for a new one
- `stats` -- periodic pool stats update (every 30s)

## Methods
- `register_sse_listener()` -- returns `asyncio.Queue` for event consumption
- `unregister_sse_listener(q)` -- remove listener from event loop

## Usage
```python
queue = register_sse_listener()
while True:
    event = await queue.get()
    # process event
```

## Caveats
- No backpressure handling -- slow consumers may accumulate events
- Events are lost if no listener is registered at emission time
