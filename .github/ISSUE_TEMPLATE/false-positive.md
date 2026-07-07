---
name: False positive (exact flagged something that isn't a magic constant)
about: exact reported a match that is not actually a hand-typed exact constant
title: "[false-positive] "
labels: false-positive
---

**What exact reported**
```
<!-- paste the exact output, including the confidence/surplus line -->
```

**The literal in context**
```python
<!-- a few lines around the flagged number, so the intent is clear -->
```

**Why it's not a magic constant**
<!-- e.g. it's an empirical fit coefficient, a measured value, an arbitrary
     threshold, a coincidental rational in test data... -->

**Environment**
- exact version / commit:
- Python version:
- OS:

**Reproduce**
<!-- Ideally a minimal snippet: the smallest file that still triggers it. -->
```python

```
