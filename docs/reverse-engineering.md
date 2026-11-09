# Reverse engineering of the Daily ETL: Purchase chain

Version 1, 2026-11-09. Status: draft, updated as the work goes on.

## 1. Scope and method

This document describes how the WideWorldImporters Daily ETL builds three warehouse tables, as read from the code of the sample database:

| Target table | Rows in the reference DW |
|---|---|
| `Fact.Purchase` | 8,367 |
| `Dimension.Supplier` | 28 |
| `Dimension.Stock Item` | 672 (671 versions plus the static "Unknown" row with key 0) |

`Dimension.Date` (1,461 rows) is generated data and is out of scope here.

The reference for the comparison is the populated data warehouse in the sample `.bak` file. All OLTP modifications precede the ETL cutoff (2016-06-06 12:31:17) and the OLTP order lines (8,367) match `Fact.Purchase`, so the DW is the full result of the load.

Every statement below carries one of these statuses:

| Status | Meaning |
|---|---|
| Code | Read in the stored procedure text, not executed |
| Data | Checked with a query on the restored databases |
| Open | Not checked yet |

## 2. Flow overview

```
WideWorldImporters (OLTP)
  Integration.Get<Table>Updates(@LastCutoff, @NewCutoff)     extraction, T-SQL
        |
        v
WideWorldImportersDW
  Integration.<Table>_Staging                                 staging tables
  Integration.MigrateStaged<Table>Data                        load, T-SQL
        |
        v
  Dimension.* / Fact.*                                        warehouse tables
  Integration.Lineage, Integration.[ETL Cutoff]               bookkeeping
```

| Point | Status |
|---|---|
| The extraction and load logic lives in stored procedures, one pair per table | Code |
| The SSIS package orchestrates the calls and fills the staging tables | Open (per Microsoft documentation, the `.dtsx` has not been read) |
| `Dimension.Supplier` and `Dimension.[Stock Item]` are loaded by procedures of the same shape | Code |

## 3. Dimensions: Supplier and Stock Item

Both dimensions keep history (slowly changing dimension type 2): every change creates a new row with its own validity interval.

### 3.1 Extraction (`GetSupplierUpdates`, `GetStockItemUpdates`)

| Step | What it does |
|---|---|
| 1 | Finds the change points: rows of the source table and of its `_Archive` table with `ValidFrom` in (`@LastCutoff`, `@NewCutoff`] |
| 2 | For each change point, reads the entity and its lookups as they were at that instant (`FOR SYSTEM_TIME AS OF`) and inserts one row into a temporary table. Done with cursors, one row at a time |
| 3 | Computes `Valid To` as the smallest `Valid From` of the same entity that is strictly greater, otherwise the end of time (`9999-12-31 23:59:59.9999999`) |
| 4 | Returns the rows. For Stock Item, empty `Color`, `Brand`, `Size` and `Barcode` become `N/A` |

Sources:

| Dimension | Tables (each with its `_Archive`) | Triggers a new version |
|---|---|---|
| Supplier | `Purchasing.Suppliers`, `Purchasing.SupplierCategories`, `Application.People` | Changes of the supplier and of its category. Changes of the contact person do not |
| Stock Item | `Warehouse.StockItems`, `Warehouse.PackageTypes`, `Warehouse.Colors` | Changes of the item only. Changes of package types and colors do not |

Status: Code. The limits in the last column have no effect on this dataset (Section 7).

Column mapping, Supplier: `Supplier` = `SupplierName`, `Category` = `SupplierCategoryName`, `Primary Contact` = `People.FullName`, `Supplier Reference` = `SupplierReference`, `Payment Days` = `PaymentDays`, `Postal Code` = `DeliveryPostalCode`.

Column mapping, Stock Item: `Stock Item` = `StockItemName`, `Color` = `ColorName`, `Selling Package` = name of `UnitPackageID`, `Buying Package` = name of `OuterPackageID`, the other columns keep the source name. `Tax Rate` presumably should come from `TaxRate` (see finding F2).

### 3.2 Load (`MigrateStagedSupplierData`, `MigrateStagedStockItemData`)

| Step | What it does |
|---|---|
| 1 | Takes the open lineage key: the latest `Integration.Lineage` row for the table with `Data Load Completed` empty. Every inserted row carries it |
| 2 | For each business ID present in staging, sets `Valid To` of the open version (`Valid To` = end of time) to the smallest `Valid From` in staging |
| 3 | Inserts all staging rows unchanged. No comparison of columns |
| 4 | Marks the lineage row as completed and moves `Integration.[ETL Cutoff]` |

Everything runs in one transaction with `XACT_ABORT ON`. Status: Code.

Consequence: the load never detects changes. On the first load the dimension is empty, so step 2 closes nothing and the validity dates come exactly as the extraction produced them.

## 4. Fact: Purchase

### 4.1 Extraction (`GetPurchaseUpdates`)

Joins `Purchasing.PurchaseOrders`, `Purchasing.PurchaseOrderLines`, `Warehouse.StockItems` and `Warehouse.PackageTypes`, the last two at their current value (no time travel). Rows are selected when `Last Modified When` is in (`@LastCutoff`, `@NewCutoff`].

