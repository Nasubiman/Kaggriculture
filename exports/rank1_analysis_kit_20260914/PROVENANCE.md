# Provenance and limitations

This kit contains public Kaggle game-history data for the Kaggriculture team
`Majkel1337`, submission id `56156662`, collected through 2026-09-14.

The action in a Kaggle raw replay is serialized one step after the observation
that produced it. The two derived JSONL datasets pair `observation[t]` with
`action[t+1]`. No private opponent observation is reconstructed: `private`
contains only what the rank-1 player could observe in its own seat.

The corpus is observational. It does not prove that a frequent conditional
behavior is part of the submitted agent's source code, and it may reflect the
distribution of public opponents and seeds.

