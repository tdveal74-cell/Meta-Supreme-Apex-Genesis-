"""DEVON presence streaming middleware.

What this is
------------
A separate FastAPI service that turns one DEVON reply into a presence
stream for a web client: the tokens as they arrive, ARKit face blendshape
frames on an audio timeline, and (when LiveKit is not configured) the
audio itself as PCM chunks over the same WebSocket. It sits beside the
DEVON API and trusts the same access JWTs, so a signed in web session can
open it with the token it already holds.

Protocol v2 added the other direction. Until it this service had a mouth,
a face and a brain and no ear at all: the client sent text it already had,
the socket only ever read text, and the ``listening`` state was a label on
a text box. A v2 client can push one recorded clip up, ``hearing.py``
transcribes it, and the text enters the same turn a typed message enters.
The version is negotiated at hello and the server answers with the one the
CLIENT asked for, so this service and the web app can deploy in either
order. NOTHING SENDS AUDIO YET: the capture side of the page is not built,
so v2 is a door that works and has nobody walking through it.

It carries two mechanisms the plain chat lane does not need:

1. a sliding window buffer (``buffer.py``) that keeps the face in step
   with the audio clock and sheds expression frames before lip sync
   frames when the client renderer reports it is behind; and
2. a circuit breaker and router (``breaker.py``) that measures time to
   first token per turn and moves the same turn onto the fallback
   provider when the primary is slow or failing, without dropping the
   WebSocket.

The wire protocol is in ``protocol.py``. The web client is built against
that same text, so the field names there are a contract, not a sketch.

What it refuses
---------------
- It never calls a tool and never writes to DEVON's stores. It is a
  rendering lane: text in, tokens and frames out. Every effect DEVON can
  have stays behind the human gated paths in the main API.
- It refuses to start in a deployed environment on an empty or public
  default SECRET_KEY, with the same rule as ``app/core/config.py``.
- It refuses frames that name a blendshape outside the ARKit 52 or carry
  a weight outside 0..1, by naming the offender rather than clamping it.
- It never delays or drops audio. Audio chunks go to the client the
  moment they exist; only face frames are buffered and compressed.

What is a later gate
--------------------
- The provider base class has no streaming API, so the provider adapter
  in ``inference.py`` measures whole completion latency as its time to
  first token. SSE streaming against api.cerebras.ai is the next gate and
  was not verified in this build.
- ``CartesiaSpeech`` is a stub that raises ``SpeechNotConfigured``. The
  vendor response shape was not verified here and is not invented.
- LiveKit: CLOSED on 2026-09-16. This paragraph said the publisher did not
  exist and that audio reached the client over the WebSocket only. That was
  true and it was also a trap: with LIVEKIT_* set, frames were produced and
  dropped, and ``/health`` still answered 200 while DEVON said nothing.
  ``livekit_publisher.py`` now publishes into the room, ``livekit`` is pinned
  in ``requirements.txt``, and ``create_app`` refuses to boot when LIVEKIT_* is
  set without it. PROVEN against a real room on 2026-09-16 at 13:27:51Z: Tee
  set the three variables, opened the presence stage and heard DEVON speak.
  The service log for that turn carries the socket accept, then ``OPTIONS``
  and ``POST`` on ``/livekit/token`` at 200, which only answer that way when
  ``livekit_configured`` is true. No error was logged.
- Sentence level pipelining (starting speech before the last token) is
  not done. A turn streams every token, then speaks the whole reply.
"""

SERVICE_NAME = "devon-presence"
