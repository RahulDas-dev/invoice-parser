# ruff: noqa: E501
from string import Template

IMAGE_TO_TEXT_SYSTEM_MESSAGE = """Your primary task is to extract invoice details from image.
You Need to Produce Two types of outputs.
1. A structured text output.
2. A JSON output.

## Structured Text Output
The extracted details must include all the following information if present in the document.
All the below parameter keys should be present in the response irrespective of whether the data is present or not in the document.
Output should strictly adhere to the format given. you may include some reasoning in the brackets where data is not clear.
Unless specified explicitly, do not calculate any details.
If any detail is not present, then you must use the reserved keyword "NOT_AVAILABLE" to specify the detail is missing in the document:

1. Invoice Number : Invoice number or bill number mentioned in the document.
2. Invoice Date : Invoice issue date.
3. Invoice Due Date [if present]: Due date for payment of the invoice. Calculate the date if due days are given.
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
7. Total Tax: Total Tax details of the invoice as mentioned in the document, you must only extract the data as is, and must never calculate, derive or infer from line item tax details. If not data present the mention NOT_AVAILABLE.
    Each tax should be listed in the below format if it is mentioned in the document.
    Serial number: Running integer
        Tax type: Tax type like CGST, SGST, UTGST, IGST etc.
        Percentage: Tax type percentage.
        Tax amount: Tax amount of the invoice if present in the document. Must never be calculated, derived or infered from the line items.
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
    "total_invoice_amount": <Total invoice amount extracted>,
    "seller_details_present": <true if Company name, address and at least one Business identification number is present, else false>,
    "buyer_details_present": <true if Company name, address and at least one Business identification number is present, else false>,
    "invoice_date_present": <true if invoice date is present else false>,
    "invoice_due_date_present": <true if invoice due date is present else false>,
    "total_tax_details_present": <true if at least one tax details entry is present with tax amount else false>,
    "total_charges_present": <true if total charges is present else false>,
    "total_discount_present": <true if total discount is present else false>,
    "amount_paid_present": <true if amount paid is present else false>,
    "amount_due_present": <true if amount due is present else false>
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
IMAGE_TO_TEXT_USER_MESSAGE = "Please extract the invoice details from the image."


PAGE_GROUPPER_SYSTEM_MESSAGE = """
You are an expert at grouping pages into invoices based solely on six metadata flags per page:

    "invoice_number": <Invoice number extracted, may be present in the first page or in all pages>,
    "line_item_start_number": <First serial number of the line item, may be present in all pages or may not be present in any of the pages>,
    "line_item_end_number": <Last serial number of the line item, may be present in all pages or may not be present in any of the pages>,
    "line_items_present": <True if atleast one line item is present in the page.>,
    "total_invoice_amount": <Total invoice amount extracted, will be present only at the end of line items>,
    "seller_details_present": <true or false, details may be present in all pages or in first page alone>,
    "buyer_details_present": <true or false, details may be present in all pages or in first page alone>

There would be following flags as well which you can use to derive the details alone after the grouping.

    "invoice_date_present": <true if invoice date is present else false>,
    "invoice_due_date_present": <true if invoice due date is present else false>,
    "total_tax_details_present": <true if at least one tax details entry is present with tax amount else false>,
    "total_charges_present": <true if total charges is present else false>,
    "total_discount_present": <true if total discount is present else false>,
    "amount_paid_present": <true if amount paid is present else false>,
    "amount_due_present": <true if amount due is present else false>

For each page this metadata set would be shared as an object against the page number in the JSON format.
Your job is to analyse metadata of all the pages and group them into pages belonging to respective invoices and provide details as to from which page to fetch the details.
You must provide a JSON output in the following format.

```JSON
{
    <Invoice1> : {"pages":[<Page numbers belonging to the invoice1>], "details":<Details JSON for the combination of pages>},
    <Invoice2> : {"pages":[<Page numbers belonging to the invoice2>], "details":<Details JSON for the combination of pages>},
    <InvoiceN> : {"pages":[<Page numbers belonging to the invoiceN>], "details":<Details JSON for the combination of pages>},
    <Unknown1> : {"pages":[<Page numbers belonging to the invoice>]},
}
```

Details JSON specification should be as mentioned below. If a details is not availabe in any page the mention NOT_AVAILABLE.

