{{ config(materialized='view') }}

select person_id, full_name, valid_from, valid_to
from {{ source('raw', 'people') }}

union all

select person_id, full_name, valid_from, valid_to
from {{ source('raw', 'people_archive') }}