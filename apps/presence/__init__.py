"""DEVON presence streaming middleware.

What this is
------------
A separate FastAPI service that turns one DEVON reply into a presence
stream for a web client: the tokens as they arrive, ARKit face blendshape
frames on an audio timeline, and (when LiveKit is not configured) the
audio itself as PCM chunks over the same WebSocket. It sits beside the
DEVON API and trusts the same access JWTs, so a signed in web session can
open it with the token it already holds.

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
- LiveKit: this service mints join tokens (``livekit_token.py``) but does
  not publish audio into a room. That publisher needs a LiveKit server
  SDK that is not in ``requirements.txt``. Until it exists, audio reaches
  the client over the WebSocket only, and only when LIVEKIT_* is unset.
- Sentence level pipelining (starting speech before the last token) is
  not done. A turn streams every token, then speaks the whole reply.
"""

SERVICE_NAME = "devon-presence"
