Turn the description below into a benchmark problem for a black-box optimization
platform. If an image is attached it shows the formula; follow it exactly.

Produce:
- `source`: Python that defines `f(X)`. X is a NumPy array of shape (n, dim); return n
  values to be MINIMISED. Use only NumPy (imported as np inside the source). The
  function must work for every dimension listed in `dims`, be deterministic, and return
  finite values everywhere in the box. Handle constraints with a penalty added to the
  objective and say how in the description.
- `lower`, `upper`: one number each; the search box is the same in every variable.
- `dims`: the dimensions to offer (each at least 2, at most three of them).
- `name`, a one-line `summary`, and a plain-language `description` for participants.
  The description must explain the behaviour of the landscape WITHOUT revealing the
  formula.
- `level`: Easy, Medium or Hard. `tags`: up to four short keywords.

Description from the author:
$text
