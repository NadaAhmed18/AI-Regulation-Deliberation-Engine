# Week 1 — Knowledge Infrastructure

## RAG Foundation

## 1. Overview

This week you will build the **knowledge infrastructure** that will power the AI agents developed in the following weeks.

The goal is to build a complete pipeline that can:

1. Collect information from a chosen domain.
2. Clean and preprocess the collected information.
3. Split documents into meaningful chunks.
4. Convert those chunks into vector embeddings.
5. Store the embeddings and associated metadata in PostgreSQL.
6. Retrieve relevant information in response to a natural-language query.
7. Evaluate the quality of the retrieval system quantitatively.

By the end of the week, you should have a working Retrieval-Augmented Generation (**RAG**) foundation that can provide relevant, grounded context to the agents developed in Week 2.

---

# 2. Why This Matters

The systems built in later weeks depend on this knowledge layer.

Week 2 agents will use your retrieval system as a source of factual context when forming their initial opinions.

Week 3 discussions will continue to use the retrieval system to obtain supporting evidence during discussions.

Week 4 will use the outputs of the discussion engine and the quality of the underlying knowledge infrastructure will directly affect the usefulness of the resulting analytics.

A weak retrieval system means that downstream agents may reason about incomplete, irrelevant, or poorly grounded information.

Your goal is therefore not simply to "make a vector database work."

You are building the **knowledge foundation for the entire platform**.

---

# 3. The Problem

Choose a domain or topic that will serve as the knowledge domain for the project.

Examples could include:

* A scientific field
* A technological topic
* A social or economic topic
* A policy area
* A research domain
* Another well-defined topic approved by the program

You will then construct a knowledge pipeline around that domain.

Your pipeline should transform:

```text
Web / External Sources
        │
        ▼
Raw Documents
        │
        ▼
Clean Documents
        │
        ▼
Chunks + Metadata
        │
        ▼
Embeddings
        │
        ▼
PostgreSQL + Vector Storage
        │
        ▼
Retrieval
        │
        ▼
Ranked Relevant Context
```

The exact implementation is up to you.

---

# 4. What You Need to Build

Your implementation must contain the following capabilities:

### 4.1 Data collection

Build a repeatable process for collecting documents related to your chosen domain.

### 4.2 Data cleaning

Remove irrelevant markup and noise from the collected documents.

### 4.3 Chunking

Choose and implement a chunking strategy appropriate for your documents and embedding model.

### 4.4 Embedding generation

Choose an embedding model and convert your chunks into vector representations.

### 4.5 Vector storage

Store the vectors together with the corresponding text and metadata in PostgreSQL.

### 4.6 Retrieval

Build a retrieval interface that accepts a natural-language query and returns ranked relevant chunks.

### 4.7 Evaluation

Create a small evaluation dataset and quantitatively evaluate your retrieval system.

---

# 5. Requirements

## 5.1 Build a Web Scraping / Data Collection Pipeline

Create a script, service, or pipeline that collects raw documents related to your chosen domain.

### Requirements

Your collection process must:

* Accept a set of seed URLs, search queries, or another clearly documented source-selection mechanism.
* Fetch relevant pages or articles.
* Save the collected documents locally.
* Be repeatable and re-runnable.
* Preserve enough metadata to identify where each document came from.

The collection process is the **data-entry point for the entire project**, so it should not depend on manually copying and pasting documents.

### Minimum acceptance criterion

Running your collection process should produce **at least 50 raw documents** for your chosen domain.

The documents should be stored in a clearly identifiable raw-data location.

### Things you need to decide

You are responsible for choosing:

* Which sources to collect.
* How sources are discovered.
* Which scraping/crawling approach to use.
* How raw documents are represented.
* Which metadata should be preserved.

Document the important decisions you make.

---

# 6. Clean and Preprocess the Data

Raw web pages usually contain information that is not useful for retrieval, such as:

* HTML markup
* Navigation elements
* Advertisements
* Scripts
* Styling information
* Boilerplate
* Repeated page elements

Build a preprocessing stage that converts the collected documents into useful textual content.

### Requirements

Your cleaning process should:

