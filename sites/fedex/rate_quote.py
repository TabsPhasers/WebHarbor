"""Issue and verify server-signed rate-estimate request facts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import asdict, dataclass


SIGNING_KEY = b"webharbor-fedex-rate-quote-v1"


@dataclass(frozen=True)
class QuoteRequest:
    origin_state: str
    destination_state: str
    weight_lb: float
    package_type: str


def issue_quote_token(quote: QuoteRequest) -> str:
    payload = json.dumps(asdict(quote), sort_keys=True, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(SIGNING_KEY, encoded, hashlib.sha256).hexdigest().encode()
    return (encoded + b"." + signature).decode()


def verify_quote_token(token: str) -> QuoteRequest | None:
    try:
        encoded, supplied_signature = token.encode().rsplit(b".", 1)
        expected_signature = hmac.new(SIGNING_KEY, encoded, hashlib.sha256).hexdigest().encode()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        padding = b"=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        quote = QuoteRequest(
            origin_state=str(payload["origin_state"]),
            destination_state=str(payload["destination_state"]),
            weight_lb=float(payload["weight_lb"]),
            package_type=str(payload["package_type"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return quote if quote.weight_lb > 0 else None
