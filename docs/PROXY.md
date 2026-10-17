# HTTP proxy support (1.0.1)

Default remains `http_transport = "direct"`: system DNS, validated global addresses, pinned destination IP, TLS hostname checks. A network that requires an outbound proxy may deny direct DNS/connections; version 1.0.0 could not collect through that environment.

For an explicitly configured, trusted proxy environment:

```bash
# HTTPS_PROXY/https_proxy must already point to a proxy you are authorized to use.
osintcli config http_transport proxy
osintcli scan example.com --modules dns,rdap,ct --yes
```

OsintCLI reads the normal proxy environment through Python's ProxyHandler. It does not discover proxies, circumvent a gateway, change NO_PROXY, disable TLS validation, or print proxy credentials. Proxy connection errors remain bounded and redacted. Python documentation: https://docs.python.org/3/library/urllib.request.html#urllib.request.ProxyHandler

**Trust boundary:** proxy mode cannot provide local DNS-to-socket pinning for origin hosts because the trusted proxy resolves/reaches them. Therefore it only permits exact, explicitly approved HTTPS hostnames. Default list contains the public DNS, RDAP registry, CT and public profile API sources. Every redirect is checked against the list; authentication is stripped when the hostname changes. HTTP, local names and IP literals are rejected. The owner-configured AI hostname is permitted only when that AI submission is explicitly requested.

To authorize a website for the direct website requests via proxy, append its exact public hostname to the comma-separated `proxy_allowed_hosts` list in Settings (preserve the existing source hosts). This is an explicit trust decision by the user, not automatic trust in arbitrary URLs returned by a source. No wildcard domains are accepted.

Origin-certificate TLS collection requires **direct mode**. A TLS-intercepting proxy's certificate must not be presented as the target's original certificate. In proxy mode that adapter returns `DIRECT_REQUIRED` instead of false success. Switch back with `osintcli config http_transport direct` on a network that permits direct access.

Proxy mode was exercised through real CLI calls, database persistence and exports. See LIVE-VERIFICATION.md for the observed source results and limitations; this is separate from mocked regression tests.