* Remove HTML/markup where appropriate.
* Remove navigation and other obvious boilerplate.
* Remove script/style content.
* Normalize whitespace and encoding where necessary.
* Preserve the substantive content of the original document.
* Preserve enough metadata to trace cleaned content back to its source.

### Minimum acceptance criterion

Perform a manual spot-check of **at least five cleaned documents**.

The checked documents should not contain obvious:

* HTML tags
* Script/style content
* Navigation boilerplate

Document any important cleaning assumptions or limitations.

---

# 7. Choose and Implement a Chunking Strategy

Documents need to be divided into smaller units before they can be effectively embedded and retrieved.

You must choose a chunking strategy appropriate for your domain.

Possible approaches include, but are not limited to:

* Fixed-size chunking
* Sentence-based chunking
* Recursive chunking
* Semantic chunking
* Structure-aware chunking

You are **not required to use one of these approaches specifically**.

The important requirement is that you make a reasoned choice.

### Your chunking strategy should consider

* Document structure
* Typical document length
* Embedding model context limitations
* Preservation of context
* Retrieval quality
* Chunk size
* Chunk overlap, if applicable

### Requirements

Your pipeline must:

* Split cleaned documents into retrievable chunks.
* Associate each chunk with its source document.
* Preserve useful metadata such as document ID and position.
* Produce chunks that are meaningful when retrieved independently.

### Acceptance criteria

Your documentation must explain:

1. Which chunking strategy you selected.
2. Why you selected it.
3. Important parameters such as chunk size or overlap, where applicable.
4. Any trade-offs you considered.

Every generated chunk should remain within the size limits appropriate for your selected embedding model.

---

# 8. Choose and Implement an Embedding Model

Select an embedding model appropriate for your project.

You may use:

* An open-source embedding model.
* An API-based embedding model.
* Another appropriate embedding solution.

Your choice should consider factors such as:

* Retrieval quality
* Domain suitability
* Embedding dimensionality
* Cost
* Latency
* Availability
* Hardware requirements

### Requirements

Your system must:

* Generate an embedding for every chunk.
* Associate each embedding with its chunk.
* Use a consistent embedding model throughout the dataset.
* Document the selected model and its vector dimensionality.

### Acceptance criteria

The number of generated embeddings must match the number of chunks being indexed.

Your README or documentation must state:

```text
Embedding model:
Vector dimensionality:
Reason for selection:
```

---

# 9. Store the Knowledge Base in PostgreSQL

PostgreSQL must be used as the vector database for this project.

A vector extension such as **pgvector** is recommended.

Your database should store, at minimum:

* Chunk text
* Chunk embedding
* Source/document identifier
* Relevant metadata

The exact schema is your responsibility.

### Requirements

You must:

1. Configure PostgreSQL for vector storage.
2. Create an appropriate database schema.
3. Insert the generated chunks and embeddings.
4. Preserve the metadata required for retrieval and source tracing.

### Acceptance criteria

You should be able to demonstrate that:

* PostgreSQL is running.
* The required vector functionality is enabled.
* Your schema can store the embeddings.
* The number of stored chunks corresponds to the number of indexed chunks.

A database query should be sufficient to verify that the vector extension and schema are correctly configured.

---

# 10. Choose and Implement a Retrieval Strategy

Your system must provide a retrieval mechanism that accepts a natural-language query and returns relevant chunks.

You may choose the retrieval approach that you believe best fits your domain.

Possible approaches include:

* Basic vector RAG
* Re-ranked RAG
* Hybrid search
* Graph-based retrieval
* Another defensible retrieval strategy

You are expected to **justify your choice**.

### Requirements

A retrieval request should contain:

```text
Natural-language query
```

The retrieval system should return a ranked set of relevant results.

Each result should contain enough information to identify and understand the retrieved content, including at minimum:

```text
Chunk text
Source
Relevance / similarity information
```

The exact API design is up to you.

For example, you may expose retrieval through:

* A Python function
* An HTTP endpoint
* A command-line interface
* Another clearly documented interface

### Acceptance criteria

A sample query must produce a valid ranked result containing relevant chunks.

Your documentation must explain:

