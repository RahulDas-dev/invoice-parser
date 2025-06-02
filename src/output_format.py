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
        return (
            self.Tax_Type == "NOT_AVAILABLE"
            and self.Tax_Rate == 0.0
            and self.Tax_Amount == 0.0
        )


class Item(BaseModel):
    """
    Structured model for summarizing item details in the invoice.
    """

    slno: PositiveInt
    description: str = Field(
        default="NOT_AVAILABLE", description="Description of the item"
    )
    inventory_flag: bool = Field(
        default=False,
        description="Depicts if the item is an inventory item for which inventory or stock must be updated.",
    )
    quantity: float = Field(default="NOT_AVAILABLE", description="Quantity of the item")
    UOM: str = Field(default="NOT_AVAILABLE", description="Unit of measurement")
    HSN_CODE: str = Field(
        default="NOT_AVAILABLE",
        description="HSN code of the item, sometimes called as SAC code",
    )
    price: float = Field(default="NOT_AVAILABLE", description="Price of the item")
    tax: list[TaxComponents] = Field(
        default_factory=list, description="List of taxes for the line item"
    )
    discount: float = Field(default=0.0, description="Discount amount of the item")
    amount: float = Field(default=0.0, description="Amount of the item")
    currency: str = Field(default="INR", description="Currency of the price")

    @property
    def is_empty(self) -> bool:
        return (
            self.description == "NOT_AVAILABLE"
            and self.quantity == "NOT_AVAILABLE"
            and self.price == "NOT_AVAILABLE"
        )


class BusinessIdNumber(BaseModel):
    """
    Structured model for summarizing company details.
    """

    BIN_Type: str = Field(
        default="NOT_AVAILABLE",
        description="Business identification type like GSTIN, PAN, TAN, IEC and CIN",
    )
    BIN_Number: str = Field(
        default="NOT_AVAILABLE", description="Respective identification number"
    )


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
    state: str = Field(
        default="NOT_AVAILABLE", description="State of the company present in address"
    )
    country: str = Field(
        default="NOT_AVAILABLE", description="Country of the company present in address"
    )
    pin_code: str = Field(
        default="NOT_AVAILABLE",
        description="6 digit Pin code of the company present in address",
    )
    phone_number: str = Field(
        default="NOT_AVAILABLE", description="Phone number of the company"
    )
    email: str = Field(default="NOT_AVAILABLE", description="Email of the company")

    @property
    def is_empty(self) -> bool:
        return (
            self.name == "NOT_AVAILABLE"
            and self.address == "NOT_AVAILABLE"
            and self.phone_number == "NOT_AVAILABLE"
            and self.email == "NOT_AVAILABLE"
        )


class Invoice(BaseModel):
    """
    Structured model for summarizing invoice details.
    """

    invoice_number: str = Field(default="NOT_AVAILABLE", description="Invoice number")
    invoice_date: str = Field(default="NOT_AVAILABLE", description="Invoice date")
    invoice_due_date: str = Field(
        default="NOT_AVAILABLE", description="Invoice due date"
    )
    seller_details: CompanyDetails = Field(
        default_factory=lambda: CompanyDetails(),
        description="Details of the seller Comapny",
    )
    buyer_details: CompanyDetails = Field(
        default_factory=lambda: CompanyDetails(),
        description="Details of the buyer Company",
    )
    items: list[Item] = Field(
        default_factory=list, description="List of items in the invoice"
    )
    total_tax: list[TaxComponents] = Field(
        default_factory=lambda: TaxComponents(), description="Total tax components"
    )
    total_charge: float = Field(default=0.0, description="Total charges")
    total_discount: float = Field(default=0.0, description="Total discount applied")
    total_amount: float = Field(default=0.0, description="Total amount of the invoice")
    amount_paid: float = Field(default=0.0, description="Amount paid")
    amount_due: float = Field(default=0.0, description="Amount due")
    page_no: str = Field(
        default="",
        description="Page no in string Format, Where the Information Available if processing multiple pages 1 to 5 then it will be '1-5' or '1' if only one page",
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


class TokenDetails(BaseModel):
    """
    Structured model for summarizing token count details.
    """

    request_tokens: int | None = Field(
        default=None, description="Token count for request"
    )
    response_tokens: int | None = Field(
        default=None, description="Token count for response"
    )
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

    details: list[Invoice] = Field(
        description="Deatils of invoice present per page", default_factory=list
    )
    error_message: str | None = Field(
        default=None, description="Error message if any error occurs during processing"
    )
    agent1_token_expenditure: list[TokenDetails] = Field(
        default_factory=list, description="Token Expenditure for agent 1"
    )
    agent2_token_expenditure: list[TokenDetails] = Field(
        default_factory=list, description="Token Expenditure for agent 2"
    )
