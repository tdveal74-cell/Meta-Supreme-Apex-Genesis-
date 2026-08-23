"""Intelligence layer, trimmed for the soul service deployment.

The platform's own __init__ exports the Council engine. The phone lane needs
only the soul layer, so this deployment keeps the package shallow and the
cold start short. The modules it does import are byte-identical to main.
"""
