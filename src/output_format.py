from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, PositiveInt


class TaxComponents(BaseModel):
    """
    Structured model for summarizing tax components.
    """

    Tax_Type: str = Field(
        default="NOT_AVAILABLE",
        description="Tax type like CGST, SGST, UTGST, IGST, VAT etc",
    )
    Tax_Rate: float = Field(default=0.0, description="Tax Rate in percentage")
    Tax_Amount: float = Field(default=0.0, description="Tax Amount")

    @property
    def is_empty(self) -> bool:
        return self.Tax_Type == "NOT_AVAILABLE" and self.Tax_Rate == 0.0 and self.Tax_Amount == 0.0


class Item(BaseModel):
    """
    Structured model for summarizing item details in the invoice.
    """

    slno: PositiveInt
    description: str = Field(default="NOT_AVAILABLE", description="Description of the item")
    inventory_flag: bool = Field(
        default=False,
        description="Depicts if the item is an inventory item for which inventory or stock must be updated.",
    )
    quantity: float = Field(default=0.0, description="Quantity of the item")
    UOM: str = Field(default="NOT_AVAILABLE", description="Unit of measurement")
    HSN_CODE: str = Field(
        default="NOT_AVAILABLE",
        description="HSN code of the item, sometimes called as SAC code",
    )
    price: float = Field(default=0.0, description="Price of the item")
    tax: list[TaxComponents] = Field(default_factory=list, description="List of taxes for the line item")
    discount: float = Field(default=0.0, description="Discount amount of the item")
    amount: float = Field(default=0.0, description="Amount of the item")
    currency: str = Field(default="INR", description="Currency of the price")

    @property
    def is_empty(self) -> bool:
        return self.description == "NOT_AVAILABLE" and self.quantity == "NOT_AVAILABLE" and self.price == 0.0


class BusinessIdNumber(BaseModel):
    """
    Structured model for summarizing company details.
    """

    BIN_Type: str = Field(
        default="NOT_AVAILABLE",
        description="Business identification type like GSTIN, PAN, TAN, IEC and CIN",
    )
    BIN_Number: str = Field(default="NOT_AVAILABLE", description="Respective identification number")

    @property
    def is_empty(self) -> bool:
        return self.BIN_Type == "NOT_AVAILABLE" and self.BIN_Number == "NOT_AVAILABLE"


class CompanyDetails(BaseModel):
    """
    Structured model for summarizing company details.
    """

    name: str = Field(default="NOT_AVAILABLE", description="Name of the company")
    BIN_Details: list[BusinessIdNumber] = Field(
        default_factory=list,
        description="List of unique business identification numbers",
    )
    address: str = Field(default="NOT_AVAILABLE", description="Address of the company")
    state: str = Field(default="NOT_AVAILABLE", description="State of the company present in address")
    country: str = Field(default="NOT_AVAILABLE", description="Country of the company present in address")
    pin_code: str = Field(
        default="NOT_AVAILABLE",
        description="6 digit Pin code of the company present in address",
    )
    phone_number: str = Field(default="NOT_AVAILABLE", description="Phone number of the company")
    email: str = Field(default="NOT_AVAILABLE", description="Email of the company")

    @property
    def is_empty(self) -> bool:
        return (
            self.name == "NOT_AVAILABLE"
            and all(item.is_empty for item in self.BIN_Details)
            and self.address == "NOT_AVAILABLE"
            and self.phone_number == "NOT_AVAILABLE"
            and self.email == "NOT_AVAILABLE"
        )

    def count_available_details(self) -> int:
        """Count the number of available (non-default) details."""
        count = 0

        # Check basic fields
        if self.name != "NOT_AVAILABLE":
            count += 1
        if self.address != "NOT_AVAILABLE":
            count += 1
        if self.state != "NOT_AVAILABLE":
            count += 1
        if self.country != "NOT_AVAILABLE":
            count += 1
        if self.pin_code != "NOT_AVAILABLE":
            count += 1
        if self.phone_number != "NOT_AVAILABLE":
            count += 1
        if self.email != "NOT_AVAILABLE":
            count += 1

        # Count non-empty BIN details - each valid BIN adds to the count
        for bin_detail in self.BIN_Details:
            if not bin_detail.is_empty:
                count += 1

        return count

    def __ge__(self, other: "CompanyDetails") -> bool:
        """Greater than or equal: self has more or equal available details than other."""
        if not isinstance(other, CompanyDetails):
            return TypeError("Can only compare with another CompanyDetails object")
        return self.count_available_details() >= other.count_available_details()

    def merge_with(self, other: "CompanyDetails") -> "CompanyDetails":
        """
        Merge this CompanyDetails with another, taking non-default values where available.
        Priority: self > other (self's values take precedence when both have data)
        """
        if not isinstance(other, CompanyDetails):
            raise TypeError("Can only merge with another CompanyDetails object")

        # Helper function to choose the best value
        def choose_best_value(self_val: str, other_val: str) -> str:
            if self_val.upper() != "NOT_AVAILABLE":
                return self_val
            if other_val.upper() != "NOT_AVAILABLE":
                return other_val
            return "NOT_AVAILABLE"

        # Merge BIN details - combine unique entries
        merged_bins = []
        all_bins = list(self.BIN_Details) + list(other.BIN_Details)

        # Use a dict to track unique BIN types and keep the best version
        bin_dict = {}
        for bin_item in all_bins:
            if not bin_item.is_empty:
                bin_type = bin_item.BIN_Type
                if bin_type not in bin_dict or bin_item in self.BIN_Details:
                    bin_dict[bin_type] = bin_item

        merged_bins = [bin_dict.values()]

        # Create merged company
        return CompanyDetails(
            name=choose_best_value(self.name, other.name),
            address=choose_best_value(self.address, other.address),
            state=choose_best_value(self.state, other.state),
            country=choose_best_value(self.country, other.country),
            pin_code=choose_best_value(self.pin_code, other.pin_code),
            phone_number=choose_best_value(self.phone_number, other.phone_number),
            email=choose_best_value(self.email, other.email),
            BIN_Details=merged_bins,
        )


