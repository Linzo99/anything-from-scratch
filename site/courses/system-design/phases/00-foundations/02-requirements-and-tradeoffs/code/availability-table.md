<!-- Reference: convert availability percentages to downtime budgets. -->

# Availability → Downtime Cheat-Sheet

| Availability | Per year | Per month | Per day |
|--------------|----------|-----------|---------|
| 90% ("one nine") | 36.5 days | 73 hours | 2.4 hours |
| 99% ("two nines") | 3.65 days | 7.3 hours | 14.4 min |
| 99.9% ("three nines") | 8.77 hours | 43.8 min | 1.44 min |
| 99.95% | 4.38 hours | 21.9 min | 43.2 sec |
| 99.99% ("four nines") | 52.6 min | 4.38 min | 8.6 sec |
| 99.999% ("five nines") | 5.26 min | 26.3 sec | 0.86 sec |

## Requirements checklist (ask before designing)

**Functional (what):**
- [ ] What are the core user actions? (verbs)
- [ ] Which features are explicitly OUT of scope?

**Non-functional (how well):**
- [ ] Peak QPS? Total users? DAU?
- [ ] Data volume now, and growth rate?
- [ ] Read:write ratio?
- [ ] Latency target (state as p99)?
- [ ] Availability target (how many nines)?
- [ ] Consistency: must reads see latest write, or is stale OK?
- [ ] Durability: can we ever lose data?

## The trap

Designing for 100x your real load wastes money and adds complexity that itself
causes outages. Estimate ACTUAL load, design for that + headroom, note where
you'd evolve. Under-specifying is bad; designing for imaginary scale is just as bad.