1. Which retrieval strategy you selected.
2. Why it was appropriate for your domain.
3. Any important retrieval parameters.
4. Any limitations you identified.

---

# 11. Evaluate the RAG System

A working retrieval system is not enough.

You must evaluate whether it actually retrieves useful information.

Create a small evaluation set containing representative questions or queries from your chosen domain.

### Minimum requirements

Create at least **five representative test queries**.

For each query, define what information or sources would be considered relevant.

You may use an established evaluation framework such as **RAGAS**, or another defensible evaluation approach.

You may also use manually prepared relevance information together with appropriate retrieval metrics such as precision or recall.

The important requirement is that the evaluation is **quantitative**, rather than relying only on visual inspection.

### Your evaluation should answer questions such as

* Does the system retrieve relevant information?
* Are the most relevant chunks appearing near the top?
* Are there systematic retrieval failures?
* Which types of queries perform poorly?
* What could be improved?

### Acceptance criteria

Your evaluation must:

* Contain at least five representative queries.
* Define expected relevant information/sources.
* Produce at least one quantitative retrieval metric for each test query.
* Record the results.
* Include a short interpretation of the results.

Store the evaluation results in your documentation.

---

# 12. Design Freedom

One of the main goals of this week is to practice making engineering decisions.

You are **not expected to follow a predetermined implementation architecture**.

You are responsible for choosing:

### Data collection

* Scraping/crawling tools
* Source discovery approach
* Document format
* Metadata

### Preprocessing

* Cleaning approach
* Normalization strategy
* Handling of malformed documents

### Chunking

* Chunking method
* Chunk size
* Overlap
* Metadata

### Embeddings

* Embedding model
* Local vs. API-based generation

### Database

* Schema
* Index configuration
* Metadata representation

### Retrieval

* Retrieval strategy
* Number of retrieved chunks
* Ranking/re-ranking approach
* Query processing

### Evaluation

* Evaluation framework
* Metrics
* Test-query construction

You should be prepared to explain and defend these decisions.

---

# 13. Constraints

The following constraints apply:

### Required

* PostgreSQL must be used as the vector database.
* The system must support vector-based retrieval.
* The data collection process must be repeatable.
* At least 50 raw documents must be collected.
* At least 5 evaluation queries must be created.
* Retrieval quality must be evaluated quantitatively.
* The final system must expose a usable retrieval interface.

### Not prescribed

The following are intentionally left open:

* Programming language, unless constrained by the program environment.
* Scraping library.
* Embedding model.
* Chunking algorithm.
* RAG architecture.
* Retrieval framework.
* API framework.
* Internal folder structure.

If you choose a technology that introduces additional infrastructure or cost, document that decision.

---

# 14. Suggested Repository Structure

The repository intentionally contains only minimal scaffolding.

A possible structure is:

```text
.
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
│
├── data/
│   └── .gitkeep
│
├── docs/
│   └── .gitkeep
│
├── src/
│   └── .gitkeep
│
└── tests/
    └── .gitkeep
```

This structure is **only a starting point**.

You are free to reorganize it as your implementation grows.

For example, you may introduce additional directories for:

* ingestion
* preprocessing
* embeddings
* retrieval
* database access
* evaluation
* configuration
* experiments

The quality of your architecture and the reasoning behind it matter more than following a particular folder structure.

---

# 15. Environment and Configuration

Do not commit API keys, passwords, or other secrets to the repository.

Use environment variables or another appropriate configuration mechanism.

Your repository should include an example configuration file such as:

```text
.env.example
```

with placeholder values rather than real credentials.

If your implementation requires services such as PostgreSQL, document how they should be started.

---

# 16. Documentation Requirements

Your repository must contain enough documentation for another engineer to understand and reproduce your system.

At minimum, your documentation must cover:

## Overview

A short explanation of:

* The selected domain.
* What you built.
* The overall pipeline.

## Setup

Explain:

* Required software.
* Dependencies.
* Required services.
* Environment variables.
* Installation steps.

## Running the Pipeline

Explain how to:

1. Collect data.
2. Clean/process the data.
3. Generate chunks.
4. Generate embeddings.
5. Populate the database.
6. Run retrieval.
7. Run evaluation.

