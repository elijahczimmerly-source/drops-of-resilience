# Why Dampening Variance Improves RMSE (and Why NEX "Wins" on RMSE)

## The puzzle

NEX underpredicts extreme precipitation by 25% (Ext99 = -25.3%), yet has the lowest RMSE of all three products (8.64 vs DOR's 9.91). How does getting the extremes *wrong* lead to a *better* error score?

## RMSE measures the difference between sim and obs

RMSE is the root-mean-square of `sim - obs` across all pixel-days. When bias is near zero (the means of sim and obs are approximately equal, which they are because bias correction did its job), RMSE squared equals the **variance of the difference**:

RMSE² = Var(sim - obs)

## The variance of a difference between independent variables

There's a standard statistical identity:

Var(X - Y) = Var(X) + Var(Y) - 2 * Cov(X, Y)

When X and Y are **correlated** (Cov > 0), their swings partially line up. The difference between them is smaller than you'd expect from their individual variances alone, because when X swings high, Y tends to swing high too, and the errors cancel.

When X and Y are **independent** (Cov = 0, i.e. r = 0), their swings don't line up at all. The variance of their difference is just the sum of their individual variances:

Var(sim - obs) = Var(sim) + Var(obs) = sigma_sim² + sigma_obs²

## Why this applies to precipitation

For pr, the pixel-day correlation between DOR and GridMET is r ~ 0.025 — essentially zero. The GCM doesn't know which pixels are wet on which days, so DOR's daily spatial pattern is effectively independent of reality. This means:

**RMSE² ~ sigma_sim² + sigma_obs²**

sigma_obs is fixed (that's reality — about 7.1 mm/day). The only lever is sigma_sim.

## Why dampening variance helps

Because the means are the same (bias correction did its job), the biggest factor in how sim and obs differ day-to-day is their variances — i.e., how big the swings are. When two series have the same mean but their swings don't line up, bigger swings mean bigger mismatches.

If DOR produces a realistic distribution (sigma_sim ~ sigma_obs ~ 7.1), then:

RMSE² ~ 7.1² + 7.1² ~ 101 → RMSE ~ 10.0

If NEX compresses the distribution (sigma_sim ~ 5.3, consistent with 25% Ext99 underprediction):

RMSE² ~ 5.3² + 7.1² ~ 78.5 → RMSE ~ 8.9

NEX makes smaller guesses. The guesses are still in the wrong places, but each wrong guess costs less because it's closer to the mean. The extreme case: predict the climatological mean everywhere, every day (sigma_sim = 0). RMSE would equal sigma_obs ~ 7.1 — the lowest possible — but Ext99 would be -100%.

## The only way to reduce RMSE without dampening variance

Improve r — make the daily spatial pattern less random. If the covariance term is positive (sim and obs swings partially line up), the variance of their difference shrinks even when both have large individual variance. Getting r from ~0.025 to ~0.26 would match NEX's RMSE while keeping DOR's nearly perfect Ext99. This is the motivation behind the cross-variable noise conditioning idea (see `PLAN-CROSS-VARIABLE-NOISE.md`).
