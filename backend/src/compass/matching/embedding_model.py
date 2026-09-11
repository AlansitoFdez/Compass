"""Which embedding model this project uses, and the shape of its output.

Deliberately free of imports, and that is the whole reason this module exists rather than
these two constants living where they are used. They were split across
`matching/embeddings.py` (the name) and `tenders/models.py` (the dimension), which meant
asking "what model is this?" pulled in the ORM, and through it `core.db`, which builds an
engine from `Settings` at import time. So a question with a one-line answer required a
fully configured environment -- which is exactly how the Docker build that bakes the model
into the image failed, with a pydantic validation error and nothing to do with Docker.

They also belong together on their own terms: the dimension is not a fact about the
`tenders` table, it is a fact about the model, and the table merely has to agree with it.
"""

# Decided in 2.4 by measuring real recall@k against a golden set -- see
# docs/phases/phase2/subphases/phase2.4.md.
EMBEDDING_MODEL_NAME = "ibm-granite/granite-embedding-278m-multilingual"

# The model's own output width, which fixes the `Vector(n)` column in `tenders.models`.
# Changing the model means migrating that column and recomputing every stored embedding,
# not editing this number.
EMBEDDING_DIMENSIONS = 768