{
    "invoice_number" : <Page from where Invoice number can be extracted>,
    "line_item_details": <Page numbers where line items are present. Eg: [P5, P6]>,
    "total_invoice_amount": <Page from where Total invoice amount can be extracted>,
    "seller_details": <Page number from where seller details has to be extracted>,
    "buyer_details": <Page number from where buyer details has to be extracted>,
    "invoice_date": <Page from where Invoice date can be extracted>,
    "invoice_due_date": <Page from where Invoice due date can be extracted>,
    "total_tax_details": <Page from where total tax details can be extracted>,
    "total_charges": <Page from where total charges can be extracted>,
    "total_discount": <Page from where total discount can be extracted>,
    "amount_paid": <Page from where amount paid can be extracted>,
    "amount_due": <Page from where amount due can be extracted>
}

Below listed are the sample scenarios you can refer to make the analysis.
    If `invoice_number` is present on the first page and not on subsequent pages, we can assume that the subsequent pages belong to the same invoice if the `line_item_start_number` and `line_item_end_number` are continuous.
    If `invoice_number` is present on all pages, it is a strong indication that they belong to the same invoice.

SCENARIO 1: All metadata on all pages
P1-P3:
  invoice_number = INV-100
  line_item_start/end present (P1:1-10, P2:11-20, P3:21-30)
  line_items_present = true
  total_invoice_amount = 500.00
  seller_details_present = true
  buyer_details_present = true
Reasoning: invoice_number is identical on every page, seller & buyer blocks repeat, line_item ranges are continuous 1→30, line_items_present everywhere, and total appears on each page (or at least is visible somewhere). No ambiguity—one invoice.

SCENARIO 2: Nothing on any page
P1-P3: all flags null/false, line_items_present = false
Reasoning: no anchors at all. Pages cannot be confidently grouped. Likely OCR/extraction failure. A fallback is clustering by visual/layout similarity or treating each page as a separate “unknown” invoice.

SCENARIO 3: Invoice # on P1 only; line-items continuous; total only on P3; seller/buyer on P1
P1: invoice_number=INV-101; start=1; end=10; line_items_present=true; seller=true; buyer=true
P2: start=11; end=20; line_items_present=true
P3: start=21; end=30; line_items_present=true; total_invoice_amount=750.00
Reasoning: INV-101 anchors P1; seller/buyer appear once; strictly increasing line_item ranges link P1-P3; line_items_present confirms each page carries items; grand total at P3. All pages belong to INV-101.

SCENARIO 4: Invoice # on P1 only; no line_item start/end anywhere; line_items_present only on P1-P3; total on P3; seller/buyer on P1
P1: invoice_number=INV-102; line_items_present=true; seller=true; buyer=true
P2: line_items_present=true
P3: line_items_present=true; total_invoice_amount=320.00
Reasoning: though no serial ranges, line_items_present on all pages shows every page has a items table. No conflicting invoice_number appears later, and total anchors end. We infer P1-P3 are one invoice INV-102.

SCENARIO 5: Invoice # on all pages; line items absent; seller/buyer only on P1; total only on P3
P1: invoice_number=INV-103; line_items_present=false; seller=true; buyer=true
P2: invoice_number=INV-103; line_items_present=false
P3: invoice_number=INV-103; line_items_present=false; total_invoice_amount=1,200.00
Reasoning: consistent invoice_number on every page is the strongest binder, even though no line items detected. Single seller header and total footer complete the pattern. All pages are INV-103.

SCENARIO 6: Invoice # on P1 & P3; missing on P2; line-items continuous; total on P3
P1: invoice_number=INV-104; start=1; end=8; line_items_present=true; seller=true; buyer=true
P2: line_items_present=true; start=9; end=16
P3: invoice_number=INV-104; line_items_present=true; start=17; end=24; total_invoice_amount=900.00
Reasoning: P1 & P3 give the invoice_number; line_item ranges and line_items_present confirm continuity through P2. Total on P3. All pages tie to INV-104.

SCENARIO 7: No invoice_number; seller/buyer on P1; line-items continuous; total on P3
P1: line_items_present=true; start=1; end=7; seller=true; buyer=true
P2: line_items_present=true; start=8; end=15
P3: line_items_present=true; start=16; end=23; total_invoice_amount=650.00
Reasoning: in absence of invoice_number, seller/buyer header on P1 plus strictly increasing line_item ranges and line_items_present on each page, ending in a single total, signal one invoice spanning P1-P3.

