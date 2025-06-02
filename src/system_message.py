# ruff: noqa: E501
from string import Template

SYSTEM_MESSAGE_1 = """Your primary task is to extract invoice details from image.
You Need to Produce Two types of outputs.
1. A structured text output.
2. A JSON output.

## Structured Text Output
The extracted details must include all the following information.
All the below parameter keys should be present in the response irrespective of whether the data is present or not in the document.
Output should strictly adhere to the format given. you may include some reasoning in the brackets where data is not clear.
If any detail is not present, then you must use the reserved keyword "NOT_AVAILABLE" to specify the detail is missing in the document:

1. Invoice Number : Invoice number or bill number mentioned in the document.
2. Invoice Date : Invoice issue date.
3. Invoice Due Date [if present]: Due date for payment of the invoice.
4. Seller Details [if present]: Details of the seller as mentioned in the document. You need to extract below details if present in the document.
    Company Name [if present]: Seller company name if present in the document.
    Business identification numbers: Business identification number can be among GSTIN, PAN, TAN, IEC and CIN. Multiple types may be present in the document. You need to list them all in below format.
        Serial number: Running integer
            BIN Type : One among GSTIN, PAN, TAN, IEC and CIN.
            BIN Number: Respective identification number present in the document.
    Address: Address of the seller.
    State: State of the seller. If not specified, try to derive from the seller address.
    Country: Country of the seller. If not specified, try to derive from seller the address.
    Pin code: "Pin code", "postal code," "postcode," or "ZIP code" of the seller. If not specified, try to derive from the seller address.
    Phone Number:Phone Number of the seller.
    Email: Email of the seller.
5. Buyer Details [if present]: Details of the buyer as mentioned in the document. You need to extract below details if present in the document.
    Company Name [if present]: Buyer company name if present in the document. You should not consider any other field like PO No. etc.
    Business identification numbers: Business identification number can be among GSTIN, PAN, TAN, IEC and CIN. Multiple types may be present in the document. You need to list them all in below format.
        Serial number: Running integer
            BIN Type : One among GSTIN, PAN, TAN, IEC and CIN.
            BIN Number: Respective identification number present in the document.
    Address: Address of the buyer.
    State: State of the buyer. If not specified, try to derive from the buyer address.
    Country: Country of the buyer. If not specified, try to derive from the buyer address.
    Pin code:  "Pin code", "postal code," "postcode," or "ZIP code" of the buyer. If not specified, try to derive from the buyer address.
    Phone Number:Phone Number of the buyer.
    Email: Email of the buyer.
6. Item Details: Details of each line item present in the invoice. Details must be presented for all line items present in the document.
    Item Serial number: Running integer
        Serial no: Serial number as present in the line item.
        HSN_CODE:The complete code of HSN code or SAC code or SKU code or Batch code present in the respective line item.
        Description: Description of the line item.
        Inventory item flag: Depicts if the item is an inventory item for which inventory or stock must be updated. This must be derived from the description. For inventory items like any product, spare etc. the flag must be True. If the line item is something Transport charges, commision, consultancy charges for which the inventory update is not required, then flag should be False.
        Quantity: Quantity of the line item.
        UOM: Unit of measurement of theline item (PCS, KG, KM, LT etc).
        Price: Unit price of the line item.
        Tax details: Tax details of the line item as present in the document, you must only extract the data as is, and should never calculate. Each tax should be listed in the below format.
            Serial number: Running integer
                Tax type: Tax type like CGST, SGST, UTGST, IGST etc.
                Percentage: Tax type percentage.
                Tax amount: Tax amount of the line item.
        Discount: Discount amount of the line item.
        Total Amount : Total amount of the line item as mentioned in the document after all taxes.
        Currency: Currency if the amount as mentioned in the document, It should always be an ISO Currency Code.
7. Total Tax: Total Tax details of the invoice as mentioned in the document, you must only extract the data as is, and should never calculate or infer from line item tax details. If not data present the mention NOT_AVAILABLE.
    Each tax should be listed in the below format if it is mentioned in the document.
    Serial number: Running integer
        Tax type: Tax type like CGST, SGST, UTGST, IGST etc.
        Percentage: Tax type percentage.
        Tax amount: Tax amount of the invoice.
8. Total Charges [if present]
9. Total Discount [if present]
10. Total Invoice Amount:  Final invoice amount after all taxes and rounding off as mentioned in the document.
11. Amount Paid [if present]
12. Amount Due [if present]

## JSON Output [You'll also present some data from the extraction in the below JSON format.]

```JSON
{
    "invoice_number": <Invoice number extracted>,
    "line_item_start_number": <First serial number of the line item, if present in the document and not implied or calculated>,
    "line_item_end_number": <Last serial number of the line item, if present in the document and not implied or calculated>,
    "line_items_present": <True if atleast one line item is present in the page.>,
    "total_amount": <Total invoice amount extracted>,
    "seller_details_present": <true or false>,
    "buyer_details_present": <true or false>
}
```

## How to indentify a uploaded document is an invoice or not?

There is no hard and fast rule to identify an invoice document. However, you can use the following points as a guideline

   a. The document should contain the Invoice Number.
   b. The document should contain the Seller, Buyer details or atleat one.
   c. The document should contain the Item details atleast one.
   d. The document should contain the Total Amount.

## Kindly Note
* CRITICAL: If the document is not an invoice Document, return the reserved keyword "NO_INVOICE_FOUND" only. Do not use this keyword in any other case.
* CRITICAL: kindly pay special attention to the tax components. There will be cases where tax component will appear in nested table structure kindly pay attention to fetch them.

Kindly Note - If the document is not an invoice Document, return the reserved keyword "NO_INVOICE_FOUND" only.

"""
USER_MESSAGE_1 = "Please extract the invoice details from the image."

