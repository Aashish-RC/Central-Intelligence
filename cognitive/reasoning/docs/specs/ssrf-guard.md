Authored by a session that read the source or the old code. Implementation must be done by a fresh session that sees only this file.

Purpose: before the gateway makes an outbound request to a URL taken from config or a request, decide if it is safe.
Rules:
1. Only http and https. Reject others (file, ftp, gopher, data).
2. Reject URLs containing credentials (user:pass@).
3. Resolve the hostname; check EVERY returned address. If any address is unsafe, reject.
4. Unsafe: IPv4 loopback 127/8, 0.0.0.0/8, private 10/8, 172.16/12, 192.168/16, link-local 169.254/16 (includes cloud metadata 169.254.169.254), shared address space 100.64/10, multicast and reserved ranges; IPv6 ::1, ::, fc00::/7, fe80::/10, multicast ff00::/8; IPv4-mapped IPv6 (::ffff:a.b.c.d) is judged by the embedded IPv4.
5. Numeric forms are normalised before checking: decimal (2130706433), hex (0x7f000001), octal (0177.0.0.1), short forms (127.1) all count as loopback.
6. Fail closed: DNS failure, timeout, or empty answer means reject.
7. Allow-list: an explicit config list of hosts (for example localhost for a local model runtime) may bypass rule 4 only for those exact hosts and ports.
8. Redirects are not followed automatically. Each redirect target is validated again; maximum 3 hops; a redirect from https to http is rejected.
9. Where the runtime allows, connect to the validated address (pin) to reduce DNS rebinding. If not possible, document the residual risk.
Resolver is injectable for tests; the default uses the system resolver. Tests must run offline.
Edge cases to test: every range above, each numeric form, a hostname that resolves to one public and one private address, DNS failure, allow-listed localhost, redirect to a private address, https-to-http redirect, credentials in URL.
