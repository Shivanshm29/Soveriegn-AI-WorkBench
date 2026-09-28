"""Sovereign HTTP Client with active network policy enforcement.

Guarantees that:
1. Every outbound request is checked against SovereigntyPolicy before network dispatch.
2. 3xx HTTP redirects to external destinations are intercepted and blocked.
3. Ambient environment proxies (HTTP_PROXY / HTTPS_PROXY) are ignored (trust_env=False).
"""

from typing import Optional, Dict, Any
from urllib.parse import urljoin
import httpx

from backend.app.security.sovereignty_policy import (
    SovereigntyPolicy,
    get_sovereignty_policy,
)
from backend.app.security.network_policy import SovereigntyViolationError


class SovereignHttpClient:
    """HTTP client wrapper enforcing local-only zero-egress policies."""

    def __init__(
        self,
        policy: Optional[SovereigntyPolicy] = None,
        component: str = "app",
        timeout: float = 30.0,
        **client_kwargs,
    ):
        self.policy = policy or get_sovereignty_policy()
        self.component = component
        self.timeout = timeout

        # Ensure environment proxies cannot silently divert traffic in sovereign mode
        client_kwargs["trust_env"] = False

        # Set up response hook to intercept any redirect before it is followed
        event_hooks = client_kwargs.get("event_hooks", {})
        existing_response_hooks = event_hooks.get("response", [])

        async def _sync_response_hook(response: httpx.Response):
            pass

        def _on_response(response: httpx.Response) -> None:
            # Check for redirect responses (HTTP 301, 302, 303, 307, 308)
            if response.is_redirect and "location" in response.headers:
                location = response.headers["location"]
                # Resolve relative redirect URLs against the original request URL
                target_url = str(response.url.join(location))
                # Validate redirect destination; raises SovereigntyViolationError if external
                self.policy.validate_endpoint(
                    target_url,
                    component=f"{self.component}:redirect",
                )

        combined_hooks = list(existing_response_hooks) + [_on_response]
        event_hooks["response"] = combined_hooks
        client_kwargs["event_hooks"] = event_hooks

        self._client = httpx.Client(timeout=self.timeout, **client_kwargs)

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Validate URL and issue HTTP request."""
        # Pre-validate target URL before dispatching to the network
        self.policy.validate_endpoint(str(url), component=self.component)
        resp = self._client.request(method, url, **kwargs)
        if resp.is_redirect and "location" in resp.headers:
            location = resp.headers["location"]
            if hasattr(resp, "url") and resp.url:
                target_url = str(resp.url.join(location))
            else:
                target_url = urljoin(str(url), location)
            self.policy.validate_endpoint(target_url, component=f"{self.component}:redirect")
        return resp

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
