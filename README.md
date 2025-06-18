# Agentic Invoice Parser –

This repository contains the capstone project for the **Post Graduate Program in AI & Machine Learning** – an **Agentic Workflow-based Invoice Parser** designed to extract structured data from complex Indian invoice PDFs.

## Project Overview

In real-world enterprise settings, invoices often arrive as PDF files containing **multiple invoices**, with each invoice potentially spanning **multiple pages** and including **tables, images, and varied layouts**. This project leverages an **agentic architecture** to intelligently parse, segment, and extract relevant information from such documents into a structured schema.

Built using **Pydantic-AI** and **Pydantic-Graph**, the workflow uses **Large Language Models (LLMs)** to reason through document structure and extract key fields in a reliable, modular fashion.

## Here is The [workflow](Invoice_parser.drawio.svg)

![workflow](Invoice_parser.drawio.svg)

---

## Features
- **Very Minimum Cost Per page**: < 50 paisa /per page
- **Multi-invoice PDF support**: Automatically detects and segments individual invoices from a single PDF.
- **Multi-page invoice parsing**: Handles invoices that span across several pages.
- **Agentic workflow**: Implements modular agent steps using Pydantic-AI and Pydantic-Graph.
- **Structured output**: Extracted data is validated and output using a well-defined Pydantic schema.
- **Table & key-value extraction**: Supports varied layouts including tables, text blocks, and image-embedded sections.
---
##### Working on Observability


## Tech Stack

- **Python**
- **Pydantic / Pydantic-AI**
- **Pydantic-Graph**
- **LLMs** (llama 4/ openai)
- **pypdfium2** - (PDF to Images)
- **Pydantic-settings** - (Config Management)
- **Project Management** uv

---

## How to Run

1. **Install Dependencies**
```
   uv sync --frozen --no-dev
```

2. **Run the Parser**
```
    uv run main.py path/to/the/invoice.pdf
```


## The Invoice JSON [Schema](./schema.json)