class Invoice(BaseModel):
    """
    Structured model for summarizing invoice details.
    """

    invoice_number: str = Field(default="NOT_AVAILABLE", description="Invoice number")
    invoice_date: str = Field(default="NOT_AVAILABLE", description="Invoice date")
    invoice_due_date: str = Field(default="NOT_AVAILABLE", description="Invoice due date")
    seller_details: CompanyDetails = Field(
        default_factory=lambda: CompanyDetails(),
        description="Details of the seller Comapny",
    )
    buyer_details: CompanyDetails = Field(
        default_factory=lambda: CompanyDetails(),
        description="Details of the buyer Company",
    )
    items: list[Item] = Field(default_factory=list, description="List of items in the invoice")
    total_tax: list[TaxComponents] = Field(default_factory=lambda: TaxComponents(), description="Total tax components")
    total_charge: float = Field(default=0.0, description="Total charges")
    total_discount: float = Field(default=0.0, description="Total discount applied")
    total_amount: float = Field(default=0.0, description="Total amount of the invoice")
    amount_paid: float = Field(default=0.0, description="Amount paid")
    amount_due: float = Field(default=0.0, description="Amount due")
    page_no: str = Field(
        default="",
        description="Page no in string Format, E.g., '1-2' for pages 1 and 2, or '3' for page 3",
    )

    @property
    def is_empty(self) -> bool:
        return (
            self.invoice_number == "NOT_AVAILABLE"
            and self.invoice_date == "NOT_AVAILABLE"
            and self.buyer_details.is_empty
            and self.seller_details.is_empty
            and (all(item.is_empty for item in self.items) or not self.items)
            and self.total_tax.is_empty
            and self.total_charge == 0.0
            and self.total_discount == 0.0
            and self.total_amount == 0.0
            and self.amount_paid == 0.0
            and self.amount_due == 0.0
        )

    def count_available_details(self) -> int:
        """Count the number of available (non-default) details."""
        count = 0

        # Basic invoice fields
        if self.invoice_number != "NOT_AVAILABLE":
            count += 1
        if self.invoice_date != "NOT_AVAILABLE":
            count += 1
        if self.invoice_due_date != "NOT_AVAILABLE":
            count += 1

        # Company details (count their internal details)
        count += self.seller_details.count_available_details()
        count += self.buyer_details.count_available_details()

        # Items count
        count += len([item for item in self.items if not item.is_empty])

        # Tax components
        count += len([tax for tax in self.total_tax if not tax.is_empty])

        # Amount fields
        if self.total_charge != 0.0:
            count += 1
        if self.total_discount != 0.0:
            count += 1
        if self.total_amount != 0.0:
            count += 1
        if self.amount_paid != 0.0:
            count += 1
        if self.amount_due != 0.0:
            count += 1
        return count

    def merge_with(self, other: "Invoice") -> "Invoice":
        """
        Merge this Invoice with another, combining items and taking best available data.
        Amount fields: take non-zero values with priority to self
        Items: collect all unique items from both invoices
        """
        if not isinstance(other, Invoice):
            raise TypeError("Can only merge with another Invoice object")

        def choose_best_value(self_val: str, other_val: str, default: str = "NOT_AVAILABLE") -> str:
            if self_val.upper() != default.upper():
                return self_val
            if other_val.upper() != default.upper():
                return other_val
            return default

        def choose_best_amount(self_val: float, other_val: float) -> float:
            """For amount fields, prefer non-zero values with self having priority."""
            if self_val != 0.0:
                return self_val
            if other_val != 0.0:
                return other_val
            return 0.0

        # Merge items - collect all unique items by slno
        merged_items = list(self.items) + list(other.items)

        # Merge total tax components
        merged_total_tax = list(self.total_tax) + list(other.total_tax)

        # Merge page numbers
        def merge_page_numbers(page1: str, page2: str) -> str:
            if not page1 and not page2:
                return ""
            if not page1:
                return page2
            if not page2:
                return page1
            # Combine page ranges
            pages1 = page1.split("-") if page1 else []
            pages2 = page2.split("-") if page2 else []

            # Convert to integers for proper handling, then back to strings
            all_pages = sorted({p.strip() for p in pages1 + pages2})
            return "-".join(all_pages)

        # Create merged invoice
        return Invoice(
            invoice_number=choose_best_value(self.invoice_number, other.invoice_number, "NOT_AVAILABLE"),
            invoice_date=choose_best_value(self.invoice_date, other.invoice_date, "NOT_AVAILABLE"),
            invoice_due_date=choose_best_value(self.invoice_due_date, other.invoice_due_date, "NOT_AVAILABLE"),
            seller_details=self.seller_details.merge_with(other.seller_details),
            buyer_details=self.buyer_details.merge_with(other.buyer_details),
            items=merged_items,
            total_tax=merged_total_tax,
            total_charge=choose_best_amount(self.total_charge, other.total_charge),
            total_discount=choose_best_amount(self.total_discount, other.total_discount),
            total_amount=choose_best_amount(self.total_amount, other.total_amount),
            amount_paid=choose_best_amount(self.amount_paid, other.amount_paid),
            amount_due=choose_best_amount(self.amount_due, other.amount_due),
            page_no=merge_page_numbers(self.page_no, other.page_no),
        )

    def __gt__(self, other: "Invoice") -> bool:
        """Greater than: self has more available details than other."""
        if not isinstance(other, Invoice):
            return NotImplemented
        return self._count_available_details() > other._count_available_details()


