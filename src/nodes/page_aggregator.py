from asyncio.log import logger
from collections.abc import Mapping
from typing import Any

from config import InvoiceParserConfig
from output_format import Invoice


class PageAggregator:
    def __init__(self, config: InvoiceParserConfig):
        self.merger_strategy = config.MERGER_STRATEGY

    async def run(self, invoices: list[Invoice], merger_stratagy: Mapping[str, Any]) -> Invoice:
        """
        Process the image and return a text description.
        """
        logger.info(f"merging {len(invoices)} invoices from Pages {[inv.page_nos for inv in invoices]}")
        if self.merger_strategy == "classic":
            merged_invoice = self._classic_merge(invoices)
        elif self.merger_strategy == "smart":
            merged_invoice = self._smart_merge(invoices)
        elif self.merger_strategy == "strategy":
            merged_invoice = self._merge_with_stratagy(invoices, merger_stratagy)
        else:
            raise ValueError(f"Unknown merger strategy: {self.merger_strategy}")
        return merged_invoice

    def _classic_merge(self, invoices: list[Invoice]) -> Invoice:
        """
        Merge multiple invoice objects that belong to the same invoice number
        into a single consolidated invoice.

        Args:
            invoices: List of Invoice objects with the same invoice number
        Returns:
            A single merged Invoice object
        """
        if not invoices:
            return Invoice()

        if len(invoices) == 1:
            return invoices[0]

        merged_invoice = invoices[0]
        for invoice in invoices[1:]:
            merged_invoice = merged_invoice.merge_with(invoice)

        return merged_invoice

    def _smart_merge(self, invoices: list["Invoice"]) -> "Invoice":
        """
        Smart merge that prioritizes invoices with more complete information.
        Invoices with more details get higher priority in merging.
        """
        if not invoices:
            return Invoice()

        if len(invoices) == 1:
            return invoices[0]

        # Sort invoices by completeness (most complete first)
        sorted_invoices = sorted(invoices, key=lambda x: x.count_available_details(), reverse=True)

        # Start with the most complete invoice
        result = sorted_invoices[0]

        # Merge with others, preserving the priority of the more complete base
        for invoice in sorted_invoices[1:]:
            result = result.merge_with(invoice)

        return result

    def _merge_with_stratagy(self, invoices: list["Invoice"], merger_stratagy: Mapping[str, Any]) -> "Invoice":
        """
        Smart merge that prioritizes invoices with more complete information.
        Invoices with more details get higher priority in merging.
        """
        if not invoices:
            return Invoice()

        if len(invoices) == 1:
            return invoices[0]

        raise NotImplementedError(f"Smart merge with strategy {merger_stratagy} is not implemented yet.")
