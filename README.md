# makefun-polymarket-faa-attribution-02

Entry for make.fun's **polymarket-faa-attribution-02**: forecast the Yes
price of every market in Polymarket's FAA outage attribution family at
every minute of the 4 hours after each checkpoint — five quantiles
(5/25/50/75/95%) per market per minute, 240 minutes per case.

`main.py` (Python 3.13, standard library only, no network, deterministic)
reads each case file in `$MAKEFUN_INPUT_DIR` and writes one forecast file
per case to `$MAKEFUN_OUTPUT_DIR`. Instead of scaling a random walk from
one-minute volatility — which badly overstates four-hour travel because
grid midpoints bounce — it reads the travel distribution straight from
each market's own last 24 hours: empirical quantiles of H-minute price
changes for several horizons H, interpolated in sqrt(h) and blended with
the house random-walk spread to steady thin samples.
