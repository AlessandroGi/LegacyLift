"""Tables copied from SQL Server to PostgreSQL. Single source of truth for both scripts.

Each column is written as "SourceName:kind". Kinds: int, text, bool, num, ts, date.
The Photo column of stock items is not copied (extract_from_sqlserver.py checks it is empty).
"""
import re

OLTP = "WideWorldImporters"
DW = "WideWorldImportersDW"

PG_TYPES = {
    "int": "integer",
    "text": "text",
    "bool": "boolean",
    "num": "numeric",
    "ts": "timestamp",
    "date": "date",
}

# Source (OLTP) tables, current and _Archive tables share the same columns.
SUPPLIER = (
    "SupplierID:int, SupplierName:text, SupplierCategoryID:int, PrimaryContactPersonID:int, "
    "SupplierReference:text, PaymentDays:int, DeliveryPostalCode:text, ValidFrom:ts, ValidTo:ts"
)
CATEGORY = "SupplierCategoryID:int, SupplierCategoryName:text, ValidFrom:ts, ValidTo:ts"
PERSON = "PersonID:int, FullName:text, ValidFrom:ts, ValidTo:ts"
ITEM = (
    "StockItemID:int, StockItemName:text, ColorID:int, UnitPackageID:int, OuterPackageID:int, "
    "Brand:text, Size:text, LeadTimeDays:int, QuantityPerOuter:int, IsChillerStock:bool, "
    "Barcode:text, TaxRate:num, UnitPrice:num, RecommendedRetailPrice:num, "
    "TypicalWeightPerUnit:num, ValidFrom:ts, ValidTo:ts"
)
PACKAGE = "PackageTypeID:int, PackageTypeName:text, ValidFrom:ts, ValidTo:ts"
COLOR = "ColorID:int, ColorName:text, ValidFrom:ts, ValidTo:ts"
ORDER = "PurchaseOrderID:int, SupplierID:int, OrderDate:date, LastEditedWhen:ts"
ORDER_LINE = (
    "PurchaseOrderID:int, StockItemID:int, OrderedOuters:int, ReceivedOuters:int, "
    "PackageTypeID:int, IsOrderLineFinalized:bool, LastEditedWhen:ts"
)

# Legacy data warehouse tables, the reference for the comparison.
L_SUPPLIER = (
    "Supplier Key:int, WWI Supplier ID:int, Supplier:text, Category:text, Primary Contact:text, "
    "Supplier Reference:text, Payment Days:int, Postal Code:text, Valid From:ts, Valid To:ts, "
    "Lineage Key:int"
)
L_ITEM = (
    "Stock Item Key:int, WWI Stock Item ID:int, Stock Item:text, Color:text, Selling Package:text, "
    "Buying Package:text, Brand:text, Size:text, Lead Time Days:int, Quantity Per Outer:int, "
    "Is Chiller Stock:bool, Barcode:text, Tax Rate:num, Unit Price:num, "
    "Recommended Retail Price:num, Typical Weight Per Unit:num, Valid From:ts, Valid To:ts, "
    "Lineage Key:int"
)
L_PURCHASE = (
    "Date Key:date, Supplier Key:int, Stock Item Key:int, WWI Purchase Order ID:int, "
    "Ordered Outers:int, Ordered Quantity:int, Received Outers:int, Package:text, "
    "Is Order Finalized:bool, Lineage Key:int"
)

# (database, source table, PostgreSQL schema, PostgreSQL table, columns)
TABLES = [
    (OLTP, "Purchasing.Suppliers", "raw", "suppliers", SUPPLIER),
    (OLTP, "Purchasing.Suppliers_Archive", "raw", "suppliers_archive", SUPPLIER),
    (OLTP, "Purchasing.SupplierCategories", "raw", "supplier_categories", CATEGORY),
    (OLTP, "Purchasing.SupplierCategories_Archive", "raw", "supplier_categories_archive", CATEGORY),
    (OLTP, "Application.People", "raw", "people", PERSON),
    (OLTP, "Application.People_Archive", "raw", "people_archive", PERSON),
    (OLTP, "Warehouse.StockItems", "raw", "stock_items", ITEM),
    (OLTP, "Warehouse.StockItems_Archive", "raw", "stock_items_archive", ITEM),
    (OLTP, "Warehouse.PackageTypes", "raw", "package_types", PACKAGE),
    (OLTP, "Warehouse.PackageTypes_Archive", "raw", "package_types_archive", PACKAGE),
    (OLTP, "Warehouse.Colors", "raw", "colors", COLOR),
    (OLTP, "Warehouse.Colors_Archive", "raw", "colors_archive", COLOR),
    (OLTP, "Purchasing.PurchaseOrders", "raw", "purchase_orders", ORDER),
    (OLTP, "Purchasing.PurchaseOrderLines", "raw", "purchase_order_lines", ORDER_LINE),
    (DW, "Dimension.Supplier", "legacy", "dim_supplier", L_SUPPLIER),
    (DW, "Dimension.[Stock Item]", "legacy", "dim_stock_item", L_ITEM),
    (DW, "Fact.Purchase", "legacy", "fact_purchase", L_PURCHASE),
]


def snake(name):
    """'WWI Supplier ID' -> 'wwi_supplier_id', 'SupplierID' -> 'supplier_id'."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).replace(" ", "_").lower()


def columns(spec):
    """'A:int, B C:text' -> [('A', 'int'), ('B C', 'text')]."""
    return [tuple(c.strip().rsplit(":", 1)) for c in spec.split(",")]