class TokenDetails(BaseModel):
    """
    Structured model for summarizing token count details.
    """

    request_tokens: int | None = Field(default=None, description="Token count for request")
    response_tokens: int | None = Field(default=None, description="Token count for response")
    page_no: str = Field(default="", description="Page no")


class TokenExpenditure(BaseModel):
    """
    Structured model for summarizing token count details.
    """

    agent1_token_count: list[TokenDetails] = Field(
        default_factory=lambda: [TokenDetails()],
        description="Token Expenditure for agent 1",
    )
    agent2_token_count: list[TokenDetails] = Field(
        default_factory=lambda: [TokenDetails()],
        description="Token Expenditure for agent 2",
    )


class InvoiceData(BaseModel):
    """Structured model for summarizing invoice details from List of pages."""

    details: list[Invoice] = Field(description="Deatils of invoice present per page", default_factory=list)
    error_message: str | None = Field(default=None, description="Error message if any error occurs during processing")
    agent1_token_expenditure: list[TokenDetails] = Field(
        default_factory=list, description="Token Expenditure for agent 1"
    )
    agent2_token_expenditure: list[TokenDetails] = Field(
        default_factory=list, description="Token Expenditure for agent 2"
    )


class MergeStrategy(BaseModel):
    """
    Structured model for specifying how to merge invoices from multiple pages.

    This model provides a strategy for merging invoice data spread across multiple
    pages into a single consolidated invoice. For each field, you can specify the
    page number where the accurate data is located.

    Example usage:
    ```python
    strategy = MergeStrategy(
        pages=["1", "2", "3"],
        details=MergeDetails(
            invoice_number="1",
            line_item_details=["1", "2"],
            total_invoice_amount="3"
        )
    )
    merged_invoice = merge_invoices(invoices, strategy)
    ```
    """

    pages: list[str] = Field(default_factory=list, description="List of page numbers in the invoice")
    details: Mapping[str, Any] = Field(
        default_factory=dict,
        description="Details of which page to get each field from",
    )