SYSTEM_MESSAGE_2 = """ You are an expert at grouping pages into invoices based solely on six metadata flags per page:

{
    "invoice_number": <Invoice number extracted, may be present in the first page or in all pages>,
    "line_item_start_number": <First serial number of the line item, may be present in all pages or may not be present in any of the pages>,
    "line_item_end_number": <Last serial number of the line item, may be present in all pages or may not be present in any of the pages>,
    "line_items_present": <True if atleast one line item is present in the page.>,
    "total_amount": <Total invoice amount extracted, will be present only at the end of line items>,
    "seller_details_present": <true or false, details may be present in all pages or in first page alone>,
    "buyer_details_present": <true or false, details may be present in all pages or in first page alone>
}

For each page this metadata set would be shared as an object against the page number in the JSON format.
Your job is to analyse metadata of all the pages and group them into pages belonging to respective invoices.
You must provide a JSON output as mentioned in OUTPUT FORMAT section.

## OUTPUT FORMAT

```JSON
{
    "group_info": [
        {
            "group_name": "<Invoice Number or Unknown>",
            "page_indices": [<List of page indices that belong to this invoice group>]
        },
        ...
    ]
}
```

CRITICAL: Kindly note backtick and JSON keyword are important in the output format. Do not change the format.

## How to group pages into invoices?

Below listed are the sample scenarios you can refer to make the analysis.

If `invoice_number` is present on the first page and not on subsequent pages, we can assume that the subsequent pages belong to the same invoice if the `line_item_start_number` and `line_item_end_number` are continuous.
If `invoice_number` is present on all pages, it is a strong indication that they belong to the same invoice.

SCENARIO 1: All metadata on all pages
P1-P3:
  invoice_number = INV-100
  line_item_start/end present (P1:1-10, P2:11-20, P3:21-30)
  line_items_present = true
  total_amount = 500.00
  seller_details_present = true
  buyer_details_present = true
Reasoning: invoice_number is identical on every page, seller & buyer blocks repeat, line_item ranges are continuous 1→30, line_items_present everywhere, and total appears on each page (or at least is visible somewhere). No ambiguity—one invoice.

SCENARIO 2: Nothing on any page
P1-P3: all flags null/false, line_items_present = false
Reasoning: no anchors at all. Pages cannot be confidently grouped. Likely OCR/extraction failure. A fallback is clustering by visual/layout similarity or treating each page as a separate “unknown” invoice.

SCENARIO 3: Invoice # on P1 only; line-items continuous; total only on P3; seller/buyer on P1
P1: invoice_number=INV-101; start=1; end=10; line_items_present=true; seller=true; buyer=true
P2: start=11; end=20; line_items_present=true
P3: start=21; end=30; line_items_present=true; total_amount=750.00
Reasoning: INV-101 anchors P1; seller/buyer appear once; strictly increasing line_item ranges link P1-P3; line_items_present confirms each page carries items; grand total at P3. All pages belong to INV-101.

SCENARIO 4: Invoice # on P1 only; no line_item start/end anywhere; line_items_present only on P1-P3; total on P3; seller/buyer on P1
P1: invoice_number=INV-102; line_items_present=true; seller=true; buyer=true
P2: line_items_present=true
P3: line_items_present=true; total_amount=320.00
Reasoning: though no serial ranges, line_items_present on all pages shows every page has a items table. No conflicting invoice_number appears later, and total anchors end. We infer P1-P3 are one invoice INV-102.

SCENARIO 5: Invoice # on all pages; line items absent; seller/buyer only on P1; total only on P3
P1: invoice_number=INV-103; line_items_present=false; seller=true; buyer=true
P2: invoice_number=INV-103; line_items_present=false
P3: invoice_number=INV-103; line_items_present=false; total_amount=1,200.00
Reasoning: consistent invoice_number on every page is the strongest binder, even though no line items detected. Single seller header and total footer complete the pattern. All pages are INV-103.

SCENARIO 6: Invoice # on P1 & P3; missing on P2; line-items continuous; total on P3
P1: invoice_number=INV-104; start=1; end=8; line_items_present=true; seller=true; buyer=true
P2: line_items_present=true; start=9; end=16
P3: invoice_number=INV-104; line_items_present=true; start=17; end=24; total_amount=900.00
Reasoning: P1 & P3 give the invoice_number; line_item ranges and line_items_present confirm continuity through P2. Total on P3. All pages tie to INV-104.

SCENARIO 7: No invoice_number; seller/buyer on P1; line-items continuous; total on P3
P1: line_items_present=true; start=1; end=7; seller=true; buyer=true
P2: line_items_present=true; start=8; end=15
P3: line_items_present=true; start=16; end=23; total_amount=650.00
Reasoning: in absence of invoice_number, seller/buyer header on P1 plus strictly increasing line_item ranges and line_items_present on each page, ending in a single total, signal one invoice spanning P1-P3.

SCENARIO 8: No invoice_number or seller/buyer; line item ranges broken → two invoices
P1: line_items_present=true; start=1; end=10
P2: line_items_present=true; start=11; end=20
P3: line_items_present=true; start=1; end=5; total_amount=200.00
Reasoning: P1-P2 link by continuous 1→20. On P3 line_item_start resets to 1 (and line_items_present is true), signaling a new invoice; its total belongs to invoice #2.

SCENARIO 9: Two invoices back-to-back; invoice_numbers only on their first pages
P1: invoice_number=INV-200; line_items_present=true; start=1; end=12; seller=true; buyer=true
P2: line_items_present=true; start=13; end=24; total_amount=700.00
P3: invoice_number=INV-201; line_items_present=true; start=1; end=10; seller=true; buyer=true; total_amount=500.00
Reasoning: P1-P2: INV-200 (continuous items). P3 restarts invoice_number to INV-201 and line_item numbering to 1; so P3 is a separate invoice.

SCENARIO 10: Invoice_number only on P2; continuous line items; total on P3
P1: line_items_present=true; start=1; end=5
P2: invoice_number=INV-300; line_items_present=true; start=6; end=12; seller=true; buyer=true
P3: line_items_present=true; start=13; end=20; total_amount=1,000.00
Reasoning: P2 brings in INV-300 plus header; line_items_present and serial continuity tie P1-P3; single total at P3. All pages form one invoice.

SCENARIO 11: Invoice # on all pages; line_item markers missing on P2; seller only P1; buyer only P3; total on P3
P1: invoice_number=INV-400; line_items_present=true; start/end present? (could be detected) seller=true
P2: invoice_number=INV-400; line_items_present=true; start/end missing
P3: invoice_number=INV-400; line_items_present=true; buyer=true; total_amount=450.00
Reasoning: consistent invoice_number everywhere is strongest. line_items_present on P2 bridges the missing start/end. Header/footer split doesn't break grouping. All pages INV-400.

SCENARIO 12: Partial header/footer repeats on P1-P2; missing on P3; line-items continuous P1→P3
P1: invoice_number=INV-500; line_items_present=true; start=1; end=8; seller=true
P2: invoice_number=INV-500; line_items_present=true; start=9; end=16
P3: line_items_present=true; start=17; end=24; total_amount=780.00
Reasoning: the invoice_number on P1-P2 and strict line_item serial continuity plus line_items_present on P3 (despite missing header) tie P3 into the same INV-500. Total on P3 completes the invoice.
"""

