{{ config(materialized='view') }}

-- Every version of every supplier: the current table plus its temporal history table.
select supplier_id, supplier_name, supplier_category_id, primary_contact_person_id,
       supplier_reference, payment_days, delivery_postal_code, valid_from, valid_to
from {{ source('raw', 'suppliers') }}

union all

select supplier_id, supplier_name, supplier_category_id, primary_contact_person_id,
       supplier_reference, payment_days, delivery_postal_code, valid_from, valid_to
from {{ source('raw', 'suppliers_archive') }}