| Output column | Source |
|---|---|
| `Date Key` | `CAST(OrderDate AS date)` |
| `WWI Purchase Order ID` | `PurchaseOrderID` |
| `Ordered Outers` | `OrderedOuters` |
| `Ordered Quantity` | `OrderedOuters * QuantityPerOuter` (current value of the item) |
| `Received Outers` | `ReceivedOuters` |
| `Package` | `PackageTypeName` |
| `Is Order Finalized` | `IsOrderLineFinalized` |
| `WWI Supplier ID`, `WWI Stock Item ID` | `SupplierID`, `StockItemID` |
| `Last Modified When` | greater of the line's and the order's `LastEditedWhen` |

`Last Modified When` exists only in staging. It is used to pick dimension versions and is not stored in `Fact.Purchase`. Status: Code.

### 4.2 Load (`MigrateStagedPurchaseData`)

| Step | What it does |
|---|---|
| 1 | Resolves `Supplier Key` and `Stock Item Key`: the dimension version of the same business ID with `Valid From` < `Last Modified When` <= `Valid To`, `TOP(1)` ordered by `Valid From`, otherwise key 0 ("Unknown") |
| 2 | Deletes from `Fact.Purchase` all rows of the orders present in staging, by `WWI Purchase Order ID` alone |
| 3 | Inserts all current lines of those orders |
| 4 | Lineage and cutoff, as for the dimensions |

Status: Code. Grain: `WWI Purchase Order ID` plus `Stock Item Key` is unique (8,367 rows, 8,367 distinct pairs). Status: Data.

## 5. Boundary rules that differ

| Where | Rule |
|---|---|
| `FOR SYSTEM_TIME AS OF t` in the extraction | `ValidFrom <= t` and `t < ValidTo` |
| Key resolution in `MigrateStagedPurchaseData` | `Valid From < t` and `t <= Valid To` |

Both must be reproduced as they are in the new models.

## 6. Findings

| ID | Object | Finding | Type | Status |
|---|---|---|---|---|
| F1 | `Dimension.Supplier`, supplier 3 | Versions with keys 16 and 27 overlap: same `Valid From` (2013-01-01 00:05), both open. Supplier 3 has no purchase orders, so no row of `Fact.Purchase` is affected | Legacy error | Code and Data |
| F2 | `Dimension.[Stock Item]`, `Tax Rate` | Contains `Lead Time Days`. In the 227 current versions, 227 equal `Lead Time Days` and 0 equal the OLTP `TaxRate` | Legacy error | Code and Data (current versions only) |
| F3 | End-of-time value | `9999-12-31 23:59:59.9999999` becomes `10000-01-01 00:00:00` in PostgreSQL 16 | Engine difference | Data |

F1, cause: in the category-change cursor of `GetSupplierUpdates` the inserted `Valid From` is the supplier row's own `ValidFrom` instead of the instant of the category change. The category of supplier 3 was renamed on 2015-01-01 16:00, but the supplier row had not changed since 2013-01-01 00:05, so the new version got the old date. The `Valid To` update then closes a row only when another row of the same supplier has a strictly greater `Valid From`. Here both rows have the same one, so neither is closed. Smallest fix in the legacy code: use `@ValidFrom` in place of `s.ValidFrom` in that cursor.

F2, cause: in `GetStockItemUpdates`, `si.LeadTimeDays` appears twice in the select list, and the second occurrence sits in the position of `Tax Rate`.

F3, cause: `datetime2(7)` keeps 7 decimals, PostgreSQL `timestamp` keeps 6 and rounds. The legacy code finds open versions with `Valid To = @EndOfTime`, an exact equality. Proposed rule: truncate (not round) to 6 decimals every time column when copying data, so the end of time becomes `9999-12-31 23:59:59.999999`.

Treatment of F1 and F2 in the new implementation: apply the correct logic and list the difference among the known and accepted ones.

## 7. Limits of the legacy code without effect on this dataset

| Limit | Check | Result |
|---|---|---|
| Changes to `Warehouse.Colors` do not create item versions | Archive rows with `ValidFrom` from 2013-01-02 | 0 |
| Changes to `Warehouse.PackageTypes` do not create item versions | Same | 0 |
| Changes to a contact person do not create supplier versions | Full name of the 13 supplier contacts with later versions | Never changes in the history |

Note for comparisons: at least one contact has a double space in the full name in the source. Do not trim or normalize whitespace when comparing.

## 8. Notes for the dbt and PostgreSQL implementation

Proposed, not implemented yet.

| T-SQL construct | Proposed translation |
|---|---|
| Cursors that insert one row per change point | One set-based query: union of change points, join to each history table on the validity interval |
| `FOR SYSTEM_TIME AS OF` | Join on `valid_from <= t and t < valid_to` over current plus archive rows |
| `Valid To` from `MIN(Valid From)` of later rows | `lead(valid_from)` window function per business ID |
| `TOP(1) ... ORDER BY [Valid From]` | Window function or lateral join with a deterministic order |
| `datetime2(7)` | `timestamp` with truncation to 6 decimals |
| `bit` | `boolean` |
| `ISNULL(x, N'N/A')` | `coalesce(x, 'N/A')` |
| Row with key 0 ("Unknown") | Seed with the static values |
| Correct versions (F1) | `Valid From` = later of the supplier start and the category start, `Valid To` = next `Valid From` |
| Incremental mechanism (close, delete, insert) | Out of the MVP: models rebuild the tables in full, which gives the same final result |

## 9. Open points

| Point | Next step |
|---|---|
| Does the SSIS package call the extraction procedures as assumed | Read the `.dtsx` |
| Is there an "Unknown" row also in `Dimension.Supplier` (28 rows) | Query on key 0 |
| Source columns needed in the raw schema | Tables of Section 3.1 and 4.1, with archive tables, time columns truncated to 6 decimals |
