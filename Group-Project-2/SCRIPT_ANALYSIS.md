# Source inspection reference — Part 2

This is a technical reference for independent investigation, not a completed assignment response. Line numbers refer to the two unmodified local assignment files inspected in full. No remote script run has taken place and no success/failure condition has been observed on your lab instance.

## Inspected files and dependencies

| Variant | File | SHA-256 |
| --- | --- | --- |
| Original | `infinite-money-logic-flaw.py` | `fe1dcd851416b188686d271818b4091326cd99d2ba234a78d54e63b3d9ba96c4` |
| Updated | `infinite-money-logic-flaw__updated.py` | `d3957ab9d901dba7f8128d55dfa40d6b02f6352938ae281cd14cb5549e09b55d` |

Original imports `requests`, `requests.packages.urllib3.exceptions.InsecureRequestWarning`, `re`, and `sys` (lines 3–8). Updated adds standard-library `os` (lines 5–11). The vendored urllib3 import resolves through Requests; Requests and its four runtime dependencies are pinned in `requirements.txt`. No Beautiful Soup, browser automation, additional Python framework, or Git is used. Updated `compare()` executes the external shell command `diff` (line 25); Docker therefore includes Debian `diffutils`. Standard-library Python `pdb`, `unittest`, and interactive consoles are available without extra packages.

## Original: observed code flow

There are no user-defined functions: all execution is top-level. Lines 10–12 require exactly one positional argument. Line 16 takes the URL directly; the script itself does not validate or normalize it. Line 14 defines a proxy at container-local `127.0.0.1:8080`; lines 4–6 suppress insecure TLS warnings. Every HTTP call supplies `verify=False`. Neither a proxy service nor host Burp is available in this lab, so literal unwrapped execution is incompatible with the isolation/transport requirements.

The loop at lines 19–95 runs up to 500 times, printing a carriage-return progress counter. Each iteration performs these eight explicit requests, sequentially:

| Step | Lines | Request and state handling |
| --- | --- | --- |
| Login form | 21–23 | `GET <base>login`; take the returned `session` cookie; parse a first matching HTML value using regex |
| Authentication | 25–37 | `POST login` with `csrf`, hardcoded training account credentials, and an explicit Cookie header; disable redirects; require a new `session` cookie in this response |
| Add item | 39–49 | `POST cart` with `productId=2`, `redir=PRODUCT`, and `quantity=1` |
| Read cart | 51–52 | `GET cart`, then extract another value using the same broad CSRF regex |
| Coupon | 55–64 | `POST cart/coupon` with that token and fixed `SIGNUP30` |
| Checkout | 66–74 | `POST cart/checkout` using the same token |
| Confirmation | 76–86 | `GET cart/order-confirmation?order-confirmed=true`; extract the first cell immediately after the precisely formatted Code header/row |
| Redeem | 87–95 | `POST gift-card` using the extracted code and the cart token; disable redirects |

`requests.get/post` calls are used directly rather than a script-level persistent `requests.Session`. The manually constructed Cookie header carries the post-login cookie through the remaining steps. Each iteration logs in again; this is a fresh HTTP authentication sequence, not a fresh account or reset of server-side credit/order history. All POSTs explicitly disable redirects; GETs use Requests' normal redirect behavior. The script assumes both login responses contain the expected session cookie; missing cookies raise `KeyError`.

The CSRF pattern (lines 23 and 52) matches an attribute sequence rather than an input explicitly named `csrf`. The confirmation pattern (lines 83–86) depends on exact whitespace/newlines and selects the row adjacent to the header. Both dereference `.group(1)` without checking for no match. These choices can fail on altered HTML, redirects, an expired lab, an error page, or a different form. Those are source-level failure possibilities, not observed outcomes.

`r3`, `r5`, `r6`, and `r8` are never validated. There is no `raise_for_status()`, credit check, redemption-result check, completion assertion, or jacket-purchase request. `productId=2` is assumed to be the relevant gift-card item; confirm the actual catalogue mapping in your own lab. The absence of a jacket purchase matters separately from whether the code successfully increases credit.

## Updated: observed changes

The login/cart/coupon/checkout sequence is materially the same (lines 41–103). Credentials, product ID, coupon, session assumptions, CSRF reuse, proxy/TLS settings, request count per iteration, and the 500-iteration upper bound are unchanged.

