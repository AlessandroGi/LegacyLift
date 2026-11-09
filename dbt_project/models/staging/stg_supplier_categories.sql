{{ config(materialized='view') }}

select supplier_category_id, supplier_category_name, valid_from, valid_to
from {{ source('raw', 'supplier_categories') }}

union all

select supplier_category_id, supplier_category_name, valid_from, valid_to
from {{ source('raw', 'supplier_categories_archive') }}