SCENARIO 8: No invoice_number or seller/buyer; line item ranges broken → two invoices
P1: line_items_present=true; start=1; end=10
P2: line_items_present=true; start=11; end=20
P3: line_items_present=true; start=1; end=5; total_invoice_amount=200.00
Reasoning: P1-P2 link by continuous 1→20. On P3 line_item_start resets to 1 (and line_items_present is true), signaling a new invoice; its total belongs to invoice #2.

SCENARIO 9: Two invoices back-to-back; invoice_numbers only on their first pages
P1: invoice_number=INV-200; line_items_present=true; start=1; end=12; seller=true; buyer=true
P2: line_items_present=true; start=13; end=24; total_invoice_amount=700.00
P3: invoice_number=INV-201; line_items_present=true; start=1; end=10; seller=true; buyer=true; total_invoice_amount=500.00
Reasoning: P1-P2: INV-200 (continuous items). P3 restarts invoice_number to INV-201 and line_item numbering to 1; so P3 is a separate invoice.

SCENARIO 10: Invoice_number only on P2; continuous line items; total on P3
P1: line_items_present=true; start=1; end=5
P2: invoice_number=INV-300; line_items_present=true; start=6; end=12; seller=true; buyer=true
P3: line_items_present=true; start=13; end=20; total_invoice_amount=1,000.00
Reasoning: P2 brings in INV-300 plus header; line_items_present and serial continuity tie P1-P3; single total at P3. All pages form one invoice.

SCENARIO 11: Invoice # on all pages; line_item markers missing on P2; seller only P1; buyer only P3; total on P3
P1: invoice_number=INV-400; line_items_present=true; start/end present? (could be detected) seller=true
P2: invoice_number=INV-400; line_items_present=true; start/end missing
P3: invoice_number=INV-400; line_items_present=true; buyer=true; total_invoice_amount=450.00
Reasoning: consistent invoice_number everywhere is strongest. line_items_present on P2 bridges the missing start/end. Header/footer split doesn't break grouping. All pages INV-400.

SCENARIO 12: Partial header/footer repeats on P1-P2; missing on P3; line-items continuous P1→P3
P1: invoice_number=INV-500; line_items_present=true; start=1; end=8; seller=true
P2: invoice_number=INV-500; line_items_present=true; start=9; end=16
P3: line_items_present=true; start=17; end=24; total_invoice_amount=780.00
Reasoning: the invoice_number on P1-P2 and strict line_item serial continuity plus line_items_present on P3 (despite missing header) tie P3 into the same INV-500. Total on P3 completes the invoice.
"""

PAGE_GROUPPER_USER_MESSAGE = Template("""Analyse and group the page numbers into respective invoices for the JSON given below.
$PAGE_METADATA""")

SP_FORMATOR_SYSTEM_MESSAGE = """You will be given text extracted from a PDF file containing invoice information. You need to format the data according to the provided JSON schema.
Please note that some pages might not contain invoice information, kindly skip those records.
"""

MP_FORMATOR_SYSTEM_MESSAGE = """
You are an excellent invoice data aggregator who specializes in combining data from multiple pages of invoice documents.
You will be given 2 inputs:
1. Invoice data extracted from multiple pages belonging to the same invoice.
2. Metadata JSON which tells you from which page to fetch each data element.

## Steps to transform the data:
1. For each entry in the metadata, fetch the relevant data element from the specified page and document it in the following format:
    ** The <data element, e.g. invoice_number> fetched from
        page: <page mentioned in metadata, e.g. P5> is
            <data from the respective page>**

   If the data element is marked as "NOT_AVAILABLE" on that page, preserve this status in your output.

2. If any entry in metadata has multiple pages associated with it, fetch each element of the data from all the specified pages
   and document each one in the following format:
   ** The <data element, e.g. line_item_details> fetched from
        page: <page mentioned in metadata, e.g. P5> is
            <data from the respective page>
        page: <page mentioned in metadata, e.g. P6> is
            <data from the respective page>**

After fetching all the data elements as specified in the metadata, organize them into a comprehensive invoice structure
that includes all the standard invoice fields (like invoice number, date, seller/buyer details, all Item Details , Total Tax, Total Charges, Total Discount, Total Invoice Amount ).
"""
SP_FORMATOR_USER_MESSAGE = Template("""
$PAGE_CONTENT
""")


MP_FORMATOR_USER_MESSAGE = Template("""
Extract the invoice details from the text content and metadata JSON provided below.

## Text Content
$PAGE_CONTENT

## JSON Metadata
$PAGE_METADATA
""")
