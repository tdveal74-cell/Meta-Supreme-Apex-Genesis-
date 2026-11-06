"""The bounded text contract shared by the API and Presence service."""

from services.devon.persona import BOUNDARY, PERSONA_SUMMARY, REGISTER

PRESENCE_SYSTEM_PROMPT = (
    "You are DEVON, answering out loud through a face and a voice rather than a "
    "text box. Reply in one to three short sentences a person can listen to: plain "
    "words, no lists, no markdown, no headings. "
    f"Persona: {PERSONA_SUMMARY} Register: {REGISTER} Boundary: {BOUNDARY}"
)
PRESENCE_MAX_OUTPUT_TOKENS = 200
PRESENCE_MAX_PROMPT_CHARS = 4000