The exact commands depend on your implementation.

## Design Decisions

Document important decisions including:

* Data collection strategy
* Cleaning strategy
* Chunking strategy
* Embedding model
* Vector database configuration
* Retrieval strategy
* Evaluation methodology

For each major decision, briefly explain **why** you selected it.

## Evaluation

Document:

* Test queries
* Evaluation methodology
* Metrics
* Results
* Interpretation
* Known weaknesses

---

# 17. Acceptance Criteria

The week is considered complete when all of the following are satisfied.

### Data collection

* [ ] A repeatable data collection pipeline exists.
* [ ] At least 50 raw documents have been collected.
* [ ] Source information is preserved.

### Cleaning

* [ ] Raw documents are converted into usable text.
* [ ] HTML/markup and obvious boilerplate have been removed.
* [ ] At least five documents have been manually spot-checked.

### Chunking

* [ ] A chunking strategy has been selected.
* [ ] The strategy is documented and justified.
* [ ] Documents are split into retrievable chunks.
* [ ] Chunks contain source metadata.

### Embeddings

* [ ] An embedding model has been selected.
* [ ] The model choice is documented.
* [ ] Every chunk has a corresponding embedding.
* [ ] The vector dimensionality is documented.

### PostgreSQL

* [ ] PostgreSQL is configured for vector storage.
* [ ] A suitable schema exists.
* [ ] Chunks and embeddings are stored.
* [ ] Stored data can be queried successfully.

### Retrieval

* [ ] A retrieval interface exists.
* [ ] It accepts a natural-language query.
* [ ] It returns ranked relevant chunks.
* [ ] Results contain source information.
* [ ] The retrieval strategy is documented.

### Evaluation

* [ ] At least five representative queries exist.
* [ ] Relevant sources/information are defined.
* [ ] A quantitative evaluation is performed.
* [ ] At least one quantitative metric is recorded for each test query.
* [ ] Results and observations are documented.

### Reproducibility

* [ ] Another developer can understand how to set up the system.
* [ ] Another developer can reproduce the retrieval demonstration.
* [ ] Dependencies and required services are documented.
* [ ] No secrets are committed to the repository.

---

# 18. Final Deliverables

At the end of the week, your repository should contain:

### 1. Working knowledge pipeline

A complete pipeline from data collection through retrieval.

### 2. Populated vector database

PostgreSQL containing your chunks, embeddings, and metadata.

### 3. Retrieval interface

A documented interface capable of returning relevant chunks for a natural-language query.

### 4. Evaluation

A quantitative evaluation of retrieval quality using at least five representative queries.

### 5. Documentation

Documentation explaining your architecture, setup, design decisions, and evaluation results.

### 6. Demonstration

A reproducible demonstration showing that a query can be submitted and relevant knowledge can be retrieved.

---

# 19. Reviewer Reproduction

Your README must contain a clear set of commands that a reviewer can follow to reproduce the core demonstration.

The reviewer should be able to determine:

1. How to install the dependencies.
2. How to start PostgreSQL.
3. How to initialize the database.
4. How to run the data pipeline.
5. How to run retrieval.
6. How to run the evaluation.

For example:

```bash
# Install dependencies
...

# Start required services
...

# Run the data pipeline
...

# Run retrieval
...

# Run evaluation
...
```

Replace the placeholders with the actual commands for your implementation.

A reviewer should **not need to inspect your source code to figure out how to run the project**.

---

# 20. Pull Request Submission

Submit your completed work according to the program's shared repository workflow.

Your Pull Request should clearly communicate:

### What you implemented

Briefly describe the completed pipeline.

### What decisions you made

Mention important architectural or technology choices.

### What was evaluated

Summarize your evaluation methodology and results.

### Known limitations

Be honest about limitations, failures, or areas that could be improved.

### Reproduction instructions

Provide the exact commands needed for the reviewer to reproduce the core demonstration.

A useful PR description should allow a reviewer to understand the implementation without reading the entire codebase first.

---

# 21. Learning Resources

The following resources are recommended for this week.

## Required