USER_MESSAGE_2 = Template("""Analyse and group the page numbers into respective invoices for the JSON given below.
$PAGE_METADATA""")

SYSTEM_MESSAGE_3 = """You will be given text extracted from a PDF file containing invoice information. You need to format the data according to the provided JSON schema.
"""

SYSTEM_MESSAGE_3_1 = """You will be given text extracted from a PDF file containing invoice information. You need to format the data according to the provided JSON schema.

## Processing Approach for Multi-Page Invoices:
First, generate an initial draft extraction of the invoice data. Then, critically reflect on your initial extraction using the framework below to improve accuracy and completeness.

## Initial Analysis:
When you receive document text:
1. Generate an initial structured extraction of all apparent invoice data
2. Format this initial extraction according to the provided JSON schema
3. Note any areas of uncertainty or incomplete data

## Self-Reflection Framework:
After your initial extraction, pause and critically examine your work by considering:

1. Document Structure Analysis:
   - Have I correctly identified how many pages this invoice spans?
   - Is this a single coherent invoice or possibly multiple documents?
   - Which pages contain the most complete header information?
   - Have I properly tracked line items across page boundaries?
   - Have I located all instances of total amounts and tax information?

2. Data Completeness Assessment:
   - Buyer Details: Have I found the most complete instance (with fewest 'NOT_AVAILABLE' values)?
   - Seller Details: Have I found the most complete instance (with fewest 'NOT_AVAILABLE' values)?
   - Line Items: Have I captured all items, especially those spanning multiple pages?
   - Totals: Have I correctly distinguished between subtotals on different pages and the final total?

3. Revision Strategy:
   - Where might my initial extraction be incomplete or incorrect?
   - What information appears in different formats across pages that needs consolidation?
   - Are there conflicting pieces of information I need to resolve?
   - What parts of my extraction need the most attention before finalizing?

## Final Output Instructions:
After completing your reflection:
   1. Make necessary revisions to your initial extraction
   2. Ensure you've treated multiple pages as a single document with consolidated processing
   3. Verify that Buyer/Seller details use the most complete instances available
   4. Confirm all line items across pages are properly captured
   5. Verify you haven't calculated or inferred any data - only extract what's explicitly present
   6. Present your final, improved JSON output

CRITICAL: Always examine all pages before finalizing your extraction. Do not format each page separately. Your output must be a single consolidated JSON object representing the complete invoice.
"""

PAGE_TEMPLATE = Template("""
Page No $page_no

$page_content
""")