The new `compare(File1, File2)` function (lines 14–26) reads each file into a set (`d` and `e`), but neither set is used. It writes the stdout of `os.popen("diff " + File1 + " " + File2).read()` to `file3.txt`. This is an external text diff, not a Python set-difference calculation or an HTML-aware comparison. The filenames passed by this script are fixed local names, so URL input is not interpolated into the shell command.

The changed extraction sequence is:

- First iteration, lines 105–115: use the original Code-header regex, print the code, and save the full confirmation HTML as `req.txt`.
- Later iterations, lines 117–126: save current HTML as `req2.txt`, compare old and current HTML, then replace `req.txt` with the current page for the next iteration.
- Lines 129–140: read `file3.txt`, find the first generic `<td>(.*?)</td>` match anywhere in the diff text, and use that match as the code.
- Lines 142 and 147–155: print the selected code and submit it using the same `POST gift-card` workflow.

The changed functionality is therefore selection of a cell from the textual change between consecutive confirmation pages. It could select a newly added gift-card row when the confirmation page accumulates earlier orders and the original header-adjacent row remains an already-redeemed card. **That page structure and redemption behavior are hypotheses requiring real evidence.** Nothing in the local files proves your server uses that structure.

The updated parser does not distinguish added `>` lines from removed `<` lines, check that the cell is a gift-card code, or verify successful redemption. A changed old row, unrelated table cell, empty diff, different whitespace, or missing `diff` can break the assumption. Normal `diff` exit 1 means files differ; the code ignores its exit status entirely, including operational errors. On a regex failure `.group(1)` raises `AttributeError`. The new prints disclose redeemable gift-card codes, and the HTML/diff files may contain tokens and account data; the controlled runner keeps files private and redacts terminal codes.

## What the lab documentation establishes

PortSwigger states that the objective is buying the target leather jacket. Its documented workflow discounts a gift card with the newsletter coupon and redeems it for more credit than its purchase cost. This supports investigating the purchase/redemption cycle; it does not verify either downloaded script on your instance. See the [official lab description and workflow](https://portswigger.net/web-security/logic-flaws/examples/lab-logic-flaws-infinite-money).

## Controlled execution and comparison boundaries

The runner verifies both source hashes, then generates a separate copy per run in the Docker volume. Only the proxy dictionary and eight `verify=False` literals are replaced with `{}` and `verify=True`; line numbers and business logic remain unchanged. `safety-diff original|updated` makes this reviewable. An additional Requests HTTP adapter guard validates the selected exact HTTPS hostname on every send, including redirects, forces certificate verification, and bypasses proxy settings. No requests are added, replayed, reordered, retried, or made concurrent. Terminal output redaction/timestamps are instrumentation, not source behavior. Recorded execution is explicitly described as transport-safe execution of the supplied logic; it is not evidence of the literal hardcoded proxy/TLS behavior.

Optional HTTP evidence records methods, known endpoint paths, timestamps, status codes, exception types, and opaque per-run gift-card reference numbers. Repeated reference numbers show that the same gift-card value was submitted again without revealing the value. They do **not** prove why a server rejected it, that it was successfully redeemed, or that account credit increased. Each reference namespace starts fresh in each run.

## Evidence to collect before drawing conclusions

Use separate fresh instances of the same named Academy lab for a controlled comparison, or explicitly document differing initial balances, coupons, history, and elapsed time. A new container does not reset the remote lab. Do not automatically rerun a failed attempt: purchases and redemptions are not rolled back.

Record starting credit, selected lab/instance, source hashes, container/dependency versions, timestamps, run exit code, and the transport-policy diff. For the original inspect progress, HTTP statuses, repeated opaque gift-card references, private confirmation HTML where available, and the account/confirmation interface. Check whether the header-adjacent card remains the same after another order, whether a redemption error is shown, and whether credit stops increasing. Treat these as observations to make, not prefilled findings.

For the updated variant compare opaque card references and account credit, and privately inspect `req.txt`, `req2.txt`, and `file3.txt` if extraction fails. The last file pair only covers the latest iteration; it is not a complete page archive. The original writes no such HTML files, so its confirmation-page structure must be checked in the browser or debugger. Avoid sharing raw response bodies, code values, cookies, tokens, or debugger locals.

Check the browser's explicit solved indicator after completing the actual objective. If automation only accumulates credit, note separately any manual steps taken afterward. A zero process exit means the script ended without an uncaught exception; a `302` alone does not establish successful redemption or completion. A nonzero exit after several iterations can coexist with earlier successful purchases. No run outcome has been verified during implementation.