### 1. Web Scraping Pipeline for RAG: Clean Data for LLMs

https://alterlab.io/blog/web-scraping-pipeline-for-rag-clean-data-for-llms

**Estimated time:** 25 minutes

Useful for:

* Data collection
* Cleaning
* Preparing web content for RAG

---

### 2. RAG from Scratch — TypeScript/Python

https://www.channel.tel/blog/rag-from-scratch-retrieval-augmented-generation-typescript-python

**Estimated time:** 40 minutes

Useful for:

* Understanding an end-to-end RAG pipeline
* Retrieval implementation

---

### 3. Chunking Strategies Guide

https://www.pinecone.io/learn/chunking-strategies/

**Estimated time:** 20 minutes

Useful for:

* Understanding chunking trade-offs
* Selecting a chunking strategy

---

### 4. PostgreSQL as a Vector Database — pgvector

https://www.tigerdata.com/blog/postgresql-as-a-vector-database-using-pgvector

**Estimated time:** 25 minutes

Useful for:

* PostgreSQL vector storage
* pgvector
* Vector database concepts

---

### 5. pgvector with LlamaIndex

https://rivestack.io/blog/pgvector-llamaindex

**Estimated time:** 30 minutes

Useful for:

* Integrating pgvector with retrieval frameworks

---

### 6. RAGAS Evaluation Tutorial

https://www.youtube.com/watch?v=-69Fx8F9ma4

**Estimated time:** 30 minutes

Useful for:

* RAG evaluation
* Quantitative retrieval assessment

---

## Optional

### AI-Ready Data with Crawl4AI

https://floredata.com/blog/ai-ready-data-with-crawl4ai/

Useful if you want to explore an AI-oriented crawling approach.

### RAG Pipeline Tutorial

https://www.youtube.com/watch?v=MykcjWPJ6T4

Useful as an additional end-to-end RAG walkthrough.

### Intro to RAG and Embeddings — Arabic

https://www.youtube.com/watch?v=T4iKsOpFsKM

Useful for additional introductory material on embeddings and RAG.

### Evaluate and Optimize RAG with TruLens

https://www.youtube.com/watch?v=ul5huLywzZk

An alternative evaluation framework to RAGAS.

### GraphRAG Explained — Arabic

https://www.youtube.com/watch?v=JTVx6i6MzVw

Only relevant if you choose to explore Graph RAG.

---

# 22. Handoff to Week 2

Your Week 1 implementation will become infrastructure for the agent framework in Week 2.

The most important handoff is therefore the **retrieval interface**.

Week 2 should be able to use your system to submit a natural-language query and receive relevant, source-attributed context without needing to understand the internals of your ingestion or embedding pipeline.

Document this interface clearly.

At minimum, explain:

```text
Input:
    What does the retrieval system accept?

Output:
    What does it return?

How is it accessed?
    Function / API / CLI / other

Example:
    Example request

    Example response
```

The Week 2 agents will depend on this interface to ground their reasoning.

---

# 23. Engineering Mindset

There is intentionally no single "correct" implementation for this week.

Two teams may make different choices and both produce strong solutions.

What matters is that your implementation is:

* Functional
* Reproducible
* Measurable
* Well documented
* Appropriate for the selected domain
* Reasonably maintainable
* Able to provide useful retrieval results

Do not optimize for checking boxes alone.

You should be able to answer:

> **Why did you build the system this way?**

and

> **How do you know that your retrieval system actually works?**

Those questions are just as important as getting the code to run.

---

# 24. Definition of Done

You are done when you can demonstrate the following end-to-end flow:

```text
Chosen Domain
      │
      ▼
Collect ≥ 50 Documents
      │
      ▼
Clean & Preprocess
      │
      ▼
Chunk Documents
      │
      ▼
Generate Embeddings
      │
      ▼
Store in PostgreSQL
      │
      ▼
Submit Natural-Language Query
      │
      ▼
Retrieve Ranked Chunks
      │
      ▼
Evaluate Retrieval Quality
      │
      ▼
Document Results & Decisions
```

The final system should provide a reliable knowledge foundation that can be consumed by the AI agents in **Week 2**.
