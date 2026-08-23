# RAJA AI Chart Scanner V2

Mobile/PWA chart scanner using the same Quotex/Pocket Option pair lists from the supplied RAJA AI bot build.

## V2 changes
- Same RAJA AI Quotex/Pocket Option pair sets, grouped by Crypto Live, Crypto OTC, Forex Live and Forex OTC.
- Hidden admin route: open the app URL with `#admin`.
- Default admin code: `3250` (can be overridden with `RAJA_SCANNER_ADMIN_PASSWORD`).
- Bottom navigation does not expose Admin.
- RAJA-style sound alerts: candidate ding, T-10 beep, 5/4/3/2/1 ticks, directional entry tone and NO TRADE tone.
- Sound on/off button in the header.
- Current-candle countdown for 1m/2m/5m/10m/15m/30m.
- A valid signal waits for selected candle close, then opens a short next-candle ENTRY NOW alert window.
- Green/red full-screen flash and result-card pulse on signal/entry.
- Live Camera **ARM CLOSE SCAN** automatically captures a fresh chart frame at candle close, analyzes it, then shows the next-candle entry alert when valid.
- Screenshot upload remains available. Static screenshots cannot update while a candle is finishing, so Live Camera Close Scan is the strict close-confirm option.
- Entry alerts do not place a broker order automatically.

## Access rules retained
- 12-hour one-time free trial: one claim per User/UID + one per device.
- One active device/session; a new login replaces the previous device.
- Affiliate Pro: Quotex/Pocket Option partner signup + minimum $50 deposit + admin verification.
- Monthly Pro: €19.99/month with manual approval/payment-reference flow.

## Partner links
- Quotex: `https://broker-qx.pro/sign-up/?lid=2209395`
- Pocket Option: `https://u3.shortink.io/smart/txvQPFrBEgdZmL`

## Railway
Recommended persistence: `DATABASE_URL=<Railway Postgres URL>`

Default admin code is `3250`. Optional override: `RAJA_SCANNER_ADMIN_PASSWORD=...`

Optional price override: `RAJA_SCANNER_MONTHLY_PRICE_EUR=19.99`

## Technical note
The image engine analyzes visible chart pixels/price action and does not fabricate exact RSI/EMA/MACD/ADX/ATR values when a screenshot does not contain trustworthy OHLC history.
