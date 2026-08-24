# Week 2 : The page showed nothing at all

## Problem

The results page went completely blank. Not an error message, not half
a table - a white screen.

The backend was fine. Opening the data directly in the browser worked:

```text
http://127.0.0.1:8000/api/demo   ->  200, full JSON
```

So the data was there and the page still showed nothing.

## Cause

The page gets the data and builds the whole table in one step:

```javascript
const d = await (await fetch("/api/demo")).json();
out.innerHTML = `... ${d.chains.map(...)} ...`;
```

The backend response had changed, so `d.chains` did not exist any more.
`d.chains.map(...)` failed, the function stopped right there, and
`out.innerHTML` was never set. The page was left empty.

The error was only printed in the browser console, which I did not have
open, so from the outside it just looked like nothing happened.

## Fix

Check the response first, and show the problem if something is wrong:

```javascript
try {
  const res = await fetch("/api/demo");
  if (!res.ok) throw new Error("/api/demo returned " + res.status);
  d = await res.json();
} catch (err) {
  out.innerHTML = `<div class="err">Could not load the demo.<br>${err.message}</div>`;
  return;
}
```

Now a red box appears with the reason instead of a blank page.

## What I learned

A blank page is the worst error message, because it looks the same
whether the server is down, the data is wrong, or there is a typo in
the JavaScript. A few lines turned it into a sentence saying what
broke.

This matters for us because we demo this live. A red box telling us
what to fix is recoverable in front of people. A white screen is not.
