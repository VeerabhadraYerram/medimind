"""
Pathway streaming demo.
Demonstrates live ingestion of documents from the data/ directory
and reactive computation using Pathway tables.
"""


import pathway as pw

# 1. Live ingestion from folder
documents = pw.io.fs.read(
    path="./data",
    format="plaintext",
)

# 2. Sink keeps pipeline alive
pw.io.null.write(documents)

# 3. Run streaming engine
pw.run()
