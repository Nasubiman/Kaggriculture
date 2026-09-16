# Incumbent-centered genome search v3

The current `main.py` remains unchanged.  This change makes future searches
start from its frozen genome and preserves its WOOL, STRAWBERRY, and WHEAT
market gates in most first-stage candidates.  Earlier searches spent almost
all of their standard 48-candidate budget on stale default-genome anchors.

The search space now includes a configurable step-0 WHEAT round trip.  Its
default `inherit` mode reproduces the current agent; explicit `roundtrip_first`
at quantity 45 also reproduces the current opening.  Alternative modes retain
the same net 13 WHEAT.  The local search uses incumbent-derived mechanism
anchors, conditionally avoids inactive-gate mutations, and recombines market
products independently instead of swapping every economic setting at once.

The default league now includes v45, v43, v41 competitive, v38 low pressure,
and results5.  Screening/race/final seed counts are 8/24/200 per opponent and
both seats.  A candidate is not promoted unless the held-out reward and margin
gate passes.  Search random seed and game-seed origin are exposed as Makefile
arguments.

Run on the compute server with `make current-genome-search`; inspect the result
with `make current-genome-status`.  `make current-genome-use` remains a separate,
explicit promotion step.  The first execution was a deliberately tiny
three-opponent, 12-candidate smoke test.  It completed all stages, returned
`accepted=false`, and did not change `main.py`.  The smoke test is not evidence
of a performance improvement.

Checks: `PYTHONPATH=training .venv/bin/python -m unittest
training/test_current_genome_search.py -v`; five full-episode seed checks found
identical final rewards for the plain incumbent, the inherited genome, and an
explicit 45-unit round trip.  A promoted standalone file made from the
unchanged incumbent genome also matched `main.py` exactly on three seeds in
both seats against v45.
