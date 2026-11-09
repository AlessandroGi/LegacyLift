-- The rebuilt dimension must equal the legacy one on every business column (surrogate keys excluded).
-- Known exception: supplier 3, finding F1 (legacy leaves two open versions); see docs/reverse-engineering.md.
-- Returns the rows found on one side only.
with legacy as (
    select wwi_supplier_id, supplier, category, primary_contact, supplier_reference,
           payment_days, postal_code, valid_from, valid_to
    from {{ source('legacy', 'dim_supplier') }}
    where wwi_supplier_id <> 3
),
rebuilt as (
    select wwi_supplier_id, supplier, category, primary_contact, supplier_reference,
           payment_days, postal_code, valid_from, valid_to
    from {{ ref('dim_supplier') }}
    where wwi_supplier_id <> 3
)
select 'only_legacy' as side, d.* from (select * from legacy except select * from rebuilt) as d
union all
select 'only_rebuilt', d.* from (select * from rebuilt except select * from legacy) as d
