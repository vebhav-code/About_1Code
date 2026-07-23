# 1Code Challenge: Silent Session Expiry

## Run

```
npm install
npm start
```

Server starts on `http://localhost:4000`.

## Reproduce the bug

1. Log in:
   ```
   curl -i -c cookies.txt -X POST http://localhost:4000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"demo","password":"demo123"}'
   ```
   Copy the `accessToken` from the JSON response.

2. Immediately call the protected route (should work):
   ```
   curl -i http://localhost:4000/api/auth/me \
     -H "Authorization: Bearer <accessToken>"
   ```

3. Wait about 30-40 seconds for the access token to expire, then try to refresh using the cookie jar from step 1:
   ```
   curl -i -b cookies.txt -X POST http://localhost:4000/api/auth/refresh
   ```

   Expected: a new `accessToken` is returned and the session continues.
   Actual: the endpoint returns `401 Invalid or expired refresh token`, even though the refresh token cookie has a 7-day lifetime and has not expired.
