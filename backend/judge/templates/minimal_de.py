import numpy as np


def optimize(f, dim, lower, upper, budget, rng):
    # Differential evolution (rand/1/bin). Each generation is evaluated as one
    # batch, which is much faster than calling f once per point.
    pop_size, F, CR = 10 * dim, 0.7, 0.9
    pop = rng.uniform(lower, upper, size=(pop_size, dim))
    fit = f(pop)

    while True:  # f raises BudgetExhausted when the budget is used up
        a, b, c = (pop[rng.permutation(pop_size)] for _ in range(3))
        mutant = np.clip(a + F * (b - c), lower, upper)
        cross = rng.random((pop_size, dim)) < CR
        cross[np.arange(pop_size), rng.integers(dim, size=pop_size)] = True
        trial = np.where(cross, mutant, pop)
        trial_fit = f(trial)
        better = trial_fit <= fit
        pop[better], fit[better] = trial[better], trial_fit[better]
