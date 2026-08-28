# Getting Started with REST APIs

A practical, beginner-friendly guide to what REST APIs are and how to use them —
methods, status codes, headers, data formats, and authorization. Examples use
the weather API in this project so the concepts stay concrete.

---

## Table of contents

1. [What is an API?](#1-what-is-an-api)
2. [What makes an API "REST"?](#2-what-makes-an-api-rest)
3. [Anatomy of a request and response](#3-anatomy-of-a-request-and-response)
4. [HTTP methods (the "verbs")](#4-http-methods-the-verbs)
5. [Status codes](#5-status-codes)
6. [Passing data: path, query, headers, body](#6-passing-data-path-query-headers-body)
7. [Content types & data formats](#7-content-types--data-formats)
8. [Authentication & authorization](#8-authentication--authorization)
9. [Common headers](#9-common-headers)
10. [Calling an API: tools & examples](#10-calling-an-api-tools--examples)
11. [Good practices](#11-good-practices)
12. [Glossary](#12-glossary)

---

## 1. What is an API?

An **API** (Application Programming Interface) is a contract that lets one piece
of software talk to another. A **web API** does this over HTTP — the same
protocol your browser uses.

Instead of a human clicking buttons, a program sends a **request** to a URL and
gets back **data** (usually JSON) it can process.

> In this project, your FastAPI app *is* a web API. A browser or `curl` sends it
> `GET /weather?location=London`, and it responds with JSON. Under the hood,
> your app is itself a *client* of another API (Open-Meteo).

---

## 2. What makes an API "REST"?

**REST** (REpresentational State Transfer) is a style — a set of conventions —
for building web APIs. An API is "RESTful" when it follows ideas like:

- **Resources** are the nouns, identified by URLs.
  `/weather`, `/forecast`, `/users/42`.
- **HTTP methods** are the verbs (see below). The same URL can behave
  differently for `GET` vs `DELETE`.
- **Stateless**: each request carries everything the server needs. The server
  doesn't remember previous requests — no server-side session between calls.
- **Uniform, predictable structure**: standard methods, standard status codes,
  standard headers.
- **Representations**: the server sends a *representation* of a resource,
  commonly JSON.

REST is a convention, not a strict standard — most "REST APIs" follow most of
these ideas rather than all of them perfectly.

---

## 3. Anatomy of a request and response

**A request** has four parts:

```
GET /weather?location=London HTTP/1.1      ← method + path + query + version
Host: 127.0.0.1:8077                        ┐
Accept: application/json                    ├ headers (metadata)
Authorization: Bearer abc123                ┘
                                            ← blank line
{ "optional": "body" }                      ← body (data sent to server)
```

**A response** mirrors it:

```
HTTP/1.1 200 OK                             ← status line (code + reason)
Content-Type: application/json              ┐
Content-Length: 342                         ┘ headers
                                            ← blank line
{ "location": {...}, "current": {...} }     ← body (data returned)
```

A full URL breaks down like this:

```
https://api.example.com:443/v1/weather?location=London&days=3#section
└─┬─┘   └──────┬───────┘└┬┘└────┬────┘ └────────┬──────────┘ └──┬──┘
scheme      host       port   path            query          fragment
```

---

## 4. HTTP methods (the "verbs")

The method tells the server *what kind of action* you want on a resource.

| Method     | Purpose                              | Has body? | Safe? | Idempotent? |
|------------|--------------------------------------|-----------|-------|-------------|
| **GET**    | Read / retrieve a resource           | No        | Yes   | Yes         |
| **POST**   | Create a resource / trigger an action| Yes       | No    | No          |
| **PUT**    | Replace a resource entirely          | Yes       | No    | Yes         |
| **PATCH**  | Update part of a resource            | Yes       | No    | No          |
| **DELETE** | Remove a resource                    | Usually no| No    | Yes         |
| **HEAD**   | Like GET but headers only (no body)  | No        | Yes   | Yes         |
| **OPTIONS**| Ask what methods/permissions apply   | No        | Yes   | Yes         |

- **Safe** = doesn't change data on the server (read-only).
- **Idempotent** = doing it once or many times has the same effect. `DELETE`ing
  the same item twice leaves the same end state; `POST`ing twice may create two
  records.

**Examples**

```bash
GET    /weather?location=London     # read current weather   (this project)
POST   /users        {name:"Ana"}   # create a new user
PUT    /users/42     {full record}  # replace user 42 entirely
PATCH  /users/42     {email:"..."}  # change just the email
DELETE /users/42                    # remove user 42
```

> This project is read-only, so it only uses **GET**.

---

## 5. Status codes

The 3-digit response code tells you what happened. The first digit is the class:

| Range | Class          | Meaning                             |
|-------|----------------|-------------------------------------|
| 1xx   | Informational  | Rarely seen directly                |
| 2xx   | **Success**    | It worked                           |
| 3xx   | Redirection    | Look elsewhere                      |
| 4xx   | **Client error** | *You* sent something wrong        |
| 5xx   | **Server error** | The *server* failed               |

**The ones you'll actually meet:**

| Code | Name                  | When                                             |
|------|-----------------------|--------------------------------------------------|
| 200  | OK                    | Standard success (GET returned data)             |
| 201  | Created               | POST successfully created a resource             |
| 204  | No Content            | Success, nothing to return (e.g. DELETE)         |
| 301/302 | Moved / Found      | Resource is at a different URL                   |
| 400  | Bad Request           | Malformed request                                |
| 401  | Unauthorized          | Missing/invalid credentials (**authentication**) |
| 403  | Forbidden             | Authenticated, but not allowed (**authorization**)|
| 404  | Not Found             | No such resource                                 |
| 405  | Method Not Allowed    | Wrong method for this URL                         |
| 422  | Unprocessable Entity  | Body/params valid syntax but failed validation   |
| 429  | Too Many Requests     | Rate limit hit — slow down                        |
| 500  | Internal Server Error | Unhandled error on the server                     |
| 502/503 | Bad Gateway / Unavailable | Upstream failed / server overloaded      |

**From this project:**

| Code | Example trigger                                       |
|------|-------------------------------------------------------|
| 200  | `GET /weather?location=London`                        |
| 404  | `GET /weather?location=zzzznotaplace` (can't geocode) |
| 422  | `GET /forecast?location=London&days=0` (days must be ≥1)|
| 502  | Open-Meteo unreachable                                 |

> **401 vs 403** is a classic confusion: **401** = "I don't know who you are"
> (bad or missing credentials). **403** = "I know who you are, but you can't do
> this."

---

## 6. Passing data: path, query, headers, body

There are four places to put information in a request:

| Location    | Looks like                          | Use for                                  |
|-------------|-------------------------------------|------------------------------------------|
| **Path**    | `/users/42`                         | *Identifying* a specific resource        |
| **Query**   | `/weather?location=London&days=3`   | Filtering, options, search parameters    |
| **Headers** | `Authorization: Bearer ...`         | Metadata: auth, content type, caching    |
| **Body**    | `{ "name": "Ana" }`                 | The payload for POST/PUT/PATCH           |

**Path vs query rule of thumb:** the path says *which* resource; the query says
*how* you want it. This project uses query params: `?location=London&days=3`.

```
/forecast ? location=London & days=3
          ↑            ↑
        starts      separates
        query       params
```

---

## 7. Content types & data formats

The `Content-Type` header declares the format of the body. Common ones:

| Content-Type                        | Format                               |
|-------------------------------------|--------------------------------------|
| `application/json`                  | **JSON** — the default for most APIs |
| `application/x-www-form-urlencoded` | HTML form fields (`a=1&b=2`)         |
| `multipart/form-data`               | File uploads                         |
| `text/plain`                        | Plain text                           |
| `application/xml`                   | XML (older APIs)                     |

**JSON** is the lingua franca of REST. Example body:

```json
{ "name": "Ana", "age": 30, "tags": ["admin", "beta"], "active": true }
```

- The **request** says what it's sending with `Content-Type`.
- The **request** says what it wants back with the `Accept` header.
- The **response** says what it actually sent with `Content-Type`.

---

## 8. Authentication & authorization

Two different things people lump together:

- **Authentication** = *who are you?* (proving identity) → failures give **401**.
- **Authorization** = *what are you allowed to do?* (permissions) → **403**.

Credentials are almost always passed in the **`Authorization` header** (or
sometimes a custom header / query param). Here are the common schemes:

### 8.1 No auth (public API)

Open-Meteo — and this tutorial project — need no credentials at all. Fine for
public, read-only data.

```bash
curl "http://127.0.0.1:8077/weather?location=London"
```

### 8.2 API key

A single secret string identifying the *application*. Simple, common for public
data services. Passed as a header (preferred) or query param.

```bash
# As a header (better — stays out of logs/URLs):
curl -H "X-API-Key: sk_live_abc123" https://api.example.com/data

# As a query param (easier, but leaks into logs/history):
curl "https://api.example.com/data?api_key=sk_live_abc123"
```

### 8.3 Bearer token (incl. OAuth 2.0 / JWT)

A token — often a **JWT** — representing a logged-in user or granted scope. The
most common scheme for modern APIs. The client obtains a token (via login or an
OAuth flow), then sends it on every request:

```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiI..." \
  https://api.example.com/me
```

**OAuth 2.0** is the framework for *getting* that token without sharing a
password (think "Sign in with Google"). Simplified flow:

```
1. App redirects user to the provider's login/consent page.
2. User approves; provider redirects back with an authorization code.
3. App exchanges the code (+ its secret) for an access token.
4. App calls the API with:  Authorization: Bearer <access_token>
5. Token expires; app uses a refresh token to get a new one.
```

Tokens usually **expire** (minutes to hours) and carry **scopes** (e.g.
`read:weather`) that limit what they can do — that's authorization built in.

### 8.4 Basic auth

Username and password, Base64-encoded in the header. Simple but weak — only over
HTTPS, and rarely used for public APIs today.

```bash
curl -u alice:secret https://api.example.com/data
# sends header:  Authorization: Basic YWxpY2U6c2VjcmV0
```

> Base64 is **encoding, not encryption** — anyone can decode it. Basic auth is
> only safe over HTTPS.

### 8.5 Session cookies

After login, the server sets a `Set-Cookie` header; the browser returns it
automatically on later requests. Common for websites, less so for
service-to-service APIs.

### Scheme comparison

| Scheme        | Identifies   | Where              | Expires? | Typical use                    |
|---------------|--------------|--------------------|----------|--------------------------------|
| None          | —            | —                  | —        | Public, read-only data         |
| API key       | App          | Header/query       | No       | Public data services, quotas   |
| Basic         | User         | `Authorization`    | No       | Internal tools, legacy         |
| Bearer / JWT  | User/app     | `Authorization`    | Yes      | Modern APIs, mobile, SPAs      |
| OAuth 2.0     | User/app     | `Authorization`    | Yes      | Third-party access delegation  |
| Session cookie| User         | `Cookie`           | Yes      | Browser-based web apps         |

> **Keep secrets out of code.** Put keys/tokens in environment variables or a
> secrets manager — never commit them to git. Always use **HTTPS** so
> credentials aren't sent in the clear.

---

## 9. Common headers

| Header          | Direction | Purpose                                          |
|-----------------|-----------|--------------------------------------------------|
| `Authorization` | request   | Credentials (`Bearer ...`, `Basic ...`)          |
| `Content-Type`  | both      | Format of the body being sent                    |
| `Accept`        | request   | Format the client wants back                     |
| `User-Agent`    | request   | Identifies the client software                   |
| `Cache-Control` | both      | Caching rules                                     |
| `Set-Cookie`    | response  | Server asks client to store a cookie             |
| `Location`      | response  | Where a created/moved resource lives             |
| `Retry-After`   | response  | With 429/503: how long to wait                   |
| `X-RateLimit-*` | response  | How many requests you have left                  |

---

## 10. Calling an API: tools & examples

### curl (command line)

```bash
# GET with query params
curl "http://127.0.0.1:8077/weather?location=London"

# Show status code and headers
curl -i "http://127.0.0.1:8077/weather?location=London"

# POST JSON with a header
curl -X POST https://api.example.com/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{"name": "Ana"}'
```

### Python (`requests` / `httpx`)

```python
import httpx

resp = httpx.get(
    "http://127.0.0.1:8077/forecast",
    params={"location": "London", "days": 3},
    headers={"Accept": "application/json"},
)
resp.raise_for_status()      # raises on 4xx/5xx
data = resp.json()
print(data["daily"][0]["description"])
```

> This is exactly what `app/weather_client.py` does to call Open-Meteo.

### JavaScript (`fetch`)

```javascript
const res = await fetch("/weather?location=London");
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const data = await res.json();
console.log(data.current.temperature_c);
```

> This is what the UI in `app/static/index.html` uses.

### Browser / Swagger UI

Interactive docs are auto-generated by FastAPI:

- Swagger UI: `http://127.0.0.1:8077/docs`
- OpenAPI schema: `http://127.0.0.1:8077/openapi.json`

Other GUI tools: **Postman**, **Insomnia**, **Hoppscotch**.

---

## 11. Good practices

- **Use the right method & status code** — GET to read, POST to create, `201`
  for created, `404` for missing.
- **Version your API** — `/v1/weather` so you can evolve without breaking
  clients.
- **Validate input** and return `422`/`400` with a clear message (FastAPI does
  this automatically — try `days=0`).
- **Handle errors on the client** — always check the status code before trusting
  the body.
- **Respect rate limits** — watch for `429` and `Retry-After`.
- **Paginate large lists** — `?page=2&limit=50` instead of returning everything.
- **Always use HTTPS** in production.
- **Never hard-code secrets** — use env vars / secrets managers.
- **Read the docs** — every API documents its resources, params, and auth.

---

## 12. Glossary

| Term         | Meaning                                                        |
|--------------|----------------------------------------------------------------|
| **Endpoint** | A specific URL + method combo you can call (`GET /weather`).    |
| **Resource** | A "thing" the API exposes, identified by a URL.                |
| **Payload**  | The data in a request/response body.                           |
| **Header**   | Key–value metadata attached to a request/response.            |
| **JSON**     | JavaScript Object Notation — the usual data format.            |
| **JWT**      | JSON Web Token — a signed, self-contained bearer token.        |
| **OAuth**    | A framework for delegated authorization (login without sharing passwords). |
| **Scope**    | A permission attached to a token (`read:weather`).             |
| **Idempotent** | Repeating the call yields the same end state.                |
| **Rate limit** | A cap on how many requests you may make in a time window.    |
| **CORS**     | Browser rules controlling cross-origin requests to an API.     |
| **Payload / Body** | Data sent with POST/PUT/PATCH requests.                  |
| **OpenAPI**  | A standard spec describing an API (powers Swagger UI).         |

---

### See also

- [`README.md`](../README.md) — this project's own endpoints and how they work.
- [Open-Meteo docs](https://open-meteo.com/en/docs) — the upstream API used here.
- [MDN: HTTP](https://developer.mozilla.org/en-US/docs/Web/HTTP) — deep reference
  on methods, status codes, and headers.
